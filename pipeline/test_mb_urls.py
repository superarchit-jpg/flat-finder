"""Regression tests for whitespace introduced into Magicbricks project URLs."""
from mb_crawl import normalize_url


def test_nonbreaking_space_does_not_create_double_hyphen():
    raw = "https://www.magicbricks.com/cgewho-kendriya-vihar-2\u00a0-sector-82-noida-pdpid-123"
    assert normalize_url(raw) == "https://www.magicbricks.com/cgewho-kendriya-vihar-2-sector-82-noida-pdpid-123"


def test_clean_url_unchanged():
    url = "https://www.magicbricks.com/prateek-canary-sector-150-noida-pdpid-123"
    assert normalize_url(url) == url
