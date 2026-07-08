import fastf1
from pathlib import Path
import logging
import pandas as pd
import os

OUT_DIR = Path("../data/raw/qualifying")

OUT_DIR.mkdir(parents=True, exist_ok=True)

# cache
CACHE_DIR = Path("fastf1_cache_dir")
CACHE_DIR.mkdir(exist_ok=True)

try:
    fastf1.Cache.enable_cache(CACHE_DIR)
except Exception as e:
    logging.warning(f"Could not enable FastF1 cache: {e}")
    logging.warning("Downloads may be slow and repeated.")

# Define the year you want to fetch
YEAR = 2025 # Last run was 2024 

# Get the schedule 
schedule = fastf1.get_event_schedule(YEAR)

print(f"--- Starting to fetch {YEAR} Qualifying Results ---")
print(f"Output directory: {OUT_DIR.resolve()}") # Shows the full, absolute path

# Loop through each event in the schedule
for index, event in schedule.iterrows():
    
    event_name = event['EventName']
    round_number = event['RoundNumber']

    print(f"\nProcessing: Round {round_number} - {event_name} (Qualifying)")

    try:
        # Get the qualifying session for year and name 
        qualy_session = fastf1.get_session(YEAR, event_name, 'Q')
        
        # Session
        qualy_session.load(telemetry=False, weather=False, messages=False)
        
        if qualy_session.results is None:
            print(f"    -> No results found for {event_name} Qualifying.")
            continue # Skip to the next event in the loop
        columns_to_save = ['Position', 'FullName', 'TeamName', 'Q1', 'Q2', 'Q3']
        
        # Get just the columns we want and make a copy
        event_results = qualy_session.results[columns_to_save].copy()
        
        # --- Add the Event data (the "Context") ---
        # This is key. We add info about the event to each row.
        event_results['Year'] = YEAR
        event_results['RoundNumber'] = round_number
        event_results['EventName'] = event_name
        
        # Re-order columns to be more logical
        final_columns = [
            'Year', 'RoundNumber', 'EventName', 
            'Position', 'FullName', 'TeamName', 
            'Q1', 'Q2', 'Q3', 
        ]
        event_results = event_results[final_columns]
        
        # Define the output file (inside the loop)
        filename = f"{YEAR}_Round_{str(round_number).zfill(2)}_{event_name.replace(' ', '_')}_Qualifying.csv"
        out_path = OUT_DIR / filename
        
        # Save the results for THIS event to a CSV file 
        event_results.to_csv(out_path, index=False)
        
        print(f"Saved: {out_path.name}")

    except Exception as e:
        # Catch any errors, e.g., session data not available yet
        print(f"ERROR processing {event_name}: {e}")

print("\nAll Qualifying events processed.")