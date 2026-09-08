import numpy as np
from pathlib import Path

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)


# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(r"D:\Network_Attak_Forecasting")

DATA_FILE = (
    BASE_DIR
    / "data"
    / "simulated"
    / "fused_train_val_test.npz"
)


# ============================================================
# Load dataset
# ============================================================

print("Loading dataset...")

data = np.load(
    DATA_FILE,
    allow_pickle=True
)

X_train = data["X_train"]
X_val = data["X_val"]
X_test = data["X_test"]

y_attack_train = data["y_attack_train"]
y_attack_val = data["y_attack_val"]
y_attack_test = data["y_attack_test"]

y_stage_train = data["y_stage_train"]
y_stage_val = data["y_stage_val"]
y_stage_test = data["y_stage_test"]

stage_names = data["stage_names"]


print("\nDataset:")
print("X_train:", X_train.shape)
print("X_val:  ", X_val.shape)
print("X_test: ", X_test.shape)


# ============================================================
# IMPORTANT:
# Logistic Regression uses ONLY the CURRENT state.
#
# Transformer will later use all 5 historical states.
#
# X shape:
# (samples, 5, 44)
#
# We use X[:, -1, :] = S(t)
# ============================================================

X_train_current = X_train[:, -1, :]
X_val_current = X_val[:, -1, :]
X_test_current = X_test[:, -1, :]


print("\nCurrent-state feature shape:")
print("Train:", X_train_current.shape)
print("Val:  ", X_val_current.shape)
print("Test: ", X_test_current.shape)


# ============================================================
# Evaluation helper
# ============================================================

def evaluate_binary(model, X, y, name):

    predictions = model.predict(X)

    accuracy = accuracy_score(
        y,
        predictions
    )

    precision = precision_score(
        y,
        predictions,
        zero_division=0
    )

    recall = recall_score(
        y,
        predictions,
        zero_division=0
    )

    f1 = f1_score(
        y,
        predictions,
        zero_division=0
    )

    print(f"\n{'=' * 50}")
    print(name)
    print(f"{'=' * 50}")

    print(f"Accuracy : {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall   : {recall:.4f}")
    print(f"F1 Score : {f1:.4f}")

    print("\nClassification Report:")
    print(
        classification_report(
            y,
            predictions,
            target_names=[
                "Benign",
                "Attack"
            ],
            zero_division=0
        )
    )

    print("Confusion Matrix:")
    print(
        confusion_matrix(
            y,
            predictions
        )
    )

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1
    }


# ============================================================
# 1. LOGISTIC REGRESSION — ATTACK FORECASTING
# ============================================================

print("\n")
print("=" * 60)
print("MODEL 1: LOGISTIC REGRESSION — ATTACK FORECAST")
print("=" * 60)

attack_model = LogisticRegression(
    max_iter=2000,
    class_weight="balanced",
    random_state=42
)

attack_model.fit(
    X_train_current,
    y_attack_train
)


# Validation
attack_val_results = evaluate_binary(
    attack_model,
    X_val_current,
    y_attack_val,
    "Validation — Attack Forecast"
)


# Test
attack_test_results = evaluate_binary(
    attack_model,
    X_test_current,
    y_attack_test,
    "TEST — Attack Forecast"
)


# ============================================================
# 2. LOGISTIC REGRESSION — ATTACK STAGE FORECASTING
# ============================================================

print("\n")
print("=" * 60)
print("MODEL 2: LOGISTIC REGRESSION — STAGE FORECAST")
print("=" * 60)

stage_model = LogisticRegression(
    max_iter=3000,
    class_weight="balanced",
    multi_class="auto",
    random_state=42
)

stage_model.fit(
    X_train_current,
    y_stage_train
)


# ============================================================
# Stage validation
# ============================================================

stage_val_predictions = stage_model.predict(
    X_val_current
)

stage_test_predictions = stage_model.predict(
    X_test_current
)


# ============================================================
# Stage metrics
# ============================================================

stage_val_accuracy = accuracy_score(
    y_stage_val,
    stage_val_predictions
)

stage_val_f1 = f1_score(
    y_stage_val,
    stage_val_predictions,
    average="macro",
    zero_division=0
)

stage_test_accuracy = accuracy_score(
    y_stage_test,
    stage_test_predictions
)

stage_test_f1 = f1_score(
    y_stage_test,
    stage_test_predictions,
    average="macro",
    zero_division=0
)


print("\nValidation:")
print(
    f"Accuracy : {stage_val_accuracy:.4f}"
)

print(
    f"Macro F1 : {stage_val_f1:.4f}"
)


print("\nTEST:")
print(
    f"Accuracy : {stage_test_accuracy:.4f}"
)

print(
    f"Macro F1 : {stage_test_f1:.4f}"
)


print("\nStage Classification Report:")

print(
    classification_report(
        y_stage_test,
        stage_test_predictions,
        labels=np.arange(len(stage_names)),
        target_names=stage_names,
        zero_division=0
    )
)


print("\nStage Confusion Matrix:")

print(
    confusion_matrix(
        y_stage_test,
        stage_test_predictions,
        labels=np.arange(len(stage_names))
    )
)


# ============================================================
# Summary
# ============================================================

print("\n")
print("=" * 60)
print("LOGISTIC REGRESSION BASELINE SUMMARY")
print("=" * 60)

print(
    f"""
Attack Forecast:
    Validation Accuracy : {attack_val_results['accuracy']:.4f}
    Validation F1       : {attack_val_results['f1']:.4f}

    Test Accuracy       : {attack_test_results['accuracy']:.4f}
    Test Precision      : {attack_test_results['precision']:.4f}
    Test Recall         : {attack_test_results['recall']:.4f}
    Test F1             : {attack_test_results['f1']:.4f}

Stage Forecast:
    Validation Accuracy : {stage_val_accuracy:.4f}
    Validation Macro F1 : {stage_val_f1:.4f}

    Test Accuracy       : {stage_test_accuracy:.4f}
    Test Macro F1       : {stage_test_f1:.4f}
"""
)

print("=" * 60)
print("Baseline training complete.")
print("=" * 60)