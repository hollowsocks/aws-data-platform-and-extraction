from datetime import datetime

from dateutil import tz

from triplewhale_ingestion.sql_loader import (
    _hour_to_utc,
    _region_from_ad_row,
    _region_from_country,
    _tokenize_ad_text,
)


def test_region_from_country_maps_gb_to_uk():
    assert _region_from_country("GB") == "UK"
    assert _region_from_country("US") == "US"
    assert _region_from_country("CA") == "CA"
    assert _region_from_country("au") == "AU"
    assert _region_from_country("LV") is None


def test_tokenizer_splits_on_non_alnum():
    tokens = _tokenize_ad_text(["02_Prospecting_MM_JSD_SCALE-CA-CBO_Tag-Hero"])
    assert "CA" in tokens
    assert "SCALE" in tokens


def test_region_inferred_from_ad_row_uses_account_map_first():
    row = {
        "account_id": "act_123",
        "campaign_name": "Generic Campaign",
        "adset_name": "Generic Adset",
        "ad_name": None,
    }
    assert _region_from_ad_row(row, {"act_123": "UK"}) == "UK"


def test_region_inferred_from_keywords():
    row = {
        "account_id": "act_999",
        "campaign_name": "02_Prospecting_MM_JSD_SCALE-AU-CBO_Tag-Hero",
        "adset_name": "AU-TopAds_interest-layered-stack_M35+_7DC1DV",
        "ad_name": None,
    }
    assert _region_from_ad_row(row, {}) == "AU"


def test_hour_to_utc_localises_and_converts():
    chicago = tz.gettz("America/Chicago")
    naive = "2025-10-14 23:00:00"
    ts_utc = _hour_to_utc(naive, chicago)
    assert ts_utc.tzinfo == tz.UTC
    assert ts_utc.hour in {4, 5}
