"""
SYNTHETIC LONDON MARKET PORTFOLIO DATA GENERATOR
=================================================
Fidelis Partnership - Portfolio Pricing Engine

This script generates synthetic gross loss scenarios for a London Market 
specialty insurance portfolio. It creates correlated annual aggregate losses
for 6 lines of business using a Gaussian copula with specified marginal
distributions.

Author: Data Architect Agent
Date: 2024

Usage:
    python generate_losses.py

Outputs:
    - data/gross_losses.csv: 100,000 simulation scenarios
    - data/portfolio_config.json: Full configuration and statistics
"""

import numpy as np
import pandas as pd
from scipy.stats import norm, lognorm, nbinom
import json
import os

# =============================================================================
# CONFIGURATION
# =============================================================================

RANDOM_SEED = 42
N_SIMULATIONS = 100_000

# Lines of Business Configuration
# GWP in GBP thousands
LOB_CONFIG = {
    'PropCat_XL': {
        'gwp': 25_000,
        'distribution': {
            'type': 'ParetoGPD',
            'threshold': 5_000,    # Excess layer attachment (GBP k)
            'shape': 0.7,          # GPD shape parameter (xi) - heavy tail
            'scale': 3_500,        # GPD scale parameter (sigma)
            'freq': 0.80           # Probability of occurrence
        },
        'description': 'Property Catastrophe XL - heavy-tailed cat exposure'
    },
    'Specialty_Casualty': {
        'gwp': 20_000,
        'distribution': {
            'type': 'Lognormal',
            'mean': 12_000,        # Expected annual loss (GBP k)
            'cv': 0.80             # Coefficient of variation
        },
        'description': 'Specialty Casualty - D&O, PI, Liability'
    },
    'Marine_Hull_Cargo': {
        'gwp': 15_000,
        'distribution': {
            'type': 'Lognormal',
            'mean': 8_000,
            'cv': 1.20             # Higher CV for hull concentration
        },
        'description': 'Marine Hull & Cargo'
    },
    'Political_Violence': {
        'gwp': 12_000,
        'distribution': {
            'type': 'ParetoGPD',
            'threshold': 2_000,
            'shape': 0.90,         # Very heavy tail
            'scale': 2_500,
            'freq': 0.30           # Low frequency events
        },
        'description': 'Political Violence - terrorism, war, civil commotion'
    },
    'Energy': {
        'gwp': 18_000,
        'distribution': {
            'type': 'Lognormal',
            'mean': 10_000,
            'cv': 1.50             # High volatility - offshore risks
        },
        'description': 'Energy - upstream/downstream, offshore'
    },
    'Cyber': {
        'gwp': 8_000,
        'distribution': {
            'type': 'CompoundNegBinPareto',
            'n': 2,                # NegBin n parameter
            'p': 0.40,             # NegBin p parameter (E[N] = n*(1-p)/p = 3)
            'pareto_shape': 2.5,   # Pareto alpha (tail index)
            'pareto_scale': 800    # Pareto minimum/scale
        },
        'description': 'Cyber - emerging class with systemic risk potential'
    }
}

# Gaussian Copula Correlation Matrix
# Order: PropCat, Casualty, Marine, PolVio, Energy, Cyber
CORRELATION_MATRIX = np.array([
    [1.00, 0.10, 0.25, 0.15, 0.30, 0.20],  # PropCat_XL
    [0.10, 1.00, 0.15, 0.10, 0.10, 0.25],  # Specialty_Casualty
    [0.25, 0.15, 1.00, 0.20, 0.35, 0.15],  # Marine_Hull_Cargo
    [0.15, 0.10, 0.20, 1.00, 0.20, 0.10],  # Political_Violence
    [0.30, 0.10, 0.35, 0.20, 1.00, 0.15],  # Energy
    [0.20, 0.25, 0.15, 0.10, 0.15, 1.00]   # Cyber
])

LOB_ORDER = ['PropCat_XL', 'Specialty_Casualty', 'Marine_Hull_Cargo', 
             'Political_Violence', 'Energy', 'Cyber']

