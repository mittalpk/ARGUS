import numpy as np
from sklearn.metrics import roc_curve, auc

def compute_apcer_bpcer(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> tuple[float, float]:
    """
    Computes APCER and BPCER at a given classification threshold.
    y_true: 0 for genuine (bona fide), 1 for fraudulent (attack).
    """
    preds = (y_prob >= threshold).astype(int)
    
    bona_fide_mask = (y_true == 0)
    attack_mask = (y_true == 1)
    
    if bona_fide_mask.sum() == 0:
        bpcer = 0.0
    else:
        bpcer = np.sum((preds == 1) & bona_fide_mask) / np.sum(bona_fide_mask)
        
    if attack_mask.sum() == 0:
        apcer = 0.0
    else:
        apcer = np.sum((preds == 0) & attack_mask) / np.sum(attack_mask)
        
    return float(apcer), float(bpcer)

def compute_apcer_at_target_bpcer(
    y_true: np.ndarray, 
    y_prob: np.ndarray, 
    target_bpcer: float = 0.01
) -> tuple[float, float, float]:
    """
    Finds the operating point where BPCER is closest to target_bpcer (e.g. 1%)
    and returns (APCER, BPCER, operating_threshold).
    """
    # y_true labels: 1 = fraud (positive class), 0 = genuine (negative class)
    # ROC curve calculations
    fpr, tpr, thresholds = roc_curve(y_true, y_prob)
    
    # BPCER = fpr (False Positive Rate)
    # APCER = 1 - tpr (1 - True Positive Rate)
    
    # Find the threshold where BPCER (fpr) <= target_bpcer
    eligible_indices = np.where(fpr <= target_bpcer)[0]
    if len(eligible_indices) == 0:
        idx = np.argmin(fpr)
    else:
        # Get the index matching the highest index where BPCER <= target
        idx = eligible_indices[-1]
        
    apcer = 1.0 - tpr[idx]
    bpcer = fpr[idx]
    threshold = thresholds[idx]
    
    return float(apcer), float(bpcer), float(threshold)

def compute_audet(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """
    Computes AuDET (Area under Detection Error Trade-off curve).
    Equal to the area under the BPCER (FPR) vs APCER (FNR) curve.
    """
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    fnr = 1.0 - tpr
    
    # Sort by FPR (BPCER) to calculate area correctly
    sort_idx = np.argsort(fpr)
    fpr_sorted = fpr[sort_idx]
    fnr_sorted = fnr[sort_idx]
    
    # Integrate using trapezoidal rule
    audet = np.trapz(fnr_sorted, fpr_sorted)
    return float(audet)
