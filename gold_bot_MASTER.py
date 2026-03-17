#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║          GOLD MASTER BOT — Telegram Edition                     ║
║          بوت تحليل الذهب الاحترافي                              ║
╚══════════════════════════════════════════════════════════════════╝

المميزات:
  ✅ مؤشرات صحيحة: EMA · RSI · MACD · Supertrend · BB · ATR
  ✅ Multi-Timeframe: 1m · 5m · 15m · 1h
  ✅ Pivot Points + Fibonacci تلقائي
  ✅ Smart Money: Order Blocks + FVG
  ✅ تنبيهات عند كسر مستويات
  ✅ تقرير صباحي + مسائي تلقائي
  ✅ تحليل ذكاء اصطناعي بـ Claude API
  ✅ Async صح — بدون threading issues

التثبيت:
  pip install python-telegram-bot requests numpy pandas ta anthropic

الاستخدام:
  python gold_bot_MASTER.py

الأوامر:
  /start    - بداية + قائمة الأوامر
  /price    - السعر الحالي
  /analysis - تحليل كامل
  /trade    - إشارة شراء/بيع
  /mtf      - Multi-Timeframe analysis
  /pivots   - Pivot Points
  /fib      - Fibonacci levels
  /smc      - Smart Money Concepts
  /report   - تقرير شامل
  /alert    - تفعيل/تعطيل التنبيهات
  /ai       - تحليل Claude AI (محتاج CLAUDE_API_KEY)
  /help     - المساعدة
"""

import os
import logging
import asyncio
import time
import threading
from datetime import datetime, timedelta, timezone

# ── Timezone helper ───────────────────────────────────────────────
def now_local():
    """الوقت المحلي GMT+2"""
    return datetime.now(timezone.utc) + timedelta(hours=2)

def fmt_time():
    return now_local().strftime('%H:%M:%S') + ' (GMT+2)'

def fmt_datetime():
    return now_local().strftime('%Y-%m-%d %H:%M')
from typing import Optional

import requests
import numpy as np

# ── Try to import optional dependencies ──────────────────────────
try:
    import pandas as pd
    import ta
    HAS_TA = True
except ImportError:
    HAS_TA = False
    print("⚠️  ta library not found — using built-in indicators")

try:
    import anthropic
    HAS_CLAUDE = True
except ImportError:
    HAS_CLAUDE = False

from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, JobQueue
)
from telegram.constants import ParseMode

# ════════════════════════════════════════════════════════════════
#  ⚠️  CONFIG — ضع بياناتك هنا أو في environment variables
# ════════════════════════════════════════════════════════════════

# Telegram Bot Token — احصل عليه من @BotFather
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8718855546:AAGyI5ltYabZtbNQnmna1OwbztbIZ5KzNo0")

# TwelveData API Key — twelvedata.com (free plan: 800 req/day)
TWELVEDATA_KEY  = os.getenv("TWELVEDATA_KEY",  "dba6442c915a4bcf8234161b5c97c92e")

# Claude API Key (اختياري — للتحليل بالذكاء الاصطناعي)
CLAUDE_KEY      = os.getenv("CLAUDE_KEY",      "")

# Chat IDs for daily reports (أضف الـ chat IDs اللي تحب ترسلها)
REPORT_CHAT_IDS = []  # مثال: [123456789, -987654321]

# ════════════════════════════════════════════════════════════════
#  LOGGING
# ════════════════════════════════════════════════════════════════

logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
#  KEEP-ALIVE — يمنع Render من إيقاف البوت
# ════════════════════════════════════════════════════════════════
def keep_alive():
    """سيرفر صغير يخلي Render يظن في طلبات دايماً"""
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'Gold Bot is alive!')
            def log_message(self, *args): pass  # اخفي الـ logs
        port = int(os.environ.get('PORT', 8080))
        server = HTTPServer(('0.0.0.0', port), Handler)
        log.info(f'Keep-alive server on port {port}')
        server.serve_forever()
    except Exception as e:
        log.warning(f'Keep-alive failed: {e}')

# شغّل الـ keep-alive في thread منفصل
threading.Thread(target=keep_alive, daemon=True).start()

# ════════════════════════════════════════════════════════════════
#  STATE
# ════════════════════════════════════════════════════════════════

alert_subscribers: set[int] = set()
alert_last_signal: dict[int, str] = {}   # chat_id -> last signal sent
level_alerts: dict[int, list] = {}        # chat_id -> [{price, type, label}]

# ════════════════════════════════════════════════════════════════
#  DATA FETCH — TwelveData
# ════════════════════════════════════════════════════════════════

TIMEFRAMES = {
    '1m':  {'interval': '1min',  'outputsize': 200},
    '5m':  {'interval': '5min',  'outputsize': 200},
    '15m': {'interval': '15min', 'outputsize': 200},
    '1h':  {'interval': '1h',    'outputsize': 200},
    '4h':  {'interval': '4h',    'outputsize': 200},
    '1d':  {'interval': '1day',  'outputsize': 200},
}

def fetch_ohlcv(interval: str = '1min', outputsize: int = 200) -> Optional[dict]:
    """Fetch OHLCV data from TwelveData. Returns dict with lists or None."""
    try:
        url = (
            f"https://api.twelvedata.com/time_series"
            f"?symbol=XAU/USD"
            f"&interval={interval}"
            f"&outputsize={outputsize}"
            f"&apikey={TWELVEDATA_KEY}"
        )
        r = requests.get(url, timeout=10)
        data = r.json()

        if "values" not in data:
            log.warning(f"TwelveData error: {data.get('message', 'unknown')}")
            return None

        rows = list(reversed(data["values"]))  # oldest first
        return {
            'open':   [float(x['open'])   for x in rows],
            'high':   [float(x['high'])   for x in rows],
            'low':    [float(x['low'])    for x in rows],
            'close':  [float(x['close'])  for x in rows],
            'volume': [float(x.get('volume', 0)) for x in rows],
            'time':   [x['datetime']      for x in rows],
        }
    except Exception as e:
        log.error(f"fetch_ohlcv error: {e}")
        return None

def get_price() -> Optional[float]:
    """Get current gold price."""
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={TWELVEDATA_KEY}"
        r = requests.get(url, timeout=8)
        return float(r.json()["price"])
    except:
        d = fetch_ohlcv('1min', 5)
        return d['close'][-1] if d else None

# ════════════════════════════════════════════════════════════════
#  INDICATORS — Correct implementations
# ════════════════════════════════════════════════════════════════

def calc_ema(prices: list, period: int) -> list:
    """Proper EMA using Wilder's multiplier."""
    prices = np.array(prices, dtype=float)
    ema    = np.zeros_like(prices)
    k      = 2.0 / (period + 1)
    ema[0] = prices[0]
    for i in range(1, len(prices)):
        ema[i] = prices[i] * k + ema[i-1] * (1 - k)
    return ema.tolist()

def calc_rsi(prices: list, period: int = 14) -> list:
    """Proper RSI using Wilder's smoothing (same as TradingView)."""
    prices = np.array(prices, dtype=float)
    n      = len(prices)
    rsi    = np.full(n, 50.0)
    if n < period + 1:
        return rsi.tolist()

    deltas = np.diff(prices)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # First average
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, n - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        rsi[i + 1] = 100 - (100 / (1 + rs))

    return rsi.tolist()

def calc_macd(prices: list, fast=12, slow=26, signal=9) -> dict:
    """MACD with proper EMA calculations."""
    e_fast   = calc_ema(prices, fast)
    e_slow   = calc_ema(prices, slow)
    macd_line= [f - s for f, s in zip(e_fast, e_slow)]
    sig_line = calc_ema(macd_line, signal)
    histogram= [m - s for m, s in zip(macd_line, sig_line)]
    n = len(prices) - 1
    return {
        'line':    macd_line[n],
        'signal':  sig_line[n],
        'hist':    histogram[n],
        'crossUp': macd_line[n] >  sig_line[n] and macd_line[n-1] <= sig_line[n-1],
        'crossDn': macd_line[n] <  sig_line[n] and macd_line[n-1] >= sig_line[n-1],
        'bull':    macd_line[n] > sig_line[n],
    }

