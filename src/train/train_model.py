import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib 
import warnings

# Experiment B 

warnings.filterwarnings('ignore')


# --- 1. Load Data ---
DATA_FILE = "../data/processed/feature_engineered_data.csv"
try:
    df = pd.read_csv(DATA_FILE)
except FileNotFoundError:
    exit()

print(f"Loaded feature engineered data. Shape: {df.shape}")

target = 'IsPodium' # This is what we want to achieve 

# Prevent data leaks 
non_feature_cols = [
    'Year',          
    'RacePos',       
    'Points',        
    'Laps',          
    'FinishedRace',  
    'IsRaceWinner',  
    'IsPodium'      
]

features = [col for col in df.columns if col not in non_feature_cols]

X = df[features]
y = df[target]

print(f"Target (y): {target}")
print(f"Number of Features (X): {len(features)}")


# --- 3. Split Data (Time-Based Split) ---
TRAIN_UNTIL_ROUND = 17  # Train on races 1-17
TEST_FROM_ROUND = 17    # Test on races 18-24 

# Create the training dataset
X_train = X[df['RoundNumber'] < TEST_FROM_ROUND]
y_train = y[df['RoundNumber'] < TEST_FROM_ROUND]

# Create the testing dataset
X_test = X[df['RoundNumber'] >= TEST_FROM_ROUND]
y_test = y[df['RoundNumber'] >= TEST_FROM_ROUND]


# --- 4. Train the Model ---
print("\nTraining RandomForestClassifier")

model = RandomForestClassifier(
    n_estimators=100,       # 100 "trees" in the forest
    random_state=42,        
    class_weight='balanced' 
)

# Train using the data 
model.fit(X_train, y_train)

print("Model training complete ")


# Evaluate
print("\n--- Model Evaluation on Test Data ---")

y_pred = model.predict(X_test)
print(f"Overall Accuracy: {accuracy_score(y_test, y_pred):.4f}")

print("\nClassification Report:")
print(" (1 = Podium, 0 = No Podium)\n")
print(classification_report(y_test, y_pred, target_names=['No Podium (0)', 'Podium (1)']))


# 6. Save the Model 
MODEL_PATH = "/Users/axelreich/Library/CloudStorage/OneDrive-FloridaStateUniversity/Semester8/DataMining/f1-ml-project/src/models/podium_model.pkl"
joblib.dump(model, MODEL_PATH)

print(f"\nModel saved to {MODEL_PATH}")
print("--- Script Finished. ---")