# Harvest modules — a simple guide

This folder is a toolbox. The notebooks in `notebooks/` are the recipes that call these tools.

Each section names a Python file, then walks through **every function** in that file: what it is for, what you give it, what you get back, and what to check if the result looks wrong.

---

## Two numbers this project cares about

Meters report two related things:

- **kW** (kilowatts) — how hard the building is using power *right now*. Think of the speedometer.
- **kWh** (kilowatt-hours) — how much energy has been used *in total* over time. Think of the odometer. This number should mostly go up.

The meters do not always log at a neat clock time (for example 2:00, 2:15, 2:30). This code lines things up onto a **15-minute schedule** so every meter can be compared.

**kW path:** take the power readings that fell in each 15-minute window and average them.

**kWh path:** the meter’s running total is cleaned (bad spikes removed), then estimated at exact 15-minute clock times.

There is also a step that compares Harvest’s kW to another system (Aurora), and a step that reports how complete a kW file is.

### How the files fit together

1. **`harvest_orig.py`** — gather raw CSV files from disk into one clean table.
2. Then either:
   - **`harvest_kw.py`** — make 15-minute average kW.  
     Optional next: **`find_missing_data.py`** (how complete is the file?) or **`harvest_kw_comp.py`** (does it match Aurora?).
   - **`harvest_kwh.py`** — clean and fill in 15-minute kWh.
3. **`file_naming.py`** — pick a consistent name when saving a CSV.

### Words used below

| Word | Meaning |
|---|---|
| CSV | A spreadsheet saved as text (the usual meter export). |
| Column | A named field in that spreadsheet, such as `datetime` or `meter_name`. |
| Function | A named step in the Python file. Notebooks call these by name. |
| Dataframe | The table in memory after Python has loaded a CSV. |

If two tables talk about the same meter, the **meter name must match exactly** (including capital letters). If kW values look about **1,000 times too big or too small**, the meter *model* in the info file is probably wrong (see `process_kw_data` below).

---

## 1. `harvest_orig.py` — load raw meter files

**Job:** Start from a folder on disk. Inside it, each subfolder is one meter, and each subfolder holds one or more CSV files. This file finds those CSVs, cleans the column names, and stacks them into tables the later steps can use.

A usable raw file must end up with three columns: **`datetime`**, **`kwh`**, and **`3_phase_watt_total`** (power).

Some exports use different labels. This code treats `total_watt_hour` as kWh (the export name is misleading), `3_phase_positive_real_energy_used` as kWh, and `3_phase_real_power` as power. New names from a vendor will be skipped until someone adds a rename here.

### `validate_base_path(path)`

**What it does:** Checks whether the folder path you typed actually exists on the computer.

**You give it:** A folder path (text).

**You get back:** True or False. It does **not** check whether CSVs are inside.

**If something looks wrong:** False means a typo, a moved folder, or a path on a different machine. True does not mean the data is good.

---

### `get_csv_paths(base_path)`

**What it does:** Looks at each subfolder. Builds a meter name from the folder name (lowercase, spaces become `_`, a trailing `_mtr` is removed). Collects every `.csv` file that does not start with a `.` (hidden files are ignored).

**You give it:** The parent folder that contains one subfolder per meter.

**You get back:** A dictionary: meter name → list of CSV file paths.

**If something looks wrong:** A meter is missing if that folder had no CSV, only hidden files, or was not a folder. Check the folder names and that files end in `.csv`.

---

### `load_meter_dfs(basepath)`

**What it does:** This is the main load step.

For each meter it opens each CSV, strips broken null characters that sometimes appear in exports, makes column names lowercase with underscores, applies the column renames above, keeps only the three required columns, and skips files that are empty or still missing those columns (it **prints** a message instead of crashing). It then stacks that meter’s files, adds a `meter_name` column, and sorts by time.

**You give it:** The same parent folder as `get_csv_paths`.

**You get back:** A **list** of tables, one table per meter. Columns: `datetime`, `meter_name`, `kwh`, `3_phase_watt_total`.

**If something looks wrong:**
- A meter vanished — read the printed “Skipping…” lines. The file was empty, had no rows, or used unexpected column names.
- The program crashes with an empty-concat error — every CSV for that meter was skipped.
- kWh looks 1,000 times off — do not treat `kwh` as watt-hours; the code already treats it as kWh.

---

### `concat_meter_dfs(meter_dfs)`

**What it does:** Stacks the list of per-meter tables into **one** table for all meters.

**You give it:** The list from `load_meter_dfs`.

**You get back:** One combined table.

**If something looks wrong:** If the list is empty, stacking will fail. Fix loading first.

---

### `meter_list(csv_path)`

