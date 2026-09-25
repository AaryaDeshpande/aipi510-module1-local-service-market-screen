"""Download the two small Census source archives needed by the market screen.

Run from anywhere: python src/download_sources.py [--refresh]
The May 2025 BLS OEWS snapshot is managed separately by load_oews.py.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
SOURCES = {
    "cbp23us.zip": "https://www2.census.gov/programs-surveys/cbp/datasets/2023/cbp23us.zip",
    "naics_2022_to_2017.xlsx": "https://www.census.gov/naics/concordances/2022_to_2017_NAICS.xlsx",
}


def validate_archive(path: Path) -> None:
    """Fail on a truncated ZIP or an HTML error page saved as a data file."""
    try:
        with ZipFile(path) as archive:
            corrupt = archive.testzip()
            if corrupt is not None:
                raise ValueError(f"Corrupt member {corrupt!r} in {path}")
            members = set(archive.namelist())
    except BadZipFile as exc:
        raise ValueError(f"Not a valid ZIP-based source file: {path}") from exc

    if path.suffix == ".xlsx":
        if "xl/workbook.xml" not in members:
            raise ValueError(f"Not a valid XLSX workbook: {path}")
    elif "cbp23us.txt" not in members:
        raise ValueError(f"CBP archive lacks cbp23us.txt: {path}")


def download(name: str, url: str, *, refresh: bool = False) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    destination = RAW / name
    if destination.exists() and not refresh:
        validate_archive(destination)
        print(f"Using existing {destination}")
        return destination

    request = Request(url, headers={"User-Agent": "AIPI510-public-data-analysis/1.0"})
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{name}.", suffix=destination.suffix, dir=RAW, delete=False
        ) as stream:
            temporary = Path(stream.name)
            with urlopen(request, timeout=60) as response:
                status = response.status
                if status != 200:
                    raise RuntimeError(f"HTTP {status} for {url}")
                shutil.copyfileobj(response, stream)
        validate_archive(temporary)
        temporary.replace(destination)
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"Could not download {url}: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    print(f"Downloaded {destination} from {url}")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Replace cached Census files")
    args = parser.parse_args()
    for name, url in SOURCES.items():
        download(name, url, refresh=args.refresh)


if __name__ == "__main__":
    main()
