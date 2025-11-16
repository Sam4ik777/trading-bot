from flask import Flask, request
import alpaca_trade_api as tradeapi
import requests
import logging
import sqlite3
from datetime import datetime

# --- CONFIG ---
API_KEY = "PKBBURTVQLLWHOUSYOCM7JTDY2"
API_SECRET = "FQsuGxCP3mVdP6Z2toUXBpi3HyG7ipHU3JtwTQEBLh9"
BASE_URL = "https://paper-api.alpaca.markets"  # Paper trading
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"
DB_PATH = "trades.db"

# --- INIT ---
app = Flask(__name__)
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL)
logging.basicConfig(filename='trades.log', level=logging.INFO)

# --- DB Setup ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            strategy_name TEXT,
            symbol TEXT,
            entry_price REAL,
            exit_price REAL,
            quantity INTEGER,
            profit_loss REAL,
            risk_reward REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            equity REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- FUNCTIONS ---
def send_telegram(message):
    """Send a message to Telegram bot."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})

def log_trade(strategy_name, symbol, entry_price, exit_price, quantity, risk_reward):
    """Log trade details into SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    profit_loss = (exit_price - entry_price) * quantity

    cursor.execute('''
        INSERT INTO trades (timestamp, strategy_name, symbol, entry_price, exit_price, quantity, profit_loss, risk_reward)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, strategy_name, symbol, entry_price, exit_price, quantity, profit_loss, risk_reward))

    conn.commit()
    conn.close()
    print(f"✅ Trade logged: {strategy_name}, {symbol}, P/L: {profit_loss}")

def log_account_equity():
    """Log current account equity to SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    account = api.get_account()
    equity = float(account.equity)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('INSERT INTO equity_log (timestamp, equity) VALUES (?, ?)', (timestamp, equity))
    conn.commit()
    conn.close()
    print(f"📈 Equity logged: {equity}")

# --- ROUTES ---
@app.route('/webhook', methods=['POST'])
def webhook():
    """Receive TradingView webhook and execute trade."""
    data = request.json
    signal = data.get('signal')
    symbol = data.get('symbol')
    price = float(data.get('price', 0))

    qty = 1  # Static quantity for now
    try:
        if signal == "BUY":
            api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc')
            msg = f"✅ BUY order placed for {symbol} at approx {price}"
            log_trade("TrendPullback", symbol, price, price, qty, 2.0)

        elif signal == "SELL":
            api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
            msg = f"✅ SELL order placed for {symbol} at approx {price}"
            log_trade("TrendPullback", symbol, price, price, qty, 2.0)

        else:
            msg = "⚠️ Invalid signal received."

        # Log equity after trade
        log_account_equity()

        logging.info(msg)
        send_telegram(msg)
        return {"status": "success", "message": msg}
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        logging.error(error_msg)
        send_telegram(error_msg)
        return {"status": "error", "message": error_msg}

@app.route('/account', methods=['GET'])
def account_info():
    """Return current account equity and open positions."""
    try:
        account = api.get_account()
        positions = api.list_positions()
        positions_data = [
            {
                "symbol": p.symbol,
                "qty": p.qty,
                "unrealized_pl": p.unrealized_pl,
                "current_price": p.current_price
            }
            for p in positions
        ]
        return {
            "equity": account.equity,
            "cash": account.cash,
            "positions": positions_data
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
