"""
PORTFOLIO PRICING ENGINE - FINAL PRODUCTION VERSION
The Fidelis Partnership - London Market MGU

Purpose: Assess whether each line of business is ACCRETIVE (returns exceed cost of capital)
         on a NET OF REINSURANCE basis

Author: Lead Actuary (consolidated from team deliverables)
Date: 2024
Status: Production-ready

USAGE:
------
Command line (from team_workspace directory):
    python outputs/pricing_engine_final.py

From Jupyter:
    import sys
    sys.path.insert(0, 'team_workspace/outputs')
    from pricing_engine_final import PortfolioPricingEngine
    engine = PortfolioPricingEngine()
    results = engine.run_full_analysis()

OUTPUT:
-------
- accretion_analysis.csv: Line-by-line ROAC and accretion status
- capital_allocations.csv: Gross and net capital by line
- portfolio_summary.json: Aggregate portfolio metrics
- Console: Executive summary with recommendations
"""

import pandas as pd
import numpy as np
import json
from typing import Dict, Optional, Tuple
from scipy.stats import norm
import warnings
from pathlib import Path
import time


# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # Capital measurement
    'confidence_level': 0.995,  # Lloyd's SCR = 99.5% TVaR
    
    # Hurdle rate
    'hurdle_roac': 0.12,  # 12% ROAC (London Market MGU standard)
    'cost_of_capital_rate': 0.12,  # Same as hurdle for simplicity
    
    # Data paths - relative to script location
    'use_synthetic_data': True,  # Set False to use real data
    'data_dir': 'data',
    'output_dir': 'outputs',
    
    # Risk measurement
    'risk_measure': 'tvar',  # 'tvar' (recommended) or 'var'
    
    # Expense assumptions
    'default_expense_ratio': 0.40,  # 40% expense ratio if not specified
}


# ============================================================================
# RISK ENGINE
# ============================================================================

class RiskMeasurementEngine:
    """
    Core risk measurement and capital allocation engine
    
    Implements TVaR (Tail Value at Risk) at 99.5% for Lloyd's alignment
    Uses Euler gradient allocation for capital decomposition
    """
    
    def __init__(self, confidence_level: float = 0.995):
        self.alpha = confidence_level
        
    def compute_tvar(self, losses: np.ndarray) -> Tuple[float, float]:
        """
        Compute TVaR (Expected Shortfall) and VaR
        
        Returns
        -------
        tvar, var : float, float
        """
        if len(losses) == 0:
            return np.nan, np.nan
            
        var = np.quantile(losses, self.alpha)
        tail_scenarios = losses >= var
        
        if tail_scenarios.sum() == 0:
            tvar = var
        else:
            tvar = losses[tail_scenarios].mean()
            
        return tvar, var
    
    def euler_allocation(self, loss_matrix: pd.DataFrame) -> pd.DataFrame:
        """
        Euler gradient allocation for TVaR
        
        Capital_i = E[Loss_i | Portfolio Loss >= Portfolio VaR_alpha]
        
        Parameters
        ----------
        loss_matrix : pd.DataFrame
            Loss scenarios by LoB (rows=scenarios, columns=LoBs)
            
        Returns
        -------
        allocations : pd.DataFrame
            Allocated capital and diversification metrics by LoB
        """
        portfolio_loss = loss_matrix.sum(axis=1).values
        portfolio_var = np.quantile(portfolio_loss, self.alpha)
        portfolio_tvar = portfolio_loss[portfolio_loss >= portfolio_var].mean()
        
        tail_mask = portfolio_loss >= portfolio_var
        
        allocations = []
        
        for lob in loss_matrix.columns:
            lob_losses = loss_matrix[lob].values
            
            # Euler allocation
            allocated_capital = lob_losses[tail_mask].mean()
            
            # Standalone metrics
            standalone_tvar, standalone_var = self.compute_tvar(lob_losses)
            
            # Diversification benefit
            div_benefit = standalone_tvar - allocated_capital
            div_benefit_pct = (div_benefit / standalone_tvar * 100) if standalone_tvar > 0 else 0
            
            allocations.append({
                'LoB': lob,
                'Allocated_Capital': allocated_capital,
                'Standalone_TVaR': standalone_tvar,
                'Standalone_VaR': standalone_var,
                'Diversification_Benefit': div_benefit,
                'Diversification_Benefit_%': div_benefit_pct
            })
        
        return pd.DataFrame(allocations)


