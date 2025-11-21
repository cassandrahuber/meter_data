import pandas as pd

def load_data(data_path, info_path):
    """
    Load meter data and meter info from CSV files. Prepare dataframe by cleaning and formatting.

    Parameters:
        data_path (str): Path to the meter data CSV.
        info_path (str): Path to the meter info CSV (contains meter model info).

    Returns:
        df (dataframe): Cleaned and formatted meter data.
        info_df (dataframe): Cleaned meter info data.
    """

    df = pd.read_csv(data_path, encoding='utf-8')
    info_df = pd.read_csv(info_path, encoding='utf-8')

    # remove total watt hour column, it is not relevant to these calculations
    df.drop('total_watt_hour', axis=1, inplace=True)

    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values(by=['meter_name', 'datetime'])

    # remove extra columns
    info_df.drop(columns={'header1', 'header2'}, axis=1, inplace=True)
    
    # ensure all meter names are uniform
    info_df['meter_name'] = info_df['meter_name'].str.replace(' ', '_')
    
    return df, info_df

def process_kw_data(df, info_df):
    """
    Process meter data to calculate average kw per 15-minute interval, adjusting for meter model.
    PQM2 meters report in kw, while EPM7000 meters report in watts.

    Parameters:
        df (dataframe): Meter data.
        info_df (dataframe): Meter model info.

    Returns:
        result_df (dataframe): Processed data with average kw per 15-minute interval.
    """
    # create set of all meters of EPM7000 model
    # PQM2 meter model is already in kw (so we won't divide by 1000)
    model_check = set(info_df[info_df['meter_model'].str.contains('EPM7000')]['meter_name'])

    # create column that contains the interval that the row belongs to
    df['interval'] = df['datetime'].dt.floor('15min')

    # create result dataframe categorized by the meter name and interval calculate the average of the 3 phase watt total
    result_df = df.groupby(['meter_name', 'interval'])['3_phase_watt_total'].mean().reset_index()

    # create kw column, dividing by 1000 for EPM7000 meters
    result_df['kw'] = result_df['3_phase_watt_total'].copy()
    result_df.loc[result_df['meter_name'].isin(model_check), 'kw'] /= 1000

    # rename and reorder columns, delete 3 phase column
    result_df.rename(columns={'interval': 'datetime'}, inplace=True)
    result_df.drop('3_phase_watt_total', axis=1, inplace=True)
    result_df = result_df[['datetime', 'meter_name', 'kw']]

    return result_df

def load_data_for_comparison(brian_csv, aurora_csv):
    """
    Load Brian's processed kw meter data from CSV and Aurora's from CSV for comparison.
    
    Parameters:
    """

    brian_df = pd.read_csv(brian_csv, encoding='utf-8')
    aurora_df = pd.read_csv(aurora_csv, encoding='utf-8')

    # convert datetime