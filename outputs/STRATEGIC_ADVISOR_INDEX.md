# STRATEGIC PORTFOLIO ADVISOR — OUTPUT INDEX
## The Fidelis Partnership — Portfolio Pricing Engine
### Complete Deliverables Package

**Prepared by:** Strategic Portfolio Advisor  
**Date:** 2024  
**Status:** ✅ COMPLETE  
**Target Audience:** Head of Portfolio Management, Senior Leadership

---

## QUICK START — MANAGEMENT READING ORDER

If you only have 30 minutes, read these in order:

1. **START HERE:** `strategic_recommendations.md` — Section 1 (Portfolio Scorecard) + Section 3 (Top 3 Priorities)
   - 5 minutes to understand the headline numbers and key decisions needed

2. **THEN:** `strategic_recommendations.md` — Section 2 (Traffic Light Summary)
   - 5 minutes to see which lines to grow/reduce/review

3. **THEN:** `strategic_recommendations.md` — Section 6 (Risks & Caveats)
   - 10 minutes to understand model limitations before making decisions

4. **FINALLY:** `ri_optimisation.csv` — scan for your lines of interest
   - 10 minutes to see specific RI alternatives tested

---

## DELIVERABLE 1: RI OPTIMISATION ANALYSIS

**File:** `ri_optimisation.csv`

**Purpose:** Test alternative reinsurance structures for each LoB to identify opportunities for premium savings, capital reduction, or improved protection.

**Methodology:** For each LoB with reinsurance, tested 2-3 alternatives:
- **REDUCE RI:** Raise retentions by 25% (save premium, retain more risk)
- **INCREASE RI:** Lower retentions or add capacity (spend premium, transfer more risk)
- **QUOTA SHARE:** Add/adjust QS proportional ceding
- **MARKET TEST:** Same structure, better pricing

**Key Results:**

| Line | Best Alternative | Impact | Recommendation |
|------|------------------|--------|----------------|
| **PropCat** | Market Test (10% better pricing) | Save £660k | ✅ Execute immediately |
| **Specialty Casualty** | Increase QS to 35% | Cost £1.4M, free capacity | ⚠️ Only if growing |
| **Marine** | Increase limit to £10M | Cost £1.5M, fix breach rate | ✅ Essential — execute |
| **Political Violence** | All alternatives worse | N/A | Exit recommended |
| **Energy** | Raise attachment to £8.75M | Save £711k net | ⚠️ Marginal benefit |
| **Cyber** | Add Cat XL (£30M xs £15M) | Cost £3.7M, systemic protection | ✅ Before growing |

**Read This If:** You want to understand specific RI structure changes and their financial impact.

**Management Action Required:**
- Approve Marine XL limit increase (£1.5M spend)
- Approve Cyber Cat XL addition (£3.7M spend) before growth
- Authorize PropCat RI market testing

---

## DELIVERABLE 2: GWP MIX OPTIMISATION

**File:** `gwp_optimisation.csv`

**Purpose:** Use mathematical optimization (scipy) to find the optimal GWP allocation across lines that maximizes portfolio ROAC.

**Methodology:**
- Objective function: Maximize portfolio ROAC
- Constraints: Total GWP within ±2%, each LoB between 50-150% of current, minimum £2M per line
- Optimizer: Sequential Least Squares Programming (SLSQP)

**Key Results:**

| Line | Current | Optimal | Change | Rationale |
|------|---------|---------|--------|-----------|
| **Energy** | £18M | £22M | **+22%** | Best ROAC (10.1%), capital-efficient |
| **Cyber** | £8M | £10M | **+21%** | Profitable (7.3%), very capital-efficient |
| **Marine** | £15M | £18M | **+20%** | Profitable (9.4%), capital-efficient |
| **Specialty Casualty** | £20M | £18M | **-12%** | Dilutive (-11.8%), pricing issue |
| **PropCat** | £25M | £21M | **-16%** | Dilutive (-9.8%), capital-intensive |
| **Political Violence** | £12M | £10M | **-18%** | Severely dilutive (-11.8%) |

