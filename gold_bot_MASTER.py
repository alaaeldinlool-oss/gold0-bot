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

async def _safe_reply_text(self, text, *args, **kwargs):
    try:
        kwargs['parse_mode'] = ParseMode.HTML
        return await _orig_reply_text(self, text, *args, **kwargs)
    except Exception:
        return await _orig_reply_text(self, text, *args, **kwargs)

async def _safe_send_message(self, *args, **kwargs):
    try:
        if 'text' in kwargs:
            kwargs['parse_mode'] = ParseMode.HTML
        return await _orig_send_message(self, *args, **kwargs)
    except Exception:
        return await _orig_send_message(self, *args, **kwargs)

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
            'accuracy': round(len(wins)/total*100, 1),
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

        # هامش السوق المحلي المصري (+2%)
        margin = 1.02
        g21 = round(eg['gram_21'] * margin)
        g24 = round(eg['gram_24'] * margin)
        g18 = round(eg['gram_18'] * margin)
        g14 = round(eg['gram_14'] * margin)

        # دولار البنك الحقيقي من gold-price-live
        usd_sagha = get_sagha_rate()

        data = {
            'gram_21_buy':  g21,
            'gram_21_sell': round(g21 * 0.993),
            'gram_24':      g24,
            'gram_18':      g18,
            'gram_14':      g14,
            'dollar_bank':  usd_egp,
            'dollar_sagha': usd_sagha,
            'gold_usd':     gold_usd,
        }
        _egypt_gold_cache = {'data': data, 'time': now_t}
        log.info(f"✅ Egypt gold calculated: 21k={g21}, USD/EGP={usd_egp}")
        return data
    except Exception as e:
        log.warning(f"Egypt gold calculation failed: {e}")
    return None



def get_usd_egp() -> Optional[float]:
    """جيب سعر الدولار — من gold-price-live.com أو TwelveData أو APIs مجانية"""
    global _usd_egp_cache
    now_t = time.time()
    if _usd_egp_cache['rate'] and now_t - _usd_egp_cache['time'] < 1800:
        return _usd_egp_cache['rate']

    # ── المصدر الأول: gold-price-live.com (الأدق للسوق المصري) ──
    try:
        import re
        r = requests.get('https://gold-price-live.com/', timeout=8,
                         headers={'User-Agent': 'Mozilla/5.0'})
        text = r.text

        # دولار البنوك
        m_bank = re.search(r'الدولار في البنوك\s*\n\s*([\d.]+)\s*جنيه', text)
        # دولار الصاغة
        m_sagha = re.search(r'دولار الصاغة الآن\s*\n\s*([\d.]+)\s*جنيه', text)

        bank_rate  = float(m_bank.group(1))  if m_bank  else None
        sagha_rate = float(m_sagha.group(1)) if m_sagha else None

        if bank_rate and 40 < bank_rate < 100:
            _usd_egp_cache = {
                'rate':       bank_rate,
                'sagha_rate': sagha_rate or round(bank_rate - 0.55, 2),
                'time':       now_t
            }
            log.info(f"✅ USD/EGP from gold-price-live: bank={bank_rate}, sagha={sagha_rate}")
            return bank_rate
    except Exception as e:
        log.warning(f"gold-price-live USD/EGP failed: {e}")

    # ── المصدر الثاني: TwelveData ──
    try:
        url  = f"https://api.twelvedata.com/price?symbol=USD/EGP&apikey={TWELVEDATA_KEY}"
        r    = requests.get(url, timeout=8)
        data = r.json()
        if 'price' in data:
            rate = float(data['price'])
            if rate > 0:
                _usd_egp_cache = {'rate': rate, 'sagha_rate': round(rate - 0.55, 2), 'time': now_t}
                log.info(f"✅ USD/EGP from TwelveData: {rate}")
                return rate
    except Exception as e:
        log.warning(f"TwelveData USD/EGP failed: {e}")

    # ── المصادر الاحتياطية ──
    sources = [
        ("https://api.exchangerate-api.com/v4/latest/USD",  'rates'),
        ("https://open.er-api.com/v6/latest/USD",            'conversion_rates'),
        ("https://api.fxratesapi.com/latest?base=USD",       'rates'),
    ]
    for url, key in sources:
        try:
            r    = requests.get(url, timeout=8)
            data = r.json()
            if key in data and 'EGP' in data[key]:
                rate = float(data[key]['EGP'])
                if rate > 0:
                    _usd_egp_cache = {'rate': rate, 'sagha_rate': round(rate - 0.55, 2), 'time': now_t}
                    log.info(f"✅ USD/EGP from {url}: {rate}")
                    return rate
        except Exception as e:
            log.warning(f"USD/EGP failed {url}: {e}")

    if _usd_egp_cache.get('rate'):
        return _usd_egp_cache['rate']
    return None

def get_sagha_rate() -> float:
    """جيب سعر دولار الصاغة"""
    get_usd_egp()  # refresh cache
    return _usd_egp_cache.get('sagha_rate') or (_usd_egp_cache.get('rate', 52.0) - 0.55)

def calc_egypt_gold(gold_usd: float, usd_egp: float) -> dict:
    """
    احسب سعر الذهب المصري بكل العيارات
    gold_usd = سعر الأوقية بالدولار
    usd_egp  = سعر الدولار بالجنيه
    """
    # 1 أوقية = 31.1035 جرام
    gram_24 = (gold_usd / 31.1035) * usd_egp

    return {
        'usd_egp': usd_egp,
        'gram_24': gram_24,
        'gram_21': gram_24 * 0.875,
        'gram_18': gram_24 * 0.750,
        'gram_14': gram_24 * 0.585,
        'ounce':   gold_usd * usd_egp,
    }

def fmt_egypt_gold_msg(gold_usd: float) -> str:
    """رسالة أسعار الذهب المصري — من السوق المحلي مباشرة"""
    local = get_egypt_gold_prices()

    if local and local.get('gram_21_buy'):
        usd_egp  = local.get('dollar_bank') or local.get('dollar_sagha') or get_usd_egp() or 52.0
        g21_buy  = local['gram_21_buy']
        g21_sell = local.get('gram_21_sell') or g21_buy
        g18      = local.get('gram_18') or g21_buy * 0.857
        g24      = local.get('gram_24') or g21_buy * 1.143
        g14      = round(g21_buy * 0.667)
        ounce    = round(g24 * 31.1035)
        d_sagha  = local.get('dollar_sagha')

        lines = [
            "🇪🇬 أسعار الذهب في مصر",
            "🔴 مباشر من السوق",
            "",
            f"💵 الدولار البنوك: {usd_egp:.2f} جنيه",
        ]
        if d_sagha:
            lines.append(f"💱 دولار الصاغة: {d_sagha:.2f} جنيه")
        lines += [
            f"🥇 الذهب عالمياً: ${gold_usd:,.2f}",
            "",
            "📊 سعر الجرام:",
            "",
            f"🔸 عيار 24:       {g24:,.0f} جنيه",
            f"🔸 عيار 21 بيع:  {g21_buy:,.0f} جنيه",
            f"🔸 عيار 21 شراء: {g21_sell:,.0f} جنيه",
            f"🔸 عيار 18:       {g18:,.0f} جنيه",
            f"🔸 عيار 14:       {g14:,.0f} جنيه",
            "",
            f"🏅 الأوقية: {ounce:,.0f} جنيه",
            "",
            "📡 محسوب من TwelveData (XAU/USD + USD/EGP)",
            f"🕐 {now_local().strftime('%H:%M:%S')} GMT+2",
        ]
    else:
        usd_egp = get_usd_egp() or 52.0
        eg = calc_egypt_gold(gold_usd, usd_egp)
        lines = [
            "🇪🇬 أسعار الذهب في مصر",
            "⚠️ تقريبي",
            "",
            f"💵 الدولار: {usd_egp:.2f} جنيه",
            f"🥇 الذهب عالمياً: ${gold_usd:,.2f}",
            "",
            "📊 سعر الجرام تقريبي:",
            "",
            f"🔸 عيار 24: {eg['gram_24']:,.0f} جنيه",
            f"🔸 عيار 21: {eg['gram_21']:,.0f} جنيه",
            f"🔸 عيار 18: {eg['gram_18']:,.0f} جنيه",
            f"🔸 عيار 14: {eg['gram_14']:,.0f} جنيه",
            "",
            "⚠️ فشل جلب السعر المحلي",
            f"🕐 {now_local().strftime('%H:%M:%S')} GMT+2",
        ]
    return '\n'.join(lines)

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
#  GANN ANALYSIS
# ════════════════════════════════════════════════════════════════

def calc_gann_square(price: float) -> dict:
    """Gann Square of Nine — مستويات دعم ومقاومة"""
    import math
    root = math.sqrt(price)

    # الزوايا الصحيحة: كل 0.25 على الجذر = 45° على المربع
    angle_labels = ['45°', '90°', '135°', '180°', '225°', '270°', '315°', '360°']
    resistance = []
    support    = []

    for i, lbl in enumerate(angle_labels, 1):
        step = i * 0.25
        r = round((root + step) ** 2, 2)
        s = round(max(root - step, 0.1) ** 2, 2)
        if r > price:
            resistance.append({'level': r, 'angle': lbl})
        if 0 < s < price:
            support.append({'level': s, 'angle': lbl})

    return {
        'price':      price,
        'root':       round(root, 4),
        'resistance': resistance[:5],
        'support':    support[:5],
    }


def calc_gann_fan(H: float, L: float, price: float) -> dict:
    """
    Gann Fan — خطوط الزوايا من قمة أو قاع
    الزوايا: 1x8, 1x4, 1x3, 1x2, 1x1, 2x1, 3x1, 4x1, 8x1
    """
    rng   = H - L
    # نسب زوايا Gann
    ratios = {
        '1x8 (82.5°)': 1/8,
        '1x4 (75°)':   1/4,
        '1x3 (71.25°)':1/3,
        '1x2 (63.75°)':1/2,
        '1x1 (45°) ⭐': 1.0,
        '2x1 (26.25°)':2.0,
        '3x1 (18.75°)':3.0,
        '4x1 (15°)':   4.0,
        '8x1 (7.5°)':  8.0,
    }
    
    # حساب المستويات من القاع (صاعد) والقمة (هابط)
    fan_from_low  = {}
    fan_from_high = {}
    
    for label, ratio in ratios.items():
        fan_from_low[label]  = round(L + rng * ratio, 3)
        fan_from_high[label] = round(H - rng * ratio, 3)
    
    # تحديد الزاوية الحالية
    current_ratio = (price - L) / rng if rng > 0 else 0
    if current_ratio >= 0.875:
        current_angle = "1x8 (82.5°) - قوي جداً"
    elif current_ratio >= 0.75:
        current_angle = "1x4 (75°) - قوي"
    elif current_ratio >= 0.5:
        current_angle = "1x1 (45°) - متوازن"
    elif current_ratio >= 0.25:
        current_angle = "2x1 (26.25°) - ضعيف"
    else:
        current_angle = "4x1 (15°) - ضعيف جداً"
    
    return {
        'H': H, 'L': L,
        'price': price,
        'fan_from_low':  fan_from_low,
        'fan_from_high': fan_from_high,
        'current_angle': current_angle,
        'current_ratio': round(current_ratio * 100, 1),
    }




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
        f"📈 المؤشرات:",
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
            f"🎯 Entry · TP · SL:",
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
        f"💰 السعر: *{fmt_price(price)}* - [{zone}]",
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
        lines.append("📦 Order Blocks:")
        for ob in obs:
            near  = abs((ob['top']+ob['bottom'])/2 - price) / price < 0.012
            color = '🟦' if ob['type']=='BULL' else '🟥'
            note  = ' ← السعر قريب! 🎯' if near else ''
            lines.append(f"  {color} {ob['type']} OB: {ob['bottom']:.2f}–{ob['top']:.2f}{note}")
        lines.append("")

    if fvgs:
        lines.append("⬜ Fair Value Gaps:")
        for fvg in fvgs:
            icon  = '⬆️' if fvg['type']=='BULL' else '⬇️'
            near  = abs((fvg['top']+fvg['bottom'])/2 - price) / price < 0.008
            note  = ' ← داخل FVG!' if near else ''
            lines.append(f"  {icon} {fvg['type']} FVG: {fvg['bottom']:.2f}–{fvg['top']:.2f}{note}")

    lines.append(f"\n🕐 {now_local().strftime('%H:%M:%S') + ' (GMT+2)'}")
    lines.append("╚══════════════════════════╝")
    return '\n'.join(lines)

