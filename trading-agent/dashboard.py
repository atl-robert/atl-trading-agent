import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="Algorithmic Trading Agent Dashboard", page_icon="📈", layout="wide")

API_URL = "http://127.0.0.1:8000"

st.title("📈 Algorithmic Trading Agent Control Center")
st.markdown("Real-time monitoring, strategy backtesting, audit logging, and performance analytics.")

# Sidebar controls
st.sidebar.header("Agent Configuration")
symbol = st.sidebar.selectbox("Trading Symbol", ["EURUSD=X", "BTC-USD", "AAPL", "GBPUSD=X"])
initial_capital = st.sidebar.number_input("Initial Capital ($)", value=10000.0, step=1000.0)

tab1, tab2, tab3, tab4 = st.tabs(["🚀 Live Execution", "📊 Backtest Simulation", "📜 Trade Journal Audit", "📉 Performance Analytics"])

with tab1:
    st.subheader("Manual Tick Execution")
    st.write(f"Trigger an immediate analysis and trade execution cycle for **{symbol}**.")
    if st.button("Run Execution Tick", type="primary"):
        with st.spinner("Executing trading cycle & broadcasting Telegram alert..."):
            try:
                res = requests.post(f"{API_URL}/api/v1/run-tick?symbol={symbol}&use_live_data=true")
                if res.status_code == 200:
                    data = res.json().get("result", {})
                    st.success("Tick executed successfully!")
                    st.json(data)
                else:
                    st.error(f"Execution failed: {res.text}")
            except Exception as e:
                st.error(f"Could not connect to FastAPI backend: {e}")

with tab2:
    st.subheader("Historical Backtest Engine & Risk Analytics")
    st.write(f"Run a comprehensive historical simulation on **{symbol}** with institutional performance metrics.")
    if st.button("Run Advanced Backtest"):
        with st.spinner("Simulating historical data & computing performance metrics..."):
            try:
                res = requests.post(f"{API_URL}/api/v1/backtest?symbol={symbol}&initial_capital={initial_capital}")
                if res.status_code == 200:
                    results = res.json().get("backtest_results", {})
                    st.success("Backtest simulation completed!")
                    
                    # Metrics Display
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Return", f"{results.get('total_return_pct', 0)}%")
                    col2.metric("Sharpe Ratio", f"{results.get('sharpe_ratio', 0)}")
                    col3.metric("Max Drawdown", f"{results.get('max_drawdown_pct', 0)}%")
                    col4.metric("Win Rate", f"{results.get('win_rate_pct', 0)}%")
                    
                    st.json(results)
                else:
                    st.error(f"Backtest failed: {res.text}")
            except Exception as e:
                st.error(f"Could not connect to backend: {e}")

with tab3:
    st.subheader("SQLite Trade Journal Audit Log")
    st.write("Review past trade signals, entry prices, and execution statuses recorded in your database.")
    try:
        res = requests.get(f"{API_URL}/api/v1/journal?limit=50")
        if res.status_code == 200:
            data = res.json()
            logs = data.get("logs", [])
            if logs:
                df_logs = pd.DataFrame(logs)
                st.dataframe(df_logs, use_container_width=True)
            else:
                st.info("No trade logs found in the database yet.")
        else:
            st.error("Failed to fetch journal logs.")
    except Exception as e:
        st.error(f"Could not connect to backend: {e}")

with tab4:
    st.subheader("Portfolio Performance Analytics")
    st.write("Visualizing execution history and asset entry price distributions.")
    try:
        res = requests.get(f"{API_URL}/api/v1/journal?limit=100")
        if res.status_code == 200:
            logs = res.json().get("logs", [])
            if logs:
                df_analytics = pd.DataFrame(logs)
                df_analytics['timestamp'] = pd.to_datetime(df_analytics['timestamp'])
                
                # Plotly chart of entry prices over time
                fig = px.scatter(
                    df_analytics, 
                    x='timestamp', 
                    y='entry_price', 
                    color='signal', 
                    symbol='regime',
                    title="Executed Trade Entries Over Time",
                    labels={'entry_price': 'Entry Price ($)', 'timestamp': 'Timestamp'}
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Not enough trade data available for visualization yet. Run a few execution ticks first!")
        else:
            st.error("Failed to load performance analytics.")
    except Exception as e:
        st.error(f"Could not connect to backend: {e}")