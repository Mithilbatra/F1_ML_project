import fastf1
from pathlib import Path
import logging
import pandas as pd
import os


# Define the output directory using pathlib.Path
OUT_DIR = Path("../data/raw/race")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Define a cache directory
CACHE_DIR = Path("fastf1_cache_dir")
CACHE_DIR.mkdir(exist_ok=True)

try:
    fastf1.Cache.enable_cache(CACHE_DIR)
except Exception as e:
    logging.warning(f"Could not enable FastF1 cache: {e}")
    logging.warning("Downloads may be slow and repeated.")

YEAR = 2025         # Grab any year

schedule = fastf1.get_event_schedule(YEAR)

print(f"Output directory: {OUT_DIR.resolve()}")  # Check for the full absolute path 

for index, event in schedule.iterrows():
    
    event_name = event['EventName']
    round_number = event['RoundNumber']

    print(f"\nProcessing: Round {round_number} - {event_name} (Race)")

    try:
        race_session = fastf1.get_session(YEAR, event_name, 'R')
        race_session.load(telemetry=False, weather=False, messages=False)
        if race_session.results is None:
            print(f"    -> No results found for {event_name} Race.")
            continue # Skip to the next event in the loop

        columns_to_save = [
            'Position', 'FullName', 'TeamName', 
            'Status', 'Points', 'Laps', 'GridPosition'
        ]
        
        event_results = race_session.results[columns_to_save].copy()
        
        event_results['Year'] = YEAR
        event_results['RoundNumber'] = round_number
        event_results['EventName'] = event_name
        
        # Order the columns to add them into the csv 
        final_columns = [
            'Year', 'RoundNumber', 'EventName', 
            'Position', 'FullName', 'TeamName', 
            'GridPosition', 'Status', 'Points', 'Laps'
        ]
        event_results = event_results[final_columns]
        filename = f"{YEAR}_Round_{str(round_number).zfill(2)}_{event_name.replace(' ', '_')}_Race.csv"
        out_path = OUT_DIR / filename
        event_results.to_csv(out_path, index=False)
        

    except Exception as e:
        print(f"ERROR processing {event_name}: {e}")

