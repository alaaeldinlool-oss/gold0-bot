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

# ================= USD/EGP ENGINE =================
_usd_egp_cache = {
    'rate': None,
    'time': 0
}

def get_usd_egp():
    global _usd_egp_cache
    now = time.time()

    if _usd_egp_cache['rate'] and now - _usd_egp_cache['time'] < 60:
        return _usd_egp_cache['rate']

    sources = [
        "https://api.exchangerate-api.com/v4/latest/USD",
        "https://open.er-api.com/v6/latest/USD",
        "https://api.fxratesapi.com/latest?base=USD&symbols=EGP"
    ]

    for url in sources:
        try:
            r = requests.get(url, timeout=4)
            data = r.json()

            rate = None
            if "rates" in data:
                rate = data["rates"].get("EGP")
            elif "data" in data:
                rate = data["data"].get("EGP")

            if rate:
                rate = float(rate)
                if 30 < rate < 100:
                    _usd_egp_cache['rate'] = rate
                    _usd_egp_cache['time'] = now
                    return rate

        except Exception as e:
            print("USD SOURCE FAIL:", url, e)

    return _usd_egp_cache.get('rate', 50.0)
# ==================================================

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
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

try:
    from pymongo import MongoClient
    HAS_MONGO = True
except ImportError:
    HAS_MONGO = False

from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, JobQueue
)
from telegram.constants import ParseMode

# SAFE TELEGRAM PATCH (HTML ONLY)
from telegram import Message
from telegram import Bot as _BotClass

async def _safe_reply_text(self, text, args, kwargs):
    try:
        kwargs['parse_mode'] = ParseMode.HTML
        return await _orig_reply_text(self, text, args, kwargs)
    except Exception:
        return await _orig_reply_text(self, text, args, kwargs)

async def _safe_send_message(self, args, kwargs):
    try:
        if 'text' in kwargs:
            kwargs['parse_mode'] = ParseMode.HTML
        return await _orig_send_message(self, args, kwargs)
    except Exception:
        return await _orig_send_message(self, args, kwargs)

if not hasattr(Message, '_patched_safe'):
    _orig_reply_text = Message.reply_text
    Message.reply_text = _safe_reply_text
    Message._patched_safe = True

if not hasattr(_BotClass, '_patched_safe'):
    _orig_send_message = _BotClass.send_message
    _BotClass.send_message = _safe_send_message
    _BotClass._patched_safe = True


# ════════════════════════════════════════════════════════════════
#  ⚠️  CONFIG — ضع بياناتك هنا أو في environment variables
# ════════════════════════════════════════════════════════════════

# Telegram Bot Token — احصل عليه من @BotFather
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8718855546:AAGyI5ltYabZtbNQnmna1OwbztbIZ5KzNo0")

# TwelveData API Key — twelvedata.com (free plan: 800 req/day)
TWELVEDATA_KEY  = os.getenv("TWELVEDATA_KEY",  "dba6442c915a4bcf8234161b5c97c92e")

# Groq API Key (مجاني — من console.groq.com)
GROQ_KEY        = os.getenv("GROQ_KEY",        "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")

# MongoDB URI (لحفظ الإشارات والإحصائيات)
MONGODB_URI     = os.getenv("MONGODB_URI",     "mongodb+srv://alaaeldinlool_db_user:97sJMDccaJjmszje@cluster0.oufdfub.mongodb.net/?appName=Cluster0")

# Chat IDs for daily reports (أضف الـ chat IDs اللي تحب ترسلها)
REPORT_CHAT_IDS = [6141014695]  #


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
#  MONGODB — حفظ الإشارات والإحصائيات
# ════════════════════════════════════════════════════════════════

_mongo_db = None

def get_db():
    """اتصال بـ MongoDB"""
    global _mongo_db
    if _mongo_db is not None:
        return _mongo_db
    if not HAS_MONGO or not MONGODB_URI:
        return None
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        _mongo_db = client['goldbot']
        log.info("✅ MongoDB connected")
        return _mongo_db
    except Exception as e:
        log.warning(f"MongoDB connection failed: {e}")
        return None

def save_signal(chat_id: int, direction: str, price: float,
                tp1: float, tp2: float, sl: float):
    """احفظ الإشارة في MongoDB"""
    db = get_db()
    if db is None:
        return
    try:
        db.signals.insert_one({
            'chat_id':   chat_id,
            'direction': direction,
            'price':     price,
            'tp1':       tp1,
            'tp2':       tp2,
            'sl':        sl,
            'result':    'pending',   # pending / tp1 / tp2 / sl
            'pnl':       0.0,
            'time':      now_local().isoformat(),
        })
    except Exception as e:
        log.warning(f"save_signal error: {e}")

