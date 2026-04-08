# Deploying the Portfolio Pricing Dashboard to Streamlit Community Cloud

## What you need
- A **GitHub account** (free) — [github.com](https://github.com)
- A **Streamlit Community Cloud account** (free) — [share.streamlit.io](https://share.streamlit.io)

## Step 1 — Push to GitHub

1. Create a new repository on GitHub (e.g. `portfolio-pricing-dashboard`). Set it to **Public** (required for the free Streamlit tier).

2. Open a terminal in this folder (`03_Latest_Run`) and run:

```bash
git init
git add dashboard.py requirements.txt .streamlit/config.toml .gitignore
git add outputs/ data/ confidence_sensitivity.csv tail_correlation_stress_test.csv
git add ri_efficiency_challenge_metrics.csv ri_efficiency_challenge_verdicts.csv
git commit -m "Initial commit — Portfolio Pricing Dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/portfolio-pricing-dashboard.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

## Step 2 — Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **"New app"**.
3. Select your repository (`portfolio-pricing-dashboard`), branch (`main`), and main file (`dashboard.py`).
4. Click **"Deploy"**.

Streamlit will install the dependencies from `requirements.txt` and launch the app. After a minute or two you'll get a public URL like:

```
https://your-username-portfolio-pricing-dashboard-dashboard-abc123.streamlit.app
```

Share that link with anyone — they can view and interact with the dashboard in their browser.

## Updating the dashboard

Any time you push changes to the `main` branch on GitHub, Streamlit Cloud automatically redeploys. Just:

```bash
git add -A
git commit -m "Update dashboard"
git push
```

## File structure required

```
portfolio-pricing-dashboard/
├── dashboard.py                          # Main Streamlit app
├── requirements.txt                      # Python dependencies
├── .streamlit/config.toml                # Theme configuration
├── .gitignore
├── confidence_sensitivity.csv
├── tail_correlation_stress_test.csv
├── ri_efficiency_challenge_metrics.csv
├── ri_efficiency_challenge_verdicts.csv
├── data/
│   └── portfolio_config.json
└── outputs/
    ├── accretion_analysis_final.csv
    ├── traffic_light_analysis.csv
    ├── gwp_optimisation.csv
    ├── capital_allocation.csv
    └── ri_optimisation.csv
```

## Notes

- The free tier has a resource limit (1GB RAM, 1 CPU). This dashboard is well within those limits.
- If the app goes unused for a few days, Streamlit may put it to sleep. Visiting the URL wakes it up in ~30 seconds.
- To make the repo private (and still deploy), you'd need Streamlit's paid tier or self-host on a cloud provider.