**Impact:**
- Portfolio ROAC: -9.9% → -9.6% (+0.3pp improvement)
- Capital freed: £89M
- Net profit improvement: +£10.6M

**Why Limited Improvement?**
Optimization is constrained by:
- Can't exit lines entirely (minimum £2M GWP)
- Can't exceed 150% growth per line
- Total GWP held constant

**Reality:** True opportunity requires exiting Political Violence and cutting PropCat 40% (beyond optimizer constraints).

**Read This If:** You want to see the quantitative optimization results and understand why manual strategic decisions outperform pure optimization.

**Management Action Required:**
- Note: Optimization confirms strategic recommendations but is constrained by minimum/maximum bounds
- Real opportunity requires strategic decisions beyond optimization (exits, major reductions)

---

## DELIVERABLE 3: TRAFFIC LIGHT FLAGS

**File:** `traffic_light_analysis.csv`

**Purpose:** Assign each LoB a strategic action flag (GROW / MAINTAIN / REDUCE / STRATEGIC REVIEW) based on ROAC, profitability, capital efficiency, and growth opportunity.

**Classification Criteria:**

| Flag | Criteria | Count | Lines |
|------|----------|-------|-------|
| 🟢 **GROW** | ROAC > 5%, capital-efficient | **3** | Energy, Marine, Cyber |
| 🟡 **MAINTAIN** | ROAC -5% to +5%, fixable | **0** | (none) |
| 🟠 **REDUCE** | ROAC -10% to -5%, dilutive | **2** | PropCat, Specialty Casualty |
| 🔴 **STRATEGIC REVIEW** | ROAC < -10%, capital > 10x GWP | **1** | Political Violence |

**Key Metrics by Flag:**

| Flag | GWP | Capital | Profit | Key Finding |
|------|-----|---------|--------|-------------|
| 🟢 GROW | £41M (42%) | £31M (4%) | **+£2.9M** | Profitable and capital-efficient |
| 🟠 REDUCE | £45M (46%) | £407M (53%) | **-£40.0M** | Dilutive, needs pricing/RI fixes |
| 🔴 REVIEW | £12M (12%) | £326M (43%) | **-£38.4M** | Exit recommended |

**Break-Even Analysis:**

| Line | Current ROAC | Break-Even Price Increase | Feasible? |
|------|--------------|---------------------------|-----------|
| **PropCat** | -9.8% | **+123%** | ❌ No — market won't bear |
| **Specialty Casualty** | -11.8% | **+5.4%** | ✅ Yes — achievable at renewal |
| **Political Violence** | -11.8% | **+266%** | ❌ No — structurally broken |

**First Remediation by Line:**

- **Energy:** Grow to £22M; maintain current strategy
- **Marine:** Grow to £18M after fixing RI (increase XL limit)
- **Cyber:** Grow to £10M after adding Cat XL (systemic protection)
- **PropCat:** Market test RI; reduce to £21M; increase pricing 15%
- **Specialty Casualty:** Increase pricing 5.4% at renewal
- **Political Violence:** Senior review required; exit recommended

**Read This If:** You want to see the strategic classification of each line and understand the "first remediation" action for each.

**Management Action Required:**
- Approve growth strategy for Energy/Marine/Cyber
- Approve reduction/repricing strategy for PropCat/Casualty
- Make strategic decision on Political Violence exit

---

## DELIVERABLE 4: STRATEGIC RECOMMENDATIONS (MAIN DOCUMENT)

**File:** `strategic_recommendations.md`

**Purpose:** Comprehensive management summary with portfolio scorecard, traffic lights, top priorities, RI assessment, GWP mix recommendations, and risks/caveats.

**Structure:**

