import pandas as pd
import numpy as np
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score, confusion_matrix

class NaiveRetryBaseline:
    """
    Naive Baseline Recovery Model:
    Retries every eligible failed payment once after a fixed delay without ML intelligence.
    Rules out only high-risk compliance failures (e.g. RISK_REJECTED).
    """

    def __init__(self, name: str = "Naive Single-Retry Baseline"):
        self.name = name

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Returns fixed heuristics probabilities.
        Eligible failures get fixed ~0.65 probability, risk rejects get 0.05.
        """
        probas = []
        for idx, row in X.iterrows():
            f_code = row.get("failure_code", "")
            r_count = row.get("retry_count", 0)
            if f_code == "RISK_REJECTED" or r_count >= 3:
                probas.append([0.95, 0.05])
            else:
                probas.append([0.35, 0.65])
        return np.array(probas)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Returns binary predictions (1 = retry/recoverable, 0 = do not retry).
        """
        probas = self.predict_proba(X)
        return (probas[:, 1] >= 0.5).astype(int)

    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
        """
        Evaluates naive baseline predictions against ground truth test set.
        """
        y_pred = self.predict(X_test)
        y_proba = self.predict_proba(X_test)[:, 1]

        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        acc = accuracy_score(y_test, y_pred)
        cm = confusion_matrix(y_test, y_pred).tolist()

        return {
            "model_name": self.name,
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1": round(float(f1), 4),
            "accuracy": round(float(acc), 4),
            "confusion_matrix": cm
        }
