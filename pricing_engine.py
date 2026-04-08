"""
Portfolio Pricing Engine — All modules in one cell for Jupyter compatibility.
"""

import numpy as np
import pandas as pd
from scipy import stats
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import json
import warnings
warnings.filterwarnings('ignore')


# ════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════════

@dataclass
class EngineConfig:
    """Global engine configuration."""
    wang_lambda: float = 1.0              # Wang Transform risk aversion parameter
    n_simulations: int = 100_000          # Monte Carlo simulation count
    confidence_level: float = 0.995       # 1-in-200 (Solvency II standard)
    cost_of_capital: float = 0.10         # 10% hurdle rate
    correlation_matrix: Optional[list] = None
    random_seed: int = 42
    use_claude_agent: bool = False
    anthropic_api_key: Optional[str] = None
    claude_model: str = "claude-sonnet-4-20250514"


@dataclass
class LineOfBusiness:
    """Defines a line of business for pricing."""
    name: str
    distribution: object
    gross_premium: float
    reinsurance_program: object = None
    expenses: float = 0.0
    metadata: dict = field(default_factory=dict)


# ════════════════════════════════════════════════════════════════════
# LOSS DISTRIBUTIONS
# ════════════════════════════════════════════════════════════════════

class LossDistribution(ABC):
    """Base class for all loss distributions."""
    @abstractmethod
    def simulate(self, n: int) -> np.ndarray:
        pass
    @abstractmethod
    def cdf(self, x: np.ndarray) -> np.ndarray:
        pass
    @abstractmethod
    def quantile(self, p: np.ndarray) -> np.ndarray:
        pass
    def mean(self) -> float:
        return np.mean(self.simulate(100_000))


class Lognormal(LossDistribution):
    """
    Lognormal loss distribution.
    Parametrise with (mu, sigma) or (mean_loss, cv).
    """
    def __init__(self, mu=None, sigma=None, mean_loss=None, cv=None):
        if mean_loss is not None and cv is not None:
            variance_loss = (cv * mean_loss) ** 2
            self.sigma = np.sqrt(np.log(1 + variance_loss / mean_loss**2))
            self.mu = np.log(mean_loss) - 0.5 * self.sigma**2
        elif mu is not None and sigma is not None:
            self.mu = mu
            self.sigma = sigma
        else:
            raise ValueError("Provide either (mu, sigma) or (mean_loss, cv)")
        self._dist = stats.lognorm(s=self.sigma, scale=np.exp(self.mu))

    def simulate(self, n):
        return self._dist.rvs(size=n)
    def cdf(self, x):
        return self._dist.cdf(x)
    def quantile(self, p):
        return self._dist.ppf(p)
    def mean(self):
        return self._dist.mean()
    def __repr__(self):
        return f"Lognormal(μ={self.mu:.4f}, σ={self.sigma:.4f}, E[L]={self.mean():,.0f})"


class ParetoGPD(LossDistribution):
    """
    Generalised Pareto Distribution for excess losses.
    Compound Poisson-GPD for annual aggregate simulation.
    """
    def __init__(self, threshold, shape, scale, frequency=1.0):
        self.threshold = threshold
        self.shape = shape
        self.scale = scale
        self.frequency = frequency
        self._gpd = stats.genpareto(c=shape, scale=scale)

    def simulate(self, n):
        annual_losses = np.zeros(n)
        event_counts = np.random.poisson(self.frequency, size=n)
        for i in range(n):
            if event_counts[i] > 0:
                severities = self.threshold + self._gpd.rvs(size=event_counts[i])
                annual_losses[i] = np.sum(severities)
        return annual_losses

    def cdf(self, x):
        return self._gpd.cdf(np.maximum(np.asarray(x) - self.threshold, 0))
    def quantile(self, p):
        return self.threshold + self._gpd.ppf(np.asarray(p))
    def mean(self):
        if self.shape < 1:
            return self.frequency * (self.threshold + self.scale / (1 - self.shape))
        return float('inf')
    def __repr__(self):
        return f"ParetoGPD(threshold={self.threshold:,.0f}, ξ={self.shape:.3f}, σ={self.scale:,.0f}, freq={self.frequency:.1f})"


