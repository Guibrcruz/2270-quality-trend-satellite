"""
Shared calculation layer for the 2270 SPHQ quality-trend strategy.

The notebook embeds the same logic so it can run in a fresh Colab session with
no external files. The Streamlit app imports this module. A consistency test
compares the two.

Strategy
--------
Asset:    SPHQ (Invesco S&P 500 Quality ETF).
Signal:   month-end close above the 200-day simple moving average.
Holding:  100% SPHQ when the signal is on, 100% T-bills when it is off.
Execution: month-end close signal, trade at the open of t + lag (default 2).
Costs:    10 bps per side on traded notional.
"""
from __future__ import annotations

from typing import Iterable, Mapping

import numpy as np
import pandas as pd
import yfinance as yf

TRADING_DAYS = 252
DEFAULT_TICKER = "SPHQ"
DEFAULT_BENCHMARK = "SPY"
DEFAULT_RF = "^IRX"


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def download_prices(
    tickers: Iterable[str] = (DEFAULT_TICKER,),
    start: str = "2008-01-01",
    end: str = "2026-01-01",
    benchmark: str = DEFAULT_BENCHMARK,
    rf_ticker: str = DEFAULT_RF,
) -> dict[str, pd.DataFrame | pd.DatetimeIndex | None]:
    """Download adjusted OHLC data through Yahoo Finance.

    Returns a dictionary with ``open``, ``close``, ``volume`` and ``calendar``.
    The calendar is the benchmark's trading calendar.
    """
    tickers = list(dict.fromkeys(list(tickers)))
    all_tickers = list(dict.fromkeys(tickers + [benchmark, rf_ticker]))

    raw = yf.download(
        all_tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )
    if raw.empty:
        raise ValueError("Yahoo Finance returned no data. Check the tickers and dates.")

    if isinstance(raw.columns, pd.MultiIndex):
        first_level = list(raw.columns.get_level_values(0))
        if "Close" in first_level:
            close = raw["Close"].copy()
            open_ = raw["Open"].copy()
            volume = raw["Volume"].copy() if "Volume" in first_level else None
        else:
            close = raw.xs("Close", axis=1, level=1).copy()
            open_ = raw.xs("Open", axis=1, level=1).copy()
            volume = (
                raw.xs("Volume", axis=1, level=1).copy()
                if "Volume" in raw.columns.get_level_values(1)
                else None
            )
    else:
        if "Close" not in raw.columns:
            raise ValueError("Could not find a Close column in the downloaded data.")
        close = raw[["Close"]].copy()
        open_ = raw[["Open"]].copy()
        volume = raw[["Volume"]].copy() if "Volume" in raw.columns else None
        close.columns = [tickers[0]]
        open_.columns = [tickers[0]]
        if volume is not None:
            volume.columns = [tickers[0]]

    close = close.reindex(columns=all_tickers)
    open_ = open_.reindex(columns=all_tickers)
    if volume is not None:
        volume = volume.reindex(columns=all_tickers)

    if benchmark not in close.columns or close[benchmark].dropna().empty:
        raise ValueError(f"No usable data for benchmark {benchmark}.")

    calendar = close[benchmark].dropna().index
    calendar = calendar.tz_localize(None) if calendar.tz is not None else calendar
    close = close.reindex(calendar)
    open_ = open_.reindex(calendar)
    if volume is not None:
        volume = volume.reindex(calendar)

    return {
        "open": open_,
        "close": close,
        "volume": volume,
        "calendar": calendar,
    }


# --------------------------------------------------------------------------- #
# Signal
# --------------------------------------------------------------------------- #
def compute_sma(close: pd.Series, window: int = 200) -> pd.Series:
    """Simple moving average with a full-window requirement."""
    return close.rolling(window=window, min_periods=window).mean()


def month_end_dates(index: pd.DatetimeIndex, start: str, end: str) -> list[pd.Timestamp]:
    """Last trading day of each month inside the sample."""
    series = pd.Series(index=index, data=index)
    sample = series.loc[pd.Timestamp(start):pd.Timestamp(end)]
    return list(sample.groupby(sample.index.to_period("M")).tail(1).values)


