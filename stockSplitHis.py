#!/usr/bin/env python3
"""
Check whether a ticker is valid and report stock splits in the last 10 years.

Requires:
    pip install yfinance pandas
"""

from __future__ import annotations

import os
import webbrowser
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

import pandas as pd
import yfinance as yf


def classify_split(ratio: float) -> str:
    """
    Classify a split ratio.

    In Yahoo/yfinance split data:
    - ratio > 1.0 usually means a forward split (e.g. 4.0 => 4-for-1)
    - ratio < 1.0 usually means a reverse split (e.g. 0.1 => 1-for-10)
    """
    if ratio > 1.0:
        return "forward"
    if ratio < 1.0:
        return "reverse"
    return "unknown"


def format_ratio(ratio: float, split_type: str) -> str:
    """
    Forward splits: 1-for-4 (smaller-for-larger)
    Reverse splits: 10-for-1 (larger-for-smaller)
    Both cases use d-for-n from the Fraction representation.
    """
    if ratio <= 0:
        return f"raw ratio={ratio}"

    from fractions import Fraction

    frac = Fraction(ratio).limit_denominator(1000)
    n, d = frac.numerator, frac.denominator
    if d == 1000 or n == 1000:
        if split_type == "reverse":
            return f"{round(1/ratio)}-for-1 (approx)"
        return f"1-for-{round(ratio)} (approx)"
    return f"{d}-for-{n}"


def ticker_exists(ticker: str) -> Tuple[bool, str]:
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo", interval="1d", auto_adjust=False)

        if not hist.empty:
            return True, "Found recent market data."

        return False, "No market data found for this ticker."

    except Exception as exc:
        return False, f"Lookup error: {exc}"


def get_splits(ticker: str, years: int) -> List[Tuple[str, float, str, str]]:
    """
    Return split events in the last `years` years as:
    (date_str, raw_ratio, ratio_text, split_type)
    """
    stock = yf.Ticker(ticker)

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=365 * years + 3)

    # history(actions=True) includes a 'Stock Splits' column
    hist = stock.history(
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=False,
        actions=True,
    )

    if hist.empty or "Stock Splits" not in hist.columns:
        return []

    split_rows = hist[hist["Stock Splits"] != 0].copy()
    if split_rows.empty:
        return []

    results: List[Tuple[str, float, str, str]] = []

    for dt, row in split_rows.iterrows():
        ratio = float(row["Stock Splits"])
        split_type = classify_split(ratio)
        ratio_text = format_ratio(ratio, split_type)

        # Normalize timestamp display
        if hasattr(dt, "strftime"):
            date_str = dt.strftime("%Y-%m-%d")
        else:
            date_str = str(dt)

        results.append((date_str, ratio, ratio_text, split_type))

    return results


def generate_html(ticker: str, years: int, splits: List[Tuple[str, float, str, str]]) -> str:
    """Build an HTML report and return the file path."""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if splits:
        rows = ""
        for date_str, raw_ratio, ratio_text, split_type in splits:
            badge_color = "#2ecc71" if split_type == "forward" else "#e74c3c"
            rows += f"""
            <tr>
                <td>{date_str}</td>
                <td>{ratio_text}</td>
                <td><span style="background:{badge_color};color:#fff;padding:2px 10px;border-radius:12px;font-size:0.85em">{split_type}</span></td>
                <td>{raw_ratio}</td>
            </tr>"""
        table = f"""
        <table>
            <thead><tr><th>Date</th><th>Ratio</th><th>Type</th><th>Raw Ratio</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>"""
    else:
        table = f'<p class="none">No splits found for <strong>{ticker}</strong> in the last {years} year(s).</p>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Split History — {ticker}</title>
<style>
  body {{ font-family: Arial, sans-serif; background: #f4f6f9; color: #333; margin: 0; padding: 30px; }}
  .card {{ background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,.1); max-width: 700px; margin: auto; padding: 30px; }}
  h1 {{ margin: 0 0 4px; font-size: 1.8em; }}
  .sub {{ color: #888; font-size: 0.9em; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #2c3e50; color: #fff; padding: 10px 14px; text-align: left; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #eee; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f9f9f9; }}
  .none {{ color: #888; font-style: italic; }}
  .footer {{ text-align: center; color: #bbb; font-size: 0.8em; margin-top: 20px; }}
</style>
</head>
<body>
<div class="card">
  <h1>{ticker} — Split History</h1>
  <div class="sub">Last {years} year(s) &nbsp;|&nbsp; Generated: {generated}</div>
  {table}
</div>
<div class="footer">Data via yfinance</div>
</body>
</html>"""

    path = os.path.abspath(f"split_{ticker}.html")
    with open(path, "w") as f:
        f.write(html)
    return path


def main() -> None:
    while True:
        ticker = input("\nEnter a ticker symbol (or 'q' to quit): ").strip().upper()

        if ticker in ("Q", "QUIT", "EXIT", ""):
            print("Goodbye.")
            break

        exists, message = ticker_exists(ticker)
        print(f"\nTicker check for '{ticker}': {message}")

        if not exists:
            print("Result: ticker does not appear to be valid.")
            continue

        print("Result: ticker appears valid.")

        years_input = input("\n How many years back to check? : ").strip()
        try:
            years = int(years_input)
            if years <= 0:
                raise ValueError
        except ValueError:
            print("Error: please enter a positive whole number for years.")
            continue

        try:
            splits = get_splits(ticker, years)

            if not splits:
                print(f"\nNo forward or reverse splits found for {ticker} in the last {years} year(s).")
            else:
                print(f"\nSplit history for {ticker} in the last {years} year(s):")
                for date_str, raw_ratio, ratio_text, split_type in splits:
                    print(f"  - {date_str}: {ratio_text} ({split_type} split, raw ratio={raw_ratio})")

            path = generate_html(ticker, years, splits)
            print(f"\nHTML report saved: {path}")
            webbrowser.open(f"file://{path}")

        except Exception as exc:
            print(f"\nError while retrieving split history: {exc}")


if __name__ == "__main__":
    main()


