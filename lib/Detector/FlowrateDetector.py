"""Flow-rate BOCP (normal / Gamma on δ) — port of sandbox/CustomBOC/CustomBOCP_normal.ipynb.

Persisted columns mirror PeakMin (S, I, C, H) plus dx, δ̂, and one-step S_pred for plots.
Episode state (flag, n_step, α, β) lives on the instance only — reset in run_detector().
"""

import numpy as np
import pandas as pd

from lib.Detector.Detector import Detector
from lib.config import FLOWRATE_TABLE, FLOWRATE_CONFIG_PARAMS_DEFAULT, ALARM_CONN

class FlowRateDetector(Detector):
    def __init__(self):
        super().__init__(
            detector_table_config=FLOWRATE_TABLE,
            config_cols=FLOWRATE_CONFIG_PARAMS_DEFAULT.keys(),
        )

    def load_config(self, args={"resource": ALARM_CONN}):
        super().load_config(args=args)
        row = self.config_data.iloc[0]
        self.n_window = int(row["WindowSize"])
        self.alpha0 = float(row["Alpha0"])
        self.beta0 = float(row["Beta0"])
        self.sigma = float(row["Sigma"])
        self.delta_threshold = float(row["deltaXThreshold"])
        alert = float(row["AlertRate"])
        # notebook: calc_gamma(0.99, n_window)
        self.gamma = -np.log(1 - alert) / self.n_window

    def calc_df(self, i):
        signal = self.sandbox_data["AverageFlowRate"].astype(float)
        a = signal.iloc[i]
        b = signal.iloc[i - 1] if i > 0 else a
        if pd.isna(a) or not np.isfinite(a):
            a = 0.0
        if pd.isna(b) or not np.isfinite(b):
            b = 0.0
        return a - b

    def calc_S(self, i):
        """Notebook calc_S: sum(window) - current over [i-T, i)."""
        signal = self.sandbox_data["AverageFlowRate"].astype(float)
        if i <= self.n_window:
            return 0.0
        current_val = signal.iloc[i]
        current_val = 0.0 if pd.isna(current_val) else float(current_val)
        window = signal.iloc[i - self.n_window : i].fillna(0.0)
        return float(np.sum(window - current_val))

    @staticmethod
    def step(delta, n_window, n_step, initial_value=0.0):
        return initial_value + delta * np.clip(n_window - n_step, 0, None)

    @staticmethod
    def indicator_function(delta_est, threshold):
        if pd.isna(delta_est) or not np.isfinite(delta_est):
            return 0
        return 1 if float(delta_est) < threshold else 0

    @staticmethod
    def survival_function(I_t, C_t_1):
        c = 0.0 if pd.isna(C_t_1) or not np.isfinite(C_t_1) else float(C_t_1)
        return c + 1 if I_t == 1 else 0.0

    @staticmethod
    def hazard_function(C_t, gamma):
        c = 0.0 if pd.isna(C_t) or not np.isfinite(C_t) else float(C_t)
        return 1.0 - np.exp(-gamma * c)

    def update(self, i):
        S_i = self.calc_S(i)
        df_i = self.calc_df(i)
        self.sandbox_data.loc[i, "FlowrateS"] = S_i
        self.sandbox_data.loc[i, "FlowrateDx"] = df_i

        if i == 0:
            self.sandbox_data.loc[i, "FlowrateDelta"] = 0.0
            self.sandbox_data.loc[i, "FlowrateSpred"] = 0.0
            self.sandbox_data.loc[i, "FlowrateI"] = 0
            self.sandbox_data.loc[i, "FlowRateC"] = 0.0
            self.sandbox_data.loc[i, "FlowrateH"] = 0.0
            return

        sigma2 = self.sigma**2
        in_episode = self._flag or (df_i > self.delta_threshold)

        if in_episode:
            r = self.n_window - self._n_step
            alpha_i = self._alpha + abs(S_i) / sigma2
            beta_i = self._beta + r / sigma2
            rate_hat = alpha_i / beta_i if beta_i > 0 else 0.0
            delta_est = np.sign(S_i) * rate_hat if S_i != 0 else rate_hat

            self._n_step += 1
            self._flag = True
            self._alpha, self._beta = alpha_i, beta_i

            S_pred = self.step(delta_est, self.n_window, self._n_step, 0.0)
            I_i = self.indicator_function(delta_est, self.delta_threshold)
            c_prev = float(self.sandbox_data["FlowRateC"].iloc[i - 1])
            C_i = self.survival_function(I_i, c_prev)
            H_i = self.hazard_function(C_i, self.gamma)
            self.sandbox_data.loc[i, "FlowrateDelta"] = delta_est
            # notebook: end of window → reset episode on same index
            if self._n_step >= self.n_window:
                self._n_step = 0
                self._alpha = self.alpha0
                self._beta = self.beta0
                self._flag = False
                self.sandbox_data.loc[i, "FlowrateDelta"] = 0.0

            self.sandbox_data.loc[i, "FlowrateSpred"] = S_pred
            self.sandbox_data.loc[i, "FlowrateI"] = I_i
            self.sandbox_data.loc[i, "FlowRateC"] = C_i
            self.sandbox_data.loc[i, "FlowrateH"] = H_i
            self.sandbox_data.loc[i, "FlowrateAlpha"] = alpha_i
            self.sandbox_data.loc[i, "FlowrateBeta"] = beta_i
            self.sandbox_data.loc[i, "FlowRateNStep"] = self._n_step
            self.sandbox_data.loc[i, "FlowRateFlag"] = self._flag
        
        else:
            self.sandbox_data.loc[i, "FlowrateAlpha"] = self.alpha0
            self.sandbox_data.loc[i, "FlowrateBeta"] = self.beta0
            self.sandbox_data.loc[i, "FlowrateDelta"] = 0.0
            self.sandbox_data.loc[i, "FlowrateSpred"] = 0.0
            self.sandbox_data.loc[i, "FlowrateI"] = 0
            self.sandbox_data.loc[i, "FlowRateC"] = 0.0
            self.sandbox_data.loc[i, "FlowrateH"] = 0.0
            self.sandbox_data.loc[i, "FlowRateNStep"] = 0
            self.sandbox_data.loc[i, "FlowRateFlag"] = False


    def run_detector(self, resource=None, write_back=True):
        self._n_step = self.sandbox_data["FlowRateNStep"].iloc[self.first_index]
        self._flag = self.sandbox_data["FlowRateFlag"].iloc[self.first_index]
        self._alpha = self.alpha0
        self._beta = self.beta0
        super().run_detector(resource=resource, write_back=write_back)