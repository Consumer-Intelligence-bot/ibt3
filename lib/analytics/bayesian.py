"""
Bayesian smoothing using Beta-Binomial.
"""
import numpy as np
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


# Evidence strength thresholds for awareness change detection
EVIDENCE_STRONG = 0.95
EVIDENCE_MODERATE = 0.90
EVIDENCE_WEAK = 0.80


def _evidence_label(prob: float) -> str:
    """Classify the posterior probability into an evidence strength label."""
    if prob >= EVIDENCE_STRONG:
        return "strong"
    if prob >= EVIDENCE_MODERATE:
        return "moderate"
    if prob >= EVIDENCE_WEAK:
        return "weak"
    return "none"


def bayesian_change_test(
    successes_a: int, trials_a: int,
    successes_b: int, trials_b: int,
    prior_mean: float,
    prior_strength: int = PRIOR_STRENGTH,
    n_samples: int = 10_000,
    credible_level: float = 0.95,
) -> dict:
    """
    Monte Carlo test for genuine awareness change between two periods.

    Draws samples from the Beta posterior for each period and computes
    the distribution of the difference (rate_B - rate_A).

    Returns dict with:
        posterior_mean_change: shrinkage-adjusted point estimate (rate units)
        ci_lower, ci_upper: credible interval on the change (rate units)
        prob_gain: P(rate_B > rate_A)
        prob_loss: P(rate_B < rate_A)
        significant: True if credible interval excludes zero
        evidence_strength: 'strong'|'moderate'|'weak'|'none'
        direction: 'gain'|'loss'|'flat'
    """
    alpha_prior = max(prior_mean * prior_strength, 0.5)
    beta_prior = max((1 - prior_mean) * prior_strength, 0.5)

    alpha_a = alpha_prior + successes_a
    beta_a = beta_prior + max(trials_a - successes_a, 0)
    alpha_b = alpha_prior + successes_b
    beta_b = beta_prior + max(trials_b - successes_b, 0)

    rng = np.random.default_rng(42)
    samples_a = beta_dist.rvs(alpha_a, beta_a, size=n_samples, random_state=rng)
    samples_b = beta_dist.rvs(alpha_b, beta_b, size=n_samples, random_state=rng)
    delta = samples_b - samples_a

    tail = (1 - credible_level) / 2
    ci_lower, ci_upper = np.percentile(delta, [tail * 100, (1 - tail) * 100])
    mean_change = float(np.mean(delta))
    prob_gain = float((delta > 0).mean())
    prob_loss = float((delta < 0).mean())
    significant = bool(ci_lower > 0 or ci_upper < 0)

    # Direction based on stronger evidence
    if prob_gain >= EVIDENCE_WEAK:
        direction = "gain"
        evidence = _evidence_label(prob_gain)
    elif prob_loss >= EVIDENCE_WEAK:
        direction = "loss"
        evidence = _evidence_label(prob_loss)
    else:
        direction = "flat"
        evidence = "none"

    return {
        "posterior_mean_change": mean_change,
        "ci_lower": float(ci_lower),
        "ci_upper": float(ci_upper),
        "prob_gain": prob_gain,
        "prob_loss": prob_loss,
        "significant": significant,
        "evidence_strength": evidence,
        "direction": direction,
    }
