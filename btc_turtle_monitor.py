#!/usr/bin/env python3
import time
import requests
from datetime import datetime, timezone

# ===== 配置区域 =====
SYMBOL = "bitcoin"
CURRENCY = "usd"

INTERVAL_SECONDS = 60          # 每隔 60 秒拉一次价格
ENTRY_LOOKBACK = 20            # N：入场窗口长度（N 根 bar）
EXIT_LOOKBACK = 10             # M：出场窗口长度（M 根 bar）

MIN_HISTORY = max(ENTRY_LOOKBACK, EXIT_LOOKBACK) + 1

# ===== 状态变量 =====
prices = []        # 历史收盘价（简单用每分钟价格代替）
position = 0       # 0 = 空仓, 1 = 多头持仓
last_signal = None # "BUY" / "SELL" / None


def now_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def fetch_price():
    """
    从 CoinGecko 获取当前 BTC/USD 价格
    文档: https://www.coingecko.com/en/api/documentation
    """
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": SYMBOL,
        "vs_currencies": CURRENCY
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return float(data[SYMBOL][CURRENCY])
    except Exception as e:
        print(f"[{now_str()}] [ERROR] Fetch price failed: {e}")
        return None


def generate_signal():
    """
    根据海龟交易法生成信号:
    - 最近 N 根的最高价突破 → BUY
    - 最近 M 根的最低价跌破 → SELL
    """
    if len(prices) < MIN_HISTORY:
        return None

    # 最近一根收盘价
    close = prices[-1]

    # N 根内的最高价（不含当前这一根）
    recent_high = max(prices[-ENTRY_LOOKBACK-1:-1])
    # M 根内的最低价
    recent_low = min(prices[-EXIT_LOOKBACK-1:-1])

    global position

    # 空仓 → 突破 20 日高点 → 开多
    if position == 0 and close > recent_high:
        return "BUY"

    # 持多 → 跌破 10 日低点 → 平仓
    if position == 1 and close < recent_low:
        return "SELL"

    return None


import subprocess


def send_signal_notification(signal: str, price: float):
    """信号通知：通过本机 openclaw CLI 发送 WhatsApp 消息。"""
    msg = (
        f"[BTC 海龟信号]\n"
        f"时间: {now_str()}\n"
        f"信号: {signal}\n"
        f"价格: {price:.2f} USD\n"
    )

    try:
        subprocess.run(
            [
                "openclaw", "message", "send",
                "--channel=whatsapp",
                "--target=+85268231734",
                "--message", msg,
            ],
            check=True,
        )
        print(f"[NOTIFY_SENT] {msg}")
    except Exception as e:
        print(f"[NOTIFY_ERROR] {e}")


def main_loop():
    global position, last_signal

    print(f"[{now_str()}] BTC Turtle monitor started.")
    print(f"  Interval: {INTERVAL_SECONDS}s, Entry lookback: {ENTRY_LOOKBACK}, Exit lookback: {EXIT_LOOKBACK}")
    print("  Data source: CoinGecko BTC/USD")
    print("------------------------------------------------------------")

    while True:
        price = fetch_price()
        if price is None:
            time.sleep(INTERVAL_SECONDS)
            continue

        prices.append(price)
        if len(prices) > 5000:
            # 防止内存无上限增长，老数据截断
            prices.pop(0)

        print(f"[{now_str()}] Price: {price:.2f} USD (history len={len(prices)})")

        signal = generate_signal()
        if signal is not None and signal != last_signal:
            # 只在新信号出现时输出
            last_signal = signal

            if signal == "BUY":
                position = 1
            elif signal == "SELL":
                position = 0

            print("============================================================")
            print(f"[{now_str()}] TURTLE SIGNAL: {signal}")
            print(f"  Current price: {price:.2f} USD")
            print(f"  Position after signal: {position}")
            print("============================================================")

            # 在这里调用通知函数
            send_signal_notification(signal, price)

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main_loop()
