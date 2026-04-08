"""
Spectral Risk Measure Framework - Version 1
============================================

Dual Risk Measure Framework for Lloyd's Portfolio Pricing Engine

Author: Quantitative Risk Modeller
Date: 2024
Workspace: team_workspace

Purpose:
--------
Implements TWO separate risk measures for TWO separate purposes:

1. CAPITAL MEASURE - TVaR at 99.5%
   - Regulatory capital requirement (Lloyd's SCR alignment)
   - Euler gradient allocation per LoB
   - Answers: "how much capital must we hold?"

2. PRICING MEASURE - Wang Transform distortion
   - Risk loading embedded in pricing hurdle
   - g(s) = Phi(Phi_inv(s) + lambda)
   - Answers: "what risk premium should we charge?"

Key Features:
-------------
- Lambda calibrated on NET aggregate loss to 9% target ROAC
- Reserve risk loading applied to TVaR capital
- Mean term of claims for investment income
- Same lambda applied to both gross and net loss vectors
- Alternative spectral measures for comparison
- Fully vectorized for computational efficiency

Dependencies:
-------------
numpy, scipy, pandas
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import brentq
import time
from typing import Dict, Tuple, Optional


class SpectralRiskEngine:
    """
    Engine for computing spectral risk measures and capital allocation
    on a portfolio of correlated loss distributions.
    
    Attributes:
    -----------
    gross_losses : np.ndarray
        Matrix of gross losses (n_sims x n_lobs)
    net_losses : np.ndarray
        Matrix of net losses (n_sims x n_lobs)
    lob_names : list
        Names of lines of business
    confidence_level : float
        Regulatory confidence level (default 0.995 for Lloyd's)
    """
    
    def __init__(self, 
                 gross_losses: np.ndarray, 
                 net_losses: np.ndarray,
                 lob_names: list,
                 confidence_level: float = 0.995):
        """
        Initialize the spectral risk engine.
        
        Parameters:
        -----------
        gross_losses : np.ndarray
            Matrix of gross losses (n_sims x n_lobs)
        net_losses : np.ndarray
            Matrix of net losses (n_sims x n_lobs)
        lob_names : list
            Names of lines of business
        confidence_level : float
            Regulatory confidence level (default 0.995)
        """
        self.gross_losses = gross_losses
        self.net_losses = net_losses
        self.lob_names = lob_names
        self.confidence_level = confidence_level
        self.n_sims = gross_losses.shape[0]
        self.n_lobs = gross_losses.shape[1]
        
        # Validate inputs
        assert gross_losses.shape == net_losses.shape, "Gross and net losses must have same shape"
        assert gross_losses.shape[1] == len(lob_names), "Number of LoBs must match lob_names"
        
        # Reserve risk loading multipliers (per LoB)
        # These adjust premium risk TVaR to approximate total capital need
        self.reserve_risk_loading = {
            'PropCat_XL': 1.05,           # Short-tail, minimal reserves
            'Specialty_Casualty': 1.45,   # Long-tail, large reserves
            'Marine_Hull_Cargo': 1.25,    # Medium-tail
            'Political_Violence': 1.10,   # Event-driven, short settlement
            'Energy': 1.30,               # Medium-long tail
            'Cyber': 1.15                 # Emerging, short-medium tail
        }
        
        # Mean term of claims in years (for investment income)
        self.mean_term = {
            'PropCat_XL': 0.75,           # Fast-settling catastrophe claims
            'Specialty_Casualty': 3.50,   # Long-tail casualty reserves
            'Marine_Hull_Cargo': 2.00,    # Medium settlement
            'Political_Violence': 1.00,   # Event-driven, quick settlement
            'Energy': 2.50,               # Medium-long settlement
            'Cyber': 1.15                 # Short-medium, evolving class
        }
        
    def compute_tvar(self, losses: np.ndarray, confidence_level: float = None) -> float:
        """
        Compute Tail Value at Risk (TVaR) / Expected Shortfall.
        
        TVaR is the expected loss conditional on exceeding VaR.
        
        Parameters:
        -----------
        losses : np.ndarray
            Loss vector (can be 1D or aggregate of multiple columns)
        confidence_level : float
            Confidence level (default uses self.confidence_level)
            
        Returns:
        --------
        float : TVaR value
        """
        if confidence_level is None:
            confidence_level = self.confidence_level
            
        # Ensure 1D
        if len(losses.shape) > 1:
            losses = losses.flatten()
            
        # Sort losses
        sorted_losses = np.sort(losses)
        
        # Find VaR threshold
        var_index = int(np.ceil(confidence_level * len(sorted_losses))) - 1
        var = sorted_losses[var_index]
        
        # TVaR is mean of all losses >= VaR
        tvar = np.mean(sorted_losses[sorted_losses >= var])
        
        return tvar
    
    def compute_var(self, losses: np.ndarray, confidence_level: float = None) -> float:
        """
        Compute Value at Risk (VaR).
        
        Parameters:
        -----------
        losses : np.ndarray
            Loss vector
        confidence_level : float
            Confidence level
            
        Returns:
        --------
        float : VaR value
        """
        if confidence_level is None:
            confidence_level = self.confidence_level
            
        if len(losses.shape) > 1:
            losses = losses.flatten()
            
        return np.percentile(losses, confidence_level * 100)
    
    def euler_allocation(self, losses: np.ndarray, epsilon: float = 0.001) -> np.ndarray:
        """
        Compute Euler gradient allocation of TVaR capital to individual LoBs.
        
        This is the industry-standard method for allocating diversified portfolio
        capital back to individual business units. It satisfies:
        - Full allocation: sum of allocations = portfolio TVaR
        - Gradient property: allocation_i = d(TVaR)/d(lambda_i)
        
        Implementation uses finite difference approximation:
        allocation_i ≈ [TVaR(portfolio + ε*LoB_i) - TVaR(portfolio - ε*LoB_i)] / (2*ε)
        
        Parameters:
        -----------
        losses : np.ndarray
            Loss matrix (n_sims x n_lobs)
        epsilon : float
            Finite difference step size
            
        Returns:
        --------
        np.ndarray : Allocated capital per LoB
        """
        n_sims, n_lobs = losses.shape
        
        # Compute portfolio TVaR
        portfolio_losses = losses.sum(axis=1)
        portfolio_tvar = self.compute_tvar(portfolio_losses)
        
        # Allocate via Euler gradient method
        allocations = np.zeros(n_lobs)
        
        for i in range(n_lobs):
            # Perturb LoB i upward
            perturbed_up = losses.copy()
            perturbed_up[:, i] += epsilon
            tvar_up = self.compute_tvar(perturbed_up.sum(axis=1))
            
            # Perturb LoB i downward
            perturbed_down = losses.copy()
            perturbed_down[:, i] -= epsilon
            tvar_down = self.compute_tvar(perturbed_down.sum(axis=1))
            
            # Gradient approximation
            gradient = (tvar_up - tvar_down) / (2 * epsilon)
            allocations[i] = gradient
        
        # Normalize to ensure exact allocation (handles numerical errors)
        allocations = allocations * (portfolio_tvar / allocations.sum())
        
        return allocations
    
    def apply_reserve_risk_loading(self, allocations: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Apply reserve risk loading to premium risk capital allocations.
        
        This approximates total capital requirement by scaling up premium risk
        capital using LoB-specific multipliers that reflect reserve risk.
        
        Parameters:
        -----------
        allocations : np.ndarray
            Premium risk TVaR allocations per LoB
            
        Returns:
        --------
        tuple : (adjusted_allocations, portfolio_adjusted_tvar)
        """
        adjusted = np.zeros_like(allocations)
        
        for i, lob in enumerate(self.lob_names):
            loading = self.reserve_risk_loading.get(lob, 1.0)
            adjusted[i] = allocations[i] * loading
        
        portfolio_adjusted = adjusted.sum()
        
        return adjusted, portfolio_adjusted
    
    def compute_wang_el(self, losses: np.ndarray, lambda_param: float) -> float:
        """
        Compute Wang Transform expected loss (risk-adjusted expectation).
        
        The Wang Transform is a spectral risk measure that distorts probabilities:
        g(s) = Φ(Φ^(-1)(s) + λ)
        
        For empirical distribution with ordered sample L_1 <= L_2 <= ... <= L_n:
        E_Wang[L] = sum_{i=1}^n L_i * [g((n-i+1)/n) - g((n-i)/n)]
        
        where g is applied to the survival function S(x) = P(L >= x).
        
        Fully vectorized for computational efficiency.
        
        Parameters:
        -----------
        losses : np.ndarray
            Loss vector (1D)
        lambda_param : float
            Wang Transform parameter (higher = more risk-averse)
            
        Returns:
        --------
        float : Wang-adjusted expected loss
        """
        if len(losses.shape) > 1:
            losses = losses.flatten()
        
        # Sort losses
        sorted_losses = np.sort(losses)
        n = len(sorted_losses)
        
        # Vectorized survival probabilities
        indices = np.arange(n)
        s_before = (n - indices) / n
        s_after = (n - indices - 1) / n
        
        # Clip to avoid numerical issues with ppf at boundaries
        s_before = np.clip(s_before, 1e-10, 0.9999999)
        s_after = np.clip(s_after, 1e-10, 0.9999999)
        
        # Vectorized Wang distortion
        g_before = stats.norm.cdf(stats.norm.ppf(s_before) + lambda_param)
        g_after = stats.norm.cdf(stats.norm.ppf(s_after) + lambda_param)
        
        # Compute weights
        weights = g_before - g_after
        
        # Wang expected loss is weighted sum
        wang_el = np.sum(sorted_losses * weights)
        
        return wang_el
    
    def compute_hp(self, losses: np.ndarray, lambda_param: float) -> float:
        """
        Compute Hazard Premium (HP) - the risk loading above expected loss.
        
        HP = Wang_EL - E[L]
        
        This is the additional premium required to compensate for bearing risk
        at the specified lambda level.
        
        Parameters:
        -----------
        losses : np.ndarray
            Loss vector
        lambda_param : float
            Wang Transform parameter
            
        Returns:
        --------
        float : Hazard premium
        """
        wang_el = self.compute_wang_el(losses, lambda_param)
        expected_loss = np.mean(losses)
        hp = wang_el - expected_loss
        
        return hp
    
    def calibrate_lambda(self, 
                        net_losses: np.ndarray,
                        target_roac: float = 0.09,
                        lambda_range: Tuple[float, float] = (0.001, 3.0)) -> Dict:
        """
        Calibrate Wang Transform lambda parameter to achieve target ROAC.
        
        Calibration target:
        (Wang_EL[net_portfolio] - EL[net_portfolio]) = target_roac * TVaR_adjusted_portfolio
        
        Lambda is calibrated on the NET aggregate portfolio because:
        - Insurers are capitalized on net-of-RI basis
        - Lambda reflects company-level risk appetite
        
        The reserve-risk-adjusted TVaR is used as the capital target.
        
        Parameters:
        -----------
        net_losses : np.ndarray
            Net loss matrix (n_sims x n_lobs)
        target_roac : float
            Target return on adjusted capital (default 0.09 = 9%)
        lambda_range : tuple
            Search range for lambda
            
        Returns:
        --------
        dict : Calibration results including lambda, Wang EL, target HP, achieved ROAC
        """
        # Compute net portfolio aggregate losses
        net_portfolio = net_losses.sum(axis=1)
        
        # Compute premium risk TVaR capital
        net_tvar_premium = self.compute_tvar(net_portfolio)
        
        # Apply reserve risk loading
        net_allocations = self.euler_allocation(net_losses)
        net_allocations_adjusted, net_tvar_adjusted = self.apply_reserve_risk_loading(net_allocations)
        
        # Target hazard premium
        target_hp = target_roac * net_tvar_adjusted
        
        # Expected loss
        net_el = net_portfolio.mean()
        
        # Define objective function: find lambda such that Wang HP = target HP
        def objective(lam):
            wang_el = self.compute_wang_el(net_portfolio, lam)
            hp = wang_el - net_el
            return hp - target_hp
        
        # Test boundary values
        obj_low = objective(lambda_range[0])
        obj_high = objective(lambda_range[1])
        
        # Solve using Brent's method
        try:
            lambda_calibrated = brentq(objective, lambda_range[0], lambda_range[1])
        except ValueError as e:
            # If no solution in range, report boundary behavior
            hp_low = obj_low + target_hp
            hp_high = obj_high + target_hp
            raise ValueError(
                f"Lambda calibration failed. No solution in range {lambda_range}.\n"
                f"HP at lambda={lambda_range[0]}: £{hp_low:,.0f}k\n"
                f"HP at lambda={lambda_range[1]}: £{hp_high:,.0f}k\n"
                f"Target HP: £{target_hp:,.0f}k\n"
                f"Objective at low: {obj_low:,.0f}\n"
                f"Objective at high: {obj_high:,.0f}\n"
                f"Net EL: £{net_el:,.0f}k\n"
                f"Net TVaR adjusted: £{net_tvar_adjusted:,.0f}k"
            )
        
        # Compute achieved values
        wang_el_achieved = self.compute_wang_el(net_portfolio, lambda_calibrated)
        hp_achieved = wang_el_achieved - net_el
        roac_achieved = hp_achieved / net_tvar_adjusted
        
        results = {
            'lambda': lambda_calibrated,
            'target_roac': target_roac,
            'achieved_roac': roac_achieved,
            'net_tvar_premium_risk': net_tvar_premium,
            'net_tvar_adjusted': net_tvar_adjusted,
            'net_el': net_el,
            'wang_el': wang_el_achieved,
            'target_hp': target_hp,
            'achieved_hp': hp_achieved,
            'calibration_error_pct': abs(roac_achieved - target_roac) / target_roac * 100
        }
        
        return results
    
    def compute_portfolio_metrics(self, lambda_param: float, investment_yield: float = 0.02) -> pd.DataFrame:
        """
        Compute comprehensive risk and pricing metrics for all LoBs.
        
        This is the main output function that produces per-LoB analysis including:
        - TVaR capital allocation (net and gross)
        - Reserve-risk-adjusted capital
        - Wang Transform hazard premiums (net and gross)
        - Investment income (net and gross)
        - Risk-adjusted pricing hurdles
        
        Parameters:
        -----------
        lambda_param : float
            Calibrated Wang Transform parameter
        investment_yield : float
            Annual investment yield (default 2%)
            
        Returns:
        --------
        pd.DataFrame : Comprehensive metrics per LoB
        """
        # Compute net allocations
        net_allocations = self.euler_allocation(self.net_losses)
        net_allocations_adjusted, net_tvar_adjusted = self.apply_reserve_risk_loading(net_allocations)
        
        # Compute gross allocations
        gross_allocations = self.euler_allocation(self.gross_losses)
        gross_allocations_adjusted, gross_tvar_adjusted = self.apply_reserve_risk_loading(gross_allocations)
        
        # Build results DataFrame
        results = []
        
        for i, lob in enumerate(self.lob_names):
            # Expected losses
            gross_el = self.gross_losses[:, i].mean()
            net_el = self.net_losses[:, i].mean()
            
            # Wang Transform metrics (using same lambda for both)
            wang_el_gross = self.compute_wang_el(self.gross_losses[:, i], lambda_param)
            wang_el_net = self.compute_wang_el(self.net_losses[:, i], lambda_param)
            
            hp_gross = wang_el_gross - gross_el
            hp_net = wang_el_net - net_el
            
            # Investment income
            mean_term_lob = self.mean_term.get(lob, 2.0)
            inv_income_gross = investment_yield * mean_term_lob * gross_el
            inv_income_net = investment_yield * mean_term_lob * net_el
            
            # Reserve risk loading
            reserve_loading = self.reserve_risk_loading.get(lob, 1.0)
            
            results.append({
                'LoB': lob,
                
                # Capital metrics (premium risk)
                'TVaR_Net_Premium': net_allocations[i],
                'TVaR_Gross_Premium': gross_allocations[i],
                
                # Reserve risk adjustment
                'Reserve_Risk_Loading': reserve_loading,
                'TVaR_Net_Adjusted': net_allocations_adjusted[i],
                'TVaR_Gross_Adjusted': gross_allocations_adjusted[i],
                
                # Expected losses
                'EL_Gross': gross_el,
                'EL_Net': net_el,
                
                # Wang Transform pricing
                'Wang_EL_Gross': wang_el_gross,
                'Wang_EL_Net': wang_el_net,
                'HP_Gross': hp_gross,
                'HP_Net': hp_net,
                
                # Investment income
                'Mean_Term_Years': mean_term_lob,
                'Inv_Income_Gross': inv_income_gross,
                'Inv_Income_Net': inv_income_net,
                
                # Risk-adjusted metrics
                'Risk_Adjusted_EL_Gross': wang_el_gross - inv_income_gross,
                'Risk_Adjusted_EL_Net': wang_el_net - inv_income_net,
            })
        
        df = pd.DataFrame(results)
        
        return df
    
    def compare_spectral_measures(self, losses: np.ndarray, lambda_wang: float) -> pd.DataFrame:
        """
        Compare Wang Transform to alternative spectral measures.
        
        For reference, evaluates:
        1. Wang Transform: g(s) = Φ(Φ^(-1)(s) + λ)
        2. Power Distortion: g(s) = s^(1/(1+θ))
        3. Dual Power: g(s) = 1 - (1-s)^(1+γ)
        
        Parameters:
        -----------
        losses : np.ndarray
            Loss vector (typically PropCat gross for comparison)
        lambda_wang : float
            Calibrated Wang lambda
            
        Returns:
        --------
        pd.DataFrame : Comparison of measures
        """
        # TVaR baseline
        tvar = self.compute_tvar(losses)
        
        # Wang Transform
        wang_el = self.compute_wang_el(losses, lambda_wang)
        
        # Power Distortion: calibrate theta to match Wang (vectorized)
        def power_distortion_el(theta):
            sorted_losses = np.sort(losses)
            n = len(sorted_losses)
            indices = np.arange(n)
            s_before = np.clip((n - indices) / n, 1e-10, 0.9999999)
            s_after = np.clip((n - indices - 1) / n, 1e-10, 0.9999999)
            g_before = s_before ** (1 / (1 + theta))
            g_after = s_after ** (1 / (1 + theta))
            weights = g_before - g_after
            return np.sum(sorted_losses * weights)
        
        # Find theta that gives similar risk loading to Wang
        theta_test = np.linspace(0.1, 2.0, 20)
        power_els = [power_distortion_el(t) for t in theta_test]
        best_theta_idx = np.argmin(np.abs(np.array(power_els) - wang_el))
        best_theta = theta_test[best_theta_idx]
        power_el = power_els[best_theta_idx]
        
        # Dual Power: calibrate gamma similarly (vectorized)
        def dual_power_el(gamma):
            sorted_losses = np.sort(losses)
            n = len(sorted_losses)
            indices = np.arange(n)
            s_before = np.clip((n - indices) / n, 1e-10, 0.9999999)
            s_after = np.clip((n - indices - 1) / n, 1e-10, 0.9999999)
            g_before = 1 - (1 - s_before) ** (1 + gamma)
            g_after = 1 - (1 - s_after) ** (1 + gamma)
            weights = g_before - g_after
            return np.sum(sorted_losses * weights)
        
        gamma_test = np.linspace(0.1, 2.0, 20)
        dual_els = [dual_power_el(g) for g in gamma_test]
        best_gamma_idx = np.argmin(np.abs(np.array(dual_els) - wang_el))
        best_gamma = gamma_test[best_gamma_idx]
        dual_el = dual_els[best_gamma_idx]
        
        # Build comparison
        comparison = pd.DataFrame([
            {
                'Measure': 'TVaR 99.5%',
                'Parameter': 'confidence=0.995',
                'Value': tvar,
                'Pct_Diff_from_TVaR': 0.0
            },
            {
                'Measure': 'Wang Transform',
                'Parameter': f'lambda={lambda_wang:.4f}',
                'Value': wang_el,
                'Pct_Diff_from_TVaR': (wang_el - tvar) / tvar * 100
            },
            {
                'Measure': 'Power Distortion',
                'Parameter': f'theta={best_theta:.4f}',
                'Value': power_el,
                'Pct_Diff_from_TVaR': (power_el - tvar) / tvar * 100
            },
            {
                'Measure': 'Dual Power',
                'Parameter': f'gamma={best_gamma:.4f}',
                'Value': dual_el,
                'Pct_Diff_from_TVaR': (dual_el - tvar) / tvar * 100
            }
        ])
        
        return comparison
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 