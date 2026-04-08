"""
Portfolio Pricing Dashboard  v3.0
Complete Streamlit implementation — with traffic lights, 3-scenario GWP optimisation,
methodology panel, key assumptions widget, sensitivity analysis, and derivation trail.
"""

import streamlit as st
import numpy as np
import pandas as pd
from scipy import stats
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import json, warnings, sys, os

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─────────────────────────────────────────────────────────────────────
# COLOUR SCHEME  (blacks / greys / turquoise / blues)
# ─────────────────────────────────────────────────────────────────────
NAVY   = "#0D1B2A"
TEAL   = "#00BCD4"
BLUE   = "#1976D2"
SLATE  = "#37474F"
LGREY  = "#ECEFF1"
GREEN  = "#00ACC1"
AMBER  = "#FF8F00"
RED    = "#C62828"
WHITE  = "#FFFFFF"

LOB_COLOURS = {
    "PropCat_XL":          BLUE,
    "Specialty_Casualty":  TEAL,
    "Marine_Hull_Cargo":   "#26A69A",
    "Political_Violence":  "#5C6BC0",
    "Energy":              "#00897B",
    "Cyber":               "#039BE5",
}

# ─────────────────────────────────────────────────────────────────────
# PLOTLY TEMPLATE — force black text on white background everywhere
# ─────────────────────────────────────────────────────────────────────
FIDELIS_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font=dict(color="black", family="Arial"),
        title_font=dict(color="black"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(
            title_font=dict(color="black"),
            tickfont=dict(color="black"),
            linecolor="black",
            gridcolor="#E0E0E0",
        ),
        yaxis=dict(
            title_font=dict(color="black"),
            tickfont=dict(color="black"),
            linecolor="black",
            gridcolor="#E0E0E0",
        ),
        legend=dict(font=dict(color="black")),
    )
)
pio.templates["fidelis"] = FIDELIS_TEMPLATE
pio.templates.default = "fidelis"