# ════════════════════════════════════════════════════════════════
#  SESSION ANALYSIS — تحليل السيشن
# ════════════════════════════════════════════════════════════════

SESSIONS = {
    'asian': {
        'name':    '🌏 Asian Session',
        'name_ar': 'السيشن الآسيوي',
        'start':   0,   # UTC
        'end':     8,   # UTC
        'color':   '🟡',
        'nature':  'هادئ — حركة محدودة وتذبذب ضيق',
        'tip':     'تجنب الدخول في إشارات قوية — السيولة منخفضة',
        'gold':    'الذهب بيتحرك في نطاق ضيق عادةً',
        'risk':    '⚠️ منخفض الحركة',
    },
    'london': {
        'name':    '🏦 London Session',
        'name_ar': 'السيشن الأوروبي',
        'start':   8,   # UTC
        'end':     16,  # UTC
        'color':   '🟢',
        'nature':  'نشيط — أعلى سيولة في اليوم',
        'tip':     'أفضل وقت للتداول — الاتجاه بيتحدد هنا',
        'gold':    'أكبر حركة في الذهب تحصل في London',
        'risk':    '✅ عالي الحركة',
    },
    'newyork': {
        'name':    '🗽 New York Session',
        'name_ar': 'السيشن الأمريكي',
        'start':   13,  # UTC
        'end':     21,  # UTC
        'color':   '🔵',
        'nature':  'متوسط إلى نشيط — تأثير الأخبار الأمريكية',
        'tip':     'راقب أخبار الـ Fed والتضخم — بتأثر على الذهب مباشرة',
        'gold':    'الذهب حساس جداً لبيانات الدولار في هذا الوقت',
        'risk':    '✅ عالي الحركة',
    },
    'overlap': {
        'name':    '⚡ London-NY Overlap',
        'name_ar': 'تداخل London و New York',
        'start':   13,
        'end':     16,
        'color':   '🔥',
        'nature':  'الأقوى في اليوم — أعلى سيولة وأكبر حركة',
        'tip':     'أفضل وقت للإشارات القوية — الحركة ممتازة',
        'gold':    'أعلى تذبذب في الذهب — فرص كثيرة',
        'risk':    '🔥 أعلى حركة',
    },
}

def get_current_session() -> dict:
    """احسب السيشن الحالي بناءً على الوقت UTC"""
    utc_hour = datetime.now(timezone.utc).hour

    # تداخل London-NY (الأقوى)
    if 13 <= utc_hour < 16:
        s = SESSIONS['overlap'].copy()
        s['active'] = True
        s['next'] = 'New York ينتهي الـ Overlap ويكمل'
        s['hours_left'] = 16 - utc_hour
        return s

    # London
    if 8 <= utc_hour < 16:
        s = SESSIONS['london'].copy()
        s['active'] = True
        s['next'] = '⚡ Overlap مع New York يبدأ الساعة 13:00 UTC'
        s['hours_left'] = 16 - utc_hour
        return s

    # New York
    if 13 <= utc_hour < 21:
        s = SESSIONS['newyork'].copy()
        s['active'] = True
        s['next'] = '🌏 Asian Session يبدأ الساعة 00:00 UTC'
        s['hours_left'] = 21 - utc_hour
        return s

    # Asian
    s = SESSIONS['asian'].copy()
    s['active'] = True
    if utc_hour < 8:
        s['next'] = '🏦 London Session يبدأ الساعة 08:00 UTC'
        s['hours_left'] = 8 - utc_hour
    else:
        s['next'] = '🌏 Asian Session يبدأ منتصف الليل'
        s['hours_left'] = 24 - utc_hour
    return s

def fmt_session_msg(price: float, sig: dict) -> str:
    """رسالة تحليل السيشن الكاملة"""
    utc_now  = datetime.now(timezone.utc)
    local_now= now_local()
    session  = get_current_session()

    # السيشن القادم
    sessions_order = [
        ('🌏 Asian',         '00:00', '08:00', 'UTC'),
        ('🏦 London',        '08:00', '16:00', 'UTC'),
        ('⚡ London-NY',     '13:00', '16:00', 'UTC'),
        ('🗽 New York',      '13:00', '21:00', 'UTC'),
    ]

    dire = sig.get('direction', 'NEUTRAL')
    bs   = sig.get('buyScore', 0)
    ss   = sig.get('sellScore', 0)
    atr  = sig.get('ATR', 0)

    # توافق الإشارة مع السيشن
    if session['name_ar'] == 'السيشن الآسيوي':
        compat = '⚠️ سيولة منخفضة — إشارات أقل موثوقية'
    elif dire == 'NEUTRAL':
        compat = '⏳ لا توجد إشارة واضحة دلوقتي'
    elif bs >= 8 or ss >= 8:
        compat = '🔥 إشارة قوية في سيشن نشيط — فرصة ممتازة!'
    else:
        compat = '📊 إشارة متوسطة — انتظر تأكيد أكتر'

    lines = [
        f"╔══ 🕐 SESSION ANALYSIS ══╗",
        f"",
        f"{session['color']} السيشن الحالي:",
        f"   {session['name']}",
        f"   ({session['name_ar']})",
        f"",
        f"⏰ الوقت:",
        f"   🌍 UTC:    `{utc_now.strftime('%H:%M')}`",
        f"   🇪🇬 GMT+2: `{local_now.strftime('%H:%M')}`",
        f"   ⏳ متبقي: `{session['hours_left']} ساعة تقريباً`",
        f"",
        f"📊 طبيعة السيشن:",
        f"   {session['nature']}",
        f"   {session['risk']}",
        f"",
        f"🥇 الذهب في هذا السيشن:",
        f"   {session['gold']}",
        f"",
        f"💡 نصيحة:",
        f"   {session['tip']}",
        f"",
        f"📈 الإشارة الحالية:",
        f"   💰 السعر: *{fmt_price(price)}*",
        f"   {'🟢 BULLISH' if dire=='BULLISH' else '🔴 BEARISH' if dire=='BEARISH' else '🟡 NEUTRAL'}",
        f"   BUY {bs}/12 · SELL {ss}/12",
        f"",
        f"🔗 التوافق مع السيشن:",
        f"   {compat}",
        f"",
        f"⏭ القادم:",
        f"   {session['next']}",
        f"",
        f"╚══════════════════════════╝",
    ]
    return '\n'.join(lines)


