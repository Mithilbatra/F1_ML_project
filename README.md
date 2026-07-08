# F1 Podium Finish Predictor

A machine learning project that predicts Formula 1 podium finishes (Top 3 positions) using historical race and qualifying data from the 2024 and 2025 F1 seasons. Built with Python, scikit-learn, and FastF1 API.

## Project Overview

This project uses Random Forest Classifier models to predict which drivers will finish on the podium in F1 races. The system includes:

- **Data Pipeline**: Automated ETL process extracting race and qualifying results
- **Feature Engineering**: 22+ predictive features including driver momentum, season statistics, and track characteristics
- **Model Training**: Multiple model iterations with hyperparameter tuning
- **Evaluation Tools**: Comprehensive metrics and visualization dashboards
- **Prediction Scripts**: Ready-to-use prediction scripts for upcoming races

**Model Performance**: Achieves 87% accuracy in predicting podium finishes.

## Prerequisites

- **Python**: 3.12 or higher
- **Package Manager**: `pip` or `uv` (recommended)
- **Internet Connection**: Required for downloading F1 data via FastF1 API

## Installation

### Option 1: Using UV (Recommended)

If you have `uv` installed:

```bash
# Clone the repository (or navigate to project directory)
cd f1-ml-project

# Install dependencies
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```


## Project Structure

```
f1-ml-project/
├── data/
│   ├── raw/                    # Raw data from FastF1 API
│   │   ├── qualifying/         # Qualifying results by year
│   │   └── race/               # Race results by year
│   └── processed/              # Processed and feature-engineered data
├── notebooks/                  # Jupyter notebooks for analysis
│   ├── save_f1_qualy_results.ipynb
│   ├── save_f1_race_results.ipynb
│   ├── merge_qualy_race.ipynb
│   ├── build_features.ipynb
│   ├── build_improved_features.ipynb
│   ├── train_model*.ipynb
│   ├── evaluate_model.ipynb
│   └── predict_qatar_gp.ipynb
├── src/
│   ├── etl/                    # Extract, Transform, Load scripts
│   ├── features/               # Feature engineering scripts
│   └── models/                 # Model files and evaluation
├── experiments/                # Experimental scripts
└── pyproject.toml              # Project configuration and dependencies
```

## Running the Project

### Step 1: Fetch Data (ETL)

#### Using Notebooks (Recommended for first-time users):

1. Start Jupyter Lab:
   ```bash
   jupyter lab
   ```

2. Navigate to `notebooks/` and run in order:
   - `save_f1_qualy_results.ipynb` - Fetches qualifying session data
   - `save_f1_race_results.ipynb` - Fetches race session data

   **Note**: Update the `YEAR` variable in each notebook to specify which season(s) to download (2024, 2025, etc.)

#### Using Python Scripts:

```bash
# From project root directory
cd src/etl

# Update YEAR variable in the script, then run:
python save_f1_qualy_results.py
python save_f1_race_results.py
```

**Output**: Raw CSV files in `data/raw/qualifying/` and `data/raw/race/` directories.

### Step 2: Merge Data

Run the merge notebook or script to combine qualifying and race results:

```bash
# Using notebook (recommended)
jupyter lab notebooks/merge_qualy_race.ipynb

# Or using Python script
python src/etl/process_qualy_race_results.py
```

**Output**: `data/processed/2024_master_results.csv` and `2025_master_results.csv`

### Step 3: Feature Engineering

Create features for model training:

```bash
# Using notebook (recommended)
jupyter lab notebooks/build_improved_features.ipynb

# Or using Python script
python src/features/build_improved_features.py
```

**Output**: `data/processed/improved_feature_engineered_data.csv`

### Step 4: Train Models

Train a model using one of the training notebooks:

```bash
jupyter lab notebooks/train_model.ipynb      # Basic model
jupyter lab notebooks/train_model2.ipynb     # Improved model
jupyter lab notebooks/train_model3.ipynb     # Hyperparameter-tuned model
```

**Output**: Trained model files (`.pkl`) saved in `src/models/`

### Step 5: Evaluate Models

Evaluate model performance:

```bash
jupyter lab notebooks/evaluate_model.ipynb       # Basic evaluation
jupyter lab notebooks/advanced_evaluation.ipynb  # Advanced metrics
```

### Step 6: Make Predictions

Predict podium finishes for a specific race:

```bash
# Predict Qatar GP (example)
jupyter lab notebooks/predict_qatar_gp.ipynb

# Or use the Python script
python experiments/predict_gp/predict_qatar_gp.py
```

## 🔧 Configuration

### Cache Directory

FastF1 caches downloaded data to speed up future runs. The cache is stored in:
- `notebooks/fastf1_cache_dir/` (for notebooks)
- Or a specified directory in Python scripts

You can modify the cache location in the scripts/notebooks if needed.

### Year Selection

To download data for a specific year, update the `YEAR` variable in:
- `notebooks/save_f1_qualy_results.ipynb`
- `notebooks/save_f1_race_results.ipynb`
- Or corresponding Python scripts in `src/etl/`

## Models Included

| Model | Training Data | Test Data | Accuracy | Location |
|-------|--------------|-----------|----------|----------|
| Basic Model | 2024 R1-16 | 2024 R17-24 | 87.5% | `src/models/podium_model.pkl` |
| Improved Model | 2024 R1-14 | 2024 R15-24 | 86% | `src/models/improved_podium_model.pkl` |
| Tuned 2025 Model | 2025 R1-19 | 2025 R20-24 | 83.3% | `src/models/tuned_podium_model.pkl` |

## Key Features

The models use 22+ engineered features including:
- Qualifying times (Q1, Q2, Q3 in seconds)
- Team one-hot encodings
- Driver momentum (rolling averages of last 3 races)
- Season cumulative statistics (points, DNFs)
- Lag features (previous race positions)
- Track type indicators (street circuit vs permanent)

## Important Notes

### Data Leakage Prevention
- All features use `shift(1)` to ensure only historical data is used
- Time-based train/test splits (no random splits)
- Season statistics calculated with proper temporal alignment

### Class Imbalance
- Models use `class_weight='balanced'` to handle imbalanced podium predictions
- Only ~30 podium finishes per 200+ race entries

### Team Name Normalization
- Team names are normalized across seasons (e.g., RB/AlphaTauri → Racing Bulls)
- Critical for multi-year analysis


## Dependencies

- **fastf1** (>=3.6.1) - F1 data API
- **pandas** (>=2.3.3) - Data manipulation
- **scikit-learn** (>=1.7.2) - Machine learning
- **numpy** (>=2.3.4) - Numerical operations
- **matplotlib** (>=3.10.7) - Visualization
- **seaborn** (>=0.13.2) - Statistical visualization
- **jupyter** (>=1.1.1) - Jupyter notebooks
- **jupyterlab** (>=4.4.10) - Jupyter Lab interface

See `pyproject.toml` for complete dependency list.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

