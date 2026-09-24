# Local-service market screen

**Research question:** Which selected U.S. local-service industries combine many small employer establishments with a substantial office and administrative workforce—and therefore merit closer customer discovery?

This repository is a reproducible **screen for interviews**, not a ranking of businesses or a product recommendation. It compares 12 deliberately selected industries with public Census and BLS data, exposes each measure separately, and documents the assumptions behind a directional wage-payroll proxy. The accompanying [public-facing article](docs/index.md) explains the findings for a general audience.

## What is here

| Path | Purpose |
|---|---|
| `data/raw/cbp23us.zip` | Original 2023 U.S. County Business Patterns (CBP) national data archive; includes `cbp23us.txt`. |
| `data/raw/naics_2022_to_2017.xlsx` | Census 2022-to-2017 NAICS concordance used to check the scope of every cross-source industry match. |
| `data/raw/oews_2025.json` | Small, inspectable snapshot of 36 May 2025 BLS OEWS API estimates, their series IDs, and retrieval metadata. |
| `config/industry_crosswalk.csv` | The 12 selected industry labels, CBP 2017-NAICS codes, OEWS 2022-NAICS codes, and scope notes. |
| `src/download_sources.py` | Downloads/validates the two official Census archives, without replacing present files unless requested. |
| `src/load_cbp.py`, `src/load_oews.py` | Validate and load each source; missing/suppressed values are errors, not zeros. |
| `src/build_market_screen.py` | Checks the NAICS concordance, joins the sources, engineers measures, and writes the analysis table. |
| `src/eda.py` | Writes descriptive ranges, missing-value counts, IQR flags, and a cross-source employment comparison. |
| `src/make_figures.py` | Generates three PNG/SVG charts and copies article-ready PNGs to `docs/figures/`. |
| `data/processed/local_service_market_screen.csv` | Analysis-ready output: one row per selected industry. |
| `data/processed/eda_summary.json` | Machine-readable exploratory and quality-control summary. |
| `figures/` and `docs/` | Three visualizations and the draft public article. |
| `tests/test_pipeline.py` | Source, crosswalk, formula, and sanity-check tests. |

The included raw snapshots make the analysis reproducible without depending on the sources staying online. Refreshing them later may change the results if an agency revises its files or estimates.

## Sources and unit of analysis

