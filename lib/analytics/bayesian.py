"""
Bayesian smoothing using Beta-Binomial.
"""
from scipy.stats import beta as beta_dist

from lib.config import PRIOR_STRENGTH


def bayesian_smooth_rate(
    successes: int,
    trials: int,
    prior_mean: float,
    prior_strength: int = PRIOR_STRENGTH,
) -> dict:
    """
    Beta-Binomial smoothing. prior_mean should be market average for same demographic.
    Returns posterior_mean, ci_lower, ci_upper, ess, weight, raw_rate.
    """
    if trials == 0:
        return {
            "posterior_mean": prior_mean,
            "ci_lower": prior_mean,
            "ci_upper": prior_mean,
            "ess": prior_strength * 2,
            "weight": 0.0,
            "raw_rate": None,
        }
    alpha_prior = prior_mean * prior_strength
    beta_prior = (1 - prior_mean) * prior_strength
    alpha_post = alpha_prior + successes
    beta_post = beta_prior + (trials - successes)
    posterior_mean = alpha_post / (alpha_post + beta_post)
    ci_lower, ci_upper = beta_dist.ppf([0.025, 0.975], alpha_post, beta_post)
    ess = alpha_post + beta_post
    weight = trials / ess
    raw_rate = successes / trials
    return {
        "posterior_mean": posterior_mean,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "ess": ess,
        "weight": weight,
        "raw_rate": raw_rate,
    }
