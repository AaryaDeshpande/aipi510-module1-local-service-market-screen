"""Inspect selected source rows and summarize the engineered market screen.

This is an exploratory check, not an opportunity ranking. Run after
build_market_screen.py; it writes a small machine-readable QA summary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / "data/processed/local_service_market_screen.csv"
OUTPUT = ROOT / "data/processed/eda_summary.json"
METRICS = [
    "small_establishments",
    "small_establishment_share",
    "avg_employees_per_establishment",
    "admin_employment_share",
    "admin_mean_wage",
    "estimated_admin_payroll_per_establishment",
]


def summarize(data: pd.DataFrame) -> dict:
    if data["industry"].duplicated().any():
        raise ValueError("Duplicate industry in processed data")
    summary: dict = {
        "industry_count": int(len(data)),
        "missing_values": {key: int(value) for key, value in data.isna().sum().items()},
        "metric_summary": {},
        "iqr_outliers": {},
        "source_employment_ratio": {},
    }
    for metric in METRICS:
        series = pd.to_numeric(data[metric], errors="raise")
        q1, q3 = series.quantile([0.25, 0.75])
        iqr = q3 - q1
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        summary["metric_summary"][metric] = {
            "min": float(series.min()),
            "median": float(series.median()),
            "max": float(series.max()),
        }
        summary["iqr_outliers"][metric] = data.loc[
            (series < low) | (series > high), "industry"
        ].tolist()

    # Not expected to equal one: CBP is 2023 administrative data and OEWS is a
    # modeled May 2025 survey estimate covering wage/salary employment.
    ratio = data["oews_total_employment"] / data["cbp_total_employment"]
    summary["source_employment_ratio"] = {
        "min": float(ratio.min()),
        "median": float(ratio.median()),
        "max": float(ratio.max()),
        "largest_gap_industry": str(data.loc[(ratio - 1).abs().idxmax(), "industry"]),
    }
    return summary


def main() -> None:
    data = pd.read_csv(SCREEN)
    summary = summarize(data)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"EDA summary: {len(data)} industries; {sum(summary['missing_values'].values())} missing cells")
    for metric, industries in summary["iqr_outliers"].items():
        if industries:
            print(f"IQR flag for {metric}: {', '.join(industries)}")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
