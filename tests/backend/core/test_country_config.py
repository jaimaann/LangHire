"""Unit tests for backend/core/country_config.py.

Validates the COUNTRY_CONFIGS structure, the SUPPORTED_COUNTRIES /
NOTICE_PERIOD_OPTIONS exports, and get_country_config lookup + fallback.
"""
import pytest

from core import country_config as cc


def test_supported_countries_matches_configs():
    """SUPPORTED_COUNTRIES is exactly the config keys."""
    assert cc.SUPPORTED_COUNTRIES == list(cc.COUNTRY_CONFIGS.keys())
    assert "US" in cc.SUPPORTED_COUNTRIES


def test_us_is_present_as_fallback_anchor():
    """The US config must exist since it is the fallback target."""
    assert "US" in cc.COUNTRY_CONFIGS


@pytest.mark.parametrize("code", list(cc.COUNTRY_CONFIGS.keys()))
def test_every_config_has_required_keys(code):
    """Every country config exposes the full set of required keys/types."""
    cfg = cc.COUNTRY_CONFIGS[code]
    required = {
        "name": str,
        "flag": str,
        "date_format": str,
        "currency": str,
        "salary_period": str,
        "address_labels": dict,
        "work_auth_options": list,
        "show_notice_period": bool,
        "show_nationality": bool,
        "show_cover_letter": bool,
        "show_photo": bool,
        "show_date_of_birth": bool,
        "phone_prefix": str,
        "default_sources": list,
        "default_language": str,
    }
    for key, typ in required.items():
        assert key in cfg, f"{code} missing {key}"
        assert isinstance(cfg[key], typ), f"{code}.{key} should be {typ}"
    assert cfg["work_auth_options"], f"{code} has no work_auth_options"
    assert cfg["default_sources"], f"{code} has no default_sources"
    assert {"state", "zip"} <= cfg["address_labels"].keys()
    assert cfg["phone_prefix"].startswith("+")
    assert cfg["salary_period"] in ("annual", "monthly")


def test_get_country_config_known():
    """A known code returns its own config object (identity)."""
    assert cc.get_country_config("GB") is cc.COUNTRY_CONFIGS["GB"]
    assert cc.get_country_config("DE")["currency"] == "EUR"


@pytest.mark.parametrize("bad", ["XX", "", "us", "USA", None.__class__.__name__])
def test_get_country_config_unknown_falls_back_to_us(bad):
    """Unknown / mis-cased codes fall back to the US config."""
    assert cc.get_country_config(bad) is cc.COUNTRY_CONFIGS["US"]


def test_get_country_config_us_identity():
    """Requesting US returns the US config itself."""
    assert cc.get_country_config("US") is cc.COUNTRY_CONFIGS["US"]


def test_notice_period_options_structure():
    """NOTICE_PERIOD_OPTIONS is a non-empty list of strings ending in 'Other'."""
    assert isinstance(cc.NOTICE_PERIOD_OPTIONS, list)
    assert all(isinstance(o, str) for o in cc.NOTICE_PERIOD_OPTIONS)
    assert "Immediate" in cc.NOTICE_PERIOD_OPTIONS
    assert cc.NOTICE_PERIOD_OPTIONS[-1] == "Other"


def test_currency_codes_are_three_letters():
    """Currency codes look like ISO 4217 (three uppercase letters)."""
    for code, cfg in cc.COUNTRY_CONFIGS.items():
        cur = cfg["currency"]
        assert len(cur) == 3 and cur.isupper(), f"{code} currency {cur!r}"