# --------------------------------------------------------------------------- #
# Backtest
# --------------------------------------------------------------------------- #
def run_trend_backtest(
    open_: pd.DataFrame,
    close: pd.DataFrame,
    ticker: str = DEFAULT_TICKER,
    benchmark: str = DEFAULT_BENCHMARK,
    rf_ticker: str = DEFAULT_RF,
    start: str = "2010-01-01",
    end: str = "2025-12-31",
    sma_window: int = 200,
    lag: int = 2,
    cost_bps: float = 10.0,
    initial_cash: float = 100_000.0,
) -> dict:
    """Monthly quality-trend backtest, long-only and all-in/all-cash.

    The signal is the month-end close versus the 200-day SMA. The order is
    executed at the open ``lag`` trading days later. The portfolio holds either
    the ETF or cash, never both, and never uses leverage.
    """
    if lag < 1:
        raise ValueError("lag must be at least 1 trading day.")
    for column in [ticker, benchmark, rf_ticker]:
        if column not in close.columns:
            raise ValueError(f"Missing column: {column}")

    dates = close.index
    start_i = int(dates.searchsorted(pd.Timestamp(start)))
    end_i = int(dates.searchsorted(pd.Timestamp(end), side="right"))
    if start_i >= end_i:
        raise ValueError("start must be before end and inside the price data.")
    base_i = max(start_i - 1, 0)
    has_base = base_i < start_i

    sma = compute_sma(close[ticker], window=sma_window)
    signal = close[ticker] > sma
    op = open_[ticker].to_numpy(float)
    cl = close[ticker].to_numpy(float)

    rf_annual = close[rf_ticker].ffill().to_numpy(float) / 100.0
    rf_daily = (1.0 + rf_annual) ** (1.0 / TRADING_DAYS) - 1.0

    month_ends = month_end_dates(dates, start, end)
    pending: dict[int, tuple[bool, pd.Timestamp]] = {}
    for d in month_ends:
        exec_i = int(dates.searchsorted(d)) + lag
        if exec_i >= end_i:
            continue
        value = signal.loc[d]
        wanted = bool(value) if pd.notna(value) else False
        pending[exec_i] = (wanted, d)

    shares = 0.0
    last_px = np.nan
    cash = float(initial_cash)
    entry_date: pd.Timestamp | None = None
    equity_rows: list[tuple] = []
    trade_rows: list[tuple] = []
    position_rows: list[tuple] = []

    if has_base:
        equity_rows.append((dates[base_i], float(initial_cash), float(initial_cash), 0.0, 0))
        position_rows.append((dates[base_i], 0.0, 0.0))

    for i in range(start_i, end_i):
        dt = dates[i]
        if np.isfinite(cl[i]):
            last_px = cl[i]

        if i in pending:
            wanted, signal_date = pending.pop(i)
            px = op[i]
            if np.isfinite(px) and px > 0:
                if wanted and shares == 0.0:
                    qty = cash / (px * (1.0 + cost_bps / 10_000.0))
                    notional = qty * px
                    fee = notional * cost_bps / 10_000.0
                    cash -= notional + fee
                    shares = qty
                    entry_date = dt
                    trade_rows.append(
                        (signal_date, dt, ticker, "buy", px, notional, fee, 0.0, cash)
                    )
                elif (not wanted) and shares > 0.0:
                    notional = shares * px
                    fee = notional * cost_bps / 10_000.0
                    cash += notional - fee
                    holding_days = (dt - entry_date).days if entry_date is not None else np.nan
                    trade_rows.append(
                        (signal_date, dt, ticker, "sell", px, notional, fee, holding_days, cash)
                    )
                    shares = 0.0
                    entry_date = None

        price = cl[i] if np.isfinite(cl[i]) else last_px
        invested = shares * price
        equity = cash + invested
        equity_rows.append((dt, equity, cash, invested, int(shares > 0)))
        position_rows.append((dt, shares, 1.0 if shares > 0 else 0.0))

        if np.isfinite(rf_daily[i]):
            cash *= 1.0 + rf_daily[i]

    equity = pd.DataFrame(
        equity_rows, columns=["Date", "Equity", "Cash", "Invested", "NPos"]
    ).set_index("Date")
    trades = pd.DataFrame(
        trade_rows,
        columns=[
            "SignalDate", "ExecDate", "Ticker", "Action", "Price",
            "Notional", "Fee", "HoldingDays", "CashAfter",
        ],
    )
    positions = pd.DataFrame(
        position_rows, columns=["Date", "Shares", "Weight"]
    ).set_index("Date")

    benchmark_prices = close[benchmark].loc[equity.index]
    rf_series = pd.Series(rf_daily, index=dates).loc[equity.index]

    return {
        "equity": equity,
        "trades": trades,
        "positions": positions,
        "benchmark": benchmark_prices,
        "rf_daily": rf_series,
        "sma": sma.loc[equity.index],
        "signal": signal.loc[equity.index],
        "params": {
            "ticker": ticker,
            "benchmark": benchmark,
            "rf_ticker": rf_ticker,
            "start": start,
            "end": end,
            "sma_window": sma_window,
            "lag": lag,
            "cost_bps": cost_bps,
            "initial_cash": initial_cash,
        },
    }