def calc_atr(high: list, low: list, close: list, period: int = 14) -> float:
    """Average True Range."""
    tr_list = []
    for i in range(1, len(close)):
        tr = max(high[i] - low[i],
                 abs(high[i] - close[i-1]),
                 abs(low[i]  - close[i-1]))
        tr_list.append(tr)
    if not tr_list:
        return 0
    # Wilder smoothing
    atr = np.mean(tr_list[:period]) if len(tr_list) >= period else np.mean(tr_list)
    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period
    return float(atr)

def calc_bb(prices: list, period: int = 20, std_dev: float = 2.0) -> dict:
    """Bollinger Bands."""
    arr  = np.array(prices[-period:], dtype=float)
    mean = float(np.mean(arr))
    std  = float(np.std(arr, ddof=1))
    return {
        'upper':   mean + std_dev * std,
        'middle':  mean,
        'lower':   mean - std_dev * std,
        'squeeze': (std / mean) < 0.005,
    }

def calc_supertrend(high: list, low: list, close: list,
                    period: int = 10, mult: float = 3.0) -> dict:
    """Supertrend indicator — same logic as TradingView."""
    n   = len(close)
    atr_vals = []

    # Calculate ATR for each bar
    for i in range(1, n):
        tr = max(high[i] - low[i],
                 abs(high[i] - close[i-1]),
                 abs(low[i]  - close[i-1]))
        atr_vals.append(tr)

    # Smooth ATR with RMA (Wilder)
    atr_smooth = [np.mean(atr_vals[:period])]
    for i in range(period, len(atr_vals)):
        atr_smooth.append((atr_smooth[-1] * (period-1) + atr_vals[i]) / period)

    # Pad to match close length
    atr_full = [atr_vals[0]] * (n - len(atr_smooth)) + atr_smooth

    st    = float(low[0])
    direction = 1   # 1 = bearish (below), -1 = bullish (above)

    for i in range(1, n):
        hl2     = (high[i] + low[i]) / 2
        upper_b = hl2 + mult * atr_full[i]
        lower_b = hl2 - mult * atr_full[i]

        if close[i] > (st if direction < 0 else upper_b):
            direction = -1
            st = max(lower_b, st if direction == -1 else 0)
        else:
            direction = 1
            st = min(upper_b, st if direction == 1 else 999999)

    return {'value': st, 'bullish': direction < 0}

def calc_stoch_rsi(prices: list, rsi_p=14, stoch_p=14, k=3, d=3) -> dict:
    """Stochastic RSI."""
    rsi_arr = calc_rsi(prices, rsi_p)
    n = len(rsi_arr)
    k_raw = []
    for i in range(stoch_p - 1, n):
        window = rsi_arr[i-stoch_p+1:i+1]
        lo, hi = min(window), max(window)
        k_raw.append(50 if hi == lo else (rsi_arr[i] - lo) / (hi - lo) * 100)

    # Smooth
    def smooth(arr, period):
        if len(arr) < period: return arr
        result = [np.mean(arr[:period])]
        for i in range(period, len(arr)):
            result.append((result[-1] * (period-1) + arr[i]) / period)
        return result

    k_smooth = smooth(k_raw, k)
    d_smooth = smooth(k_smooth, d)
    return {
        'k':   round(k_smooth[-1], 1) if k_smooth else 50,
        'd':   round(d_smooth[-1], 1) if d_smooth else 50,
        'ob':  k_smooth[-1] >= 80 if k_smooth else False,
        'os':  k_smooth[-1] <= 20 if k_smooth else False,
    }

def calc_williams_r(high: list, low: list, close: list, period: int = 14) -> float:
    """Williams %R."""
    h = max(high[-period:])
    l = min(low[-period:])
    if h == l: return -50
    return (h - close[-1]) / (h - l) * -100

# ════════════════════════════════════════════════════════════════
#  PIVOT POINTS
# ════════════════════════════════════════════════════════════════

def calc_pivots(H: float, L: float, C: float) -> dict:
    PP = (H + L + C) / 3
    return {
        'PP': PP,
        'R1': 2*PP - L,  'R2': PP + (H-L),  'R3': H + 2*(PP-L),
        'S1': 2*PP - H,  'S2': PP - (H-L),  'S3': L - 2*(H-PP),
    }

def calc_fibonacci(H: float, L: float) -> dict:
    r = H - L
    return {
        'H': H, 'L': L,
        '0%':    H,
        '23.6%': H - r*0.236,
        '38.2%': H - r*0.382,
        '50%':   H - r*0.500,
        '61.8%': H - r*0.618,
        '78.6%': H - r*0.786,
        '100%':  L,
        '127.2%':L - r*0.272,
        '161.8%':L - r*0.618,
    }

# ════════════════════════════════════════════════════════════════
#  SMART MONEY CONCEPTS
# ════════════════════════════════════════════════════════════════

def detect_order_blocks(d: dict, lookback: int = 30) -> list:
    obs = []
    c_arr = d['close'][-lookback:]
    o_arr = d['open'][-lookback:]
    n = len(c_arr)
    for i in range(1, n-2):
        body = abs(c_arr[i] - o_arr[i])
        move = abs(c_arr[i+1]-o_arr[i+1]) + abs(c_arr[i+2]-o_arr[i+2])
        if c_arr[i] < o_arr[i] and c_arr[i+1] > o_arr[i+1] and move > body*1.5:
            obs.append({'type':'BULL', 'top':round(o_arr[i],2), 'bottom':round(c_arr[i],2)})
        if c_arr[i] > o_arr[i] and c_arr[i+1] < o_arr[i+1] and move > body*1.5:
            obs.append({'type':'BEAR', 'top':round(c_arr[i],2), 'bottom':round(o_arr[i],2)})
    return obs[-3:]

def detect_fvg(d: dict, lookback: int = 20) -> list:
    fvgs = []
    h, l = d['high'][-lookback:], d['low'][-lookback:]
    for i in range(2, len(h)):
        if l[i] > h[i-2]:
            fvgs.append({'type':'BULL','top':round(l[i],2),'bottom':round(h[i-2],2)})
        if l[i-2] > h[i]:
            fvgs.append({'type':'BEAR','top':round(l[i-2],2),'bottom':round(h[i],2)})
    return fvgs[-2:]

def market_structure(d: dict) -> str:
    closes = d['close'][-30:]
    highs  = d['high'][-30:]
    lows   = d['low'][-30:]
    swings = []
    for i in range(2, len(closes)-2):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]: swings.append(('H', highs[i]))
        if lows[i]  < lows[i-1]  and lows[i]  < lows[i+1]:  swings.append(('L', lows[i]))
    if len(swings) < 4: return 'RANGING'
    hs = [p for t,p in swings[-6:] if t=='H']
    ls = [p for t,p in swings[-6:] if t=='L']
    if len(hs)>=2 and len(ls)>=2:
        if hs[-1]>hs[0] and ls[-1]>ls[0]: return 'BULLISH ↑ (HH+HL)'
        if hs[-1]<hs[0] and ls[-1]<ls[0]: return 'BEARISH ↓ (LH+LL)'
    return 'RANGING'

# ════════════════════════════════════════════════════════════════
#  SIGNAL ENGINE
# ════════════════════════════════════════════════════════════════