# =============================================================================
# DISTRIBUTION FUNCTIONS
# =============================================================================

def lognormal_params_from_mean_cv(mean, cv):
    """
    Convert mean and coefficient of variation to lognormal (mu, sigma).
    
    For X ~ Lognormal(mu, sigma):
        E[X] = exp(mu + sigma^2/2)
        CV(X) = sqrt(exp(sigma^2) - 1)
    """
    sigma2 = np.log(1 + cv**2)
    sigma = np.sqrt(sigma2)
    mu = np.log(mean) - sigma2 / 2
    return mu, sigma


def inverse_cdf_lognormal(u, mean, cv):
    """Inverse CDF (quantile function) for Lognormal distribution."""
    mu, sigma = lognormal_params_from_mean_cv(mean, cv)
    return lognorm.ppf(u, s=sigma, scale=np.exp(mu))


def inverse_cdf_gpd_with_freq(u, threshold, shape, scale, freq):
    """
    Inverse CDF for zero-inflated Generalized Pareto Distribution.
    
    This models XL attachment behavior:
    - With probability (1-freq): loss = 0 (no cat event hits layer)
    - With probability freq: loss = threshold + GPD(shape, scale)
    
    The GPD is appropriate for excess-of-threshold losses and allows
    for heavy tails when shape > 0.
    
    Parameters:
        u: Uniform(0,1) samples
        threshold: Loss below which layer doesn't attach
        shape: GPD shape parameter (xi). >0 for heavy tail
        scale: GPD scale parameter (sigma)
        freq: Probability of layer being triggered
    """
    losses = np.zeros_like(u)
    triggered = u >= (1 - freq)
    
    if np.any(triggered):
        # Rescale triggered portion to U(0,1)
        u_triggered = (u[triggered] - (1 - freq)) / freq
        
        # GPD inverse CDF
        if shape != 0:
            # x = scale/shape * ((1-u)^(-shape) - 1)
            losses[triggered] = threshold + scale / shape * ((1 - u_triggered)**(-shape) - 1)
        else:
            # Exponential case (shape = 0)
            losses[triggered] = threshold - scale * np.log(1 - u_triggered)
    
    return losses


def simulate_cyber_compound(n_samples, u_samples, n_param, p_param, pareto_shape, pareto_scale):
    """
    Simulate compound Negative Binomial frequency x Pareto severity.
    
    This models cyber risk where:
    - Number of claims ~ NegBin(n, p) with E[N] = n*(1-p)/p
    - Each claim severity ~ Pareto(alpha, scale)
    - Annual aggregate = sum of claim severities
    
    The copula uniform drives claim frequency, maintaining correlation
    with other LoBs. Severities are independent conditional on frequency.
    """
    # Transform uniform to NegBin count
    freq_counts = nbinom.ppf(u_samples, n_param, p_param).astype(int)
    
    losses = np.zeros(n_samples)
    for i in range(n_samples):
        n_claims = freq_counts[i]
        if n_claims > 0:
            # Pareto Type I: P(X > x) = (scale/x)^alpha for x >= scale
            # Inverse CDF: x = scale * u^(-1/alpha)
            severities = pareto_scale * (1 - np.random.random(n_claims))**(-1/pareto_shape)
            losses[i] = np.sum(severities)
    
    return losses


def generate_gaussian_copula_samples(n_samples, corr_matrix):
    """
    Generate correlated uniform samples using Gaussian copula.
    
    Method:
    1. Generate independent N(0,1) samples
    2. Apply Cholesky factor to induce correlation
    3. Transform to U(0,1) via standard normal CDF
    
    The copula captures dependence structure while preserving
    arbitrary marginal distributions.
    """
    n_vars = corr_matrix.shape[0]
    L = np.linalg.cholesky(corr_matrix)
    Z = np.random.standard_normal((n_samples, n_vars))
    Z_correlated = Z @ L.T
    U = norm.cdf(Z_correlated)
    return U


# =============================================================================
# MAIN GENERATION FUNCTION
# =============================================================================

