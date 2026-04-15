from __future__ import annotations

import streamlit as st
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import List, Tuple
import yfinance as yf

st.set_page_config(page_title="Stock Split History", page_icon="📈")
st.title("📈 Stock Split History Checker")


def classify_split(ratio: float) -> str:
    if ratio > 1.0: return "forward"
    if ratio < 1.0: return "reverse"
    return "unknown"


def format_ratio(ratio: float, split_type: str) -> str:
    if ratio <= 0: return f"raw ratio={ratio}"
    frac = Fraction(ratio).limit_denominator(20)
    n, d = frac.numerator, frac.denominator
    return f"{d}-for-{n}"


def ticker_exists(ticker: str) -> bool:
    try:
        hist = yf.Ticker(ticker).history(period="1mo", interval="1d", auto_adjust=False)
        return not hist.empty
    except Exception:
        return False


def get_splits(ticker: str, years: int) -> List[Tuple[str, float, str, str]]:
    stock = yf.Ticker(ticker)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=365 * years + 3)
    hist = stock.history(
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        interval="1d", auto_adjust=False, actions=True,
    )
    if hist.empty or "Stock Splits" not in hist.columns:
        return []
    split_rows = hist[hist["Stock Splits"] != 0].copy()
    if split_rows.empty:
        return []
    results = []
    for dt, row in split_rows.iterrows():
        ratio = float(row["Stock Splits"])
        split_type = classify_split(ratio)
        date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
        results.append((date_str, ratio, format_ratio(ratio, split_type), split_type))
    return results


# --- UI ---
col1, col2 = st.columns([2, 1])
with col1:
    ticker = st.text_input("Ticker Symbol", value="SOXL").strip().upper()
with col2:
    years = st.number_input("Years to check (1-50)", min_value=1, max_value=50, value=10)

if st.button("Check Splits", type="primary"):
    if not ticker:
        st.warning("Please enter a ticker symbol.")
    else:
        with st.spinner(f"Looking up {ticker}..."):
            if not ticker_exists(ticker):
                st.error(f"❌ '{ticker}' does not appear to be a valid ticker.")
            else:
                splits = get_splits(ticker, years)
                if not splits:
                    st.info(f"No splits found for **{ticker}** in the last {years} year(s).")
                else:
                    st.success(f"Found {len(splits)} split(s) for **{ticker}** in the last {years} year(s).")
                    rows = []
                    for date_str, raw_ratio, ratio_text, split_type in splits:
                        rows.append({
                            "Date": date_str,
                            "Ratio": ratio_text,
                            "Type": split_type,
                            "Raw Ratio": raw_ratio,
                        })
                    st.table(rows)