async def cmd_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /session — تحليل السيشن الحالي"""
    await update.message.reply_text("⏳ جاري تحليل السيشن...")
    price = get_price_cached()
    d     = fetch_ohlcv_cached('1h', 200)
    if not price or not d:
        await update.message.reply_text("❌ فشل جلب البيانات.")
        return
    sig = full_analysis(d)
    await update.message.reply_text(
        fmt_session_msg(price, sig),
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard()
    )


async def notify_session_start(context):
    """تنبيه تلقائي لما سيشن قوي يبدأ"""
    if not alert_subscribers:
        return
    utc_hour = datetime.now(timezone.utc).hour
    utc_min  = datetime.now(timezone.utc).minute

    # بعت التنبيه بس في أول 5 دقائق من بداية السيشن
    if utc_min > 5:
        return

    msg = None
    if utc_hour == 8:
        msg = ("🏦 London Session بدأ!\n\n"
               "أعلى سيولة في اليوم 🔥\n"
               "راقب الذهب — الاتجاه بيتحدد دلوقتي\n"
               "✅ أفضل وقت للتداول")
    elif utc_hour == 13:
        msg = ("⚡ London-NY Overlap بدأ!\n\n"
               "🔥 أقوى وقت في اليوم!\n"
               "أعلى سيولة وأكبر حركة\n"
               "🎯 فرص إشارات قوية الآن")
    elif utc_hour == 0:
        msg = ("🌏 Asian Session بدأ\n\n"
               "⚠️ سيولة منخفضة\n"
               "حركة محدودة في الذهب\n"
               "انتظر London Session الساعة 08:00 UTC")

    if msg:
        price = get_price_cached()
        if price:
            msg += f"\n\n💰 السعر الحالي: *{fmt_price(price)}*"
        for chat_id in list(alert_subscribers):
            try:
                await context.bot.send_message(
                    chat_id=chat_id, text=msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=main_keyboard()
                )
            except Exception as e:
                log.warning(f"session notify error: {e}")


async def track_sessions(context):
    """يتتبع فتح وإغلاق كل سيشن ويبعت تقرير"""
    try:
        price = get_price_cached()
        if not price:
            return

        utc_hour = datetime.now(timezone.utc).hour
        utc_min  = datetime.now(timezone.utc).minute

        # تعريف السيشنات
        sessions_config = {
            'asian':   {'start': 0,  'end': 8,  'icon': '🌏', 'name': 'Asian Session'},
            'london':  {'start': 8,  'end': 16, 'icon': '🏦', 'name': 'London Session'},
            'newyork': {'start': 13, 'end': 21, 'icon': '🗽', 'name': 'New York Session'},
        }

        for key, cfg in sessions_config.items():
            s = session_data[key]

            # بداية السيشن (أول 5 دقائق)
            if utc_hour == cfg['start'] and utc_min <= 5 and not s['active']:
                s['open']   = price
                s['high']   = price
                s['low']    = price
                s['active'] = True
                s['start_time'] = now_local().strftime('%H:%M')

                text = (
                    f"{cfg['icon']} {cfg['name']} - فتح السيشن\n\n"
                    f"🟢 سعر الفتح: {fmt_price(price)}\n"
                    f"🕐 {now_local().strftime('%H:%M')} (GMT+2)\n\n"
                    f"⏳ السيشن بدأ - سيتم إرسال تقرير الإغلاق بعد انتهائه"
                )
                for chat_id in list(alert_subscribers):
                    try:
                        await context.bot.send_message(
                            chat_id=chat_id, text=text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=main_keyboard()
                        )
                    except Exception as e:
                        log.warning(f"session open notify error: {e}")

            # تحديث High/Low أثناء السيشن
            if s['active'] and cfg['start'] <= utc_hour < cfg['end']:
                if s['high'] is None or price > s['high']:
                    s['high'] = price
                if s['low'] is None or price < s['low']:
                    s['low'] = price

            # نهاية السيشن (أول 5 دقائق بعد الإغلاق)
            if utc_hour == cfg['end'] and utc_min <= 5 and s['active']:
                s['active'] = False
                close_price = price
                open_price  = s['open'] or price
                high_price  = s['high'] or price
                low_price   = s['low']  or price
                chg         = close_price - open_price
                chg_pct     = (chg / open_price * 100) if open_price else 0
                rng         = high_price - low_price
                chg_icon    = '📈' if chg >= 0 else '📉'
                sign        = '+' if chg >= 0 else ''

                text = (
                    f"{cfg['icon']} {cfg['name']} - تقرير الإغلاق\n\n"
                    f"🟢 سعر الفتح:   {fmt_price(open_price)}\n"
                    f"🔴 سعر الإغلاق: {fmt_price(close_price)}\n\n"
                    f"{chg_icon} التغيير: {sign}{chg:.2f}$ ({sign}{chg_pct:.2f}%)\n\n"
                    f"📊 أعلى سعر: {fmt_price(high_price)}\n"
                    f"📊 أدنى سعر: {fmt_price(low_price)}\n"
                    f"📏 النطاق:   {rng:.2f}$\n\n"
                    f"{'🟢 سيشن صاعد' if chg >= 0 else '🔴 سيشن هابط'}\n"
                    f"🕐 {now_local().strftime('%H:%M')} (GMT+2)"
                )

                # احفظ في MongoDB
                db = get_db()
                if db is not None:
                    try:
                        db.sessions.insert_one({
                            'session':  key,
                            'name':     cfg['name'],
                            'open':     open_price,
                            'close':    close_price,
                            'high':     high_price,
                            'low':      low_price,
                            'change':   round(chg, 2),
                            'change_pct': round(chg_pct, 2),
                            'range':    round(rng, 2),
                            'date':     now_local().strftime('%Y-%m-%d'),
                            'time':     now_local().isoformat(),
                        })
                    except Exception as e:
                        log.warning(f"session save error: {e}")

                for chat_id in list(alert_subscribers):
                    try:
                        await context.bot.send_message(
                            chat_id=chat_id, text=text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=main_keyboard()
                        )
                    except Exception as e:
                        log.warning(f"session close notify error: {e}")

                # reset
                session_data[key] = {
                    'open': None, 'high': None,
                    'low': None, 'active': False
                }

    except Exception as e:
        log.error(f"track_sessions error: {e}")


async def cmd_session_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ملخص سيشنات اليوم"""
    await update.message.reply_text("⏳ جاري جلب ملخص السيشنات...")
    db = get_db()
    if db is None:
        await update.message.reply_text("❌ MongoDB غير متصل.", reply_markup=main_keyboard())
        return
    try:
        today = now_local().strftime('%Y-%m-%d')
        # جيب سيشنات اليوم أولاً
        records = list(db.sessions.find({'date': today}).sort('time', 1))
        # لو مفيش اليوم، جيب آخر 6 سيشنات
        if not records:
            records = list(db.sessions.find().sort('time', -1).limit(6))
            label = "آخر السيشنات المسجّلة"
        else:
            label = f"سيشنات اليوم - {today}"

        if not records:
            # Fallback: احسب السيشنات من بيانات TwelveData
            try:
                d = fetch_ohlcv('1h', 24)
                if d and d.get('close'):
                    today = now_local().strftime('%Y-%m-%d')
                    sessions_def = {
                        'asian':   {'start': 0,  'end': 8,  'icon': '🌏', 'name': 'Asian Session'},
                        'london':  {'start': 8,  'end': 16, 'icon': '🏦', 'name': 'London Session'},
                        'newyork': {'start': 13, 'end': 21, 'icon': '🗽', 'name': 'New York Session'},
                    }
                    lines = [f"📋 سيشنات اليوم (محسوبة) - {today}\n"]
                    total_chg = 0
                    for key, cfg in sessions_def.items():
                        # فلتر الشمعات في وقت السيشن
                        s_candles = [
                            i for i, t in enumerate(d['time'])
                            if today in t and cfg['start'] <= int(t[11:13]) < cfg['end']
                        ]
                        if not s_candles:
                            continue
                        open_p  = d['open'][s_candles[0]]
                        close_p = d['close'][s_candles[-1]]
                        high_p  = max(d['high'][i] for i in s_candles)
                        low_p   = min(d['low'][i]  for i in s_candles)
                        chg     = close_p - open_p
                        chg_pct = (chg / open_p * 100) if open_p else 0
                        rng     = high_p - low_p
                        chg_i   = '📈' if chg >= 0 else '📉'
                        sign    = '+' if chg >= 0 else ''
                        total_chg += chg
                        lines.append(
                            f"{cfg['icon']} {cfg['name']}\n"
                            f"   🟢 فتح:   {open_p:.2f}\n"
                            f"   🔴 إغلاق: {close_p:.2f}\n"
                            f"   {chg_i} {sign}{chg:.2f}$ ({sign}{chg_pct:.2f}%)\n"
                            f"   📏 نطاق: {rng:.2f}$\n"
                        )
                    if len(lines) > 1:
                        sign = '+' if total_chg >= 0 else ''
                        icon = '📈' if total_chg >= 0 else '📉'
                        lines.append(f"{'─'*25}")
                        lines.append(f"{icon} إجمالي اليوم: {sign}{total_chg:.2f}$")
                        await update.message.reply_text(
                            '\n'.join(lines),
                            parse_mode=ParseMode.HTML,
                            reply_markup=main_keyboard()
                        )
                        return
            except Exception as e:
                log.warning(f"session fallback error: {e}")

            await update.message.reply_text(
                "📊 لا يوجد سيشنات مسجّلة بعد.\n"
                "يتم التسجيل تلقائياً عند إغلاق كل سيشن.",
                reply_markup=main_keyboard()
            )
            return

        lines = [f"📋 {label}\n"]
        total_chg = 0
        for r in records:
            icon  = '🌏' if r['session']=='asian' else '🏦' if r['session']=='london' else '🗽'
            chg_i = '📈' if r['change'] >= 0 else '📉'
            sign  = '+' if r['change'] >= 0 else ''
            total_chg += r['change']
            # وقت الفتح والإغلاق
            t = r.get('time', '')[:16].replace('T', ' ') if r.get('time') else ''
            lines.append(
                f"{icon} {r['name']}\n"
                f"   🟢 فتح:   {r['open']:.2f}\n"
                f"   🔴 إغلاق: {r['close']:.2f}\n"
                f"   {chg_i} {sign}{r['change']:.2f}$ ({sign}{r['change_pct']:.2f}%)\n"
                f"   📏 نطاق: {r['range']:.2f}$\n"
            )

        # ملخص اليوم
        if len(records) > 1:
            sign = '+' if total_chg >= 0 else ''
            icon = '📈' if total_chg >= 0 else '📉'
            lines.append(f"{'─'*25}")
            lines.append(f"{icon} إجمالي اليوم: {sign}{total_chg:.2f}$")

        await update.message.reply_text(
            '\n'.join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard()
        )
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)[:100]}")


async def send_daily_sessions_summary(context):
    """يبعت ملخص سيشنات اليوم تلقائياً عند انتهاء سيشن New York (21 UTC)"""
    if not alert_subscribers:
        return
    db = get_db()
    if db is None:
        return
    try:
        today = now_local().strftime('%Y-%m-%d')
        records = list(db.sessions.find({'date': today}).sort('time', 1))
        if not records:
            return

        lines = [f"📋 ملخص سيشنات اليوم - {today}\n"]
        total_chg = 0
        for r in records:
            icon  = '🌏' if r['session']=='asian' else '🏦' if r['session']=='london' else '🗽'
            chg_i = '📈' if r['change'] >= 0 else '📉'
            sign  = '+' if r['change'] >= 0 else ''
            total_chg += r['change']
            lines.append(
                f"{icon} {r['name']}\n"
                f"   🟢 فتح: {r['open']:.2f} | 🔴 إغلاق: {r['close']:.2f}\n"
                f"   {chg_i} {sign}{r['change']:.2f}$ ({sign}{r['change_pct']:.2f}%)\n"
            )

        sign = '+' if total_chg >= 0 else ''
        icon = '📈' if total_chg >= 0 else '📉'
        lines.append(f"{'─'*25}")
        lines.append(f"{icon} إجمالي اليوم: {sign}{total_chg:.2f}$")

        text = '\n'.join(lines)
        for chat_id in list(alert_subscribers):
            try:
                await context.bot.send_message(
                    chat_id=chat_id, text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=main_keyboard()
                )
            except Exception as e:
                log.warning(f"daily sessions summary error: {e}")
    except Exception as e:
        log.error(f"send_daily_sessions_summary error: {e}")


# ════════════════════════════════════════════════════════════════
#  DAILY & WEEKLY TRACKING
# ════════════════════════════════════════════════════════════════

DAYS_AR = {
    0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء',
    3: 'الخميس',  4: 'الجمعة',   5: 'السبت', 6: 'الأحد'
}

async def track_daily(context):
    """يتتبع فتح/إغلاق كل يوم ويحفظ في MongoDB"""
    if not alert_subscribers:
        return
    try:
        price    = get_price_cached()
        if not price:
            return

        now      = now_local()
        today    = now.strftime('%Y-%m-%d')
        utc_hour = datetime.now(timezone.utc).hour
        utc_min  = datetime.now(timezone.utc).minute

        # فتح اليوم (00:00 UTC = بداية اليوم)
        if utc_hour == 0 and utc_min <= 5:
            if daily_data['date'] != today:
                daily_data['open']   = price
                daily_data['high']   = price
                daily_data['low']    = price
                daily_data['date']   = today
                daily_data['active'] = True

        # تحديث High/Low
        if daily_data['active']:
            if daily_data['high'] is None or price > daily_data['high']:
                daily_data['high'] = price
            if daily_data['low'] is None or price < daily_data['low']:
                daily_data['low'] = price

        # إغلاق اليوم (23:55 UTC)
        if utc_hour == 23 and utc_min >= 55 and daily_data['active']:
            daily_data['active'] = False
            open_p  = daily_data['open'] or price
            high_p  = daily_data['high'] or price
            low_p   = daily_data['low']  or price
            chg     = price - open_p
            chg_pct = (chg / open_p * 100) if open_p else 0
            day_name= DAYS_AR.get(now.weekday(), '')

            db = get_db()
            if db is not None:
                db.daily.insert_one({
                    'date':       today,
                    'day_name':   day_name,
                    'weekday':    now.weekday(),
                    'open':       round(open_p, 3),
                    'close':      round(price, 3),
                    'high':       round(high_p, 3),
                    'low':        round(low_p, 3),
                    'change':     round(chg, 3),
                    'change_pct': round(chg_pct, 3),
                    'bullish':    chg >= 0,
                    'range':      round(high_p - low_p, 3),
                })
                log.info(f"Daily saved: {today} {chg:+.2f}")

    except Exception as e:
        log.error(f"track_daily error: {e}")


