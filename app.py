from __future__ import annotations

import streamlit as st
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import List, Tuple
import yfinance as yf

st.set_page_config(page_title="Stock Split History", page_icon="📈")
st.title("📈 Stock Split History Checker")
st.caption("⚠️ Data is sourced from the selected provider. It may be incomplete or inaccurate. Use this tool with caution and verify important information independently.")
st.divider()


def classify_split(ratio: float) -> str:
    if ratio > 1.0: return "forward"
    if ratio < 1.0: return "reverse"
    return "unknown"


def format_ratio(ratio: float, split_type: str) -> str:
    if ratio <= 0: return f"raw ratio={ratio}"
    frac = Fraction(ratio).limit_denominator(20)
    n, d = frac.numerator, frac.denominator
    return f"{d}-for-{n}"


# --- Yahoo Finance ---
def ticker_exists_yahoo(ticker: str) -> bool:
    try:
        hist = yf.Ticker(ticker).history(period="1mo", interval="1d", auto_adjust=False)
        return not hist.empty
    except Exception:
        return False


def get_splits_yahoo(ticker: str, years: int) -> List[Tuple[str, float, str, str, str]]:
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
        close = row.get("Close", None)
        price_str = f"${close:.2f}" if close is not None else "N/A"
        results.append((date_str, ratio, format_ratio(ratio, split_type), split_type, price_str))
    return results


# --- Polygon ---
def ticker_exists_polygon(ticker: str, api_key: str) -> bool:
    try:
        from polygon import RESTClient
        client = RESTClient(api_key=api_key)
        splits = list(client.list_splits(ticker=ticker, limit=1))
        # also verify ticker has recent data
        return True  # if no exception, ticker is valid
    except Exception:
        return False


def get_splits_polygon(ticker: str, years: int, api_key: str) -> List[Tuple[str, float, str, str, str]]:
    from polygon import RESTClient
    client = RESTClient(api_key=api_key)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=365 * years + 3)
    splits_raw = list(client.list_splits(
        ticker=ticker,
        execution_date_gte=start_date.strftime("%Y-%m-%d"),
        execution_date_lte=end_date.strftime("%Y-%m-%d"),
        limit=100,
    ))
    if not splits_raw:
        return []
    results = []
    for s in sorted(splits_raw, key=lambda x: x.execution_date):
        split_to = s.split_to
        split_from = s.split_from
        ratio = split_to / split_from
        split_type = classify_split(ratio)
        results.append((s.execution_date, ratio, format_ratio(ratio, split_type), split_type, "N/A"))
    return results


# --- UI ---
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    ticker = st.text_input("Ticker Symbol", value="SOXL").strip().upper()
with col2:
    years = st.number_input("Years to check (1-50)", min_value=1, max_value=50, value=10)
with col3:
    source = st.selectbox("Data Source", ["Yahoo Finance", "Polygon.io"])

if st.button("Check Splits", type="primary"):
    if not ticker:
        st.warning("Please enter a ticker symbol.")
    else:
        with st.spinner(f"Looking up {ticker} via {source}..."):
            if source == "Yahoo Finance":
                valid = ticker_exists_yahoo(ticker)
                splits = get_splits_yahoo(ticker, years) if valid else []
            else:
                api_key = st.secrets.get("POLYGON_API_KEY", "")
                if not api_key:
                    st.error("Polygon API key not configured.")
                    st.stop()
                valid = ticker_exists_polygon(ticker, api_key)
                splits = get_splits_polygon(ticker, years, api_key) if valid else []

            if not valid:
                st.error(f"❌ Cannot retrieve information for ticker '{ticker}'.")
            elif not splits:
                st.info(f"No splits found for **{ticker}** in the last {years} year(s).")
            else:
                st.success(f"Found {len(splits)} split(s) for **{ticker}** in the last {years} year(s).")
                rows = []
                for date_str, raw_ratio, ratio_text, split_type, price_str in splits:
                    rows.append({
                        "Date": date_str,
                        "Ratio": ratio_text,
                        "Type": split_type,
                        "Raw Ratio": raw_ratio,
                        "Price After Split": price_str,
                    })
                st.table(rows)

st.divider()
st.caption("💡 Tip: If a valid ticker shows as invalid or returns no data, try clicking 'Check Splits' again. The data provider can occasionally be slow to respond.")
