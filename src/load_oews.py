"""Fetch and validate May 2025 national, industry-specific OEWS estimates.

For each selected industry, the BLS API supplies three published estimates:
employment across all occupations (SOC 00-0000), employment in office and
administrative support (SOC 43-0000), and the latter group's annual mean wage.
The administrative employment share is calculated from the two employment
estimates. BLS rounds employment estimates, so that share is approximate.

The saved JSON is a small, inspectable source snapshot. Subsequent runs use the
snapshot unless --refresh is passed, avoiding unnecessary API requests.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_TABLE_URL = "https://www.bls.gov/oes/2025/may/oessrci.htm"
BLS_METHODS_URL = "https://www.bls.gov/oes/2025/may/oes_tec.htm"
DATA_YEAR = "2025"
DATA_PERIOD = "A01"  # OEWS annual May estimate in the BLS time-series API.
MAX_SERIES_PER_REQUEST = 24  # Below the unregistered API limit of 25.
DEFAULT_RAW_PATH = Path(__file__).resolve().parents[1] / "data/raw/oews_2025.json"

# OEWS industry codes are six characters; some four-digit NAICS industries are
# padded with two zeroes. Match these explicitly to CBP's 2017 NAICS rows.
INDUSTRIES: dict[str, str] = {
    "621200": "Offices of Dentists",
    "541940": "Veterinary Services",
    "621310": "Offices of Chiropractors",
    "621320": "Offices of Optometrists",
    "621340": "Offices of Physical, Occupational and Speech Therapists, and Audiologists",
    "541100": "Legal Services",
    "541200": "Accounting, Tax Preparation, Bookkeeping, and Payroll Services",
    "811100": "Automotive Repair and Maintenance",
    "238210": "Electrical Contractors and Other Wiring Installation Contractors",
    "238220": "Plumbing, Heating, and Air-Conditioning Contractors",
    "561730": "Landscaping Services",
    "621600": "Home Health Care Services",
}

MEASURES: dict[str, tuple[str, str]] = {
    "total_employment": ("00-0000", "01"),
    "admin_employment": ("43-0000", "01"),
    "admin_annual_mean_wage": ("43-0000", "04"),
}


def make_series_id(industry_code: str, occupation_code: str, datatype: str) -> str:
    """Construct an OEWS national time-series ID from BLS's published format."""
    occupation = occupation_code.replace("-", "")
    if len(industry_code) != 6 or not industry_code.isdigit():
        raise ValueError(f"Expected a six-digit OEWS industry code: {industry_code!r}")
    if len(occupation) != 6 or not occupation.isdigit():
        raise ValueError(f"Expected a six-digit SOC code: {occupation_code!r}")
    if datatype not in {"01", "04"}:
        raise ValueError(f"Unsupported OEWS datatype: {datatype!r}")
    return "OEUN0000000" + industry_code + occupation + datatype


def _series_lookup() -> dict[str, tuple[str, str]]:
    return {
        make_series_id(code, occupation, datatype): (code, measure)
        for code in INDUSTRIES
        for measure, (occupation, datatype) in MEASURES.items()
    }


def _post_api(series_ids: list[str], *, timeout: int = 45) -> dict[str, Any]:
    payload = json.dumps(
        {"seriesid": series_ids, "startyear": DATA_YEAR, "endyear": DATA_YEAR}
    ).encode("utf-8")
    request = Request(
        BLS_API_URL,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "AIPI510-public-data-analysis/1.0",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"BLS API request failed: {exc}") from exc
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("BLS API returned non-JSON content") from exc
    if not isinstance(parsed, dict):
        raise ValueError("BLS API returned an unexpected JSON structure")
    return parsed