class EmpiricalDistribution(LossDistribution):
    """
    Empirical distribution from historical data or model output.
    Uses bootstrap resampling.
    """
    def __init__(self, data, weights=None):
        self.data = np.asarray(data, dtype=float)
        self.weights = weights
        if weights is not None:
            self.weights = np.asarray(weights, dtype=float)
            self.weights /= self.weights.sum()
        self._sorted = np.sort(self.data)
        self._n = len(self.data)

    def simulate(self, n):
        return self.data[np.random.choice(self._n, size=n, replace=True, p=self.weights)]
    def cdf(self, x):
        return np.searchsorted(self._sorted, np.asarray(x), side='right') / self._n
    def quantile(self, p):
        p = np.asarray(p)
        indices = p * (self._n - 1)
        lower = np.clip(np.floor(indices).astype(int), 0, self._n - 1)
        upper = np.clip(np.ceil(indices).astype(int), 0, self._n - 1)
        frac = indices - lower
        return self._sorted[lower] * (1 - frac) + self._sorted[upper] * frac
    def mean(self):
        return np.average(self.data, weights=self.weights)
    @classmethod
    def from_csv(cls, filepath, column='loss', **kwargs):
        return cls(data=pd.read_csv(filepath)[column].values, **kwargs)


# ════════════════════════════════════════════════════════════════════
# SPECTRAL RISK MEASURES
# ════════════════════════════════════════════════════════════════════

class SpectralRiskMeasure(ABC):
    """Base class for spectral risk measures."""
    @abstractmethod
    def distortion(self, s):
        pass
    @abstractmethod
    def risk_spectrum(self, p):
        pass

    def compute(self, losses, confidence_level=0.995):
        """Compute SRM via numerical integration over weighted quantiles."""
        sorted_losses = np.sort(losses)
        n = len(sorted_losses)
        n_points = min(n, 10_000)
        p = np.linspace(1e-6, confidence_level, n_points)
        quantiles = np.interp(p, np.linspace(0, 1, n), sorted_losses)
        weights = self.risk_spectrum(p)
        dp = p[1] - p[0]
        total_weight = np.sum(weights) * dp
        if total_weight > 0:
            weights = weights / total_weight
        return np.sum(quantiles * weights) * dp


class WangTransform(SpectralRiskMeasure):
    """
    Wang Transform: g(s) = Φ(Φ⁻¹(s) + λ)
    
    λ = 0   → risk neutral (expected value)
    λ = 0.5 → moderate risk loading
    λ = 1.0 → standard risk loading
    λ = 2.0 → very conservative
    """
    def __init__(self, lambda_param=1.0):
        self.lambda_param = lambda_param

    def distortion(self, s):
        s = np.clip(s, 1e-10, 1 - 1e-10)
        return stats.norm.cdf(stats.norm.ppf(s) + self.lambda_param)

    def risk_spectrum(self, p):
        p = np.clip(p, 1e-10, 1 - 1e-10)
        z = stats.norm.ppf(p)
        return np.exp(self.lambda_param * z - 0.5 * self.lambda_param**2)

    def compute_lognormal_analytical(self, mu, sigma):
        """Closed-form: E[X] · exp(λσ) — useful sanity check."""
        return np.exp(mu + self.lambda_param * sigma + 0.5 * sigma**2)


# ════════════════════════════════════════════════════════════════════
# REINSURANCE STRUCTURES
# ════════════════════════════════════════════════════════════════════

class ReinsuranceTreaty(ABC):
    def __init__(self, name):
        self.name = name
    @abstractmethod
    def apply(self, gross_losses):
        pass
    @abstractmethod
    def premium(self, gross_losses):
        pass
    def recovery(self, gross_losses):
        return gross_losses - self.apply(gross_losses)


class QuotaShare(ReinsuranceTreaty):
    """Proportional cession."""
    def __init__(self, cession_rate, commission=0.0, name="Quota Share"):
        super().__init__(name)
        self.cession_rate = cession_rate
        self.commission = commission

    def apply(self, gross_losses):
        return gross_losses * (1 - self.cession_rate)

    def premium(self, gross_losses):
        expected_ceded = np.mean(gross_losses) * self.cession_rate
        return expected_ceded * 1.10 * (1 - self.commission)


