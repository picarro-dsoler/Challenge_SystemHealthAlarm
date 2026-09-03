import numpy as np
from scipy.stats import multivariate_normal

Y_EPS = 1e-6


def enforce_positive_y(Y, eps=Y_EPS):
    """Clip Y so it stays strictly positive (physical non-negativity constraint)."""
    return np.maximum(Y, eps)


def build_features_global_raw(Q, Y):
    """
    Build the 4D feature matrix used in BOCPD_test / BOCPD_ENBW notebooks.

    Q and Y are globally z-scored; Y is not log-transformed.
    """
    Q = np.asarray(Q, dtype=float)
    Y = np.asarray(Y, dtype=float)
    Q_norm = (Q - np.mean(Q)) / np.std(Q)
    Y_norm = (Y - np.mean(Y)) / np.std(Y)
    dQ = np.gradient(Q_norm)
    dY = np.gradient(Y_norm)
    return np.column_stack([Q_norm, dQ, Y_norm, dY])


def build_features(Q, Y, eps=Y_EPS):
    """
    Build the 4D BOCPD input matrix.

    Q uses global z-scoring. Y is clipped to be non-negative, then modeled on
    log scale so the implied measurement stays positive.
    """
    Y = enforce_positive_y(Y, eps)

    Q_norm = (Q - np.mean(Q)) / np.std(Q)
    Y_log = np.log(Y)
    Y_feat = (Y_log - np.mean(Y_log)) / (np.std(Y_log) + eps)
    dQ = np.gradient(Q_norm)
    dY = np.gradient(Y_feat)

    return np.column_stack([Q_norm, dQ, Y_feat, dY])


def _rolling_zscore_causal(x, window, min_periods, eps=Y_EPS):
    """Z-score each point using mean/std of past observations only (no lookahead)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    out = np.zeros(n)

    for t in range(n):
        if t == 0:
            continue
        past = x[max(0, t - window) : t]
        if len(past) < min_periods:
            continue
        mu = past.mean()
        sigma = past.std()
        out[t] = (x[t] - mu) / (sigma + eps)

    return out


def build_features_local(Q, Y, window=30, min_periods=10, eps=Y_EPS):
    """
    Build the 4D BOCPD input matrix with causal rolling local z-scoring.

    Q and Y are clipped positive, transformed with log, then z-scored using
    mean/std from the previous `window` observations only. Early points with
    fewer than `min_periods` past samples are left at 0.
    """
    Q = np.maximum(np.asarray(Q, dtype=float), eps)
    Y = enforce_positive_y(Y, eps)
    Q_log = np.log(Q)
    Y_log = np.log(Y)

    Q_feat = _rolling_zscore_causal(Q_log, window, min_periods, eps)
    Y_feat = _rolling_zscore_causal(Y_log, window, min_periods, eps)
    dQ = np.gradient(Q_feat)
    dY = np.gradient(Y_feat)

    return np.column_stack([Q_feat, dQ, Y_feat, dY])


def bocpd_multivariate(X, hazard=1 / 50):
    T, d = X.shape
    R = np.zeros((T + 1, T + 1))
    R[0, 0] = 1.0

    cp_probs = []
    means = [np.zeros((1, d))]
    covs = [np.array([np.eye(d)])]

    for t in range(T):
        x = X[t]
        pred_probs = np.zeros(t + 1)

        for r in range(t + 1):
            try:
                pred_probs[r] = multivariate_normal.pdf(
                    x,
                    mean=means[t][r],
                    cov=covs[t][r] + 1e-4 * np.eye(d),
                    allow_singular=True,
                )
            except Exception:
                pred_probs[r] = 1e-12

        growth_probs = R[: t + 1, t] * pred_probs * (1 - hazard)
        cp_prob = np.sum(R[: t + 1, t] * pred_probs * hazard)

        R[1 : t + 2, t + 1] = growth_probs
        R[0, t + 1] = cp_prob

        normalization = np.sum(R[:, t + 1])
        if normalization > 0:
            R[:, t + 1] /= normalization

        cp_probs.append(R[0, t + 1])

        new_means = np.zeros((t + 2, d))
        new_covs = np.zeros((t + 2, d, d))
        new_means[0] = np.zeros(d)
        new_covs[0] = np.eye(d)

        for r in range(1, t + 2):
            segment = X[t - r + 1 : t + 1]
            new_means[r] = np.mean(segment, axis=0)
            if len(segment) > 3:
                c = np.cov(segment.T)
                new_covs[r] = np.eye(d) if np.ndim(c) == 0 else c
            else:
                new_covs[r] = np.eye(d)

        means.append(new_means)
        covs.append(new_covs)

    return np.array(cp_probs), R


def run_length_alarm(R, threshold=50):
    """Alarm when MAP run length collapses (changepoint)."""
    map_rl = np.argmax(R[:, 1:], axis=0)
    rl_drop = -np.diff(map_rl, prepend=map_rl[0])
    alarm = rl_drop >= threshold
    return rl_drop.astype(float), alarm
