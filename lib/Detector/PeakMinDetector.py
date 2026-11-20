"""Peak-rate (PPM) detector — port of sandbox/CustomBOC/CustomPPM.ipynb.

AlarmData columns
-----------------
Inputs (per survey row, time-ordered by StartDateTime):
  PeakCount            — number of peaks in that survey
  RawDurationMinutes   — survey length (minutes); used with PeakCount for rates
  PeakMinutes          — stored on AlarmData but not used here (reader-derived ratio)

Outputs (written each update at index i):
  PeakS   — P(k_i | H_prev): NegBin predictive likelihood under “still healthy history”
  PeakI   — P(H_cut | k_i): posterior prob. current window is a rate cut / fault regime
  PeakC   — survival counter: grows when PeakI > 0.95, else shrinks (Bernoulli run length)
  PeakH   — hazard in [0,1]: 1 - exp(-gamma * PeakC); alarm strength vs time in “cut” belief

  PeakMin_lastUpdate     — set by base Detector.run_detector when row is processed

Config (PEAKMIN_CONFIG_PARAMS_DEFAULT)
--------------------------------------
  NWindowSize      -> N_win   surveys in λ posterior for H_prev window
  WindowMeasured   -> N_curr  surveys aggregated into (k_i, t_i) at each step
  Alpha0, Beta0    -> Gamma(α,β) prior on peak rate λ (also start a_seq, b_seq)
  LambdaThreshold  -> λ_cut fixed rate under H_cut (Poisson mean λ_cut * t_i)
  PriorWeightPrev  -> Bayes weight on H_prev likelihood
  PriorWeightCut   -> Bayes weight on H_cut likelihood

Instance state (not in DB)
--------------------------
  a_seq, b_seq — running Gamma posterior hyperparameters; reset at each run_detector()
  gamma      — hazard time-scale from calc_gamma(0.995, N_curr) in the notebook
"""

import numpy as np
import pandas as pd
import scipy.stats as stats

