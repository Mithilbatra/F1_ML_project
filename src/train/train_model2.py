import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib 
import warnings
import os
from pathlib import Path

# Experiment C 
warnings.filterwarnings('ignore')

# --- 1. Robust Data Loading --- 

filename = "improved_feature_engineered_data.csv"

# Wanted to try that for each path you could run it without problem
possible_paths = [
    f"data/processed/{filename}",           
    f"../data/processed/{filename}",        
    f"../../data/processed/{filename}",     
    "data/processed/feature_engineered_data.csv",
    "../../data/processed/feature_engineered_data.csv"
]

DATA_FILE = None

for path in possible_paths:
    if os.path.exists(path):
        DATA_FILE = path
        print(f"Found data at: {DATA_FILE}")
        break


df = pd.read_csv(DATA_FILE)
print(f"Loaded data. Shape: {df.shape}")

# Define Target and Features
target = 'IsPodium' 

# Columns to ignore for testing 
non_feature_cols = [
    'Year', 'RoundNumber', 'FullName', 'EventName', 'TeamName',
    'RacePos', 'Points', 'Laps', 'FinishedRace', 
    'IsRaceWinner', 'IsPodium', 'Time', 'Driver', 'Constructor',
    'GridPosition', 'QualyPos' 
]

# Automatically grab all numeric columns that are NOT in the ignore list
features = [col for col in df.columns if col not in non_feature_cols]

X = df[features]
y = df[target]

print(f"Target: {target}")
print(f"Training on {len(features)} features.")


# Strategy: 

SPLIT_ROUND = 15

# Create masks
train_mask = (df['Year'] == 2024) & (df['RoundNumber'] < SPLIT_ROUND)
test_mask = (df['Year'] == 2024) & (df['RoundNumber'] >= SPLIT_ROUND)

X_train = X[train_mask]
y_train = y[train_mask]

X_test = X[test_mask]
y_test = y[test_mask]

# Create a Context DataFrame for the Report ---
test_context = df[test_mask][[
    'Year', 'RoundNumber', 'EventName', 'FullName', 'RacePos'
]].copy()

print(f"\nTraining samples: {len(X_train)} (Rounds 1-{SPLIT_ROUND-1})")
print(f"Testing samples:  {len(X_test)} (Rounds {SPLIT_ROUND}-24)")

# Train the Model 
print("\nTraining RandomForestClassifier...")
model = RandomForestClassifier(
    n_estimators=500,
    random_state=42,
    class_weight='balanced'
)
model.fit(X_train, y_train)

# Check the metrics 
print("\n--- Model Metrics ---")
y_pred = model.predict(X_test)
print(f"Overall Accuracy: {accuracy_score(y_test, y_pred):.4f}")
print(classification_report(y_test, y_pred, target_names=['No Podium', 'Podium']))


print("\n--- Detailed Prediction Analysis ---")

probs = model.predict_proba(X_test)[:, 1]

test_context['Predicted_Podium'] = y_pred
test_context['Actual_Podium'] = y_test.values
test_context['Podium_Probability'] = probs
test_context['Confidence'] = test_context['Podium_Probability'].apply(lambda x: f"{x*100:.1f}%")

# Show the podium picks 
interesting_rows = test_context[
    (test_context['Predicted_Podium'] == 1) | 
    (test_context['Actual_Podium'] == 1)
].copy()

# Round then position sorted 
interesting_rows.sort_values(by=['RoundNumber', 'Podium_Probability'], ascending=[True, False], inplace=True)
cols_to_show = ['RoundNumber', 'FullName', 'RacePos', 'Predicted_Podium', 'Actual_Podium', 'Confidence']
print(interesting_rows[cols_to_show].to_string(index=False))


# Save the Model 
SAVE_PATH = "src/models/improved_podium_model.pkl"

if not os.path.exists("src/models"):
    SAVE_PATH = "improved_podium_model.pkl"

joblib.dump(model, SAVE_PATH)
print(f"\nModel saved to {SAVE_PATH}")
print("--- Script Finished. ---")