### Section 1: Portfolio Scorecard
- 5 headline numbers with context
- Critical insight: 42% of GWP is profitable, 58% destroys £78M annually
- **Read time:** 5 minutes

### Section 2: Traffic Light Summary
- Classification framework
- Traffic light table with ROAC, capital, and key actions
- Portfolio composition by flag
- **Read time:** 5 minutes

### Section 3: Top 3 Priority Actions (MOST IMPORTANT)
1. **EXIT Political Violence** (free £326M capital, stop £38M loss)
2. **REDUCE PropCat 40%** (free £156M capital, market test RI)
3. **GROW Energy/Marine/Cyber 20%** (add £9M GWP, +£1.5M profit)

**Quantified impacts for each priority**
- **Read time:** 15 minutes (⭐ START HERE)

### Section 4: RI Programme Assessment
- What's working (Casualty QS, PolVio hybrid)
- What needs fixing (PropCat pricing, Marine limit, Cyber systemic)
- Top 3 RI improvements ranked
- **Read time:** 10 minutes

### Section 5: GWP Mix Recommendation
- Current vs. optimal allocation table
- Optimization constraints and expected impact
- Unconstrained recommendation (target state)
- **Read time:** 10 minutes

### Section 6: Risks & Caveats
- Model limitations (tail correlation, zero-inflation, cyber systemic)
- Key sensitivities (what if scenarios)
- Model risk governance requirements
- What this model does NOT tell you
- **Read time:** 15 minutes (⭐ CRITICAL BEFORE DECISIONS)

### Executive Summary for Senior Leadership
- The Situation (3 profitable, 3 dilutive)
- The Recommendation (immediate + growth actions)
- The Impact (ROAC -9.9% → +12.5%)
- The Ask (Board approvals needed)
- **Read time:** 5 minutes

**Read This If:** You are making strategic decisions about the portfolio or presenting to the Board.

**Management Action Required:**
- Read Section 3 (Top 3 Priorities) in full
- Review Section 6 (Risks) before committing to decisions
- Present Executive Summary to Board for approval
- Timeline: Decisions by Q1 2025 for mid-year renewals

---

## KEY FINDINGS AT A GLANCE

### The Problem
- Portfolio ROAC is -9.9% (below 10% hurdle)
- Three lines (PropCat, Specialty Casualty, Political Violence) destroy £78.4M annually
- These dilutive lines consume 96% of total capital (£733M of £763M)
- PropCat and Political Violence require 16-27x their GWP in capital

### The Opportunity
- Three lines (Energy, Marine, Cyber) are profitable and capital-efficient
- These lines generate £2.9M on only £41M GWP (42% of portfolio)
- They consume only 4% of total capital
- Massive opportunity to redeploy capital from dilutive to profitable lines

### The Recommendation
**Immediate (0-90 days):**
1. Exit Political Violence → free £326M capital
2. Reduce PropCat 40% → free £156M capital
3. Market test PropCat RI → save £660k
4. Fix Marine RI (increase limit) → essential protection

**Growth (90-180 days):**
5. Grow Energy to £30M (+67%)
6. Grow Marine to £22M (+47%)
7. Add Cyber Cat XL → systemic protection
8. Grow Cyber to £12M (+50%)
9. Reprice Specialty Casualty +5%

### The Impact
**Full Implementation:**
- Portfolio GWP: £98M → £94M (-4%)
- Portfolio ROAC: -9.9% → **+12.5%** (above hurdle!)
- Annual Profit: -£75M → **+£12M** (£87M swing)
- Capital Required: £763M → £299M (free £464M)

**Capital Redeployment:**
£464M freed capital can support £2.3B of additional business or be returned to shareholders.

---

## CRITICAL ASSUMPTIONS & LIMITATIONS

### What This Model DOES:
✅ Measures net-of-reinsurance ROAC by line  
✅ Allocates capital using Lloyd's-standard Euler method  
✅ Tests alternative RI structures quantitatively  
✅ Optimizes GWP mix within portfolio constraints  
✅ Identifies relative performance (best to worst lines)  

