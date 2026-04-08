"""
DATA UTILITIES FOR PORTFOLIO PRICING ENGINE
============================================
Fidelis Partnership

Provides convenient functions for loading and working with the synthetic
loss data. Import this module in other scripts for consistent data access.

Usage:
    from data.data_utils import load_gross_losses, load_config, get_lob_stats
    
    df = load_gross_losses()
    config = load_config()
    stats = get_lob_stats('PropCat_XL')
"""

import pandas as pd
import numpy as np
import json
import os

# =============================================================================
# PATH CONFIGURATION
# =============================================================================

# Adjust base path depending on where script is run from
def get_data_dir():
    """Find the data directory relative to current working directory."""
    candidates = [
        'team_workspace/data',
        'data',
        '.'
    ]
    for path in candidates:
        if os.path.exists(os.path.join(path, 'gross_losses.csv')):
            return path
    raise FileNotFoundError("Cannot locate data directory with gross_losses.csv")


# =============================================================================
# DATA LOADING FUNCTIONS
# =============================================================================

def load_gross_losses(data_dir=None):
    """
    Load gross losses DataFrame.
    
    Returns:
        pd.DataFrame with columns:
        - simulation_id (int)
        - PropCat_XL (float) - GBP thousands
        - Specialty_Casualty (float)
        - Marine_Hull_Cargo (float)
        - Political_Violence (float)
        - Energy (float)
        - Cyber (float)
    """
    if data_dir is None:
        data_dir = get_data_dir()
    
    path = os.path.join(data_dir, 'gross_losses.csv')
    df = pd.read_csv(path)
    return df


def load_config(data_dir=None):
    """
    Load portfolio configuration JSON.
    
    Returns:
        dict with keys:
        - portfolio_name
        - currency, units
        - n_simulations, random_seed
        - lines_of_business (dict per LoB)
        - correlation (matrix and notes)
        - portfolio_summary (aggregated stats)
        - capital_framework (Lloyd's parameters)
    """
    if data_dir is None:
        data_dir = get_data_dir()
    
    path = os.path.join(data_dir, 'portfolio_config.json')
    with open(path, 'r') as f:
        config = json.load(f)
    return config


def load_net_losses(data_dir=None):
    """
    Load net losses DataFrame (after reinsurance).
    
    Returns:
        pd.DataFrame or None if file doesn't exist yet
    """
    if data_dir is None:
        data_dir = get_data_dir()
    
    path = os.path.join(data_dir, 'net_losses.csv')
    if os.path.exists(path):
        return pd.read_csv(path)
    else:
        return None


# =============================================================================
# CONVENIENCE ACCESSORS
# =============================================================================

LOB_ORDER = ['PropCat_XL', 'Specialty_Casualty', 'Marine_Hull_Cargo', 
             'Political_Violence', 'Energy', 'Cyber']


def get_lob_names():
    """Return list of LoB column names in standard order."""
    return LOB_ORDER.copy()


def get_gwp(lob=None, config=None):
    """
    Get GWP for a single LoB or all LoBs.
    
    Args:
        lob: LoB name, or None for dict of all
        config: Pre-loaded config, or None to load
    
    Returns:
        float (if lob specified) or dict
    """
    if config is None:
        config = load_config()
    
    if lob is not None:
        return config['lines_of_business'][lob]['gwp']
    else:
        return {l: config['lines_of_business'][l]['gwp'] for l in LOB_ORDER}


def get_lob_stats(lob, config=None):
    """
    Get statistics for a single LoB.
    
    Returns dict with:
        gwp, mean_loss, std_loss, cv, loss_ratio_pct,
        zero_pct, var_995, tvar_995, percentiles
    """
    if config is None:
        config = load_config()
    
    return config['lines_of_business'][lob]['statistics']


def get_portfolio_loss(df=None):
    """
    Get portfolio aggregate loss array.
    
    Args:
        df: Losses DataFrame, or None to load
    
    Returns:
        np.array of shape (n_simulations,)
    """
    if df is None:
        df = load_gross_losses()
    
    return df[LOB_ORDER].sum(axis=1).values


