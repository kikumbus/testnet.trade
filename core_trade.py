import numpy as np
from binance.client import Client
import talib
from datetime import datetime, timedelta
import pandas as pd
import requests
import math

# Initialize Binance Testnet client
api_key = '62114c155fe5b416a20bcc69947c04320ba67b33177da66f4473307d5eeace3a'
api_secret = '06f866562ac67534f4160f44934f0694852be6468a65f898bb1b14b07c0beecb'
client = Client(api_key, api_secret, testnet=True)

# LINE Bot API settings
LINE_ACCESS_TOKEN = "RawBoDyh+H4Ali8aePaLZFsQ0KzpsvJigkidOEVRpy2c8K4GtwtcRWmAgtmnF1cZyEGNlWJwi/XLyxqMEoCJglDfoDo7N+q7dcNKOxkt6073ZWWysZixGRnfYKbGPlmtc/xRPU9JS+zklXUeURGDJQdB04t89/1O/w1cDnyilFU="
LINE_API_URL = "https://api.line.me/v2/bot/message/push"
LINE_USER_ID = "U9364edfcfe43f9a74ce9ef4639cede32"

# Trading parameters
initial_capital = 1000.0
leverage = 20
risk_per_trade = 0.25
adx_threshold = 8
invest_per_trade = 150  # Fixed investment per trade in USDT

# Function to get all active USDT-paired futures coins
def get_all_usdt_futures_pairs():
    exchange_info = client.futures_exchange_info()
    return {s['symbol']: s for s in exchange_info['symbols'] if s['status'] == 'TRADING' and s['symbol'].endswith('USDT')}

# Function to get historical price data
def get_historical_data(symbol, interval='1h', limit=500):
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    close_prices = [float(kline[4]) for kline in klines]
    high_prices = [float(kline[2]) for kline in klines]
    low_prices = [float(kline[3]) for kline in klines]
    return np.array(close_prices), np.array(high_prices), np.array(low_prices)

# Function to get latest bid/ask price
def get_latest_bid_ask(symbol):
    ticker = client.futures_order_book(symbol=symbol, limit=5)
    return float(ticker['bids'][0][0]), float(ticker['asks'][0][0])

# Function to fetch Binance's price filters (fixed missing key issue)
def get_price_filters(symbol):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            return {
                "tick_size": float(s['filters'][0]['tickSize']),
                "step_size": float(s['filters'][2]['stepSize']),
                "min_notional": float(s['filters'][5]['notional']) if len(s['filters']) > 5 else 100,
                "multiplier_up": float(s['filters'][1].get('multiplierUp', 1.05)),  # Fetch max price limit
                "multiplier_down": float(s['filters'][1].get('multiplierDown', 0.95))  # Fetch min price limit
            }
    return None

def ___get_price_filters(symbol):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            return {
                "tick_size": float(s['filters'][0]['tickSize']),
                "step_size": float(s['filters'][2]['stepSize']),
                "min_notional": float(s['filters'][5]['notional']) if len(s['filters']) > 5 else 100,
                "percent_price_multiplier": float(s['filters'][1].get('multiplierUp', 1.05))  # Default if missing
            }
    return None

# Function to adjust price to Binance's tick size
def adjust_price_to_tick(price, tick_size):
    return round(math.floor(price / tick_size) * tick_size, int(-math.log10(tick_size)))

# Function to adjust quantity to Binance's step size
def adjust_quantity_to_step(quantity, step_size):
    return round(math.floor(quantity / step_size) * step_size, int(-math.log10(step_size)))

# Function to set ISOLATED margin mode only if needed
def set_margin_type(symbol):
    try:
        positions = client.futures_position_information()
        for position in positions:
            if position['symbol'] == symbol and position['isolated'] == "true":
                print(f"✅ {symbol} is already in ISOLATED mode.")
                return  # No need to change
        
        client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
        print(f"✅ Changed margin type to ISOLATED for {symbol}")
    except Exception as e:
        if "No need to change margin type" not in str(e):
            print(f"⚠️ Error setting margin type for {symbol}: {e}")


def _____________set_margin_type(symbol):
    try:
        positions = client.futures_position_information()
        for position in positions:
            if position['symbol'] == symbol:
                if position['isolated'] == "true":  # Correctly checking isolated mode
                    print(f"✅ {symbol} is already in ISOLATED mode.")
                    return  # No need to change
                break  # Stop searching

        client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
        print(f"✅ Changed margin type to ISOLATED for {symbol}")
    except Exception as e:
        if "No need to change margin type" not in str(e):
            print(f"⚠️ Error setting margin type for {symbol}: {e}")

