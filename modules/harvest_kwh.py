import pandas as pd
import numpy as np



def load_kwh(data_path):
    """
    Load the preprocessed kwh csv and fix any malformed rows before later steps.

    Parameters:
        data_path (str): Path to the CSV file containing meter original data.

    Returns:
        dataframe: Loaded dataframe with datetime and numeric columns cleaned.
    """
    # load raw data from csv
    df = pd.read_csv(data_path, encoding='utf-8', low_memory=False)

    # rename column kwh to meter_reading
    if 'kwh' in df.columns and 'meter_reading' not in df.columns:
        df.rename(columns={'kwh': 'meter_reading'}, inplace=True)

    # convert datetime column to a datetime type
    df['datetime'] = pd.to_datetime(df['datetime'], format='%Y-%m-%d %H:%M:%S', errors='coerce')

    # convert meter reading to number so interpolation can subtract readings
    df['meter_reading'] = pd.to_numeric(df['meter_reading'], errors='coerce')

    # convert power column too, if it exists
    if '3_phase_watt_total' in df.columns:
        df['3_phase_watt_total'] = pd.to_numeric(df['3_phase_watt_total'], errors='coerce')

    return df


def _typical_positive_step(values):
    """
    Get a typical positive increase size for the cumulative meter readings.
    """
    differences = pd.Series(values).diff()
    positive_differences = differences[differences > 0]

    if positive_differences.empty:
        return 1.0

    upper_limit = positive_differences.quantile(0.90)
    trimmed_positive_differences = positive_differences[positive_differences <= upper_limit]

    if trimmed_positive_differences.empty:
        trimmed_positive_differences = positive_differences

    typical_step = float(trimmed_positive_differences.median())

    if typical_step <= 0:
        typical_step = 1.0

    return typical_step


def remove_invalid_power_rows(meter_group, tiny_power_threshold=1e-20):
    """
    Remove rows where 3_phase_watt_total is a tiny nonzero corrupted value such
    as 5.94e-39. Keep real zeros.
    """
    if '3_phase_watt_total' not in meter_group.columns:
        return meter_group

    power_values = pd.to_numeric(meter_group['3_phase_watt_total'], errors='coerce')
    bad_power_mask = power_values.abs().gt(0) & power_values.abs().lt(tiny_power_threshold)

    if not bad_power_mask.any():
        return meter_group

    return meter_group.loc[~bad_power_mask].reset_index(drop=True)


def remove_kwh_spikes(meter_group, lookback_rows=90, lookback_minutes=60):
    """
    Remove short lived upward spike blocks when the meter jumps way up and then
    returns back down near its earlier level.
    """
    meter_group = meter_group.sort_values('datetime').reset_index(drop=True).copy()

    if meter_group.shape[0] < 3:
        return meter_group

    values = pd.to_numeric(meter_group['meter_reading'], errors='coerce').to_numpy(dtype=float)
    times = pd.to_datetime(meter_group['datetime']).to_numpy()
    differences = np.diff(values)

    # if the cumulative series never drops, there is no spike block to remove
    if not np.any(differences < 0):
        return meter_group

    typical_step = _typical_positive_step(values)
    return_slack = max(typical_step * 3.0, 1.0)
    spike_height = max(typical_step * 20.0, 10.0)

    suspicious_drop_indexes = np.flatnonzero(differences < -spike_height)

    if suspicious_drop_indexes.size == 0:
        return meter_group

    keep_mask = np.ones(len(meter_group), dtype=bool)

    for drop_index in suspicious_drop_indexes:
        if not keep_mask[drop_index]:
            continue

        return_value = values[drop_index + 1]
        scan_index = drop_index
        rows_scanned = 0
        earliest_allowed_time = pd.Timestamp(times[drop_index + 1]) - pd.Timedelta(minutes=lookback_minutes)

        while (
            scan_index >= 0
            and rows_scanned < lookback_rows
            and pd.Timestamp(times[scan_index]) >= earliest_allowed_time
            and values[scan_index] > return_value + spike_height
        ):
            scan_index -= 1
            rows_scanned += 1

        block_start_index = scan_index + 1

        if block_start_index == 0:
            continue

        previous_good_value = values[block_start_index - 1]
        allowed_return_upper = previous_good_value + (return_slack * (drop_index - block_start_index + 3))
        allowed_return_lower = previous_good_value - return_slack

        returned_to_baseline = allowed_return_lower <= return_value <= allowed_return_upper

        if returned_to_baseline:
            keep_mask[block_start_index:drop_index + 1] = False

    return meter_group.loc[keep_mask].reset_index(drop=True)


def clean_kwh_spikes(df):
    """
    Remove corrupted power rows and spike rows from the loaded kwh dataframe.

    Parameters:
        df (dataframe): Loaded kwh dataframe.

    Returns:
        dataframe: Cleaned dataframe with spike rows removed.
    """
    all_meter_groups = []

    for meter_name, meter_group in df.groupby('meter_name', sort=False):
        meter_group = meter_group.sort_values('datetime').reset_index(drop=True)

        meter_group = remove_invalid_power_rows(meter_group)
        meter_group = remove_kwh_spikes(meter_group)

        if not meter_group.empty:
            all_meter_groups.append(meter_group)

    if len(all_meter_groups) == 0:
        return df.iloc[0:0].copy()

    result = pd.concat(all_meter_groups, ignore_index=True)
    result = result.sort_values(by=['meter_name', 'datetime']).reset_index(drop=True)
    return result