# ============================================================================
# REINSURANCE ENGINE
# ============================================================================

class ReinsuranceEngine:
    """
    Apply reinsurance structures to gross losses
    
    Supports: XL (Excess of Loss), QS (Quota Share), ASL (Aggregate Stop Loss)
    """
    
    @staticmethod
    def apply_xl(gross_losses: np.ndarray, attachment: float, limit: float) -> np.ndarray:
        """Apply XL reinsurance layer"""
        ceded = np.clip(gross_losses - attachment, 0, limit)
        net = gross_losses - ceded
        return net
    
    @staticmethod
    def apply_qs(gross_losses: np.ndarray, cession_pct: float) -> np.ndarray:
        """Apply Quota Share"""
        net = gross_losses * (1 - cession_pct)
        return net
    
    @staticmethod
    def apply_asl(gross_losses: np.ndarray, attachment: float, limit: float) -> np.ndarray:
        """Apply Aggregate Stop Loss (caps annual loss)"""
        ceded = np.clip(gross_losses - attachment, 0, limit)
        net = gross_losses - ceded
        return net
    
    def apply_reinsurance_program(self, 
                                  gross_losses: pd.DataFrame,
                                  ri_structures: Dict) -> pd.DataFrame:
        """
        Apply full reinsurance program to gross losses
        
        Parameters
        ----------
        gross_losses : pd.DataFrame
            Gross loss scenarios by LoB
        ri_structures : dict
            Dictionary defining RI structure per LoB
            
        Returns
        -------
        net_losses : pd.DataFrame
            Net losses after reinsurance
        """
        net_losses = gross_losses.copy()
        
        for lob, structure in ri_structures.items():
            if lob not in net_losses.columns:
                continue
                
            gross = gross_losses[lob].values
            
            if structure['type'] == 'XL':
                net = self.apply_xl(gross, structure['attachment'], structure['limit'])
            elif structure['type'] == 'QS':
                net = self.apply_qs(gross, structure['cession'])
            elif structure['type'] == 'hybrid':
                # First apply QS
                net = self.apply_qs(gross, structure['qs_cession'])
                # Then apply Cat XL to net after QS
                net = self.apply_xl(net, structure['xl_attachment'], structure['xl_limit'])
            elif structure['type'] == 'XL+ASL':
                # Apply per-occurrence XL
                net = self.apply_xl(gross, structure['xl_attachment'], structure['xl_limit'])
                # Then apply aggregate stop loss
                net = self.apply_asl(net, structure['asl_attachment'], structure['asl_limit'])
            else:
                net = gross  # No RI
                
            net_losses[lob] = net
            
        return net_losses


# ============================================================================
# ACCRETION ANALYSIS ENGINE
# ============================================================================

class AccretionEngine:
    """
    Determine which lines are accretive (returns > cost of capital)
    """
    
    def __init__(self, hurdle_roac: float = 0.12, cost_of_capital_rate: float = 0.12):
        self.hurdle_roac = hurdle_roac
        self.cost_of_capital_rate = cost_of_capital_rate
    
    def compute_accretion(self,
                          gwp: Dict[str, float],
                          net_premium: Dict[str, float],
                          net_mean_loss: Dict[str, float],
                          allocated_capital: Dict[str, float],
                          expense_ratio: Optional[Dict[str, float]] = None) -> pd.DataFrame:
        """
        Compute ROAC and accretion status by line
        
        Parameters
        ----------
        gwp : dict
            Gross written premium by LoB
        net_premium : dict
            Net premium after RI by LoB
        net_mean_loss : dict
            Net mean loss (expected loss after RI) by LoB
        allocated_capital : dict
            Allocated capital (net basis) by LoB
        expense_ratio : dict, optional
            Expense ratio by LoB (defaults to 40%)
            
        Returns
        -------
        accretion_df : pd.DataFrame
            Line-by-line accretion analysis
        """
        
        results = []
        
        for lob in gwp.keys():
            gwp_lob = gwp[lob]
            net_prem = net_premium.get(lob, gwp_lob)  # If no RI, net=gross
            mean_loss = net_mean_loss[lob]
            capital = allocated_capital[lob]
            
            # Expense ratio
            if expense_ratio and lob in expense_ratio:
                exp_ratio = expense_ratio[lob]
            else:
                exp_ratio = CONFIG['default_expense_ratio']
            
            # Loss ratio (on net premium)
            loss_ratio = mean_loss / net_prem if net_prem > 0 else 0
            
            # Expected margin = Net Premium - Mean Loss - Expenses
            expenses = net_prem * exp_ratio
            expected_margin = net_prem - mean_loss - expenses
            
            # Cost of capital
            cost_of_capital = capital * self.cost_of_capital_rate
            
            # Net profit
            net_profit = expected_margin - cost_of_capital
            
            # ROAC
            roac = net_profit / capital if capital > 0 else 0
            
            # Accretive?
            accretive = roac >= self.hurdle_roac
            
            results.append({
                'LoB': lob,
                'GWP': gwp_lob,
                'Net_Premium': net_prem,
                'Net_Mean_Loss': mean_loss,
                'Loss_Ratio': loss_ratio,
                'Expected_Margin': expected_margin,
                'Allocated_Capital': capital,
                'Profit_Before_CoC': expected_margin,
                'Cost_of_Capital': cost_of_capital,
                'Net_Profit': net_profit,
                'ROAC': roac,
                'Accretive': accretive
            })
        
        return pd.DataFrame(results)


