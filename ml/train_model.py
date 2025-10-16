# ml/train_model.py
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
import joblib
import os

# MUST match DB crop order used in backend seed:
CROP_INDEX = ["Pearl Millet","Sorghum","Pigeon Pea","Greengram","Sesame","Groundnut","Horsegram","Cowpea"]

def make_synthetic(n=4000, random_state=1):
    rng = np.random.RandomState(random_state)
    rainfall = rng.uniform(150, 900, n)
    soil_ph = rng.uniform(5.0, 8.5, n)
    area = rng.uniform(500, 20000, n)
    investment = rng.choice([0,1,2], n)  # 0 low,1 med,2 high
    crop_type = rng.choice(len(CROP_INDEX), n)
    base = 800 + 0.5 * (rainfall - 300) + (soil_ph-6.5)*50 + (investment*200)
    crop_mult = np.array([1.0,1.2,0.9,0.8,1.1,1.4,0.7,0.9])
    yields = base * crop_mult[crop_type] + rng.normal(0,150,n)
    price = np.array([10,9,22,30,40,18,20,20])[crop_type]
    input_cost = np.array([10000,12000,9000,7000,6000,15000,5000,6000])[crop_type]
    gross = yields * price / 10000.0
    score = gross - (input_cost/10000.0) + rng.normal(0,2,n)
    df = pd.DataFrame({
        'rainfall':rainfall,'soil_ph':soil_ph,'area':area,'investment':investment,'crop_type':crop_type,
        'yield':yields,'score':score
    })
    return df

def train_and_save():
    df = make_synthetic(4000)
    X = df[['rainfall','soil_ph','area','investment','crop_type']]
    y = df['score']
    X_train, X_test, y_train, y_test = train_test_split(X,y,test_size=0.15, random_state=42)
    model = GradientBoostingRegressor(n_estimators=200, max_depth=4, random_state=42)
    print("Training model...")
    model.fit(X_train, y_train)
    print("Train R2:", model.score(X_train,y_train))
    print("Test R2:", model.score(X_test,y_test))
    os.makedirs('ml/models', exist_ok=True)
    joblib.dump(model, 'ml/models/crop_ranker.pkl')
    print("Saved model to ml/models/crop_ranker.pkl")

if __name__ == "__main__":
    train_and_save()