# --------------------------------------------------------------------------- #
# Performance
# --------------------------------------------------------------------------- #
def performance_metrics(
    equity: pd.Series | pd.DataFrame,
    benchmark: pd.Series,
    rf_daily: pd.Series,
    periods: int = TRADING_DAYS,
) -> dict:
    """Required performance measures plus supporting evidence.

    Alpha is the annualized regression intercept of daily excess returns.
    Beta is the daily covariance slope and is *not* annualized.
    The information ratio is benchmark-relative: mean(active) / std(active).
    """
    if isinstance(equity, pd.DataFrame):
        equity = equity["Equity"]
    equity = equity.astype(float)
    benchmark = benchmark.astype(float).reindex(equity.index)

    returns = equity.pct_change(fill_method=None).dropna()
    bench_returns = benchmark.pct_change(fill_method=None).reindex(returns.index).dropna()
    returns = returns.reindex(bench_returns.index)
    rf = rf_daily.reindex(returns.index).ffill()

    excess = returns - rf
    bench_excess = bench_returns - rf
    years = len(returns) / periods

    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0
    bench_cagr = (benchmark.iloc[-1] / benchmark.iloc[0]) ** (1.0 / years) - 1.0
    arithmetic = returns.mean() * periods
    bench_arithmetic = bench_returns.mean() * periods

    vol = returns.std(ddof=1) * np.sqrt(periods)
    bench_vol = bench_returns.std(ddof=1) * np.sqrt(periods)

    sharpe = excess.mean() / excess.std(ddof=1) * np.sqrt(periods)
    bench_sharpe = bench_excess.mean() / bench_excess.std(ddof=1) * np.sqrt(periods)

    beta = np.cov(returns, bench_returns, ddof=1)[0, 1] / np.var(bench_returns, ddof=1)
    alpha_daily = excess.mean() - beta * bench_excess.mean()
    alpha = alpha_daily * periods

    x = np.column_stack([np.ones(len(excess)), bench_excess.to_numpy(float)])
    coef, *_ = np.linalg.lstsq(x, excess.to_numpy(float), rcond=None)
    resid = excess.to_numpy(float) - x @ coef
    dof = len(excess) - 2
    sigma2 = float(resid @ resid) / dof
    se_alpha_daily = np.sqrt(sigma2 * np.linalg.inv(x.T @ x)[0, 0])
    alpha_t = float(coef[0] / se_alpha_daily)

    active = returns - bench_returns
    information_ratio = active.mean() / active.std(ddof=1) * np.sqrt(periods)
    tracking_error = active.std(ddof=1) * np.sqrt(periods)

    cumulative = (1.0 + returns).cumprod()
    drawdown = cumulative / cumulative.cummax() - 1.0
    max_drawdown = float(drawdown.min())
    trough = drawdown.idxmin()
    peak = cumulative.loc[:trough].idxmax()

    return {
        "CAGR": float(cagr),
        "BenchmarkCAGR": float(bench_cagr),
        "ArithmeticReturn": float(arithmetic),
        "BenchmarkArithmeticReturn": float(bench_arithmetic),
        "Volatility": float(vol),
        "BenchmarkVolatility": float(bench_vol),
        "Sharpe": float(sharpe),
        "BenchmarkSharpe": float(bench_sharpe),
        "Beta": float(beta),
        "Alpha": float(alpha),
        "AlphaT": alpha_t,
        "InformationRatio": float(information_ratio),
        "TrackingError": float(tracking_error),
        "MaxDrawdown": max_drawdown,
        "MaxDrawdownPeak": peak,
        "MaxDrawdownTrough": trough,
        "Years": float(years),
        "Observations": int(len(returns)),
    }


def policy_benchmark(
    benchmark: pd.Series,
    rf_daily: pd.Series,
    weight: float = 0.50,
    cost_bps: float = 10.0,
    periods: int = TRADING_DAYS,
) -> pd.Series:
    """Monthly-rebalanced ``weight`` benchmark / ``1-weight`` cash portfolio.

    Cash earns the daily risk-free rate. Rebalancing costs are charged on the
    notional traded at each month-end. Returns start at 1 on the first date.
    """
    benchmark = benchmark.astype(float)
    rf = rf_daily.reindex(benchmark.index).ffill().fillna(0.0)
    bench_returns = benchmark.pct_change(fill_method=None).fillna(0.0)

    values = [1.0]
    current_weight = weight
    for i in range(1, len(benchmark)):
        b = float(bench_returns.iloc[i])
        r = float(rf.iloc[i])
        port_return = current_weight * b + (1.0 - current_weight) * r
        current_weight = current_weight * (1.0 + b) / (1.0 + port_return)

        is_month_end = (
            benchmark.index[i].month != benchmark.index[i + 1].month
            if i + 1 < len(benchmark)
            else True
        )
        if is_month_end and i + 1 < len(benchmark):
            turnover = 2.0 * abs(weight - current_weight)
            port_return -= turnover * cost_bps / 10_000.0
            current_weight = weight

        values.append(values[-1] * (1.0 + port_return))
    return pd.Series(values, index=benchmark.index, name="PolicyBenchmark")