def _parse_batch(response: dict[str, Any], expected: set[str]) -> dict[str, dict[str, Any]]:
    if response.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(
            f"BLS API status {response.get('status')!r}: {response.get('message')!r}"
        )
    results = response.get("Results")
    if not isinstance(results, dict) or not isinstance(results.get("series"), list):
        raise ValueError("BLS API response is missing Results.series")

    found: dict[str, dict[str, Any]] = {}
    for series in results["series"]:
        if not isinstance(series, dict):
            raise ValueError("BLS API series entry is not an object")
        sid = series.get("seriesID")
        if sid not in expected:
            raise ValueError(f"Unexpected BLS series ID: {sid!r}")
        if sid in found:
            raise ValueError(f"Duplicate BLS series ID: {sid}")
        observations = series.get("data")
        if not isinstance(observations, list):
            raise ValueError(f"Missing observations for BLS series {sid}")
        matching = [
            item
            for item in observations
            if isinstance(item, dict)
            and item.get("year") == DATA_YEAR
            and item.get("period") == DATA_PERIOD
        ]
        if len(matching) != 1:
            raise ValueError(
                f"Expected exactly one May {DATA_YEAR} observation for {sid}; "
                f"found {len(matching)}"
            )
        item = matching[0]
        raw_value = item.get("value")
        try:
            value = int(str(raw_value).replace(",", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Missing or suppressed BLS value for {sid}: {raw_value!r}") from exc
        if value <= 0:
            raise ValueError(f"Nonpositive BLS value for {sid}: {value}")
        footnotes = item.get("footnotes", [])
        if not isinstance(footnotes, list):
            raise ValueError(f"Unexpected BLS footnotes for {sid}")
        found[sid] = {"value": value, "footnotes": footnotes}

    missing = expected - found.keys()
    if missing:
        raise ValueError(f"BLS API omitted series: {', '.join(sorted(missing))}")
    return found


def fetch_oews_snapshot() -> dict[str, Any]:
    """Download all 36 estimates in two unregistered BLS API requests."""
    lookup = _series_lookup()
    series_ids = list(lookup)
    observations: dict[str, dict[str, Any]] = {}
    for start in range(0, len(series_ids), MAX_SERIES_PER_REQUEST):
        batch = series_ids[start : start + MAX_SERIES_PER_REQUEST]
        observations.update(_parse_batch(_post_api(batch), set(batch)))

    records = []
    for code, title in INDUSTRIES.items():
        measures: dict[str, Any] = {}
        series: dict[str, str] = {}
        for measure, (occupation, datatype) in MEASURES.items():
            sid = make_series_id(code, occupation, datatype)
            measures[measure] = observations[sid]["value"]
            series[measure] = sid
        records.append(
            {
                "oews_industry_code": code,
                "industry_title": title,
                **measures,
                "series_ids": series,
            }
        )

    snapshot = {
        "source": "U.S. Bureau of Labor Statistics, Occupational Employment and Wage Statistics",
        "source_url": BLS_TABLE_URL,
        "api_url": BLS_API_URL,
        "methods_url": BLS_METHODS_URL,
        "reference_year": int(DATA_YEAR),
        "period": DATA_PERIOD,
        "naics_version": 2022,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "notes": (
            "Employment estimates are rounded by BLS. Office/administrative share "
            "is derived as SOC 43-0000 employment divided by SOC 00-0000 employment "
            "within the same OEWS industry; it is not a separately downloaded estimate."
        ),
        "records": records,
    }
    parse_oews_snapshot(snapshot)  # Validate before saving.
    return snapshot


def parse_oews_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return validated, analysis-ready rows from a saved source snapshot."""
    if not isinstance(snapshot, dict):
        raise ValueError("OEWS snapshot must be a JSON object")
    if snapshot.get("reference_year") != 2025 or snapshot.get("period") != DATA_PERIOD:
        raise ValueError("OEWS snapshot is not the May 2025 estimate")
    if snapshot.get("naics_version") != 2022:
        raise ValueError("OEWS snapshot must use 2022 NAICS")
    records = snapshot.get("records")
    if not isinstance(records, list) or len(records) != len(INDUSTRIES):
        raise ValueError("OEWS snapshot has an unexpected number of industries")
    output = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("OEWS record must be an object")
        code = record.get("oews_industry_code")
        if code not in INDUSTRIES or code in seen:
            raise ValueError(f"Unknown or duplicate OEWS industry code: {code!r}")
        seen.add(code)
        if record.get("industry_title") != INDUSTRIES[code]:
            raise ValueError(f"Unexpected industry title for OEWS code {code}")
        ids = record.get("series_ids")
        if not isinstance(ids, dict):
            raise ValueError(f"Missing BLS series IDs for {code}")
        values: dict[str, int] = {}
        for measure, (occupation, datatype) in MEASURES.items():
            if ids.get(measure) != make_series_id(code, occupation, datatype):
                raise ValueError(f"Incorrect BLS {measure} series ID for {code}")
            value = record.get(measure)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"Invalid {measure} estimate for {code}: {value!r}")
            values[measure] = value
        if values["admin_employment"] > values["total_employment"]:
            raise ValueError(f"Admin employment exceeds total employment for {code}")
        output.append(
            {
                "oews_industry_code": code,
                "industry_title": INDUSTRIES[code],
                **values,
                "admin_employment_share": (
                    values["admin_employment"] / values["total_employment"]
                ),
            }
        )
    if seen != set(INDUSTRIES):
        raise ValueError("OEWS snapshot is missing expected industries")
    return output


def load_snapshot(path: Path = DEFAULT_RAW_PATH, *, refresh: bool = False) -> dict[str, Any]:
    """Use a validated local source snapshot, fetching it when necessary."""
    path = Path(path)
    if refresh or not path.exists():
        snapshot = fetch_oews_snapshot()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    else:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    parse_oews_snapshot(snapshot)
    return snapshot


def load_oews(
    path: Path = DEFAULT_RAW_PATH,
    industry_codes: Iterable[str] | None = None,
    *,
    refresh: bool = False,
):
    """Return selected OEWS industries as a pandas DataFrame.

    The local JSON snapshot is used if present. Missing snapshots are fetched
    from the BLS API; pass refresh=True to explicitly replace one.
    """
    import pandas as pd

    records = parse_oews_snapshot(load_snapshot(path, refresh=refresh))
    requested = list(INDUSTRIES if industry_codes is None else industry_codes)
    if len(requested) != len(set(requested)):
        raise ValueError("Duplicate OEWS industry code requested")
    unknown = set(requested) - set(INDUSTRIES)
    if unknown:
        raise ValueError(f"Unknown OEWS industry code(s): {', '.join(sorted(unknown))}")
    by_code = {row["oews_industry_code"]: row for row in records}
    return pd.DataFrame(
        [
            {
                "bls_naics_2022": code,
                "oews_total_employment": by_code[code]["total_employment"],
                "oews_admin_employment": by_code[code]["admin_employment"],
                "admin_mean_wage": by_code[code]["admin_annual_mean_wage"],
                "admin_employment_share": by_code[code]["admin_employment_share"],
            }
            for code in requested
        ],
        columns=[
            "bls_naics_2022",
            "oews_total_employment",
            "oews_admin_employment",
            "admin_mean_wage",
            "admin_employment_share",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_RAW_PATH)
    parser.add_argument("--fetch", action="store_true", help="Fetch a fresh BLS API snapshot")
    args = parser.parse_args()
    rows = parse_oews_snapshot(load_snapshot(args.input, refresh=args.fetch))
    print(f"Validated {len(rows)} May 2025 OEWS industry records in {args.input}")


if __name__ == "__main__":
    main()