def get_weekly_report(weeks_back: int = 0) -> Optional[dict]:
    """جيب بيانات أسبوع من TwelveData 1day مباشرة - الأدق"""
    from datetime import date as ddate
    db  = get_db()
    now = now_local()

    days_since_monday = now.weekday()
    week_start = now - timedelta(days=days_since_monday + weeks_back * 7)
    week_end   = week_start + timedelta(days=4)
    ws = week_start.strftime('%Y-%m-%d')
    we = week_end.strftime('%Y-%m-%d')

    days = []

    # TwelveData 1day - الأدق
    try:
        d = fetch_ohlcv('1day', 14)
        if d and d.get('close'):
            for i in range(len(d['close'])):
                date_str = d['time'][i][:10]
                if ws <= date_str <= we:
                    d_obj = ddate.fromisoformat(date_str)
                    if d_obj.weekday() > 4:
                        continue
                    chg      = d['close'][i] - d['open'][i]
                    chg_pct  = (chg / d['open'][i] * 100) if d['open'][i] else 0
                    day_name = DAYS_AR.get(d_obj.weekday(), date_str)
                    days.append({
                        'date':       date_str,
                        'day_name':   day_name,
                        'weekday':    d_obj.weekday(),
                        'open':       round(d['open'][i],  3),
                        'close':      round(d['close'][i], 3),
                        'high':       round(d['high'][i],  3),
                        'low':        round(d['low'][i],   3),
                        'change':     round(chg, 3),
                        'change_pct': round(chg_pct, 3),
                        'bullish':    chg >= 0,
                        'range':      round(d['high'][i] - d['low'][i], 3),
                    })
    except Exception as e:
        log.warning(f"TwelveData weekly error: {e}")

    # اليوم الحالي من 1h لو مش في 1day
    today_str  = now.strftime('%Y-%m-%d')
    today_obj  = ddate.fromisoformat(today_str)
    is_weekday = today_obj.weekday() <= 4
    already_in = any(x['date'] == today_str for x in days)

    if ws <= today_str <= we and is_weekday and not already_in:
        try:
            d_today = fetch_ohlcv('1h', 24)
            if d_today and d_today.get('close'):
                today_candles = [i for i, t in enumerate(d_today['time']) if today_str in t]
                if today_candles:
                    open_t  = d_today['open'][today_candles[0]]
                    close_t = d_today['close'][today_candles[-1]]
                    high_t  = max(d_today['high'][i] for i in today_candles)
                    low_t   = min(d_today['low'][i]  for i in today_candles)
                    chg     = close_t - open_t
                    chg_pct = (chg / open_t * 100) if open_t else 0
                    days.append({
                        'date':       today_str,
                        'day_name':   DAYS_AR.get(today_obj.weekday(), today_str) + ' (جاري)',
                        'weekday':    today_obj.weekday(),
                        'open':       round(open_t,  3),
                        'close':      round(close_t, 3),
                        'high':       round(high_t,  3),
                        'low':        round(low_t,   3),
                        'change':     round(chg, 3),
                        'change_pct': round(chg_pct, 3),
                        'bullish':    chg >= 0,
                        'range':      round(high_t - low_t, 3),
                    })
                    days.sort(key=lambda x: x['date'])
        except Exception as e:
            log.warning(f"today data error: {e}")

    # Fallback: MongoDB
    if not days and db is not None:
        try:
            days = list(db.daily.find({
                'date': {'$gte': ws, '$lte': we}, 'weekday': {'$lte': 4}
            }).sort('date', 1))
        except Exception as e:
            log.warning(f"MongoDB weekly error: {e}")

    if not days:
        return None

    total_chg  = sum(x['change'] for x in days)
    bull_days  = [x for x in days if x['bullish']]
    bear_days  = [x for x in days if not x['bullish']]
    best_buy   = max(days, key=lambda x: x['change'])
    best_sell  = min(days, key=lambda x: x['change'])
    all_prices = [x['open'] for x in days] + [x['close'] for x in days]
    week_high  = max(all_prices)
    week_low   = min(all_prices)

    return {
        'days':       days,
        'week_start': ws,
        'week_end':   we,
        'total_chg':  round(total_chg, 2),
        'bull_days':  len(bull_days),
        'bear_days':  len(bear_days),
        'best_buy':   best_buy,
        'best_sell':  best_sell,
        'week_high':  week_high,
        'week_low':   week_low,
        'week_range': round(week_high - week_low, 2),
        'source':     'TwelveData',
    }


def fmt_weekly_msg(report: dict, prev: dict = None, label: str = "هذا الأسبوع") -> str:
    """رسالة التقرير الأسبوعي"""
    days      = report['days']
    days_done = len(days)
    days_left = max(5 - days_done, 0)
    source    = "📡 مباشر" if report.get('source') == 'live' else "💾 قاعدة بيانات"

    lines = [
        f"📅 التقرير الأسبوعي - {label}",
        f"📆 {report['week_start']} ← {report['week_end']}",
        f"📊 {days_done}/5 أيام  {source}",
        f"",
        f"أسعار الأيام:",
    ]

    for d in days:
        sign  = '+' if d['change'] >= 0 else ''
        arrow = '🟢' if d['bullish'] else '🔴'
        lines.append(
            f"{arrow} {d['day_name']}\n"
            f"   فتح: {d['open']:.2f} | إغلاق: {d['close']:.2f} | "
            f"تغيير: {sign}{d['change']:.2f}$"
        )

    if days_left > 0:
        lines.append(f"\n⏳ {days_left} يوم باقي لإكمال الأسبوع")

    # حساب النطاق من open/close بس عشان High/Low ممكن تكون غلط في MongoDB
    all_prices = [d['open'] for d in days] + [d['close'] for d in days]
    week_high  = max(all_prices)
    week_low   = min(all_prices)
    week_range = round(week_high - week_low, 2)

    lines += [
        f"",
        f"📈 ملخص الأسبوع:",
        f"{'🟢' if report['total_chg']>=0 else '🔴'} إجمالي: {'+' if report['total_chg']>=0 else ''}{report['total_chg']:.2f}$",
        f"📊 صاعدة: {report['bull_days']} | هابطة: {report['bear_days']}",
        f"📏 نطاق: {week_range:.2f}$",
        f"⬆️ أعلى: {week_high:.2f} | ⬇️ أدنى: {week_low:.2f}",
    ]

    if days_done >= 2:
        bb = report['best_buy']
        bs = report['best_sell']

        if bb['change'] >= 0:
            bb_lines = [
                f"🟢 أفضل يوم صاعد: {bb['day_name']}",
                f"   ↗ فتح {bb['open']:.2f} ← إغلاق {bb['close']:.2f} (+{bb['change']:.2f}$)",
            ]
        else:
            bb_lines = [
                f"🟡 أقل يوم خسارة: {bb['day_name']}",
                f"   ↘ فتح {bb['open']:.2f} ← إغلاق {bb['close']:.2f} ({bb['change']:.2f}$)",
            ]

        if bs['change'] < 0:
            bs_lines = [
                f"🔴 أسوأ يوم هابط: {bs['day_name']}",
                f"   ↘ فتح {bs['open']:.2f} ← إغلاق {bs['close']:.2f} ({bs['change']:.2f}$)",
            ]
        else:
            bs_lines = [
                f"🟡 أقل يوم ربح: {bs['day_name']}",
                f"   ↗ فتح {bs['open']:.2f} ← إغلاق {bs['close']:.2f} (+{bs['change']:.2f}$)",
            ]

        lines += ["", "─────────────────"] + bb_lines + [""] + bs_lines

    if prev and prev.get('total_chg') is not None:
        curr_chg = report['total_chg']
        prev_chg = prev['total_chg']
        diff     = curr_chg - prev_chg

        curr_icon = '🟢' if curr_chg >= 0 else '🔴'
        prev_icon = '🟢' if prev_chg >= 0 else '🔴'
        curr_sign = '+' if curr_chg >= 0 else ''
        prev_sign = '+' if prev_chg >= 0 else ''

        if diff > 0:
            diff_line = f"✅ الأسبوع الحالي أفضل بـ +{diff:.2f}$"
        elif diff < 0:
            diff_line = f"⚠️ الأسبوع الحالي أضعف بـ {diff:.2f}$"
        else:
            diff_line = "➡️ نفس الأداء"

        lines += [
            f"",
            f"📊 مقارنة الأسبوعين:",
            f"  {curr_icon} هذا الأسبوع:   {curr_sign}{curr_chg:.2f}$",
            f"  {prev_icon} الأسبوع الماضي: {prev_sign}{prev_chg:.2f}$",
            f"  {diff_line}",
        ]

    lines += [
        f"",
        f"🕐 {now_local().strftime('%Y-%m-%d %H:%M')} GMT+2",
    ]
    return '\n'.join(lines)


async def send_weekly_report(context):
    """يبعت التقرير الأسبوعي تلقائياً كل جمعة 21:00 UTC"""
    if not alert_subscribers:
        return
    try:
        report = get_weekly_report(0)
        prev   = get_weekly_report(1)
        if not report:
            return

        # توقع AI
        ai_text = ""
        if HAS_GROQ and GROQ_KEY:
            try:
                client = Groq(api_key=GROQ_KEY)
                prompt = (
                    f"أنت محلل ذهب محترف. بناءً على بيانات هذا الأسبوع:\n"
                    f"التغيير الإجمالي: {report['total_chg']:+.2f}$\n"
                    f"أيام صاعدة: {report['bull_days']} | هابطة: {report['bear_days']}\n"
                    f"نطاق الأسبوع: {report['week_range']:.2f}$\n"
                    f"قدم توقعك للأسبوع القادم في 3 جمل بالعربية."
                )
                resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200,
                )
                ai_text = f"\n\n🤖 توقع AI للأسبوع القادم:\n{resp.choices[0].message.content}"
            except:
                pass

        text = fmt_weekly_msg(report, prev) + ai_text

        for chat_id in list(alert_subscribers):
            try:
                await context.bot.send_message(
                    chat_id=chat_id, text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=main_keyboard()
                )
            except Exception as e:
                log.warning(f"weekly report send error: {e}")

    except Exception as e:
        log.error(f"send_weekly_report error: {e}")