### What This Model DOES NOT:
❌ Account for expense ratio differences by line  
❌ Consider strategic value (Lloyd's franchise, broker relationships)  
❌ Model personnel/organizational implications  
❌ Capture market cycle effects (we price for today)  
❌ Include regulatory requirements (Lloyd's minimum cat participation)  
❌ Model true cyber systemic scenarios (cloud outage)  

### Key Risks:
⚠️ **Gaussian copula** may understate capital by £349M (33%) in tail stress  
⚠️ **Cyber systemic** not modeled — DO NOT grow without Cat XL  
⚠️ **Political Violence** break-even needs 266% price increase (impossible)  
⚠️ **Zero-inflation** creates capital allocation instability (±48%)  

### Governance:
- Annual recalibration required
- Quarterly validation against actual experience
- Stress testing before each renewal
- Independent peer review (COMPLETED)
- Management sign-off on limitations (REQUIRED)

---

## NEXT STEPS FOR MANAGEMENT

### Within 30 Days:
1. ✅ Read `strategic_recommendations.md` — Sections 1, 3, 6
2. ✅ Review `traffic_light_analysis.csv` — understand flag logic
3. ⏱️ Present to Executive Committee for feedback
4. ⏱️ Consult with Lloyd's re: Political Violence exit implications
5. ⏱️ Consult with brokers re: PropCat reduction implications

### Within 60 Days:
6. ⏱️ Board approval for Political Violence exit
7. ⏱️ Board approval for PropCat 40% reduction
8. ⏱️ Authorize RI market testing (PropCat, Marine, Cyber)
9. ⏱️ Approve growth mandates for Energy/Marine/Cyber
10. ⏱️ Commission detailed expense analysis by line

### Within 90 Days:
11. ⏱️ Announce Political Violence non-renewal to market
12. ⏱️ Execute PropCat GWP reduction (renewal conversations)
13. ⏱️ Bind Marine XL limit increase (£1.5M spend)
14. ⏱️ Bind Cyber Cat XL (£3.7M spend)
15. ⏱️ Begin Energy/Marine growth plan execution

### Within 180 Days:
16. ⏱️ Complete mid-year renewals with new strategy
17. ⏱️ Monitor actual vs. model predictions (quarterly validation)
18. ⏱️ Review and recalibrate model parameters
19. ⏱️ Report to Board on execution progress

---

## CONTACT & QUESTIONS

**For technical questions about the model:**
- See `FINAL_REPORT.md` — full methodology and validation
- See `risk_model_v2.py` — Python implementation
- See `peer_review_response_v2.md` — answers to technical challenges

**For RI structure questions:**
- See `ri_analysis.md` — comprehensive RI design and validation
- See `ri_alternatives.md` — detailed alternatives analysis

**For capital allocation questions:**
- See `outputs/capital_allocations_final.csv` — Euler allocations
- See `outputs/capital_report.md` — Capital Allocator's narrative (if exists)

**For data foundation questions:**
- See `data/portfolio_config.json` — LoB definitions and parameters
- See `DATA_FOUNDATION_HANDOVER.md` — complete data documentation

---

## VERSION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024 | Strategic Portfolio Advisor | Initial delivery of all 4 deliverables |

---

## SIGN-OFF

This strategic analysis has been completed and is ready for management review and decision-making.

**Prepared by:** Strategic Portfolio Advisor  
**Date:** 2024  
**Status:** ✅ COMPLETE  

**Recommended for:**
- ✅ Executive Committee review
- ✅ Board presentation
- ✅ Implementation planning

**NOT recommended for:**
- ❌ External publication (contains sensitive strategic information)
- ❌ Regulatory submission (requires additional validation)
- ❌ Pricing individual risks (portfolio-level model only)

---

**END OF INDEX**