**What it does:** Opens an already-combined CSV, prints every unique meter name, and saves a small file next to it named `*_meter_list.csv`.

**You give it:** Path to a combined CSV that has a `meter_name` column.

**You get back:** Nothing to the notebook besides printed names; the list is written to disk. If `meter_name` is missing, it raises an error listing the columns it did find.

**If something looks wrong:** You passed a raw single-meter file that never got a `meter_name` column. Run `load_meter_dfs` first.

---

## 2. `harvest_kw.py` — turn power into 15-minute kW

**Job:** After you have the combined meter table, average power onto a 15-minute clock and convert units so every meter is in kW.

You also need a **meter info** CSV with at least `meter_name` and `meter_model`. Two hardware types exist:

- **EPM7000** — reports power in **watts**. The code divides by 1,000 to get kW.
- **PQM2** (and anything whose model name does not contain `EPM7000`) — treated as already in **kW**.

The info file’s meter names only have spaces turned into `_`. They are **not** lowercased. The data file’s names usually **are** lowercase (from `harvest_orig`). If those strings do not match, the 1,000× conversion will not apply and kW will look wrong.

### `load_data(data_path, info_path)`

**What it does:** Reads the combined meter CSV and the info CSV. Drops `total_watt_hour` from the data if it is still there (not used for kW). Turns `datetime` into real dates and sorts by meter, then time. Drops `header1` and `header2` from the info file (those two columns **must exist**). Makes info meter names use `_` instead of spaces.

**You give it:** Path to the combined data CSV, and path to the meter info CSV.

**You get back:** Two tables: cleaned meter data, and cleaned info.

**If something looks wrong:** An error about `header1` / `header2` means the info spreadsheet no longer has those extra header columns — put them back or change this function so it does not drop them.

---

### `filter_time_frame(df, start, end)`

**What it does:** Keeps only rows whose `datetime` is between `start` and `end` (both ends included).

**You give it:** A meter data table, plus a start time and an end time.

**You get back:** A smaller copy of that table.

**If something looks wrong:** Empty result usually means the dates are outside the data, or timezone/format so the times never overlap.

---

### `process_kw_data(df, info_df)`

**What it does:** For each meter, snaps each timestamp down to the start of its 15-minute block (2:07 becomes 2:00). Averages `3_phase_watt_total` inside each block. For meters whose model contains `EPM7000`, divides that average by 1,000. Renames the time column back to `datetime` and keeps `mean_kw`.

**You give it:** The data table and the info table from `load_data` (optionally after `filter_time_frame`).

**You get back:** A table with `datetime`, `meter_name`, `mean_kw`. One row per meter per 15-minute block that had at least one raw reading. Gaps in the raw file stay as missing times; this function does not invent empty rows.

**If something looks wrong:**
- Values ~1,000× too high or low — meter name mismatch or wrong `meter_model`.
- A “hole” in the series — there was no raw reading in that 15 minutes. That is expected, not a failed average.

---

## 3. `harvest_kwh.py` — clean the running energy total and fill 15-minute times

**Job:** Work with the odometer (`kwh` / `meter_reading`). Remove obvious corruption, then estimate the reading at exact 15-minute clock times.

Usual order:

1. `load_kwh`
2. `clean_kwh_spikes` (which uses the helpers below)
3. `process_kwh`
4. `interval_kwh` if you only want the neat 15-minute rows

### `load_kwh(data_path)`

**What it does:** Reads the combined CSV. Renames `kwh` to `meter_reading` if needed. Turns `datetime` into dates using the pattern `YYYY-MM-DD HH:MM:SS` (unreadable times become empty). Turns `meter_reading` and, if present, `3_phase_watt_total` into numbers.

**You give it:** Path to the combined meter CSV.

**You get back:** A table ready for cleaning.

**If something looks wrong:** Many empty datetimes means the file does not use that date format (different separators, extra milliseconds, and so on). Fix the format or this step.

---

### `_typical_positive_step(values)`

**What it does:** Helper used only by spike removal. Looks at how much the running total usually *increases* from one row to the next (ignores the largest 10% of increases so outliers do not dominate) and returns a typical step size. If it cannot tell, it uses `1.0`.

**You give it:** A list of meter readings for one meter (the spike function passes this in; you rarely call it yourself).

**You get back:** One number: a typical healthy increase.

**If something looks wrong:** If this number is huge, real small spikes may not get removed. If it is tiny, normal jumps may look like spikes. That is why spike cleanup is per meter.

---

### `remove_invalid_power_rows(meter_group, tiny_power_threshold=1e-20)`

**What it does:** For **one meter**, drops rows where power is a tiny junk number (not quite zero, such as `5.94e-39`). True zeros are kept. If there is no power column, nothing changes.