async def cmd_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/weekly — التقرير الأسبوعي يدوي"""
    await update.message.reply_text("⏳ جاري إعداد التقرير الأسبوعي...")

    # هل طلب الأسبوع السابق؟
    weeks_back = 0
    if context.args and context.args[0] == 'last':
        weeks_back = 1

    report = get_weekly_report(weeks_back)
    prev   = get_weekly_report(weeks_back + 1)

    if not report:
        await update.message.reply_text(
            "📊 لا توجد بيانات كافية بعد.\n"
            "البوت يحتاج يشتغل أسبوع كامل لجمع البيانات.\n\n"
            "💡 البيانات بتتجمع تلقائياً كل يوم!",
            reply_markup=main_keyboard()
        )
        return

    label = "الأسبوع السابق" if weeks_back == 1 else "هذا الأسبوع"
    await update.message.reply_text(
        fmt_weekly_msg(report, prev, label),
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard()
    )


# ════════════════════════════════════════════════════════════════
#  GROQ AI ANALYSIS (مجاني)
# ════════════════════════════════════════════════════════════════

async def claude_analysis(sig: dict) -> str:
    if not HAS_GROQ or not GROQ_KEY:
        return "⚠️ Groq API غير مفعّل. أضف GROQ_KEY في Render Environment Variables.\nاحصل على Key المجاني من: console.groq.com"
    try:
        client = Groq(api_key=GROQ_KEY)
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

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        result = response.choices[0].message.content
        return f"🤖 تحليل Groq AI:\n\n{result}"
    except Exception as e:
        return f"⚠️ Groq error: {str(e)[:100]}"

# ════════════════════════════════════════════════════════════════
#  CHART GENERATOR — شارت احترافي بالصورة
# ════════════════════════════════════════════════════════════════

def detect_trendlines(highs: list, lows: list, n: int):
    """كشف Trendlines — بيرسم الترند الحقيقي بس"""
    swing_lows  = [(i, lows[i])  for i in range(2, n-2)
                   if lows[i]  < lows[i-1]  and lows[i]  < lows[i-2]
                   and lows[i]  < lows[i+1]  and lows[i]  < lows[i+2]]

    swing_highs = [(i, highs[i]) for i in range(2, n-2)
                   if highs[i] > highs[i-1] and highs[i] > highs[i-2]
                   and highs[i] > highs[i+1] and highs[i] > highs[i+2]]

    trendlines  = []
    price_range = max(highs) - min(lows)
    y_min       = min(lows)  - price_range * 0.05
    y_max       = max(highs) + price_range * 0.05

    # Uptrend — بس لو آخر Swing Low أعلى من أدناه (Higher Lows)
    if len(swing_lows) >= 2:
        p2 = swing_lows[-1]
        candidates = [p for p in swing_lows[:-1] if p[1] < p2[1] and p[0] < p2[0]]
        if candidates:
            p1    = min(candidates, key=lambda x: x[1])
            slope = (p2[1] - p1[1]) / max(p2[0] - p1[0], 1)
            # تأكد إن الخط صاعد فعلاً
            if slope > 0:
                x_end = min(p2[0] + 5, n - 1)
                y_end = p2[1] + slope * (x_end - p2[0])
                if y_min <= y_end <= y_max:
                    trendlines.append({
                        'type':  'up',
                        'x1': p1[0], 'y1': p1[1],
                        'x2': x_end, 'y2': y_end,
                        'color': '#26a69a',
                        'label': '📈 Uptrend',
                    })

    # Downtrend — بس لو آخر Swing High أدنى من أعلاه (Lower Highs)
    if len(swing_highs) >= 2:
        p2 = swing_highs[-1]
        candidates = [p for p in swing_highs[:-1] if p[1] > p2[1] and p[0] < p2[0]]
        if candidates:
            p1    = max(candidates, key=lambda x: x[1])
            slope = (p2[1] - p1[1]) / max(p2[0] - p1[0], 1)
            # تأكد إن الخط هابط فعلاً
            if slope < 0:
                x_end = min(p2[0] + 5, n - 1)
                y_end = p2[1] + slope * (x_end - p2[0])
                if y_min <= y_end <= y_max:
                    trendlines.append({
                        'type':  'down',
                        'x1': p1[0], 'y1': p1[1],
                        'x2': x_end, 'y2': y_end,
                        'color': '#ef5350',
                        'label': '📉 Downtrend',
                    })

    return trendlines


def generate_chart(d: dict, sig: dict, tf: str = '1H') -> Optional[bytes]:
    """يرسم شارت كاندل مع EMA + Trendlines + دعم ومقاومة"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import io

        closes = d['close'][-60:]
        opens  = d['open'][-60:]
        highs  = d['high'][-60:]
        lows   = d['low'][-60:]
        n = len(closes)
        xs = list(range(n))

        # EMAs
        ema20 = calc_ema(closes, 20)[-n:]
        ema50 = calc_ema(closes, 50)[-n:]

        # Pivot Points
        H = max(highs); L = min(lows); C = closes[-1]
        PP = (H + L + C) / 3
        R1 = 2*PP - L;  R2 = PP + (H-L)
        S1 = 2*PP - H;  S2 = PP - (H-L)

        # ATR / TP / SL
        atr  = sig.get('ATR', (H-L)*0.01)
        price= sig.get('price', C)
        dire = sig.get('direction', 'NEUTRAL')
        tp1  = price + atr*1.5 if dire=='BULLISH' else price - atr*1.5
        sl   = price - atr     if dire=='BULLISH' else price + atr

        # Trendlines
        trendlines = detect_trendlines(highs, lows, n)

        # ── رسم الشارت (subplots: شارت + RSI) ──
        fig, (ax, ax_rsi) = plt.subplots(
            2, 1, figsize=(13, 8),
            gridspec_kw={'height_ratios': [3, 1]},
            facecolor='#0d1117'
        )
        ax.set_facecolor('#0d1117')
        ax_rsi.set_facecolor('#0d1117')

        # كاندل ستيك
        for i in xs:
            o, c_, h, l = opens[i], closes[i], highs[i], lows[i]
            color = '#26a69a' if c_ >= o else '#ef5350'
            ax.plot([i, i], [l, h], color=color, linewidth=0.8, zorder=2)
            body_h = abs(c_ - o)
            body_y = min(o, c_)
            rect = plt.Rectangle((i-0.35, body_y), 0.7,
                                  max(body_h, atr*0.05),
                                  color=color, zorder=3)
            ax.add_patch(rect)

        # EMA
        ax.plot(xs, ema20, color='#f6c90e', linewidth=1.5, label='EMA 20', zorder=4)
        ax.plot(xs, ema50, color='#2196F3', linewidth=1.5, label='EMA 50', zorder=4)

        # ── Trendlines ──
        for tl in trendlines:
            ax.plot([tl['x1'], tl['x2']], [tl['y1'], tl['y2']],
                    color=tl['color'], linewidth=2.0,
                    linestyle='--' if tl['type']=='channel' else '-',
                    alpha=0.85, zorder=5,
                    label=tl['label'])
            # نقاط الارتداد
            ax.scatter(tl['x1'], tl['y1'], color=tl['color'],
                       s=40, zorder=6, alpha=0.8)

        # Pivot Lines
        ax.axhline(R1, color='#ef5350', linewidth=1.0, linestyle='--', alpha=0.7)
        ax.axhline(R2, color='#ef5350', linewidth=0.7, linestyle=':', alpha=0.5)
        ax.axhline(S1, color='#26a69a', linewidth=1.0, linestyle='--', alpha=0.7)
        ax.axhline(S2, color='#26a69a', linewidth=0.7, linestyle=':', alpha=0.5)
        ax.axhline(PP, color='#9c27b0', linewidth=0.8, linestyle='-', alpha=0.6)

        ax.text(n+0.3, R1, f'R1 {R1:.1f}', color='#ef5350', fontsize=7, va='center', fontweight='bold')
        ax.text(n+0.3, R2, f'R2 {R2:.1f}', color='#ef5350', fontsize=7, va='center', alpha=0.7)
        ax.text(n+0.3, S1, f'S1 {S1:.1f}', color='#26a69a', fontsize=7, va='center', fontweight='bold')
        ax.text(n+0.3, S2, f'S2 {S2:.1f}', color='#26a69a', fontsize=7, va='center', alpha=0.7)
        ax.text(n+0.3, PP, f'PP {PP:.1f}', color='#9c27b0', fontsize=7, va='center')

        # TP / SL
        if dire != 'NEUTRAL':
            tc = '#26a69a' if dire=='BULLISH' else '#ef5350'
            sc = '#ef5350' if dire=='BULLISH' else '#26a69a'
            ax.axhline(tp1, color=tc, linewidth=1.2, linestyle='-.', alpha=0.9)
            ax.axhline(sl,  color=sc, linewidth=1.2, linestyle='-.', alpha=0.9)
            ax.text(0.5, tp1, f'TP {tp1:.1f}', color=tc, fontsize=8, va='bottom', fontweight='bold')
            ax.text(0.5, sl,  f'SL {sl:.1f}',  color=sc, fontsize=8, va='top',    fontweight='bold')

        # السعر الحالي
        ax.axhline(price, color='#ffffff', linewidth=0.8, linestyle='-', alpha=0.4)
        ax.text(n+0.3, price, f'{price:.2f}', color='#ffffff', fontsize=9,
                va='center', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#1f2937',
                          edgecolor='white', alpha=0.8))

        # ── RSI Panel ──
        rsi_vals = calc_rsi(d['close'], 14)[-n:]
        rsi_xs   = list(range(n))
        ax_rsi.plot(rsi_xs, rsi_vals, color='#ce93d8', linewidth=1.2)
        ax_rsi.axhline(70, color='#ef5350', linewidth=0.8, linestyle='--', alpha=0.6)
        ax_rsi.axhline(30, color='#26a69a', linewidth=0.8, linestyle='--', alpha=0.6)
        ax_rsi.axhline(50, color='#ffffff', linewidth=0.5, linestyle=':', alpha=0.3)
        ax_rsi.fill_between(rsi_xs, rsi_vals, 70,
                            where=[r > 70 for r in rsi_vals],
                            color='#ef5350', alpha=0.2)
        ax_rsi.fill_between(rsi_xs, rsi_vals, 30,
                            where=[r < 30 for r in rsi_vals],
                            color='#26a69a', alpha=0.2)
        ax_rsi.set_ylim(0, 100)
        ax_rsi.set_xlim(-1, n+4)
        ax_rsi.text(n+0.3, rsi_vals[-1], f'{rsi_vals[-1]:.0f}',
                    color='#ce93d8', fontsize=8, va='center')
        ax_rsi.text(1, 72, 'OB', color='#ef5350', fontsize=7, alpha=0.7)
        ax_rsi.text(1, 25, 'OS', color='#26a69a', fontsize=7, alpha=0.7)
        ax_rsi.set_ylabel('RSI', color='#8b949e', fontsize=8)
        ax_rsi.tick_params(colors='#8b949e', labelsize=7)
        ax_rsi.spines[:].set_color('#30363d')
        ax_rsi.set_facecolor('#0d1117')

        # تنسيق
        ax.tick_params(colors='#8b949e', labelsize=8)
        ax.spines[:].set_color('#30363d')
        ax.yaxis.set_tick_params(labelright=True, labelleft=False)
        ax.yaxis.tick_right()
        ax.set_xlim(-1, n+4)
        ax.grid(True, color='#21262d', linewidth=0.5, alpha=0.5)
        ax_rsi.grid(True, color='#21262d', linewidth=0.5, alpha=0.3)

        # عنوان
        dir_ar  = '🟢 BULLISH' if dire=='BULLISH' else '🔴 BEARISH' if dire=='BEARISH' else '🟡 NEUTRAL'
        rsi_now = sig.get('RSI', 50)
        bs = sig.get('buyScore', 0); ss = sig.get('sellScore', 0)
        trend_str = ' | '.join([t['label'] for t in trendlines]) if trendlines else 'No Trend'
        ax.set_title(
            f'GOLD / USD  [{tf}]   ${price:,.2f}   {dir_ar}\n'
            f'RSI: {rsi_now:.1f}   BUY: {bs}/12   SELL: {ss}/12   {trend_str}\n'
            f'{now_local().strftime("%Y-%m-%d %H:%M")} GMT+2',
            color='white', fontsize=10, pad=8, fontweight='bold'
        )
        ax.legend(loc='upper left', facecolor='#1f2937',
                  edgecolor='#30363d', labelcolor='white', fontsize=7)

        plt.tight_layout(pad=0.5)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=130, bbox_inches='tight',
                    facecolor='#0d1117')
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    except Exception as e:
        log.error(f"generate_chart error: {e}")
        return None


