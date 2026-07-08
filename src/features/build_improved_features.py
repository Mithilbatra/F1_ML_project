import pandas as pd
import numpy as np
from pathlib import Path

# Resolve the project root regardless of the current working directory
import pathlib
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = BASE_DIR / "processed"
FILE_2024 = PROCESSED_DIR / "2024_master_results.csv"
FILE_2025 = PROCESSED_DIR / "2025_master_results.csv"
OUTPUT_FILE = PROCESSED_DIR / "improved_feature_engineered_data.csv"

print("--- Starting Advanced Feature Engineering ---")

# --- 2. Load and Merge Datasets ---
try:
    dfs_to_merge = []
    if FILE_2024.exists():
        print(f"Loading {FILE_2024.name}...")
        dfs_to_merge.append(pd.read_csv(FILE_2024))
    
    if FILE_2025.exists():
        print(f"Loading {FILE_2025.name}...")
        dfs_to_merge.append(pd.read_csv(FILE_2025))
    
    if not dfs_to_merge:
        print("Error: No master result files found in ../data/processed/")
        exit()

    # Concatenate vertically
    df = pd.concat(dfs_to_merge, ignore_index=True)
    print(f"Merged data total rows: {len(df)}")
    
except Exception as e:
    print(f"Error loading files: {e}")
    exit()

# --- 3. Initial Cleaning ---

df = df[~df['EventName'].str.contains('Pre-Season', case=False, na=False)].copy()
time_cols = ['Q1', 'Q2', 'Q3']
fill_value = 999.0 

for col in time_cols:
    if col in df.columns:
        df[col] = pd.to_timedelta(df[col], errors='coerce').dt.total_seconds()
        df[col] = df[col].fillna(fill_value)
    
# Normalize 
team_mapping = {
    'RB': 'Racing Bulls',           
    'AlphaTauri': 'Racing Bulls',   
    'Visa Cash App RB': 'Racing Bulls',
    'Alfa Romeo': 'Kick Sauber',    
    'Sauber': 'Kick Sauber',
    'Stake F1 Team Kick Sauber': 'Kick Sauber'
}
df['TeamName'] = df['TeamName'].replace(team_mapping)

# --- 5. Engineer Basic Features ---
# One-Hot Encode Teams
df = pd.get_dummies(df, columns=['TeamName'], prefix='Team', dtype=int)
# Binary Features
df['FinishedRace'] = df['Status'].apply(lambda x: 1 if 'Finished' in str(x) or 'Lapped' in str(x) else 0)
# Target Variables
df['IsRaceWinner'] = (df['RacePos'] == 1).astype(int)
df['IsPodium'] = (df['RacePos'] <= 3).astype(int)
# Track Type Feature
street_circuits = ['Monaco', 'Singapore', 'Jeddah', 'Baku', 'Miami', 'Las Vegas', 'Albert Park']
df['IsStreetCircuit'] = df['EventName'].apply(lambda x: 1 if any(s in str(x) for s in street_circuits) else 0)


# Rolling feature
# Sort by Year -> Round -> Driver
df = df.sort_values(by=['Year', 'RoundNumber', 'FullName'])
driver_groups = df.groupby('FullName')

df['RacePos_Last_1'] = driver_groups['RacePos'].shift(1).fillna(20)
df['RacePos_Last_2'] = driver_groups['RacePos'].shift(2).fillna(20)
df['RacePos_Last_3'] = driver_groups['RacePos'].shift(3).fillna(20)

# Calculate average
window = 3
df['driver_avg_points_last_3'] = driver_groups['Points'].shift(1).rolling(window, min_periods=1).mean().fillna(0)
df['driver_avg_finish_last_3'] = driver_groups['RacePos'].shift(1).rolling(window, min_periods=1).mean().fillna(20)
df['driver_avg_qualy_last_3'] = driver_groups['QualyPos'].shift(1).rolling(window, min_periods=1).mean().fillna(20)


# Season Points and dnf
df['season_points'] = df.groupby(['Year', 'FullName'])['Points'].transform(
    lambda x: x.shift(1).fillna(0).cumsum()
)
df['dnfs_season'] = df.groupby(['Year', 'FullName'])['FinishedRace'].transform(
    lambda x: (x == 0).shift(1).fillna(0).astype(int).cumsum()
)

print("Finished advanced features (Lags, Rolling Averages, Season Stats)")

# Final Cleanup and Save ---
cols_to_fill = ['QualyPos', 'GridPosition', 'RacePos']
df[cols_to_fill] = df[cols_to_fill].fillna(20)
df['Points'] = df['Points'].fillna(0)

# Drop nonumeric columns
cols_to_drop = ['Status', 'Time', 'Driver', 'Constructor'] 
df = df.drop(columns=[c for c in cols_to_drop if c in df.columns], errors='ignore')

# Final sort
df = df.sort_values(by=['Year', 'RoundNumber', 'QualyPos'])

# Save
df.to_csv(OUTPUT_FILE, index=False)

print(f"\n--- Success! ---")
print(f"Feature-engineered data saved to: {OUTPUT_FILE.resolve()}")
print(f"Total Rows: {len(df)}")