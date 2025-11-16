import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
import requests
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
API_URL = "http://localhost:5000/account"  # bot.py endpoint for account info
DB_PATH = "trades.db"

# Auto-refresh every 10 seconds
st_autorefresh(interval=10000, limit=None, key="refresh")

# --- FUNCTIONS ---
def fetch_trades(month=None, year=None):
    conn = sqlite3.connect(DB_PATH)
    query = 'SELECT * FROM trades'
    params = []
    if month and year:
        query += ' WHERE strftime("%m", timestamp) = ? AND strftime("%Y", timestamp) = ?'
        params = [f"{month:02d}", str(year)]
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def fetch_account_info():
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception:
        return None

# --- DASHBOARD ---
st.title("Trading Bot Performance Dashboard")

# Sidebar filters
month = st.sidebar.selectbox("Select Month", list(range(1, 13)), index=datetime.now().month - 1)
year = st.sidebar.selectbox("Select Year", [datetime.now().year])

# Fetch trades
trades_df = fetch_trades(month, year)

# Fetch account info
account_info = fetch_account_info()

if trades_df.empty:
    st.warning("No trades found for this period.")
else:
    # Metrics
    total_trades = len(trades_df)
    wins = len(trades_df[trades_df['profit_loss'] > 0])
    win_rate = (wins / total_trades) * 100
    total_profit_loss = trades_df['profit_loss'].sum()
    avg_rr = trades_df['risk_reward'].mean()

    st.subheader("Monthly Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Trades", total_trades)
    col2.metric("Win Rate", f"{win_rate:.2f}%")
    col3.metric("Total P/L", f"{total_profit_loss:.2f}")
    col4.metric("Avg Risk/Reward", f"{avg_rr:.2f}")

    # Strategy breakdown
    st.subheader("Strategy Breakdown")
    strategy_stats = trades_df.groupby('strategy_name').agg({
        'profit_loss': ['sum', 'mean'],
        'risk_reward': 'mean',
        'id': 'count'
    })
    strategy_stats_reset = strategy_stats.reset_index()
    strategy_stats_reset.columns = ['strategy_name', 'profit_loss_sum', 'profit_loss_mean', 'risk_reward_mean', 'trade_count']
    st.dataframe(strategy_stats_reset)

    # Charts
    st.subheader("Charts")

    # Equity curve
    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
    trades_df = trades_df.sort_values('timestamp')
    trades_df['cumulative_pl'] = trades_df['profit_loss'].cumsum()

    fig_equity = px.line(trades_df, x='timestamp', y='cumulative_pl', title='Live Equity Curve', markers=True)
    fig_equity.update_layout(yaxis_title='Cumulative P/L', xaxis_title='Time')

    # Overlay Alpaca account equity if available
    if account_info:
        alpaca_equity = float(account_info.get("equity", 0))
        fig_equity.add_hline(y=alpaca_equity, line_dash="dot", annotation_text="Current Account Equity")

    st.plotly_chart(fig_equity, use_container_width=True)

    # Win rate by strategy
    win_rate_by_strategy = trades_df.groupby('strategy_name').apply(lambda x: (x['profit_loss'] > 0).mean() * 100).reset_index(name='win_rate')
    fig_win_rate = px.bar(win_rate_by_strategy, x='strategy_name', y='win_rate', title='Win Rate by Strategy')
    st.plotly_chart(fig_win_rate)

    # Profit/Loss per strategy
    fig_pl = px.bar(strategy_stats_reset, x='strategy_name', y='profit_loss_sum', title='Total P/L per Strategy')
    st.plotly_chart(fig_pl)

    # Export to CSV
    st.download_button("Download Report as CSV", trades_df.to_csv(index=False), file_name=f"monthly_report_{year}_{month}.csv")

# --- Positions Table ---
st.subheader("Open Positions")
if account_info and account_info.get("positions"):
    positions_df = pd.DataFrame(account_info["positions"])
    st.dataframe(positions_df)
else:
    st.info("No open positions or unable to fetch account info.")