def full_analysis(d: dict) -> dict:
    """Run all indicators and return scored signal."""
    cl = d['close']; hi = d['high']; lo = d['low']
    price = cl[-1]
    n     = len(cl) - 1

    # EMAs
    E20  = calc_ema(cl, 20)[n]
    E50  = calc_ema(cl, 50)[n]
    E200 = calc_ema(cl, min(200, len(cl)-1))[n]

    # Oscillators
    RSI   = calc_rsi(cl)[n]
    MC    = calc_macd(cl)
    ATR   = calc_atr(hi, lo, cl)
    BB    = calc_bb(cl)
    ST    = calc_supertrend(hi, lo, cl)
    SRSI  = calc_stoch_rsi(cl)
    WR    = calc_williams_r(hi, lo, cl)

    # Derived signals
    ema_bull = E20 > E50 and E50 > E200
    ema_bear = E20 < E50 and E50 < E200
    rsi_ob   = RSI >= 70;  rsi_os = RSI <= 30
    m_bull   = MC['bull']; m_bear = not MC['bull']
    st_bull  = ST['bullish']

    # Scoring 0-12
    bs = ((2 if ema_bull else 0) + (2 if rsi_os else 0) +
          (1 if RSI > 50 and not rsi_ob else 0) +
          (2 if MC['crossUp'] else 0) + (1 if m_bull else 0) +
          (1 if st_bull else 0) + (1 if price < BB['lower'] else 0) +
          (2 if SRSI['os'] else 0))

    ss = ((2 if ema_bear else 0) + (2 if rsi_ob else 0) +
          (1 if RSI < 50 and not rsi_os else 0) +
          (2 if MC['crossDn'] else 0) + (1 if m_bear else 0) +
          (1 if not st_bull else 0) + (1 if price > BB['upper'] else 0) +
          (2 if SRSI['ob'] else 0))

    bf = ((1 if ema_bull else 0) + (1 if m_bull else 0) +
          (1 if st_bull else 0)  + (1 if RSI > 50 else 0) +
          (1 if SRSI['k'] < 50 else 0))
    bef= ((1 if ema_bear else 0) + (1 if m_bear else 0) +
          (1 if not st_bull else 0) + (1 if RSI < 50 else 0) +
          (1 if SRSI['k'] > 50 else 0))

    direction = 'BULLISH' if bf >= 3 else 'BEARISH' if bef >= 3 else 'NEUTRAL'

    return {
        'price': price, 'E20': E20, 'E50': E50, 'E200': E200,
        'RSI': RSI, 'MACD': MC, 'ATR': ATR, 'BB': BB,
        'ST': ST, 'SRSI': SRSI, 'WR': WR,
        'buyScore': min(bs, 12), 'sellScore': min(ss, 12),
        'bullFactors': bf, 'bearFactors': bef,
        'direction': direction,
        'ema_bull': ema_bull, 'ema_bear': ema_bear,
        'rsi_ob': rsi_ob, 'rsi_os': rsi_os,
        'st_bull': st_bull,
    }

# ════════════════════════════════════════════════════════════════
#  FORMATTERS — Telegram messages
# ════════════════════════════════════════════════════════════════

def fmt_price(price: float) -> str:
    return f"${price:,.3f}"

def fmt_direction(d: str) -> str:
    return {'BULLISH': '🟢 صاعد BULLISH', 'BEARISH': '🔴 هابط BEARISH',
            'NEUTRAL': '🟡 محايد NEUTRAL'}.get(d, d)

