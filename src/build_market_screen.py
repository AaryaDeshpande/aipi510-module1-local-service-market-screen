"""Build a transparent local-service market screen from Census CBP and BLS OEWS.

Run from the repository root: python src/build_market_screen.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from load_cbp import load_cbp, validate_naics_scope
from load_oews import load_oews


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAPPING = ROOT / "config/industry_crosswalk.csv"
DEFAULT_CBP = ROOT / "data/raw/cbp23us.zip"
DEFAULT_CONCORDANCE = ROOT / "data/raw/naics_2022_to_2017.xlsx"
DEFAULT_OEWS = ROOT / "data/raw/oews_2025.json"
DEFAULT_OUTPUT = ROOT / "data/processed/local_service_market_screen.csv"

OUTPUT_COLUMNS = [
    "industry",
    "cbp_naics_2017",
    "bls_naics_2022",
    "scope_note",
    "cbp_year",
    "oews_reference_year",
    "total_establishments",
    "establishments_lt5",
    "establishments_5_9",
    "establishments_10_19",
    "small_establishments",
    "market_depth",
    "small_establishment_share",
    "cbp_total_employment",
    "avg_employees_per_establishment",
    "oews_total_employment",
    "oews_admin_employment",
    "admin_employment_share",
    "admin_mean_wage",
    "estimated_admin_payroll_per_establishment",
]


def build_market_screen(
    mapping_path: Path = DEFAULT_MAPPING,
    cbp_path: Path = DEFAULT_CBP,
    concordance_path: Path = DEFAULT_CONCORDANCE,
    oews_path: Path = DEFAULT_OEWS,
) -> pd.DataFrame:
    mapping = pd.read_csv(
        mapping_path, dtype={"cbp_naics_2017": str, "bls_naics_2022": str}
    )
    if (
        mapping["industry"].duplicated().any()
        or mapping["cbp_naics_2017"].duplicated().any()
        or mapping["bls_naics_2022"].duplicated().any()
    ):
        raise ValueError("Industry mapping contains duplicate labels or NAICS codes")
    validate_naics_scope(mapping, concordance_path)

    census = load_cbp(cbp_path, mapping)
    oews = load_oews(oews_path, mapping["bls_naics_2022"])
    joined = census.merge(oews, on="bls_naics_2022", validate="one_to_one")
    if len(joined) != len(mapping):
        raise ValueError("Source join omitted an industry")

    # Explicit plan alias: potential reach among small employer locations.
    joined["market_depth"] = joined["small_establishments"]
    # Directional cross-source proxy, not observed payroll or addressable spend.
    joined["estimated_admin_payroll_per_establishment"] = (
        joined["avg_employees_per_establishment"]
        * joined["admin_employment_share"]
        * joined["admin_mean_wage"]
    )
    joined["cbp_year"] = 2023
    joined["oews_reference_year"] = 2025

    if joined[OUTPUT_COLUMNS].isna().any().any():
        raise ValueError("Missing value in output")
    if not joined["small_establishment_share"].between(0, 1).all():
        raise ValueError("Invalid share of small establishments")
    if not joined["admin_employment_share"].between(0, 1).all():
        raise ValueError("Invalid administrative employment share")
    return joined[OUTPUT_COLUMNS].sort_values("industry").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--cbp", type=Path, default=DEFAULT_CBP)
    parser.add_argument("--concordance", type=Path, default=DEFAULT_CONCORDANCE)
    parser.add_argument("--oews", type=Path, default=DEFAULT_OEWS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    screen = build_market_screen(args.mapping, args.cbp, args.concordance, args.oews)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    screen.to_csv(args.output, index=False, float_format="%.6f")
    print(f"Wrote {len(screen)} industries to {args.output}")


if __name__ == "__main__":
    main()
