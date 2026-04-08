# PORTFOLIO PRICING ENGINE
## Summary for Management
### The Fidelis Partnership

**Date:** 2024  
**Prepared by:** Lead Actuary

---

## What We Built

We created a model that answers a critical business question: **Which of our six insurance lines are profitable enough to justify the capital they require?**

The model simulates 100,000 possible loss scenarios, calculates the capital needed to meet Lloyd's requirements (1-in-200 year standard), accounts for reinsurance protection, and computes the return on capital for each line of business.

---

## What We Found

### The Bottom Line: Four Lines Make Money, Two Lines Lose Money

**Making Money (28-60% return on capital):**
- Specialty Casualty: 36.5% return - best performer
- Cyber: 60.0% return - highest return but carries hidden risks
- Marine Hull & Cargo: 28.1% return - solid and stable
- Energy: 28.2% return - solid and stable

**Losing Money (only 1-3% return on capital):**
- Property Cat XL: 2.6% return - needs £396 million capital for £25 million premium
- Political Violence: 1.3% return - needs £326 million capital for £12 million premium

### Why the Difference?

The profitable lines need modest capital relative to their premiums. Specialty Casualty, for example, needs only 55p of capital for every £1 of premium. So even after paying claims, reinsurance, and expenses, there's substantial profit relative to capital employed.

The unprofitable lines need enormous capital because catastrophic events—though rare—can be devastating. Political Violence needs £27 of capital for every £1 of premium. Even with decent underwriting margins, the profits can't justify tying up hundreds of millions in capital.

**Simple Example - Political Violence:**
- Premium written: £12 million
- Expected profit after claims and reinsurance: £4 million
- Capital required for 1-in-200 year protection: £326 million
- Return: £4 million / £326 million = **1.3%**
- Government bonds yield 4-5% with zero risk

We're taking significant insurance risk for less return than a risk-free investment.

---

## What We Should Do

### Immediate Actions (Next 6 Months)

**1. Exit Political Violence** - High Priority

Stop writing new business and allow existing policies to expire. This frees £326 million in capital.

Why? We're earning 1.3% on capital that could earn 5% risk-free. The opportunity cost is approximately £12 million per year.

**2. Reduce Property Cat by 40%** - High Priority

Cut exposure from £25 million to £15 million. Renegotiate reinsurance terms (current structure appears 10-15% too expensive).

Why? PropCat has strategic value (Lloyd's requires catastrophe capacity) but current scale destroys value. Smaller footprint maintains the franchise while improving returns.

**3. Fix Reinsurance Gaps** - Medium Priority

- Marine: Current XL runs out too often—replace with 30% quota share
- Energy: Move attachment point higher to avoid working-layer pricing
- Cost: Budget £2-3 million additional, but prevents £20-30 million tail exposures

### Growth Opportunities (Next 12 Months)

**1. Grow Cyber to £15 million** - BUT add protection first

Cyber earns 60% return—highest in the portfolio. However, current protection doesn't cover systemic events (major cloud outage, ransomware pandemic). 

Before growing:
- Add catastrophic event reinsurance (~£3.7 million additional cost)
- This protects against scenarios where many clients are affected simultaneously

**2. Grow Specialty Casualty to £30 million**

This is our most stable, predictable line. Low capital requirements, excellent returns. Should be the "ballast" of the portfolio.

---

## The Numbers

### If We Implement All Recommendations:

| Metric | Today | After Changes | Improvement |
|--------|-------|---------------|-------------|
| Total Premium | £98 million | £93 million | -5% (smaller but better) |
| Return on Capital | 8.4% | 25-30% | +17-22 points |
| Capital Freed | — | £486 million | Available for growth |
| Annual Value | -£63 million | +£10-15 million | £73-78 million swing |

### Where Freed Capital Could Go:

£486 million of freed capital could support:
- £2.4 billion of additional Specialty Casualty at 36% returns
- Or £600 million of Cyber at 30% returns (after systemic protection)
- Or combination of both

---

## Key Risks and Uncertainties

### What We're Confident About

The four profitable lines are genuinely accretive—this finding is robust across different assumptions.

The two unprofitable lines are clearly non-accretive—this is not a marginal call.

The model has been independently peer-reviewed and all calculations verified.

### What We're Less Certain About

**Tail correlation may be understated by up to 33%.** If true, we'd need £350 million more capital portfolio-wide, and Property Cat would look even worse.

**Cyber systemic risk is difficult to model.** A major cloud provider outage could cause £500 million in losses across the portfolio. Our model doesn't fully capture this. That's why we must add catastrophic protection before growing Cyber.

**Market conditions change.** This analysis uses current pricing. In a soft market with 20% lower prices, all returns fall proportionally.

### What Could Go Wrong

**Worst case:** We grow Cyber without adding catastrophic protection, and a major cloud outage occurs. Net losses could exceed £350 million—potentially capital-threatening.

**How we avoid this:** Don't grow Cyber until catastrophe reinsurance is in place. The £3.7 million cost is insurance against catastrophic downside.

---

## Why This Matters

Every £100 million locked up in low-returning business is £100 million we can't deploy elsewhere.

Political Violence earns 1.3% on £326 million = £4 million profit.

That same £326 million in Specialty Casualty could support £1.6 billion of premium earning 36% = £115 million profit.

**The opportunity cost is over £110 million per year.**

Even accounting for transition costs and execution risk, this is one of the clearest capital reallocation opportunities available to the firm.

---

## How the Model Was Validated

This model went through rigorous independent peer review. Key challenges addressed:

1. **Framework choice validated** - We tested seven different risk measurement approaches. Only TVaR@99.5% produces capital estimates aligned with Lloyd's requirements.

2. **All calculations verified** - The model was executed and independently checked. Capital allocations sum perfectly to portfolio total (zero error).

3. **Stress scenarios tested** - We examined what happens if correlations are higher than assumed (they likely are), and if Lloyd's changes confidence requirements.

4. **Known limitations documented** - The model has weaknesses (tail correlation, cyber systemic risk, parameter uncertainty) which are clearly disclosed with recommended mitigations.

This peer review process added substantial value. Without it, we would have missed approximately £350 million of potential capital underestimation due to tail correlation effects.

---

## Recommended Timeline

### Month 1:
- Present findings to Board
- Obtain approval to exit Political Violence
- Communicate to underwriters and brokers

### Month 2-3:
- Non-renew Political Violence policies
- Negotiate improved reinsurance terms
- Negotiate Cyber catastrophe protection

### Month 4-6:
- Begin reducing PropCat exposure at renewal
- Begin growing Cyber (once protection in place)
- Begin growing Specialty Casualty

### Month 7-12:
- Monitor actual results vs. model predictions
- Quarterly model recalibration
- Prepare for version 2 enhancements

---

## One-Slide Summary

**FINDING:** Four lines earn 28-60% on capital. Two lines earn 1-3% and consume £722 million of capital.

**RECOMMENDATION:** Exit Political Violence, reduce Property Cat. Grow Specialty Casualty and Cyber (with protection).

**IMPACT:** Free £486 million capital, improve returns from 8% to 25-30%, create £73-78 million additional annual value.

**RISK:** Must add Cyber catastrophic protection before growing—systemic event could cause £350 million loss.

**TIMELINE:** 12 months to full implementation.

---

## Questions?

For technical details, see the Full Technical Report.

For implementation planning, contact the Lead Actuary.

---

**Recommendation: APPROVE portfolio rebalancing as outlined above.**

---

*End of Management Summary*
