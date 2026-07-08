import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import warnings
import os

warnings.filterwarnings('ignore')

print("--- Qatar Grand Prix (Round 23) Prediction Simulation ---")

# Load data file 
DATA_FILE = "data/processed/improved_feature_engineered_data.csv"
possible_paths = [DATA_FILE, f"../{DATA_FILE}", f"../../{DATA_FILE}"]
for path in possible_paths:
    if os.path.exists(path):
        DATA_FILE = path
        break

try:
    df = pd.read_csv(DATA_FILE)
    print(f"Loaded data. Shape: {df.shape}")
except FileNotFoundError:
    print("Error: Data file not found.")
    exit()

# Config
TARGET_ROUND = 23 # Qatar is round 23 so this is the target one 
TARGET_YEAR = 2024

target = 'IsPodium' 
non_feature_cols = [
    'Year', 'RoundNumber', 'FullName', 'EventName', 'TeamName',
    'RacePos', 'Points', 'Laps', 'FinishedRace', 
    'IsRaceWinner', 'IsPodium', 'Time', 'Driver', 'Constructor',
    'GridPosition', 'QualyPos' 
]
features = [col for col in df.columns if col not in non_feature_cols]

# Train on EVERYTHING before Qatar (Rounds 1-22 of 2024)
train_mask = (df['Year'] == TARGET_YEAR) & (df['RoundNumber'] < TARGET_ROUND)
qatar_mask = (df['Year'] == TARGET_YEAR) & (df['RoundNumber'] == TARGET_ROUND)

X_train = df[train_mask][features]
y_train = df[train_mask][target]

X_qatar = df[qatar_mask][features]

qatar_context = df[qatar_mask][['FullName', 'QualyPos', 'RacePos']].copy()


if len(X_qatar) == 0:
    print("Error: No data found for Round 23. Please check your CSV to ensure Round 23 exists.")
    exit()

# --- 4. Train the Model ---
print("\nTraining model on pre-Qatar data...")
model = RandomForestClassifier(
    n_estimators=500, 
    random_state=42, 
    class_weight='balanced'
)
model.fit(X_train, y_train)

print("Predicting outcomes...\n")
probs = model.predict_proba(X_qatar)[:, 1]
predictions = model.predict(X_qatar)

# Report results
qatar_context['Predicted_Podium'] = predictions
qatar_context['Podium_Probability'] = probs
qatar_context['Confidence'] = qatar_context['Podium_Probability'].apply(lambda x: f"{x*100:.1f}%")

# Sort by probabiblity
qatar_context = qatar_context.sort_values(by='Podium_Probability', ascending=False)

cols = ['FullName', 'QualyPos', 'Confidence', 'Predicted_Podium', 'RacePos']

print(f"--- PREDICTIONS FOR QATAR GP (Round {TARGET_ROUND}) ---")
print("(Model Confidence)")
print(qatar_context[cols].to_string(index=False))

# Analyze
top_3_picks = qatar_context.head(3)
print("\n--- Model's Top 3 Picks ---")
for i, row in top_3_picks.iterrows():
    print(f"{row['FullName']}: {row['Confidence']} chance.")

actual_podium = qatar_context[qatar_context['RacePos'] <= 3]
print("\n--- Actual Podium ---")
for i, row in actual_podium.iterrows():
    print(f"P{int(row['RacePos'])}: {row['FullName']}")