class ExcessOfLoss(ReinsuranceTreaty):
    """Non-proportional: Limit XS Retention."""
    def __init__(self, retention, limit, rate_on_line=None, reinstatements=1, name="Excess of Loss"):
        super().__init__(name)
        self.retention = retention
        self.limit = limit
        self.rate_on_line = rate_on_line
        self.reinstatements = reinstatements

    def apply(self, gross_losses):
        ceded = np.minimum(np.maximum(gross_losses - self.retention, 0), self.limit)
        return gross_losses - ceded

    def premium(self, gross_losses):
        if self.rate_on_line is not None:
            return self.rate_on_line * self.limit
        ceded = np.minimum(np.maximum(gross_losses - self.retention, 0), self.limit)
        expected_ceded = np.mean(ceded)
        lol = expected_ceded / self.limit if self.limit > 0 else 0
        loading = 3.0 if lol < 0.01 else 2.0 if lol < 0.05 else 1.5 if lol < 0.15 else 1.25
        return expected_ceded * loading


class StopLoss(ReinsuranceTreaty):
    """Aggregate excess of loss."""
    def __init__(self, aggregate_retention, aggregate_limit, rate_on_line=None, name="Stop Loss"):
        super().__init__(name)
        self.aggregate_retention = aggregate_retention
        self.aggregate_limit = aggregate_limit
        self.rate_on_line = rate_on_line

    def apply(self, gross_losses):
        excess = np.maximum(gross_losses - self.aggregate_retention, 0)
        ceded = np.minimum(excess, self.aggregate_limit)
        return gross_losses - ceded

    def premium(self, gross_losses):
        if self.rate_on_line is not None:
            return self.rate_on_line * self.aggregate_limit
        excess = np.maximum(gross_losses - self.aggregate_retention, 0)
        return np.mean(np.minimum(excess, self.aggregate_limit)) * 2.0


class ReinsuranceProgram:
    """Chains multiple treaties sequentially."""
    def __init__(self, treaties, name="RI Programme"):
        self.treaties = treaties
        self.name = name

    def apply(self, gross_losses):
        net = gross_losses.copy()
        for treaty in self.treaties:
            net = treaty.apply(net)
        return net

    def total_premium(self, gross_losses):
        return sum(t.premium(gross_losses) for t in self.treaties)


# ════════════════════════════════════════════════════════════════════
# PORTFOLIO AGGREGATION (Gaussian Copula + Euler Allocation)
# ════════════════════════════════════════════════════════════════════

