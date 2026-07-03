import numpy as np
import pytest
from src.training.metrics import compute_apcer_bpcer, compute_apcer_at_target_bpcer, compute_audet

def test_compute_apcer_bpcer():
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    # Predictions: 4 genuine, 4 fraudulent
    y_prob = np.array([0.1, 0.2, 0.3, 0.8, 0.2, 0.7, 0.8, 0.9])
    
    # Threshold at 0.5:
    # y_prob >= 0.5: [0, 0, 0, 1, 0, 1, 1, 1]
    # FP (genuine pred as fraud): 1 (index 3, prob 0.8) -> BPCER = 1 / 4 = 0.25
    # FN (fraud pred as genuine): 1 (index 4, prob 0.2) -> APCER = 1 / 4 = 0.25
    apcer, bpcer = compute_apcer_bpcer(y_true, y_prob, threshold=0.5)
    assert apcer == 0.25
    assert bpcer == 0.25

def test_compute_apcer_at_target_bpcer():
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    y_prob = np.array([0.1, 0.15, 0.2, 0.25, 0.8, 0.85, 0.9, 0.95])
    
    # This represents perfect split. BPCER (fpr) can be 0.0 at threshold 0.5.
    apcer, bpcer, threshold = compute_apcer_at_target_bpcer(y_true, y_prob, target_bpcer=0.01)
    assert apcer == 0.0
    assert bpcer == 0.0
    assert threshold >= 0.25 and threshold <= 0.8

def test_compute_audet():
    y_true = np.array([0, 0, 1, 1])
    y_prob = np.array([0.1, 0.2, 0.8, 0.9])
    
    # Perfect classifier should have AuDET = 0.0
    audet = compute_audet(y_true, y_prob)
    assert audet == 0.0
