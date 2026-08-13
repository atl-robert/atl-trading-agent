import streamlit as st
import pandas as pd
import numpy as np
import datetime

# Page Configuration
st.set_page_config(
    page_title="Algorithmic Trading Dashboard",
    page_icon="📈",
    layout="wide"
)

# App Title & Overview
st.title("📊 Trading Bot & Portfolio Dashboard")
st.markdown("Real-time monitoring for your automated strategies, historical backtests, and active trade journal.")

# Sidebar Navigation / Controls
st.sidebar.header("Dashboard Controls")
selected_tab = st.sidebar.radio(
    "Select View",
    ["Overview", "Trade Journal", "Backtest Analyzer", "Strategy Parameters"]
)

# ---------------------------------------------------------
# MOCK DATA GENERATION (Replace with your actual backend data)
# ---------------------------------------------------------
@st.cache_data
def load_mock_data():
    # Equity curve data
    dates = pd.date_range(start="2026-01-01", periods=60, freq="D")
    # Simulate a rough initial backtest drawdown that recovers
    np.random.seed(42)
    returns = np.random.normal(loc=0.001, scale=0.02, size=60)
    equity = 10000 * (1 + returns).cumprod()
    
    # Trade journal logs
    trades_df = pd.DataFrame({
        "ID": [1, 2, 3, 4],
        "Timestamp": pd.date_range(end=datetime.datetime.now(), periods=4, freq="h"),
        "Symbol": ["BTC/USD", "ETH/USD", "SOL/USD", "BTC/USD"],
        "Side": ["BUY", "SELL", "BUY", "BUY"],
        "Amount": [0.1, 1.5, 12.0, 0.2],
        "Price": [64200.50, 3450.20, 142.80, 65100.00],
        "Status": ["CLOSED", "CLOSED", "CLOSED", "ACTIVE"]
    })
    return dates, equity, trades_df

dates, equity, trades_df = load_mock_data()

# ---------------------------------------------------------
# TAB 1: OVERVIEW
# ---------------------------------------------------------
if selected_tab == "Overview":
    st.subheader("Portfolio Performance & Key Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Portfolio Value", "$11,245.80", "+12.45%")
    col2.metric("Active Positions", "1", "BTC/USD")
    col3.metric("Win Rate (60d)", "54.2%", "+2.1%")
    col4.metric("Max Drawdown", "-32.1%", "High Risk")
    
    st.markdown("---")
    st.subheader("Equity Curve (Last 60 Days)")
    
    # Plotting equity over time
    chart_data = pd.DataFrame({"Equity ($)": equity}, index=dates)
    st.line_chart(chart_data)

# ---------------------------------------------------------
# TAB 2: TRADE JOURNAL
# ---------------------------------------------------------
elif selected_tab == "Trade Journal":
    st.subheader("Active & Historical Trade Logs")
    st.markdown("Here are the recorded executions logged from your bot execution engine:")
    
    st.dataframe(trades_df, use_container_width=True)
    
    if st.button("Refresh Trade Logs"):
        st.success("Trade logs successfully synchronized with database!")

# ---------------------------------------------------------
# TAB 3: BACKTEST ANALYZER
# ---------------------------------------------------------
elif selected_tab == "Backtest Analyzer":
    st.subheader("Strategy Backtest Results")
    st.markdown("Analyze historical stress-testing parameters and risk metrics.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("### Simulation Parameters")
        st.text("Initial Capital: $10,000.00")
        st.text("Strategy: Moving Average Crossover (Fast/Slow)")
        st.text("Timeframe: 60 Days")
    
    with col2:
        st.write("### Performance Report")
        st.warning("⚠️ Warning: Significant historical drawdown detected ($3,211 low point). Consider tightening your stop-loss parameters.")
        st.metric("Ending Backtest Balance", "$3,211.45", "-67.8%")

# ---------------------------------------------------------
# TAB 4: STRATEGY PARAMETERS
# ---------------------------------------------------------
elif selected_tab == "Strategy Parameters":
    st.subheader("Live Strategy Tuning")
    
    with st.form("strategy_form"):
        st.write("Adjust live execution parameters:")
        fast_ma = st.slider("Fast Moving Average Window", min_value=5, max_value=50, value=10)
        slow_ma = st.slider("Slow Moving Average Window", min_value=20, max_value=200, value=50)
        stop_loss_pct = st.slider("Stop Loss Threshold (%)", min_value=1.0, max_value=10.0, value=3.0)
        
        submitted = st.form_submit_button("Save & Deploy Parameters")
        if submitted:
            st.success(f"Strategy successfully updated! Fast MA: {fast_ma}, Slow MA: {slow_ma}, Stop Loss: {stop_loss_pct}%")