class PortfolioAggregator:
    def __init__(self, n_simulations=100_000, seed=42):
        self.n_simulations = n_simulations
        self.seed = seed

    def aggregate(self, lines, spectral_measure, confidence_level=0.995, correlation_matrix=None):
        n_lines = len(lines)
        np.random.seed(self.seed)

        if correlation_matrix is None:
            correlation_matrix = np.full((n_lines, n_lines), 0.20)
            np.fill_diagonal(correlation_matrix, 1.0)
        else:
            correlation_matrix = np.asarray(correlation_matrix)

        # Gaussian copula
        try:
            L = np.linalg.cholesky(correlation_matrix)
        except np.linalg.LinAlgError:
            correlation_matrix = self._nearest_pd(correlation_matrix)
            L = np.linalg.cholesky(correlation_matrix)

        Z = np.random.standard_normal((self.n_simulations, n_lines))
        correlated_uniforms = stats.norm.cdf(Z @ L.T)

        # Transform to losses
        line_losses = np.zeros((self.n_simulations, n_lines))
        for i, lob in enumerate(lines):
            marginal = np.sort(lob.distribution.simulate(self.n_simulations))
            indices = np.clip((correlated_uniforms[:, i] * self.n_simulations).astype(int), 0, self.n_simulations - 1)
            line_losses[:, i] = marginal[indices]

        # Apply RI
        net_line_losses = np.zeros_like(line_losses)
        for i, lob in enumerate(lines):
            if lob.reinsurance_program:
                net_line_losses[:, i] = lob.reinsurance_program.apply(line_losses[:, i])
            else:
                net_line_losses[:, i] = line_losses[:, i]

        portfolio_losses = np.sum(net_line_losses, axis=1)
        diversified_capital = spectral_measure.compute(portfolio_losses, confidence_level)

        # Euler allocation
        marginal_contributions = self._euler_allocation(
            net_line_losses, portfolio_losses, spectral_measure, confidence_level
        )

        standalone_capitals = np.array([
            spectral_measure.compute(net_line_losses[:, i], confidence_level)
            for i in range(n_lines)
        ])

        return {
            "diversified_capital": diversified_capital,
            "marginal_contributions": marginal_contributions,
            "standalone_capitals": standalone_capitals,
            "portfolio_losses": portfolio_losses,
        }

    def _euler_allocation(self, line_losses, portfolio_losses, spectral_measure, confidence_level):
        n_sims, n_lines = line_losses.shape
        sort_idx = np.argsort(portfolio_losses)
        sorted_lines = line_losses[sort_idx]
        p = np.linspace(1e-6, confidence_level, n_sims)
        weights = spectral_measure.risk_spectrum(p)
        dp = p[1] - p[0]
        total_weight = np.sum(weights) * dp
        if total_weight > 0:
            weights = weights / total_weight
        marginal = np.zeros(n_lines)
        quantile_grid = np.linspace(0, 1, n_sims)
        for i in range(n_lines):
            line_at_p = np.interp(p, quantile_grid, sorted_lines[:, i])
            marginal[i] = np.sum(line_at_p * weights) * dp
        diversified_total = spectral_measure.compute(portfolio_losses, confidence_level)
        marginal_sum = np.sum(marginal)
        if marginal_sum > 0:
            marginal = marginal * (diversified_total / marginal_sum)
        return marginal

    @staticmethod
    def _nearest_pd(A):
        B = (A + A.T) / 2
        _, s, V = np.linalg.svd(B)
        H = V.T @ np.diag(s) @ V
        A3 = (B + H) / 2
        A3 = (A3 + A3.T) / 2
        k = 1
        I = np.eye(A.shape[0])
        while True:
            try:
                np.linalg.cholesky(A3)
                return A3
            except np.linalg.LinAlgError:
                mineig = np.min(np.real(np.linalg.eigvals(A3)))
                A3 += I * (-mineig * k**2 + np.spacing(np.linalg.norm(A)))
                k += 1


# ════════════════════════════════════════════════════════════════════
# MAIN ENGINE
# ════════════════════════════════════════════════════════════════════