# ============================================================================
# SYNTHETIC DATA GENERATOR
# ============================================================================

def generate_synthetic_data(n_scenarios: int = 100000, seed: int = 42) -> Tuple[pd.DataFrame, Dict]:
    """
    Generate synthetic London Market portfolio data
    
    Parameters
    ----------
    n_scenarios : int
        Number of Monte Carlo scenarios
    seed : int
        Random seed for reproducibility
        
    Returns
    -------
    gross_losses : pd.DataFrame
        Simulated gross losses by LoB
    gwp_dict : dict
        Gross written premium by LoB
    """
    np.random.seed(seed)
    
    # Portfolio definition
    gwp_dict = {
        'PropCat_XL': 25000,
        'Specialty_Casualty': 20000,
        'Marine_Hull_Cargo': 15000,
        'Political_Violence': 12000,
        'Energy': 18000,
        'Cyber': 8000
    }
    
    # Generate correlated uniform random variables (Gaussian copula)
    correlation_matrix = np.array([
        [1.00, 0.10, 0.25, 0.15, 0.30, 0.20],  # PropCat
        [0.10, 1.00, 0.15, 0.10, 0.10, 0.25],  # Casualty
        [0.25, 0.15, 1.00, 0.20, 0.35, 0.15],  # Marine
        [0.15, 0.10, 0.20, 1.00, 0.20, 0.10],  # PolVio
        [0.30, 0.10, 0.35, 0.20, 1.00, 0.15],  # Energy
        [0.20, 0.25, 0.15, 0.10, 0.15, 1.00],  # Cyber
    ])
    
    # Generate correlated standard normals
    L = np.linalg.cholesky(correlation_matrix)
    z = np.random.standard_normal((n_scenarios, 6))
    correlated_z = z @ L.T
    
    # Transform to uniform via normal CDF
    uniform = norm.cdf(correlated_z)
    
    losses = {}
    
    # PropCat XL - GPD with zero-inflation
    freq = 0.80  # 80% chance of loss
    shape, scale = 0.7, 15000
    u = uniform[:, 0]
    has_loss = u < freq
    propcat = np.zeros(n_scenarios)
    u_loss = (u[has_loss] / freq)  # Rescale to [0,1] for GPD
    propcat[has_loss] = scale / shape * ((1 - u_loss) ** (-shape) - 1)
    losses['PropCat_XL'] = propcat
    
    # Specialty Casualty - Lognormal (attritional)
    mean_loss, cv = 12000, 0.8
    sigma = np.sqrt(np.log(1 + cv**2))
    mu = np.log(mean_loss) - sigma**2 / 2
    losses['Specialty_Casualty'] = np.exp(norm.ppf(uniform[:, 1]) * sigma + mu)
    
    # Marine Hull & Cargo - Lognormal (moderate volatility)
    mean_loss, cv = 8000, 1.2
    sigma = np.sqrt(np.log(1 + cv**2))
    mu = np.log(mean_loss) - sigma**2 / 2
    losses['Marine_Hull_Cargo'] = np.exp(norm.ppf(uniform[:, 2]) * sigma + mu)
    
    # Political Violence - GPD with high zero-inflation
    freq = 0.30  # Only 30% chance of loss
    shape, scale = 0.9, 10000
    u = uniform[:, 3]
    has_loss = u < freq
    polvio = np.zeros(n_scenarios)
    u_loss = (u[has_loss] / freq)
    polvio[has_loss] = scale / shape * ((1 - u_loss) ** (-shape) - 1)
    losses['Political_Violence'] = polvio
    
    # Energy - Lognormal (high volatility)
    mean_loss, cv = 10000, 1.5
    sigma = np.sqrt(np.log(1 + cv**2))
    mu = np.log(mean_loss) - sigma**2 / 2
    losses['Energy'] = np.exp(norm.ppf(uniform[:, 4]) * sigma + mu)
    
    # Cyber - Compound (NegBin frequency x Pareto severity)
    n_claims = np.random.negative_binomial(2, 0.4, n_scenarios)  # E[N] = 3
    pareto_alpha, pareto_scale = 2.5, 800
    cyber = np.zeros(n_scenarios)
    for i in range(n_scenarios):
        if n_claims[i] > 0:
            claims = pareto_scale * (np.random.pareto(pareto_alpha, n_claims[i]) + 1)
            cyber[i] = claims.sum()
    losses['Cyber'] = cyber
    
    gross_losses = pd.DataFrame(losses)
    
    return gross_losses, gwp_dict