# ─────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Portfolio Pricing Dashboard",
    layout="wide",
    page_icon="📊",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
  .block-container {{padding-top:1rem}}
  [data-testid="metric-container"] {{
      background:#E0F7FA; border-left:3px solid {TEAL};
      border-radius:6px; padding:10px;
  }}
  h1,h2 {{color:{NAVY}}}
  h3 {{color:{BLUE}}}
  .pill-green {{background:#E8F5E9;color:#2E7D32;padding:3px 10px;border-radius:12px;font-weight:600;font-size:0.85rem}}
  .pill-amber {{background:#FFF8E1;color:#F57F17;padding:3px 10px;border-radius:12px;font-weight:600;font-size:0.85rem}}
  .pill-red   {{background:#FFEBEE;color:#C62828;padding:3px 10px;border-radius:12px;font-weight:600;font-size:0.85rem}}
  .audit-box  {{background:#F5F5F5;border-left:4px solid {TEAL};padding:12px;border-radius:4px;font-size:0.85rem}}
</style>
""", unsafe_allow_html=True)

st.title("📊 Portfolio Pricing Dashboard")
st.markdown("**London Market MGU — Net of Reinsurance Accretion Analysis** | v3.0")

# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────
WS = os.path.dirname(os.path.abspath(__file__))

def load_csv(rel):
    p = os.path.join(WS, rel)
    if os.path.exists(p):
        return pd.read_csv(p)
    return pd.DataFrame()

def load_json(rel):
    p = os.path.join(WS, rel)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}

def fmt_k(v, dp=0):
    try:
        v = float(v)
        if abs(v) >= 1_000:
            return f"£{v/1000:,.{dp}f}M"
        return f"£{v:,.{dp}f}k"
    except Exception:
        return str(v)

def traffic_emoji(flag_str):
    s = str(flag_str).upper()
    if "GROW"      in s: return "🟢"
    if "REDUCE"    in s: return "🟠"
    if "STRATEGIC" in s: return "🔴"
    return "⚪"

def traffic_color(flag_str):
    s = str(flag_str).upper()
    if "GROW"      in s: return GREEN
    if "REDUCE"    in s: return AMBER
    if "STRATEGIC" in s: return RED
    return SLATE

def pad_yaxis(fig, margin_pct=0.15):
    """Add vertical padding to a Plotly figure so bars/lines don't crowd the edges."""
    try:
        yvals = []
        for trace in fig.data:
            y = getattr(trace, "y", None)
            if y is not None:
                yvals.extend([v for v in y if v is not None and isinstance(v, (int, float))])
        if yvals:
            ymin, ymax = min(yvals), max(yvals)
            span = ymax - ymin if ymax != ymin else abs(ymax) * 0.5 or 1.0
            pad = span * margin_pct
            fig.update_layout(yaxis_range=[ymin - pad, ymax + pad])
    except Exception:
        pass
    return fig

# ─────────────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────────────
accretion   = load_csv("outputs/accretion_analysis_final.csv")
traffic     = load_csv("outputs/traffic_light_analysis.csv")
gwp_opt     = load_csv("outputs/gwp_optimisation.csv")
cap_alloc   = load_csv("outputs/capital_allocation.csv")
ri_opt      = load_csv("outputs/ri_optimisation.csv")
conf_sens   = load_csv("confidence_sensitivity.csv")
tail_stress = load_csv("tail_correlation_stress_test.csv")
ri_verdicts = load_csv("ri_efficiency_challenge_verdicts.csv")
ri_metrics  = load_csv("ri_efficiency_challenge_metrics.csv")
config      = load_json("data/portfolio_config.json")

LOBS = accretion["LoB"].tolist() if not accretion.empty else []

# ─────────────────────────────────────────────────────────────────────
# LIVE ADJUSTMENTS — apply sidebar parameter changes to static CSV data
# ─────────────────────────────────────────────────────────────────────
# The pipeline bakes in 4% investment yield. The slider lets the user
# see what happens at different yields. We adjust EP by the delta in
# investment income: ΔEP = (slider_yield - 0.04) × mean_term × E[loss]
BAKED_IN_YIELD = 0.04
MEAN_TERM_MAP = {
    "PropCat_XL": 0.75, "Specialty_Casualty": 3.50,
    "Marine_Hull_Cargo": 2.00, "Political_Violence": 1.00,
    "Energy": 2.50, "Cyber": 1.50,
}

def apply_yield_adjustment(df, slider_yield):
    """Adjust EP/profit columns for a change in investment yield vs the baked-in 4%."""
    if df.empty:
        return df
    df = df.copy()
    yield_delta = slider_yield - BAKED_IN_YIELD

    # Identify the right columns
    profit_c = "EP_Net" if "EP_Net" in df.columns else "Net_Profit"
    el_net_c = ("EL_Net" if "EL_Net" in df.columns
                else "Net_Mean_Loss" if "Net_Mean_Loss" in df.columns else None)

    if el_net_c and yield_delta != 0:
        for i, row in df.iterrows():
            lob = row.get("LoB", "")
            mt = MEAN_TERM_MAP.get(lob, 1.75)
            el = row[el_net_c]
            inv_adj = yield_delta * mt * el
            df.at[i, profit_c] = row[profit_c] + inv_adj
            if "InvIncome" in df.columns:
                df.at[i, "InvIncome"] = row["InvIncome"] + inv_adj
        # Recompute derived columns
        acc_c = "IsAccretive" if "IsAccretive" in df.columns else "Accretive"
        if acc_c in df.columns:
            df[acc_c] = df[profit_c] > 0
        if "EP_HP_Ratio" in df.columns and "HP_Net" in df.columns:
            df["EP_HP_Ratio"] = df.apply(
                lambda r: r[profit_c] / r["HP_Net"] if abs(r["HP_Net"]) > 1e-6 else float('nan'), axis=1)
    return df

# ─────────────────────────────────────────────────────────────────────
# SIDEBAR  — KEY ASSUMPTIONS (always visible)
# ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Key Assumptions")
    st.markdown("---")
    hurdle      = st.slider("Hurdle Rate (%)", 5, 20, 10, 1) / 100.0
    confidence  = st.selectbox("TVaR Confidence",
                               [0.990, 0.995, 0.999], index=1,
                               format_func=lambda x: f"{x:.1%} (1-in-{round(1/(1-x))})")
    inv_yield   = st.slider("Investment Yield (%)", 1, 8, 4, 1) / 100.0
    acq_cost    = st.slider("Acquisition Cost (%)", 15, 40, 25, 1) / 100.0

    st.markdown("---")
    st.subheader("Risk Model")
    wang_lambda = 0.855
    st.metric("Wang \u03bb (calibrated on net portfolio)", f"{wang_lambda:.4f}")
    st.caption(f"\u03bb calibrated on NET aggregate losses: Wang E[L\u209f\u2091\u209c] \u2212 E[L\u209f\u2091\u209c] = {hurdle*100:.0f}% \u00d7 TVaR_adjusted (incl. reserve risk loading)")

    st.markdown("---")
    st.subheader("Mean Term of Claims (yrs)")
    mean_term_defaults = {
        "PropCat_XL": 0.75, "Specialty_Casualty": 3.50,
        "Marine_Hull_Cargo": 2.00, "Political_Violence": 1.00,
        "Energy": 2.50, "Cyber": 1.50,
    }
    mt_df = pd.DataFrame([
        {"LoB": k.replace("_", " "), "Years": v}
        for k, v in mean_term_defaults.items()
    ])
    st.dataframe(mt_df, hide_index=True, use_container_width=True)
    st.caption("Investment income = yield × mean term × E[loss] per LoB")

    st.markdown("---")
    st.subheader("Reserve Risk Loadings")
    rrl_defaults = {
        "PropCat_XL": 1.05, "Specialty_Casualty": 1.45,
        "Marine_Hull_Cargo": 1.25, "Political_Violence": 1.10,
        "Energy": 1.30, "Cyber": 1.15,
    }
    rrl_df = pd.DataFrame([
        {"LoB": k.replace("_", " "), "Loading": f"{v:.2f}×"}
        for k, v in rrl_defaults.items()
    ])
    st.dataframe(rrl_df, hide_index=True, use_container_width=True)
    st.caption("Multiplier on premium risk TVaR → feeds Wang λ calibration target")

    st.markdown("---")
    st.subheader("Portfolio (Synthetic)")
    total_gwp = accretion["GWP"].sum() if not accretion.empty else 98_000
    st.metric("Total GWP", fmt_k(total_gwp))
    st.metric("No. of LoBs", len(LOBS))
    st.metric("Simulations", "100,000")
    st.caption("Correlations: Gaussian copula (see Sensitivity tab for tail-correlation stress)")

# ─────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────
(
    tab_exec, tab_traffic, tab_gwp_tab, tab_ri,
    tab_capital, tab_sens, tab_method, tab_audit
) = st.tabs([
    "Executive Summary",
    "Traffic Lights",
    "GWP Optimisation",
    "RI Efficiency",
    "Capital Allocation",
    "Sensitivity Analysis",
    "Methodology",
    "Audit Trail",
])

# ── Apply live investment yield adjustment to all data ──
accretion = apply_yield_adjustment(accretion, inv_yield)

# ═══════════════════════════════════════════════════════════════════════
# TAB 1 — EXECUTIVE SUMMARY
# ═══════════════════════════════════════════════════════════════════════
with tab_exec:
    st.subheader("Portfolio Snapshot")

    if not accretion.empty:
        # Support both old column names and new
        profit_col  = "EP_Net"  if "EP_Net"  in accretion.columns else "Net_Profit"
        hp_col      = "HP_Net"  if "HP_Net"  in accretion.columns else "Cost_of_Capital"
        cap_col     = "TVaRCapital" if "TVaRCapital" in accretion.columns else "Allocated_Capital"
        acc_col     = "IsAccretive" if "IsAccretive" in accretion.columns else "Accretive"

        total_cap    = accretion[cap_col].sum() if cap_col in accretion.columns else 0
        total_profit = accretion[profit_col].sum()
        total_hp     = accretion[hp_col].sum() if hp_col in accretion.columns else 0
        n_accretive  = int((accretion[acc_col] == True).sum())

        # ROAC = (EP + HP) / TVaR — add back the hurdle charge for a true return on capital
        port_roac = (total_profit + total_hp) / total_cap if total_cap > 0 else 0

        # EPR = EP / HP — the primary decision metric
        port_epr = total_profit / total_hp if abs(total_hp) > 0 else None

        # Per-LoB ROAC and EPR columns (computed fresh, not from CSV)
        if hp_col in accretion.columns and cap_col in accretion.columns:
            accretion["_ROAC"] = accretion.apply(
                lambda r: (r[profit_col] + r[hp_col]) / r[cap_col]
                if abs(r[cap_col]) > 1e-6 else float("nan"), axis=1)
            accretion["_EPR"] = accretion.apply(
                lambda r: r[profit_col] / r[hp_col]
                if abs(r[hp_col]) > 1e-6 else float("nan"), axis=1)
        else:
            accretion["_ROAC"] = float("nan")
            accretion["_EPR"]  = float("nan")

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Portfolio GWP",  fmt_k(total_gwp))
        k2.metric("Economic Profit (EP)", fmt_k(total_profit),
                  delta="accretive" if total_profit > 0 else "-dilutive")
        if port_epr is not None:
            k3.metric("EPR (EP / HP)", f"{port_epr:.2f}",
                      help="Economic Profit Ratio = EP ÷ HP. >1 = earning above cost of capital; <1 = dilutive.")
        else:
            k3.metric("EPR (EP / HP)", "N/A",
                      help="HP data not available — run the updated pipeline to generate EP/HP metrics")
        k4.metric("Accretive LoBs", f"{n_accretive} / {len(LOBS)}")
        k5.metric("ROAC", f"{port_roac*100:.1f}%",
                  delta=f"{(port_roac - hurdle)*100:+.1f}pp vs {hurdle:.0%} hurdle",
                  help="Return on Allocated Capital = (EP + HP) / TVaR. Comparable to hurdle rate.")

        st.markdown("---")
        st.subheader("Economic Profit by Line of Business")

        colors = [GREEN if r[acc_col] == True else RED
                  for _, r in accretion.iterrows()]

        bar_text = [f"EPR: {r['_EPR']:.2f}" if pd.notna(r["_EPR"]) else fmt_k(r[profit_col])
                    for _, r in accretion.iterrows()]

        fig_acc = go.Figure(go.Bar(
            x=accretion["LoB"],
            y=accretion[profit_col] / 1000,
            marker_color=colors,
            text=bar_text,
            textposition="outside",
        ))
        fig_acc.add_hline(y=0, line_color=TEAL, line_dash="dash", line_width=2)
        fig_acc.update_layout(
            title="Economic Profit (£M) — net of RI, after Wang hurdle deduction",
            xaxis=dict(title="Line of Business", tickfont=dict(color="black"), title_font=dict(color="black")),
            yaxis=dict(title="Economic Profit £M", tickfont=dict(color="black"), title_font=dict(color="black")),
            plot_bgcolor="white", paper_bgcolor="white",
            font=dict(color="black"),
        )
        st.plotly_chart(pad_yaxis(fig_acc), use_container_width=True)

        tbl = accretion.copy()
        disp_cols = ["LoB", "GWP"]
        if profit_col in tbl.columns:
            tbl["EP (£k)"] = tbl[profit_col].map("{:+,.0f}".format)
            disp_cols.append("EP (£k)")
        tbl["EPR"] = tbl["_EPR"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
        disp_cols.append("EPR")
        tbl["ROAC"] = tbl["_ROAC"].map(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A")
        disp_cols.append("ROAC")
        if "RI_Efficiency" in tbl.columns:
            tbl["RI Eff (Ceded EP/HP)"] = tbl["RI_Efficiency"].map(
                lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
            disp_cols.append("RI Eff (Ceded EP/HP)")
        tbl["Status"] = tbl[acc_col].map(lambda x: "Accretive" if x else "Dilutive")
        disp_cols.append("Status")
        st.dataframe(tbl[disp_cols], use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════
# TAB 2 — TRAFFIC LIGHTS
# ═══════════════════════════════════════════════════════════════════════
with tab_traffic:
    st.subheader("Traffic Light Analysis — Strategic Recommendations by Line")

    st.markdown("""
| Signal | Meaning |
|--------|---------|
| **GROW** | EP > 0 AND EPR > 1 — earns above cost of risk capital; expand capacity |
| **MAINTAIN** | Broadly accretive or near break-even — monitor and optimise |
| **REDUCE** | Sub-hurdle but correctable — price/RI remediation available |
| **STRATEGIC REVIEW** | Severely dilutive with no clear fix visible — senior review required |
    """)

    # Build a lookup from accretion data for corrected ROAC and EPR
    _acc_lookup = {}
    if not accretion.empty and "_ROAC" in accretion.columns:
        for _, _ar in accretion.iterrows():
            _acc_lookup[_ar["LoB"]] = {
                "roac": _ar["_ROAC"], "epr": _ar["_EPR"],
                "ep": _ar[profit_col], "hp": _ar.get(hp_col, 0),
                "tvar": _ar.get(cap_col, 0),
            }

    if not traffic.empty:
        for _, row in traffic.iterrows():
            lob    = row["LoB"]
            flag_csv = str(row.get("Flag", ""))
            ap     = float(row.get("Accretive_Profit_£M", 0))
            cap    = float(row.get("TVaR_Capital_£M", 0))
            action = row.get("Key_Action", "")
            remed  = row.get("First_Remediation", "")
            reason = row.get("Reasoning", "")
            capgwp = float(row.get("Capital/GWP", 0))
            bep    = row.get("Breakeven_Price_Increase_%", "")
            opt    = row.get("Optimal_GWP_£k", "")
            chg    = row.get("GWP_Change_%", "")

            # Use corrected metrics from accretion if available
            acc = _acc_lookup.get(lob, {})
            epr  = acc.get("epr", float("nan"))
            roac = acc.get("roac", float("nan"))
            ep_k = acc.get("ep", ap * 1000)  # fallback to traffic CSV value

            # Override traffic light flag based on EP (absolute) — the primary signal
            if pd.notna(epr) and not pd.isna(ep_k):
                if ep_k > 0 and epr > 1:
                    flag = "🟢 GROW"
                elif ep_k > 0 or (pd.notna(epr) and 0.8 <= epr <= 1.0):
                    flag = "🟡 MAINTAIN"
                elif ep_k < 0 and epr < 0:
                    flag = "🔴 STRATEGIC REVIEW"
                else:
                    flag = "🟠 REDUCE"
            else:
                flag = flag_csv  # fall back to CSV if no corrected data

            emoji  = traffic_emoji(flag)
            color  = traffic_color(flag)

            epr_str  = f"EPR {epr:.2f}" if pd.notna(epr) else ""
            roac_str = f"ROAC {roac*100:.1f}%" if pd.notna(roac) else ""

            header = f"{emoji}  {lob}  —  EP {fmt_k(ep_k, 1)}  |  {epr_str}  |  {action}"
            with st.expander(header, expanded=True):
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Economic Profit", fmt_k(ep_k, 1),
                          delta="accretive" if ep_k > 0 else "-dilutive")
                c2.metric("EPR (EP / HP)", f"{epr:.2f}" if pd.notna(epr) else "N/A",
                          help="Economic Profit Ratio. >1 = earning above cost of capital.")
                c3.metric("Capital (TVaR)",  fmt_k(cap*1000))
                c4.metric("Capital / GWP",   f"{capgwp:.1f}x")
                c5.metric("ROAC", f"{roac*100:.1f}%" if pd.notna(roac) else "N/A",
                          delta=f"{(roac - hurdle)*100:+.1f}pp vs {hurdle:.0%}" if pd.notna(roac) else None,
                          help="(EP + HP) / TVaR — comparable to hurdle rate.")

                st.markdown(f"**Reasoning:** {reason}")
                st.markdown(f"**First Remediation:** {remed}")
                if bep:
                    try:
                        st.markdown(f"**Break-even Price Increase Required:** {float(bep):.1f}%")
                    except Exception:
                        pass
                if opt:
                    try:
                        st.markdown(
                            f"**Optimal GWP Target:** {fmt_k(float(opt))} ({float(chg):+.1f}% vs current)")
                    except Exception:
                        pass
                best_ri = row.get("Best_RI", "")
                ri_imp  = row.get("RI_Impact_£k", 0)
                if best_ri:
                    try:
                        st.markdown(
                            f"**Best RI Move:** {best_ri} — economic profit impact {fmt_k(float(ri_imp), 1)}")
                    except Exception:
                        pass
    else:
        st.warning("traffic_light_analysis.csv not found.")

# ═══════════════════════════════════════════════════════════════════════
# TAB 3 — GWP OPTIMISATION  (3 Scenarios)
# ═══════════════════════════════════════════════════════════════════════
with tab_gwp_tab:
    st.subheader("GWP Mix Optimisation — Four Scenarios")

    st.markdown("""
GWP targets depend on **what you are trying to maximise** and **what constraint binds**.
Scenarios A–C are **linear programs** solved via `scipy.optimize.linprog` (HiGHS solver).
Scenario D has a nonlinear ratio objective, solved via `scipy.optimize.minimize` (SLSQP).
All use per-LoB GWP bounds of 50%–200% of current.

**Key assumption:** Additional GWP in any line carries the same risk profile (loss ratio,
RI structure, capital intensity) as the current book. Under this linear scaling, EP, HP,
and TVaR all scale proportionally with GWP.

| Scenario | Objective | Binding Constraint | Strategic Question |
|----------|-----------|--------------------|--------------------|
| **A — Max ROAC** | Maximise total EP | **Fixed total TVaR** (capital committed at start of year) | Given your committed capital, what GWP mix maximises return? |
| **B — Max EP** | Maximise total EP | **Fixed total HP** (risk appetite held constant) | Given your risk charge budget, where should you concentrate? |
| **C — Min Capital** | Minimise total TVaR | **Fixed total GWP** (premium plan held constant) | Given your premium target, which mix uses least capital? |
| **D — Max RI Efficiency** | Minimise Ceded EP / Ceded HP | **Fixed total GWP** | Which allocation makes your reinsurance programme work hardest? |
    """)

    if not accretion.empty:

        @st.cache_data
        def compute_four_scenarios(accretion_json, hurdle_rate):
            from scipy.optimize import linprog, minimize

            df = pd.read_json(accretion_json)

            # ── Column compatibility ──────────────────────────────────
            profit_c = "EP_Net" if "EP_Net" in df.columns else "Net_Profit"
            cap_c    = "TVaRCapital" if "TVaRCapital" in df.columns else "Allocated_Capital"
            hp_c     = "HP_Net" if "HP_Net" in df.columns else "Cost_of_Capital"
            ri_eff_c = "RI_Efficiency" if "RI_Efficiency" in df.columns else None

            n = len(df)
            lobs       = df["LoB"].values
            gwp_base   = df["GWP"].values.astype(float)
            ep_base    = df[profit_c].values.astype(float)
            tvar_base  = df[cap_c].values.astype(float)
            hp_base    = df[hp_c].values.astype(float) if hp_c in df.columns else tvar_base * hurdle_rate

            # ── Per-LoB bounds: 50%–200% of current GWP ──────────────
            lp_bounds = [(0.5, 2.0)] * n

            # ── Helper: solve a LINEAR PROGRAM ────────────────────────
            # linprog always minimises c·w, so to maximise EP we negate.
            # A_eq · w = b_eq defines the equality constraint.
            def solve_lp(c_vec, eq_coeffs, eq_rhs):
                """Solve min c·w s.t. eq_coeffs·w = eq_rhs, 0.5 ≤ w ≤ 2.0."""
                res = linprog(
                    c=c_vec,
                    A_eq=eq_coeffs.reshape(1, -1),
                    b_eq=np.array([eq_rhs]),
                    bounds=lp_bounds,
                    method="highs",   # robust interior-point / simplex solver
                )
                return res

            # ══════════════════════════════════════════════════════════
            # SCENARIO A — Max EP, fixed TVaR (capital committed)
            # ══════════════════════════════════════════════════════════
            res_a = solve_lp(
                c_vec    = -ep_base,               # minimise -EP  =  maximise EP
                eq_coeffs = tvar_base,             # Σ(TVaR_i × w_i) = total TVaR
                eq_rhs    = float(tvar_base.sum()),
            )

            # ══════════════════════════════════════════════════════════
            # SCENARIO B — Max EP, fixed HP (risk appetite constant)
            # ══════════════════════════════════════════════════════════
            res_b = solve_lp(
                c_vec    = -ep_base,               # maximise EP
                eq_coeffs = hp_base,               # Σ(HP_i × w_i) = total HP
                eq_rhs    = float(hp_base.sum()),
            )

            # ══════════════════════════════════════════════════════════
            # SCENARIO C — Min TVaR (capital), fixed GWP
            # ══════════════════════════════════════════════════════════
            res_c = solve_lp(
                c_vec    = tvar_base,              # minimise TVaR
                eq_coeffs = gwp_base,              # Σ(GWP_i × w_i) = total GWP
                eq_rhs    = float(gwp_base.sum()),
            )

            # ══════════════════════════════════════════════════════════
            # SCENARIO D — Min RI Efficiency, fixed GWP  (NONLINEAR)
            # ══════════════════════════════════════════════════════════
            if ri_eff_c and ri_eff_c in df.columns:
                ri_eff = df[ri_eff_c].values.astype(float)
                ri_eff = np.where(np.isnan(ri_eff) | (ri_eff == 0), 1.0, ri_eff)
            else:
                # Proxy: cession rate (higher cession → less efficient RI)
                if "Net_Premium" in df.columns:
                    net_prem = df["Net_Premium"].values.astype(float)
                    ri_eff = (1 - net_prem / gwp_base).clip(0, 1)
                else:
                    ri_eff = np.ones(n) * 0.5

            total_gwp_current = float(gwp_base.sum())
            con_fix_gwp = {
                "type": "eq",
                "fun":  lambda w: float(np.dot(gwp_base, w)) - total_gwp_current,
                "jac":  lambda w: gwp_base,
            }

            def obj_ri(w):
                """Weighted-average RI efficiency across portfolio."""
                wt_gwp = gwp_base * w
                return float(np.dot(ri_eff, wt_gwp)) / float(wt_gwp.sum())

            def obj_ri_jac(w):
                wt_gwp = gwp_base * w
                total  = float(wt_gwp.sum())
                avg    = float(np.dot(ri_eff, wt_gwp)) / total
                return gwp_base * (ri_eff - avg) / total

            w0 = np.ones(n)
            res_d = minimize(obj_ri, w0, jac=obj_ri_jac,
                             method="SLSQP",
                             bounds=[(0.5, 2.0)] * n,
                             constraints=[con_fix_gwp],
                             options={"maxiter": 500, "ftol": 1e-8})

            # ── Build result DataFrames ───────────────────────────────
            results = {}
            labels  = {
                "A": "Max ROAC",
                "B": "Max EP (Fixed HP)",
                "C": "Min Capital",
                "D": "Max RI Efficiency",
            }
            for key, res in [("A", res_a), ("B", res_b), ("C", res_c), ("D", res_d)]:
                w = res.x if res.success else np.ones(n)
                new_gwp = gwp_base * w

                port_ep   = float(np.dot(ep_base, w))
                port_tvar = float(np.dot(tvar_base, w))
                port_hp   = float(np.dot(hp_base, w))
                port_roac = (port_ep + port_hp) / port_tvar if abs(port_tvar) > 1e-6 else float("nan")
                port_epr  = port_ep / port_hp if abs(port_hp) > 1e-6 else float("nan")

                tmp = pd.DataFrame({
                    "LoB":         lobs,
                    "Current_GWP": gwp_base,
                    "New_GWP":     np.round(new_gwp, 0),
                    "Change_k":    np.round(new_gwp - gwp_base, 0),
                    "Change_%":    np.round((w - 1.0) * 100, 1),
                    "Scenario":    f"Scenario {key}: {labels[key]}",
                })
                tmp.attrs["port_ep"]    = port_ep
                tmp.attrs["port_tvar"]  = port_tvar
                tmp.attrs["port_hp"]    = port_hp
                tmp.attrs["port_roac"]  = port_roac
                tmp.attrs["port_epr"]   = port_epr
                tmp.attrs["port_gwp"]   = float(new_gwp.sum())
                tmp.attrs["converged"]  = bool(res.success)
                results[key] = tmp

            return results

        scenarios = compute_four_scenarios(accretion.to_json(), hurdle)

        sA, sB, sC, sD, sComp = st.tabs([
            "A — Max ROAC",
            "B — Max EP (Fixed HP)",
            "C — Min Capital",
            "D — Max RI Efficiency",
            "Comparison",
        ])

        def render_scenario(tab_obj, key, label, desc):
            with tab_obj:
                st.markdown(f"**Objective:** {desc}")
                df_s = scenarios[key]

                # Show portfolio-level impact metrics
                port_ep   = df_s.attrs.get("port_ep", float("nan"))
                port_tvar = df_s.attrs.get("port_tvar", float("nan"))
                port_hp   = df_s.attrs.get("port_hp", float("nan"))
                port_roac = df_s.attrs.get("port_roac", float("nan"))
                port_epr  = df_s.attrs.get("port_epr", float("nan"))
                port_gwp  = df_s.attrs.get("port_gwp", float("nan"))
                converged = df_s.attrs.get("converged", True)

                mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
                mc1.metric("Total GWP", fmt_k(port_gwp))
                mc2.metric("Total EP", fmt_k(port_ep, 1))
                mc3.metric("EPR (EP / HP)", f"{port_epr:.2f}" if pd.notna(port_epr) else "—",
                           help="Economic Profit Ratio — EP / HP. >1 = value-creating")
                mc4.metric("Total TVaR", fmt_k(port_tvar))
                mc5.metric("Total HP", fmt_k(port_hp))
                mc6.metric("ROAC", f"{port_roac*100:.2f}%" if pd.notna(port_roac) else "—",
                           help="(EP + HP) / TVaR — informational")
                if not converged:
                    st.warning("Optimiser did not converge — results may be approximate.")

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name="Current GWP", x=df_s["LoB"],
                    y=df_s["Current_GWP"] / 1000,
                    marker_color=SLATE, opacity=0.5,
                ))
                fig.add_trace(go.Bar(
                    name=f"Scenario {key} Target", x=df_s["LoB"],
                    y=df_s["New_GWP"] / 1000,
                    marker_color=TEAL,
                ))
                fig.update_layout(
                    barmode="group",
                    title=f"Scenario {key}: {label} — GWP Reallocation",
                    xaxis_title="Line of Business", yaxis_title="GWP £M",
                    plot_bgcolor="white", paper_bgcolor="white",
                    font=dict(color="black"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(pad_yaxis(fig), use_container_width=True)

                tbl2 = df_s[["LoB", "Current_GWP", "New_GWP", "Change_k", "Change_%"]].copy()
                tbl2["Current_GWP"] = tbl2["Current_GWP"].map(lambda x: fmt_k(x))
                tbl2["New_GWP"]     = tbl2["New_GWP"].map(lambda x: fmt_k(x))
                tbl2["Change_k"]    = tbl2["Change_k"].map(lambda x: f"{x:+,.0f}k")
                tbl2["Change_%"]    = tbl2["Change_%"].map(lambda x: f"{x:+.1f}%")
                st.dataframe(tbl2, use_container_width=True, hide_index=True)

        render_scenario(sA, "A", "Max ROAC",
            "Maximise total EP subject to **fixed total TVaR** (capital committed at start of year). "
            "GWP and HP can float. Shifts premium toward lines with the highest EP per unit of "
            "capital consumed.")
        render_scenario(sB, "B", "Max EP (Fixed HP)",
            "Maximise total EP subject to **fixed total Hurdle Profit** (risk appetite held constant). "
            "GWP and TVaR can float. Concentrates into lines where the Wang risk charge is lowest "
            "relative to the economic profit generated.")
        render_scenario(sC, "C", "Min Capital",
            "Minimise total TVaR subject to **fixed total GWP** (premium plan held constant). "
            "Shifts premium toward lines with the lowest capital intensity (TVaR / GWP). "
            "The capital-efficiency question: write the same premium with less capital. "
            "Solved via `linprog` (HiGHS).")
        render_scenario(sD, "D", "Max RI Efficiency",
            "Minimise portfolio-weighted Ceded EP / Ceded HP subject to **fixed total GWP**. "
            "Shifts GWP to lines where RI releases the most capital per £ of economic profit ceded. "
            "Solved via `minimize` (SLSQP) — nonlinear ratio objective.")

        with sComp:
            st.subheader("Scenario Comparison — GWP Targets")

            # Portfolio-level comparison table
            comp_metrics = []
            for key, label in [("A", "Max ROAC"), ("B", "Max EP (Fixed HP)"),
                                ("C", "Min Capital"), ("D", "Max RI Efficiency")]:
                s = scenarios[key]
                comp_metrics.append({
                    "Scenario": f"{key}: {label}",
                    "Total GWP": fmt_k(s.attrs.get("port_gwp", 0)),
                    "Total EP": fmt_k(s.attrs.get("port_ep", 0), 1),
                    "Total TVaR": fmt_k(s.attrs.get("port_tvar", 0)),
                    "Total HP": fmt_k(s.attrs.get("port_hp", 0)),
                    "EPR": f"{s.attrs.get('port_epr', 0):.2f}",
                    "ROAC": f"{s.attrs.get('port_roac', 0)*100:.2f}%",
                })
            st.dataframe(pd.DataFrame(comp_metrics), use_container_width=True, hide_index=True)

            # Per-LoB GWP comparison chart
            comp_rows = []
            for key, label in [("A", "Max ROAC"), ("B", "Max EP (Fixed HP)"),
                                ("C", "Min Capital"), ("D", "Max RI Efficiency")]:
                for _, r in scenarios[key].iterrows():
                    comp_rows.append({
                        "LoB": r["LoB"],
                        "Scenario": f"{key}: {label}",
                        "Target GWP k": r["New_GWP"],
                        "Change %": r["Change_%"],
                    })
            comp_df = pd.DataFrame(comp_rows)

            fig_comp = px.bar(
                comp_df, x="LoB", y="Target GWP k",
                color="Scenario", barmode="group",
                color_discrete_sequence=[BLUE, TEAL, GREEN, AMBER],
                title="GWP Targets Across All Four Scenarios",
            )
            fig_comp.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                font=dict(color="black"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(pad_yaxis(fig_comp), use_container_width=True)

            pivot = comp_df.pivot(index="LoB", columns="Scenario", values="Target GWP k")
            pivot.insert(0, "Current GWP", accretion.set_index("LoB")["GWP"])
            pivot_fmt = pivot.map(lambda x: fmt_k(x) if pd.notnull(x) else "—")
            st.dataframe(pivot_fmt, use_container_width=True)

            st.info(
                "**A (Max ROAC):** Fixed capital — shifts GWP to lines with highest EP per unit TVaR. "
                "**B (Max EP):** Fixed hurdle profit — shifts to lines with highest EP per unit risk charge. "
                "**C (Min Capital):** Fixed GWP — finds the premium mix that uses least capital. "
                "**D (RI Efficiency):** Fixed GWP — makes the reinsurance programme work hardest. "
                "A–C solved with `linprog` (HiGHS); D with `minimize` (SLSQP). Per-LoB bounds 50%–200%."
            )

# ═══════════════════════════════════════════════════════════════════════
# TAB 4 — RI EFFICIENCY
# ═══════════════════════════════════════════════════════════════════════
with tab_ri:
    st.subheader("RI Efficiency — Challenge and Defence Summary")

    if not ri_verdicts.empty:
        st.markdown("**RI Programme Verdicts** (from Capital Efficiency Challenge)")

        # Rename confusing columns for display
        verdicts_display = ri_verdicts.copy()
        if "Accretion_Dilution" in verdicts_display.columns:
            verdicts_display["Line Status"] = verdicts_display["Accretion_Dilution"].map(
                lambda x: "Accretive" if x in [True, "True", "true", 1] else "Dilutive")
            verdicts_display.drop(columns=["Accretion_Dilution"], inplace=True)

        vcols = st.columns(len(verdicts_display))
        for i, (_, row) in enumerate(verdicts_display.iterrows()):
            v = str(row.get("Overall_Verdict", "")).upper()
            col = TEAL if "EFFICIENT" in v or "ACCEPTABLE" in v else (AMBER if "QUESTIONABLE" in v else RED)
            status = row.get("Line Status", "")
            status_col = GREEN if status == "Accretive" else RED
            vcols[i].markdown(
                f"<div style='background:{col}20;border-left:4px solid {col};"
                f"padding:8px;border-radius:4px'>"
                f"<b>{row['LoB']}</b><br/>"
                f"RI Verdict: {row['Overall_Verdict']}<br/>"
                f"<span style='color:{status_col}'>{status}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.markdown("")

        # ── Explanatory text for RI efficiency metrics ──
        if not ri_metrics.empty:
            st.markdown("---")
            st.markdown("#### Understanding the RI Efficiency Metrics")

            expl_c1, expl_c2 = st.columns(2)
            with expl_c1:
                st.markdown(
                    f"<div style='background:#f0f7ff;padding:12px;border-radius:6px;"
                    f"border-left:4px solid {TEAL}'>"
                    f"<b>Cost-Benefit Ratio</b> = Expected RI Recovery &divide; RI Premium<br/><br/>"
                    f"For every &pound;1 of reinsurance premium paid, how much comes back "
                    f"as claims recoveries? A ratio of <b>0.85</b> means 85p recovered "
                    f"per &pound;1 spent. Higher is better value — it means the RI "
                    f"programme is recovering a larger share of the premium through claims."
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with expl_c2:
                st.markdown(
                    f"<div style='background:#f0fff0;padding:12px;border-radius:6px;"
                    f"border-left:4px solid {GREEN}'>"
                    f"<b>Capital Impact Ratio</b> = Capital Released &divide; RI Premium<br/><br/>"
                    f"For every &pound;1 of reinsurance premium paid, how much regulatory "
                    f"capital (TVaR) is freed up? A ratio of <b>5.0</b> means &pound;5 of "
                    f"capital released per &pound;1 of RI premium. Higher is more "
                    f"capital-efficient — the RI programme is releasing more capital "
                    f"per pound spent."
                    f"</div>",
                    unsafe_allow_html=True,
                )

            # Show the actual metrics table
            metric_cols = ["LoB", "RI_Premium", "Expected_Recovery", "Cost_Benefit_Ratio",
                           "Capital_Reduction", "Capital_Impact_Ratio"]
            metric_cols = [c for c in metric_cols if c in ri_metrics.columns]
            if metric_cols:
                st.markdown("")
                metrics_disp = ri_metrics[metric_cols].copy()
                # Format currency columns for readability
                for cc in ["RI_Premium", "Expected_Recovery", "Capital_Reduction"]:
                    if cc in metrics_disp.columns:
                        metrics_disp[cc] = metrics_disp[cc].apply(lambda x: f"£{x/1000:,.0f}k" if pd.notna(x) else "")
                for cc in ["Cost_Benefit_Ratio", "Capital_Impact_Ratio"]:
                    if cc in metrics_disp.columns:
                        metrics_disp[cc] = metrics_disp[cc].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
                st.dataframe(metrics_disp, use_container_width=True, hide_index=True)
                st.caption(
                    "Cost-Benefit: higher = more premium recovered through claims. "
                    "Capital Impact: higher = more capital released per £ of RI premium."
                )
            st.markdown("")

    if not ri_opt.empty:
        st.subheader("RI Restructuring Options by Line")
        lob_sel = st.selectbox("Select Line of Business", ri_opt["LoB"].unique(), key="ri_lob")
        sub = ri_opt[ri_opt["LoB"] == lob_sel].copy()

        colors_ri = [GREEN if v == "BETTER" else (AMBER if v == "NEUTRAL" else RED)
                     for v in sub["Verdict"]]

        fig_ri = go.Figure(go.Bar(
            x=sub["Alternative"],
            y=sub["Accretive_Profit_Change"],
            marker_color=colors_ri,
            text=[f"{r:+.2f}pp" for r in sub.get("ROAC_Change_pp", sub.get("ROAC_Change", [0]*len(sub)))],
            textposition="outside",
        ))
        fig_ri.add_hline(y=0, line_color=TEAL, line_dash="dash")
        fig_ri.update_layout(
            title=f"{lob_sel} — RI Alternative Impact on Economic Profit (k)",
            yaxis_title="Change in Economic Profit k",
            plot_bgcolor="white", paper_bgcolor="white",
            font=dict(color="black"),
        )
        st.plotly_chart(pad_yaxis(fig_ri), use_container_width=True)

        roac_chg_col = "ROAC_Change_pp" if "ROAC_Change_pp" in sub.columns else "ROAC_Change"
        ri_disp_cols = ["Alternative", "Structure", "RI_Premium_Change", "Net_EL_Change",
                        "Capital_Change", "Accretive_Profit_Change", roac_chg_col, "Verdict"]
        ri_disp_cols = [c for c in ri_disp_cols if c in sub.columns]
        ri_display = sub[ri_disp_cols].rename(columns={
            "Accretive_Profit_Change": "EP_Change",
            "RI_Premium_Change": "RI_Prem_Change",
            "Net_EL_Change": "Net_EL_Change",
        })
        st.dataframe(ri_display, use_container_width=True, hide_index=True)
        st.caption("BETTER = improves economic profit  |  NEUTRAL = < £200k change  |  WORSE = reduces profit")

# ═══════════════════════════════════════════════════════════════════════
# TAB 5 — CAPITAL ALLOCATION
# ═══════════════════════════════════════════════════════════════════════
with tab_capital:
    st.subheader(f"Capital Allocation — Euler TVaR at {confidence:.1%}")
    st.info(
        "**Informational only.** This tab shows Euler-gradient TVaR capital allocation "
        "for regulatory and rating agency reporting purposes (Lloyd's SCR, AM Best BCAR). "
        "Capital allocation does **not** enter the Economic Profit or EP/HP pricing calculations — "
        "the Wang Natural Allocation already embeds the cost of risk via the hurdle profit (HP) term. "
        "ROAC = (EP + HP) / TVaR is shown elsewhere for executive reporting convention only — "
        "the primary decision metric is **EPR (EP / HP)**."
    )

    if not cap_alloc.empty:
        colors_cap = [LOB_COLOURS.get(lob, BLUE) for lob in cap_alloc["LoB"]]

        fig_cap = go.Figure(go.Bar(
            x=cap_alloc["LoB"],
            y=cap_alloc["Allocated_Capital"] / 1000,
            marker_color=colors_cap,
            text=[f"{r:.1f}% div" for r in cap_alloc["Div_Benefit_%"]],
            textposition="inside",
        ))
        fig_cap.update_layout(
            title="Allocated Capital (£M) — Euler Gradient Allocation",
            xaxis_title="Line of Business", yaxis_title="Allocated Capital £M",
            plot_bgcolor="white", paper_bgcolor="white",
            font=dict(color="black"),
        )
        st.plotly_chart(pad_yaxis(fig_cap), use_container_width=True)

        fig_div = go.Figure()
        fig_div.add_trace(go.Bar(
            name="Standalone TVaR",
            x=cap_alloc["LoB"], y=cap_alloc["Standalone_TVaR"] / 1000,
            marker_color=SLATE, opacity=0.5,
        ))
        fig_div.add_trace(go.Bar(
            name="Euler Allocated (diversified)",
            x=cap_alloc["LoB"], y=cap_alloc["Allocated_Capital"] / 1000,
            marker_color=TEAL,
        ))
        fig_div.update_layout(
            barmode="overlay",
            title="Standalone vs Diversified Capital (£M) — shaded = diversification benefit",
            plot_bgcolor="white", paper_bgcolor="white",
            font=dict(color="black"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(pad_yaxis(fig_div), use_container_width=True)

        display_cap = cap_alloc.copy()
        for col in ["Allocated_Capital", "Standalone_TVaR", "Diversification_Benefit"]:
            display_cap[col] = display_cap[col].map(lambda x: fmt_k(x))
        st.dataframe(display_cap, use_container_width=True, hide_index=True)

    if not conf_sens.empty:
        st.subheader("Confidence Level Sensitivity")
        st.dataframe(conf_sens, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════
# TAB 6 — SENSITIVITY ANALYSIS
# ═══════════════════════════════════════════════════════════════════════
with tab_sens:
    st.subheader("Sensitivity Analysis — Portfolio ROAC vs Key Parameters")

    if not accretion.empty:

        @st.cache_data
        def run_sensitivity(accretion_json, base_hurdle):
            df = pd.read_json(accretion_json)
            profit_c = "EP_Net" if "EP_Net" in df.columns else "Net_Profit"
            cap_c    = "TVaRCapital" if "TVaRCapital" in df.columns else "Allocated_Capital"
            base_profit = df[profit_c].sum()
            base_cap    = df[cap_c].sum() if cap_c in df.columns else 1

            profit_col = "EP_Net" if "EP_Net" in df.columns else "Net_Profit"
            cap_col    = "TVaRCapital" if "TVaRCapital" in df.columns else "Allocated_Capital"
            hp_col     = "HP_Net" if "HP_Net" in df.columns else "Cost_of_Capital" if "Cost_of_Capital" in df.columns else None
            base_hp     = df[hp_col].sum() if hp_col and hp_col in df.columns else base_cap * base_hurdle
            base_roac   = (base_profit + base_hp) / base_cap if base_cap else 0
            el_net_col = ("EL_Net" if "EL_Net" in df.columns
                          else "Net_Mean_Loss" if "Net_Mean_Loss" in df.columns else None)
            mt_col     = "Mean_Term" if "Mean_Term" in df.columns else None
            coc_col    = "Cost_of_Capital" if "Cost_of_Capital" in df.columns else None

            el_net_s = df[el_net_col] if el_net_col else df[profit_col] * 0
            mt_s     = df[mt_col] if mt_col else pd.Series([1.75] * len(df), index=df.index)

            params = [
                ("Hurdle Rate",          base_hurdle, 0.10),
                ("Investment Yield",     0.04,         0.10),
                ("Wang Lambda",          0.855,        0.10),
                ("Reserve Risk Loading", None,         0.10),
                ("Loss Ratio (Net)",     None,         0.10),
            ]
            rows = []
            for param, base, shift in params:
                for direction, sign in [("+10%", 1), ("-10%", -1)]:
                    if param == "Hurdle Rate":
                        if hp_col and hp_col in df.columns:
                            delta_hp = df[hp_col] * (sign * shift)
                            new_profit = df[profit_col] - delta_hp
                        else:
                            coc_base = df[coc_col] if coc_col else df[cap_col] * base
                            new_coc = df[cap_col] * (base * (1 + sign * shift))
                            new_profit = df[profit_col] + (coc_base - new_coc)
                    elif param == "Investment Yield":
                        delta = el_net_s * mt_s * (base * sign * shift)
                        new_profit = df[profit_col] + delta
                    elif param == "Wang Lambda":
                        if hp_col and hp_col in df.columns:
                            delta = df[hp_col] * (sign * shift)
                            new_profit = df[profit_col] - delta
                        else:
                            delta = df[cap_col] * base_hurdle * (sign * shift)
                            new_profit = df[profit_col] + delta
                    elif param == "Reserve Risk Loading":
                        if hp_col and hp_col in df.columns:
                            delta = df[hp_col] * (sign * shift)
                            new_profit = df[profit_col] - delta
                        else:
                            new_profit = df[profit_col] - df[cap_col] * base_hurdle * (sign * shift)
                    else:
                        new_profit = df[profit_col] - el_net_s * sign * shift

                    # ROAC = (EP + HP) / TVaR — HP doesn't change in this shock
                    # except for hurdle-rate and Wang lambda shocks where HP shifts
                    if param == "Hurdle Rate":
                        new_hp = base_hp * (1 + sign * shift)
                    elif param in ("Wang Lambda", "Reserve Risk Loading"):
                        new_hp = base_hp * (1 + sign * shift)
                    else:
                        new_hp = base_hp
                    new_roac  = (new_profit.sum() + new_hp) / base_cap if base_cap > 0 else 0
                    roac_chg  = (new_roac - base_roac) * 100
                    rows.append({
                        "Parameter": param, "Direction": direction,
                        "New ROAC %": round(new_roac * 100, 2),
                        "ROAC Change (pp)": round(roac_chg, 2),
                        "Sensitivity": ("HIGH" if abs(roac_chg) > 1.5
                                        else "MODERATE" if abs(roac_chg) > 0.5
                                        else "LOW"),
                    })
            return pd.DataFrame(rows)

        sens_df = run_sensitivity(accretion.to_json(), hurdle)

        tornado_up   = sens_df[sens_df["Direction"] == "+10%"].set_index("Parameter")["ROAC Change (pp)"]
        tornado_down = sens_df[sens_df["Direction"] == "-10%"].set_index("Parameter")["ROAC Change (pp)"]
        params_sorted = tornado_up.abs().sort_values(ascending=True).index.tolist()

        fig_t = go.Figure()
        fig_t.add_trace(go.Bar(
            name="+10% shock",
            y=params_sorted,
            x=[tornado_up.get(p, 0) for p in params_sorted],
            orientation="h", marker_color=BLUE,
        ))
        fig_t.add_trace(go.Bar(
            name="-10% shock",
            y=params_sorted,
            x=[tornado_down.get(p, 0) for p in params_sorted],
            orientation="h", marker_color=TEAL,
        ))
        fig_t.add_vline(x=0, line_color=NAVY, line_width=1)
        fig_t.update_layout(
            barmode="overlay",
            title="Tornado Chart — Portfolio ROAC sensitivity to +/-10% shocks (pp change)",
            xaxis_title="ROAC Change (percentage points)",
            plot_bgcolor="white", paper_bgcolor="white",
            font=dict(color="black"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(pad_yaxis(fig_t), use_container_width=True)

        def colour_sens(v):
            s = str(v)
            if "HIGH"     in s: return f"background-color:{RED}30;color:{RED};font-weight:600"
            if "MODERATE" in s: return f"background-color:{AMBER}30;color:{AMBER};font-weight:600"
            if "LOW"      in s: return f"background-color:{GREEN}30;color:{GREEN};font-weight:600"
            return ""

        st.dataframe(
            sens_df.style.map(colour_sens, subset=["Sensitivity"]),
            use_container_width=True, hide_index=True,
        )

# ═══════════════════════════════════════════════════════════════════════
# TAB 7 — METHODOLOGY
# ═══════════════════════════════════════════════════════════════════════
with tab_method:
    st.subheader("Methodology — Plain English Guide")

    st.markdown("""
### What this dashboard does

This dashboard analyses whether each line of business in the London Market
portfolio is **accretive** — generating a return above the cost of capital — on a
**net-of-reinsurance** basis.

---

### Step 1 — Loss Simulation

100,000 scenarios of gross losses are generated for 6 lines of business using a
**Gaussian copula** to model correlation between lines. Marginal distributions are
calibrated to realistic London Market loss ratios (~50–60% expected).

The copula captures diversification — Property Cat and Political Violence are
positively correlated in a major geopolitical event, while Energy and Cyber are
largely independent.

---

### Step 2 — Reinsurance Application

| Line | Structure | Purpose |
|------|-----------|---------|
| PropCat XL | 3-layer XL tower (60M xs 10M) | Catastrophe protection |
| Specialty Casualty | 25% Quota Share | Proportional risk transfer |
| Marine Hull/Cargo | 5M xs 5M XL | Per-risk protection |
| Political Violence | 40% QS + 8M xs 8M XL | Dual protection |
| Energy | 7M xs 7M XL + ASL | Per-risk + aggregate |
| Cyber | 30% Quota Share | Systemic risk cap |

Net losses = Gross losses − RI recoveries.

---

### Step 3 — Capital Allocation (Euler Method at TVaR 99.5%)

Portfolio TVaR at 99.5% (1-in-200 year) is the Lloyd's SCR standard capital requirement.

Euler gradient allocation assigns capital to each line as its conditional expected loss
in the worst 0.5% of scenarios:

> Allocated Capital_i = E[ Net Loss_i | Portfolio Net Loss >= VaR_{99.5%} ]

Allocations sum exactly to portfolio TVaR and reward lines whose losses are low or
diversifying in the tail.

---

### Step 4 — Pricing (Wang Transform — Spectral Risk Measure)

The Wang Transform distorts the loss distribution so that tail-heavy scenarios
receive higher probability weight in pricing:

> g(s) = Φ( Φ⁻¹(s) + λ )

**Lambda calibration:** λ is calibrated on the **net** aggregate loss portfolio
so that the net Wang risk loading equals the target hurdle multiplied by net TVaR:

> Wang E[L_net] − E[L_net] = Hurdle Rate × TVaR_net

The same λ is then applied to **both** gross and net loss vectors per line — λ is
a single company-level risk appetite parameter.

**Hurdle Profit (HP):** For each line, HP = Wang E[L] − E[L].
This is the minimum profit margin the line must earn to compensate for bearing its tail risk.
- HP_net: hurdle on the net (post-RI) loss distribution
- HP_gross: hurdle on the gross (pre-RI) loss distribution

---

### Step 5 — Economic Profit

> EP_net = GWP − Acquisition Costs − Ceded Premium + Ceded Recovery
>          + Investment Income − E[Gross Loss] − HP_net

**Investment income** is computed per LoB using the mean term of claims:
> Investment Income = Investment Yield × Mean Term × E[Loss]

Long-tail lines (e.g. Specialty Casualty at 3.5 years) earn significantly more investment
income than short-tail lines (e.g. PropCat at 0.75 years), reflecting the time reserves
are held before claims are paid. This is computed on both gross and net bases.

This simplifies to: **Net Premium − Acq Costs + Investment Income − E[Net Loss] − HP_net**

Positive EP_net = the line earns above its Wang-implied cost of risk capital.
Negative = it destroys value at current pricing.

### Reserve Risk Loading

The capital model input covers **premium risk only**. To approximate the additional
capital required for **reserve risk** (uncertainty in claims already incurred but not
yet settled), a per-LoB multiplicative loading is applied to TVaR capital:

> TVaR_adjusted = TVaR_premium_risk × Reserve Risk Loading

Lines with longer settlement patterns carry higher reserve risk loadings (e.g.
Specialty Casualty at 1.45× vs PropCat at 1.05×). This adjusted capital enters the
Wang λ calibration target, meaning higher reserve risk → higher λ → higher hurdle
profit required → harder for long-tail lines to be accretive.

**Primary decision metric: EPR (Economic Profit Ratio)** = EP_net ÷ HP_net
- EPR > 1: value-creating (earns above the cost of risk capital)
- EPR = 1: exactly earning the hurdle — EP = 0
- EPR < 1: value-dilutive (earning less than the Wang-implied cost of risk)
- EPR < 0: value-destructive (EP is negative)

**ROAC (Return on Allocated Capital)** = (EP + HP) ÷ TVaR
- This adds the hurdle profit back to EP before dividing by capital, giving a true
  return on capital. A line earning exactly its cost of capital shows ROAC = hurdle rate
  and EP = 0 (which is the correct identity).
- ROAC is shown for executive reporting convention but is **not** the primary pricing metric.
  EPR is preferred because it directly answers "how much value is being created per unit
  of risk charge?"

**RI Efficiency ratio: Ceded EP / Ceded HP**
- Ceded HP = HP_gross − HP_net (always positive — RI always releases some tail risk)
- Ceded EP = EP_gross − EP_net (positive if RI hurts EP; negative if RI is very efficient)
- Ratio < 1: RI is efficient (releasing more capital than it costs in EP)
- Ratio > 1: RI is expensive relative to the capital it releases
- Negative ratio: RI is so efficient it *improves* EP while releasing capital (best case)

---

### Step 6 — GWP Optimisation (Four Scenarios)

Four scenarios show what optimal GWP mix looks like under different constraints and objectives.
All assume additional GWP has the same risk profile as the current book.

- **Scenario A (Max ROAC):** Maximise EP subject to **fixed TVaR** — the board capital question.
- **Scenario B (Max EP, Fixed HP):** Maximise EP subject to **fixed HP** — the risk appetite question.
- **Scenario C (Min Capital):** Minimise TVaR subject to **fixed GWP** — the capital efficiency question.
- **Scenario D (Max RI Efficiency):** Minimise Ceded EP / Ceded HP subject to **fixed GWP**.
- A–C are linear programs solved via `scipy.optimize.linprog` (HiGHS). D uses `minimize` (SLSQP).
- All scenarios: per-LoB GWP bounds = [50%, 200%] of current.

---

### Challenge-and-Defend Loops

Three adversarial review stages were completed:

1. **Peer Review (Risk Model):** Challenger tested Wang Transform, zero-inflation handling,
   and confidence level sensitivity. Risk Modeller revised to v2.
2. **RI Efficiency Challenge:** Capital Allocator reviewed whether each RI structure
   justifies its cost from a capital perspective.
3. **Strategy Consistency Check:** Lead Actuary verified GWP targets are consistent
   with pricing framework and traffic light signals.
    """)

# ═══════════════════════════════════════════════════════════════════════
# TAB 8 — AUDIT TRAIL
# ═══════════════════════════════════════════════════════════════════════
with tab_audit:
    st.subheader("Derivation Trail — Per-Line Source and Audit")

    st.markdown("""
    For each line: the pricing metrics that drove the recommendation, which scenario
    produced the GWP target, and a plain-English explanation for executives.
    """)

    try:
        _scenarios_available = scenarios
    except NameError:
        _scenarios_available = {}
    if not traffic.empty and not accretion.empty and _scenarios_available:
        lob_audit = st.selectbox("Select Line for Audit Trail", LOBS, key="audit_lob")

        trow = traffic[traffic["LoB"] == lob_audit]
        arow = accretion[accretion["LoB"] == lob_audit]

        if not trow.empty:
            t = trow.iloc[0]
            a = arow.iloc[0].to_dict() if not arow.empty else {}

            st.markdown(f"### {lob_audit}")
            c1, c2 = st.columns(2)

            with c1:
                st.markdown("**Pricing Metrics**")
                # Support both old and new column names
                _ep = a.get('EP_Net', a.get('Net_Profit', 0))
                _hp = a.get('HP_Net', a.get('Cost_of_Capital', 0))
                _cap = a.get('TVaRCapital', a.get('Allocated_Capital', 0))
                _el_net = a.get('EL_Net', a.get('Net_Mean_Loss', 0))
                _ri_eff = a.get('RI_Efficiency', '')
                # Compute corrected metrics from raw values
                _epr  = _ep / _hp if abs(_hp) > 1e-6 else float('nan')
                _roac = (_ep + _hp) / _cap if abs(_cap) > 1e-6 else float('nan')
                audit_lines = [
                    f"<b>GWP:</b> {fmt_k(a.get('GWP', 0))}",
                    f"<b>Economic Profit (EP):</b> {fmt_k(_ep)}",
                    f"<b>Hurdle Profit (HP):</b> {fmt_k(_hp)}",
                    f"<b>EPR (EP / HP):</b> {_epr:.2f}" if not pd.isna(_epr) else "<b>EPR:</b> N/A",
                    f"<b>E[Net Loss]:</b> {fmt_k(_el_net)}",
                    f"<b>TVaR Capital:</b> {fmt_k(_cap)}",
                    f"<b>ROAC (info):</b> {_roac:.1%}" if not pd.isna(_roac) else "<b>ROAC:</b> N/A",
                ]
                if _ri_eff:
                    audit_lines.append(f"<b>RI Efficiency:</b> {float(_ri_eff):.2f}")
                st.markdown(
                    f"<div class='audit-box'>{'<br/>'.join(audit_lines)}</div>",
                    unsafe_allow_html=True,
                )

            with c2:
                st.markdown("**Strategic Recommendation**")
                flag  = str(t.get("Flag", ""))
                emoji = traffic_emoji(flag)
                color = traffic_color(flag)
                st.markdown(f"""
<div style='background:{color}20;border-left:4px solid {color};padding:12px;border-radius:4px'>
<b>Signal:</b> {emoji} {flag}<br/><br/>
<b>Key Action:</b> {t.get('Key_Action', '')}<br/><br/>
<b>Reasoning:</b> {t.get('Reasoning', '')}<br/><br/>
<b>First Remediation:</b> {t.get('First_Remediation', '')}<br/><br/>
<b>Best RI Move:</b> {t.get('Best_RI', '')}
</div>
                """, unsafe_allow_html=True)

            st.markdown("**GWP Targets Across Scenarios**")
            scenario_rows = []
            for key, label in [("A", "Max ROAC"), ("B", "Max EP (Fixed HP)"),
                                ("C", "Min Capital"), ("D", "Max RI Efficiency")]:
                s_row = scenarios[key][scenarios[key]["LoB"] == lob_audit]
                if not s_row.empty:
                    r = s_row.iloc[0]
                    scenario_rows.append({
                        "Scenario": f"{key}: {label}",
                        "Current GWP": fmt_k(r["Current_GWP"]),
                        "Target GWP": fmt_k(r["New_GWP"]),
                        "Change": f"{r['Change_%']:+.1f}%",
                        "Constraint": ("Fixed TVaR" if key == "A"
                                       else "Fixed HP" if key == "B"
                                       else "Fixed GWP"),
                    })
            if scenario_rows:
                st.dataframe(pd.DataFrame(scenario_rows), use_container_width=True, hide_index=True)

                st.markdown(f"""
<div class='audit-box'>
<b>How to explain to executives:</b><br/>
The GWP target for <b>{lob_audit}</b> differs by scenario because each holds a different
variable fixed. Scenario A fixes committed capital (TVaR) and maximises return.
Scenario B fixes the risk charge (HP) and maximises EP. Scenario C fixes the GWP plan
and minimises capital required. Scenario D fixes GWP and makes RI work hardest.
The traffic light signal ({flag.strip()})
is based on Scenario A (primary ROAC objective), cross-checked for RI and pricing consistency.
</div>
                """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Challenge and Defence Files")

    challenge_files = {
        "RI Efficiency Challenge": "challenge_ri_efficiency.md",
        "Strategy Consistency Check": "challenge_strategic_targets.md",
        "Peer Review V1": "peer_review_v1.md",
        "Peer Review V2 Verification": "peer_review_v2_verification.md",
    }
    for label, fname in challenge_files.items():
        p = os.path.join(WS, fname)
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="replace") as f:
                txt = f.read()
            with st.expander(f"{label}"):
                st.markdown(txt[:3000] + (
                    "\n\n*[truncated — open the file directly for the full version]*"
                    if len(txt) > 3000 else ""))
        else:
            st.caption(f"  {label}: file not present ({fname})")
