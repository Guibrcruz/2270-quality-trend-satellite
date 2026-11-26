"""
Streamlit app for the 2270 quality-trend strategy.

The app imports the shared calculation layer in portfolio.py, so the default
scenario reproduces the submitted notebook. The user can change the trend
window, transaction cost, execution lag, initial capital and the policy
benchmark's equity weight; every result is recalculated live from Yahoo Finance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import streamlit as st

import portfolio as pf

GROUP_NAME = "[GROUP NAME]"
MEMBERS = "[MEMBER NAMES AND STUDENT IDS]"
START = "2010-01-01"
END = "2025-12-31"
WARMUP_START = "2008-01-01"
END_EXCLUSIVE = "2026-01-01"
TICKER = "SPHQ"
BENCHMARK = "SPY"

st.set_page_config(
    page_title="Quality Trend Satellite | 2270",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.1rem; padding-bottom: 1.5rem; max-width: 1250px;}
    h1, h2, h3 {color: #17365D;}
    [data-testid="stMetricValue"] {color: #17365D; font-size: 1.75rem;}
    [data-testid="stMetricLabel"] {color: #555555; font-size: 0.9rem;}
    .small-note {color: #666666; font-size: 0.85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600, show_spinner="Downloading Yahoo Finance data...")
def load_prices() -> dict:
    return pf.download_prices(
        [TICKER],
        start=WARMUP_START,
        end=END_EXCLUSIVE,
        benchmark=BENCHMARK,
        rf_ticker="^IRX",
    )


def pct(x: float, digits: int = 2) -> str:
    return f"{x:.{digits}%}"


def num(x: float, digits: int = 2) -> str:
    return f"{x:.{digits}f}"


def money(x: float) -> str:
    # Escape the dollar sign so Streamlit's Markdown does not treat it as LaTeX.
    return f"\\${x:,.0f}"


def max_drawdown(series: pd.Series) -> float:
    curve = series.astype(float) / series.iloc[0]
    return float((curve / curve.cummax() - 1.0).min())


def run_scenario(sma_window: int, cost_bps: float, lag: int, capital: float, policy_weight: float):
    data = load_prices()
    result = pf.run_trend_backtest(
        data["open"],
        data["close"],
        ticker=TICKER,
        benchmark=BENCHMARK,
        rf_ticker="^IRX",
        start=START,
        end=END,
        sma_window=sma_window,
        lag=lag,
        cost_bps=cost_bps,
        initial_cash=capital,
    )
    eq = result["equity"]
    bench = result["benchmark"]
    rf = result["rf_daily"]
    metrics = pf.performance_metrics(eq, bench, rf)
    policy = pf.policy_benchmark(bench, rf, weight=policy_weight, cost_bps=10.0)
    policy_metrics = pf.performance_metrics(policy, bench, rf)
    relative = pf.performance_metrics(eq, policy, rf)
    roll = pf.rolling_outcomes(eq, bench)["summary"]
    roll_policy = pf.rolling_outcomes(policy, bench)["summary"]
    trades = pf.trade_summary(result["trades"], eq)
    cal = pf.calendar_returns(eq, bench)
    bh = pf.performance_metrics(data["close"][TICKER].loc[eq.index], bench, rf)
    return {
        "data": data,
        "result": result,
        "equity": eq,
        "benchmark": bench,
        "policy": policy,
        "metrics": metrics,
        "policy_metrics": policy_metrics,
        "relative": relative,
        "roll": roll,
        "roll_policy": roll_policy,
        "trades": trades,
        "calendar": cal,
        "buy_hold": bh,
    }


# --------------------------------------------------------------------------- #
# Sidebar controls
# --------------------------------------------------------------------------- #
for key, value in {"sma": 200, "cost": 10.0, "lag": 2, "capital": 100_000.0, "weight": 50}.items():
    if key not in st.session_state:
        st.session_state[key] = value


def reset_defaults() -> None:
    # Runs before the next script run, so it can safely update widget state.
    st.session_state["sma"] = 200
    st.session_state["cost"] = 10.0
    st.session_state["lag"] = 2
    st.session_state["capital"] = 100_000.0
    st.session_state["weight"] = 50

with st.sidebar:
    st.title("Assumptions")
    st.caption("The defaults reproduce the submitted notebook.")

    sma = st.slider(
        "Trend window (trading days)", min_value=100, max_value=300,
        step=10, key="sma",
        help="The strategy holds SPHQ when its month-end close is above this moving average.",
    )
    cost = st.slider(
        "Transaction cost (bps per side)", min_value=0, max_value=30,
        step=1, key="cost",
        help="Commission, spread and slippage. The notebook baseline is 10 bps.",
    )
    lag = st.slider(
        "Execution lag (trading days)", min_value=1, max_value=3,
        step=1, key="lag",
        help="Signal at the month-end close; trade at the open t+lag days later.",
    )
    capital = st.number_input(
        "Initial capital (USD)", min_value=10_000, max_value=1_000_000,
        step=10_000, key="capital",
    )
    weight = st.slider(
        "Policy benchmark equity weight", min_value=10, max_value=90,
        step=5, key="weight",
        help="The passive comparison: this percentage in SPY, the rest in T-bills, rebalanced monthly.",
    )
    policy_weight = weight / 100.0

    st.button("Reset to notebook defaults", width="stretch", on_click=reset_defaults)

    st.divider()
    st.markdown(
        f"**Notebook baseline**<br>"
        f"200-day SMA · 10 bps per side · t+2 open · 50/50 policy mix",
        unsafe_allow_html=True,
    )
    st.caption("Policy benchmark costs are held at 10 bps, as in the notebook.")

# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
try:
    r = run_scenario(int(sma), float(cost), int(lag), float(capital), policy_weight)
except Exception as exc:
    st.error(f"Could not run the backtest: {exc}")
    st.stop()

eq = r["equity"]
bench = r["benchmark"]
policy = r["policy"]
m = r["metrics"]
pm = r["policy_metrics"]
rel = r["relative"]
roll = r["roll"]
roll_policy = r["roll_policy"]
tr = r["trades"]
cal = r["calendar"]
bh = r["buy_hold"]
trades = r["result"]["trades"]

# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.title("Quality Trend Satellite")
st.markdown(
    f"**2270 Financial Modeling** · Moodle group **{GROUP_NAME}** · "
    f"SPHQ above its {int(sma)}-day trend, otherwise T-bills · 2010-2025"
)
st.caption(
    "A long-only, single-ETF satellite for a retail client with a short horizon. "
    "All results are computed live from Yahoo Finance. This is an academic exercise, not investment advice."
)

baseline = (int(sma) == 200 and abs(cost - 10.0) < 1e-9 and int(lag) == 2 and int(weight) == 50)
if baseline:
    st.success("Notebook baseline scenario: 200-day SMA, 10 bps per side, t+2 open, 50/50 policy mix.")
else:
    st.info(
        f"Custom scenario: {int(sma)}-day SMA, {cost:.0f} bps per side, t+lag {int(lag)}, "
        f"{int(weight)}/{100-int(weight)} policy mix. The notebook baseline is 200 days, 10 bps, lag 2, 50/50."
    )

# --------------------------------------------------------------------------- #
# KPI cards
# --------------------------------------------------------------------------- #
c1, c2, c3, c4 = st.columns(4)
c1.metric("CAGR, net", pct(m["CAGR"]), help="Compound annual growth rate after transaction costs.")
c2.metric("Volatility", pct(m["Volatility"]), help="Annualized standard deviation of daily returns.")
c3.metric("Sharpe ratio", num(m["Sharpe"]), help="Excess return per unit of total risk, annualized.")
c4.metric("Beta vs SPY", num(m["Beta"]), help="Daily regression slope. Beta is NOT annualized.")

c5, c6, c7, c8 = st.columns(4)
c5.metric("Alpha vs SPY", pct(m["Alpha"]), help=f"Annualized regression intercept; t = {num(m['AlphaT'])}.")
c6.metric("IR vs policy", num(rel["InformationRatio"]), help="Active return per unit of tracking error vs the policy mix.")
c7.metric("Max drawdown", pct(m["MaxDrawdown"]), help=f"{m['MaxDrawdownPeak']} to {m['MaxDrawdownTrough']}.")
c8.metric("Worst 24 months", pct(roll.loc["Worst", "Strategy"]), help="Worst overlapping 24-month return in the sample.")

st.caption(
    f"Final value of {money(capital)}: **{money(eq['Equity'].iloc[-1])}** · "
    f"SPY: {money(capital * bench.iloc[-1] / bench.iloc[0])} · "
    f"policy mix: {money(capital * policy.iloc[-1] / policy.iloc[0])} · "
    f"trades: {tr['Trades']} · turnover: {num(tr['Turnover'])}x per year"
)

# --------------------------------------------------------------------------- #
# Cumulative chart
# --------------------------------------------------------------------------- #
strat_cum = eq["Equity"] / eq["Equity"].iloc[0]
spy_cum = bench / bench.iloc[0]
pol_cum = policy / policy.iloc[0]

fig, ax = plt.subplots(figsize=(10, 4.0))
ax.plot(strat_cum.index, strat_cum, color="#1F4E79", lw=2.2, label=f"Quality trend ({strat_cum.iloc[-1]:.2f}x)")
ax.plot(spy_cum.index, spy_cum, color="#7F7F7F", lw=1.4, label=f"SPY ({spy_cum.iloc[-1]:.2f}x)")
ax.plot(pol_cum.index, pol_cum, color="#C55A11", lw=1.6, ls="--",
        label=f"{int(weight)}/{100-int(weight)} SPY/T-bill ({pol_cum.iloc[-1]:.2f}x)")
ax.axhline(1.0, color="black", lw=0.8)
ax.set_yscale("log")
ax.set_yticks([1, 1.5, 2, 3, 4, 6, 8, 10])
ax.get_yaxis().set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.1f}x"))
ax.set_title("Growth of $1, all series start at 1")
ax.set_ylabel("Growth of $1")
ax.legend(loc="upper left", frameon=False)
ax.grid(alpha=0.25)
plt.tight_layout()
st.pyplot(fig, width="stretch")
plt.close(fig)

# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
tab_perf, tab_risk, tab_trades, tab_method = st.tabs(
    ["Performance", "Risk", "Trades & costs", "Method & disclosure"]
)

with tab_perf:
    st.subheader("Headline measures")
    perf = pd.DataFrame({
        "Quality trend": [
            pct(m["CAGR"]), pct(m["ArithmeticReturn"]), pct(m["Volatility"]), num(m["Sharpe"]),
            num(m["Beta"]), f"{pct(m['Alpha'])} (t {num(m['AlphaT'])})", num(m["InformationRatio"]),
            pct(m["TrackingError"]), pct(m["MaxDrawdown"]), pct(roll.loc["Worst", "Strategy"]),
        ],
        "SPY": [
            pct(m["BenchmarkCAGR"]), pct(m["BenchmarkArithmeticReturn"]), pct(m["BenchmarkVolatility"]),
            num(m["BenchmarkSharpe"]), "1.00", "-", "-", "-", pct(max_drawdown(bench)),
            pct(roll.loc["Worst", "Benchmark"]),
        ],
        "Policy mix": [
            pct(pm["CAGR"]), pct(pm["ArithmeticReturn"]), pct(pm["Volatility"]), num(pm["Sharpe"]),
            num(pm["Beta"]), f"{pct(pm['Alpha'])} (t {num(pm['AlphaT'])})", num(pm["InformationRatio"]),
            pct(pm["TrackingError"]), pct(pm["MaxDrawdown"]), pct(roll_policy.loc["Worst", "Strategy"]),
        ],
    }, index=[
        "CAGR, net", "Average annual return (arithmetic)", "Volatility", "Sharpe",
        "Beta vs SPY (not annualized)", "Alpha vs SPY (annualized)", "Information ratio vs SPY",
        "Tracking error vs SPY", "Maximum drawdown", "Worst 24-month return",
    ])
    st.dataframe(perf, width="stretch")

    st.subheader("Calendar-year returns")
    cal_show = cal.copy()
    cal_show.index = cal_show.index.astype(int)
    st.dataframe(
        cal_show.style.format({"Strategy": "{:.2%}", "Benchmark": "{:.2%}"}),
        width="stretch",
    )

    st.subheader("The alternative: simply hold SPHQ")
    factor = pd.DataFrame({
        "Quality trend": [pct(m["CAGR"]), pct(m["Volatility"]), num(m["Sharpe"]), pct(m["MaxDrawdown"])],
        "SPHQ buy & hold": [pct(bh["CAGR"]), pct(bh["Volatility"]), num(bh["Sharpe"]), pct(bh["MaxDrawdown"])],
        "SPY": [pct(m["BenchmarkCAGR"]), pct(m["BenchmarkVolatility"]), num(m["BenchmarkSharpe"]),
                pct(max_drawdown(bench))],
    }, index=["CAGR", "Volatility", "Sharpe", "Maximum drawdown"])
    st.dataframe(factor, width="stretch")

with tab_risk:
    st.subheader("Drawdown")
    dd_strat = strat_cum / strat_cum.cummax() - 1.0
    dd_spy = spy_cum / spy_cum.cummax() - 1.0
    fig, ax = plt.subplots(figsize=(10, 3.3))
    ax.fill_between(dd_spy.index, dd_spy, 0, color="#7F7F7F", alpha=0.25, label="SPY")
    ax.fill_between(dd_strat.index, dd_strat, 0, color="#1F4E79", alpha=0.45, label="Quality trend")
    ax.set_ylabel("Drawdown")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.legend(loc="lower left", frameon=False)
    ax.grid(alpha=0.25)
    plt.tight_layout()
    st.pyplot(fig, width="stretch")
    plt.close(fig)

    st.subheader("Overlapping 24-month outcomes")
    risk = pd.DataFrame({
        "Quality trend": [pct(roll.loc["Worst", "Strategy"]), pct(roll.loc["Median", "Strategy"]),
                          pct(roll.loc["Best", "Strategy"]), pct(roll.loc["% Positive", "Strategy"], 1)],
        "SPY": [pct(roll.loc["Worst", "Benchmark"]), pct(roll.loc["Median", "Benchmark"]),
                pct(roll.loc["Best", "Benchmark"]), pct(roll.loc["% Positive", "Benchmark"], 1)],
    }, index=["Worst", "Median", "Best", "% positive"])
    st.dataframe(risk, width="stretch")
    st.caption(f"{int(roll.loc['Windows', 'Strategy']):,} overlapping windows; they are not independent observations.")

    st.subheader("Rolling 24-month return")
    rs = eq["Equity"].shift(-504) / eq["Equity"] - 1.0
    rb = bench.shift(-504) / bench - 1.0
    fig, ax = plt.subplots(figsize=(10, 3.0))
    ax.plot(rs.index, rs, color="#1F4E79", lw=1.4, label="Quality trend")
    ax.plot(rb.index, rb, color="#7F7F7F", lw=1.0, label="SPY")
    ax.axhline(0, color="black", lw=0.8)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    plt.tight_layout()
    st.pyplot(fig, width="stretch")
    plt.close(fig)

with tab_trades:
    st.subheader("Trade log")
    if trades.empty:
        st.info("No trades in this scenario.")
    else:
        show = trades.copy()
        show["SignalDate"] = pd.to_datetime(show["SignalDate"]).dt.date
        show["ExecDate"] = pd.to_datetime(show["ExecDate"]).dt.date
        st.dataframe(
            show[["SignalDate", "ExecDate", "Ticker", "Action", "Price", "Notional", "Fee", "HoldingDays"]]
            .style.format({"Price": "{:.4f}", "Notional": "{:,.2f}", "Fee": "{:,.2f}", "HoldingDays": "{:.0f}"}),
            width="stretch", hide_index=True,
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trades", tr["Trades"])
    c2.metric("Round trips", tr["RoundTrips"])
    c3.metric("One-way turnover", f"{num(tr['Turnover'])}x/yr")
    c4.metric("Cost drag", pct(tr["CostDrag"]))
    st.caption(
        f"Average holding period: {tr['AverageHoldingDays']:.0f} days. "
        f"Total costs on {money(capital)}: {money(tr['TotalCosts'])}. "
        "The policy mix is charged 10 bps at its monthly rebalance."
    )

    st.subheader("Cost sensitivity")
    cost_rows = []
    for c in [0, 5, 10, 20, 30]:
        rr = pf.run_trend_backtest(
            r["data"]["open"], r["data"]["close"], start=START, end=END,
            sma_window=int(sma), lag=int(lag), cost_bps=float(c), initial_cash=float(capital),
        )
        mm = pf.performance_metrics(rr["equity"], rr["benchmark"], rr["rf_daily"])
        cost_rows.append({
            "Cost (bps/side)": c, "CAGR": pct(mm["CAGR"]), "Vol": pct(mm["Volatility"]),
            "Sharpe": num(mm["Sharpe"]), "Max DD": pct(mm["MaxDrawdown"]),
        })
    st.dataframe(pd.DataFrame(cost_rows).set_index("Cost (bps/side)"), width="stretch")

with tab_method:
    st.subheader("How the app stays consistent with the notebook")
    st.write(
        "The app imports the same `portfolio.py` functions used by the notebook: the same "
        "month-end signal, the same t+2 open execution, the same 10 bps default cost, the same "
        "T-bill conversion and the same metric definitions. The default scenario reproduces the "
        "submitted notebook's headline numbers. The app only lets you change assumptions; it does "
        "not change the rule."
    )
    st.markdown(
        f"""
        **Default scenario:** {TICKER} above its 200-day SMA, otherwise 3-month T-bills; monthly
        signal; open of t+2; 10 bps per side; 50/50 SPY/T-bill policy benchmark.

        **Data:** Yahoo Finance adjusted OHLC, downloaded live. Sample 1 January 2010 to
        31 December 2025, with a warm-up from 1 January 2008. No data file is stored in the repo.

        **Metric definitions:** CAGR is geometric; volatility is annualized with 252 days; Sharpe
        uses daily excess returns; beta is a daily regression slope and is **not annualized**;
        alpha is the annualized regression intercept; the information ratio is annualized active
        return divided by annualized tracking error.

        **Limitations:** in-sample rule selection, survivorship bias from using a current ETF,
        one factor and one country, no taxes, no fund tracking error, and a favourable 2010-2025
        sample. Alpha's t-statistic is about 1.62, so it is not statistically significant.

        **Generative AI:** this app and the underlying analysis were built with DeepSeek V4.1 Flash
        via OpenCode. The group formulated the mandate and the original Bollinger Bands idea; the
        assistant tested it, showed that it did not survive a fair comparison, and proposed the
        SPHQ quality-trend alternative. The group reviewed the evidence and approved the pivot and
        the final rule. All code was run and checked by the group. No data or results were
        fabricated. The group should confirm that AI-assisted strategy selection is permitted under
        the course AI policy.
        """
    )
    st.info(
        "This is an academic exercise for the 2270 Financial Modeling group assignment. "
        "It is not investment advice. Past performance does not guarantee future results."
    )

st.divider()
st.caption(
    f"Prepared by {GROUP_NAME} · {MEMBERS} · 4 December 2026 · "
    "Data: Yahoo Finance via yfinance · Calculations: portfolio.py"
)
