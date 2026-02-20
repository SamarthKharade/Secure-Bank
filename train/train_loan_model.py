"""
Train Loan Eligibility Model using Logistic Regression
Run this script once to generate the trained model file.

Usage:
    python train/train_loan_model.py
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import pickle
import os

np.random.seed(42)
N = 1500

# Generate synthetic applicant data
data = {
    "average_balance": np.random.uniform(1000, 200000, N),
    "account_age_days": np.random.randint(10, 1500, N),
    "monthly_transaction_count": np.random.randint(0, 50, N),
    "requested_amount": np.random.uniform(10000, 500000, N),
}

df = pd.DataFrame(data)

# Define eligibility rules to generate labels
def is_eligible(row):
    if row["account_age_days"] < 60:
        return 0
    if row["average_balance"] < row["requested_amount"] * 0.1:
        return 0
    if row["monthly_transaction_count"] < 3:
        return 0
    if row["requested_amount"] > row["average_balance"] * 8:
        return 0
    return 1

df["eligible"] = df.apply(is_eligible, axis=1)

X = df[["average_balance", "account_age_days", "monthly_transaction_count", "requested_amount"]].values
y = df["eligible"].values

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print("Training Logistic Regression model for loan eligibility...")

model = Pipeline([
    ("scaler", StandardScaler()),
    ("clf", LogisticRegression(random_state=42, max_iter=1000))
])

model.fit(X_train, y_train)

print("\nModel Performance:")
print(classification_report(y_test, model.predict(X_test)))

# Save model
save_path = os.path.join(os.path.dirname(__file__), "../app/ml_models/loan_model.pkl")
with open(save_path, "wb") as f:
    pickle.dump(model, f)

print(f"✅ Loan eligibility model saved to {save_path}")
