import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.metrics import classification_report, accuracy_score
import warnings
import os
import joblib

# Experiment D, only 2025 data
# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

print("--- Advanced Model Training (2025 Data Only) ---")

# Load data
DATA_FILE = "data/processed/improved_feature_engineered_data.csv"
possible_paths = [DATA_FILE, f"../{DATA_FILE}", f"../../{DATA_FILE}"]
DATA_PATH = next((p for p in possible_paths if os.path.exists(p)), None)

if not DATA_PATH:
    print("Error: Data file not found.")
    exit()

df = pd.read_csv(DATA_PATH)
print(f"Loaded data. Shape: {df.shape}")

# 
CUTOFF_YEAR = 2025
CUTOFF_ROUND = 19 
target = 'IsPodium' 

# Define features
non_feature_cols = [
    'Year', 'RoundNumber', 'FullName', 'EventName', 'TeamName',
    'RacePos', 'Points', 'Laps', 'FinishedRace', 
    'IsRaceWinner', 'IsPodium', 'Time', 'Driver', 'Constructor',
    'GridPosition', 'QualyPos' 
]
features = [col for col in df.columns if col not in non_feature_cols]


# Try to train it only from the 2025 data 
train_mask = (df['Year'] == CUTOFF_YEAR) & (df['RoundNumber'] <= CUTOFF_ROUND)

# testing the uknowns what has not happened 
test_mask = (df['Year'] == CUTOFF_YEAR) & (df['RoundNumber'] > CUTOFF_ROUND)

X_train = df[train_mask][features]
y_train = df[train_mask][target]
X_test = df[test_mask][features]
y_test = df[test_mask][target]

# Create context for reporting
test_context = df[test_mask][['RoundNumber', 'EventName', 'FullName', 'RacePos']].copy()

print(f"Training set size: {len(X_train)} (2025 Data Only)")
print(f"Test set size: {len(X_test)}")


# Hyperparameter Tuning (Trying to improve the mdoel) after some tries
print("\nStarting Grid Search (finding best settings)...")

param_grid = {
    'n_estimators': [100, 200, 300],
    'max_depth': [5, 10, 20, None],
    'min_samples_split': [2, 5, 10],
    'class_weight': ['balanced', 'balanced_subsample']
}

tscv = TimeSeriesSplit(n_splits=2)
rf = RandomForestClassifier(random_state=42)

grid_search = GridSearchCV(
    estimator=rf,
    param_grid=param_grid,
    cv=tscv,
    scoring='f1',
    n_jobs=-1,
    verbose=1
)

grid_search.fit(X_train, y_train)
best_model = grid_search.best_estimator_

print(grid_search.best_params_)

# Evaluate the Best Model ---
print("\n--- Model Evaluation (Final 5 Races of 2025) ---")
y_pred = best_model.predict(X_test)
probs = best_model.predict_proba(X_test)[:, 1]

print(f"Overall Accuracy: {accuracy_score(y_test, y_pred):.4f}")
print("\nClassification Report (Raw Predictions):")
print(classification_report(y_test, y_pred, target_names=['No Podium', 'Podium']))

# Detailed Race-by-Race Predictions (FIXED LOGIC) ---
print("\n" + "="*50)
print("   DETAILED PREDICTIONS: FORCED TOP 3")
print("="*50)

test_context['Actual_Podium'] = y_test.values
test_context['Podium_Prob'] = probs
test_context['Confidence'] = test_context['Podium_Prob'].apply(lambda x: f"{x*100:.1f}%")

rounds = sorted(test_context['RoundNumber'].unique())
for r in rounds:
    race_slice = test_context[test_context['RoundNumber'] == r].copy()
    race_name = race_slice['EventName'].iloc[0]
    
    print(f"\n🏁 Round {r}: {race_name}")
    
    # Sort by dirver and probab 
    race_slice = race_slice.sort_values(by='Podium_Prob', ascending=False)
    
    # Force the Top 3 to be "Predicted Podium" (1), everyone else (0)
    race_slice['Refined_Prediction'] = 0
    race_slice.iloc[:3, race_slice.columns.get_loc('Refined_Prediction')] = 1
    
    for i, row in race_slice.head(5).iterrows():
        is_top_3_pick = row['Refined_Prediction'] == 1
        actually_podium = row['Actual_Podium'] == 1
        
        if is_top_3_pick and actually_podium:
            status = "CORRECT"
        elif is_top_3_pick and not actually_podium:
            status = "False Alarm" 
        elif not is_top_3_pick and actually_podium:
            status = "Missed"      
        else:
            status = "   (Correctly predicted loser)"
            
        print(f"   P{i+1} Pick: {row['FullName']:<20} | Conf: {row['Confidence']} | Actual Podium? {row['Actual_Podium']}  {status}")

# Save model 
MODEL_PATH = "src/models/tuned_podium_model_2025.pkl"
if not os.path.exists("src/models"):
    MODEL_PATH = "tuned_podium_model_2025.pkl"

joblib.dump(best_model, MODEL_PATH)
print(f"\nOptimized model saved to {MODEL_PATH}")