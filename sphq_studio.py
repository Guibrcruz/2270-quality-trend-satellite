"""SPHQ Studio — the 2270 quality-trend strategy with an FX Replay-style chart.

The calculations are the same `portfolio.py` code used by the submitted app and
notebook. The difference is the presentation: a dark, full-width TradingView
Lightweight Charts panel with growth, drawdown, exposure, signal and rolling
views, plus a compact assumptions panel.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import portfolio as pf
from chart_component import quality_chart

GROUP_NAME = "Group CD"
START = "2010-01-01"
END = "2025-12-31"
WARMUP_START = "2008-01-01"
END_EXCLUSIVE = "2026-01-01"
TICKER = "SPHQ"
BENCHMARK = "SPY"
RF_TICKER = "^IRX"
BASELINE = {"sma": 200, "cost": 10.0, "lag": 2, "capital": 100_000.0, "weight": 50}

st.set_page_config(
    page_title="SPHQ Studio | Quality Trend Satellite",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
    .stApp {background: #0b0e11; color: #e7ebf2;}
    [data-testid="stHeader"] {background: transparent;}
    [data-testid="stToolbar"] {display: none;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding: .55rem 1.25rem 2.2rem; max-width: 1500px;}
    h1, h2, h3 {color: #e7ebf2; letter-spacing: -.3px;}
    p, li, .stMarkdown {color: #aeb8c6;}
    [data-testid="stSidebar"] {background: #0f1318; border-right: 1px solid #232b38;}
    [data-testid="stSidebar"] .block-container {padding: 1.1rem .9rem;}
    [data-testid="stSidebar"] h3 {font-size: 13px; letter-spacing: 1.2px; color: #00c2a8;}
    [data-testid="stMetric"] {
        background: #131820; border: 1px solid #232b38; border-radius: 8px;
        padding: 9px 11px; min-height: 74px;
    }
    [data-testid="stMetricValue"] {color: #e7ebf2; font-size: 1.45rem; letter-spacing: -.4px;}
    [data-testid="stMetricLabel"] {color: #8b96a8; font-size: .72rem; text-transform: uppercase; letter-spacing: .5px;}
    [data-testid="stMetricDelta"] {font-size: .7rem;}
    .stTabs [data-baseweb="tab-list"] {gap: 4px; border-bottom: 1px solid #232b38;}
    .stTabs [data-baseweb="tab"] {color: #8b96a8; font-size: 11px; font-weight: 600; padding: 8px 10px;}
    .stTabs [aria-selected="true"] {color: #00c2a8;}
    [data-testid="stDataFrame"] {border: 1px solid #232b38; border-radius: 8px;}
    [data-testid="stExpander"] {background: #131820; border: 1px solid #232b38; border-radius: 8px;}
    .stSlider [data-baseweb="slider"] div {background: #00c2a8;}
    .stButton button {
        background: #131820; color: #c8d0dc; border: 1px solid #2b3544;
        border-radius: 5px; font-size: 11px;
    }
    .stButton button:hover {border-color: #00c2a8; color: #00c2a8;}
    .topline {
        display: flex; align-items: center; justify-content: space-between;
        color: #6f7b8d; font-size: 10px; letter-spacing: .7px; text-transform: uppercase;
        padding: 2px 2px 8px;
    }
    .topline b {color: #c8d0dc; font-weight: 600;}
    .badge {
        display: inline-block; padding: 3px 7px; border-radius: 4px; font-size: 9px;
        font-weight: 700; letter-spacing: .5px;
    }
    .badge.base {color: #00c2a8; background: rgba(0,194,168,.12); border: 1px solid rgba(0,194,168,.28);}
    .badge.custom {color: #f0b90b; background: rgba(240,185,11,.1); border: 1px solid rgba(240,185,11,.28);}
    .side-note {color: #6f7b8d; font-size: 9px; line-height: 1.45;}
    .side-title {color: #00c2a8; font-size: 11px; font-weight: 700; letter-spacing: 1.1px; margin-bottom: 2px;}
    div[data-testid="stAlert"] {border-radius: 7px; font-size: 11px;}
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Data and calculations
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=3600, show_spinner="Downloading Yahoo Finance data…")
def load_prices() -> dict:
    return pf.download_prices(
        [TICKER],
        start=WARMUP_START,
        end=END_EXCLUSIVE,
        benchmark=BENCHMARK,
        rf_ticker=RF_TICKER,
    )


@st.cache_data(show_spinner=False)
def run_scenario(sma: int, cost: float, lag: int, capital: float, weight: float) -> dict:
    data = load_prices()
    result = pf.run_trend_backtest(
        data["open"], data["close"],
        ticker=TICKER, benchmark=BENCHMARK, rf_ticker=RF_TICKER,
        start=START, end=END, sma_window=sma, lag=lag,
        cost_bps=cost, initial_cash=capital,
    )
    eq = result["equity"]
    bench = result["benchmark"]
    rf = result["rf_daily"]
    metrics = pf.performance_metrics(eq, bench, rf)
    policy = pf.policy_benchmark(bench, rf, weight=weight / 100.0, cost_bps=10.0)
    policy_metrics = pf.performance_metrics(policy, bench, rf)
    relative = pf.performance_metrics(eq, policy, rf)
    roll = pf.rolling_outcomes(eq, bench)["summary"]
    roll_policy = pf.rolling_outcomes(policy, bench)["summary"]
    trades = pf.trade_summary(result["trades"], eq)
    cal = pf.calendar_returns(eq, bench)
    bh = pf.performance_metrics(data["close"][TICKER].loc[eq.index], bench, rf)
    return {
        "data": data, "result": result, "equity": eq, "benchmark": bench,
        "policy": policy, "metrics": metrics, "policy_metrics": policy_metrics,
        "relative": relative, "roll": roll, "roll_policy": roll_policy,
        "trades": trades, "calendar": cal, "buy_hold": bh,
    }


@st.cache_data(show_spinner=False)
def sensitivity(sma: int, cost: float, lag: int, capital: float) -> dict:
    data = load_prices()

    def one(s: int, c: float, l: int) -> dict:
        r = pf.run_trend_backtest(
            data["open"], data["close"], start=START, end=END,
            sma_window=s, lag=l, cost_bps=c, initial_cash=capital,
        )
        m = pf.performance_metrics(r["equity"], r["benchmark"], r["rf_daily"])
        return {"cagr": m["CAGR"], "vol": m["Volatility"], "sharpe": m["Sharpe"],
                "maxdd": m["MaxDrawdown"]}

    return {
        "cost": [{"label": c, **one(sma, c, lag)} for c in [0, 5, 10, 20, 30]],
        "sma": [{"label": s, **one(s, cost, lag)} for s in [150, 200, 250]],
        "lag": [{"label": l, **one(sma, cost, l)} for l in [1, 2, 3]],
    }


def line(series: pd.Series, digits: int = 6) -> list[dict]:
    return [
        {"time": d.strftime("%Y-%m-%d"), "value": round(float(v), digits)}
        for d, v in series.items() if pd.notna(v)
    ]


def candles(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> list[dict]:
    rows = []
    for d in close.index:
        o, h, l, c = open_.get(d), high.get(d), low.get(d), close.get(d)
        if any(pd.isna(x) for x in (o, h, l, c)):
            continue
        rows.append({"time": d.strftime("%Y-%m-%d"),
                     "open": round(float(o), 4), "high": round(float(h), 4),
                     "low": round(float(l), 4), "close": round(float(c), 4)})
    return rows


def clean_metrics(m: dict) -> dict:
    out = {}
    for k, v in m.items():
        if isinstance(v, pd.Timestamp):
            out[k] = v.strftime("%Y-%m-%d")
        elif isinstance(v, (np.floating, np.integer)):
            out[k] = float(v) if isinstance(v, np.floating) else int(v)
        else:
            out[k] = v
    return out


def payload_for(r: dict, sma: int, cost: float, lag: int, capital: float, weight: int) -> dict:
    eq = r["equity"]
    bench = r["benchmark"]
    policy = r["policy"]
    data = r["data"]
    result = r["result"]
    idx = eq.index

    growth_s = eq["Equity"] / eq["Equity"].iloc[0]
    growth_b = bench / bench.iloc[0]
    growth_p = policy / policy.iloc[0]
    dd_s = growth_s / growth_s.cummax() - 1.0
    dd_b = growth_b / growth_b.cummax() - 1.0
    dd_p = growth_p / growth_p.cummax() - 1.0

    exposure = result["positions"]["Weight"].reindex(idx).fillna(0.0)
    sma_series = result["sma"].reindex(idx)
    op = data["open"][TICKER].reindex(idx)
    hi = data["high"][TICKER].reindex(idx)
    lo = data["low"][TICKER].reindex(idx)
    cl = data["close"][TICKER].reindex(idx)

    roll_s = (eq["Equity"].shift(-504) / eq["Equity"] - 1.0).dropna()
    roll_b = (bench.shift(-504) / bench - 1.0).reindex(roll_s.index)

    trades = []
    if not result["trades"].empty:
        for _, t in result["trades"].iterrows():
            trades.append({
                "signalDate": pd.Timestamp(t["SignalDate"]).strftime("%Y-%m-%d"),
                "execDate": pd.Timestamp(t["ExecDate"]).strftime("%Y-%m-%d"),
                "action": t["Action"], "price": round(float(t["Price"]), 4),
                "notional": round(float(t["Notional"]), 2), "fee": round(float(t["Fee"]), 2),
                "holdingDays": None if pd.isna(t["HoldingDays"]) else int(t["HoldingDays"]),
            })

    cal = []
    for year, row in r["calendar"].iterrows():
        cal.append({"year": int(year),
                    "strategy": None if pd.isna(row["Strategy"]) else float(row["Strategy"]),
                    "benchmark": None if pd.isna(row["Benchmark"]) else float(row["Benchmark"])})

    roll = r["roll"]
    roll_policy = r["roll_policy"]
    summary = {
        "windows": int(roll.loc["Windows", "Strategy"]),
        "strategy": {k: float(roll.loc[k, "Strategy"]) for k in ["Worst", "Median", "Best", "% Positive"]},
        "benchmark": {k: float(roll.loc[k, "Benchmark"]) for k in ["Worst", "Median", "Best", "% Positive"]},
        "policy": {k: float(roll_policy.loc[k, "Strategy"]) for k in ["Worst", "Median", "Best", "% Positive"]},
    }

    sens = sensitivity(int(sma), float(cost), int(lag), float(capital))
    baseline = (int(sma) == 200 and abs(cost - 10.0) < 1e-9 and int(lag) == 2 and int(weight) == 50)

    return {
        "meta": {
            "group": GROUP_NAME,
            "ticker": TICKER,
            "benchmark": BENCHMARK,
            "sample": f"{START} to {END}",
            "source": "Yahoo Finance via yfinance",
            "baseline": baseline,
        },
        "params": {"sma": int(sma), "cost": float(cost), "lag": int(lag),
                   "capital": float(capital), "weight": int(weight)},
        "growth": {"strategy": line(growth_s), "spy": line(growth_b), "policy": line(growth_p),
                   "final": {"strategy": float(growth_s.iloc[-1]), "spy": float(growth_b.iloc[-1]),
                             "policy": float(growth_p.iloc[-1])}},
        "drawdown": {"strategy": line(dd_s), "spy": line(dd_b), "policy": line(dd_p),
                     "max": {"strategy": float(dd_s.min()), "spy": float(dd_b.min()),
                             "policy": float(dd_p.min())}},
        "exposure": {"strategy": line(exposure), "policy": line(pd.Series(weight / 100.0, index=idx)),
                     "average": float(exposure.mean())},
        "signals": {"candles": candles(op, hi, lo, cl), "sma": line(sma_series),
                    "trades": trades},
        "rolling": {"strategy": line(roll_s), "spy": line(roll_b),
                    "summary": summary},
        "metrics": clean_metrics(r["metrics"]),
        "policyMetrics": clean_metrics(r["policy_metrics"]),
        "relative": clean_metrics(r["relative"]),
        "buyHold": clean_metrics(r["buy_hold"]),
        "tradeSummary": {k: (None if isinstance(v, float) and not np.isfinite(v) else v)
                         for k, v in r["trades"].items()},
        "calendar": cal,
        "sensitivity": sens,
        "metaNote": "Historical simulation, not investment advice.",
    }


# --------------------------------------------------------------------------- #
# Sidebar controls
# --------------------------------------------------------------------------- #
for key, value in BASELINE.items():
    if key not in st.session_state:
        st.session_state[key] = value


def reset_defaults() -> None:
    for key, value in BASELINE.items():
        st.session_state[key] = value


with st.sidebar:
    st.markdown("<div class='side-title'>ASSUMPTIONS</div>", unsafe_allow_html=True)
    st.caption("Defaults reproduce the submitted notebook.")
    sma = st.slider("Trend window (trading days)", 100, 300, step=10, key="sma",
                    help="Hold SPHQ when its month-end close is above this moving average.")
    cost = st.slider("Transaction cost (bps per side)", 0, 30, step=1, key="cost",
                     help="Commission, spread and slippage. The notebook baseline is 10 bps.")
    lag = st.slider("Execution lag (trading days)", 1, 3, step=1, key="lag",
                    help="Signal at the month-end close; trade at the open t+lag days later.")
    capital = st.number_input("Initial capital (USD)", 10_000, 1_000_000, step=10_000, key="capital")
    weight = st.slider("Policy benchmark equity weight", 10, 90, step=5, key="weight",
                       help="The passive comparison: this percentage in SPY, the rest in T-bills, rebalanced monthly.")
    st.button("Reset to notebook defaults", width="stretch", on_click=reset_defaults)
    st.markdown(
        "<div class='side-note' style='margin-top:10px'>"
        "<b style='color:#c8d0dc'>Notebook baseline</b><br>"
        "200-day SMA · 10 bps per side · t+2 open · 50/50 policy mix.<br><br>"
        "Policy benchmark costs are held at 10 bps."
        "</div>",
        unsafe_allow_html=True,
    )

# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
try:
    r = run_scenario(int(sma), float(cost), int(lag), float(capital), float(weight))
except Exception as exc:
    st.error(f"Could not run the backtest: {exc}")
    st.stop()

payload = payload_for(r, int(sma), float(cost), int(lag), float(capital), int(weight))
baseline = payload["meta"]["baseline"]

# --------------------------------------------------------------------------- #
# Header + chart
# --------------------------------------------------------------------------- #
st.markdown(
    f"""
    <div class="topline">
      <div><b>2270 Financial Modeling</b> · Moodle group <b>{GROUP_NAME}</b></div>
      <div><span class="badge {'base' if baseline else 'custom'}">
        {'NOTEBOOK BASELINE' if baseline else 'CUSTOM SCENARIO'}
      </span></div>
    </div>
    """,
    unsafe_allow_html=True,
)

quality_chart(payload=payload, key="sphq_chart")

st.caption(
    "Chart: **Growth** for cumulative performance · **Price & trades** for SPHQ candles with "
    "every BUY/SELL arrow · **Drawdown**, **Exposure** and **Rolling 24m** for risk."
)
st.caption(
    "Assumptions: open the sidebar (top-left arrow) to change the trend window, transaction "
    "cost, execution lag, initial capital and policy-benchmark weight."
)
st.page_link("pages/1_Treasury_Yield_Trend.py", label="Open Treasury Yield Trend")

# --------------------------------------------------------------------------- #
# KPI cards
# --------------------------------------------------------------------------- #
m = r["metrics"]
pm = r["policy_metrics"]
rel = r["relative"]
roll = r["roll"]
tr = r["trades"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("CAGR, net", f"{m['CAGR']:.2%}", help="Compound annual growth rate after transaction costs.")
c2.metric("Volatility", f"{m['Volatility']:.2%}", help="Annualized standard deviation of daily returns.")
c3.metric("Sharpe ratio", f"{m['Sharpe']:.2f}", help="Excess return per unit of total risk, annualized.")
c4.metric("Beta vs SPY", f"{m['Beta']:.2f}", help="Daily regression slope. Beta is NOT annualized.")

c5, c6, c7, c8 = st.columns(4)
c5.metric("Alpha vs SPY", f"{m['Alpha']:.2%}", help=f"Annualized regression intercept; t = {m['AlphaT']:.2f}.")
c6.metric("IR vs policy", f"{rel['InformationRatio']:.2f}", help="Active return per unit of tracking error vs the policy mix.")
c7.metric("Max drawdown", f"{m['MaxDrawdown']:.2%}", help=f"{m['MaxDrawdownPeak']} to {m['MaxDrawdownTrough']}.")
c8.metric("Worst 24 months", f"{roll.loc['Worst', 'Strategy']:.2%}", help="Worst overlapping 24-month return in the sample.")

st.caption(
    f"Final value of \\${capital:,.0f}: **\\${r['equity']['Equity'].iloc[-1]:,.0f}** · "
    f"SPY: \\${capital * r['benchmark'].iloc[-1] / r['benchmark'].iloc[0]:,.0f} · "
    f"policy mix: \\${capital * r['policy'].iloc[-1] / r['policy'].iloc[0]:,.0f} · "
    f"trades: {tr['Trades']} · turnover: {tr['Turnover']:.2f}x per year"
)

# --------------------------------------------------------------------------- #
# Detail tabs
# --------------------------------------------------------------------------- #
tab_perf, tab_risk, tab_trades, tab_method = st.tabs(
    ["Performance", "Risk", "Trades & costs", "Method & disclosure"]
)

with tab_perf:
    st.subheader("Headline measures")
    perf = pd.DataFrame({
        "Quality trend": [
            f"{m['CAGR']:.2%}", f"{m['ArithmeticReturn']:.2%}", f"{m['Volatility']:.2%}",
            f"{m['Sharpe']:.2f}", f"{m['Beta']:.2f}",
            f"{m['Alpha']:.2%} (t {m['AlphaT']:.2f})", f"{m['InformationRatio']:.2f}",
            f"{m['TrackingError']:.2%}", f"{m['MaxDrawdown']:.2%}",
            f"{roll.loc['Worst', 'Strategy']:.2%}",
        ],
        "SPY": [
            f"{m['BenchmarkCAGR']:.2%}", f"{m['BenchmarkArithmeticReturn']:.2%}",
            f"{m['BenchmarkVolatility']:.2%}", f"{m['BenchmarkSharpe']:.2f}", "1.00",
            "-", "-", "-", f"{payload['drawdown']['max']['spy']:.2%}",
            f"{roll.loc['Worst', 'Benchmark']:.2%}",
        ],
        "Policy mix": [
            f"{pm['CAGR']:.2%}", f"{pm['ArithmeticReturn']:.2%}", f"{pm['Volatility']:.2%}",
            f"{pm['Sharpe']:.2f}", f"{pm['Beta']:.2f}",
            f"{pm['Alpha']:.2%} (t {pm['AlphaT']:.2f})", f"{pm['InformationRatio']:.2f}",
            f"{pm['TrackingError']:.2%}", f"{pm['MaxDrawdown']:.2%}",
            f"{r['roll_policy'].loc['Worst', 'Strategy']:.2%}",
        ],
    }, index=[
        "CAGR, net", "Average annual return (arithmetic)", "Volatility", "Sharpe",
        "Beta vs SPY (not annualized)", "Alpha vs SPY (annualized)", "Information ratio vs SPY",
        "Tracking error vs SPY", "Maximum drawdown", "Worst 24-month return",
    ])
    st.dataframe(perf, width="stretch")

    st.subheader("Calendar-year returns")
    cal = r["calendar"].copy()
    cal.index = cal.index.astype(int)
    st.dataframe(cal.style.format({"Strategy": "{:.2%}", "Benchmark": "{:.2%}"}), width="stretch")

    st.subheader("The alternative: simply hold SPHQ")
    bh = r["buy_hold"]
    factor = pd.DataFrame({
        "Quality trend": [f"{m['CAGR']:.2%}", f"{m['Volatility']:.2%}",
                          f"{m['Sharpe']:.2f}", f"{m['MaxDrawdown']:.2%}"],
        "SPHQ buy & hold": [f"{bh['CAGR']:.2%}", f"{bh['Volatility']:.2%}",
                            f"{bh['Sharpe']:.2f}", f"{bh['MaxDrawdown']:.2%}"],
        "SPY": [f"{m['BenchmarkCAGR']:.2%}", f"{m['BenchmarkVolatility']:.2%}",
                f"{m['BenchmarkSharpe']:.2f}", f"{payload['drawdown']['max']['spy']:.2%}"],
    }, index=["CAGR", "Volatility", "Sharpe", "Maximum drawdown"])
    st.dataframe(factor, width="stretch")

with tab_risk:
    st.subheader("Overlapping 24-month outcomes")
    risk = pd.DataFrame({
        "Quality trend": [f"{roll.loc['Worst', 'Strategy']:.2%}",
                          f"{roll.loc['Median', 'Strategy']:.2%}",
                          f"{roll.loc['Best', 'Strategy']:.2%}",
                          f"{roll.loc['% Positive', 'Strategy']:.1%}"],
        "SPY": [f"{roll.loc['Worst', 'Benchmark']:.2%}",
                f"{roll.loc['Median', 'Benchmark']:.2%}",
                f"{roll.loc['Best', 'Benchmark']:.2%}",
                f"{roll.loc['% Positive', 'Benchmark']:.1%}"],
    }, index=["Worst", "Median", "Best", "% positive"])
    st.dataframe(risk, width="stretch")
    st.caption(f"{int(roll.loc['Windows', 'Strategy']):,} overlapping windows; they are not independent observations.")

    st.subheader("Drawdown and recovery")
    dd = r["equity"]["Equity"]
    dd = dd / dd.cummax() - 1.0
    trough = dd.idxmin()
    peak = dd.loc[:trough].idxmax()
    st.write(
        f"Maximum drawdown **{dd.min():.2%}**, from **{peak.date()}** to **{trough.date()}**. "
        f"SPY's maximum drawdown over the same sample was **{payload['drawdown']['max']['spy']:.2%}**."
    )

    st.subheader("Rolling 24-month return")
    st.caption("The chart above shows the full rolling series. Summary:")
    st.dataframe(pd.DataFrame({
        "Quality trend": [f"{roll.loc['Worst', 'Strategy']:.2%}", f"{roll.loc['Median', 'Strategy']:.2%}", f"{roll.loc['Best', 'Strategy']:.2%}"],
        "SPY": [f"{roll.loc['Worst', 'Benchmark']:.2%}", f"{roll.loc['Median', 'Benchmark']:.2%}", f"{roll.loc['Best', 'Benchmark']:.2%}"],
    }, index=["Worst", "Median", "Best"]), width="stretch")

with tab_trades:
    st.subheader("Trade log")
    trades = r["result"]["trades"]
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
    c3.metric("One-way turnover", f"{tr['Turnover']:.2f}x/yr")
    c4.metric("Cost drag", f"{tr['CostDrag']:.2%}")
    st.caption(
        f"Average holding period: {tr['AverageHoldingDays']:.0f} days. "
        f"Total costs on \\${capital:,.0f}: \\${tr['TotalCosts']:,.0f}. "
        "The policy mix is charged 10 bps at its monthly rebalance."
    )

    st.subheader("Cost sensitivity")
    cost_rows = [{"Cost (bps/side)": x["label"], "CAGR": f"{x['cagr']:.2%}",
                  "Vol": f"{x['vol']:.2%}", "Sharpe": f"{x['sharpe']:.2f}",
                  "Max DD": f"{x['maxdd']:.2%}"} for x in payload["sensitivity"]["cost"]]
    st.dataframe(pd.DataFrame(cost_rows).set_index("Cost (bps/side)"), width="stretch")

    st.subheader("SMA sensitivity")
    sma_rows = [{"Trend window": x["label"], "CAGR": f"{x['cagr']:.2%}",
                 "Vol": f"{x['vol']:.2%}", "Sharpe": f"{x['sharpe']:.2f}",
                 "Max DD": f"{x['maxdd']:.2%}"} for x in payload["sensitivity"]["sma"]]
    st.dataframe(pd.DataFrame(sma_rows).set_index("Trend window"), width="stretch")

    st.subheader("Execution lag sensitivity")
    lag_rows = [{"Lag (days)": x["label"], "CAGR": f"{x['cagr']:.2%}",
                 "Vol": f"{x['vol']:.2%}", "Sharpe": f"{x['sharpe']:.2f}",
                 "Max DD": f"{x['maxdd']:.2%}"} for x in payload["sensitivity"]["lag"]]
    st.dataframe(pd.DataFrame(lag_rows).set_index("Lag (days)"), width="stretch")

with tab_method:
    st.subheader("How the app stays consistent with the notebook")
    st.write(
        "This app imports the same `portfolio.py` functions used by the submitted notebook and "
        "the original Streamlit app: the same month-end signal, the same t+2 open execution, the "
        "same 10 bps default cost, the same T-bill conversion and the same metric definitions. "
        "The default scenario reproduces the notebook's headline numbers. The controls only change "
        "assumptions; they do not change the rule."
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
        fabricated. The group should confirm that AI-assisted strategy selection is permitted
        under the course AI policy.
        """
    )
    st.info(
        "This is an academic exercise for the 2270 Financial Modeling group assignment. "
        "It is not investment advice. Past performance does not guarantee future results."
    )

st.caption(
    f"Prepared by {GROUP_NAME} · 4 December 2026 · Data: Yahoo Finance via yfinance · "
    "Calculations: portfolio.py · Charting: TradingView Lightweight Charts"
)