async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /chart — يبعت صورة شارت احترافي"""
    tf_arg = context.args[0] if context.args else '1h'
    tf_cfg = TIMEFRAMES.get(tf_arg, TIMEFRAMES['1h'])
    await update.message.reply_text(f"⏳ جاري رسم الشارت على {tf_arg}...")
    d = fetch_ohlcv(tf_cfg['interval'], tf_cfg['outputsize'])
    if not d:
        await update.message.reply_text("❌ فشل جلب البيانات.")
        return
    sig = full_analysis(d)
    img = generate_chart(d, sig, tf_arg.upper())
    if img:
        await update.message.reply_photo(
            photo=img,
            caption=(f"📊 *GOLD [{tf_arg.upper()}]*\n"
                     f"💰 ${sig['price']:,.3f}\n"
                     f"{'🟢 BULLISH' if sig['direction']=='BULLISH' else '🔴 BEARISH' if sig['direction']=='BEARISH' else '🟡 NEUTRAL'}\n"
                     f"BUY {sig['buyScore']}/12 · SELL {sig['sellScore']}/12"),
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard()
        )
    else:
        await update.message.reply_text("❌ فشل رسم الشارت.")


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
                msg = f"🔔 إشارة جديدة!\n\n" + fmt_analysis_msg(sig, '1m')
                await context.bot.send_message(
                    chat_id=chat_id, text=msg,
                    parse_mode=ParseMode.HTML
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
                        text=f"🔔 Level Alert!\n"
                             f"{alert.get('label','')}\n"
                             f"السعر وصل: {fmt_price(price)}\n"
                             f"المستوى: {fmt_price(alert['price'])}",
                        parse_mode=ParseMode.HTML
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
        f"📈 المؤشرات:",
        f"   RSI: {sig['RSI']:.1f}  |  MACD: {'↑' if sig['MACD']['bull'] else '↓'}  |  ST: {'🟢' if sig['st_bull'] else '🔴'}",
        f"   Stoch RSI K: {sig['SRSI']['k']}",
        f"",
        f"📌 Pivot Points:",
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
            await context.bot.send_message(cid, text, parse_mode=ParseMode.HTML)
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
            InlineKeyboardButton("⬜ Gann Square",  callback_data="gann_square"),
            InlineKeyboardButton("📐 Gann Fan",     callback_data="gann_fan"),
        ],
        [
            InlineKeyboardButton("🔔 تنبيهات ON/OFF", callback_data="alert"),
            InlineKeyboardButton("📋 قائمة التنبيهات",callback_data="alerts"),
        ],
        [
            InlineKeyboardButton("🤖 AI تحليل",    callback_data="ai"),
            InlineKeyboardButton("📊 شارت",         callback_data="chart"),
            InlineKeyboardButton("❓ مساعدة",       callback_data="help"),
        ],
        [
            InlineKeyboardButton("🏆 إحصائياتي",   callback_data="stats"),
            InlineKeyboardButton("🕐 السيشن",       callback_data="session"),
            InlineKeyboardButton("📋 تاريخ السيشن", callback_data="session_history"),
        ],
        [
            InlineKeyboardButton("🇪🇬 ذهب مصر",    callback_data="egypt"),
            InlineKeyboardButton("📅 تقرير أسبوعي", callback_data="weekly"),
        ],
    ])



# ════════════════════════════════════════════════════════════════
#  DATA CACHE — يقلل الـ API requests
# ════════════════════════════════════════════════════════════════
_cache = {}

def fetch_ohlcv_cached(interval: str, outputsize: int, ttl: int = 600):
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
        rows.append(f"{threshold:>8.1f} {line}")
    trend = "↗" if prices[-1] > prices[0] else "↘" if prices[-1] < prices[0] else "→"
    rows.append(f"         {'▔'*width} {trend}")
    return "```\n" + "\n".join(rows) + "\n```"

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج ضغط الأزرار"""
    query = update.callback_query
    await query.answer()  # يوقف الـ loading على الزر

    data = query.data

    # نعمل fake update عشان نعيد استخدام نفس الـ handlers
    if data == "price":
        price = get_price_cached()
        if price:
            try:
                d = fetch_ohlcv("5min", 24)
                if d:
                    closes = d["close"]
                    high   = max(d["high"][-24:])
                    low    = min(d["low"][-24:])
                    open_  = closes[0]
                    chg    = price - open_
                    chg_pct= chg / open_ * 100
                    chg_icon = "📈" if chg >= 0 else "📉"
                    sign   = "+" if chg >= 0 else ""
                    text = (
                        f"🥇 GOLD / USD\n"
                        f"💰 السعر: {fmt_price(price)}\n\n"
                        f"{chg_icon} التغير (2 ساعة): {sign}{chg:.2f}$ ({sign}{chg_pct:.2f}%)\n"
                        f"📊 أعلى سعر:  {fmt_price(high)}\n"
                        f"📊 أدنى سعر:  {fmt_price(low)}\n\n"
                        f"🕐 {now_local().strftime('%H:%M:%S')} (GMT+2)"
                    )
                else:
                    raise Exception()
            except:
                text = (f"🥇 GOLD / USD\n"
                        f"💰 {fmt_price(price)}\n"
                        f"🕐 {now_local().strftime('%H:%M:%S')} (GMT+2)")
        else:
            text = "❌ فشل جلب السعر. تحقق من API Key."
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
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
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
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
            text = (f"{icon} إشارة التداول\n\n"
                    f"الاتجاه: {dire}\n"
                    f"السعر: {fmt_price(price)}\n\n"
                    f"TP1: {tp1:.3f}\n"
                    f"TP2: {tp2:.3f}\n"
                    f"SL:  {sl:.3f}\n\n"
                    f"BUY {bs}/12 · SELL {ss}/12")
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
                                       reply_markup=main_keyboard())

    elif data == "mtf":
        await query.message.reply_text("⏳ جاري تحليل Multi-Timeframe...",
                                       reply_markup=main_keyboard())
        lines = ["📊 MULTI-TIMEFRAME ANALYSIS\n"]
        for tf_name, tf_cfg in TIMEFRAMES.items():
            d = fetch_ohlcv(tf_cfg["interval"], tf_cfg["outputsize"])
            if d:
                sig  = full_analysis(d)
                dire = sig.get("direction","?")
                bs   = sig.get("buyScore",0)
                ss   = sig.get("sellScore",0)
                icon = "🟢" if dire=="BULLISH" else "🔴" if dire=="BEARISH" else "🟡"
                lines.append(f"{icon} *{tf_name}* - {dire} · BUY {bs} SELL {ss}")
        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML,
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
            text = (f"📌 PIVOT POINTS\n\n"
                    f"R3: {R3:.3f}\nR2: {R2:.3f}\nR1: {R1:.3f}\n"
                    f"PP: {PP:.3f} ←\n"
                    f"S1: {S1:.3f}\nS2: {S2:.3f}\nS3: {S3:.3f}\n\n"
                    f"📐 Fibonacci\n"
                    f"38.2%: {f382:.3f}\n50%: {f500:.3f}\n61.8%: {f618:.3f}")
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
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
            text = (f"📐 FIBONACCI RETRACEMENT\n"
                    f"High: {H:.3f} · Low: {L:.3f}\n"
                    f"الآن: {C:.3f} ({retrace:.1f}% retrace)\n\n"
                    f"0%:    {H:.3f}\n"
                    f"23.6%: {H-rng*.236:.3f}\n"
                    f"38.2%: {H-rng*.382:.3f} 🔑\n"
                    f"50%:   {H-rng*.5:.3f} 🔑\n"
                    f"61.8%: {H-rng*.618:.3f} 🥇 Golden\n"
                    f"78.6%: {H-rng*.786:.3f}\n"
                    f"100%:  {L:.3f}\n\n"
                    f"📈 Extensions:\n"
                    f"127.2%: {L-rng*.272:.3f}\n"
                    f"161.8%: {L-rng*.618:.3f}")
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
                                       reply_markup=main_keyboard())

    elif data == "gann_square":
        await query.message.reply_text("⏳ جاري حساب Gann Square...",
                                       reply_markup=main_keyboard())
        price = get_price_cached()
        if not price:
            text = "❌ فشل جلب السعر."
        else:
            g = calc_gann_square(price)
            lines = [
                f"⬜ GANN SQUARE OF NINE",
                f"السعر: {price:.2f}  |  الجذر: {g['root']}",
                "",
                "📈 مقاومة:",
            ]
            for r in g['resistance']:
                diff = r['level'] - price
                lines.append(f"  ▲ {r['level']:.2f}  ({r['angle']})  +{diff:.2f}$")
            lines.append("")
            lines.append("📉 دعم:")
            for s in g['support']:
                diff = price - s['level']
                lines.append(f"  ▼ {s['level']:.2f}  ({s['angle']})  -{diff:.2f}$")
            text = '\n'.join(lines)
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
                                       reply_markup=main_keyboard())

    elif data == "gann_fan":
        await query.message.reply_text("⏳ جاري حساب Gann Fan...",
                                       reply_markup=main_keyboard())
        d = fetch_ohlcv("1day", 90)
        if not d or not d.get("high"):
            text = "❌ فشل جلب البيانات."
        else:
            H     = max(d["high"])
            L     = min(d["low"])
            price = d["close"][-1]
            g     = calc_gann_fan(H, L, price)
            lines = [
                f"📐 GANN FAN",
                f"High: {H:.3f}  |  Low: {L:.3f}",
                f"السعر: {price:.3f}  ({g['current_ratio']}% من القاع)",
                f"الزاوية الحالية: {g['current_angle']}",
                "",
                "📈 Fan من القاع (صاعد):",
            ]
            for label, level in g['fan_from_low'].items():
                arrow = "← أنت هنا" if abs(level - price) < (H-L)*0.03 else ""
                marker = "▲" if level > price else "▼"
                lines.append(f"  {marker} {label}: {level:.3f} {arrow}")
            lines += [
                "",
                "📉 Fan من القمة (هابط):",
            ]
            for label, level in g['fan_from_high'].items():
                arrow = "← أنت هنا" if abs(level - price) < (H-L)*0.03 else ""
                marker = "▲" if level > price else "▼"
                lines.append(f"  {marker} {label}: {level:.3f} {arrow}")
            text = '\n'.join(lines)
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
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
            lines = ["⚡ SMART MONEY CONCEPTS\n"]
            if obs:
                lines.append("📦 Order Blocks:")
                for ob in obs[-3:]:
                    lines.append(f"  {'🟦' if ob.get('type')=='BULL_OB' else '🟥'} {ob.get('label','OB')}: `{ob.get('bottom',0):.3f}` - `{ob.get('top',0):.3f}`")
            if fvgs:
                lines.append("\n⬜ Fair Value Gaps:")
                for fvg in fvgs[-3:]:
                    lines.append(f"  {'⬆️' if fvg.get('type')=='BULL' else '⬇️'} {fvg.get('label','FVG')}: `{fvg.get('bottom',0):.3f}` - `{fvg.get('top',0):.3f}`")
            if not obs and not fvgs:
                lines.append("لا أنماط SMC واضحة حالياً")
            text = "\n".join(lines)
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
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
            text = (f"📈 GOLD MASTER REPORT\n"
                    f"🕐 {now_local().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"💰 السعر: *{fmt_price(price)}*\n"
                    f"{icon} الاتجاه: *{dire}*\n\n"
                    f"BUY Score:  {bs}/12\n"
                    f"SELL Score: {ss}/12\n"
                    f"RSI: {rsi:.1f}\n"
                    f"ATR: {atr:.3f}\n\n"
                    f"{fmt_analysis_msg(sig,'5m')}")
        await query.message.reply_text(text[:4000], parse_mode=ParseMode.HTML,
                                       reply_markup=main_keyboard())

    elif data == "alert":
        chat_id = query.message.chat_id
        if chat_id in alert_subscribers:
            alert_subscribers.discard(chat_id)
            status = "🔴 متوقف"
        else:
            alert_subscribers.add(chat_id)
            status = "🟢 مفعّل"
        text = (f"🔔 التنبيهات التلقائية\n"
                f"الحالة: {status}\n\n"
                f"لإضافة تنبيه عند مستوى معين:\n"
                f"`/setalert 3100 above وصل الهدف`")
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
                                       reply_markup=main_keyboard())

    elif data == "alerts":
        chat_id = query.message.chat_id
        user_alerts = level_alerts.get(chat_id, [])
        if not user_alerts:
            text = "📋 لا يوجد تنبيهات مضافة\n\nأضف تنبيه: /setalert 3100 above سبب"
        else:
            lines = ["📋 التنبيهات النشطة:\n"]
            for a in user_alerts:
                icon = "↑" if a["type"]=="above" else "↓"
                done = "✅" if a.get("triggered") else "⏳"
                lines.append(f"{done} {icon} `{a['price']:.3f}` - {a.get('label','')}")
            text = "\n".join(lines)
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
                                       reply_markup=main_keyboard())

    elif data == "ai":
        if not HAS_GROQ or not GROQ_KEY:
            text = ("🤖 Groq AI\n\n"
                    "❌ غير مفعّل حالياً\n\n"
                    "لتفعيله أضف في Render:\n"
                    "Key: `GROQ_KEY`\n"
                    "Value: مفتاح API من console.groq.com\n\n"
                    "الحصول على مفتاح مجاني:\n"
                    "1. روح console.groq.com\n"
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
                text = f"❌ خطأ في Groq AI: {str(e)}"
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
                                       reply_markup=main_keyboard())

    elif data == "chart":
        # أزرار اختيار الـ timeframe
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⏱ 1H",  callback_data="chart_1h"),
                InlineKeyboardButton("⏱ 4H",  callback_data="chart_4h"),
                InlineKeyboardButton("📅 1D",  callback_data="chart_1d"),
            ],
            [
                InlineKeyboardButton("⏱ 15m", callback_data="chart_15m"),
                InlineKeyboardButton("⏱ 5m",  callback_data="chart_5m"),
                InlineKeyboardButton("⏱ 1m",  callback_data="chart_1m"),
            ],
        ])
        await query.message.reply_text(
            "📊 اختر الـ Timeframe للشارت:",
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )

    elif data.startswith("chart_"):
        tf_arg = data.replace("chart_", "")
        tf_cfg = TIMEFRAMES.get(tf_arg, TIMEFRAMES['1h'])
        await query.message.reply_text(f"⏳ جاري رسم شارت {tf_arg.upper()}...",
                                       reply_markup=main_keyboard())
        d = fetch_ohlcv(tf_cfg["interval"], tf_cfg["outputsize"])
        if not d:
            await query.message.reply_text("❌ فشل جلب البيانات.",
                                           reply_markup=main_keyboard())
        else:
            sig = full_analysis(d)
            img = generate_chart(d, sig, tf_arg.upper())
            if img:
                await query.message.reply_photo(
                    photo=img,
                    caption=(f"📊 *GOLD [{tf_arg.upper()}]*\n"
                             f"💰 ${sig['price']:,.3f}\n"
                             f"{'🟢 BULLISH' if sig['direction']=='BULLISH' else '🔴 BEARISH' if sig['direction']=='BEARISH' else '🟡 NEUTRAL'}\n"
                             f"BUY {sig['buyScore']}/12 · SELL {sig['sellScore']}/12"),
                    parse_mode=ParseMode.HTML,
                    reply_markup=main_keyboard()
                )
            else:
                await query.message.reply_text("❌ فشل رسم الشارت.",
                                               reply_markup=main_keyboard())

    elif data == "weekly":
        await query.message.reply_text("⏳ جاري إعداد التقرير الأسبوعي...",
                                       reply_markup=main_keyboard())
        try:
            report = get_weekly_report(0)
            prev   = get_weekly_report(1)
            if not report:
                text = ("📊 لا توجد بيانات كافية بعد.\n"
                        "البوت يحتاج يشتغل لجمع البيانات.\n\n"
                        "💡 البيانات بتتجمع تلقائياً كل يوم!")
            else:
                text = fmt_weekly_msg(report, prev)
        except Exception as e:
            text = f"❌ خطأ في التقرير: {str(e)[:150]}"
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
                                       reply_markup=main_keyboard())

    elif data == "egypt":
        await query.message.reply_text("⏳ جاري جلب أسعار الذهب المصري...",
                                       reply_markup=main_keyboard())
        try:
            price = get_price_cached()
            if not price:
                text = "❌ فشل جلب السعر العالمي."
            else:
                # شغّل الـ scraping في thread منفصل مع timeout 15 ثانية
                loop = asyncio.get_event_loop()
                text = await asyncio.wait_for(
                    loop.run_in_executor(None, fmt_egypt_gold_msg, price),
                    timeout=15.0
                )
        except asyncio.TimeoutError:
            price = get_price_cached() or 0
            usd_egp = get_usd_egp() or 52.0
            eg = calc_egypt_gold(price, usd_egp)
            text = (
                f"🇪🇬 أسعار الذهب في مصر - تقريبي\n\n"
                f"💵 الدولار: *{usd_egp:.2f} جنيه*\n"
                f"🥇 الذهب: *${price:,.2f}*\n\n"
                f"🔸 عيار 21: *{eg['gram_21']:,.0f} جنيه*\n"
                f"🔸 عيار 18: *{eg['gram_18']:,.0f} جنيه*\n\n"
                f"⚠️ _انتهت مهلة جلب السعر المحلي_"
            )
        except Exception as e:
            text = f"❌ خطأ: {str(e)[:100]}"
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
                                       reply_markup=main_keyboard())

    elif data == "session_history":
        db = get_db()
        if db is None:
            await query.message.reply_text("❌ MongoDB غير متصل.",
                                           reply_markup=main_keyboard())
        else:
            try:
                records = list(db.sessions.find().sort('time', -1).limit(6))
                if not records:
                    text = ("📊 لا يوجد سيشنات مسجّلة بعد.\n"
                            "سيتم التسجيل تلقائياً عند فتح/إغلاق كل سيشن.")
                else:
                    lines = ["📋 تاريخ آخر السيشنات:\n"]
                    for r in records:
                        icon  = '🌏' if r['session']=='asian' else '🏦' if r['session']=='london' else '🗽'
                        chg_i = '📈' if r['change'] >= 0 else '📉'
                        sign  = '+' if r['change'] >= 0 else ''
                        lines.append(
                            f"{icon} *{r['name']}* - {r.get('date','')}\n"
                            f"   فتح: `{r['open']:.2f}` ← إغلاق: `{r['close']:.2f}`\n"
                            f"   {chg_i} {sign}{r['change']:.2f}$ ({sign}{r['change_pct']:.2f}%)\n"
                            f"   📏 نطاق: `{r['range']:.2f}$`\n"
                        )
                    text = '\n'.join(lines)
                await query.message.reply_text(text, parse_mode=ParseMode.HTML,
                                               reply_markup=main_keyboard())
            except Exception as e:
                await query.message.reply_text(f"❌ خطأ: {str(e)[:100]}",
                                               reply_markup=main_keyboard())

    elif data == "session":
        price = get_price_cached()
        d     = fetch_ohlcv_cached('1h', 200)
        if not price or not d:
            await query.message.reply_text("❌ فشل جلب البيانات.",
                                           reply_markup=main_keyboard())
        else:
            sig = full_analysis(d)
            await query.message.reply_text(
                fmt_session_msg(price, sig),
                parse_mode=ParseMode.HTML,
                reply_markup=main_keyboard()
            )

    elif data == "stats":
        chat_id = query.message.chat_id
        update_signals_result()
        stats = get_stats(chat_id)
        if not stats:
            text = ("📊 إحصائيات الإشارات\n\n"
                    "لا توجد إشارات مسجّلة بعد.\n"
                    "الإشارات القوية (+9/12) بتتسجل تلقائياً.")
        else:
            last10_lines = []
            for s in stats['last10']:
                icon = '✅' if s['result'] in ('tp1','tp2') else '❌'
                dire = '🟢' if s['direction']=='BULLISH' else '🔴'
                pnl  = f"+{s['pnl']:.1f}" if s['pnl'] >= 0 else f"{s['pnl']:.1f}"
                last10_lines.append(f"{icon} {dire} `{s['price']:.1f}` → {s['result'].upper()} ({pnl}$)")
            text = (
                f"📊 إحصائيات الإشارات\n\n"
                f"📈 إجمالي: *{stats['total']}*\n"
                f"✅ ناجحة: *{stats['wins']}  ❌ فاشلة: {stats['losses']}*\n"
                f"🎯 الدقة: *{stats['accuracy']}%*\n\n"
                f"💰 إجمالي الربح: *{'+' if stats['pnl']>=0 else ''}{stats['pnl']:.1f}$*\n"
                f"📈 أفضل: *+{stats['best']:.1f}$*\n"
                f"📉 أسوأ: *{stats['worst']:.1f}$*\n\n"
                f"⏱ آخر 10 إشارات:\n" +
                '\n'.join(last10_lines)
            )
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
                                       reply_markup=main_keyboard())

    elif data == "help":
        text = (
            "❓ GOLD MASTER BOT — المساعدة\n\n"
            "اضغط على أي زر أسفل الرسالة 👇\n\n"
            "💰 السعر — السعر الحالي للذهب\n"
            "📊 تحليل — تحليل فني كامل\n"
            "🎯 إشارة — BUY/SELL مع TP وSL\n"
            "⏱ MTF — تحليل 4 Timeframes\n"
            "📌 Pivots — مستويات الدعم والمقاومة\n"
            "🌀 Fibonacci — مستويات الفيبوناتشي\n"
            "⚡ SMC — Order Blocks وFVG\n"
            "📈 تقرير — تقرير شامل\n"
            "🔔 تنبيهات — تفعيل/تعطيل التنبيهات\n"
            "🤖 AI — تحليل بالذكاء الاصطناعي\n"
            "📊 شارت — شارت احترافي بالصورة\n\n"
            "لإضافة تنبيه:\n"
            "`/setalert 3100 above سبب`\n"
            "لشارت timeframe معين:\n"
            "`/chart 15m` أو `/chart 4h`"
        )
        await query.message.reply_text(text, parse_mode=ParseMode.HTML,
                                       reply_markup=main_keyboard())

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "صديقي"
    text = (
        f"🥇 GOLD MASTER BOT\n"
        f"أهلاً {name}! 👋\n\n"
        f"💡 اضغط أي زر للحصول على تحليل فوري\n"
        f"🔔 فعّل التنبيهات للحصول على إشارات تلقائية\n"
        f"⚡ إشارات قوية تصلك فوراً بدون طلب\n\n"
        f"اضغط على أي زر أسفل 👇"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard()
    )

