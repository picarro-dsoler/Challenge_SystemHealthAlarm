import numpy as np

REG_EPS = 1e-4


def hotelling_t2(x, mu, cov, reg=REG_EPS):
    """Hotelling T² statistic for one observation vs a multivariate baseline."""
    diff = np.asarray(x, dtype=float) - np.asarray(mu, dtype=float)
    cov_reg = np.asarray(cov, dtype=float) + reg * np.eye(len(mu))
    return float(diff @ np.linalg.solve(cov_reg, diff))


def rolling_hotelling_t2(X, window=30, min_periods=10, reg=REG_EPS):
    """
    Causal Hotelling T²: compare each point to mean/cov of the previous window.
    Early points with fewer than min_periods past samples are left at 0.
    """
    X = np.asarray(X, dtype=float)
    n, d = X.shape
    t2 = np.zeros(n)

    for t in range(n):
        past = X[max(0, t - window) : t]
        if len(past) < min_periods:
            continue
        mu = past.mean(axis=0)
        cov = np.cov(past.T)
        if np.ndim(cov) == 0:
            cov = np.array([[float(cov)]])
        t2[t] = hotelling_t2(X[t], mu, cov, reg=reg)

    return t2


def causal_expanding_hotelling_t2(X, min_periods=20, reg=REG_EPS):
    """Hotelling T² vs mean/cov of all strictly prior observations."""
    X = np.asarray(X, dtype=float)
    n, d = X.shape
    t2 = np.zeros(n)

    for t in range(n):
        if t < min_periods:
            continue
        past = X[:t]
        mu = past.mean(axis=0)
        cov = np.cov(past.T)
        if np.ndim(cov) == 0:
            cov = np.array([[float(cov)]])
        t2[t] = hotelling_t2(X[t], mu, cov, reg=reg)

    return t2


def hotelling_cusum_stat(
    X,
    calibration_size=100,
    reg=REG_EPS,
):
    """
    Classic multivariate (Hotelling) CUSUM against a fixed calibration baseline.

    Returns the squared norm of the cumulative sum of centered observations.
    """
    X = np.asarray(X, dtype=float)
    n, d = X.shape
    calibration_size = min(int(calibration_size), n)

    mu0 = X[:calibration_size].mean(axis=0)
    cov0 = np.cov(X[:calibration_size].T)
    if np.ndim(cov0) == 0:
        cov0 = np.array([[float(cov0)]])
    cov0 = cov0 + reg * np.eye(d)
    inv_cov0 = np.linalg.inv(cov0)

    s = np.zeros(d)
    stat = np.zeros(n)
    for t in range(calibration_size, n):
        s = s + (X[t] - mu0)
        stat[t] = float(s @ inv_cov0 @ s)

    return stat


def cusum_run_length_alarm(
    X,
    calibration_size=100,
    stat_threshold=200.0,
    drop_threshold=50,
    reg=REG_EPS,
):
    """
    BOCPD-compatible changepoint alarm from multivariate CUSUM.

    After calibration, track segment age while the Hotelling CUSUM statistic
    stays below `stat_threshold`. When the statistic crosses the threshold,
    emit the segment age as a run-length drop score (same interpretation as
    BOCPD's MAP run-length collapse).

    Returns
    -------
    score : ndarray
        Run-length drop score (0 except at detected changepoints).
    alarm : ndarray[bool]
        True where score >= drop_threshold.
    stat : ndarray
        Hotelling CUSUM statistic over time.
    """
    X = np.asarray(X, dtype=float)
    n, d = X.shape
    calibration_size = min(int(calibration_size), n)

    mu0 = X[:calibration_size].mean(axis=0)
    cov0 = np.cov(X[:calibration_size].T)
    if np.ndim(cov0) == 0:
        cov0 = np.array([[float(cov0)]])
    cov0 = cov0 + reg * np.eye(d)
    inv_cov0 = np.linalg.inv(cov0)

    s = np.zeros(d)
    age = 0
    score = np.zeros(n)
    alarm = np.zeros(n, dtype=bool)
    stat = np.zeros(n)

    for t in range(calibration_size, n):
        age += 1
        s = s + (X[t] - mu0)
        stat[t] = float(s @ inv_cov0 @ s)

        if stat[t] >= stat_threshold:
            score[t] = age
            alarm[t] = score[t] >= drop_threshold
            age = 0
            s = np.zeros(d)

    return score, alarm, stat


def multivariate_cusum(
    X,
    window=30,
    min_periods=10,
    threshold=25.0,
    drift=1.0,
    reset_on_alarm=True,
    reg=REG_EPS,
    baseline="rolling",
):
    """
    One-sided multivariate CUSUM on Hotelling T².

    Uses a rolling past window by default; set baseline=\"expanding\" for a
    strictly causal expanding baseline.
    """
    X = np.asarray(X, dtype=float)
    n = len(X)

    if baseline == "expanding":
        t2 = causal_expanding_hotelling_t2(X, min_periods=min_periods, reg=reg)
    else:
        t2 = rolling_hotelling_t2(X, window=window, min_periods=min_periods, reg=reg)

    scores = np.zeros(n)
    alarm = np.zeros(n, dtype=bool)
    cusum = 0.0

    for t in range(n):
        if t2[t] == 0:
            continue
        cusum = max(0.0, cusum + t2[t] - drift)
        scores[t] = cusum
        if cusum >= threshold:
            alarm[t] = True
            if reset_on_alarm:
                cusum = 0.0

    return scores, alarm, t2