def fmt_analysis_msg(sig: dict, tf: str = '1m') -> str:
    p   = sig['price']
    atr = sig['ATR']
    d   = sig['direction']
    is_bull = d == 'BULLISH'
    is_bear = d == 'BEARISH'

    sl  = p - atr   if is_bull else p + atr
    tp1 = p + atr*1.5 if is_bull else p - atr*1.5
    tp2 = p + atr*3   if is_bull else p - atr*3

    rsi_warn = ''
    if sig['rsi_ob']: rsi_warn = '⚠️ RSI ذروة شراء\n'
    if sig['rsi_os']: rsi_warn = '⚠️ RSI ذروة بيع\n'

    lines = [
        f"╔══ 🥇 GOLD ANALYSIS [{tf}] ══╗",
        f"💰 السعر: *{fmt_price(p)}*",
        f"",
        f"📊 *الاتجاه: {fmt_direction(d)}*",
        f"   {sig['bullFactors'] if not is_bear else sig['bearFactors']}/5 عوامل",
        f"   🟢 BUY: {sig['buyScore']}/12  |  🔴 SELL: {sig['sellScore']}/12",
        f"",
        f"📈 *المؤشرات:*",
        f"   EMA 20/50/200: {'✅ متراكبة صاعدة' if sig['ema_bull'] else '❌ متراكبة هابطة' if sig['ema_bear'] else '↔️ محايدة'}",
        f"   RSI: {sig['RSI']:.1f} {'🔴 ذروة شراء' if sig['rsi_ob'] else '🟢 ذروة بيع' if sig['rsi_os'] else ''}",
        f"   MACD: {'📈 صاعد' if sig['MACD']['bull'] else '📉 هابط'}"
             + (' 🔔 تقاطع صاعد!' if sig['MACD']['crossUp'] else '')
             + (' 🔔 تقاطع هابط!' if sig['MACD']['crossDn'] else ''),
        f"   Supertrend: {'🟢 BULL' if sig['st_bull'] else '🔴 BEAR'}",
        f"   Stoch RSI: K={sig['SRSI']['k']} {'🔴 OB' if sig['SRSI']['ob'] else '🟢 OS' if sig['SRSI']['os'] else ''}",
        f"   Williams %R: {sig['WR']:.1f}",
        f"   ATR: {sig['ATR']:.3f}",
        f"   BB: {'⚡ SQUEEZE' if sig['BB']['squeeze'] else 'normal'}",
        f"",
    ]

    if is_bull or is_bear:
        lines += [
            f"🎯 *Entry · TP · SL:*",
            f"   Entry: {fmt_price(p)}",
            f"   🟢 TP1: {fmt_price(tp1)}",
            f"   🟢 TP2: {fmt_price(tp2)}",
            f"   🔴 SL:  {fmt_price(sl)}",
            f"   R:R = 1:1.5",
            f"",
        ]

    if rsi_warn:
        lines.append(f"   {rsi_warn}")

    lines.append(f"🕐 {now_local().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("╚══════════════════════╝")
    return '\n'.join(lines)

def fmt_mtf_msg(results: dict) -> str:
    lines = [
        "╔══ 📊 Multi-Timeframe Analysis ══╗",
        "",
    ]
    agree_bull = sum(1 for r in results.values() if r['direction']=='BULLISH')
    agree_bear = sum(1 for r in results.values() if r['direction']=='BEARISH')
    overall    = '🟢 BULLISH' if agree_bull >= 3 else '🔴 BEARISH' if agree_bear >= 3 else '🟡 MIXED'

    lines += [
        f"📡 *الخلاصة: {overall}*",
        f"   {agree_bull}↑ صاعد  |  {agree_bear}↓ هابط",
        "",
        "```",
        f"{'TF':<5} {'Dir':<10} {'RSI':<6} {'MACD':<6} {'ST':<5}",
        "─" * 35,
    ]

    for tf, r in results.items():
        d_sym = '🟢' if r['direction']=='BULLISH' else '🔴' if r['direction']=='BEARISH' else '🟡'
        lines.append(
            f"{tf:<5} {d_sym+r['direction'][:7]:<10} "
            f"{r['RSI']:<6.1f} "
            f"{'↑' if r['MACD']['bull'] else '↓':<6} "
            f"{'🟢' if r['st_bull'] else '🔴'}"
        )

    lines += ["```", "", f"💰 السعر: *{fmt_price(list(results.values())[-1]['price'])}*"]
    lines.append(f"🕐 {now_local().strftime('%H:%M:%S') + ' (GMT+2)'}")
    lines.append("╚══════════════════════════════╝")
    return '\n'.join(lines)

def fmt_pivots_msg(pivots: dict, fib: dict, price: float) -> str:
    f = lambda v: f"{v:,.3f}"
    zone = ''
    if price > pivots['R3']:    zone = '↑ فوق R3'
    elif price > pivots['R2']:  zone = 'R2–R3'
    elif price > pivots['R1']:  zone = 'R1–R2'
    elif price > pivots['PP']:  zone = 'PP–R1'
    elif price > pivots['S1']:  zone = 'S1–PP ◀'
    elif price > pivots['S2']:  zone = 'S2–S1'
    elif price > pivots['S3']:  zone = 'S3–S2'
    else:                       zone = '↓ تحت S3'

    lines = [
        "╔══ 📌 Pivot Points ══╗",
        f"💰 السعر: *{fmt_price(price)}* — [{zone}]",
        "",
        "```",
        f"R3: {f(pivots['R3'])}  (+{(pivots['R3']-price)/price*100:.2f}%)",
        f"R2: {f(pivots['R2'])}  (+{(pivots['R2']-price)/price*100:.2f}%)",
        f"R1: {f(pivots['R1'])}  (+{(pivots['R1']-price)/price*100:.2f}%)",
        f"PP: {f(pivots['PP'])}  ({(pivots['PP']-price)/price*100:+.2f}%)",
        f"S1: {f(pivots['S1'])}  ({(pivots['S1']-price)/price*100:.2f}%)",
        f"S2: {f(pivots['S2'])}  ({(pivots['S2']-price)/price*100:.2f}%)",
        f"S3: {f(pivots['S3'])}  ({(pivots['S3']-price)/price*100:.2f}%)",
        "```",
        "",
        "📐 *Fibonacci (61.8% = Golden):*",
        "```",
        f"0%    (High): {f(fib['0%'])}",
        f"38.2%:        {f(fib['38.2%'])}",
        f"50%:          {f(fib['50%'])}",
        f"61.8% 🥇:     {f(fib['61.8%'])}",
        f"100%  (Low):  {f(fib['100%'])}",
        "```",
    ]
    return '\n'.join(lines)

def fmt_smc_msg(obs: list, fvgs: list, ms: str, price: float) -> str:
    lines = [
        "╔══ ⚡ Smart Money Concepts ══╗",
        f"💰 السعر: *{fmt_price(price)}*",
        f"🏗️ Market Structure: *{ms}*",
        "",
    ]

    if obs:
        lines.append("📦 *Order Blocks:*")
        for ob in obs:
            near  = abs((ob['top']+ob['bottom'])/2 - price) / price < 0.012
            color = '🟦' if ob['type']=='BULL' else '🟥'
            note  = ' ← السعر قريب! 🎯' if near else ''
            lines.append(f"  {color} {ob['type']} OB: {ob['bottom']:.2f}–{ob['top']:.2f}{note}")
        lines.append("")

    if fvgs:
        lines.append("⬜ *Fair Value Gaps:*")
        for fvg in fvgs:
            icon  = '⬆️' if fvg['type']=='BULL' else '⬇️'
            near  = abs((fvg['top']+fvg['bottom'])/2 - price) / price < 0.008
            note  = ' ← داخل FVG!' if near else ''
            lines.append(f"  {icon} {fvg['type']} FVG: {fvg['bottom']:.2f}–{fvg['top']:.2f}{note}")

    lines.append(f"\n🕐 {now_local().strftime('%H:%M:%S') + ' (GMT+2)'}")
    lines.append("╚══════════════════════════╝")
    return '\n'.join(lines)

# ════════════════════════════════════════════════════════════════
#  CLAUDE AI ANALYSIS
# ════════════════════════════════════════════════════════════════

async def claude_analysis(sig: dict) -> str:
    if not HAS_CLAUDE or not CLAUDE_KEY:
        return "⚠️ Claude API غير مفعّل. أضف CLAUDE_KEY في الإعدادات."
    try:
        client = anthropic.Anthropic(api_key=CLAUDE_KEY)
        prompt = f"""أنت محلل ذهب محترف. حلل البيانات التالية وقدم رأيك باختصار بالعربية:

السعر: ${sig['price']:.3f}
الاتجاه: {sig['direction']}
RSI: {sig['RSI']:.1f}
MACD: {'صاعد' if sig['MACD']['bull'] else 'هابط'}
Supertrend: {'صاعد' if sig['st_bull'] else 'هابط'}
BUY Score: {sig['buyScore']}/12
SELL Score: {sig['sellScore']}/12
EMA Stack: {'صاعدة' if sig['ema_bull'] else 'هابطة' if sig['ema_bear'] else 'محايدة'}

قدم:
1. خلاصة الوضع (3 جمل)
2. أهم مستويين للمراقبة
3. توصية واضحة (شراء/بيع/انتظار) مع السبب"""

        msg = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=400,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return f"🤖 *تحليل Claude AI:*\n\n{msg.content[0].text}"
    except Exception as e:
        return f"⚠️ Claude error: {str(e)[:100]}"

# ════════════════════════════════════════════════════════════════
#  ALERT ENGINE
# ════════════════════════════════════════════════════════════════

async def check_and_send_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Called every minute by JobQueue."""
    if not alert_subscribers:
        return

    d = fetch_ohlcv('1min', 200)
    if not d: return

    sig = full_analysis(d)

    for chat_id in list(alert_subscribers):
        last = alert_last_signal.get(chat_id, '')

        # Signal change alert
        if sig['direction'] != 'NEUTRAL' and sig['direction'] != last:
            alert_last_signal[chat_id] = sig['direction']
            try:
                msg = f"🔔 *إشارة جديدة!*\n\n" + fmt_analysis_msg(sig, '1m')
                await context.bot.send_message(
                    chat_id=chat_id, text=msg,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                log.warning(f"Alert send error for {chat_id}: {e}")

        # Level alerts
        price = sig['price']
        for alert in level_alerts.get(chat_id, []):
            if alert.get('triggered'): continue
            hit = (price >= alert['price'] if alert['type']=='above'
                   else price <= alert['price'])
            if hit:
                alert['triggered'] = True
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"🔔 *Level Alert!*\n"
                             f"{alert.get('label','')}\n"
                             f"السعر وصل: {fmt_price(price)}\n"
                             f"المستوى: {fmt_price(alert['price'])}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except: pass

async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    """Called twice daily — morning & evening."""
    chat_ids = REPORT_CHAT_IDS + list(alert_subscribers)
    if not chat_ids: return

    d = fetch_ohlcv('1h', 200)
    if not d: return

    sig = full_analysis(d)
    pv  = calc_pivots(max(d['high'][-5:]), min(d['low'][-5:]), d['close'][-1])
    fib = calc_fibonacci(max(d['high'][-60:]), min(d['low'][-60:]))
    ms  = market_structure(d)
    hour = datetime.now().hour
    period = '🌅 صباحي' if 5 <= hour < 12 else '🌇 مسائي'

    report = [
        f"╔══ 📰 تقرير الذهب {period} ══╗",
        f"💰 السعر: *{fmt_price(sig['price'])}*",
        f"📊 الاتجاه: *{fmt_direction(sig['direction'])}*",
        f"🏗️ هيكل السوق: *{ms}*",
        f"",
        f"📈 *المؤشرات:*",
        f"   RSI: {sig['RSI']:.1f}  |  MACD: {'↑' if sig['MACD']['bull'] else '↓'}  |  ST: {'🟢' if sig['st_bull'] else '🔴'}",
        f"   Stoch RSI K: {sig['SRSI']['k']}",
        f"",
        f"📌 *Pivot Points:*",
        f"   R1: {pv['R1']:.3f}  |  PP: {pv['PP']:.3f}  |  S1: {pv['S1']:.3f}",
        f"",
        f"🎯 *TP/SL (ATR={sig['ATR']:.2f}):*",
    ]

    if sig['direction'] != 'NEUTRAL':
        is_b = sig['direction'] == 'BULLISH'
        p = sig['price']; a = sig['ATR']
        report += [
            f"   {'🟢 TP1' if is_b else '🔴 TP1'}: {fmt_price(p + a*1.5 if is_b else p - a*1.5)}",
            f"   {'🟢 TP2' if is_b else '🔴 TP2'}: {fmt_price(p + a*3   if is_b else p - a*3)}",
            f"   {'🔴 SL'  if is_b else '🟢 SL'}:  {fmt_price(p - a     if is_b else p + a)}",
        ]

    report += ["", f"🕐 {now_local().strftime('%Y-%m-%d %H:%M')}", "╚══════════════════╝"]
    text = '\n'.join(report)

    for cid in set(chat_ids):
        try:
            await context.bot.send_message(cid, text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            log.warning(f"Report send error: {e}")

# ════════════════════════════════════════════════════════════════
#  COMMAND HANDLERS
# ════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════
#  INLINE KEYBOARD — يظهر بعد كل رد تلقائياً
# ════════════════════════════════════════════════════════════════

def main_keyboard():
    """الكيبورد الرئيسي — يظهر دايماً أسفل كل رسالة"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 السعر",      callback_data="price"),
            InlineKeyboardButton("📊 تحليل 1m",   callback_data="analysis_1m"),
            InlineKeyboardButton("📊 تحليل 5m",   callback_data="analysis_5m"),
        ],
        [
            InlineKeyboardButton("🎯 إشارة",       callback_data="trade"),
            InlineKeyboardButton("⏱ MTF",          callback_data="mtf"),
            InlineKeyboardButton("📈 تقرير",        callback_data="report"),
        ],
        [
            InlineKeyboardButton("📌 Pivots",       callback_data="pivots"),
            InlineKeyboardButton("🌀 Fibonacci",    callback_data="fib"),
            InlineKeyboardButton("⚡ SMC",           callback_data="smc"),
        ],
        [
            InlineKeyboardButton("🔔 تنبيهات ON/OFF", callback_data="alert"),
            InlineKeyboardButton("📋 قائمة التنبيهات",callback_data="alerts"),
        ],
        [
            InlineKeyboardButton("🤖 AI تحليل",    callback_data="ai"),
            InlineKeyboardButton("❓ مساعدة",       callback_data="help"),
        ],
    ])



