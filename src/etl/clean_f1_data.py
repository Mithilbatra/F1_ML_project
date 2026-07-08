import pandas as pd
from pathlib import Path
import glob

# Setup paths
BASE_DIR = Path("../data")
RAW_DIR = BASE_DIR / "raw" 
RAW_QUALY_DIR = RAW_DIR / "qualifying" / "2025"
RAW_RACE_DIR = RAW_DIR / "race" / "2025"


PROCESSED_DIR = BASE_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


try:
    # --- 1. Load all Qualifying CSVs ---
    # Get a list of all CSV files in the raw qualifying directory
    qualy_csv_files = list(RAW_QUALY_DIR.glob("*.csv"))
    
    if not qualy_csv_files:
        print(f"Error: No qualifying CSV files found in {RAW_QUALY_DIR}")
        print("Please run 'fetch_qualy_results.py' first.")
    else:
        # Read each CSV into a DataFrame and combine them into one
        qualy_df_list = [pd.read_csv(f) for f in qualy_csv_files]
        all_qualy_data = pd.concat(qualy_df_list, ignore_index=True)
        print(f"Loaded {len(all_qualy_data)} rows from {len(qualy_csv_files)} qualifying files.")
        
        race_csv_files = list(RAW_RACE_DIR.glob("*.csv"))
        
        if not race_csv_files:
            print(f"Error: No race CSV files found in {RAW_RACE_DIR}")
            print("Please run 'fetch_race_results.py' first.")
        else:
            race_df_list = [pd.read_csv(f) for f in race_csv_files]
            all_race_data = pd.concat(race_df_list, ignore_index=True)
            print(f"Loaded {len(all_race_data)} rows from {len(race_csv_files)} race files.")

            # Data for mergint all the info 
            
            all_qualy_data.rename(columns={'Position': 'QualyPos'}, inplace=True)
            all_race_data.rename(columns={'Position': 'RacePos'}, inplace=True)
            
            merge_keys = ['Year', 'RoundNumber', 'EventName', 'FullName', 'TeamName']
            
            race_columns_to_add = [
                'GridPosition', 'RacePos', 'Status', 'Points', 'Laps'
            ]
            
            race_data_subset = all_race_data[merge_keys + race_columns_to_add]
            master_results_df = pd.merge(
                all_qualy_data,
                race_data_subset,
                on=merge_keys,
                how='left'
            )
            
            master_results_df.sort_values(by=['Year', 'RoundNumber', 'QualyPos'], inplace=True)

            # Final processed file
            YEAR = all_qualy_data['Year'].min()
            output_filename = f"2025_master_results.csv"
            output_path = PROCESSED_DIR / output_filename
            
            master_results_df.to_csv(output_path, index=False)
            
            print(f"\n--- Success! ---")
            print(f"Master file saved to: {output_path.resolve()}")
            print(f"Final dataset has {len(master_results_df)} rows and {len(master_results_df.columns)} columns.")

except Exception as e:
    print(f"\n--- An Error Occurred ---")
    print(f"Error: {e}")
    print("Please check that the raw data folders and files exist.")

print("\n--- Script Finished. ---")