def ___set_margin_type(symbol):
    try:
        positions = client.futures_position_information()
        current_mode = next((x['marginType'] for x in positions if x['symbol'] == symbol), None)
        if current_mode != "ISOLATED":
            client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
            print(f"✅ Changed margin type to ISOLATED for {symbol}")
    except Exception as e:
        if "No need to change margin type" not in str(e):
            print(f"⚠️ Error setting margin type for {symbol}: {e}")

# Function to send LINE notifications
def send_line_message(message):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    data = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message}]
    }
    response = requests.post(LINE_API_URL, headers=headers, json=data)
    if response.status_code == 200:
        print("📩 Sent notification to LINE Bot")
    else:
        print(f"⚠️ Failed to send LINE notification: {response.text}")

# Scan Coins
def scan_coins():
    usdt_symbols = get_all_usdt_futures_pairs()
    profitable_coins = []

    for symbol in usdt_symbols:
        try:
            prices, high_prices, low_prices = get_historical_data(symbol)
            ma_50 = talib.EMA(prices, timeperiod=50)
            ma_200 = talib.SMA(prices, timeperiod=200)
            rsi = talib.RSI(prices, timeperiod=14)
            adx = talib.ADX(high_prices, low_prices, prices, timeperiod=14)

            position = None
            if ma_50[-1] > ma_200[-1] and rsi[-1] < 60 and adx[-1] > adx_threshold:
                position = "BUY"
            elif ma_50[-1] < ma_200[-1] and rsi[-1] > 40 and adx[-1] > adx_threshold:
                position = "SELL"

            if position:
                profitable_coins.append({"symbol": symbol, "position": position})
        except Exception as e:
            print(f"⚠️ Error processing {symbol}: {e}")

    return profitable_coins[:5]

# ✅ Function to round quantity to the nearest step size
def round_step(value, step_size):
    return round(math.floor(value / step_size) * step_size, int(-math.log10(step_size)))

# ✅ Function to round price to the nearest tick size
def round_price(value, tick_size):
    return round(math.floor(value / tick_size) * tick_size, int(-math.log10(tick_size)))

def execute_trades():
    top_coins = scan_coins()
    message = "🔥 Trading Decisions 🔥\n"

    for coin in top_coins:
        symbol = coin['symbol']
        position = coin['position']
        filters = get_price_filters(symbol)
        if not filters:
            print(f"⚠️ Skipping {symbol}: Unable to fetch price filters.")
            continue

        best_bid, best_ask = get_latest_bid_ask(symbol)
        entry_price = best_ask if position == "BUY" else best_bid
        tick_size = filters["tick_size"]
        step_size = filters["step_size"]
        min_notional = filters["min_notional"]
        multiplier_up = filters["multiplier_up"]
        multiplier_down = filters["multiplier_down"]

        # ✅ **Set margin type before trading**
        try:
            set_margin_type(symbol)
        except Exception as e:
            print(f"⚠️ Error setting margin type for {symbol}: {e}")
            continue

        # ✅ **Ensure correct quantity and investment**
        quantity = round_step(invest_per_trade / entry_price, step_size)
        investment = quantity * entry_price

        while investment < min_notional:
            quantity += step_size
            investment = quantity * entry_price

        # ✅ **Ensure TP and SL prices are within Binance’s allowed range**
        tp_price = min(entry_price * 1.05, entry_price * multiplier_up)
        sl_price = max(entry_price * 0.95, entry_price * multiplier_down)

        tp_price = round_price(tp_price, tick_size)
        sl_price = round_price(sl_price, tick_size)

        # ✅ **Fix: Prevent Stop-Loss from being invalid**
        if position == "BUY":
            sl_price = min(sl_price, entry_price - (entry_price * 0.01))
        else:
            sl_price = max(sl_price, entry_price + (entry_price * 0.01))

        # ✅ **Round final values to Binance's precision**
        quantity = round_step(quantity, step_size)
        entry_price = round_price(entry_price, tick_size)

        print(f"📊 Adjusted {symbol} Entry: {entry_price}, Qty: {quantity}")

        try:
            # ✅ **Entry Order**
            order = client.futures_create_order(
                symbol=symbol,
                side="BUY" if position == "BUY" else "SELL",
                type="LIMIT",
                timeInForce="GTC",
                quantity=quantity,
                price=entry_price
            )
            order_id = order['orderId']
            print(f"✅ Order placed for {symbol}, Order ID: {order_id}")

            # ✅ **Stop-Loss Order**
            sl_order = client.futures_create_order(
                symbol=symbol,
                side="SELL" if position == "BUY" else "BUY",
                type="STOP_MARKET",
                stopPrice=sl_price,
                closePosition=True
            )
            sl_order_id = sl_order['orderId']
            print(f"✅ Stop-Loss set for {symbol}, Order ID: {sl_order_id}")

            # ✅ **Take-Profit Order**
            tp_order = client.futures_create_order(
                symbol=symbol,
                side="SELL" if position == "BUY" else "BUY",
                type="LIMIT",
                quantity=quantity,
                price=tp_price,
                timeInForce="GTC"
            )
            tp_order_id = tp_order['orderId']
            print(f"✅ Take-Profit set for {symbol}, Order ID: {tp_order_id}")

            # ✅ **Update LINE Message**
            message += f"\n{symbol}: {position} at {entry_price}\n"
            message += f"📌 Qty: {quantity}\n"
            message += f"🎯 TP: {tp_price} (Order ID: {tp_order_id})\n"
            message += f"🛑 SL: {sl_price} (Order ID: {sl_order_id})\n"
            message += f"✅ Main Order ID: {order_id}\n"

        except Exception as e:
            print(f"⚠️ Error placing order for {symbol}: {e}")
            message += f"\n⚠️ Error placing order for {symbol}: {e}\n"

    # ✅ **Ensure message is not empty before sending**
    if message.strip() != "🔥 Trading Decisions 🔥":
        print("📩 Sending trade information to LINE...")
        send_line_message(message)
    else:
        print("⚠️ No trades were executed. Skipping LINE notification.")