# ════════════════════════════════════════════════════════════════
#  DATA CACHE — يقلل الـ API requests
# ════════════════════════════════════════════════════════════════
_cache = {}

def fetch_ohlcv_cached(interval: str, outputsize: int, ttl: int = 240):
    """Fetch with cache — بيحفظ البيانات لـ 4 دقائق"""
    key = f"{interval}_{outputsize}"
    now = time.time()
    if key in _cache and now - _cache[key]['time'] < ttl:
        return _cache[key]['data']
    data = fetch_ohlcv(interval, outputsize)
    if data:
        _cache[key] = {'data': data, 'time': now}
    return data

def get_price_cached(ttl: int = 120):
    """Get price with cache — بيحفظ لدقيقتين"""
    now = time.time()
    if 'price' in _cache and now - _cache['price']['time'] < ttl:
        return _cache['price']['data']
    price = get_price()
    if price:
        _cache['price'] = {'data': price, 'time': now}
    return price

def make_ascii_chart(prices, width=20, height=6):
    """رسم شارت نصي بسيط داخل Telegram"""
    if not prices or len(prices) < 2:
        return ""
    mn, mx = min(prices), max(prices)
    if mx == mn:
        return ""
    rng = mx - mn
    rows = []
    for row in range(height):
        threshold = mx - (rng * row / (height-1))
        line = ""
        for p in prices[-width:]:
            if abs(p - threshold) <= rng / (height * 2):
                line += "●"
            elif p >= threshold:
                line += "│"
            else:
                line += " "
        rows.append(f"`{threshold:>8.1f}` {line}")
    # Add trend arrow
    trend = "↗" if prices[-1] > prices[0] else "↘" if prices[-1] < prices[0] else "→"
    rows.append(f"         {'▔'*width} {trend}")
    return "\n".join(rows)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج ضغط الأزرار"""
    query = update.callback_query
    await query.answer()  # يوقف الـ loading على الزر

    data = query.data

    # نعمل fake update عشان نعيد استخدام نفس الـ handlers
    if data == "price":
        price = get_price_cached()
        if price:
            # Try to get recent prices for mini chart
            chart_str = ""
            try:
                d = fetch_ohlcv("5min", 24)
                if d:
                    closes = d["close"][-20:]
                    chart_str = "\n\n" + make_ascii_chart(closes)
            except:
                pass
            chg_icon = "📈" if price > (price * 0.999) else "📉"
            text = (f"🥇 *GOLD / USD*\n"
                    f"💰 *{fmt_price(price)}*\n"
                    f"🕐 {now_local().strftime('%H:%M:%S') + ' (GMT+2)'} UTC"
                    f"{chart_str}")
        else:
            text = "❌ فشل جلب السعر. تحقق من API Key."
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=main_keyboard())

    elif data in ("analysis_1m", "analysis_5m"):
        tf_arg = "1m" if data == "analysis_1m" else "5m"
        tf_cfg = TIMEFRAMES.get(tf_arg, TIMEFRAMES["1m"])
        await query.message.reply_text(f"⏳ جاري التحليل على {tf_arg}...",
                                       reply_markup=main_keyboard())
        d = fetch_ohlcv(tf_cfg["interval"], tf_cfg["outputsize"])
        if not d:
            text = "❌ فشل جلب البيانات."
        else:
            sig = full_analysis(d)
            text = fmt_analysis_msg(sig, tf_arg)
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=main_keyboard())

    elif data == "trade":
        await query.message.reply_text("⏳ جاري حساب الإشارة...",
                                       reply_markup=main_keyboard())
        d = fetch_ohlcv("5min", 200)
        if not d:
            text = "❌ فشل جلب البيانات."
        else:
            sig  = full_analysis(d)
            atr  = sig.get("ATR", 0)
            price= sig.get("price", 0)
            dire = sig.get("direction", "NEUTRAL")
            bs   = sig.get("buyScore", 0)
            ss   = sig.get("sellScore", 0)
            tp1  = price + atr*1.5 if dire == "BULLISH" else price - atr*1.5
            tp2  = price + atr*3   if dire == "BULLISH" else price - atr*3
            sl   = price - atr     if dire == "BULLISH" else price + atr
            icon = "🟢" if dire == "BULLISH" else "🔴" if dire == "BEARISH" else "🟡"
            text = (f"{icon} *إشارة التداول*\n\n"
                    f"الاتجاه: *{dire}*\n"
                    f"السعر: *{fmt_price(price)}*\n\n"
                    f"TP1: `{tp1:.3f}`\n"
                    f"TP2: `{tp2:.3f}`\n"
                    f"SL:  `{sl:.3f}`\n\n"
                    f"BUY {bs}/12 · SELL {ss}/12")
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=main_keyboard())

    elif data == "mtf":
        await query.message.reply_text("⏳ جاري تحليل Multi-Timeframe...",
                                       reply_markup=main_keyboard())
        lines = ["📊 *MULTI-TIMEFRAME ANALYSIS*\n"]
        for tf_name, tf_cfg in TIMEFRAMES.items():
            d = fetch_ohlcv(tf_cfg["interval"], tf_cfg["outputsize"])
            if d:
                sig  = full_analysis(d)
                dire = sig.get("direction","?")
                bs   = sig.get("buyScore",0)
                ss   = sig.get("sellScore",0)
                icon = "🟢" if dire=="BULLISH" else "🔴" if dire=="BEARISH" else "🟡"
                lines.append(f"{icon} *{tf_name}* — {dire} · BUY {bs} SELL {ss}")
        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=main_keyboard())

    elif data == "pivots":
        await query.message.reply_text("⏳ جاري حساب Pivot Points...",
                                       reply_markup=main_keyboard())
        d = fetch_ohlcv("1day", 10)
        if not d or not d.get("high"):
            text = "❌ فشل جلب البيانات. تحقق من TWELVEDATA_KEY."
        else:
            H = max(d["high"][-5:])
            L = min(d["low"][-5:])
            C = d["close"][-1]
            PP = (H+L+C)/3
            R1,R2,R3 = 2*PP-L, PP+(H-L), H+2*(PP-L)
            S1,S2,S3 = 2*PP-H, PP-(H-L), L-2*(H-PP)
            rng  = H - L
            f382 = H - rng*0.382
            f500 = H - rng*0.500
            f618 = H - rng*0.618
            text = (f"📌 *PIVOT POINTS*\n\n"
                    f"R3: `{R3:.3f}`\nR2: `{R2:.3f}`\nR1: `{R1:.3f}`\n"
                    f"PP: `{PP:.3f}` ←\n"
                    f"S1: `{S1:.3f}`\nS2: `{S2:.3f}`\nS3: `{S3:.3f}`\n\n"
                    f"📐 *Fibonacci*\n"
                    f"38.2%: `{f382:.3f}`\n50%: `{f500:.3f}`\n61.8%: `{f618:.3f}`")
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=main_keyboard())

    elif data == "fib":
        await query.message.reply_text("⏳ جاري حساب Fibonacci...",
                                       reply_markup=main_keyboard())
        d = fetch_ohlcv("1day", 60)
        if not d or not d.get("high"):
            text = "❌ فشل جلب البيانات. تحقق من TWELVEDATA_KEY."
        else:
            H   = max(d["high"])
            L   = min(d["low"])
            C   = d["close"][-1]
            rng = H - L
            # Find where current price sits
            retrace = ((H - C) / rng * 100) if rng > 0 else 0
            text = (f"📐 *FIBONACCI RETRACEMENT*\n"
                    f"High: `{H:.3f}` · Low: `{L:.3f}`\n"
                    f"الآن: `{C:.3f}` ({retrace:.1f}% retrace)\n\n"
                    f"0%:    `{H:.3f}`\n"
                    f"23.6%: `{H-rng*.236:.3f}`\n"
                    f"38.2%: `{H-rng*.382:.3f}` 🔑\n"
                    f"50%:   `{H-rng*.5:.3f}` 🔑\n"
                    f"61.8%: `{H-rng*.618:.3f}` 🥇 Golden\n"
                    f"78.6%: `{H-rng*.786:.3f}`\n"
                    f"100%:  `{L:.3f}`\n\n"
                    f"📈 Extensions:\n"
                    f"127.2%: `{L-rng*.272:.3f}`\n"
                    f"161.8%: `{L-rng*.618:.3f}`")
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=main_keyboard())

    elif data == "smc":
        await query.message.reply_text("⏳ جاري تحليل Smart Money...",
                                       reply_markup=main_keyboard())
        d = fetch_ohlcv("1h", 100)
        if not d or not d.get("close"):
            text = "❌ فشل جلب البيانات. تحقق من TWELVEDATA_KEY."
        else:
            sig  = full_analysis(d)
            obs  = sig.get("order_blocks", [])
            fvgs = sig.get("fvgs", [])
            lines = ["⚡ *SMART MONEY CONCEPTS*\n"]
            if obs:
                lines.append("📦 *Order Blocks:*")
                for ob in obs[-3:]:
                    lines.append(f"  {'🟦' if ob.get('type')=='BULL_OB' else '🟥'} {ob.get('label','OB')}: `{ob.get('bottom',0):.3f}` — `{ob.get('top',0):.3f}`")
            if fvgs:
                lines.append("\n⬜ *Fair Value Gaps:*")
                for fvg in fvgs[-3:]:
                    lines.append(f"  {'⬆️' if fvg.get('type')=='BULL' else '⬇️'} {fvg.get('label','FVG')}: `{fvg.get('bottom',0):.3f}` — `{fvg.get('top',0):.3f}`")
            if not obs and not fvgs:
                lines.append("لا أنماط SMC واضحة حالياً")
            text = "\n".join(lines)
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=main_keyboard())

    elif data == "report":
        await query.message.reply_text("⏳ جاري إعداد التقرير الشامل...",
                                       reply_markup=main_keyboard())
        price = get_price()
        d     = fetch_ohlcv("5min", 200)
        if not d or not price:
            text = "❌ فشل جلب البيانات."
        else:
            sig  = full_analysis(d)
            dire = sig.get("direction","NEUTRAL")
            bs   = sig.get("buyScore",0)
            ss   = sig.get("sellScore",0)
            rsi  = sig.get("RSI",50)
            atr  = sig.get("ATR",0)
            icon = "🟢" if dire=="BULLISH" else "🔴" if dire=="BEARISH" else "🟡"
            text = (f"📈 *GOLD MASTER REPORT*\n"
                    f"🕐 {now_local().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"💰 السعر: *{fmt_price(price)}*\n"
                    f"{icon} الاتجاه: *{dire}*\n\n"
                    f"BUY Score:  {bs}/12\n"
                    f"SELL Score: {ss}/12\n"
                    f"RSI: {rsi:.1f}\n"
                    f"ATR: {atr:.3f}\n\n"
                    f"{fmt_analysis_msg(sig,'5m')}")
        await query.message.reply_text(text[:4000], parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=main_keyboard())

    elif data == "alert":
        chat_id = query.message.chat_id
        if chat_id in alert_subscribers:
            alert_subscribers.discard(chat_id)
            status = "🔴 متوقف"
        else:
            alert_subscribers.add(chat_id)
            status = "🟢 مفعّل"
        text = (f"🔔 *التنبيهات التلقائية*\n"
                f"الحالة: {status}\n\n"
                f"لإضافة تنبيه عند مستوى معين:\n"
                f"`/setalert 3100 above وصل الهدف`")
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=main_keyboard())

    elif data == "alerts":
        chat_id = query.message.chat_id
        user_alerts = level_alerts.get(chat_id, [])
        if not user_alerts:
            text = "📋 لا يوجد تنبيهات مضافة\n\nأضف تنبيه: /setalert 3100 above سبب"
        else:
            lines = ["📋 *التنبيهات النشطة:*\n"]
            for a in user_alerts:
                icon = "↑" if a["type"]=="above" else "↓"
                done = "✅" if a.get("triggered") else "⏳"
                lines.append(f"{done} {icon} `{a['price']:.3f}` — {a.get('label','')}")
            text = "\n".join(lines)
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=main_keyboard())

    elif data == "ai":
        if not HAS_CLAUDE or not CLAUDE_KEY:
            text = ("🤖 *Claude AI*\n\n"
                    "❌ غير مفعّل حالياً\n\n"
                    "لتفعيله أضف في Render:\n"
                    "Key: `CLAUDE_KEY`\n"
                    "Value: مفتاح API من console.anthropic.com\n\n"
                    "الحصول على مفتاح مجاني:\n"
                    "1. روح console.anthropic.com\n"
                    "2. سجّل حساب مجاني\n"
                    "3. أنشئ API Key")
        else:
            try:
                await query.message.reply_text("⏳ جاري التحليل بالذكاء الاصطناعي...",
                                               reply_markup=main_keyboard())
                d    = fetch_ohlcv_cached("1h", 200)
                if not d:
                    text = "❌ فشل جلب البيانات."
                else:
                    sig  = full_analysis(d)
                    text = await claude_analysis(sig)
            except Exception as e:
                text = f"❌ خطأ في Claude AI: {str(e)}"
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=main_keyboard())

    elif data == "help":
        text = (
            "❓ *GOLD MASTER BOT — المساعدة*\n\n"
            "اضغط على أي زر أسفل الرسالة 👇\n\n"
            "💰 *السعر* — السعر الحالي للذهب\n"
            "📊 *تحليل* — تحليل فني كامل\n"
            "🎯 *إشارة* — BUY/SELL مع TP وSL\n"
            "⏱ *MTF* — تحليل 4 Timeframes\n"
            "📌 *Pivots* — مستويات الدعم والمقاومة\n"
            "🌀 *Fibonacci* — مستويات الفيبوناتشي\n"
            "⚡ *SMC* — Order Blocks وFVG\n"
            "📈 *تقرير* — تقرير شامل\n"
            "🔔 *تنبيهات* — تفعيل/تعطيل التنبيهات\n"
            "🤖 *AI* — تحليل بالذكاء الاصطناعي\n\n"
            "لإضافة تنبيه:\n"
            "`/setalert 3100 above سبب`"
        )
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=main_keyboard())

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "صديقي"
    text = (
        f"🥇 *GOLD MASTER BOT*\n"
        f"أهلاً {name}! 👋\n\n"
        f"💡 اضغط أي زر للحصول على تحليل فوري\n"
        f"🔔 فعّل التنبيهات للحصول على إشارات تلقائية\n"
        f"⚡ إشارات قوية تصلك فوراً بدون طلب\n\n"
        f"اضغط على أي زر أسفل 👇"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )

async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ جاري جلب السعر...")
    price = get_price()
    if price:
        await update.message.reply_text(
            f"🥇 *GOLD / USD*\n💰 *{fmt_price(price)}*\n"
            f"🕐 {now_local().strftime('%H:%M:%S') + ' (GMT+2)'}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ فشل جلب السعر. تحقق من API Key.",
            reply_markup=main_keyboard()
        )

async def cmd_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tf_arg = context.args[0] if context.args else '1m'
    tf_cfg = TIMEFRAMES.get(tf_arg, TIMEFRAMES['1m'])
    await update.message.reply_text(f"⏳ جاري التحليل على {tf_arg}...")

    d = fetch_ohlcv(tf_cfg['interval'], tf_cfg['outputsize'])
    if not d:
        await update.message.reply_text("❌ فشل جلب البيانات.")
        return

    sig = full_analysis(d)
    await update.message.reply_text(
        fmt_analysis_msg(sig, tf_arg),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )

async def cmd_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ جاري حساب الإشارة...")
    d = fetch_ohlcv('5min', 200)
    if not d:
        await update.message.reply_text("❌ فشل جلب البيانات.")
        return
    sig = full_analysis(d)
    if sig['direction'] == 'NEUTRAL':
        await update.message.reply_text(
            "⏳ لا توجد إشارة واضحة الآن.\n"
            f"BUY: {sig['buyScore']}/12  |  SELL: {sig['sellScore']}/12\n"
            "انتظر اكتمال الإشارة."
        )
    else:
        await update.message.reply_text(
            fmt_analysis_msg(sig, '5m'),
            parse_mode=ParseMode.MARKDOWN
        )

async def cmd_mtf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ جاري تحليل 4 timeframes...")
    results = {}
    for tf_name, cfg in [('1m','1min'),('5m','5min'),('15m','15min'),('1h','1h')]:
        d = fetch_ohlcv(cfg, 200)
        if d:
            results[tf_name] = full_analysis(d)
        await asyncio.sleep(0.5)  # rate limit

    if not results:
        await update.message.reply_text("❌ فشل جلب البيانات.")
        return

    await update.message.reply_text(
        fmt_mtf_msg(results), parse_mode=ParseMode.MARKDOWN
    )

async def cmd_pivots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ جاري حساب Pivots...")
    d = fetch_ohlcv('1day', 10)
    if not d:
        await update.message.reply_text("❌ فشل جلب البيانات.")
        return
    H = max(d['high'][-5:]);  L = min(d['low'][-5:]);  C = d['close'][-1]
    pv  = calc_pivots(H, L, C)
    fib = calc_fibonacci(max(d['high'][-60:] if len(d['high']) >= 60 else d['high']),
                         min(d['low'][-60:]  if len(d['low'])  >= 60 else d['low']))
    await update.message.reply_text(
        fmt_pivots_msg(pv, fib, C), parse_mode=ParseMode.MARKDOWN
    )

async def cmd_fib(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ جاري حساب Fibonacci...")
    d = fetch_ohlcv('1day', 60)
    if not d:
        await update.message.reply_text("❌ فشل جلب البيانات.")
        return
    H   = max(d['high'])
    L   = min(d['low'])
    C   = d['close'][-1]
    fib = calc_fibonacci(H, L)
    rng = H - L
    retrace = ((H - C) / rng * 100) if rng > 0 else 0
    f = lambda v: f"{v:,.3f}"
    lines = [
        "📐 *FIBONACCI RETRACEMENT*",
        f"High: `{H:.3f}` · Low: `{L:.3f}`",
        f"الآن: `{C:.3f}` ({retrace:.1f}% retrace)",
        "",
        f"0%:    `{fib['0%']:.3f}`",
        f"23.6%: `{fib['23.6%']:.3f}`",
        f"38.2%: `{fib['38.2%']:.3f}`",
        f"50%:   `{fib['50%']:.3f}`",
        f"61.8% 🥇: `{fib['61.8%']:.3f}`",
        f"78.6%: `{fib['78.6%']:.3f}`",
        f"100%:  `{fib['100%']:.3f}`",
    ]
    await update.message.reply_text(
        '\n'.join(lines), parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )

async def cmd_smc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ جاري تحليل Smart Money...")
    d = fetch_ohlcv('1h', 200)
    if not d:
        await update.message.reply_text("❌ فشل جلب البيانات.")
        return
    obs  = detect_order_blocks(d)
    fvgs = detect_fvg(d)
    ms   = market_structure(d)
    await update.message.reply_text(
        fmt_smc_msg(obs, fvgs, ms, d['close'][-1]),
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ جاري إعداد التقرير الشامل...")
    await send_daily_report(context)

async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in alert_subscribers:
        alert_subscribers.discard(chat_id)
        await update.message.reply_text("🔕 التنبيهات التلقائية متوقفة.")
    else:
        alert_subscribers.add(chat_id)
        await update.message.reply_text(
            "🔔 التنبيهات التلقائية مفعّلة!\n"
            "ستصلك إشارة عند تغيير الاتجاه."
        )

async def cmd_set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /setalert 3100 above سبب"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "الاستخدام: /setalert [سعر] [above|below] [ملاحظة]\n"
            "مثال: /setalert 3100 above مقاومة رئيسية"
        )
        return
    try:
        price = float(context.args[0])
        typ   = context.args[1].lower()
        label = ' '.join(context.args[2:]) if len(context.args) > 2 else ''
        if typ not in ('above', 'below'):
            raise ValueError()
    except:
        await update.message.reply_text("❌ خطأ في الصيغة.")
        return

    chat_id = update.effective_chat.id
    if chat_id not in level_alerts:
        level_alerts[chat_id] = []
    level_alerts[chat_id].append(
        {'price': price, 'type': typ, 'label': label, 'triggered': False}
    )
    dir_ar = 'فوق' if typ == 'above' else 'تحت'
    await update.message.reply_text(
        f"✅ تم ضبط Alert عند {dir_ar} {fmt_price(price)}"
        + (f"\nملاحظة: {label}" if label else "")
    )

async def cmd_alerts_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    alerts  = level_alerts.get(chat_id, [])
    if not alerts:
        await update.message.reply_text("لا توجد alerts مضبوطة.\nاستخدم /setalert للإضافة.")
        return
    lines = ["📋 *الـ Alerts المضبوطة:*\n"]
    for i, a in enumerate(alerts, 1):
        status = '✅ تم' if a['triggered'] else '⏳ منتظر'
        lines.append(f"{i}. {'↑' if a['type']=='above' else '↓'} {fmt_price(a['price'])} — {status}")
        if a.get('label'): lines.append(f"   {a['label']}")
    await update.message.reply_text('\n'.join(lines), parse_mode=ParseMode.MARKDOWN)

async def cmd_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 جاري تحليل Claude AI...")
    d = fetch_ohlcv('1h', 200)
    if not d:
        await update.message.reply_text("❌ فشل جلب البيانات.")
        return
    sig  = full_analysis(d)
    text = await claude_analysis(sig)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)

# ════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
#  AUTO SIGNALS & ALERTS
# ════════════════════════════════════════════════════════════════

async def auto_hourly_signal(context):
    """تنبيه تلقائي كل ساعة بالسعر والإشارة"""
    if not REPORT_CHAT_IDS:
        return
    try:
        price = get_price_cached()
        d     = fetch_ohlcv_cached("5min", 200)
        if not price or not d:
            return
        sig  = full_analysis(d)
        dire = sig.get("direction", "NEUTRAL")
        bs   = sig.get("buyScore", 0)
        ss   = sig.get("sellScore", 0)
        rsi  = sig.get("RSI", 50)
        atr  = sig.get("ATR", 0)
        icon = "🟢" if dire == "BULLISH" else "🔴" if dire == "BEARISH" else "🟡"

        tp1 = price + atr*1.5 if dire == "BULLISH" else price - atr*1.5
        sl  = price - atr     if dire == "BULLISH" else price + atr

        text = (
            f"{icon} *تحديث ساعي — GOLD*\n"
            f"🕐 {now_local().strftime('%H:%M') + ' (GMT+2)'} UTC\n\n"
            f"💰 السعر: *{fmt_price(price)}*\n"
            f"📊 الاتجاه: *{dire}*\n"
            f"BUY {bs}/12 · SELL {ss}/12\n"
            f"RSI: {rsi:.1f}\n\n"
            f"TP1: `{tp1:.3f}` · SL: `{sl:.3f}`"
        )
        for chat_id in REPORT_CHAT_IDS:
            await context.bot.send_message(
                chat_id=chat_id, text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_keyboard()
            )
    except Exception as e:
        log.error(f"auto_hourly_signal error: {e}")


async def check_strong_signal(context):
    """تنبيه فوري عند إشارة قوية جداً (BUY/SELL >= 9/12)"""
    if not REPORT_CHAT_IDS:
        return
    try:
        price = get_price()
        d     = fetch_ohlcv("5min", 200)
        if not price or not d:
            return
        sig = full_analysis(d)
        bs  = sig.get("buyScore", 0)
        ss  = sig.get("sellScore", 0)
        dire= sig.get("direction", "NEUTRAL")
        atr = sig.get("ATR", 0)

        # Only alert on very strong signals
        if bs < 9 and ss < 9:
            return

        # Avoid duplicate alerts (check last alert time)
        now = time.time()
        last = getattr(check_strong_signal, '_last_alert', 0)
        if now - last < 1800:  # Don't repeat within 30 min
            return
        check_strong_signal._last_alert = now

        if bs >= 9:
            icon = "🚀🟢"
            signal_txt = f"إشارة شراء قوية جداً! ({bs}/12)"
            tp1 = price + atr*1.5
            tp2 = price + atr*3
            sl  = price - atr
        else:
            icon = "⚡🔴"
            signal_txt = f"إشارة بيع قوية جداً! ({ss}/12)"
            tp1 = price - atr*1.5
            tp2 = price - atr*3
            sl  = price + atr

        text = (
            f"{icon} *تنبيه إشارة قوية!*\n"
            f"⏰ {now_local().strftime('%H:%M:%S') + ' (GMT+2)'} UTC\n\n"
            f"💰 السعر: *{fmt_price(price)}*\n"
            f"📢 {signal_txt}\n\n"
            f"🎯 TP1: `{tp1:.3f}`\n"
            f"🎯 TP2: `{tp2:.3f}`\n"
            f"🛑 SL:  `{sl:.3f}`\n\n"
            f"⚡ *ادخل الآن أو لا تدخل!*"
        )
        for chat_id in REPORT_CHAT_IDS:
            # Send with notification sound (default Telegram behavior)
            await context.bot.send_message(
                chat_id=chat_id, text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_keyboard()
            )
    except Exception as e:
        log.error(f"check_strong_signal error: {e}")


async def check_level_break(context):
    """تنبيه عند كسر مستوى Pivot أو EMA مهم"""
    if not REPORT_CHAT_IDS:
        return
    try:
        price = get_price_cached()
        d     = fetch_ohlcv_cached("1day", 10)
        if not price or not d:
            return

        H = max(d["high"][-5:])
        L = min(d["low"][-5:])
        C = d["close"][-1]
        PP = (H+L+C)/3
        R1 = 2*PP - L
        S1 = 2*PP - H

        # Check for level breaks
        last_price = getattr(check_level_break, '_last_price', price)
        check_level_break._last_price = price

        alerts_to_send = []

        # Pivot PP break
        if last_price < PP <= price:
            alerts_to_send.append(f"📌 كسر فوق Pivot PP: `{PP:.3f}`")
        elif last_price > PP >= price:
            alerts_to_send.append(f"📌 كسر تحت Pivot PP: `{PP:.3f}`")

        # R1 break (bullish)
        if last_price < R1 <= price:
            alerts_to_send.append(f"🚀 اختراق R1: `{R1:.3f}` — إشارة صاعدة قوية!")

        # S1 break (bearish)
        if last_price > S1 >= price:
            alerts_to_send.append(f"⚠️ كسر S1: `{S1:.3f}` — إشارة هابطة!")

        if alerts_to_send:
            text = (
                f"🔔 *تنبيه كسر مستوى!*\n"
                f"💰 السعر: *{fmt_price(price)}*\n\n" +
                "\n".join(alerts_to_send)
            )
            for chat_id in REPORT_CHAT_IDS:
                await context.bot.send_message(
                    chat_id=chat_id, text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=main_keyboard()
                )
    except Exception as e:
        log.error(f"check_level_break error: {e}")


def main():
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_TOKEN_HERE":
        print("❌ أضف TELEGRAM_TOKEN في الكود أو كـ environment variable")
        return
    if TWELVEDATA_KEY == "YOUR_TWELVEDATA_KEY_HERE":
        print("❌ أضف TWELVEDATA_KEY في الكود أو كـ environment variable")
        return

    print("🥇 GOLD MASTER BOT Starting...")
    print(f"   Claude AI: {'✅' if HAS_CLAUDE and CLAUDE_KEY else '❌ (اختياري)'}")
    print(f"   ta library: {'✅' if HAS_TA else '⚠️ (built-in indicators)'}")

    app = (ApplicationBuilder()
           .token(TELEGRAM_TOKEN)
           .build())

    # Commands
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("price",     cmd_price))
    app.add_handler(CommandHandler("analysis",  cmd_analysis))
    app.add_handler(CommandHandler("trade",     cmd_trade))
    app.add_handler(CommandHandler("mtf",       cmd_mtf))
    app.add_handler(CommandHandler("pivots",    cmd_pivots))
    app.add_handler(CommandHandler("fib",       cmd_fib))
    app.add_handler(CommandHandler("smc",       cmd_smc))
    app.add_handler(CommandHandler("report",    cmd_report))
    app.add_handler(CommandHandler("alert",     cmd_alert))
    app.add_handler(CommandHandler("setalert",  cmd_set_alert))
    app.add_handler(CommandHandler("alerts",    cmd_alerts_list))
    app.add_handler(CommandHandler("ai",        cmd_ai))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Jobs — async (no threading issues)
    jq = app.job_queue
    if jq is not None:
        jq.run_repeating(check_and_send_alerts, interval=300, first=30)
        # Hourly auto-signal
        jq.run_repeating(auto_hourly_signal, interval=3600, first=30)
        # Strong signal check every 5 minutes
        jq.run_repeating(check_strong_signal, interval=900, first=120)
        # Level break check every 2 minutes
        jq.run_repeating(check_level_break, interval=600, first=180)
        from datetime import time as dtime
        jq.run_daily(send_daily_report, time=dtime(7, 0))
        jq.run_daily(send_daily_report, time=dtime(20, 0))

    print("✅ Bot is running! Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
