import pandas as pd
import numpy as np
from pathlib import Path

PROCESSED_DIR = Path("../data/processed")
INPUT_FILE = PROCESSED_DIR / "2025_master_results.csv"  
OUTPUT_FILE = PROCESSED_DIR / "feature_engineered_data.csv" 


try:
    df = pd.read_csv(INPUT_FILE)
except FileNotFoundError:
    print(f"Error: Input file not found at {INPUT_FILE}")
    print("Please make sure you have run the data processing script first.")
    exit()

print(f"Loaded {INPUT_FILE.name}. Shape: {df.shape}")

# Clean the data
df = df[df['EventName'] != 'Pre-Season Testing'].copy()
print(f"Filtered 'Pre-Season Testing'. New shape: {df.shape}")

# Change if na bc there are some values that are NA if it did not qualify to q2 or q3 
time_cols = ['Q1', 'Q2', 'Q3']
fill_value = 999  

# Convert vals 
for col in time_cols:
    td = pd.to_timedelta(df[col], errors='coerce') 
    df[f'{col}_seconds'] = td.dt.total_seconds()    
    df[f'{col}_seconds'] = df[f'{col}_seconds'].fillna(fill_value)

df = df.drop(columns=time_cols)
print("Converted Q1, Q2, Q3 to seconds and filled NaNs.")

team_dummies = pd.get_dummies(df['TeamName'], prefix='Team', dtype=int)
df = pd.concat([df, team_dummies], axis=1)
df['FinishedRace'] = df['Status'].apply(lambda x: 1 if 'Finished' in str(x) or 'Lapped' in str(x) else 0)

# CHeck if is winner = 1 else 0 
df['IsRaceWinner'] = (df['RacePos'] == 1.0).astype(int)

# Check if is podium = 1 else 0 
df['IsPodium'] = (df['RacePos'] <= 3).astype(int)

# Clean data 
df['QualyPos'] = df['QualyPos'].fillna(99).astype(int)
df['GridPosition'] = df['GridPosition'].fillna(21).astype(int) # 21 for pit lane start
df['RacePos'] = df['RacePos'].fillna(99).astype(int) # 99 for DNF
df['Points'] = df['Points'].fillna(0).astype(float)


df = df.sort_values(by=['FullName', 'RoundNumber'])

# We use .shift(1) to prevent data leakage (we can only use data from *before* this race)
driver_groups = df.groupby('FullName')
window_size = 3

# Calculate momentum features
df['driver_avg_points_last_3'] = driver_groups['Points'].shift(1).rolling(window_size, min_periods=1).mean()
df['driver_avg_finish_pos_last_3'] = driver_groups['RacePos'].shift(1).rolling(window_size, min_periods=1).mean()
df['driver_avg_qualy_pos_last_3'] = driver_groups['QualyPos'].shift(1).rolling(window_size, min_periods=1).mean()
df['driver_championship_points_before_race'] = driver_groups['Points'].shift(1).cumsum()
df['driver_total_dnfs_season'] = (driver_groups['FinishedRace'].shift(1) == 0).astype(int).cumsum()


rolling_cols = ['driver_avg_points_last_3', 'driver_avg_finish_pos_last_3', 
                'driver_avg_qualy_pos_last_3', 'driver_championship_points_before_race',
                'driver_total_dnfs_season']
df[rolling_cols] = df[rolling_cols].fillna(0)

print("Built advanced rolling/cumulative features.")

# save model 
columns_to_drop = ['FullName', 'TeamName', 'EventName', 'Status']
df = df.drop(columns=columns_to_drop, errors='ignore')

# Sort 
df = df.sort_values(by=['RoundNumber', 'QualyPos'])

df.to_csv(OUTPUT_FILE, index=False)

print(f"\n--- Success! ---")
print(f"Feature-engineered data saved to: {OUTPUT_FILE.resolve()}")
print(f"Final dataset has {df.shape[0]} rows and {df.shape[1]} columns.")
print("\nFinal columns:")
print(df.columns.to_list())