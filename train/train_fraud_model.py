"""
Train Fraud Detection Model using Isolation Forest
Run this script once to generate the trained model file.

Usage:
    python train/train_fraud_model.py
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import pickle
import os

# ─────────────────────────────────────────────
# Generate Synthetic Training Data
# ─────────────────────────────────────────────

np.random.seed(42)
N_NORMAL = 2000
N_FRAUD = 200

# Normal transactions
normal_data = {
    "amount": np.random.lognormal(mean=7, sigma=1, size=N_NORMAL),       # ~₹1000 avg
    "hour": np.random.choice(range(8, 22), size=N_NORMAL),                # Business hours
    "balance_before": np.random.uniform(5000, 100000, size=N_NORMAL),
    "transaction_count_today": np.random.randint(1, 8, size=N_NORMAL)
}

# Fraudulent transactions (unusual patterns)
fraud_data = {
    "amount": np.random.uniform(50000, 500000, size=N_FRAUD),             # Very high amounts
    "hour": np.random.choice(range(0, 5), size=N_FRAUD),                  # Late night
    "balance_before": np.random.uniform(100, 5000, size=N_FRAUD),         # Low balance
    "transaction_count_today": np.random.randint(15, 30, size=N_FRAUD)   # Too many txns
}

# Combine
normal_df = pd.DataFrame(normal_data)
fraud_df = pd.DataFrame(fraud_data)
df = pd.concat([normal_df, fraud_df], ignore_index=True)

X = df[["amount", "hour", "balance_before", "transaction_count_today"]].values

# ─────────────────────────────────────────────
# Train Isolation Forest
# ─────────────────────────────────────────────

print("Training Isolation Forest model...")

model = Pipeline([
    ("scaler", StandardScaler()),
    ("clf", IsolationForest(
        n_estimators=100,
        contamination=0.09,  # ~9% fraud rate
        random_state=42
    ))
])

model.fit(X)

# ─────────────────────────────────────────────
# Save Model
# ─────────────────────────────────────────────

save_path = os.path.join(os.path.dirname(__file__), "../app/ml_models/fraud_model.pkl")
with open(save_path, "wb") as f:
    pickle.dump(model, f)

print(f"✅ Fraud detection model saved to {save_path}")

# ─────────────────────────────────────────────
# Quick Test
# ─────────────────────────────────────────────

test_normal = np.array([[1500, 14, 25000, 3]])      # Normal transaction
test_fraud = np.array([[200000, 2, 500, 20]])        # Suspicious transaction

pred_normal = model.predict(test_normal)[0]
pred_fraud = model.predict(test_fraud)[0]

print(f"\nTest Results:")
print(f"Normal transaction (₹1500, 2pm, ₹25k balance): {'✅ NORMAL' if pred_normal == 1 else '⚠️ FLAGGED'}")
print(f"Fraud transaction (₹2L, 2am, ₹500 balance):   {'✅ NORMAL' if pred_fraud == 1 else '🚨 FLAGGED (correct!)'}")