def generate_portfolio_losses(seed=RANDOM_SEED, n_sims=N_SIMULATIONS):
    """
    Generate synthetic loss scenarios for the full portfolio.
    
    Returns:
        DataFrame with simulation_id and loss columns for each LoB
    """
    np.random.seed(seed)
    
    # Step 1: Generate correlated uniforms via Gaussian copula
    U = generate_gaussian_copula_samples(n_sims, CORRELATION_MATRIX)
    
    # Step 2: Transform each column to its marginal distribution
    losses = {}
    
    for i, lob in enumerate(LOB_ORDER):
        config = LOB_CONFIG[lob]
        dist = config['distribution']
        u = U[:, i]
        
        if dist['type'] == 'Lognormal':
            losses[lob] = inverse_cdf_lognormal(u, dist['mean'], dist['cv'])
            
        elif dist['type'] == 'ParetoGPD':
            losses[lob] = inverse_cdf_gpd_with_freq(
                u, dist['threshold'], dist['shape'], dist['scale'], dist['freq']
            )
            
        elif dist['type'] == 'CompoundNegBinPareto':
            # Set separate seed for severity to maintain reproducibility
            np.random.seed(seed + 999)
            losses[lob] = simulate_cyber_compound(
                n_sims, u, dist['n'], dist['p'], 
                dist['pareto_shape'], dist['pareto_scale']
            )
    
    # Create DataFrame
    df = pd.DataFrame(losses)
    df.insert(0, 'simulation_id', range(n_sims))
    
    return df


def compute_statistics(df, losses_dict):
    """Compute comprehensive statistics for each LoB and portfolio."""
    
    lob_stats = {}
    
    for lob in LOB_ORDER:
        x = losses_dict[lob]
        gwp = LOB_CONFIG[lob]['gwp']
        
        mean_loss = float(np.mean(x))
        std_loss = float(np.std(x))
        cv = std_loss / mean_loss if mean_loss > 0 else 0
        zero_pct = float(100 * np.sum(x == 0) / len(x))
        
        percentiles = {
            'p50': float(np.percentile(x, 50)),
            'p75': float(np.percentile(x, 75)),
            'p90': float(np.percentile(x, 90)),
            'p95': float(np.percentile(x, 95)),
            'p99': float(np.percentile(x, 99)),
            'p995': float(np.percentile(x, 99.5)),
            'max': float(np.max(x))
        }
        
        var_995 = percentiles['p995']
        tail_losses = x[x >= var_995]
        tvar_995 = float(np.mean(tail_losses)) if len(tail_losses) > 0 else var_995
        
        lob_stats[lob] = {
            'gwp': gwp,
            'mean_loss': mean_loss,
            'std_loss': std_loss,
            'cv': cv,
            'loss_ratio_pct': 100 * mean_loss / gwp,
            'zero_pct': zero_pct,
            'var_995': var_995,
            'tvar_995': tvar_995,
            'percentiles': percentiles
        }
    
    return lob_stats


# =============================================================================
# SCRIPT EXECUTION
# =============================================================================

if __name__ == '__main__':
    print("="*70)
    print("SYNTHETIC LONDON MARKET PORTFOLIO DATA GENERATOR")
    print("Fidelis Partnership - Portfolio Pricing Engine")
    print("="*70)
    
    # Generate losses
    print(f"\nGenerating {N_SIMULATIONS:,} simulation scenarios...")
    df_losses = generate_portfolio_losses()
    
    # Extract losses dict for stats
    losses = {lob: df_losses[lob].values for lob in LOB_ORDER}
    
    # Compute statistics
    lob_stats = compute_statistics(df_losses, losses)
    
    # Display summary
    print("\nLoss Distribution Summary:")
    print("-"*70)
    for lob in LOB_ORDER:
        s = lob_stats[lob]
        print(f"{lob}: Mean LR = {s['loss_ratio_pct']:.1f}%, "
              f"CV = {s['cv']:.2f}, TVaR(99.5%) = {s['tvar_995']:,.0f}k")
    
    # Save files
    df_losses.to_csv('gross_losses.csv', index=False)
    print(f"\n[SAVED] gross_losses.csv")
    
    print("\nGeneration complete.")