def process_kwh(df):
    """
    Interpolate meter readings to exact 15 minute intervals. Contains boolean 'interpolated'
    column to indicate if the row was interpolated or not, and boolean 'is_exact' column
    to indicate if row is at an exact 15 minute interval.

    Parameters:
        df (dataframe): Cleaned dataframe containing meter original data.
    
    Returns:
        dataframe: Dataframe with interpolated kwh readings at exact 15 minute intervals.
    """
    df = df.copy()

    # drop the 3_phase_watt_total column as its not needed for kwh interpolation
    if '3_phase_watt_total' in df.columns:
        df.drop('3_phase_watt_total', axis=1, inplace=True)

    # make sure datetime is datetime type
    df['datetime'] = pd.to_datetime(df['datetime'], format='%Y-%m-%d %H:%M:%S', errors='coerce')

    df['is_exact'] = False
    df['interpolated'] = False

    window = np.timedelta64(15, 'm')
    meter_results = []

    for meter_name, meter_group in df.groupby('meter_name', sort=False):
        meter_group = meter_group.sort_values('datetime').reset_index(drop=True)

        times = meter_group['datetime'].to_numpy()
        readings = meter_group['meter_reading'].to_numpy(dtype=float)
        meter_length = len(meter_group)

        # create target intervals
        start = meter_group['datetime'].min().floor('15min')
        end = meter_group['datetime'].max().ceil('15min')

        # create array of every exact 15min timestamp that SHOULD exist for that meter
        target_intervals = pd.date_range(start=start, end=end, freq='15min')
        target_arr = target_intervals.values

        # vectorized: find where each target interval would sit among the real readings
        idx = np.searchsorted(times, target_arr, side='left')
        idx_safe = np.clip(idx, 0, max(meter_length - 1, 0))

        exact_mask = (idx < meter_length) & (times[idx_safe] == target_arr)

        # real readings that land exactly on a 15 min grid point
        exact_rows = meter_group.iloc[idx[exact_mask]].copy()
        exact_rows['is_exact'] = True
        exact_rows['interpolated'] = False

        # candidates for interpolation: readings within 15 minutes on both sides
        before_idx = idx - 1
        after_idx = idx
        valid_before = before_idx >= 0
        valid_after = after_idx < meter_length

        before_idx_safe = np.clip(before_idx, 0, max(meter_length - 1, 0))
        after_idx_safe = np.clip(after_idx, 0, max(meter_length - 1, 0))

        time_before = times[before_idx_safe]
        time_after = times[after_idx_safe]

        close_enough_before = (target_arr - time_before) <= window
        close_enough_after = (time_after - target_arr) <= window

        interp_mask = ~exact_mask & valid_before & valid_after & close_enough_before & close_enough_after

        reading_before = readings[before_idx_safe]
        reading_after = readings[after_idx_safe]

        time_diff_sec = (time_after - time_before) / np.timedelta64(1, 's')
        reading_diff = reading_after - reading_before
        # if no time difference or no reading difference, use the before reading
        no_slope = (time_diff_sec == 0) | (reading_diff == 0)

        safe_time_diff_sec = np.where(time_diff_sec == 0, 1, time_diff_sec)
        slope = np.round(np.where(no_slope, 0.0, reading_diff / safe_time_diff_sec), 4)

        sec_before_interval = (target_arr - time_before) / np.timedelta64(1, 's')
        estimated_kwh = np.where(no_slope, reading_before, reading_before + slope * sec_before_interval)

        # create interpolated rows (copy the "before" row's other columns, like the original did)
        interp_rows = meter_group.iloc[before_idx_safe[interp_mask]].copy()
        interp_rows['datetime'] = target_arr[interp_mask]
        interp_rows['meter_reading'] = estimated_kwh[interp_mask]
        interp_rows['is_exact'] = True
        interp_rows['interpolated'] = True

        # keep original nonexact interval rows
        non_exact_rows = meter_group.loc[~meter_group['datetime'].isin(target_intervals)]

        meter_results.append(pd.concat([exact_rows, interp_rows, non_exact_rows], ignore_index=True))

    # create final dataframe from per-meter results, sort by meter name and datetime, reset index
    if meter_results:
        result = pd.concat(meter_results, ignore_index=True)
    else:
        result = df.iloc[0:0].copy()

    result = result.sort_values(by=['meter_name', 'datetime']).reset_index(drop=True)

    return result


def interval_kwh(df):
    """
    Get only the rows from the dataframe that are at exact 15 minute intervals, and drop the
    'is_exact' and 'interpolated' columns.

    Parameters:
        df (dataframe): The dataframe containing the meter readings and interpolated readings
        at exact 15 minute intervals.
    
    Returns:
        dataframe: Dataframe with only the rows at exact 15 minute intervals and removed columns.
    """
    interval_df = df[df['is_exact'] == True].copy()
    interval_df.drop(['is_exact', 'interpolated'], axis=1, inplace=True)
    return interval_df


def duplicate_check(df):
    """
    Check for duplicate rows in the dataframe and print them.

    Parameters:
        df (dataframe): The dataframe to check for duplicates.
    """
    duplicate_data = df[df.duplicated(keep=False)]
    if duplicate_data.empty:
        print("No duplicate rows found.")
    else:
        print("Duplicate rows found:")
        print(duplicate_data)


def meter_list(csv):
    """
    Print the list of unique meter names in the CSV file.
    
    Parameters:
        csv (str): Path to the CSV file.
    """
    df = pd.read_csv(csv, encoding='utf-8')
    print('List of meter names: \n', df['meter_name'].unique())