1. **U.S. Census Bureau, 2023 [County Business Patterns](https://www.census.gov/data/datasets/2023/econ/cbp/2023-cbp.html):** [national data archive](https://www2.census.gov/programs-surveys/cbp/datasets/2023/cbp23us.zip). We use U.S.-level, all-legal-form-of-organization (`lfo == "-"`) rows and the establishment, employment, and establishment-size-band fields. A CBP *establishment* is a business location, not necessarily a unique firm. These are employer establishments; nonemployer businesses are outside the screen.
2. **U.S. Bureau of Labor Statistics, May 2025 [National Industry-Specific Occupational Employment and Wage Statistics](https://www.bls.gov/oes/2025/may/oessrci.htm):** [OEWS time-series API](https://api.bls.gov/publicAPI/v2/timeseries/data/) estimates of industry employment for all occupations (SOC `00-0000`), office and administrative support occupations (SOC `43-0000`), and the latter group's annual mean wage. See the [OEWS technical notes](https://www.bls.gov/oes/2025/may/oes_tec.htm) for the survey and estimation method. BLS employment estimates are rounded; the derived shares are therefore approximate.
3. **U.S. Census Bureau, [2022-to-2017 NAICS concordance](https://www.census.gov/naics/concordances/2022_to_2017_NAICS.xlsx):** used to validate the paired industry scopes. CBP uses 2017 NAICS; May 2025 OEWS uses 2022 NAICS. Identical-looking code strings alone are not proof of comparable industry definitions.

The comparison universe is not exhaustive. It contains 12 local-service industries for which the selected Census and BLS industry scopes can be checked. Some are four-digit groups (shown as `5412//` in CBP and `541200` in OEWS), while others are six-digit industries. For a four-digit match, the pipeline verifies that all constituent six-digit codes in the official concordance remain under that parent; for a six-digit match, it verifies the 2022 code maps only to the selected 2017 code. Broader categories still contain heterogeneous businesses—for example, accounting/tax includes bookkeeping and payroll services, and automotive repair/maintenance includes car washes. Do not read a four-digit result as though it describes one narrow niche.

## Reproduce from a clean Python environment

Use Python **3.11 or newer**. From this repository's root, on macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python src/download_sources.py
python src/load_oews.py
python src/build_market_screen.py
python src/eda.py
python src/make_figures.py
python -m pytest -q
```

On Windows, replace the activation line with `.venv\Scripts\activate` in Command Prompt or `.venv\Scripts\Activate.ps1` in PowerShell, then use `python` for the remaining commands.

The supplied source files mean the Census downloader and BLS loader will validate the existing snapshots and work without fresh network requests. To obtain new copies intentionally, run `python src/download_sources.py --refresh` and `python src/load_oews.py --fetch` before rebuilding; an internet connection is required. Avoid refreshing only one source if you want to reproduce this specific draft exactly.

Expected build result: 12 rows in `data/processed/local_service_market_screen.csv`, `data/processed/eda_summary.json`, and `fragmentation`, `admin_intensity`, and `market_screen` figures as PNG and SVG. The article's image copies appear under `docs/figures/`. Tests should pass; any missing source estimate, broken source archive, changed NAICS scope, duplicated industry, or invalid engineered share fails loudly rather than silently altering the screen.

## Methods and interpretation

The cleaned CSV retains source years, industry codes, raw inputs, and engineered fields. For each selected industry:

| Field | Construction | Interpretation |
|---|---|---|
| `small_establishments` | CBP `n<5 + n5_9 + n10_19` | Number of employer locations with fewer than 20 employees. |
| `market_depth` | Copy of `small_establishments` | Explicit plan label for the count of potentially reachable small employer locations; not a customer count. |
| `small_establishment_share` | `small_establishments / total_establishments` | Fraction of employer locations below 20 employees; **not** the fraction of independent companies. |
| `avg_employees_per_establishment` | CBP `employment / establishments` | Industry-wide mean location size, not the median or the size of a typical small practice. |
| `admin_employment_share` | OEWS SOC `43-0000` employment / OEWS SOC `00-0000` employment | Approximate industry office/admin occupational share, using rounded BLS employment estimates. |
| `admin_mean_wage` | OEWS annual mean wage for SOC `43-0000` | Wage context, excluding benefits. For most occupations, BLS annualizes the hourly rate with a 2,080-hour work year; it is not necessarily actual pay for a part-time worker. |
| `estimated_admin_payroll_per_establishment` | `avg_employees_per_establishment × admin_employment_share × admin_mean_wage` | **Directional proxy** obtained by combining industry averages from different years and sources; not observed payroll, addressable spend, savings, or willingness to pay. |

The figures deliberately show the dimensions rather than combining them into a black-box “opportunity score”: (1) small-establishment share and count, (2) office/admin employment share alongside annual mean wage, and (3) a bubble screen with share on the horizontal axis, payroll proxy on the vertical axis, and bubble area proportional to the small-establishment count. The `eda_summary.json` file reports descriptive ranges, IQR-based flags for review, missing-value counts, and the ratio between OEWS and CBP total employment. The source employment totals should **not** be expected to match because the reference years, coverage, and estimation methods differ. IQR flags are prompts to inspect a value, not grounds for automatic deletion.

## Limits and ethical use

- The 2023 CBP and May 2025 OEWS releases differ in time, coverage, classification vintage, and measurement method. OEWS estimates may be rounded or suppressed; CBP size-band counts can also be unavailable. The selected rows have usable values, but that does not make the sources interchangeable at the establishment level.
- A national industry average hides firm size, geography, specialty, staffing mix, and variation among individual workplaces. Some listed categories are broader than others. The payroll proxy multiplies separate aggregate measures and should not be used as a dollar opportunity estimate for a representative firm.
- The payroll proxy uses CBP's average employees across **all** establishments in an industry. The horizontal axis and bubble size describe establishments with **fewer than 20** employees, so the vertical axis is **not** estimated payroll for one of those small locations. OEWS annual mean wages are generally full-time-year rates, not observed annual compensation for each part-time worker. See the [BLS OEWS annual-wage method](https://www.bls.gov/opub/hom/oews/calculation.htm).
- The selected universe is a comparison sample, not all local-service markets. Choosing it introduces selection bias; a sector outside the list could be more promising.
- Office/admin employment is not evidence of inefficient labor, automatable tasks, or jobs that should be replaced. The public data do not measure pain, customer outcomes, regulatory constraints, decision makers, existing software, adoption, or willingness to pay.
- A defensible next step is interviews with owners, staff, and customers to understand actual workflows and harms/benefits before proposing any intervention. A structural signal can justify asking questions; it cannot validate a product.

## Collaboration and review

For the team submission, each group member should make and explain at least one meaningful change on a separate branch, open their **own** pull request, and review the other's changes before merging. The final story, chart interpretations, interview shortlist, presentation, public-access settings, and submission links need human verification. Reproducible figures and passing tests do not replace a check of source definitions and conclusions.