**You give it:** One meter’s table. Optional: how small “tiny” is (default is extremely small).

**You get back:** The same table with those junk rows removed.

**If something looks wrong:** If real tiny loads were deleted, the threshold is too high. If junk remains, they may be larger than the threshold — inspect the power column for that meter.

---

### `remove_kwh_spikes(meter_group, lookback_rows=90, lookback_minutes=60)`

**What it does:** For **one meter**, finds a pattern like: the odometer jumps way up for a short time, then drops back to about where it was. That block is treated as a glitch and removed.

It only looks back a limited amount (90 rows or 60 minutes by default). It uses `_typical_positive_step` to decide how large a jump must be to count as a spike.

**You give it:** One meter’s table, already sorted by time.

**You get back:** The table with spike rows removed.

**If something looks wrong:**
- A real meter reset or meter swap can look like a spike and get deleted.
- A leftover spike means the jump was not large enough compared to that meter’s usual step, or the “return to normal” was outside the lookback window. Try plotting `meter_reading` over time for that meter.

---

### `clean_kwh_spikes(df)`

**What it does:** Splits the full table by meter, runs `remove_invalid_power_rows` then `remove_kwh_spikes` on each, and stacks them back together.

**You give it:** The table from `load_kwh`.

**You get back:** A cleaned table. If every meter’s rows were removed, you get an empty table with the same columns.

**If something looks wrong:** Empty output — cleaning deleted everything, or `meter_name` is missing so grouping failed. Check one meter with the two functions above.

---

### `process_kwh(df)`

**What it does:** For each meter, builds every 15-minute clock time from the first reading to the last.

- If a real reading lands **exactly** on that clock time, it is kept. Flags: `is_exact=True`, `interpolated=False`.
- If not, but there is a real reading within **15 minutes before and 15 minutes after**, it **estimates** the reading at that clock time (a straight line between the two neighbors). Flags: `is_exact=True`, `interpolated=True`.
- Original readings that are **not** on the 15-minute clock are still kept (`is_exact` stays False).

If the gap is larger than 15 minutes on either side, it will **not** guess. That clock time will have no filled-in row.

**You give it:** The cleaned table (usually after `clean_kwh_spikes`). Drops `3_phase_watt_total` if present; kWh interpolation does not use it.

**You get back:** A table that includes original rows plus filled-in 15-minute rows, with the two flag columns.

**If something looks wrong:**
- Holes every 15 minutes — the meter went quiet for more than 15 minutes. That is intentional, not a failed fill.
- Estimated kWh going down — a drop in the odometer survived cleaning. Plot that meter before this step.
- Duplicate times — run `duplicate_check` on the result.

---

### `interval_kwh(df)`

**What it does:** Keeps only rows that sit on the 15-minute clock (`is_exact` is True) and removes the two flag columns.

**You give it:** The table from `process_kwh`.

**You get back:** A simpler table of 15-minute kWh only.

**If something looks wrong:** Empty table means nothing was marked exact — interpolation never ran, or `is_exact` was lost.

---

### `duplicate_check(df)`

**What it does:** Looks for identical repeated rows and prints them (or prints that none were found). It does not delete anything.

**You give it:** Any table.

**You get back:** Printed messages only.

**If something looks wrong:** Duplicates after `process_kwh` can happen at the edges of exact vs interpolated vs original rows. Decide whether to drop them in the notebook.

---

### `meter_list(csv)`

**What it does:** Opens a CSV and prints unique `meter_name` values. Unlike `harvest_orig.meter_list`, it does **not** save a file.

**You give it:** A CSV path.

**You get back:** Printed names.

**If something looks wrong:** Error if `meter_name` is missing — you have a file from an earlier stage.

---

## 4. `harvest_kw_comp.py` — compare Harvest kW to Aurora

**Job:** Put Harvest’s 15-minute kW and Aurora’s (or Blue Pillar’s) kW on the same rows, plot them, and score whether they match.

Harvest’s kW column is called `mean_kw` (or `mean`, which gets renamed). Aurora’s is called `mean` (or `blue_pillar_kw` / `mean_kw`, which get renamed to `mean`).

### `load_data_for_comparison(harvest_csv, aurora_csv)`

**What it does:** Loads both files, makes column names lowercase with underscores, makes sure each side has a kW column (see names above), and **joins** them where meter name **and** datetime match. If one side is missing a time, that cell is blank. Times are not snapped; they must already line up.

**You give it:** Path to Harvest’s processed kW CSV and path to Aurora’s kW CSV.

**You get back:** One combined table, plus a list of meter names.

**If something looks wrong:** An error listing columns means a new header name — add a rename here. Lots of blanks usually means times or meter names do not match (off by 15 minutes, different spelling, different timezone).

---

