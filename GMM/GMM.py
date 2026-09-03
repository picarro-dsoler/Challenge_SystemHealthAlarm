import numpy as np

class StreamingGMMAlarm:
    def __init__(self, means, covariances, weights, forgetting_factor=0.98, alarm_threshold=0.85):
        """
        means: initial cluster centers, shape (K, D)
        covariances: initial covariance matrices, shape (K, D, D)
        weights: initial cluster mixture weights, shape (K,)
        forgetting_factor (lambda): float close to 1 (e.g., 0.98). Deeper memory.
        alarm_threshold: probability threshold to trigger the transition alarm.
        """
        self.K = len(weights)
        self.D = means.shape[1]
        self.alpha = 1.0 - forgetting_factor  # Learning rate
        self.alarm_threshold = alarm_threshold
        
        # In a standard GMM, we track the direct parameters strictly
        self.weights = np.array(weights, dtype=float)
        self.mu = np.array(means, dtype=float)
        self.sigma = np.array(covariances, dtype=float)
        
        self.previous_probabilities = None

    def _gaussian_likelihood(self, x, mean, cov):
        """Calculates standard multi-dimensional Gaussian probability density."""
        diff = x - mean
        try:
            inv_cov = np.linalg.inv(cov)
            det_cov = np.linalg.det(cov)
        except np.linalg.LinAlgError:
            # Add a small ridge to the diagonal (regularization) if singular
            cov_reg = cov + np.eye(self.D) * 1e-6
            inv_cov = np.linalg.inv(cov_reg)
            det_cov = np.linalg.det(cov_reg)
            
        norm_const = 1.0 / np.sqrt(((2 * np.pi) ** self.D) * det_cov)
        exponent = -0.5 * np.dot(diff, np.dot(inv_cov, diff.T))
        return norm_const * np.exp(exponent)

    def process_point(self, x):
        """Processes a single streaming point, updates parameters, checks alarm."""
        # 1. E-STEP: Compute responsibilities using Bayes' Theorem
        likelihoods = np.zeros(self.K)
        for k in range(self.K):
            likelihoods[k] = self._gaussian_likelihood(x, self.mu[k], self.sigma[k])
            
        weighted_likelihoods = likelihoods * self.weights
        total_likelihood = np.sum(weighted_likelihoods)
        
        if total_likelihood == 0:
            probabilities = self.weights.copy()
        else:
            probabilities = weighted_likelihoods / total_likelihood

        # 2. CHECK ALARM: Detect an abrupt jump from Cluster 1 (Index 0) to Cluster 2 (Index 1)
        alarm_triggered = False
        alarm_msg = ""
        if self.previous_probabilities is not None:
            p_prev_c0 = self.previous_probabilities[0]
            p_curr_c1 = probabilities[1]
            
            if p_prev_c0 > 0.70 and p_curr_c1 > self.alarm_threshold:
                alarm_triggered = True
                alarm_msg = f"⚠️ ALARM: Abrupt jump from Cluster 1 to Cluster 2! (P(C1_prev)={p_prev_c0:.2f} -> P(C2_curr)={p_curr_c1:.2f})"

        # 3. ONLINE M-STEP: Update running GMM parameters
        for k in range(self.K):
            r_k = probabilities[k]
            
            # If a cluster has zero responsibility for this point, its shape doesn't move,
            # but its overall mixture weight will still naturally decay.
            if r_k > 0:
                # Effective learning step adjusted for the cluster's current weight
                rho = self.alpha * (r_k / self.weights[k])
                # Clip rho to 1.0 maximum to avoid unstable mathematical overshooting
                rho = min(rho, 1.0)
                
                # Update Mean
                old_mu = self.mu[k].copy()
                self.mu[k] = (1.0 - rho) * old_mu + rho * x
                
                # Update Covariance Matrix
                diff = (x - old_mu).reshape(-1, 1)
                x_variance = np.dot(diff, diff.T)
                self.sigma[k] = (1.0 - rho) * self.sigma[k] + rho * x_variance
                
        # 4. Update the global mixing weights and re-normalize
        self.weights = (1.0 - self.alpha) * self.weights + self.alpha * probabilities
        self.weights /= np.sum(self.weights)

        # Store history for next iteration
        self.previous_probabilities = probabilities
        
        return probabilities, alarm_triggered, alarm_msg