async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ جاري جلب السعر...")
    price = get_price()
    if price:
        await update.message.reply_text(
            f"🥇 GOLD / USD\n💰 {fmt_price(price)}\n"
            f"🕐 {now_local().strftime('%H:%M:%S') + ' (GMT+2)'}",
            parse_mode=ParseMode.HTML,
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
        parse_mode=ParseMode.HTML,
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
            parse_mode=ParseMode.HTML
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
        fmt_mtf_msg(results), parse_mode=ParseMode.HTML
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
        fmt_pivots_msg(pv, fib, C), parse_mode=ParseMode.HTML
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
        "📐 FIBONACCI RETRACEMENT",
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
        '\n'.join(lines), parse_mode=ParseMode.HTML,
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
        parse_mode=ParseMode.HTML
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
    lines = ["📋 الـ Alerts المضبوطة:\n"]
    for i, a in enumerate(alerts, 1):
        status = '✅ تم' if a['triggered'] else '⏳ منتظر'
        lines.append(f"{i}. {'↑' if a['type']=='above' else '↓'} {fmt_price(a['price'])} - {status}")
        if a.get('label'): lines.append(f"   {a['label']}")
    await update.message.reply_text('\n'.join(lines), parse_mode=ParseMode.HTML)

async def cmd_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 جاري تحليل Claude AI...")
    d = fetch_ohlcv('1h', 200)
    if not d:
        await update.message.reply_text("❌ فشل جلب البيانات.")
        return
    sig  = full_analysis(d)
    text = await claude_analysis(sig)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات الإشارات ودقتها"""
    chat_id = update.effective_chat.id
    await update.message.reply_text("⏳ جاري حساب الإحصائيات...")

    # تحديث نتائج الإشارات المفتوحة أولاً
    update_signals_result()
    stats = get_stats(chat_id)

    if not stats:
        await update.message.reply_text(
            "📊 إحصائيات الإشارات\n\n"
            "لا توجد إشارات مسجّلة بعد.\n"
            "الإشارات القوية (+9/12) بتتسجل تلقائياً.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard()
        )
        return

    # آخر 10 إشارات
    last10_lines = []
    for s in stats['last10']:
        icon = '✅' if s['result'] in ('tp1','tp2') else '❌'
        dire = '🟢' if s['direction']=='BULLISH' else '🔴'
        pnl  = f"+{s['pnl']:.1f}" if s['pnl'] >= 0 else f"{s['pnl']:.1f}"
        last10_lines.append(f"{icon} {dire} `{s['price']:.1f}` → {s['result'].upper()} ({pnl}$)")

    text = (
        f"📊 إحصائيات الإشارات\n\n"
        f"📈 إجمالي الإشارات: *{stats['total']}*\n"
        f"✅ ناجحة: *{stats['wins']}  ❌ فاشلة: {stats['losses']}*\n"
        f"🎯 الدقة: *{stats['accuracy']}%*\n\n"
        f"💰 إجمالي الربح: *{'+' if stats['pnl']>=0 else ''}{stats['pnl']:.1f}$*\n"
        f"📈 أفضل إشارة: *+{stats['best']:.1f}$*\n"
        f"📉 أسوأ إشارة: *{stats['worst']:.1f}$*\n\n"
        f"⏱ آخر 10 إشارات:\n" +
        '\n'.join(last10_lines)
    )
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard()
    )

async def cmd_egypt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أسعار الذهب في مصر"""
    await update.message.reply_text("⏳ جاري جلب أسعار الذهب المصري...")
    try:
        price = get_price_cached()
        if not price:
            await update.message.reply_text("❌ فشل جلب السعر العالمي.")
            return
        loop = asyncio.get_event_loop()
        text = await asyncio.wait_for(
            loop.run_in_executor(None, fmt_egypt_gold_msg, price),
            timeout=15.0
        )
    except asyncio.TimeoutError:
        price   = get_price_cached() or 0
        usd_egp = get_usd_egp() or 52.0
        eg      = calc_egypt_gold(price, usd_egp)
        text    = (
            f"🇪🇬 أسعار الذهب في مصر - تقريبي\n\n"
            f"💵 الدولار: *{usd_egp:.2f} جنيه*\n\n"
            f"🔸 عيار 21: *{eg['gram_21']:,.0f} جنيه*\n"
            f"🔸 عيار 18: *{eg['gram_18']:,.0f} جنيه*\n\n"
            f"⚠️ _انتهت مهلة جلب السعر المحلي_"
        )
    except Exception as e:
        text = f"❌ خطأ: {str(e)[:100]}"
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard()
    )

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
    if not alert_subscribers:
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
            f"{icon} تحديث ساعي - GOLD\n"
            f"🕐 {now_local().strftime('%H:%M') + ' (GMT+2)'} UTC\n\n"
            f"💰 السعر: *{fmt_price(price)}*\n"
            f"📊 الاتجاه: *{dire}*\n"
            f"BUY {bs}/12 · SELL {ss}/12\n"
            f"RSI: {rsi:.1f}\n\n"
            f"TP1: `{tp1:.3f}` · SL: `{sl:.3f}`"
        )
        for chat_id in list(alert_subscribers):
            await context.bot.send_message(
                chat_id=chat_id, text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=main_keyboard()
            )
    except Exception as e:
        log.error(f"auto_hourly_signal error: {e}")


