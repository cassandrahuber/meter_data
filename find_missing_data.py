import pandas as pd

# finding missing kw data 

def load_kw_data(file_path):
    """
    Load processed kw data from a CSV file.

    Parameters:
        file_path (str): Path to the CSV file.

    Returns: 
        df (dataframe): Loaded kw data.
    """
    df = pd.read_csv(file_path, encoding='utf-8')
    df['datetime'] = pd.to_datetime(df['datetime'])
    #df.drop(columns=['mean_kw'], inplace=True)

    return df

def find_missing_kw_data(file_path, start_month, end_month):
    """

    """
    import calendar

    df = load_kw_data(file_path)

    # filter data to only include months within date range
    df = df[df['datetime'].dt.month.isin(range(start_month, end_month + 1))]

    # create year and month columns
    df['year'] = df['datetime'].dt.year
    df['month'] = df['datetime'].dt.month

    # summary_df = df.groupby('meter_name')['datetime'].dt.month.count()
    #summary_df = df.groupby(['meter_name', 'datetime']).filter(
    #    lambda x: x['datetime'].dt.


    #print("max datetime in brians data:", brian_df['datetime'].max())
