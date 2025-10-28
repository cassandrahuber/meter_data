import pandas as pd
import os

# define the base path to thumb drive (input path)
base_path = '/Volumes/Untitled/MeterDataTest'

#check if base path exists
if not os.path.exists(base_path):
    print(f"Error: Path {base_path} does not exist")
    exit()

# list to store all dataframes
all_data = []

# dataframe for all data
combined_data = pd.DataFrame()

# iterate through the subfolders in the MeterDataTest folder
for subfolder in os.listdir(base_path):
    subfolder.replace(" ", "_")
    # create path for each subfolder
    folder_path = os.path.join(base_path, subfolder)

    # get the name of the meter from the subfolder name, make lowercase
    meter_name = subfolder.lower().replace(" ", "_") 

    # list of csv file paths in subfolder
    # addition with the and not is to make sure to ignore the hidden ._ files
    csv_paths = [os.path.join(folder_path, f) 
                 for f in os.listdir(folder_path) 
                 if f.endswith('.csv')
                 and not f.startswith("._")
                 and not f.startswith(".")]

    # convert each csv to a df, fix columns and add df to df list
    for csv in csv_paths:
        df = pd.read_csv(csv, encoding="utf-8")

        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

        # rename columns if they exist
        if '3_phase_positive_real_energy_used' in df.columns:
            df.rename(columns={
                '3_phase_positive_real_energy_used': 'total_watt_hour',
                '3_phase_real_power':'3_phase_watt_total'
            }, inplace=True)
        
        # convert dateime column to datetime format
        df['datetime'] = pd.to_datetime(df['datetime'], format='%Y-%m-%d %H:%M:%S')

        # create a list to store interpolated rows?
        # get the date range to create 15 min intervals

        # create a new column of the closest 15min interval
        df['interval_15min'] = df['datetime'].dt.round('15min')

        # calculate seconds from the 15min mark (negative = before, positive = after)
        df['seconds_from_interval'] = (df['datetime'] - df['interval_15min']).dt.total_seconds()

        # find the slope of two times closest to 15 min marks where it would be the 15 min mark exactly then add to the df


        # find the kw average over 15 min intervals

        # change col name
        #df.rename(columns={'total_watt_hour': 'kw_average'}, inplace=True)
        
        df.insert(0, 'meter_name', meter_name)

        all_data.append(df)


# combine all dataframes in list to one dataframe
combined_data = pd.concat(all_data, ignore_index=True)

# convert dataframe to csv
combined_data.to_csv('step1.csv', index=False)