async def check_strong_signal(context):
    """تنبيه فوري عند إشارة قوية جداً (BUY/SELL >= 9/12)"""
    if not alert_subscribers:
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
            f"{icon} تنبيه إشارة قوية!\n"
            f"⏰ {now_local().strftime('%H:%M:%S') + ' (GMT+2)'} UTC\n\n"
            f"💰 السعر: *{fmt_price(price)}*\n"
            f"📢 {signal_txt}\n\n"
            f"🎯 TP1: `{tp1:.3f}`\n"
            f"🎯 TP2: `{tp2:.3f}`\n"
            f"🛑 SL:  `{sl:.3f}`\n\n"
            f"⚡ ادخل الآن أو لا تدخل!"
        )
        for chat_id in list(alert_subscribers):
            # Send with notification sound (default Telegram behavior)
            await context.bot.send_message(
                chat_id=chat_id, text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=main_keyboard()
            )
            # احفظ الإشارة في MongoDB
            save_signal(chat_id, dire, price, tp1, tp2, sl)
    except Exception as e:
        log.error(f"check_strong_signal error: {e}")


async def check_level_break(context):
    """تنبيه عند كسر مستوى Pivot أو EMA مهم"""
    if not alert_subscribers:
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
            alerts_to_send.append(f"🚀 اختراق R1: `{R1:.3f}` - إشارة صاعدة قوية!")

        # S1 break (bearish)
        if last_price > S1 >= price:
            alerts_to_send.append(f"⚠️ كسر S1: `{S1:.3f}` - إشارة هابطة!")

        if alerts_to_send:
            text = (
                f"🔔 تنبيه كسر مستوى!\n"
                f"💰 السعر: *{fmt_price(price)}*\n\n" +
                "\n".join(alerts_to_send)
            )
            for chat_id in list(alert_subscribers):
                await context.bot.send_message(
                    chat_id=chat_id, text=text,
                    parse_mode=ParseMode.HTML,
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
    print(f"   Groq AI: {'✅' if HAS_GROQ and GROQ_KEY else '❌ (أضف GROQ_KEY)'}")
    print(f"   ta library: {'✅' if HAS_TA else '⚠️ (built-in indicators)'}")

    app = (ApplicationBuilder()
           .token(TELEGRAM_TOKEN)
           .connect_timeout(30)
           .read_timeout(30)
           .write_timeout(30)
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
    app.add_handler(CommandHandler("chart",     cmd_chart))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("session",      cmd_session))
    app.add_handler(CommandHandler("sessions",     cmd_session_history))
    app.add_handler(CommandHandler("egypt",        cmd_egypt))
    app.add_handler(CommandHandler("weekly",       cmd_weekly))
    app.add_handler(CommandHandler("help",         cmd_help))
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
        # تحديث نتائج الإشارات كل 10 دقائق
        async def _update_signals(ctx):
            update_signals_result()
        jq.run_repeating(_update_signals, interval=600, first=60)
        # تنبيه بداية السيشن كل 5 دقائق (يتحقق داخلياً)
        jq.run_repeating(notify_session_start, interval=300, first=60)
        # تتبع فتح/إغلاق السيشنات كل 5 دقائق
        jq.run_repeating(track_sessions, interval=300, first=30)
        # تتبع اليومي كل 5 دقائق
        jq.run_repeating(track_daily, interval=300, first=60)
        # تقرير أسبوعي كل جمعة 21:00 UTC
        from datetime import time as dtime
        jq.run_daily(send_weekly_report, time=dtime(21, 0), days=(4,))
        # ملخص سيشنات اليوم بعد إغلاق NY (21:30 UTC)
        jq.run_daily(send_daily_sessions_summary, time=dtime(21, 30))

    print("✅ Bot is running! Press Ctrl+C to stop.")
    try:
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            close_loop=False,
        )
    except KeyboardInterrupt:
        print("🛑 Bot stopped.")
    except Exception as e:
        log.error(f"Bot error: {e}")
        raise

if __name__ == "__main__":
    main()
