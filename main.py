

import os
import requests
import time
from datetime import datetime, time as dt_time
import pytz

# Load credentials from Replit secrets
ACCOUNT_ID = os.environ['OANDA_ACCOUNT_ID']
API_KEY = os.environ['OANDA_API_KEY']
BASE_URL = os.environ['OANDA_API_URL']

HEADERS = {
    "Authorization": f"Bearer {API_KEY}"
}

INSTRUMENT = "EUR_USD"
UNITS = 1000  # Adjust position size as needed

DAILY_MAX_LOSS = 2.0
DAILY_PROFIT_TARGET = 40.0

def get_candles(count=20, granularity='M5'):
    url = f"{BASE_URL}/v3/instruments/{INSTRUMENT}/candles"
    params = {
        "count": count,
        "granularity": granularity,
        "price": "M"
    }
    r = requests.get(url, headers=HEADERS, params=params)
    if r.status_code == 200:
        data = r.json()
        return data['candles']
    else:
        print("Error fetching candles:", r.text)
        return []

def is_trading_time():
    # Define EST timezone
    est = pytz.timezone('US/Eastern')
    now = datetime.now(est).time()
    start_time = dt_time(8, 0)  # 8:00 AM
    end_time = dt_time(10, 0)   # 10:00 AM
    current_est_time = datetime.now(est).strftime("%H:%M:%S EST")
    print(f"🕐 Current time: {current_est_time}")
    return start_time <= now <= end_time

# Calculate simple moving average
def sma(prices, period):
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

# Place market order
def place_order(units):
    url = f"{BASE_URL}/v3/accounts/{ACCOUNT_ID}/orders"
    data = {
        "order": {
            "units": str(units),
            "instrument": INSTRUMENT,
            "timeInForce": "FOK",
            "type": "MARKET",
            "positionFill": "DEFAULT"
        }
    }
    r = requests.post(url, headers=HEADERS, json=data)
    if r.status_code in [200, 201]:
        print(f"✅ Order placed: {'BUY' if units > 0 else 'SELL'} {abs(units)} units")
        return True
    else:
        print("❌ Order failed:", r.text)
        return False

# Fetch all open trades
def get_open_trades():
    url = f"{BASE_URL}/v3/accounts/{ACCOUNT_ID}/openTrades"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        return r.json().get("trades", [])
    else:
        print("Error getting open trades:", r.text)
        return []

# Close all trades (used on stop or profit hit)
def close_all_trades():
    trades = get_open_trades()
    for trade in trades:
        trade_id = trade["id"]
        url = f"{BASE_URL}/v3/accounts/{ACCOUNT_ID}/trades/{trade_id}/close"
        r = requests.put(url, headers=HEADERS)
        if r.status_code == 200:
            print(f"🛑 Closed trade {trade_id}")
        else:
            print(f"⚠️ Failed to close trade {trade_id}: {r.text}")

# Get account summary for P&L tracking
def get_account_summary():
    url = f"{BASE_URL}/v3/accounts/{ACCOUNT_ID}/summary"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        return r.json()["account"]
    else:
        print("Error getting account summary:", r.text)
        return None

# Main trading logic
def trading_strategy():
    daily_pnl = 0.0
    print(f"🚀 Starting OANDA Trading Bot for {INSTRUMENT}")
    print(f"📊 Daily targets: Max Loss: ${DAILY_MAX_LOSS}, Profit Target: ${DAILY_PROFIT_TARGET}")


    while True:
        try:
            # Check if within trading hours
            if not is_trading_time():
                print("⏸️ Outside trading hours (8-10 AM EST). Waiting...")
                time.sleep(60)
                continue

            # Check daily P&L limits
            account = get_account_summary()
            if account:
                current_pnl = float(account.get("unrealizedPL", 0))
                daily_pnl = current_pnl

                if daily_pnl <= -DAILY_MAX_LOSS:
                    print(f"🛑 Daily max loss hit: ${daily_pnl:.2f}")
                    close_all_trades()
                    break

                if daily_pnl >= DAILY_PROFIT_TARGET:
                    print(f"🎯 Daily profit target reached: ${daily_pnl:.2f}")
                    close_all_trades()
                    break

            # Get market data
            candles = get_candles(count=20, granularity='M5')
            if not candles:
                time.sleep(60)
                continue

            # Extract closing prices
            prices = []
            for candle in candles:
                if candle['complete']:
                    prices.append(float(candle['mid']['c']))

            if len(prices) < 10:
                print("⏳ Not enough data for analysis")
                time.sleep(60)
                continue

            # Calculate SMAs
            sma_short = sma(prices, 5)
            sma_long = sma(prices, 10)
            current_price = prices[-1]

            print(f"📈 Price: {current_price:.5f} | SMA5: {sma_short:.5f} | SMA10: {sma_long:.5f} | P&L: ${daily_pnl:.2f}")

            # Check for open trades
            open_trades = get_open_trades()

            # Trading logic: SMA crossover
            if sma_short and sma_long:
                if len(open_trades) == 0:  # No open positions
                    if sma_short > sma_long:  # Bullish signal
                        print("📊 Bullish signal detected - placing BUY order")
                        place_order(UNITS)
                    elif sma_short < sma_long:  # Bearish signal
                        print("📊 Bearish signal detected - placing SELL order")
                        place_order(-UNITS)
                else:
                    # Check if we should close current position
                    for trade in open_trades:
                        trade_units = int(trade["currentUnits"])
                        unrealized_pnl = float(trade["unrealizedPL"])

                        # Close long position if bearish signal
                        if trade_units > 0 and sma_short < sma_long:
                            print("🔄 Closing long position due to bearish signal")
                            close_all_trades()

                        # Close short position if bullish signal
                        elif trade_units < 0 and sma_short > sma_long:
                            print("🔄 Closing short position due to bullish signal")
                            close_all_trades()

            time.sleep(300)  # Wait 5 minutes before next analysis

        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user")
            close_all_trades()
            break
        except Exception as e:
            print(f"⚠️ Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    trading_strategy()

