import pandas as pd

def load_data_for_comparison(harvest_csv, aurora_csv):
    """
    Load harvest's processed kw meter data from CSV and Aurora's from CSV for comparison.
    
    Parameters:
        harvest_csv (str): Path to harvest's processed kw data CSV.
        aurora_csv (str): Path to Aurora's processed kw data CSV.

    Returns:
        merged_df (dataframe): Merged dataframe containing both harvest's and Aurora's data.
        meters (list): List of unique meter names in the merged dataframe.
    """
    harvest_df = pd.read_csv(harvest_csv, encoding='utf-8')
    aurora_df = pd.read_csv(aurora_csv, encoding='utf-8')

    harvest_df.columns = harvest_df.columns.str.lower().str.replace(' ', '_')
    aurora_df.columns = aurora_df.columns.str.lower().str.replace(' ', '_')

    # convert datetime column to datetime type
    harvest_df['datetime'] = pd.to_datetime(harvest_df['datetime'])
    aurora_df['datetime'] = pd.to_datetime(aurora_df['datetime'])

    # normalize Harvest kw column
    if 'mean_kw' not in harvest_df.columns:
        if 'mean' in harvest_df.columns:
            harvest_df = harvest_df.rename(columns={'mean': 'mean_kw'})
        else:
            raise KeyError(f"Harvest file is missing a kw column. Columns: {harvest_df.columns.tolist()}")

    # normalize Aurora kw column
    if 'mean' not in aurora_df.columns:
        if 'blue_pillar_kw' in aurora_df.columns:
            aurora_df = aurora_df.rename(columns={'blue_pillar_kw': 'mean'})
        elif 'mean_kw' in aurora_df.columns:
            aurora_df = aurora_df.rename(columns={'mean_kw': 'mean'})
        else:
            raise KeyError(f"Aurora file is missing a kw column. Columns: {aurora_df.columns.tolist()}")
        
    # merge the dataframes together on meter_name and datetime
    merged_df = pd.merge(
        harvest_df[['meter_name', 'datetime', 'mean_kw']],
        aurora_df[['meter_name', 'datetime', 'mean']],
        on=['meter_name', 'datetime'],
        how='outer'
    )

    merged_df = merged_df.sort_values(by=['datetime', 'meter_name']).reset_index(drop=True)
    meters = merged_df['meter_name'].dropna().unique()

    return merged_df, meters

def create_plots_pdf(merged_df, meters, filename):
    """
    Create a PDF file with plots comparing harvest's 'mean_kw' and Aurora's 'mean' 
    data for each meter.

    Parameters:
        merged_df (dataframe): Merged dataframe containing both harvest's and Aurora's data.
        meters (list): List of unique meter names.
        filename (str): Path to save the output PDF file.
    """
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    with PdfPages(filename) as pdf:
        for meter in meters:
            meter_data = merged_df[merged_df['meter_name'] == meter].sort_values('datetime')

            plt.figure(figsize=(10, 6))
            plt.plot(meter_data['datetime'], meter_data['mean_kw'], label="harvests_kw", alpha=0.7) # alpha is opacity of the line
            plt.plot(meter_data['datetime'], meter_data['mean'], label="auroras_kw", alpha=0.7)
            
            plt.xlabel('datetime')
            plt.ylabel('kw')
            plt.title(f'Meter: {meter}')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()

            # save current plot to pdf
            pdf.savefig()
            plt.close() 

def get_comparison_info(merged_df, meters, corr_threshold, pct_threshold):
    """
    Create a dataframe summarizing the comparison between harvest's and Aurora's kw data for each meter.

    Parameters:
        merged_df (dataframe): Merged dataframe containing both harvest's ('mean_kw') and Aurora's data ('mean').
        meters (list): List of unique meter names.
    
    Returns:
        info_df (dataframe): Dataframe summarizing the comparison results.
    """
    import numpy as np

    # create dataframe to hold information
    info_df = pd.DataFrame({
        'meter_name': meters,
        'harvests': '',
        'auroras': '', 
        'match': ''
    })

    # make meter_name the index
    info_df.set_index('meter_name', inplace=True)
    
    for meter in meters:
        meter_data = merged_df[merged_df['meter_name'] == meter].sort_values('datetime')
        
        # check validity of harvest's kw data for meter
        if (meter_data['mean_kw'] == 0).all():
            info_df.loc[meter, 'harvests'] = 'zeros'
        elif meter_data['mean_kw'].isna().all():
            info_df.loc[meter, 'harvests'] = 'missing'
        else:
            info_df.loc[meter, 'harvests'] = 'ok'
            
        # check validity of aurora's kw data for meter 
        if (meter_data['mean'] == 0).all():
            info_df.loc[meter, 'auroras'] = 'zeros'
        elif meter_data['mean'].isna().all():
            info_df.loc[meter, 'auroras'] = 'missing'
        else:
            info_df.loc[meter, 'auroras'] = 'ok'
        
        # check if both are 'ok', then calculate
        if info_df.loc[meter, 'harvests'] == 'ok' and info_df.loc[meter, 'auroras'] == 'ok':
            # get non-na values for comparison (keeps rows ONLY if BOTH columsn have non-na values)
            valid_data = meter_data.dropna(subset=['mean_kw', 'mean']).copy()

            if len(valid_data) > 0:
                # calculate correlation
                correlation = valid_data['mean_kw'].corr(valid_data['mean'])

                # calculate percentage difference (how close the actual values are to eachother):
                # difference between the two values (absolute to get how different)
                difference = abs(valid_data['mean_kw'] - valid_data['mean'])

                # replace any zeros in 'mean_kw' column with 'NaN' to avoid division by zero errors (to get meaningful % difference)
                valid_data['mean_kw'] = valid_data['mean_kw'].replace(0, np.nan)

                # percent difference column
                valid_data['pct_diff'] = (difference / valid_data['mean_kw']) * 100

                # average percent difference for meter
                avg_pct_diff = valid_data['pct_diff'].mean()

                # threshold for "close enough" (ie: correlation > 0.95 or avg diff < 10%)
                # r = 1.0 is perfect positive correlation, want diff % low as possible
                if correlation > corr_threshold and avg_pct_diff < pct_threshold:
                    info_df.loc[meter, 'match'] = 'yes'
                elif correlation > corr_threshold:
                    info_df.loc[meter, 'match'] = f'yes (high r={correlation:.2f}) but missing data'
                else:
                    info_df.loc[meter, 'match'] = f'no (r={correlation:.2f}, avg_pct_diff={avg_pct_diff:.1f}%)'
            else:
                info_df.loc[meter, 'match'] = 'no valid data'
        else:
            info_df.loc[meter, 'match'] = 'n/a'
    
    return info_df