class PortfolioPricingEngine:
    def __init__(self, config):
        self.config = config
        self.spectral_measure = WangTransform(lambda_param=config.wang_lambda)
        self.aggregator = PortfolioAggregator(n_simulations=config.n_simulations, seed=config.random_seed)
        self.results = None

    def run(self, lines, verbose=True):
        if verbose:
            print("=" * 70)
            print("PORTFOLIO PRICING ENGINE — Spectral Risk Measures")
            print(f"Wang Transform λ = {self.config.wang_lambda}")
            print(f"Simulations: {self.config.n_simulations:,}")
            print(f"Cost of Capital: {self.config.cost_of_capital:.1%}")
            print(f"Confidence Level: {self.config.confidence_level:.1%}")
            print("=" * 70)

        results = []
        for lob in lines:
            if verbose:
                print(f"\n--- {lob.name} ---")
            results.append(self._price_line(lob, verbose=verbose))

        self.results = pd.DataFrame(results)
        self._compute_portfolio_metrics(lines, verbose=verbose)

        if verbose:
            print("\n" + "=" * 70)
            print("RESULTS SUMMARY")
            print("=" * 70)
        return self.results

    def _price_line(self, lob, verbose=True):
        np.random.seed(self.config.random_seed)
        gross_losses = lob.distribution.simulate(self.config.n_simulations)
        gross_srm = self.spectral_measure.compute(gross_losses, self.config.confidence_level)
        gross_var = np.percentile(gross_losses, self.config.confidence_level * 100)
        gross_tvar = np.mean(gross_losses[gross_losses >= gross_var])

        # Apply RI
        net_losses = gross_losses.copy()
        total_ri_premium = 0.0
        if lob.reinsurance_program:
            net_losses = lob.reinsurance_program.apply(gross_losses)
            total_ri_premium = lob.reinsurance_program.total_premium(gross_losses)

        net_srm = self.spectral_measure.compute(net_losses, self.config.confidence_level)
        net_var = np.percentile(net_losses, self.config.confidence_level * 100)
        net_tvar = np.mean(net_losses[net_losses >= net_var]) if np.any(net_losses >= net_var) else net_var

        # Accretiveness
        net_expected_loss = np.mean(net_losses)
        capital_required = net_srm
        cost_of_capital = capital_required * self.config.cost_of_capital
        underwriting_profit = lob.gross_premium - net_expected_loss - total_ri_premium
        economic_profit = underwriting_profit - cost_of_capital
        is_accretive = economic_profit > 0
        roac = underwriting_profit / capital_required if capital_required > 0 else float('inf')

        if verbose:
            print(f"  Gross E[L] = {np.mean(gross_losses):,.0f}  |  Net E[L] = {net_expected_loss:,.0f}")
            print(f"  Gross SRM  = {gross_srm:,.0f}  |  Net SRM  = {net_srm:,.0f}")
            print(f"  Premium = {lob.gross_premium:,.0f}  |  RI Cost = {total_ri_premium:,.0f}")
            print(f"  UW Profit = {underwriting_profit:,.0f}  |  Economic Profit = {economic_profit:,.0f}")
            print(f"  ROAC = {roac:.2%}  |  {'✓ ACCRETIVE' if is_accretive else '✗ NOT ACCRETIVE'}")

        return {
            "line_of_business": lob.name,
            "gross_premium": lob.gross_premium,
            "gross_expected_loss": np.mean(gross_losses),
            "gross_loss_ratio": np.mean(gross_losses) / lob.gross_premium,
            "gross_var": gross_var, "gross_tvar": gross_tvar, "gross_srm": gross_srm,
            "ri_premium": total_ri_premium,
            "net_expected_loss": net_expected_loss,
            "net_loss_ratio": net_expected_loss / (lob.gross_premium - total_ri_premium) if (lob.gross_premium - total_ri_premium) > 0 else float('inf'),
            "net_var": net_var, "net_tvar": net_tvar, "net_srm": net_srm,
            "capital_required": capital_required,
            "cost_of_capital": cost_of_capital,
            "underwriting_profit": underwriting_profit,
            "economic_profit": economic_profit,
            "roac": roac,
            "is_accretive": is_accretive,
        }

    def _compute_portfolio_metrics(self, lines, verbose=True):
        if verbose:
            print(f"\n--- PORTFOLIO AGGREGATION ---")

        corr = self.config.correlation_matrix
        portfolio_result = self.aggregator.aggregate(
            lines=lines, spectral_measure=self.spectral_measure,
            confidence_level=self.config.confidence_level,
            correlation_matrix=corr
        )

        standalone_capital = self.results["capital_required"].sum()
        diversified_capital = portfolio_result["diversified_capital"]
        div_benefit = 1 - (diversified_capital / standalone_capital) if standalone_capital > 0 else 0

        if verbose:
            print(f"  Standalone Capital (sum) = {standalone_capital:,.0f}")
            print(f"  Diversified Capital = {diversified_capital:,.0f}")
            print(f"  Diversification Benefit = {div_benefit:.1%}")

        if "marginal_contributions" in portfolio_result:
            self.results["allocated_capital"] = portfolio_result["marginal_contributions"]
            self.results["diversification_benefit"] = 1 - self.results["allocated_capital"] / self.results["capital_required"]
            self.results["economic_profit_diversified"] = (
                self.results["underwriting_profit"] - self.results["allocated_capital"] * self.config.cost_of_capital
            )
            self.results["roac_diversified"] = self.results["underwriting_profit"] / self.results["allocated_capital"]
            self.results["is_accretive_diversified"] = self.results["economic_profit_diversified"] > 0


print("✓ Engine loaded successfully. Proceed to Cell 3.")