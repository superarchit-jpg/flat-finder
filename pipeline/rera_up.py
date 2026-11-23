"""Conservative matching of independently checked UP RERA filings.

A portal registration number alone is never confirmation. Research records must be
manually cross-checked against the official project register first.
"""
import json
import re

RERA_SITE = "https://www.up-rera.in/"
ID = re.compile(r"^UPRERAPRJ[0-9]+$", re.I)


def normalized(value):
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def annotate(societies, registry_path):
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else {"projects": []}
    entries = {}
    for item in registry.get("projects", []):
        identifier = str(item.get("registration_id", "")).strip().upper()
        if not ID.fullmatch(identifier):
            raise ValueError("Invalid UP RERA registration ID in registry")
        source = item.get("official_url", "")
        if not source.startswith(("https://up-rera.in/", "https://www.up-rera.in/")):
            raise ValueError("RERA evidence must link to the official UP RERA website")
        if not item.get("official_name") or not item.get("locality") or not item.get("checked_on"):
            raise ValueError("RERA evidence requires name, locality and review date")
        if identifier in entries:
            raise ValueError("Duplicate RERA entry: " + identifier)
        entries[identifier] = item

    counts = {"verified": 0, "portal_only": 0, "missing": 0}
    for society in societies:
        raw = str(society.get("rera_id") or "").strip().upper()
        match = ID.search(raw) if raw else None
        identifier = match.group(0) if match else None
        row = entries.get(identifier) if identifier else None
        check = {"status": "not_checked", "registration_id": identifier, "source": RERA_SITE}
        if row:
            # Do not silently join distinct phases sharing a development name.
            actual = normalized(society.get("name"))
            official = normalized(row["official_name"])
            locality = normalized(society.get("locality"))
            matched_name = official == actual or normalized(row.get("portal_name")) == actual
            matched_area = normalized(row["locality"]) in locality if locality else False
            if matched_name and matched_area:
                check = {"status": "verified", "registration_id": identifier,
                         "official_name": row["official_name"], "source": row["official_url"],
                         "checked_on": row["checked_on"]}
                counts["verified"] += 1
            else:
                check["status"] = "conflict"
        elif identifier:
            counts["portal_only"] += 1
        else:
            counts["missing"] += 1
        society["rera_verification"] = check
    print("UP RERA cross-check:", counts)
    return counts
