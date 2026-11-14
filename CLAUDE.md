# korea-bjd-shp-to-csv

Builds the Korean legal-dong (법정동) dataset — centroid + effective radius per
code — from VWorld shapefiles, and exports it for the
[dongnae](https://github.com/nash-dir/dongnae) engine (`dongnae-kr` on PyPI).
README.md (Korean) documents every script and output in detail.

## Checks

```bash
pip install pandas numpy shapely requests pytest ruff==0.15.9
ruff check .
pytest
```

Heavy dependencies (geopandas, tqdm, dotenv) are imported lazily inside the
run functions, so tests and lint need only the packages above.

## Regenerating the dataset

Inputs live in `input/` (gitignored): VWorld `LSMD_ADM_SECT_{RI,UMD}_*` shapefiles
and the master code table `LSCT_LAWDCD.csv`. They are CC BY-NC-ND and are never
committed; only derived statistics go in `results/`.

```bash
python bjd_geometry_to_csv.py -i input -o output                  # -> output/bjd_<ts>_result.csv
python bjd_csv_to_fulladdress.py -b input/LSCT_LAWDCD.csv \
    -d output/bjd_<ts>_result.csv -o results/<YYMMDD>/LSCT_LAWDCD_coords_<YYMMDD>
python bjd_csv_apply_revisions.py -i results/<YYMMDD>/LSCT_LAWDCD_coords_<YYMMDD>.csv \
    -o results/<YYMMDD>/LSCT_LAWDCD_coords_<YYMMDD>_revised.csv
python bjd_csv_to_dongnae.py -i results/<YYMMDD>/LSCT_LAWDCD_coords_<YYMMDD>_revised.csv \
    -o results/<YYMMDD>/dongnaeKR_<YYMMDD>.csv
```

- Read the geometry step's log: `[보정]` lines are dropped stray parts, and
  rows in `output/bjd_<ts>_error.csv` need a look (a valid code with a broken
  name, like 4311231021, belongs in the revisions spec).
- Hand corrections (unrecovered areas, overlapped dongs, missing shapes) live
  only in `revisions/manual_revisions.csv`. Edit that file, never the result
  CSVs. A `[확인 필요]` line means a revision now overrides real geometry, so
  check whether it is still needed.
- `input/` may hold superseded shapefiles (e.g. Jeonbuk code 45 → 52 in 2024).
  The export drops abolished codes (`DEL_DT`), so leave them alone.
- Each run gets its own `results/<YYMMDD>/` folder with a `revision_report`,
  and a README section describing what changed and any accuracy figures.
  Never rewrite an earlier results folder.

Shipping the CSV to `dongnae-kr` is done in the dongnae repo (see its
CLAUDE.md).

## Measuring accuracy (optimize/)

Run from the repo root with `python -m` (needs `pip install "dongnae>=0.3.0"`):

```bash
python -m optimize.generate_ground_truth -i input -o optimize/output/ground_truth.csv
python -m optimize.evaluate results/<old>/dongnaeKR_<old>.csv results/<new>/dongnaeKR_<new>.csv
```

- Evaluate every regenerated dataset against the previous one before
  shipping it, and quote those numbers (README results section).
- `optimize.optimize_radius` is experimental. Never ship its output without an
  `evaluate` comparison showing it helps.
- `optimize/output/` and `optimize/legacy/` (the 2025 scripts and their
  outputs, including a ground truth with broken 8-digit ids) are gitignored.

## API verification

`bjd_csv_API_verification.py` reverse-geocodes every centroid through VWorld
(~20k calls; key in `.env` as `API_KEY`, issued after 2025-12-31). Error cells
record only the exception type — never write a raw `requests` exception, since
its message includes the URL with the key.