def get_correlation_matrix(config=None):
    """
    Get the target Gaussian copula correlation matrix.
    
    Returns:
        np.array of shape (6, 6)
    """
    if config is None:
        config = load_config()
    
    return np.array(config['correlation']['target_matrix'])


# =============================================================================
# RISK METRIC FUNCTIONS
# =============================================================================

def calculate_var(losses, confidence=0.995):
    """
    Calculate Value-at-Risk at given confidence level.
    
    Args:
        losses: Array of loss samples
        confidence: Confidence level (default 99.5%)
    
    Returns:
        float: VaR
    """
    return np.percentile(losses, 100 * confidence)


def calculate_tvar(losses, confidence=0.995):
    """
    Calculate Tail Value-at-Risk (Expected Shortfall) at given confidence level.
    
    TVaR = E[L | L >= VaR]
    
    Args:
        losses: Array of loss samples
        confidence: Confidence level (default 99.5%)
    
    Returns:
        float: TVaR
    """
    var = calculate_var(losses, confidence)
    tail = losses[losses >= var]
    return np.mean(tail) if len(tail) > 0 else var


def calculate_diversification_benefit(df=None, measure='tvar', confidence=0.995):
    """
    Calculate portfolio diversification benefit.
    
    Args:
        df: Losses DataFrame
        measure: 'var' or 'tvar'
        confidence: Confidence level
    
    Returns:
        dict with standalone_sum, portfolio_measure, benefit_pct
    """
    if df is None:
        df = load_gross_losses()
    
    calc_func = calculate_tvar if measure == 'tvar' else calculate_var
    
    # Standalone measures
    standalone = {lob: calc_func(df[lob].values, confidence) for lob in LOB_ORDER}
    standalone_sum = sum(standalone.values())
    
    # Portfolio measure
    portfolio_loss = df[LOB_ORDER].sum(axis=1).values
    portfolio_measure = calc_func(portfolio_loss, confidence)
    
    # Benefit
    benefit_pct = 100 * (1 - portfolio_measure / standalone_sum)
    
    return {
        'standalone': standalone,
        'standalone_sum': standalone_sum,
        'portfolio_measure': portfolio_measure,
        'benefit_pct': benefit_pct
    }


# =============================================================================
# SUMMARY FUNCTIONS
# =============================================================================

def print_portfolio_summary(df=None, config=None):
    """Print a formatted summary of the portfolio."""
    if df is None:
        df = load_gross_losses()
    if config is None:
        config = load_config()
    
    print("=" * 70)
    print("PORTFOLIO SUMMARY")
    print("=" * 70)
    print(f"Simulations: {len(df):,}")
    print(f"Total GWP: GBP {config['portfolio_summary']['total_gwp']:,}k")
    print()
    
    print(f"{'LoB':<22} {'GWP':>10} {'Mean LR':>10} {'CV':>8} {'TVaR99.5':>12}")
    print("-" * 62)
    
    for lob in LOB_ORDER:
        stats = config['lines_of_business'][lob]['statistics']
        print(f"{lob:<22} {stats['gwp']:>10,} {stats['loss_ratio_pct']:>9.1f}% "
              f"{stats['cv']:>8.2f} {stats['tvar_995']:>12,.0f}")
    
    print()
    ps = config['portfolio_summary']
    print(f"Portfolio Mean LR: {ps['mean_lr_pct']:.1f}%")
    print(f"Portfolio TVaR(99.5%): GBP {ps['tvar_995']:,.0f}k")
    print(f"Diversification Benefit: {ps['diversification']['div_benefit_tvar_pct']:.1f}%")


# =============================================================================
# MAIN (for testing)
# =============================================================================

if __name__ == '__main__':
    print("Testing data_utils module...\n")
    
    df = load_gross_losses()
    config = load_config()
    
    print(f"Loaded {len(df):,} simulations")
    print(f"Columns: {list(df.columns)}")
    print()
    
    print_portfolio_summary(df, config)
    
    print("\n[OK] data_utils module working correctly")
