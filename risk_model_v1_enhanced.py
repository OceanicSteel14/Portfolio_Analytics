
"""
Spectral Risk Engine v1.0 - Enhanced Framework
The Fidelis Partnership - London Market MGU
Portfolio Pricing Engine - Dual Risk Measure Framework with Reserve Risk

Author: Quantitative Risk Modeller (Round 1)
Date: 2024

DUAL RISK MEASURE FRAMEWORK with Reserve Risk Loading and Investment Income
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import brentq
import json
import time
from typing import Dict, Tuple, Optional, List

# Reserve risk loading factors (multiplicative on TVaR premium risk)
RESERVE_RISK_LOADINGS = {
    'PropCat_XL': 1.05,          # Short-tail, minimal reserves
    'Specialty_Casualty': 1.45,  # Long-tail, large reserves  
    'Marine_Hull_Cargo': 1.25,   # Medium-tail
    'Political_Violence': 1.10,  # Event-driven, short settlement
    'Energy': 1.30,              # Medium-long tail
    'Cyber': 1.15                # Emerging, short-medium tail
}

# Mean term of claims (years) for investment income
MEAN_TERM_CLAIMS = {
    'PropCat_XL': 0.75,          # Fast-settling catastrophe claims
    'Specialty_Casualty': 3.50,  # Long-tail casualty reserves
    'Marine_Hull_Cargo': 2.00,   # Medium settlement
    'Political_Violence': 1.00,  # Event-driven, quick settlement
    'Energy': 2.50,              # Medium-long settlement
    'Cyber': 1.50                # Short-medium, evolving class
}


class SpectralRiskEngine:
    """
    Enhanced Dual Risk Measure Framework for London Market Portfolio Pricing
    
    Key Enhancements:
    1. Reserve risk loading on TVaR capital (per-LoB factors)
    2. Investment income calculation using mean term of claims
    3. Dual processing of GROSS and NET loss distributions
    4. Lambda calibrated on NET aggregate with reserve-adjusted capital
    5. Same lambda applied to both gross and net for consistency
    """
    
    def __init__(self, confidence_level=0.995, target_roac=0.09, investment_yield=0.025):
        """
        Initialize Spectral Risk Engine
        
        Parameters
        ----------
        confidence_level : float
            Confidence level for TVaR (0.995 = 99.5% for Lloyd's SCR)
        target_roac : float
            Target ROAC for Wang lambda calibration (0.09 = 9%)
        investment_yield : float
            Annual investment yield for reserves (0.025 = 2.5%)
        """
        if not 0 < confidence_level < 1:
            raise ValueError("confidence_level must be between 0 and 1")
        if not 0 < target_roac < 1:
            raise ValueError("target_roac must be between 0 and 1")
        
        self.confidence_level = confidence_level
        self.alpha = confidence_level
        self.target_roac = target_roac
        self.investment_yield = investment_yield
        self.lambda_calibrated = None
        self.calibration_info = None
    
    # =========================================================================
    # CAPITAL MEASURE: TVaR with Reserve Risk Adjustment
    # =========================================================================
    
    def compute_tvar(self, losses, alpha=None):
        """Compute Tail Value at Risk (Expected Shortfall)"""
        if alpha is None:
            alpha = self.alpha
        
        losses = np.asarray(losses)
        if len(losses) == 0:
            return np.nan, np.nan
        
        var = np.percentile(losses, alpha * 100)
        tail_losses = losses[losses >= var]
        tvar = tail_losses.mean() if len(tail_losses) > 0 else var
        
        return float(tvar), float(var)
    
    def apply_reserve_risk_loading(self, tvar_premium_dict):
        """
        Apply reserve risk loading to premium risk TVaR
        
        TVaR_adjusted(i) = TVaR_premium(i) x reserve_loading(i)
        
        Parameters
        ----------
        tvar_premium_dict : dict
            Dictionary of {lob: tvar_premium_risk}
        
        Returns
        -------
        tvar_adjusted_dict : dict
            Dictionary of {lob: tvar_adjusted}
        portfolio_tvar_adjusted : float
            Sum of adjusted TVaRs (conservative, ignores reserve diversification)
        """
        tvar_adjusted = {}
        for lob, tvar_prem in tvar_premium_dict.items():
            loading = RESERVE_RISK_LOADINGS.get(lob, 1.0)
            tvar_adjusted[lob] = tvar_prem * loading
        
        portfolio_tvar_adjusted = sum(tvar_adjusted.values())
        
        return tvar_adjusted, portfolio_tvar_adjusted
    
    # =========================================================================
    # PRICING MEASURE: Wang Transform Distortion
    # =========================================================================
    
    def compute_wang_transform(self, losses, lambda_param):
        """
        Wang Transform distortion risk measure
        
        g(s) = Phi(Phi^-1(s) + lambda)
        """
        n = len(losses)
        sorted_losses = np.sort(losses)
        ranks = np.arange(1, n + 1)
        
        # Survival probabilities
        survival_i = (n - ranks + 1) / n
        survival_i_prev = (n - ranks + 2) / n
        
        survival_i = np.clip(survival_i, 1e-10, 1 - 1e-10)
        survival_i_prev = np.clip(survival_i_prev, 1e-10, 1 - 1e-10)
        
        # Wang distortion
        g_i = norm.cdf(norm.ppf(survival_i) + lambda_param)
        g_i_prev = norm.cdf(norm.ppf(survival_i_prev) + lambda_param)
        
        weights = g_i_prev - g_i
        
        return float(np.sum(sorted_losses * weights))
    
    def compute_power_distortion(self, losses, theta):
        """Power Distortion: g(s) = s^(1/(1+theta))"""
        n = len(losses)
        sorted_losses = np.sort(losses)
        ranks = np.arange(1, n + 1)
        
        survival_i = (n - ranks + 1) / n
        survival_i_prev = (n - ranks + 2) / n
        
        survival_i = np.clip(survival_i, 1e-10, 1)
        survival_i_prev = np.clip(survival_i_prev, 1e-10, 1)
        
        exponent = 1 / (1 + theta)
        g_i = np.power(survival_i, exponent)
        g_i_prev = np.power(survival_i_prev, exponent)
        
        weights = g_i_prev - g_i
        return float(np.sum(sorted_losses * weights))
    
    def compute_dual_power(self, losses, gamma):
        """Dual Power: g(s) = 1 - (1-s)^(1+gamma)"""
        n = len(losses)
        sorted_losses = np.sort(losses)
        ranks = np.arange(1, n + 1)
        
        survival_i = (n - ranks + 1) / n
        survival_i_prev = (n - ranks + 2) / n
        
        survival_i = np.clip(survival_i, 0, 1 - 1e-10)
        survival_i_prev = np.clip(survival_i_prev, 0, 1 - 1e-10)
        
        exponent = 1 + gamma
        g_i = 1 - np.power(1 - survival_i, exponent)
        g_i_prev = 1 - np.power(1 - survival_i_prev, exponent)
        
        weights = g_i_prev - g_i
        return float(np.sum(sorted_losses * weights))
    
    # =========================================================================
    # LAMBDA CALIBRATION ON NET AGGREGATE WITH RESERVE RISK
    # =========================================================================
    
    def calibrate_lambda(self, net_losses_matrix):
        """
        Calibrate Wang Transform lambda on NET aggregate losses
        
        Calibration target:
        (Wang E[L_net_portfolio] - E[L_net_portfolio]) = target_roac x TVaR_adjusted_portfolio
        
        where TVaR_adjusted_portfolio = sum of (TVaR_premium(i) x reserve_loading(i))
        
        Parameters
        ----------
        net_losses_matrix : pd.DataFrame
            NET loss scenarios by LoB (rows=scenarios, columns=LoBs)
        
        Returns
        -------
        lambda_calibrated : float
        calibration_info : dict
        """
        # Compute portfolio aggregate net losses
        portfolio_net = net_losses_matrix.sum(axis=1).values
        mean_net = portfolio_net.mean()
        
        # Compute per-LoB net TVaR (premium risk only)
        tvar_premium_net = {}
        for lob in net_losses_matrix.columns:
            tvar, var = self.compute_tvar(net_losses_matrix[lob].values)
            tvar_premium_net[lob] = tvar
        
        # Apply reserve risk loading
        tvar_adjusted_dict, tvar_adjusted_portfolio = self.apply_reserve_risk_loading(tvar_premium_net)
        
        # Portfolio-level net TVaR (premium risk only, for comparison)
        tvar_portfolio_premium, var_portfolio = self.compute_tvar(portfolio_net)
        
        # Calibration target: risk loading = target_roac x adjusted capital
        target_loading = self.target_roac * tvar_adjusted_portfolio
        target_wang_el = mean_net + target_loading
        
        def objective(lam):
            return self.compute_wang_transform(portfolio_net, lam) - target_wang_el
        
        try:
            self.lambda_calibrated = brentq(objective, 0.001, 5.0, xtol=1e-12)
        except ValueError as e:
            raise ValueError(f"Could not calibrate lambda: {e}. "
                           f"Target Wang E[L] = {target_wang_el:.0f} may be outside feasible range.")
        
        # Verify calibration
        wang_el = self.compute_wang_transform(portfolio_net, self.lambda_calibrated)
        actual_loading = wang_el - mean_net
        achieved_roac = actual_loading / tvar_adjusted_portfolio if tvar_adjusted_portfolio > 0 else np.nan
        
        self.calibration_info = {
            'target_roac': self.target_roac,
            'achieved_roac': achieved_roac,
            'tvar_premium_portfolio': tvar_portfolio_premium,
            'tvar_adjusted_portfolio': tvar_adjusted_portfolio,
            'reserve_adjustment_gbpk': tvar_adjusted_portfolio - tvar_portfolio_premium,
            'var_portfolio': var_portfolio,
            'mean_net_loss': mean_net,
            'target_loading': target_loading,
            'actual_loading': actual_loading,
            'wang_el': wang_el,
            'lambda': self.lambda_calibrated,
            'error_bps': abs(achieved_roac - self.target_roac) * 10000,
            'n_scenarios': len(portfolio_net),
            'calibration_basis': 'NET aggregate with reserve risk adjustment'
        }
        
        return self.lambda_calibrated, self.calibration_info
    
    # =========================================================================
    # EULER ALLOCATION FOR TVaR
    # =========================================================================
    
    def euler_allocation_tvar(self, loss_matrix):
        """
        Euler gradient allocation for TVaR
        
        Capital_i = E[L_i | L_portfolio >= VaR_alpha(L_portfolio)]
        """
        portfolio_loss = loss_matrix.sum(axis=1).values
        var = np.percentile(portfolio_loss, self.alpha * 100)
        tvar = portfolio_loss[portfolio_loss >= var].mean()
        
        tail_mask = portfolio_loss >= var
        n_tail = tail_mask.sum()
        
        allocations = []
        for lob in loss_matrix.columns:
            lob_losses = loss_matrix[lob].values
            
            # Euler allocation = conditional expectation in tail
            allocated_premium = lob_losses[tail_mask].mean()
            
            # Apply reserve risk loading
            reserve_loading = RESERVE_RISK_LOADINGS.get(lob, 1.0)
            allocated_adjusted = allocated_premium * reserve_loading
            
            # Standalone metrics
            standalone_tvar, standalone_var = self.compute_tvar(lob_losses, self.alpha)
            standalone_adjusted = standalone_tvar * reserve_loading
            
            # Diversification benefit (on adjusted basis)
            div_benefit = standalone_adjusted - allocated_adjusted
            div_benefit_pct = (div_benefit / standalone_adjusted * 100) if standalone_adjusted > 0 else 0
            
            allocations.append({
                'LoB': lob,
                'Allocated_Capital_Premium': allocated_premium,
                'Reserve_Loading_Factor': reserve_loading,
                'Allocated_Capital_Adjusted': allocated_adjusted,
                'Standalone_TVaR_Premium': standalone_tvar,
                'Standalone_TVaR_Adjusted': standalone_adjusted,
                'Standalone_VaR': standalone_var,
                'Div_Benefit_GBPk': div_benefit,
                'Div_Benefit_Pct': div_benefit_pct
            })
        
        allocations_df = pd.DataFrame(allocations)
        
        # Validate: sum of premium allocations = portfolio TVaR
        total_allocated_premium = allocations_df['Allocated_Capital_Premium'].sum()
        total_allocated_adjusted = allocations_df['Allocated_Capital_Adjusted'].sum()
        allocation_error = abs(total_allocated_premium - tvar)
        
        meta = {
            'portfolio_tvar_premium': tvar,
            'portfolio_tvar_adjusted': total_allocated_adjusted,
            'portfolio_var': var,
            'n_tail_scenarios': n_tail,
            'allocation_error_premium': allocation_error
        }
        
        return allocations_df, meta
    
    # =========================================================================
    # INVESTMENT INCOME
    # =========================================================================
    
    def compute_investment_income(self, loss_matrix):
        """
        Compute investment income per LoB
        
        Investment Income = yield x mean_term x E[loss]
        """
        investment_income = {}
        for lob in loss_matrix.columns:
            mean_loss = loss_matrix[lob].mean()
            mean_term = MEAN_TERM_CLAIMS.get(lob, 1.0)
            inv_income = self.investment_yield * mean_term * mean_loss
            investment_income[lob] = {
                'Mean_Loss': mean_loss,
                'Mean_Term_Years': mean_term,
                'Investment_Yield': self.investment_yield,
                'Investment_Income': inv_income
            }
        return investment_income
    
    # =========================================================================
    # MAIN COMPUTATION
    # =========================================================================
    
    def compute_portfolio_risk(self, gross_losses, net_losses, gwp=None):
        """
        Main method: compute comprehensive dual-framework risk metrics
        
        Process:
        1. Calibrate lambda on NET aggregate with reserve-adjusted TVaR
        2. Apply same lambda to BOTH gross and net losses
        3. Compute TVaR Euler allocations (with reserve adjustment)
        4. Compute Wang pricing metrics for each LoB
        5. Compute investment income
        
        Parameters
        ----------
        gross_losses : pd.DataFrame
            GROSS loss scenarios by LoB
        net_losses : pd.DataFrame
            NET loss scenarios by LoB
        gwp : dict, optional
            Gross Written Premium by LoB
        
        Returns
        -------
        results : dict
            Comprehensive results dictionary
        """
        start_time = time.time()
        
        # Validate inputs
        if not isinstance(gross_losses, pd.DataFrame):
            raise TypeError("gross_losses must be a pandas DataFrame")
        if not isinstance(net_losses, pd.DataFrame):
            raise TypeError("net_losses must be a pandas DataFrame")
        if list(gross_losses.columns) != list(net_losses.columns):
            raise ValueError("gross_losses and net_losses must have same LoBs")
        
        # 1. Calibrate lambda on NET aggregate
        print("Calibrating lambda on NET aggregate with reserve risk adjustment...")
        self.calibrate_lambda(net_losses)
        
        # 2. Portfolio-level metrics (NET)
        portfolio_net = net_losses.sum(axis=1).values
        portfolio_net_mean = portfolio_net.mean()
        portfolio_net_tvar, portfolio_net_var = self.compute_tvar(portfolio_net)
        portfolio_net_wang = self.compute_wang_transform(portfolio_net, self.lambda_calibrated)
        
        # Portfolio-level metrics (GROSS)
        portfolio_gross = gross_losses.sum(axis=1).values
        portfolio_gross_mean = portfolio_gross.mean()
        portfolio_gross_tvar, portfolio_gross_var = self.compute_tvar(portfolio_gross)
        portfolio_gross_wang = self.compute_wang_transform(portfolio_gross, self.lambda_calibrated)
        
        portfolio_metrics = {
            'Net': {
                'Mean_Loss': portfolio_net_mean,
                'VaR_99.5': portfolio_net_var,
                'TVaR_99.5_Premium': portfolio_net_tvar,
                'TVaR_99.5_Adjusted': self.calibration_info['tvar_adjusted_portfolio'],
                'Wang_EL': portfolio_net_wang,
                'Risk_Loading': portfolio_net_wang - portfolio_net_mean,
                'Implied_ROAC_Pct': (portfolio_net_wang - portfolio_net_mean) / self.calibration_info['tvar_adjusted_portfolio'] * 100
            },
            'Gross': {
                'Mean_Loss': portfolio_gross_mean,
                'VaR_99.5': portfolio_gross_var,
                'TVaR_99.5': portfolio_gross_tvar,
                'Wang_EL': portfolio_gross_wang,
                'Risk_Loading': portfolio_gross_wang - portfolio_gross_mean
            },
            'N_Scenarios': len(portfolio_net),
            'Lambda': self.lambda_calibrated
        }
        
        # 3. Euler allocation on NET (for capital)
        print("Computing Euler capital allocations on NET losses...")
        capital_allocations_net, alloc_meta_net = self.euler_allocation_tvar(net_losses)
        
        # 4. Euler allocation on GROSS (for comparison)
        capital_allocations_gross, alloc_meta_gross = self.euler_allocation_tvar(gross_losses)
        
        # 5. Wang pricing metrics per LoB (NET and GROSS)
        print("Computing Wang pricing metrics...")
        pricing_metrics_net = self.compute_lob_pricing_metrics(net_losses, capital_allocations_net, 'Net')
        pricing_metrics_gross = self.compute_lob_pricing_metrics(gross_losses, capital_allocations_gross, 'Gross')
        
        # 6. Investment income
        print("Computing investment income...")
        inv_income_net = self.compute_investment_income(net_losses)
        inv_income_gross = self.compute_investment_income(gross_losses)
        
        # 7. Add GWP-based metrics if provided
        if gwp:
            capital_allocations_net['GWP'] = capital_allocations_net['LoB'].map(gwp)
            capital_allocations_net['Capital_Intensity'] = capital_allocations_net['Allocated_Capital_Adjusted'] / capital_allocations_net['GWP']
            capital_allocations_gross['GWP'] = capital_allocations_gross['LoB'].map(gwp)
            pricing_metrics_net['GWP'] = pricing_metrics_net['LoB'].map(gwp)
            pricing_metrics_gross['GWP'] = pricing_metrics_gross['LoB'].map(gwp)
        
        runtime = time.time() - start_time
        
        results = {
            'calibration': self.calibration_info,
            'portfolio_metrics': portfolio_metrics,
            'capital_allocations_net': capital_allocations_net,
            'capital_allocations_gross': capital_allocations_gross,
            'pricing_metrics_net': pricing_metrics_net,
            'pricing_metrics_gross': pricing_metrics_gross,
            'investment_income_net': inv_income_net,
            'investment_income_gross': inv_income_gross,
            'allocation_meta_net': alloc_meta_net,
            'allocation_meta_gross': alloc_meta_gross,
            'runtime_seconds': runtime
        }
        
        return results
    
    def compute_lob_pricing_metrics(self, loss_matrix, capital_allocations, basis):
        """Compute Wang-based pricing metrics per LoB"""
        if self.lambda_calibrated is None:
            raise ValueError("Must calibrate lambda first")
        
        pricing = []
        for lob in loss_matrix.columns:
            lob_losses = loss_matrix[lob].values
            
            mean_loss = lob_losses.mean()
            tvar, var = self.compute_tvar(lob_losses)
            
            # Wang-based pricing
            wang_el = self.compute_wang_transform(lob_losses, self.lambda_calibrated)
            risk_loading = wang_el - mean_loss
            
            # Get allocated capital
            alloc_row = capital_allocations[capital_allocations['LoB'] == lob].iloc[0]
            allocated_capital_adjusted = alloc_row['Allocated_Capital_Adjusted']
            
            # Implied ROAC using adjusted capital
            implied_roac = (risk_loading / allocated_capital_adjusted * 100) if allocated_capital_adjusted > 0 else np.nan
            
            pricing.append({
                'LoB': lob,
                'Basis': basis,
                'Mean_Loss': mean_loss,
                'TVaR_Premium': tvar,
                'Allocated_Capital_Adjusted': allocated_capital_adjusted,
                'Wang_EL': wang_el,
                'Risk_Loading': risk_loading,
                'Implied_ROAC_Pct': implied_roac
            })
        
        return pd.DataFrame(pricing)
    
    def create_summary_report(self, results):
        """Create human-readable summary report"""
        lines = []
        lines.append("="*80)
        lines.append("SPECTRAL RISK ENGINE - DUAL FRAMEWORK WITH RESERVE RISK")
        lines.append("="*80)
        lines.append("")
        
        # Calibration
        cal = results['calibration']
        lines.append("LAMBDA CALIBRATION (on NET aggregate with reserve risk):")
        lines.append("-"*80)
        lines.append(f"  Target ROAC:                 {cal['target_roac']*100:.1f}%")
        lines.append(f"  Achieved ROAC:               {cal['achieved_roac']*100:.4f}%")
        lines.append(f"  Lambda Calibrated:           {cal['lambda']:.6f}")
        lines.append(f"  Calibration Error:           {cal['error_bps']:.4f} basis points")
        lines.append(f"  TVaR Premium (Net):          GBP {cal['tvar_premium_portfolio']:>12,.0f}k")
        lines.append(f"  TVaR Adjusted (w/ Reserve):  GBP {cal['tvar_adjusted_portfolio']:>12,.0f}k")
        lines.append(f"  Reserve Risk Adjustment:     GBP {cal['reserve_adjustment_gbpk']:>12,.0f}k")
        lines.append("")
        
        # Portfolio
        pm_net = results['portfolio_metrics']['Net']
        pm_gross = results['portfolio_metrics']['Gross']
        lines.append("PORTFOLIO METRICS:")
        lines.append("-"*80)
        lines.append(f"  NET PORTFOLIO:")
        lines.append(f"    Mean Loss:         GBP {pm_net['Mean_Loss']:>12,.0f}k")
        lines.append(f"    TVaR Premium:      GBP {pm_net['TVaR_99.5_Premium']:>12,.0f}k")
        lines.append(f"    TVaR Adjusted:     GBP {pm_net['TVaR_99.5_Adjusted']:>12,.0f}k")
        lines.append(f"    Wang E[L]:         GBP {pm_net['Wang_EL']:>12,.0f}k")
        lines.append(f"    Risk Loading:      GBP {pm_net['Risk_Loading']:>12,.0f}k")
        lines.append(f"    Implied ROAC:      {pm_net['Implied_ROAC_Pct']:.2f}%")
        lines.append("")
        lines.append(f"  GROSS PORTFOLIO:")
        lines.append(f"    Mean Loss:         GBP {pm_gross['Mean_Loss']:>12,.0f}k")
        lines.append(f"    TVaR:              GBP {pm_gross['TVaR_99.5']:>12,.0f}k")
        lines.append(f"    Wang E[L]:         GBP {pm_gross['Wang_EL']:>12,.0f}k")
        lines.append("")
        
        lines.append(f"Runtime: {results['runtime_seconds']:.3f} seconds")
        lines.append("="*80)
        
        return "\n".join(lines)


# =============================================================================
# STANDALONE CONVENIENCE FUNCTIONS
# =============================================================================

def calibrate_lambda(net_losses, target_roac, confidence_level=0.995):
    """Standalone function to calibrate Wang Transform lambda"""
    engine = SpectralRiskEngine(confidence_level=confidence_level, target_roac=target_roac)
    return engine.calibrate_lambda(net_losses)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("Spectral Risk Engine v1.0 - Enhanced Framework")
    print("="*80)
    
    try:
        # Load data
        print("Loading loss data...")
        gross = pd.read_csv('team_workspace/data/gross_losses.csv', index_col=0)
        net = pd.read_csv('team_workspace/data/net_losses.csv', index_col=0)
        
        with open('team_workspace/data/portfolio_config.json', 'r') as f:
            config = json.load(f)
        
        gwp_dict = {lob: data['gwp'] for lob, data in config['lines_of_business'].items()}
        
        print(f"Loaded: {len(gross):,} scenarios x {len(gross.columns)} LoBs")
        print(f"  Gross and Net losses aligned: {list(gross.columns) == list(net.columns)}")
        print()
        
        # Initialize and run engine
        print("Initializing engine...")
        engine = SpectralRiskEngine(
            confidence_level=0.995, 
            target_roac=0.09,
            investment_yield=0.025
        )
        
        print("Computing portfolio risk metrics...")
        results = engine.compute_portfolio_risk(gross, net, gwp=gwp_dict)
        
        # Print summary
        print()
        print(engine.create_summary_report(results))
        print()
        
        # Save results
        print("Saving results...")
        results['capital_allocations_net'].to_csv('team_workspace/capital_allocations_net.csv', index=False)
        results['capital_allocations_gross'].to_csv('team_workspace/capital_allocations_gross.csv', index=False)
        results['pricing_metrics_net'].to_csv('team_workspace/pricing_metrics_net.csv', index=False)
        results['pricing_metrics_gross'].to_csv('team_workspace/pricing_metrics_gross.csv', index=False)
        
        print("SUCCESS: All results computed and saved")
        
    except FileNotFoundError as e:
        print(f"Error: Could not find data files - {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
