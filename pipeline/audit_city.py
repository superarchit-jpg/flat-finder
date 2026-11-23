"""Audit generated city data without pretending that portal facts are verified.

Usage: python pipeline/audit_city.py noida [--strict]
Outputs pipeline/out/<city>/audit.json, used by CI and human review.
Strict mode fails on structural errors, not simply on missing independent
evidence; review-required records remain explicitly unverified.
"""
import json
import math
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def check(city):
    cfg = json.loads((ROOT / "data/cities.json").read_text())[city]
    base = ROOT / "web/public/data"
    doc = json.loads((base / (city + ".json")).read_text())
    details = json.loads((base / (city + "-details.json")).read_text())
    shapes = json.loads((base / (city + "-shapes.geojson")).read_text())
    south, west, north, east = cfg["bbox"]
    fatal, findings = [], []
    counts = Counter()
    seen = set()

    def flag(s, field, reason, severity="review"):
        findings.append({"id": s.get("id"), "name": s.get("name"),
                         "field": field, "severity": severity, "reason": reason})
        counts[field + ":" + severity] += 1
        if severity == "error":
            fatal.append(s.get("id", "?") + ": " + field + ": " + reason)

    for s in doc.get("societies", []):
        sid = s.get("id")
        if not sid or sid in seen:
            flag(s, "id", "Missing or duplicate society identifier", "error")
        seen.add(sid)
        lat, lng = s.get("lat"), s.get("lng")
        if not number(lat) or not number(lng) or not south <= lat <= north or not west <= lng <= east:
            flag(s, "location", "Missing or outside declared city bounds", "error")
        else:
            counts["geocoded"] += 1
        if not s.get("locality"):
            flag(s, "location", "No locality; coordinates require manual confirmation")
        if not str(s.get("url") or "").startswith("https://"):
            flag(s, "source", "Property page source missing/invalid", "error")
        if not s.get("osm_area"):
            flag(s, "location", "No independent named OSM site match; map point unconfirmed")
        rera = s.get("rera_verification", {})
        if rera.get("status") == "verified":
            if not str(rera.get("source") or "").startswith("https://"):
                flag(s, "rera", "Verified RERA entry has no cited source", "error")
            counts["rera_verified"] += 1
        else:
            flag(s, "rera", "UP RERA registration not independently confirmed")
        if not s.get("amenities"):
            flag(s, "amenities", "No portal amenities supplied")
        elif not s.get("amen_facts"):
            flag(s, "amenities", "Portal claims only; no independent amenity evidence")
        else:
            counts["amenity_facts"] += 1
        prices = s.get("prices") or {}
        if not prices:
            flag(s, "prices", "No BHK-specific prices")
        for bhk, entry in prices.items():
            for category in ("buy", "rent", "buy_est", "rent_est"):
                value = (entry.get(category) or {})
                if not value:
                    continue
                observed = value.get("median") if category in ("buy", "rent") else value.get("value")
                if observed is not None and (not number(observed) or observed <= 0):
                    flag(s, "prices", bhk + " BHK " + category + " non-positive/non-finite", "error")
                if category.endswith("_est"):
                    counts["estimated_price_entries"] += 1
                else:
                    counts["portal_price_entries"] += 1
            if entry.get("flags"):
                flag(s, "prices", "Portal price flagged as potential outlier: " + str(entry["flags"]))
        units = s.get("unit_types") or []
        if not units:
            flag(s, "floor_plans", "No unit configurations")
        for unit in units:
            beds = unit.get("bedrooms") or []
            if unit.get("rooms_complete") and not beds:
                flag(s, "floor_plans", "Marked complete without bedroom measurements", "error")
            if unit.get("rooms_complete") and unit.get("bhk") and len(beds) < unit["bhk"] and not unit.get("others_larger"):
                flag(s, "floor_plans", "Marked complete with fewer bedrooms than BHK", "error")
            if beds and not unit.get("source"):
                flag(s, "floor_plans", "Bedroom measurements without source", "error")
            for room in beds:
                if len(room) != 2 or not all(number(x) and x > 0 for x in room):
                    flag(s, "floor_plans", "Invalid bedroom measurements", "error")
            if beds:
                counts["measured_unit_types"] += 1
            else:
                counts["unmeasured_unit_types"] += 1
        if sid not in details:
            flag(s, "details", "Society detail record missing", "error")

    if doc.get("city", {}).get("id") != city:
        fatal.append("Output city ID differs from requested city")
    if doc.get("counts", {}).get("on_map") != len(doc.get("societies", [])):
        fatal.append("On-map count differs from actual number of societies")
    if shapes.get("type") != "FeatureCollection":
        fatal.append("Shapes must be a GeoJSON FeatureCollection")
    if not doc.get("societies"):
        fatal.append("No properties collected")
    report = {
        "city": city,
        "source": "Generated Magicbricks/OSM data; no independently verified facts implied",
        "counts": {"societies": len(doc.get("societies", [])), **dict(counts)},
        "errors": fatal,
        "review_queue": findings,
        "note": "RERA, amenity and floor-plan review warnings are not confirmations."
    }
    out = ROOT / "pipeline/out" / city
    out.mkdir(parents=True, exist_ok=True)
    (out / "audit.json").write_text(json.dumps(report, indent=2))
    print("NOIDA audit:", json.dumps(report["counts"], indent=2))
    print("Structural errors:", len(fatal), "Review findings:", len(findings))
    return len(fatal)


if __name__ == "__main__":
    target = next((a for a in sys.argv[1:] if not a.startswith("--")), "noida")
    n = check(target)
    if "--strict" in sys.argv and n:
        sys.exit(1)
