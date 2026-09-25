"""Small invariants that catch common join and feature-engineering mistakes."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from build_market_screen import build_market_screen  # noqa: E402
from load_cbp import validate_naics_scope  # noqa: E402
from load_oews import load_oews, make_series_id  # noqa: E402


def test_bls_series_id() -> None:
    assert make_series_id("621200", "43-0000", "01") == "OEUN000000062120043000001"


def test_selected_naics_crosswalk() -> None:
    mapping = pd.read_csv(ROOT / "config/industry_crosswalk.csv", dtype=str)
    validate_naics_scope(mapping, ROOT / "data/raw/naics_2022_to_2017.xlsx")


def test_official_snapshot_has_real_estimates() -> None:
    oews = load_oews(ROOT / "data/raw/oews_2025.json")
    assert len(oews) == 12
    assert oews["admin_employment_share"].between(0, 1).all()
    dental = oews.set_index("bls_naics_2022").loc["621200"]
    assert dental["oews_admin_employment"] == 297_210
    assert dental["admin_mean_wage"] == 51_480


def test_build_features_and_sanity_checks() -> None:
    data = build_market_screen()
    assert len(data) == 12
    assert data["industry"].is_unique
    assert data["small_establishments"].le(data["total_establishments"]).all()
    assert data["market_depth"].equals(data["small_establishments"])
    expected = (
        data["avg_employees_per_establishment"]
        * data["admin_employment_share"]
        * data["admin_mean_wage"]
    )
    assert (data["estimated_admin_payroll_per_establishment"] - expected).abs().max() < 1e-7
    dental = data.set_index("industry").loc["Dental offices"]
    assert dental["total_establishments"] == 135_665
    assert dental["small_establishments"] == 129_008
    assert dental["small_establishment_share"] == pytest.approx(0.9509, abs=1e-4)