### `create_plots_pdf(merged_df, meters, filename)`

**What it does:** Makes a PDF with one chart per meter: Harvest kW and Aurora kW over time.

**You give it:** The combined table, the meter list, and a file path for the PDF.

**You get back:** A PDF on disk. Many meters → a large file.

**If something looks wrong:** Empty charts — that meter has no overlapping times. Lines far apart — units or a 1,000× model issue in Harvest, or Aurora on a different scale.

---

### `get_comparison_info(merged_df, meters, corr_threshold, pct_threshold)`

**What it does:** For each meter, labels Harvest and Aurora as:

- `ok` — has real numbers
- `zeros` — every value is 0
- `missing` — every value is blank

If both are `ok`, it checks how well the two lines move together (correlation) and how far apart the values are on average (percent difference compared to Harvest). Harvest zeros are skipped in that percent so they do not explode the math.

Then `match` is:

- `yes` — correlation above your threshold **and** average percent difference below your threshold
- `yes (high r=…) but missing data` — they move together but the average gap is still large (this label is a bit misleading; it can also mean a scale difference, not only missing data)
- `no` — with the correlation and average percent shown
- `no valid data` or `n/a` — not enough overlapping numbers, or one side was zeros/missing

**You give it:** The combined table, the meter list, and two numbers you choose: how high correlation must be, and how small the average percent gap must be.

**You get back:** A summary table, one row per meter.

**If something looks wrong:** Nothing ever says `yes` — fix time alignment before tightening thresholds. Huge percent difference while the plot looks similar — Harvest values near zero, or a 1,000× unit mismatch.

---

## 5. `find_missing_data.py` — how complete is the kW file?

**Job:** For a **processed kW** file (`mean_kw`), estimate what percent of the expected 15-minute readings showed up in each month. A full day of 15-minute data is 96 readings.

### `load_kw_data(file_path)`

**What it does:** Reads the kW CSV and turns `datetime` into dates.

**You give it:** Path to a processed kW CSV.

**You get back:** That table in memory.

**If something looks wrong:** Wrong file (kWh instead of kW) will show up in the next function, which needs `mean_kw`.

---

### `find_missing_kw_data(file_path, start_month, end_month)`

**What it does:** Loads the file, keeps months from `start_month` to `end_month` as calendar month numbers (1 = January). **Every year** in the file is included; you cannot say “only 2024.” For each meter and month it counts non-blank `mean_kw` rows and divides by (days in that month × 96), then shows a grid: meters down the side, months across the top, percent present (one decimal).

**You give it:** Path to the processed kW CSV, and two month numbers (for example 6 and 8 for June–August).

**You get back:** That percent grid.

**If something looks wrong:**
- Error on `mean_kw` — this is not a Harvest kW file (maybe kWh, or Aurora’s `mean` column).
- Over 100% — more than 96 points per day (duplicates, or data that was never averaged to 15 minutes).
- Too low for a month you think is full — the math assumes the **whole calendar month**, even if your file only covers two weeks. Also, “June–August” includes those months in every year present.
- Month columns not in calendar order — the code comments mention reordering but does not do it.

---

## 6. `file_naming.py` — name the output file

### `make_filename(df, name, var, ext)`

**What it does:** Builds a name like `meter_data_kw_240101-240331.csv` using the earliest and latest `datetime` in the table (`YYMMDD`–`YYMMDD`).

**You give it:** A table with a `datetime` column, a short name (for example `meter_data`), a variable tag (for example `kw`), and a file ending (for example `csv`).

**You get back:** A file name string. It also converts `datetime` on the table you passed in (it changes that table in place).

**If something looks wrong:** A crash in date formatting usually means `datetime` never parsed (all empty). Copy the table first if you still need the original `datetime` text.

---

## If you think there is a bug

Start from **what looks wrong**, then open the matching file:

| What you see | Look here first |
|---|---|
| Missing meters, weird columns, skipped files | `harvest_orig.py` (`load_meter_dfs` prints why) |
| kW about 1,000× too big or too small | `harvest_kw.py` (`process_kw_data`) and the meter info names/models |
| kWh jumps up then back, or holes at 15-minute times | `harvest_kwh.py` (cleaning vs interpolation) |
| Harvest and Aurora do not line up | `harvest_kw_comp.py` (names and timestamps before the score thresholds) |
| Completeness percents look impossible | `find_missing_data.py` (wrong file type, or not 15-minute data) |
| Output file name / dates wrong | `file_naming.py` |

Then pick **one meter**, look at the raw numbers over time, and follow that same meter through the function that changed it. Almost all of the hard logic runs **per meter**, so one example is enough to see the mistake.

The notebooks under `notebooks/` show the intended order of these functions and where files are saved.