def rolling_outcomes(
    equity: pd.Series | pd.DataFrame,
    benchmark: pd.Series,
    window: int = 504,
) -> dict[str, pd.DataFrame | pd.Series]:
    """Overlapping holding-period outcomes, default 24 months (504 days)."""
    if isinstance(equity, pd.DataFrame):
        equity = equity["Equity"]
    equity = equity.astype(float)
    benchmark = benchmark.astype(float).reindex(equity.index)

    strat = (equity.shift(-window) / equity - 1.0).dropna()
    bench = (benchmark.shift(-window) / benchmark - 1.0).dropna().reindex(strat.index)

    summary = pd.DataFrame(
        {
            "Strategy": [
                len(strat), strat.min(), strat.median(), strat.max(), (strat > 0).mean(),
            ],
            "Benchmark": [
                len(bench), bench.min(), bench.median(), bench.max(), (bench > 0).mean(),
            ],
        },
        index=["Windows", "Worst", "Median", "Best", "% Positive"],
    )
    return {"summary": summary, "strategy": strat, "benchmark": bench}


def calendar_returns(equity: pd.Series | pd.DataFrame, benchmark: pd.Series) -> pd.DataFrame:
    """Calendar-year returns; the base year (2009) is dropped."""
    if isinstance(equity, pd.DataFrame):
        equity = equity["Equity"]
    equity = equity.astype(float)
    benchmark = benchmark.astype(float).reindex(equity.index)

    strat = equity.groupby(equity.index.year).last().pct_change()
    bench = benchmark.groupby(benchmark.index.year).last().pct_change()
    out = pd.DataFrame({"Strategy": strat, "Benchmark": bench})
    out.index.name = "Year"
    return out.dropna(how="all")


def trade_summary(trades: pd.DataFrame, equity: pd.DataFrame, periods: int = TRADING_DAYS) -> dict:
    """Turnover, costs and holding-period statistics."""
    if trades.empty:
        return {
            "Trades": 0, "RoundTrips": 0, "Turnover": 0.0,
            "TotalCosts": 0.0, "CostDrag": 0.0, "AverageHoldingDays": np.nan,
        }
    years = (len(equity) - 1) / periods
    average_equity = equity["Equity"].mean()
    total_notional = float(trades["Notional"].sum())
    one_way_turnover = total_notional / 2.0 / average_equity / years
    total_costs = float(trades["Fee"].sum())
    sells = trades[trades["Action"] == "sell"]
    return {
        "Trades": int(len(trades)),
        "RoundTrips": int(len(sells)),
        "Turnover": float(one_way_turnover),
        "TotalCosts": total_costs,
        "CostDrag": total_costs / average_equity / years,
        "AverageHoldingDays": float(sells["HoldingDays"].mean()) if not sells.empty else np.nan,
    }


def validate_backtest(result: Mapping) -> list[str]:
    """Run mechanical checks and return a list of failure messages."""
    failures: list[str] = []
    equity = result["equity"]
    trades = result["trades"]
    positions = result["positions"]

    if (equity["Cash"] < -1e-6).any():
        failures.append("Negative cash: the portfolio used leverage.")
    if (positions["Shares"] < -1e-9).any():
        failures.append("Negative share count: short position detected.")
    diff = (equity["Equity"] - equity["Cash"] - equity["Invested"]).abs().max()
    if diff > 1e-5:
        failures.append(f"Equity != cash + invested (max diff {diff:.6f}).")
    if not trades.empty:
        if (trades["Fee"] < 0).any():
            failures.append("Negative transaction cost.")
        if (pd.to_datetime(trades["ExecDate"]) < pd.to_datetime(trades["SignalDate"])).any():
            failures.append("Trade executed before its signal.")
        if (trades["Notional"] <= 0).any():
            failures.append("Non-positive trade notional.")
    if abs(equity["Equity"].iloc[0] - result["params"]["initial_cash"]) > 1e-6:
        failures.append("Equity curve does not start at the initial cash.")
    # All-in or all-cash: never a partial position.
    partial = (positions["Shares"] > 0) & (equity["Cash"] > 1e-4)
    if partial.any():
        failures.append("Partial position detected: the strategy should be all-in or all-cash.")
    return failures