def close_all_positions():
    try:
        positions = client.futures_account()["positions"]
        message = "⚠️ Closing All Positions ⚠️\n"

        for pos in positions:
            symbol = pos["symbol"]
            position_amt = float(pos["positionAmt"])
            if position_amt == 0:
                continue  # Skip if no open position

            side = "BUY" if position_amt < 0 else "SELL"
            best_bid, best_ask = get_latest_bid_ask(symbol)

            # **Get Binance’s Price Filters**
            filters = get_price_filters(symbol)
            tick_size = filters["tick_size"]
            percent_up = filters["multiplier_up"]
            percent_down = filters["multiplier_down"]

            # **Calculate Safe Close Price**
            close_price = best_ask if side == "BUY" else best_bid
            upper_limit = close_price * percent_up
            lower_limit = close_price * percent_down

            # **Adjust Price to Binance’s Allowed Range**
            if side == "BUY":
                close_price = min(close_price, upper_limit)  # Ensure price is within allowed range
            else:
                close_price = max(close_price, lower_limit)

            # Round to the correct tick size
            close_price = adjust_price_to_tick(close_price, tick_size)

            try:
                # **1️⃣ Attempt to Close Position with LIMIT Order**
                close_order = client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type="LIMIT",
                    quantity=abs(position_amt),
                    price=close_price,
                    timeInForce="GTC",
                    reduceOnly=True
                )
                message += f"\n✅ Closed {symbol} {side} @ {close_price} (Qty: {abs(position_amt)})\n"
                print(f"✅ Closed {symbol} position at {close_price}")

            except Exception as e:
                print(f"⚠️ Error closing {symbol} with LIMIT order: {e}")
                message += f"\n⚠️ Error closing {symbol} with LIMIT order: {e}\n"

                # **2️⃣ If LIMIT order fails, use STOP_MARKET order**
                try:
                    stop_order = client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type="STOP_MARKET",
                        quantity=abs(position_amt),
                        stopPrice=close_price,
                        reduceOnly=True
                    )
                    message += f"\n✅ STOP_MARKET order placed for {symbol} at {close_price}\n"
                    print(f"✅ STOP_MARKET order placed for {symbol} at {close_price}")

                except Exception as stop_err:
                    print(f"⚠️ Error closing {symbol} with STOP_MARKET order: {stop_err}")
                    message += f"\n⚠️ Error closing {symbol} with STOP_MARKET order: {stop_err}\n"

                    # **3️⃣ If STOP_MARKET also fails, try MARKET order**
                    try:
                        market_order = client.futures_create_order(
                            symbol=symbol,
                            side=side,
                            type="MARKET",
                            quantity=abs(position_amt)
                        )
                        message += f"\n✅ MARKET order placed for {symbol}\n"
                        print(f"✅ MARKET order placed for {symbol}")

                    except Exception as market_err:
                        print(f"❌ FINAL FAILURE: Could not close {symbol}. Error: {market_err}")
                        message += f"\n❌ FINAL FAILURE: Could not close {symbol}. Error: {market_err}\n"

        send_line_message(message)
    
    except Exception as e:
        print(f"⚠️ Error fetching positions: {e}")

if __name__ == "__main__":
    execute_trades()
    # Run Close Position Script
    #close_all_positions()