# ============================================================================
# MAIN PORTFOLIO PRICING ENGINE
# ============================================================================

class PortfolioPricingEngine:
    """
    Main engine coordinating all components
    """
    
    def __init__(self, config: Optional[Dict] = None):
        if config is None:
            config = CONFIG
        self.config = config
        
        self.risk_engine = RiskMeasurementEngine(config['confidence_level'])
        self.ri_engine = ReinsuranceEngine()
        self.accretion_engine = AccretionEngine(
            config['hurdle_roac'],
            config['cost_of_capital_rate']
        )
        
    def load_data(self) -> Tuple[pd.DataFrame, Dict, Dict]:
        """
        Load gross losses and configuration
        
        Returns
        -------
        gross_losses : pd.DataFrame
        gwp_dict : dict
        ri_structures : dict
        """
        
        if self.config['use_synthetic_data']:
            # Generate synthetic data
            gross_losses, gwp_dict = generate_synthetic_data()
        else:
            # For real data, implement custom loader
            data_dir = Path(self.config['data_dir'])
            gross_losses = pd.read_csv(data_dir / 'gross_losses.csv', index_col=0)
            
            with open(data_dir / 'portfolio_config.json', 'r') as f:
                portfolio_config = json.load(f)
            
            gwp_dict = {lob: data['gwp'] 
                       for lob, data in portfolio_config['lines_of_business'].items()}
        
        # Reinsurance structures from analysis
        ri_structures = {
            'PropCat_XL': {
                'type': 'XL',
                'attachment': 10000,
                'limit': 60000
            },
            'Specialty_Casualty': {
                'type': 'QS',
                'cession': 0.25
            },
            'Marine_Hull_Cargo': {
                'type': 'XL',
                'attachment': 5000,
                'limit': 5000
            },
            'Political_Violence': {
                'type': 'hybrid',
                'qs_cession': 0.40,
                'xl_attachment': 8000,
                'xl_limit': 8000
            },
            'Energy': {
                'type': 'XL+ASL',
                'xl_attachment': 7000,
                'xl_limit': 7000,
                'asl_attachment': 15000,
                'asl_limit': 15000
            },
            'Cyber': {
                'type': 'QS',
                'cession': 0.30
            }
        }
        
        return gross_losses, gwp_dict, ri_structures
    
    def run_full_analysis(self, save_outputs: bool = True, output_dir: Optional[str] = None) -> Dict:
        """
        Execute complete portfolio pricing analysis
        
        Returns
        -------
        results : dict
            Complete analysis results
        """
        
        print("=" * 80)
        print("PORTFOLIO PRICING ENGINE - FINAL ANALYSIS")
        print("The Fidelis Partnership - London Market MGU")
        print("=" * 80)
        print()
        
        start_time = time.time()
        
        # ====================================================================
        # 1. LOAD DATA
        # ====================================================================
        
        print("[1/6] Loading data...")
        gross_losses, gwp_dict, ri_structures = self.load_data()
        print(f"      Loaded {len(gross_losses):,} scenarios for {len(gross_losses.columns)} lines")
        print(f"      Data source: {'Synthetic' if self.config['use_synthetic_data'] else 'Real'}")
        print()
        
        # ====================================================================
        # 2. GROSS CAPITAL ALLOCATION
        # ====================================================================
        
        print("[2/6] Computing gross capital allocations (pre-reinsurance)...")
        gross_allocations = self.risk_engine.euler_allocation(gross_losses)
        gross_capital = gross_allocations['Allocated_Capital'].sum()
        print(f"      Gross portfolio capital: GBP {gross_capital:,.0f}k")
        print()
        
        # ====================================================================
        # 3. APPLY REINSURANCE
        # ====================================================================
        
        print("[3/6] Applying reinsurance structures...")
        net_losses = self.ri_engine.apply_reinsurance_program(gross_losses, ri_structures)
        
        gross_mean = gross_losses.sum(axis=1).mean()
        net_mean = net_losses.sum(axis=1).mean()
        ri_benefit = gross_mean - net_mean
        print(f"      Mean loss reduction: GBP {ri_benefit:,.0f}k ({ri_benefit/gross_mean*100:.1f}%)")
        print()
        
        # ====================================================================
        # 4. NET CAPITAL ALLOCATION
        # ====================================================================
        
        print("[4/6] Computing net capital allocations (post-reinsurance)...")
        net_allocations = self.risk_engine.euler_allocation(net_losses)
        net_capital = net_allocations['Allocated_Capital'].sum()
        capital_freed = gross_capital - net_capital
        print(f"      Net portfolio capital: GBP {net_capital:,.0f}k")
        print(f"      Capital freed by RI: GBP {capital_freed:,.0f}k ({capital_freed/gross_capital*100:.1f}%)")
        print()
        
        # ====================================================================
        # 5. ACCRETION ANALYSIS
        # ====================================================================
        
        print("[5/6] Computing accretion analysis...")
        
        # Net mean losses by LoB
        net_mean_loss = {lob: net_losses[lob].mean() for lob in net_losses.columns}
        
        # Net premium (gross for XL, reduced for QS)
        net_premium = {}
        for lob in gwp_dict.keys():
            structure = ri_structures[lob]
            if structure['type'] == 'QS':
                net_premium[lob] = gwp_dict[lob] * (1 - structure['cession'])
            elif structure['type'] == 'hybrid':
                net_premium[lob] = gwp_dict[lob] * (1 - structure['qs_cession'])
            else:
                net_premium[lob] = gwp_dict[lob]
        
        # Allocated capital (net)
        allocated_capital = {row['LoB']: row['Allocated_Capital'] 
                           for _, row in net_allocations.iterrows()}
        
        accretion_df = self.accretion_engine.compute_accretion(
            gwp_dict,
            net_premium,
            net_mean_loss,
            allocated_capital
        )
        
        n_accretive = accretion_df['Accretive'].sum()
        print(f"      {n_accretive} of {len(accretion_df)} lines are accretive (ROAC >= {self.config['hurdle_roac']:.0%})")
        print()
        
        # ====================================================================
        # 6. COMPILE RESULTS
        # ====================================================================
        
        print("[6/6] Compiling results...")
        
        portfolio_summary = {
            'total_gwp': sum(gwp_dict.values()),
            'gross_capital': float(gross_capital),
            'net_capital': float(net_capital),
            'capital_freed': float(capital_freed),
            'n_lines_total': len(gwp_dict),
            'n_lines_accretive': int(n_accretive),
            'portfolio_roac': float(accretion_df['Net_Profit'].sum() / accretion_df['Allocated_Capital'].sum()),
            'hurdle_roac': self.config['hurdle_roac'],
            'confidence_level': self.config['confidence_level']
        }
        
        compute_time = time.time() - start_time
        
        results = {
            'gross_allocations': gross_allocations,
            'net_allocations': net_allocations,
            'accretion': accretion_df,
            'summary': portfolio_summary,
            'ri_structures': ri_structures,
            'gwp': gwp_dict,
            'compute_time': compute_time
        }
        
        print(f"      Analysis complete in {compute_time:.2f} seconds")
        print()
        
        # ====================================================================
        # 7. SAVE OUTPUTS
        # ====================================================================
        
        if save_outputs:
            if output_dir is None:
                output_dir = Path(self.config['output_dir'])
            else:
                output_dir = Path(output_dir)
            output_dir.mkdir(exist_ok=True, parents=True)
            
            print("Saving outputs...")
            
            accretion_df.to_csv(output_dir / 'accretion_analysis_engine.csv', index=False)
            print(f"      Saved: {output_dir / 'accretion_analysis_engine.csv'}")
            
            # Combined capital allocations
            capital_combined = gross_allocations.merge(
                net_allocations,
                on='LoB',
                suffixes=('_Gross', '_Net')
            )
            capital_combined.to_csv(output_dir / 'capital_allocations_engine.csv', index=False)
            print(f"      Saved: {output_dir / 'capital_allocations_engine.csv'}")
            
            with open(output_dir / 'portfolio_summary_engine.json', 'w') as f:
                json.dump(portfolio_summary, f, indent=2)
            print(f"      Saved: {output_dir / 'portfolio_summary_engine.json'}")
            print()
        
        # ====================================================================
        # 8. DISPLAY SUMMARY
        # ====================================================================
        
        self._display_summary(accretion_df, portfolio_summary)
        
        return results
    
    def _display_summary(self, accretion_df: pd.DataFrame, summary: Dict):
        """Display executive summary to console"""
        
        print("=" * 80)
        print("EXECUTIVE SUMMARY")
        print("=" * 80)
        print()
        
        print("Portfolio Metrics:")
        print(f"  Total GWP:               GBP {summary['total_gwp']:>12,}k")
        print(f"  Net Capital Required:    GBP {summary['net_capital']:>12,.0f}k")
        print(f"  Portfolio ROAC:          {summary['portfolio_roac']:>12.1%}")
        print(f"  Hurdle Rate:             {summary['hurdle_roac']:>12.1%}")
        print(f"  Lines Accretive:         {summary['n_lines_accretive']:>12} of {summary['n_lines_total']}")
        print()
        
        print("Accretion by Line of Business:")
        print("-" * 80)
        print(f"  {'Line':<25} {'GWP':>10} {'Capital':>12} {'ROAC':>8} {'Status':>12}")
        print("  " + "-" * 75)
        
        # Sort by ROAC descending
        for _, row in accretion_df.sort_values('ROAC', ascending=False).iterrows():
            status = "ACCRETIVE" if row['Accretive'] else "DESTROYS VALUE"
            print(f"  {row['LoB']:<25} {row['GWP']:>9,.0f}k {row['Allocated_Capital']:>11,.0f}k "
                  f"{row['ROAC']:>7.1%} {status:>12}")
        
        print("  " + "-" * 75)
        print(f"  {'PORTFOLIO TOTAL':<25} {accretion_df['GWP'].sum():>9,.0f}k "
              f"{accretion_df['Allocated_Capital'].sum():>11,.0f}k "
              f"{summary['portfolio_roac']:>7.1%}")
        print()
        
        # Strategic recommendations
        print("Strategic Recommendations:")
        print("-" * 80)
        
        non_accretive = accretion_df[~accretion_df['Accretive']]
        accretive = accretion_df[accretion_df['Accretive']]
        
        if len(non_accretive) > 0:
            print("  EXIT / REDUCE (ROAC below hurdle):")
            for _, row in non_accretive.iterrows():
                capital_intensity = row['Allocated_Capital'] / row['GWP']
                print(f"     - {row['LoB']}: {row['ROAC']:.1%} ROAC, "
                      f"{capital_intensity:.1f}x capital intensity")
            print()
        
        if len(accretive) > 0:
            print("  MAINTAIN / GROW (ROAC above hurdle):")
            for _, row in accretive.sort_values('ROAC', ascending=False).iterrows():
                print(f"     - {row['LoB']}: {row['ROAC']:.1%} ROAC")
            print()
        
        print("=" * 80)
        print()


# ============================================================================
# COMMAND LINE EXECUTION
# ============================================================================

if __name__ == "__main__":
    """
    Execute full analysis when run as script
    """
    
    print()
    print("Initializing Portfolio Pricing Engine...")
    print()
    
    # Initialize engine with default config
    engine = PortfolioPricingEngine()
    
    # Run analysis
    try:
        results = engine.run_full_analysis(save_outputs=True, output_dir='.')
        
        print("Analysis complete!")
        print()
        print("Files created:")
        print("  - accretion_analysis_engine.csv")
        print("  - capital_allocations_engine.csv")  
        print("  - portfolio_summary_engine.json")
        print()
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        raise
