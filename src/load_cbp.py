"""Load 2023 U.S. County Business Patterns employer-establishment counts."""

from __future__ import annotations

from pathlib import Path
import zipfile

import pandas as pd


COUNT_COLUMNS = ("est", "emp", "n<5", "n5_9", "n10_19")


def validate_naics_scope(mapping: pd.DataFrame, concordance_path: Path) -> None:
    """Reject cross-year mappings whose 2022 and 2017 six-digit components differ.

    A CBP code ending in // is an aggregate (e.g. 6212//). An OEWS code ending
    in 00 denotes the corresponding four-digit industry (e.g. 621200). For
    aggregates, every constituent code must stay within the same four-digit
    parent in the official Census 2022-to-2017 concordance.
    """
    cross = pd.read_excel(concordance_path, skiprows=2, usecols="A:D", dtype=str)
    cross.columns = ("naics_2022", "title_2022", "naics_2017", "title_2017")
    cross = cross.dropna(subset=["naics_2022", "naics_2017"])
    cross = cross[
        cross["naics_2022"].str.fullmatch(r"\d{6}")
        & cross["naics_2017"].str.fullmatch(r"\d{6}")
    ]

    for row in mapping.itertuples(index=False):
        cbp_code = row.cbp_naics_2017
        oews_code = row.bls_naics_2022
        if cbp_code.endswith("//"):
            prefix = cbp_code[:4]
            if oews_code != prefix + "00":
                raise ValueError(f"Invalid four-digit pairing: {cbp_code} / {oews_code}")
            relevant = cross[
                cross["naics_2022"].str.startswith(prefix)
                | cross["naics_2017"].str.startswith(prefix)
            ]
            if relevant.empty or not (
                relevant["naics_2022"].str.startswith(prefix)
                & relevant["naics_2017"].str.startswith(prefix)
            ).all():
                raise ValueError(f"Changed NAICS scope for {row.industry}: {prefix}")
        else:
            relevant = cross[cross["naics_2022"] == oews_code]
            if relevant.empty or not (relevant["naics_2017"] == cbp_code).all():
                raise ValueError(f"Changed NAICS scope for {row.industry}: {cbp_code}")


def load_cbp(zip_path: Path, mapping: pd.DataFrame) -> pd.DataFrame:
    """Return one row per selected industry, preserving unavailable values as NA."""
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open("cbp23us.txt") as stream:
            raw = pd.read_csv(stream, dtype=str, low_memory=False)

    raw = raw.loc[raw["lfo"] == "-", ["naics", *COUNT_COLUMNS]].copy()
    for column in COUNT_COLUMNS:
        # CBP uses literal N for unavailable counts. Never turn it into zero.
        raw[column] = pd.to_numeric(raw[column], errors="coerce")

    selected = mapping.merge(
        raw, how="left", left_on="cbp_naics_2017", right_on="naics", validate="one_to_one"
    )
    if selected[list(COUNT_COLUMNS)].isna().any().any():
        missing = selected.loc[selected[list(COUNT_COLUMNS)].isna().any(axis=1), "industry"]
        raise ValueError(f"Unavailable or missing CBP counts: {missing.tolist()}")
    if (selected["est"] <= 0).any():
        raise ValueError("Every selected industry must have employer establishments")

    selected[list(COUNT_COLUMNS)] = selected[list(COUNT_COLUMNS)].astype("int64")

    selected["small_establishments"] = selected[["n<5", "n5_9", "n10_19"]].sum(axis=1)
    if (selected["small_establishments"] > selected["est"]).any():
        raise ValueError("CBP size-band sum exceeds establishments")
    selected["small_establishment_share"] = selected["small_establishments"] / selected["est"]
    selected["avg_employees_per_establishment"] = selected["emp"] / selected["est"]
    return selected.rename(
        columns={
            "est": "total_establishments",
            "emp": "cbp_total_employment",
            "n<5": "establishments_lt5",
            "n5_9": "establishments_5_9",
            "n10_19": "establishments_10_19",
        }
    )
