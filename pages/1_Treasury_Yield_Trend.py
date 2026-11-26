import pandas as pd
import streamlit as st

import portfolio as pf


@st.cache_data(ttl=3600, show_spinner="Downloading ETF prices and Treasury yields")
def load_inputs() -> tuple[pd.DataFrame, pd.Series]:
    return pf.download_yield_trend_inputs()


st.set_page_config(page_title="Treasury Yield Trend | 2270", layout="wide")
st.title("Treasury Yield Trend")
st.caption("2016–2025 · SPY, RSP, SPHQ and BND · Trades at the second U.S. trading close after month-end")

baseline = pf.YIELD_TREND_BASELINE
equity_splits = [30, 70]
equity_tilts = ["SPHQ", "RSP"]
with st.sidebar:
    st.header("Allocation rule")
    equity_if_falling = st.selectbox(
        "Equity / bond split when yields fall",
        equity_splits,
        index=equity_splits.index(round(baseline["equity_if_falling"] * 100)),
        format_func=lambda equity: f"{equity}% / {100 - equity}%",
        help="When yields rise, the split reverses.",
    )
    second_if_falling = st.selectbox(
        "Second-ranked ETF when yields fall",
        equity_tilts,
        index=equity_tilts.index(baseline["second_if_falling"]),
        help="SPY ranks first when yields fall.",
    )
    first_if_rising = st.selectbox(
        "First-ranked ETF when yields rise",
        equity_tilts,
        index=equity_tilts.index(baseline["first_if_rising"]),
        help="SPY ranks third when yields rise.",
    )
    lookback_months = st.slider("Yield-change lookback (months)", 1, 12, baseline["lookback_months"])
    cost_bps = st.slider("Transaction cost (bps per side)", 0, 30, int(baseline["cost_bps"]))

try:
    close, monthly_yield = load_inputs()
    result = pf.run_yield_trend_scenario(
        close,
        monthly_yield,
        equity_if_falling=equity_if_falling / 100,
        second_if_falling=second_if_falling,
        first_if_rising=first_if_rising,
        lookback_months=lookback_months,
        cost_bps=cost_bps,
    )
except (OSError, ValueError, KeyError) as exc:
    st.error(f"Could not run the backtest. {exc}")
    st.stop()

strategy = result["strategy"]["equity"]["Equity"]
policy = result["policy"]["equity"]["Equity"]
spy = result["spy"]
growth = pd.DataFrame({"Yield trend": strategy, "Fixed-weight mix": policy, "SPY": spy})
st.subheader("Growth of $1")
st.line_chart(growth / growth.iloc[0])

metrics = pf.yield_trend_metrics(result)
percent_rows = [
    "Maximum drawdown", "Worst rolling 24 months", "Annualized average return",
    "Annualized volatility", "Annualized alpha vs SPY",
]
st.table(metrics.style.format("{:.3f}").format("{:.2%}", subset=pd.IndexSlice[percent_rows, :]))
st.caption("Both Sharpe ratios use the same risk-free rate. Gross Sharpe excludes simulated trading costs.")

st.subheader("Target weights")
weights = result["state_weights"]
weights.loc["Fixed-weight mix"] = weights.mean()
st.dataframe(weights.style.format("{:.2%}"), width="stretch")
st.caption(
    "The fixed mix averages the two sets of target weights and trades on the same schedule. "
    "Both portfolios include trading costs. SPY is a buy-and-hold reference. "
    "Equity ranks use a 50:25:15 ratio. Flat yields carry forward the previous direction."
)

with st.expander("Trade log and data sources"):
    trades = result["strategy"]["trades"]
    st.write(f"Total strategy trading costs were USD {trades['Fee'].sum():,.2f} on USD 100,000 of initial capital.")
    st.dataframe(trades, width="stretch", hide_index=True)
    st.caption(
        "ETF closes are adjusted for distributions and splits using yfinance. "
        "The yield signal uses the historical FRED series with a one-Fed-business-day publication lag. "
        "[FRED 3-year Treasury yield](https://fred.stlouisfed.org/series/DGS3)"
    )