def update_signals_result():
    """راجع الإشارات المفتوحة وشوف هل وصلت TP أو SL"""
    db = get_db()
    if db is None:
        return
    try:
        price = get_price()
        if not price:
            return
        pending = list(db.signals.find({'result': 'pending'}))
        for sig in pending:
            entry  = sig['price']
            tp1    = sig['tp1']
            tp2    = sig['tp2']
            sl     = sig['sl']
            dire   = sig['direction']
            result = None
            pnl    = 0.0

            if dire == 'BULLISH':
                if price >= tp2:
                    result = 'tp2'; pnl = tp2 - entry
                elif price >= tp1:
                    result = 'tp1'; pnl = tp1 - entry
                elif price <= sl:
                    result = 'sl';  pnl = sl  - entry
            else:
                if price <= tp2:
                    result = 'tp2'; pnl = entry - tp2
                elif price <= tp1:
                    result = 'tp1'; pnl = entry - tp1
                elif price >= sl:
                    result = 'sl';  pnl = entry - sl

            if result:
                db.signals.update_one(
                    {'_id': sig['_id']},
                    {'$set': {'result': result, 'pnl': round(pnl, 2)}}
                )
    except Exception as e:
        log.warning(f"update_signals_result error: {e}")

def get_stats(chat_id: int) -> dict:
    """احسب إحصائيات الإشارات لـ chat_id"""
    db = get_db()
    if db is None:
        return {}
    try:
        signals = list(db.signals.find({'chat_id': chat_id, 'result': {'$ne': 'pending'}}))
        if not signals:
            return {}
        total   = len(signals)
        wins    = [s for s in signals if s['result'] in ('tp1','tp2')]
        losses  = [s for s in signals if s['result'] == 'sl']
        pnl_sum = sum(s['pnl'] for s in signals)
        best    = max(signals, key=lambda x: x['pnl'])
        worst   = min(signals, key=lambda x: x['pnl'])
        last10  = signals[-10:]
        return {
            'total':    total,
            'wins':     len(wins),
            'losses':   len(losses),
            'accuracy': round(len(wins)/total100, 1),
            'pnl':      round(pnl_sum, 2),
            'best':     round(best['pnl'], 2),
            'worst':    round(worst['pnl'], 2),
            'last10':   last10,
        }
    except Exception as e:
        log.warning(f"get_stats error: {e}")
        return {}

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
            def log_message(self, args): pass  # اخفي الـ logs
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

# تتبع فتح/إغلاق السيشنات
session_data: dict = {
    'asian':   {'open': None, 'high': None, 'low': None, 'active': False},
    'london':  {'open': None, 'high': None, 'low': None, 'active': False},
    'newyork': {'open': None, 'high': None, 'low': None, 'active': False},
}

# تتبع فتح/إغلاق اليوم
daily_data: dict = {
    'open':   None,
    'high':   None,
    'low':    None,
    'date':   None,
    'active': False,
}

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

_egypt_gold_cache = {'data': None, 'time': 0}

def ar_to_en(s: str) -> str:
    for i, d in enumerate('٠١٢٣٤٥٦٧٨٩'):
        s = s.replace(d, str(i))
    return s

def get_egypt_gold_prices() -> Optional[dict]:
    """احسب أسعار الذهب المصري من TwelveData (USD/EGP + XAU/USD)"""
    global _egypt_gold_cache
    now_t = time.time()
    if _egypt_gold_cache['data'] and now_t - _egypt_gold_cache['time'] < 600:
        return _egypt_gold_cache['data']
    try:
        # جيب سعر الدولار من TwelveData
        usd_egp = get_usd_egp()
        if not usd_egp:
            return None

        # جيب سعر الذهب العالمي
        gold_usd = get_price_cached()
        if not gold_usd:
            return None

        # احسب الأسعار المحلية
        eg = calc_egypt_gold(gold_usd, usd_egp)

        # هامش السوق المحلي المصري (عادة +2% على السعر العالمي)
        margin = 1.02
        g21 = round(eg['gram_21']  margin)
        g24 = round(eg['gram_24']  margin)
        g18 = round(eg['gram_18']  margin)
        g14 = round(eg['gram_14']  margin)

        data = {
            'gram_21_buy':  g21,
            'gram_21_sell': round(g21  0.993),
            'gram_24':      g24,
            'gram_18':      g18,
            'gram_14':      g14,
            'dollar_bank':  usd_egp,
            'dollar_sagha': usd_egp,
            'gold_usd':     gold_usd,
        }
        _egypt_gold_cache = {'data': data, 'time': now_t}
        log.info(f"✅ Egypt gold calculated: 21k={g21}, USD/EGP={usd_egp}")
        return data
    except Exception as e:
        log.warning(f"Egypt gold calculation failed: {e}")
    return None



