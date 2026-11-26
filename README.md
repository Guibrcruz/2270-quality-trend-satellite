# Quality Trend Satellite — 2270 Streamlit App

An interactive version of the group's quality-trend strategy:

> Hold the Invesco S&P 500 Quality ETF (SPHQ) when its month-end close is above its
> 200-day simple moving average; otherwise hold 3-month T-bills. Rebalance monthly,
> execute at the open two trading days after the signal, and charge 10 bps per side.

The app imports the same `portfolio.py` calculation layer used by the submitted notebook,
so the default scenario reproduces the notebook's headline results.

## Live app

`[STREAMLIT APP URL]`

## What you can change

- Trend window: 100–300 trading days (default 200)
- Transaction cost: 0–30 bps per side (default 10)
- Execution lag: 1–3 trading days (default 2)
- Initial capital: $10,000–$1,000,000
- Policy benchmark equity weight: 10–90% (default 50%)

Every change recalculates the equity curve, drawdown, metrics, trade log and cost
sensitivity from Yahoo Finance data. The **Reset to notebook defaults** button restores
the submitted baseline.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open `http://localhost:8501`.

## Data and methodology

- Data: Yahoo Finance adjusted OHLC via `yfinance`; no data file is stored in the repo.
- Sample: 1 January 2010 to 31 December 2025, with a warm-up from 1 January 2008.
- Costs: 10 bps per side by default; the policy benchmark is charged 10 bps at its monthly rebalance.
- Annualization: 252 trading days. Beta is a daily regression slope and is **not** annualized.
- Alpha is the annualized regression intercept; the information ratio is annualized active
  return divided by annualized tracking error.

## Limitations

In-sample rule selection, survivorship bias from using a current ETF, one factor and one
country, no taxes, no fund tracking error, and a favourable 2010–2025 sample. Alpha's
t-statistic is about 1.62, so it is not statistically significant. This is an academic
exercise, not investment advice.

## Group

- Moodle group: `[GROUP NAME]`
- Members: `[MEMBER NAMES AND STUDENT IDS]`
- Submission: 4 December 2026

## Generative-AI disclosure

Built with DeepSeek V4.1 Flash via OpenCode. The group formulated the mandate and approved
the rule; all code was run and checked by the group. No data or results were fabricated.
