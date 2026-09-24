"""Trend helpers for the dashboard Analytics tab."""

from __future__ import annotations

import pandas as pd


def successful_quotes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df[(df["status"] == "success") & (df["fare_min"].fillna(0) > 0)].copy()
    if "timestamp" in out.columns:
        ts = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
        out["timestamp"] = ts
        try:
            local = ts.dt.tz_convert("Asia/Kolkata")
        except (TypeError, AttributeError, ValueError):
            local = ts
        out["hour"] = local.dt.hour
        out["weekday"] = local.dt.day_name()
        out["local_time"] = local
    return out


def cheapest_win_rate(df: pd.DataFrame) -> pd.DataFrame:
    """Share of scrape runs where each platform was cheapest."""
    ok = successful_quotes(df)
    if ok.empty or "scrape_run_id" not in ok.columns:
        return pd.DataFrame(columns=["platform", "wins", "runs", "win_rate"])

    winners = (
        ok.sort_values("fare_min")
        .groupby("scrape_run_id", as_index=False)
        .first()[["scrape_run_id", "platform"]]
    )
    total_runs = winners["scrape_run_id"].nunique()
    counts = winners["platform"].value_counts().rename_axis("platform").reset_index(name="wins")
    counts["runs"] = total_runs
    counts["win_rate"] = (counts["wins"] / total_runs * 100).round(1)
    return counts


def hourly_average(df: pd.DataFrame) -> pd.DataFrame:
    ok = successful_quotes(df)
    if ok.empty:
        return pd.DataFrame(columns=["hour", "platform", "fare_min"])
    return (
        ok.groupby(["hour", "platform"], as_index=False)["fare_min"]
        .mean()
        .round(1)
    )


def weekday_average(df: pd.DataFrame) -> pd.DataFrame:
    ok = successful_quotes(df)
    if ok.empty:
        return pd.DataFrame(columns=["weekday", "platform", "fare_min"])
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    agg = (
        ok.groupby(["weekday", "platform"], as_index=False)["fare_min"]
        .mean()
        .round(1)
    )
    agg["weekday"] = pd.Categorical(agg["weekday"], categories=order, ordered=True)
    return agg.sort_values("weekday")
