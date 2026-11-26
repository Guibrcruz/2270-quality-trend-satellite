from io import BytesIO
from unittest.mock import patch

import numpy as np
import pandas as pd

import portfolio as pf


def test_yield_trend():
    data = BytesIO(
        b"observation_date,DGS3\n"
        b"2024-08-29,3.5\n2024-08-30,3.0\n2024-09-03,3.0\n2024-09-30,4.0\n"
    )
    with patch.object(pf, "urlopen", return_value=data):
        monthly = pf.download_month_end_3y_yield("2024-08-01", "2024-09-30")
    assert monthly.tolist() == [3.5, 3.0]

    monthly.loc[pd.Timestamp("2024-10-31")] = 3.0
    monthly.loc[pd.Timestamp("2024-11-30")] = 4.0
    _, trend = pf.yield_trend_targets(
        monthly, equity_if_falling=0.3, second_if_falling="SPHQ", first_if_rising="RSP",
    )
    assert np.allclose(trend.sum(axis=1), 1.0)
    assert np.allclose(trend["BND"], [0.7, 0.7, 0.3])
    assert trend.drop(columns="BND").idxmax(axis=1).tolist() == ["SPY", "SPY", "RSP"]

    dates = pd.to_datetime([
        "2024-08-30", "2024-09-03", "2024-09-04", "2024-09-05", "2024-09-30",
        "2024-10-01", "2024-10-02", "2024-10-03",
    ])
    prices = pd.DataFrame(
        {"SPY": [100, 105, 110, 130, 130, 130, 160, 120],
         "BND": [100, 100, 100, 100, 100, 100, 100, 150]},
        index=dates,
    )
    targets = pd.DataFrame(
        {"SPY": [1.0, 0.0], "BND": [0.0, 1.0]},
        index=pd.to_datetime(["2024-08-31", "2024-09-30"]),
    )
    result = pf.run_monthly_etf_backtest(prices, targets, initial_cash=1000, cost_bps=10)
    trades = result["trades"]
    equity = result["equity"]["Equity"]
    assert trades["ExecDate"].tolist() == [dates[2], dates[6], dates[6]]
    assert trades["Action"].tolist() == ["buy", "sell", "buy"]
    assert equity.iloc[:2].tolist() == [1000, 1000]
    assert np.isclose(equity.iloc[2], 1000 / 1.001)
    assert np.allclose(trades["Fee"], trades["Notional"] * 0.001)
    mark_before_trade = equity.iloc[5] * 160 / 130
    assert np.isclose(equity.iloc[6], mark_before_trade - trades["Fee"].iloc[1:].sum())
    assert np.isclose(equity.iloc[7], equity.iloc[6] * 1.5)


if __name__ == "__main__":
    test_yield_trend()
    print("Yield trend checks passed.")
