# Harvest notebooks — a simple guide

Notebooks are the **recipes**. They set file paths and flags, then call functions from `modules/`. How those functions work is documented in [modules/README.md](../modules/README.md). This page is the map: which notebook to open, in what order, and what you should change.

Run notebooks from the `notebooks/` folder so the `../data/` paths still work.

## What to run, and when

```text
1. harvest_orig.ipynb
        │
        ├── 2a. harvest_kwh.ipynb          (kWh — energy total)
        └── 2b. harvest_kw.ipynb           (kW — power)
                    │
                    └── 3. harvest_comparison_aurora_kw.ipynb

Optional: harvest_aurora_kwh.ipynb   (same kWh steps, Aurora file format)

Helpers in other/  — not part of the main pipeline
```

kW and kWh (steps 2a and 2b) can run in either order. Both need the CSV from step 1.

| Notebook | What it is for | You point it at | You should get |
|---|---|---|---|
| [harvest_orig.ipynb](harvest_orig.ipynb) | Combine raw meter folders into one table | A folder of one subfolder per meter | `data/outputs/harvest_orig_YYMMDD-YYMMDD.csv` |
| [harvest_kwh.ipynb](harvest_kwh.ipynb) | Clean spikes and fill 15-minute kWh | That orig CSV | `harvest_kwh_…csv` (all rows) and `harvest_kwh_15min_…csv` (clock times only) |
| [harvest_kw.ipynb](harvest_kw.ipynb) | Average power to 15-minute kW | Orig CSV **and** `harvest_meter_guide.csv` (meter models) | `harvest_kw_YYMMDD-YYMMDD.csv` |
| [harvest_comparison_aurora_kw.ipynb](harvest_comparison_aurora_kw.ipynb) | Compare Harvest kW to Aurora kW | Both kW CSVs | A plots PDF plus a comparison-info CSV |
| [harvest_aurora_kwh.ipynb](harvest_aurora_kwh.ipynb) | Run Harvest kWh steps on Aurora’s kWh file | Aurora long-format kWh CSV | `aurora_kwh_…csv` files (Aurora is often already on 15 minutes) |

## What you must edit

Each notebook has a blue **Enter input** cell near the top. Change paths and switches there. You usually do not need to edit the processing cells unless you are changing the recipe.

Typical edits:

- **Date stamps in filenames** — orig output is named from the data’s min/max dates. Later notebooks must use that same stamp (for example `harvest_orig_250723-260508.csv`).
- **`data_path`** — orig needs a *folder* of raw CSVs, not a single file.
- **`info_path`** — kw needs the meter-model guide or kW can be off by 1,000.
- Flags such as `time_frame`, `dedup_check`, `create_merged_csv`.

## If a notebook looks wrong

1. Confirm you ran **orig** first and copied the filename stamp correctly.
2. Open the matching section in [modules/README.md](../modules/README.md) (the notebook’s markdown cells name the function).
3. Check **one meter** in the output CSV before re-running everything.

## `other/` — extra notebooks

These are one-off checks, not the main pipeline:

| Notebook | What it is for |
|---|---|
| [other/find_time_skips.ipynb](other/find_time_skips.ipynb) | kWh: which meters are missing 15-minute slots. kW: monthly completeness via `find_missing_kw_data`. |
| [other/swapping_gilmore_hall_kw.ipynb](other/swapping_gilmore_hall_kw.ipynb) | Plot Harvest vs Aurora Gilmore Hall A/B **crossed** (A vs B) to see if labels were swapped. |
