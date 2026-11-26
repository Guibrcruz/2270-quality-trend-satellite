# SPHQ Studio — 2270 Streamlit App

An interactive version of the group's quality-trend strategy:

> Hold the Invesco S&P 500 Quality ETF (SPHQ) when its month-end close is above its
> 200-day simple moving average; otherwise hold 3-month T-bills. Rebalance monthly,
> execute at the open two trading days after the signal, and charge 10 bps per side.

The app imports the same `portfolio.py` calculation layer used by the submitted notebook,
so the default scenario reproduces the notebook's headline results.

## Live app

https://2270-quality-trend-satellite.streamlit.app

## Group

- Moodle group: **Group CD**
- Members: Gabriel Conceição, Guilherme Cruz, Joana Alves, Francisco Correia,
  Luís Moreira, Miguel Monteiro
- Submission: 4 December 2026

## Chart views

The dark chart panel uses TradingView Lightweight Charts and has five views:

- **Growth** — quality trend, SPY and the 50/50 SPY/T-bill policy mix, all starting at 1x.
- **Price & trades** — SPHQ candlesticks, the 200-day SMA and every executed BUY/SELL
  arrow. Hover a trade date to see its execution price.
- **Drawdown** — peak-to-trough decline for the strategy, SPY and the policy mix.
- **Exposure** — share of the portfolio invested in SPHQ over time.
- **Rolling 24m** — overlapping 24-month returns, with the strategy and SPY.

The date buttons switch between MAX, 5Y, 3Y and 1Y. The LOG button toggles the growth
chart between logarithmic and linear scales.

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

Then open `http://localhost:8501`. The chart component is vendored in `chart_component/`,
so it does not load Lightweight Charts from a CDN.

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

## Generative-AI disclosure

Built with DeepSeek V4.1 Flash via OpenCode. The group formulated the mandate and the original
Bollinger Bands idea; the assistant tested it, showed that it did not survive a fair comparison,
and proposed the SPHQ quality-trend alternative. The group reviewed the evidence and approved
the pivot and the final rule. All code was run and checked by the group. No data or results were
fabricated. The group should confirm that AI-assisted strategy selection is permitted under the
course AI policy.