from lib.Detector.Detector import Detector
from lib.config import PEAKMIN_TABLE, PEAKMIN_CONFIG_PARAMS_DEFAULT, ALARM_CONN
class PeakMinDetector(Detector):
    def __init__(self):
        super().__init__(
            detector_table_config=PEAKMIN_TABLE,
            config_cols=PEAKMIN_CONFIG_PARAMS_DEFAULT.keys(),
        )

    def load_config(self, args={"resource": ALARM_CONN}):
        super().load_config(args=args)
        row = self.config_data.iloc[0]
        self.N_win = int(row["WindowMeasured"])       # min i before H_prev / Bayes runs
        self.N_curr = int(row["WindowSize"])   # width of (k_i, t_i) aggregate
        self.alpha0 = float(row["Alpha0"])       # Gamma prior shape on λ
        self.beta0 = float(row["Beta0"])         # Gamma prior rate (exposure scale)
        self.lambda_cut = float(row["LambdaThreshold"])  # Poisson rate under fault hypothesis
        self.prior_weight_prev = float(row["PriorWeightPrev"])  # π_prev in Bayes odds
        self.prior_weight_cut = float(row["PriorWeightCut"])   # π_cut  (notebook often 10× prev)
        self.gamma = -np.log(1 - 0.995) / self.N_curr  # hazard slope; notebook calc_gamma
        self.a_seq = self.alpha0  # seq. Gamma shape — updated each i, not written to DB
        self.b_seq = self.beta0   # seq. Gamma rate   — same

    @staticmethod
    def survival_function(P_t, C_t_1):
        """Map P(H_cut) at i to run-length counter C (CustomPPM survival_function)."""
        prev = 0.0 if not np.isfinite(C_t_1) else float(C_t_1)
        if not np.isfinite(P_t):
            return prev  # warmup: Bayes not ready → hold C
        if P_t > 0.95:
            return prev + 1  # another step believing “cut” regime
        return max(0.0, prev - 2)  # evidence against cut → decay C fast

    @staticmethod
    def hazard_function(C_t, gamma):
        """H from C and gamma (CustomPPM hazard_function)."""
        c = 0.0 if pd.isna(C_t) or not np.isfinite(C_t) else float(C_t)
        return 1 - np.exp(-gamma * c)

    def update(self, i):
        """One survey index i — same order as CustomPPM ``for i in range(n):`` loop."""
        peaks = self.sandbox_data["PeakCount"].astype(float)
        duration = self.sandbox_data["RawDurationMinutes"].astype(float)

        # --- Step 1: aggregate recent surveys into one count + exposure (notebook k_i, t_i) ---
        # Slice [lo, i) = N_curr rows ending at i-1 (row i itself is not in the window).
        lo = max(0, i - self.N_curr)
        ki = float(peaks.iloc[lo:i].sum())
        ti = float(duration.iloc[lo:i].sum())
        k_int = int(round(ki)) if np.isfinite(ki) else -1  # discrete count for pmf()

        like_prev = np.nan  # notebook: prob_belongs_prevN[i]
        like_cut = np.nan  # notebook: prob_lambda_cut_like[i]

        # --- Step 2: P(k_i | H_prev) — history window, no overlap with Step 1 aggregate ---
        # Learns λ from [i - N_win - N_curr, i - N_curr); predicts the Step-1 window length t_i.
        if i >= self.N_win and k_int >= 0 and np.isfinite(ti) and ti > 0:
            k_lo = max(0, i - self.N_win - self.N_curr)
            k_hi = max(0, i - self.N_curr)
            k_prev = peaks.iloc[k_lo:k_hi]
            t_prev = duration.iloc[k_lo:k_hi]
            a_win = self.alpha0 + float(k_prev.sum())  # suff. stat for peak counts in history
            b_win = self.beta0 + float(t_prev.sum())   # suff. stat for exposure in history
            if a_win > 0 and b_win > 0:
                p_win = b_win / (b_win + ti)  # NegBin p: predict ti minutes ahead
                like_prev = stats.nbinom.pmf(k_int, a_win, p_win)

        # --- Step 3: P(k_i | H_cut) — single fixed λ_cut, ignores individual survey history ---
        if k_int >= 0 and np.isfinite(ti) and ti > 0:
            mu_cut = self.lambda_cut * ti  # expected peaks in window if fault rate applies
            like_cut = stats.poisson.pmf(k_int, mu_cut)

        # --- Step 4: Bayes → post_H_cut (stored as PeakI); post_H_prev = 1 - PeakI ---
        post_h_prev = np.nan
        post_h_cut = np.nan
        if (
            i >= self.N_win
            and np.isfinite(like_prev)
            and np.isfinite(like_cut)
            and like_prev >= 0
            and like_cut >= 0
        ):
            num = self.prior_weight_prev * like_prev  # weighted evidence for healthy regime
            den = num + self.prior_weight_cut * like_cut
            if den > 0:
                post_h_prev = num / den
                post_h_cut = 1.0 - post_h_prev

        # --- Step 5: write likelihood + posterior cols (warmup rows keep prior Peak*) ---
        if np.isfinite(like_prev):
            self.sandbox_data.loc[i, "PeakS"] = like_prev
        if np.isfinite(post_h_cut):
            self.sandbox_data.loc[i, "PeakI"] = post_h_cut

        # --- Step 6: Bernoulli run-length C, then hazard H (drives alarms with FlowrateH) ---
        c_prev = float(self.sandbox_data["PeakC"].iloc[i - 1]) if i > 0 else 0.0
        if pd.isna(c_prev) or not np.isfinite(c_prev):
            c_prev = 0.0
        c_i = self.survival_function(post_h_cut, c_prev)
        h_i = self.hazard_function(c_i, self.gamma)
        self.sandbox_data.loc[i, "PeakC"] = c_i
        self.sandbox_data.loc[i, "PeakH"] = h_i

        # --- Step 7: optional seq. Gamma(a_seq,b_seq) — notebook λ_post_mean; not persisted ---
        self.a_seq = self.a_seq + (ki if np.isfinite(ki) else 0.0)
        self.b_seq = self.b_seq + (ti if np.isfinite(ti) else 0.0)

    def run_detector(self, resource=None, write_back=True):
        # Reset in-memory λ posterior, then base class loops i from first_index .. len-1.
        self.a_seq = self.alpha0
        self.b_seq = self.beta0
        super().run_detector(resource=resource, write_back=write_back)
