import asyncio
import logging
import os
import re
import html
import random
import sqlite3
import time
import hmac
import hashlib
import json
import urllib.parse
from urllib.parse import parse_qsl
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto,
    WebAppInfo, MenuButtonCommands,
)
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from apscheduler.schedulers.asyncio import AsyncIOScheduler

try:
    import psycopg2
    _HAS_PG = True
except ImportError:
    psycopg2 = None
    _HAS_PG = False

# ================= НАЛАШТУВАННЯ =================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8567214922:AAFdVBlri0WnmXZYN-szTqXUFcCZh0ZJQZA")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
SUPER_ADMIN_ID = 7883597300
PROXY_URL = os.environ.get("PROXY_URL", "").strip() or None
KYIV_TZ = ZoneInfo("Europe/Kyiv")
DB_PATH = os.environ.get("DB_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "a11_bot.db")
PRE_LESSON_PING_MINUTES = 5

# PostgreSQL (Supabase) — порожньо = використовувати SQLite
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres.dlaxkntvxuhkhymrqret:58*f?G3+Urh.%N+@aws-1-eu-west-1.pooler.supabase.com:6543/postgres",
).strip()
USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith(("postgres://", "postgresql://")) and _HAS_PG)

# ---- Web App ----
WEBAPP_PORT = int(os.environ.get("WEBAPP_PORT", "8080"))
WEBAPP_PUBLIC_URL = os.environ.get("WEBAPP_PUBLIC_URL", "https://farma-six-eosin.vercel.app/")
_WEBAPP_ORIGIN_DEFAULT = WEBAPP_PUBLIC_URL.rstrip("/")
WEBAPP_CORS_ORIGINS = [
    o.strip().rstrip("/")
    for o in os.environ.get("WEBAPP_CORS_ORIGINS", _WEBAPP_ORIGIN_DEFAULT).split(",")
    if o.strip()
]
WEBAPP_ENABLED = os.environ.get("WEBAPP_ENABLED", "1") != "0"

DEFAULT_USERNAMES = [
    "astral1tee", "YEGORUK1", "Musstang_mtt", "JOJKIPOP", "Woohytr",
    "Andrey_lunin9", "Schmal5", "DiMA_20_5", "Agronomys", "GhostM003",
    "gigeroni", "monsterolo", "MIF_TOXIK", "Pavapody", "rostok86",
]

SUBJECT_LINKS = {
    "math": {"title": "Математика (А-11)", "url": "https://us04web.zoom.us/j/5018432458?pwd=kDUVQpj6AYbyC2aG5iQwLLlxbhz0LH.1&omn=74107316608", "keywords": ["математика", "матем", "матеш", "алгебра", "геометрія", "математику"]},
    "informatics": {"title": "Інформатика (А-11)", "url": "https://us05web.zoom.us/j/4878444614?pwd=NmlwSHYyNUY0K212TXE3MFVxQzJBUT09&omn=89868507574", "keywords": ["інформатика", "інформ", "інфа", "інфу"]},
    "ukrainian": {"title": "Українська мова", "url": "https://us05web.zoom.us/j/9775340879?pwd=MzBUVUw5WlBXcERCbmxFdXVhN25RUT09&omn=83217033052", "keywords": ["українська мова", "укр мова", "укрмова", "укр", "укр мову", "укр мови", "укр моава", "урк млви", "укрмлви", "укрмоава"]},
    "ukr_literature": {"title": "Українська література (А-11)", "url": "https://us05web.zoom.us/j/9775340879?pwd=MzBUVUw5WlBXcERCbmxFdXVhN25RUT09&omn=83217033052", "keywords": ["українська література", "укр літ", "укрліт", "літературу", "укр літературу"]},
    "history_ua": {"title": "Історія України (А-11)", "url": "https://us04web.zoom.us/j/2475008726?pwd=80JZEs6MYQbHO9NM5IwCfoK28VdbYJ.1&omn=76186468704", "keywords": ["історія україни", "історія укр", "іст укр", "історію україни"]},
    "world_history": {"title": "Всесвітня історія", "url": "https://us04web.zoom.us/j/2475008726?pwd=80JZEs6MYQbHO9NM5IwCfoK28VdbYJ.1&omn=76186468704", "keywords": ["всесвітня історія", "вс історія", "вс історію", "всесвітню", "всесвітня"]},
    "physics": {"title": "Фізика (А-11)", "url": "https://us04web.zoom.us/j/9389610230?pwd=zuWaea9V3Ha1uMAGWeXb6jplywcebT.1&omn=78497060565", "keywords": ["фізика", "фзика", "фіза", "фізику"]},
}
for _key, _data in SUBJECT_LINKS.items():
    _data["_patterns"] = [(kw, re.compile(r"\b" + re.escape(kw), re.IGNORECASE)) for kw in _data["keywords"]]

FARM_BANNER_URL = "https://i.postimg.cc/7LxWBwqM/Gemini-Generated-Image-buu88kbuu88kbuu8.jpg"
SHOP_BANNER_URL = "https://i.postimg.cc/CxY0gyFC/Gemini-Generated-Image-hbc4wkhbc4wkhbc4.jpg"
MARKET_BANNER_URL = "https://i.postimg.cc/wjtXgr07/Gemini-Generated-Image-v6u3g6v6u3g6v6u3.jpg"

_banner_file_id_cache: dict = {}

FOOTER_TEXT = ("\n\nℹ️ Не хочеш, щоб я тебе тегав? Напиши «Гусь мовчати» "
               "(«Гусь говорити» — повернути). Усі команди: /infoagro")
FIRST_LESSON_TEMPLATE = "{tags}\n\n🐣 Хлопці, за {mins} хвилин перша пара!\n\n📌 {title}\n🔗 {url}\n\n☕ Прокидаємось, робимо каву/чай і готуємось виходити на урок)\n\n💬 {quote}{footer}"
NEXT_LESSON_TEMPLATE = "{tags}\n\n🔥 Через {mins} хвилин наступна пара — {title}!\n🔗 {url}\n\n💬 {quote}{footer}"
NO_LINK_TEMPLATE = "{tags}\n\n🙅 Я не маю силки для пари «{subject}», яка починається за {mins} хвилин.\n\n💬 {quote}{footer}"
BREAK_TEMPLATE = "{tags}\n\n☕ {finished} закінчився. 20 хвилин перерви.\nНаступна пара о {next_time} — {next_subject}{footer}"
DAY_END_TEMPLATE = "{tags}\n\n🎉 На сьогодні пари закінчились! Гарного дня, бережіть себе.{footer}"
INFO_TEXT = (
    "📋 <b>Команди бота</b>\n\n<b>Для всіх:</b>\n"
    "• «Гусь мовчати» / «Гусь говорити»\n"
    "• «Гусь які пари сьогодні» / «...завтра»\n"
    "• «Гусь яка зараз пара» / «Гусь яка наступна пара»\n"
    "• «Гусь силку на &lt;предмет&gt;»\n"
    "• «Гусь бонус» / «Гусь баланс» / «Гусь мій тег»\n"
    "• «Гусь крутити [ставка]» / «Гусь слоти [ставка]»\n"
    "• «Гусь дуель @username [ставка]» / «Гусь цуефа @user [ставка]»\n"
    "• «Гусь топ» / «Гусь їжа»\n\n"
    "<b>🐄 ФЕРМА (напиши «Гусь ферма» в групі):</b>\n"
    "• Відкривається Web App (та сама ферма, як у веб-версії)\n"
    "• Або натисни «📋 Текстова версія» — стара текстова ферма\n\n"
    "<b>Для адміна:</b>\n"
    "• /admin / /lid2 / /settopic / /event\n"
    "• /give /take /setbal @username|ID N\n"
    "• /settag @username|ID ТЕКСТ\n"
    "• /userinfo / /logs / /balances\n"
    "• /reload — перечитати БД без перезапуску\n"
    "• /setprice КЛЮЧ ЦІНА — змінити ціну\n"
    "• /money_trace @user|ID [днів] — всі транзакції\n"
    "• /setwebapp URL — задати посилання на веб-гру\n")

LESSON_START_TIME = "09:00"
LESSON_DURATION_MINUTES = 40
BREAK_DURATION_MINUTES = 20
LESSON_SLOT_MINUTES = LESSON_DURATION_MINUTES + BREAK_DURATION_MINUTES


def compute_lesson_time(index):
    start_h, start_m = map(int, LESSON_START_TIME.split(":"))
    total = start_h * 60 + start_m + index * LESSON_SLOT_MINUTES
    return (total // 60) % 24, total % 60


LESSON_NUM_PREFIX_RE = re.compile(r"^(\d+\s*[-.)]?\s*пара\.?\s*|пара\s*\d+\.?\s*)", re.IGNORECASE)


def clean_subject_text(s):
    return LESSON_NUM_PREFIX_RE.sub("", s).strip(" .-")


def parse_schedule_text(text):
    subjects = []
    for raw_line in text.strip().splitlines():
        line = raw_line.strip().strip(",")
        if not line:
            continue
        for part in line.split(","):
            cleaned = clean_subject_text(part)
            if cleaned:
                subjects.append(cleaned)
    return subjects


def determine_target_date(subjects_count):
    now = datetime.now(KYIV_TZ)
    last_h, last_m = compute_lesson_time(subjects_count - 1)
    last_end_minutes = last_h * 60 + last_m + LESSON_DURATION_MINUTES
    if now.hour * 60 + now.minute >= last_end_minutes:
        return (now + timedelta(days=1)).date()
    return now.date()


def _parse_dt(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KYIV_TZ)
    return dt


def _fmt_duration(seconds):
    seconds = int(max(0, seconds))
    m = seconds // 60
    if m >= 60:
        return f"{m // 60} год {m % 60} хв"
    return f"{m} хв"


NAME_PATTERN = re.compile(r"^\s*(гусь|агроном)\b[,:\s]*", re.IGNORECASE)
state_data = {"starosta_username": None}
BOT_USERNAME = None
known_users: dict = {}
muted_users: dict = {}
chat_schedules: dict = {}
ai_chat_enabled: dict = {}

INITIAL_BALANCE = 100
BONUS_MIN, BONUS_MAX = 30, 80
BONUS_COOLDOWN_HOURS = 24
DEFAULT_SLOT_BET = 10
DEFAULT_DUEL_BET = 20
economy_cache: dict = {}
RPS_CHOICES = ["камінь", "ножиці", "папір", "колодязь"]
RPS_BEATS = {"колодязь": {"камінь", "ножиці", "папір"}, "камінь": {"ножиці"}, "ножиці": {"папір"}, "папір": {"камінь"}}
RPS_EMOJI = {"камінь": "🪨", "ножиці": "✂️", "папір": "📄", "колодязь": "🕳️"}

SLOT_SYMBOLS = [
    {"emoji": "🍒", "weight": 35, "quad_mult": 12, "triple_mult": 1.4, "name": "вишні"},
    {"emoji": "🍋", "weight": 30, "quad_mult": 20, "triple_mult": 1.8, "name": "лимони"},
    {"emoji": "🍊", "weight": 20, "quad_mult": 40, "triple_mult": 2.5, "name": "апельсини"},
    {"emoji": "🍇", "weight": 10, "quad_mult": 110, "triple_mult": 6, "name": "виноград"},
    {"emoji": "⭐", "weight": 4, "quad_mult": 800, "triple_mult": 18, "name": "зірки"},
    {"emoji": "💎", "weight": 1, "quad_mult": 12000, "triple_mult": 70, "name": "алмази"},
]
SLOT_WEIGHTS = [s["weight"] for s in SLOT_SYMBOLS]
SLOT_EMOJIS = [s["emoji"] for s in SLOT_SYMBOLS]
SLOT_BY_EMOJI = {s["emoji"]: s for s in SLOT_SYMBOLS}
SLOT_REELS = 4
SLOT_BONUS_CHANCE = 0.15
SLOT_BONUS_MULTIPLIERS = [{"value": 2, "weight": 55}, {"value": 3, "weight": 25}, {"value": 5, "weight": 13}, {"value": 10, "weight": 6}, {"value": 20, "weight": 1}]
SLOT_BONUS_VALUES = [m["value"] for m in SLOT_BONUS_MULTIPLIERS]
SLOT_BONUS_WEIGHTS = [m["weight"] for m in SLOT_BONUS_MULTIPLIERS]
SLOT_SPINS_LIMIT = 5
SLOT_SPINS_WINDOW_SEC = 20 * 60
slot_spin_history: dict = {}

BRAND_TAGS = {
    "kucher": {"name": "🌾 Кучеравець", "price": 3000, "tag": "Кучерявий"},
    "traktor": {"name": "🚜 Тракторний", "price": 3500, "tag": "Тракторист"},
    "agronom": {"name": "🌱 Агроном", "price": 4000, "tag": "Агроном"},
    "moloko": {"name": "🥛 Молочник", "price": 5000, "tag": "Молочник"},
    "pasechnik": {"name": "🐝 Пасічник", "price": 6000, "tag": "Пасічник"},
    "fermer": {"name": "🌾 Фермер", "price": 8000, "tag": "Фермер"},
    "baron": {"name": "👑 Барон", "price": 12000, "tag": "Барон"},
    "korol": {"name": "🎩 Король ферми", "price": 15000, "tag": "Король"},
    "magnat": {"name": "💎 Магнат", "price": 20000, "tag": "Магнат"},
    "agrarniy": {"name": "🦅 Аграрний Орел", "price": 25000, "tag": "Аграрний"},
    "millioner": {"name": "💰 Мільйонер", "price": 35000, "tag": "Мільйонер"},
    "custom": {"name": "✍️ Свій тег", "price": 100000, "tag": None},
}

FARM_BUY_PRICE = {"chicken": 100, "rooster": 300, "pig": 450, "cow": 1000, "ostrich": 7500}
FARM_SELL_PRICE = {"chicken": 60, "rooster": 180, "pig": 280, "cow": 600, "ostrich": 4000, "chick": 40}
FARM_ANIMALS_UA = {"chicken": "🐔 Курка", "rooster": "🐓 Півень", "pig": "🐷 Свиня", "cow": "🐄 Корова", "ostrich": "🦤 Страус", "chick": "🐤 Курча"}
FARM_ANIMAL_TO_COLUMN = {"chicken": "chickens", "rooster": "roosters", "pig": "pigs", "cow": "cows", "ostrich": "ostriches", "chick": "chicks"}
FARM_ANIMAL_TO_MARKET_COL = dict(FARM_ANIMAL_TO_COLUMN)
FARM_FEED_PRICE = {"grain": 15, "hay": 25, "mix": 45}
FARM_FEED_UA = {"grain": "🌾 Зерно", "hay": "🌿 Сіно", "mix": "🥣 Комбікорм"}
FARM_SEED_PRICE = 20
FARM_PRODUCT_PRICE = {"eggs": 30, "milk": 200, "meat": 150, "potato": 70, "lard": 400, "cheese": 1200, "feather": 550, "ostrich_egg": 2200}
FARM_PRODUCT_UA = {"eggs": "🥚 Яйця", "milk": "🥛 Молоко", "meat": "🥓 М'ясо", "potato": "🥔 Картопля", "lard": "🥓 Сало", "cheese": "🧀 Сир", "feather": "🪶 Пір'я", "ostrich_egg": "🥚 Страусине яйце"}
FARM_PRODUCT_TO_COLUMN = {"eggs": "eggs", "milk": "milk", "meat": "meat", "potato": "potato", "lard": "lard", "cheese": "cheese", "feather": "feathers", "ostrich_egg": "ostrich_eggs"}
FARM_CYCLE = {"chicken": 30 * 60, "pig": 90 * 60, "cow": 60 * 60, "ostrich": 4 * 3600}
FARM_POTATO_GROW_SEC = 2 * 3600
FARM_CHEESE_SEC = 3600
FARM_CHEESE_MILK_COST = 10
FARM_CHEESE_YIELD = 3
FARM_BREED_SEC = 3 * 3600
FARM_MAX_ELAPSED_HOURS = 12

FARM_LEVELS = [
    (0, 1, "🥚 Новачок"), (500, 2, "🌱 Початківець"), (1500, 3, "🚜 Фермер"),
    (4000, 4, "🌾 Агроном"), (9000, 5, "💼 Магнат"), (20000, 6, "👑 Аграрний Барон"),
]


def farm_level_from_xp(xp):
    lvl, name = 1, FARM_LEVELS[0][2]
    for need, l, n in FARM_LEVELS:
        if xp >= need:
            lvl, name = l, n
    return lvl, name


CONTRACT_TEMPLATES = [
    ("🇺🇸 Америка хоче сир для піци", "cheese", (3, 8), 1600, 12),
    ("🇪🇺 ЄС замовив яйця для фабрики", "eggs", (20, 60), 40, 8),
    ("🇨🇳 Китай скуповує сало", "lard", (5, 20), 500, 10),
    ("🇦🇪 Дубай замовив страусине пір'я", "feather", (2, 6), 700, 24),
    ("🍔 McDonald's бере картоплю", "potato", (30, 80), 90, 6),
    ("🥩 Ресторан купує м'ясо", "meat", (5, 15), 200, 8),
    ("🥛 Молочна ферма замовила молоко", "milk", (15, 40), 230, 10),
    ("🥚 Фермерський ринок — страусині яйця", "ostrich_egg", (1, 4), 2400, 20),
]

FARM_COLUMNS = [
    "chickens", "pigs", "cows", "feed", "potato_seed", "eggs", "milk", "meat", "potato",
    "planted_count", "planted_at", "last_collect",
    "roosters", "chicks", "ostriches", "grain", "hay", "mix",
    "lard", "cheese", "feathers", "ostrich_eggs", "farm_xp", "last_breed",
    "cheese_started", "cheese_batch",
]
FARM_DATETIME_COLS = {"planted_at", "last_collect", "last_breed", "cheese_started"}
farm_cache: dict = {}
pending_duels: dict = {}

WORKERS = {
    "shepherd": {"name": "🐕 Пастух",     "price": 4_000,  "rent_24h": 500,   "wage": 40,  "emoji": "🐕", "effect": "eggs_bonus",   "desc": "+25% до яєць."},
    "milkmaid": {"name": "🥛 Доярка",     "price": 6_000,  "rent_24h": 700,   "wage": 60,  "emoji": "🥛", "effect": "milk_bonus",   "desc": "+25% до молока."},
    "tractor":  {"name": "🚜 Тракторист", "price": 10_000, "rent_24h": 1_200, "wage": 100, "emoji": "🚜", "effect": "potato_bonus", "desc": "+50% до картоплі."},
    "combine":  {"name": "🌾 Комбайнер",  "price": 25_000, "rent_24h": 2_500, "wage": 200, "emoji": "🌾", "effect": "wheat_unlock",  "desc": "Потрібен для поля пшениці."},
}
WORKER_EFFECTS = {
    "eggs_bonus":   {"mult": 1.25, "target": "eggs"},
    "milk_bonus":   {"mult": 1.25, "target": "milk"},
    "potato_bonus": {"mult": 1.50, "target": "potato"},
}

STARTER_KIT = {
    "balance": 15_000, "grain": 2_000, "hay": 1_000, "mix": 500,
    "potato_seed": 300, "wheat_seed": 150,
    "chickens": 5, "roosters": 1, "pigs": 2, "cows": 1,
    "plots": 1, "silos": 1,
}
STARTER_WORKERS_HOURS = 24
STARTER_WORKERS = ["tractor", "combine"]
GAMES_TOPIC_KEY = "games_topic_id"

SHOP_STOCK = {
    "chicken": {"max": 500, "per_hour": 15}, "rooster": {"max": 150, "per_hour": 5},
    "pig": {"max": 300, "per_hour": 10}, "cow": {"max": 200, "per_hour": 6},
    "ostrich": {"max": 30, "per_hour": 1},
    "grain": {"max": 50_000, "per_hour": 2_000}, "hay": {"max": 30_000, "per_hour": 1_200},
    "mix": {"max": 15_000, "per_hour": 600}, "seed": {"max": 10_000, "per_hour": 500},
    "wheat_seed": {"max": 5_000, "per_hour": 250},
}

WHEAT_GROW_SEC       = 4 * 3600
WHEAT_YIELD_PER_PLOT = 100
WHEAT_LOCAL_PRICE    = 45
WHEAT_EU_PRICE       = 120
WHEAT_SEED_PRICE     = 30
PLOT_BASE_PRICE      = 30_000
PLOT_PRICE_GROWTH    = 1.6
EU_DAILY_LIMIT       = 2000
WHEAT_SILO_PRICE     = 25_000
WHEAT_SILO_CAPACITY  = 500
WHEAT_PLOT_CAPACITY  = 100
WHEAT_AUTO_SILO_FROM_PLOTS = True

ANIMAL_FACTS = [
    ("🐔 Курка",  "30 хв", "1 🌾 зерно",            "🥚 1 яйце"),
    ("🐓 Півень", "—",     "1 🌾 зерно",            "🐤 +1 курча / 3 год"),
    ("🐷 Свиня",  "90 хв", "3 🌿 сіно",             "🥓 1 м'ясо + 1 сало"),
    ("🐄 Корова", "60 хв", "3 🌿 сіно",             "🥛 1 молоко"),
    ("🦤 Страус", "4 год", "2 🥣 комбікорм",        "🪶 1 пір'я + 🥚 1 яйце"),
    ("🌾 Поле",   "4 год", "1 🥔 насіння пшениці",  "🌾 100 тонн пшениці"),
]

BUSINESSES = {
    "kiosk":       {"name": "🏪 Кіоск",       "price": 30_000,       "hourly": 80,        "emoji": "🏪", "desc": "Насіння, вода."},
    "cafe":        {"name": "☕ Кафе",         "price": 200_000,      "hourly": 500,       "emoji": "☕", "desc": "Кава для студентів."},
    "shop":        {"name": "🏬 Магазин",     "price": 1_200_000,    "hourly": 2_800,     "emoji": "🏬", "desc": "Продукти села."},
    "restaurant":  {"name": "🍽️ Ресторан",    "price": 7_000_000,    "hourly": 15_000,    "emoji": "🍽️", "desc": "Елітне місце."},
    "factory":     {"name": "🏭 Завод",       "price": 40_000_000,   "hourly": 80_000,    "emoji": "🏭", "desc": "Промисловість."},
    "corporation": {"name": "🏢 Корпорація",  "price": 250_000_000,  "hourly": 450_000,   "emoji": "🏢", "desc": "Транснаціональна."},
    "monopoly":    {"name": "💼 Монополія",   "price": 1_500_000_000,"hourly": 2_400_000, "emoji": "💼", "desc": "Ти контролюєш все."},
}

PRESTIGE_LEVELS = [
    {"lvl": 1, "price": 500_000, "bonus_pct": 5, "name": "🥉 Новачок"},
    {"lvl": 2, "price": 2_500_000, "bonus_pct": 10, "name": "🥈 Бізнесмен"},
    {"lvl": 3, "price": 10_000_000, "bonus_pct": 20, "name": "🥇 Магнат"},
    {"lvl": 4, "price": 50_000_000, "bonus_pct": 35, "name": "💎 Олігарх"},
    {"lvl": 5, "price": 200_000_000, "bonus_pct": 50, "name": "👑 Монарх"},
    {"lvl": 6, "price": 1_000_000_000, "bonus_pct": 75, "name": "🌌 Легенда"},
    {"lvl": 7, "price": 5_000_000_000, "bonus_pct": 100, "name": "⭐ Безсмертний"},
]

BANK_RATE_PER_HOUR = 0.01
BANK_MAX_HOURS = 24
BANK_MIN_DEPOSIT = 10_000
JACKPOT_TICKET_PRICE = 25_000

SELLABLE_ITEMS = {
    "potato": ("🥔 Картопля", "potato"), "eggs": ("🥚 Яйця", "eggs"),
    "milk": ("🥛 Молоко", "milk"), "meat": ("🥓 М'ясо", "meat"),
    "lard": ("🥓 Сало", "lard"), "cheese": ("🧀 Сир", "cheese"),
    "feather": ("🪶 Пір'я", "feathers"), "ostrich_egg": ("🥚 Страусине яйце", "ostrich_eggs"),
    "wheat": ("🌾 Пшениця", "__wheat__"),
    "grain": ("🌾 Зерно", "grain"), "hay": ("🌿 Сіно", "hay"), "mix": ("🥣 Комбікорм", "mix"),
    "chicken": ("🐔 Курка", "chickens"), "rooster": ("🐓 Півень", "roosters"),
    "pig": ("🐷 Свиня", "pigs"), "cow": ("🐄 Корова", "cows"),
    "ostrich": ("🦤 Страус", "ostriches"), "chick": ("🐤 Курча", "chicks"),
}


# ================= SQLite → PostgreSQL адаптер =================
def _translate_sql(sql: str) -> str:
    s = sql.strip()
    if not s:
        return s
    upper = s.upper()
    if upper.startswith("PRAGMA"):
        return "SELECT 1 WHERE FALSE"
    if "AUTOINCREMENT" in upper:
        s = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", "SERIAL PRIMARY KEY", s, flags=re.IGNORECASE)
    if re.match(r"^INSERT\s+OR\s+IGNORE\s+INTO", upper):
        s = re.sub(r"^INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", s, flags=re.IGNORECASE)
        if "ON CONFLICT" not in s.upper():
            s = s.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    if re.match(r"^INSERT\s+OR\s+REPLACE\s+INTO", upper):
        m = re.match(r"^INSERT\s+OR\s+REPLACE\s+INTO\s+(\w+)\s*\(([^)]+)\)", s, flags=re.IGNORECASE)
        if m:
            table = m.group(1).lower()
            cols = [c.strip() for c in m.group(2).split(",")]
            if table == "workers":
                conflict, exclude = "(chat_id, user_id, worker_key)", ("chat_id", "user_id", "worker_key")
            else:
                conflict, exclude = "(chat_id, user_id)", ("chat_id", "user_id")
            update_cols = [c for c in cols if c not in exclude]
            set_clause = ", ".join(f"{c}=EXCLUDED.{c}" for c in update_cols) or "chat_id=EXCLUDED.chat_id"
            s = re.sub(r"^INSERT\s+OR\s+REPLACE\s+INTO", "INSERT INTO", s, flags=re.IGNORECASE)
            s = s.rstrip().rstrip(";") + f" ON CONFLICT {conflict} DO UPDATE SET {set_clause}"
    s = re.sub(r"\bMAX\s*\(\s*0\s*,", "GREATEST(0,", s)
    s = re.sub(r"\bMAX\s*\(\s*50\s*,", "GREATEST(50,", s)
    s = s.replace("?", "%s")
    return s


class _PgCursorWrapper:
    def __init__(self, parent):
        self._parent = parent
        self._cur = parent._conn.cursor()
        self.lastrowid = None

    def execute(self, sql, params=None):
        translated = _translate_sql(sql)
        has_returning = "RETURNING" in translated.upper() and translated.strip().upper().startswith("INSERT")
        try:
            self._cur.execute(translated, params) if params is not None else self._cur.execute(translated)
        except Exception:
            try:
                self._parent._conn.rollback()
            except Exception:
                pass
            raise
        if has_returning:
            try:
                row = self._cur.fetchone()
                self.lastrowid = row[0] if row else None
            except Exception:
                pass
        return self

    def executemany(self, sql, seq):
        translated = _translate_sql(sql)
        try:
            self._cur.executemany(translated, seq)
        except Exception:
            try:
                self._parent._conn.rollback()
            except Exception:
                pass
            raise
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass

    @property
    def rowcount(self):
        return self._cur.rowcount

    def __iter__(self):
        return iter(self._cur)


class PgConnection:
    def __init__(self, dsn: str):
        # Supabase pooler може містити спецсимволи в паролі — розбираємо через urllib
        parsed = urllib.parse.urlparse(dsn)
        if parsed.hostname:
            self._conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                user=urllib.parse.unquote(parsed.username or ""),
                password=urllib.parse.unquote(parsed.password or ""),
                dbname=(parsed.path or "/postgres").lstrip("/") or "postgres",
                sslmode="require",
                connect_timeout=20,
            )
        else:
            self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = False

    def execute(self, sql, params=None):
        return _PgCursorWrapper(self).execute(sql, params)

    def executemany(self, sql, seq):
        return _PgCursorWrapper(self).executemany(sql, seq)

    def cursor(self):
        return _PgCursorWrapper(self)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


def _get_table_columns(conn, table_name):
    cur = conn.cursor()
    if USE_POSTGRES:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table_name,))
    else:
        cur.execute(f"PRAGMA table_info({table_name})")
    rows = cur.fetchall()
    cur.close()
    if USE_POSTGRES:
        return {r[0] for r in rows}
    return {r[1] for r in rows}


# ================= БАЗА ДАНИХ =================
def db_connect():
    if USE_POSTGRES:
        return PgConnection(DATABASE_URL)
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS subject_links (key TEXT PRIMARY KEY, title TEXT, url TEXT, keyword TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS muted_users (chat_id BIGINT, user_id BIGINT, PRIMARY KEY (chat_id, user_id))")
    cur.execute("CREATE TABLE IF NOT EXISTS schedule (chat_id BIGINT, target_date TEXT, idx INTEGER, subject TEXT, PRIMARY KEY (chat_id, idx))")
    cur.execute("CREATE TABLE IF NOT EXISTS ai_chat_settings (chat_id BIGINT PRIMARY KEY, enabled INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS economy (chat_id BIGINT, user_id BIGINT, balance BIGINT DEFAULT 0, last_bonus TEXT, active_title TEXT, PRIMARY KEY (chat_id, user_id))")
    cur.execute("CREATE TABLE IF NOT EXISTS user_titles (chat_id BIGINT, user_id BIGINT, title TEXT, PRIMARY KEY (chat_id, user_id, title))")
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        chat_id BIGINT, user_id BIGINT, name TEXT, username TEXT,
        balance BIGINT DEFAULT 0, tag TEXT,
        PRIMARY KEY (chat_id, user_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS farm (
        chat_id BIGINT, user_id BIGINT,
        chickens INTEGER DEFAULT 0, pigs INTEGER DEFAULT 0, cows INTEGER DEFAULT 0,
        feed INTEGER DEFAULT 0, potato_seed INTEGER DEFAULT 0,
        eggs INTEGER DEFAULT 0, milk INTEGER DEFAULT 0, meat INTEGER DEFAULT 0, potato INTEGER DEFAULT 0,
        planted_count INTEGER DEFAULT 0, planted_at TEXT, last_collect TEXT,
        PRIMARY KEY (chat_id, user_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS contracts (
        contract_id SERIAL PRIMARY KEY,
        chat_id BIGINT, user_id BIGINT, product TEXT, need INTEGER, reward BIGINT,
        deadline TEXT, text TEXT, active INTEGER DEFAULT 1)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS user_tags (
        chat_id BIGINT, user_id BIGINT, tag_key TEXT, tag_text TEXT,
        PRIMARY KEY (chat_id, user_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS logs (
        id SERIAL PRIMARY KEY, ts TEXT NOT NULL, chat_id BIGINT, user_id BIGINT,
        event TEXT NOT NULL, amount BIGINT DEFAULT 0, balance_after BIGINT,
        balance_before BIGINT, status TEXT DEFAULT 'ok', details TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS businesses (
        chat_id BIGINT, user_id BIGINT, biz_key TEXT, qty INTEGER DEFAULT 0, last_collect TEXT,
        PRIMARY KEY (chat_id, user_id, biz_key))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS prestige (
        chat_id BIGINT, user_id BIGINT, level INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS bank (
        chat_id BIGINT, user_id BIGINT, deposit BIGINT DEFAULT 0, deposited_at TEXT,
        PRIMARY KEY (chat_id, user_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS jackpot (
        chat_id BIGINT PRIMARY KEY, pot BIGINT DEFAULT 0, last_draw TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS jackpot_tickets (
        chat_id BIGINT, user_id BIGINT, tickets INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS shop_stock (
        chat_id BIGINT, item_key TEXT, stock REAL, last_refill TEXT,
        PRIMARY KEY (chat_id, item_key))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS workers (
        chat_id BIGINT, user_id BIGINT, worker_key TEXT, hired_at TEXT,
        PRIMARY KEY (chat_id, user_id, worker_key))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS wheat_fields (
        chat_id BIGINT, user_id BIGINT, plots INTEGER DEFAULT 0,
        wheat INTEGER DEFAULT 0, wheat_seed INTEGER DEFAULT 0,
        planted_count INTEGER DEFAULT 0, planted_at TEXT,
        eu_sold_today INTEGER DEFAULT 0, eu_reset_date TEXT,
        silos INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS marketplace (
        listing_id SERIAL PRIMARY KEY,
        chat_id BIGINT, seller_id BIGINT, item_key TEXT,
        qty INTEGER, price BIGINT, created_at TEXT, active INTEGER DEFAULT 1)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS pending_trades (
        trade_id TEXT PRIMARY KEY, chat_id BIGINT, seller_id BIGINT, buyer_id BIGINT,
        item_key TEXT, qty INTEGER, price BIGINT, created_at TEXT, active INTEGER DEFAULT 1)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS user_starter (
        chat_id BIGINT, user_id BIGINT, claimed_at TEXT,
        PRIMARY KEY (chat_id, user_id))""")
    conn.commit()
    conn.close()


def migrate_farm_v2():
    conn = db_connect()
    cur = conn.cursor()
    existing = _get_table_columns(conn, "farm")
    migrations = {
        "roosters": "INTEGER DEFAULT 0", "chicks": "INTEGER DEFAULT 0", "ostriches": "INTEGER DEFAULT 0",
        "grain": "INTEGER DEFAULT 0", "hay": "INTEGER DEFAULT 0", "mix": "INTEGER DEFAULT 0",
        "lard": "INTEGER DEFAULT 0", "cheese": "INTEGER DEFAULT 0", "feathers": "INTEGER DEFAULT 0",
        "ostrich_eggs": "INTEGER DEFAULT 0", "farm_xp": "INTEGER DEFAULT 0", "last_breed": "TEXT",
        "cheese_started": "TEXT", "cheese_batch": "INTEGER DEFAULT 0",
    }
    for col, typ in migrations.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE farm ADD COLUMN {col} {typ}")
    conn.commit()
    conn.close()


def migrate_users_v3():
    conn = db_connect()
    cur = conn.cursor()
    existing = _get_table_columns(conn, "users")
    if "balance" not in existing:
        cur.execute("ALTER TABLE users ADD COLUMN balance BIGINT DEFAULT 0")
    if "tag" not in existing:
        cur.execute("ALTER TABLE users ADD COLUMN tag TEXT")
    conn.commit()
    try:
        cur.execute("UPDATE users SET balance = COALESCE((SELECT balance FROM economy WHERE economy.chat_id=users.chat_id AND economy.user_id=users.user_id), 0)")
        cur.execute("UPDATE users SET tag = (SELECT tag_text FROM user_tags WHERE user_tags.chat_id=users.chat_id AND user_tags.user_id=users.user_id)")
        conn.commit()
    except Exception as e:
        logging.error(f"[DB] sync users: {e}")
    conn.close()


def migrate_workers_expiry():
    conn = db_connect()
    cur = conn.cursor()
    existing = _get_table_columns(conn, "workers")
    if "expires_at" not in existing:
        cur.execute("ALTER TABLE workers ADD COLUMN expires_at TEXT")
        conn.commit()
    conn.close()


def migrate_wheat_silos():
    conn = db_connect()
    cur = conn.cursor()
    existing = _get_table_columns(conn, "wheat_fields")
    if "silos" not in existing:
        cur.execute("ALTER TABLE wheat_fields ADD COLUMN silos INTEGER DEFAULT 0")
        conn.commit()
        logging.info("[DB] wheat_fields.silos додано")
    conn.close()


def migrate_logs_v2():
    conn = db_connect()
    cur = conn.cursor()
    existing = _get_table_columns(conn, "logs")
    if "balance_before" not in existing:
        cur.execute("ALTER TABLE logs ADD COLUMN balance_before BIGINT")
    if "status" not in existing:
        cur.execute("ALTER TABLE logs ADD COLUMN status TEXT DEFAULT 'ok'")
    conn.commit()
    conn.close()


def _sync_user_mirror(chat_id, user_id):
    conn = db_connect()
    try:
        conn.execute("""UPDATE users SET
            balance = COALESCE((SELECT balance FROM economy WHERE economy.chat_id=? AND economy.user_id=?), 0),
            tag = (SELECT tag_text FROM user_tags WHERE user_tags.chat_id=? AND user_tags.user_id=?)
            WHERE chat_id=? AND user_id=?""", (chat_id, user_id, chat_id, user_id, chat_id, user_id))
        conn.commit()
    except Exception as e:
        logging.error(f"[SYNC] {e}")
    finally:
        conn.close()


def db_save_setting(key, value):
    conn = db_connect()
    try:
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        conn.commit()
    finally:
        conn.close()


def db_get_setting(key):
    conn = db_connect()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def db_log(chat_id, user_id, event, amount=0, balance_after=None, details="", balance_before=None, status="ok"):
    conn = db_connect()
    try:
        conn.execute(
            "INSERT INTO logs (ts, chat_id, user_id, event, amount, balance_after, balance_before, status, details) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now(KYIV_TZ).isoformat(), chat_id, user_id, event, amount,
             balance_after, balance_before, status, details))
        conn.commit()
    except Exception as e:
        logging.error(f"[LOG] {e}")
    finally:
        conn.close()


def db_get_logs(chat_id, limit=50):
    conn = db_connect()
    try:
        rows = conn.execute(
            "SELECT ts, user_id, event, amount, balance_after, details FROM logs "
            "WHERE chat_id=? ORDER BY id DESC LIMIT ?", (chat_id, limit)).fetchall()
    finally:
        conn.close()
    return rows


def db_get_user_transactions(chat_id, user_id, days=1, limit=100):
    cutoff = (datetime.now(KYIV_TZ) - timedelta(days=days)).isoformat()
    conn = db_connect()
    try:
        rows = conn.execute(
            "SELECT ts, event, amount, balance_before, balance_after, details, status "
            "FROM logs WHERE chat_id=? AND user_id=? AND ts > ? ORDER BY id DESC LIMIT ?",
            (chat_id, user_id, cutoff, limit)).fetchall()
    finally:
        conn.close()
    return rows


def db_get_all_balances(chat_id):
    conn = db_connect()
    try:
        rows = conn.execute("SELECT user_id, balance FROM economy WHERE chat_id=? ORDER BY balance DESC", (chat_id,)).fetchall()
    finally:
        conn.close()
    return rows


def db_save_starosta(username):
    db_save_setting("starosta_username", username)


def db_load_starosta():
    return db_get_setting("starosta_username")


def db_save_subject_link(key, title, url, keyword):
    conn = db_connect()
    try:
        conn.execute("INSERT INTO subject_links (key, title, url, keyword) VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET title=excluded.title, url=excluded.url, keyword=excluded.keyword", (key, title, url, keyword))
        conn.commit()
    finally:
        conn.close()


def db_load_subject_links():
    conn = db_connect()
    try:
        rows = conn.execute("SELECT key, title, url, keyword FROM subject_links").fetchall()
    finally:
        conn.close()
    return rows


def db_set_muted(chat_id, user_id, muted):
    conn = db_connect()
    try:
        if muted:
            conn.execute("INSERT OR IGNORE INTO muted_users (chat_id, user_id) VALUES (?, ?)", (chat_id, user_id))
        else:
            conn.execute("DELETE FROM muted_users WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        conn.commit()
    finally:
        conn.close()


def db_load_muted():
    conn = db_connect()
    try:
        rows = conn.execute("SELECT chat_id, user_id FROM muted_users").fetchall()
    finally:
        conn.close()
    return rows


def db_save_schedule(chat_id, target_date, subjects):
    conn = db_connect()
    try:
        conn.execute("DELETE FROM schedule WHERE chat_id=?", (chat_id,))
        conn.executemany("INSERT INTO schedule (chat_id, target_date, idx, subject) VALUES (?, ?, ?, ?)",
                         [(chat_id, target_date.isoformat(), i, s) for i, s in enumerate(subjects)])
        conn.commit()
    finally:
        conn.close()


def db_load_schedules():
    conn = db_connect()
    try:
        rows = conn.execute("SELECT chat_id, target_date, idx, subject FROM schedule ORDER BY chat_id, idx").fetchall()
    finally:
        conn.close()
    result = {}
    for chat_id, target_date_str, idx, subject in rows:
        entry = result.setdefault(chat_id, {"date": date.fromisoformat(target_date_str), "subjects": []})
        entry["subjects"].append(subject)
    return result


def db_set_ai_chat(chat_id, enabled):
    conn = db_connect()
    try:
        conn.execute("INSERT INTO ai_chat_settings (chat_id, enabled) VALUES (?, ?) ON CONFLICT(chat_id) DO UPDATE SET enabled=excluded.enabled", (chat_id, 1 if enabled else 0))
        conn.commit()
    finally:
        conn.close()


def db_load_ai_chat():
    conn = db_connect()
    try:
        rows = conn.execute("SELECT chat_id, enabled FROM ai_chat_settings").fetchall()
    finally:
        conn.close()
    return rows


def db_upsert_economy(chat_id, user_id, balance, last_bonus, active_title):
    conn = db_connect()
    try:
        conn.execute("INSERT INTO economy (chat_id, user_id, balance, last_bonus, active_title) VALUES (?, ?, ?, ?, ?) ON CONFLICT(chat_id, user_id) DO UPDATE SET balance=excluded.balance, last_bonus=excluded.last_bonus, active_title=excluded.active_title",
                     (chat_id, user_id, balance, last_bonus, active_title))
        conn.commit()
    finally:
        conn.close()


def db_load_economy():
    conn = db_connect()
    try:
        rows = conn.execute("SELECT chat_id, user_id, balance, last_bonus, active_title FROM economy").fetchall()
    finally:
        conn.close()
    return rows


def db_set_balance(chat_id, user_id, new_balance):
    conn = db_connect()
    try:
        conn.execute("INSERT INTO economy (chat_id, user_id, balance, last_bonus, active_title) VALUES (?, ?, ?, NULL, NULL) ON CONFLICT(chat_id, user_id) DO UPDATE SET balance=excluded.balance", (chat_id, user_id, new_balance))
        conn.commit()
    finally:
        conn.close()
    economy_cache.pop((chat_id, user_id), None)
    _sync_user_mirror(chat_id, user_id)
    return new_balance


def db_add_balance(chat_id, user_id, delta):
    conn = db_connect()
    try:
        conn.execute("INSERT OR IGNORE INTO economy (chat_id, user_id, balance, last_bonus, active_title) VALUES (?, ?, ?, NULL, NULL)", (chat_id, user_id, INITIAL_BALANCE))
        conn.execute("UPDATE economy SET balance = balance + ? WHERE chat_id=? AND user_id=?", (delta, chat_id, user_id))
        conn.commit()
        row = conn.execute("SELECT balance FROM economy WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
    finally:
        conn.close()
    economy_cache.pop((chat_id, user_id), None)
    _sync_user_mirror(chat_id, user_id)
    return row[0] if row else 0


def db_ensure_user_rows(chat_id, user_id):
    conn = db_connect()
    try:
        conn.execute("INSERT OR IGNORE INTO economy (chat_id, user_id, balance, last_bonus, active_title) VALUES (?, ?, ?, NULL, NULL)", (chat_id, user_id, INITIAL_BALANCE))
        conn.execute("INSERT OR IGNORE INTO farm (chat_id, user_id) VALUES (?, ?)", (chat_id, user_id))
        conn.execute("INSERT OR IGNORE INTO wheat_fields (chat_id, user_id) VALUES (?, ?)", (chat_id, user_id))
        conn.commit()
    finally:
        conn.close()


def db_save_user_tag(chat_id, user_id, tag_key, tag_text):
    conn = db_connect()
    try:
        conn.execute("INSERT INTO user_tags (chat_id, user_id, tag_key, tag_text) VALUES (?, ?, ?, ?) ON CONFLICT(chat_id, user_id) DO UPDATE SET tag_key=excluded.tag_key, tag_text=excluded.tag_text",
                     (chat_id, user_id, tag_key, tag_text))
        conn.commit()
    finally:
        conn.close()
    _sync_user_mirror(chat_id, user_id)


def db_get_user_tag(chat_id, user_id):
    conn = db_connect()
    try:
        row = conn.execute("SELECT tag_key, tag_text FROM user_tags WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
    finally:
        conn.close()
    return row


def db_upsert_user_unique(chat_id, user_id, name, username):
    conn = db_connect()
    try:
        if username:
            conn.execute("UPDATE users SET username=NULL WHERE chat_id=? AND username=? AND user_id!=?", (chat_id, username, user_id))
        conn.execute("""INSERT INTO users (chat_id, user_id, name, username, balance, tag)
                        VALUES (?, ?, ?, ?, 0, NULL)
                        ON CONFLICT(chat_id, user_id) DO UPDATE SET name=excluded.name, username=excluded.username""",
                     (chat_id, user_id, name, username))
        conn.commit()
    finally:
        conn.close()


def db_load_users():
    conn = db_connect()
    try:
        rows = conn.execute("SELECT chat_id, user_id, name, username, balance, tag FROM users").fetchall()
    finally:
        conn.close()
    return rows


def db_get_user_info(chat_id, user_id):
    conn = db_connect()
    try:
        u = conn.execute("SELECT name, username, balance, tag FROM users WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
        e = conn.execute("SELECT balance, last_bonus, active_title FROM economy WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
    finally:
        conn.close()
    return {
        "name": u[0] if u else None, "username": u[1] if u else None,
        "balance_users": u[2] if u else 0, "tag": u[3] if u else None,
        "balance_econ": e[0] if e else 0, "last_bonus": e[1] if e else None,
        "active_title": e[2] if e else None,
    }


# ================= ФЕРМА =================
def get_farm(chat_id, user_id):
    conn = db_connect()
    try:
        cols = ", ".join(FARM_COLUMNS)
        row = conn.execute(f"SELECT {cols} FROM farm WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
        if row is None:
            conn.execute("INSERT OR IGNORE INTO farm (chat_id, user_id) VALUES (?, ?)", (chat_id, user_id))
            conn.commit()
            row = tuple(0 if c not in FARM_DATETIME_COLS else None for c in FARM_COLUMNS)
    finally:
        conn.close()
    f = {}
    for i, col in enumerate(FARM_COLUMNS):
        val = row[i]
        f[col] = val if col in FARM_DATETIME_COLS else (int(val) if val is not None else 0)
    farm_cache[(chat_id, user_id)] = f
    return f


def save_farm(chat_id, user_id):
    f = farm_cache.get((chat_id, user_id))
    if f is None:
        return
    conn = db_connect()
    try:
        cols = ", ".join(FARM_COLUMNS)
        placeholders = ", ".join("?" * len(FARM_COLUMNS))
        updates = ", ".join(f"{c}=excluded.{c}" for c in FARM_COLUMNS)
        vals = [f.get(c) for c in FARM_COLUMNS]
        conn.execute(f"INSERT INTO farm (chat_id, user_id, {cols}) VALUES (?, ?, {placeholders}) ON CONFLICT(chat_id, user_id) DO UPDATE SET {updates}",
                     (chat_id, user_id, *vals))
        conn.commit()
    finally:
        conn.close()


def db_load_farm():
    conn = db_connect()
    try:
        cols = ", ".join(FARM_COLUMNS)
        rows = conn.execute(f"SELECT chat_id, user_id, {cols} FROM farm").fetchall()
    finally:
        conn.close()
    return rows


def farm_add_xp(chat_id, user_id, amount):
    if (chat_id, user_id) not in farm_cache:
        get_farm(chat_id, user_id)
    f = farm_cache[(chat_id, user_id)]
    f["farm_xp"] = f.get("farm_xp", 0) + amount
    save_farm(chat_id, user_id)


def get_economy(chat_id, user_id):
    conn = db_connect()
    try:
        row = conn.execute("SELECT balance, last_bonus, active_title FROM economy WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
        if row is None:
            conn.execute("INSERT OR IGNORE INTO economy (chat_id, user_id, balance, last_bonus, active_title) VALUES (?, ?, ?, NULL, NULL)", (chat_id, user_id, INITIAL_BALANCE))
            conn.commit()
            row = (INITIAL_BALANCE, None, None)
    finally:
        conn.close()
    econ = {"balance": row[0], "last_bonus": row[1], "active_title": row[2]}
    economy_cache[(chat_id, user_id)] = econ
    return econ


def save_economy(chat_id, user_id):
    econ = economy_cache.get((chat_id, user_id))
    if econ is None:
        return
    db_upsert_economy(chat_id, user_id, econ["balance"], econ["last_bonus"], econ["active_title"])
    _sync_user_mirror(chat_id, user_id)


# ================= СКЛАД МАГАЗИНУ =================
_stock_cache: dict = {}


def get_stock(chat_id, item_key):
    cfg = SHOP_STOCK.get(item_key)
    if not cfg:
        return 999_999
    key = (chat_id, item_key)
    now = datetime.now(KYIV_TZ)
    if key in _stock_cache:
        d = _stock_cache[key]
    else:
        conn = db_connect()
        try:
            row = conn.execute("SELECT stock, last_refill FROM shop_stock WHERE chat_id=? AND item_key=?", (chat_id, item_key)).fetchone()
        finally:
            conn.close()
        if row:
            d = {"stock": float(row[0]), "last_refill": row[1]}
        else:
            d = {"stock": float(cfg["max"]), "last_refill": now.isoformat()}
    last = _parse_dt(d["last_refill"]) or now
    hours = (now - last).total_seconds() / 3600.0
    if hours > 0:
        d["stock"] = min(cfg["max"], d["stock"] + cfg["per_hour"] * hours)
        d["last_refill"] = now.isoformat()
    _stock_cache[key] = d
    return d["stock"]


def consume_stock(chat_id, item_key, amount):
    cfg = SHOP_STOCK.get(item_key)
    if not cfg:
        return True
    get_stock(chat_id, item_key)
    key = (chat_id, item_key)
    d = _stock_cache.get(key)
    if not d or d["stock"] < amount:
        return False
    d["stock"] -= amount
    save_stock(chat_id, item_key)
    return True


def save_stock(chat_id, item_key):
    key = (chat_id, item_key)
    d = _stock_cache.get(key)
    if not d:
        return
    conn = db_connect()
    try:
        conn.execute("""INSERT INTO shop_stock (chat_id, item_key, stock, last_refill)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(chat_id, item_key) DO UPDATE SET
                        stock=excluded.stock, last_refill=excluded.last_refill""",
                     (chat_id, item_key, d["stock"], d["last_refill"]))
        conn.commit()
    finally:
        conn.close()


# ================= РОБІТНИКИ =================
def get_workers(chat_id, user_id):
    conn = db_connect()
    try:
        now_iso = datetime.now(KYIV_TZ).isoformat()
        rows = conn.execute("""SELECT worker_key FROM workers
                               WHERE chat_id=? AND user_id=?
                               AND (expires_at IS NULL OR expires_at > ?)""",
                           (chat_id, user_id, now_iso)).fetchall()
    finally:
        conn.close()
    return set(r[0] for r in rows)


def hire_worker(chat_id, user_id, worker_key, hours=None):
    ws = get_workers(chat_id, user_id)
    if worker_key in ws:
        return False, "Вже найнятий."
    expires = None
    if hours:
        expires = (datetime.now(KYIV_TZ) + timedelta(hours=hours)).isoformat()
    conn = db_connect()
    try:
        conn.execute("""INSERT OR REPLACE INTO workers
                       (chat_id, user_id, worker_key, hired_at, expires_at)
                       VALUES (?, ?, ?, ?, ?)""",
                     (chat_id, user_id, worker_key, datetime.now(KYIV_TZ).isoformat(), expires))
        conn.commit()
    finally:
        conn.close()
    return True, "OK"


def get_total_wage_per_hour(chat_id, user_id):
    ws = get_workers(chat_id, user_id)
    return sum(WORKERS[w]["wage"] for w in ws if w in WORKERS)


def get_worker_mult(chat_id, user_id, target):
    ws = get_workers(chat_id, user_id)
    mult = 1.0
    for w in ws:
        eff = WORKERS.get(w, {}).get("effect")
        if eff and eff in WORKER_EFFECTS:
            if WORKER_EFFECTS[eff]["target"] == target:
                mult *= WORKER_EFFECTS[eff]["mult"]
    return mult


# ================= СТАРТОВИЙ НАБІР =================
def has_claimed_starter(chat_id, user_id):
    conn = db_connect()
    try:
        row = conn.execute("SELECT claimed_at FROM user_starter WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
    finally:
        conn.close()
    return row is not None


def claim_starter_kit(chat_id, user_id):
    if has_claimed_starter(chat_id, user_id):
        return False
    db_ensure_user_rows(chat_id, user_id)
    before = get_economy(chat_id, user_id)["balance"]
    db_add_balance(chat_id, user_id, STARTER_KIT["balance"])
    after = get_economy(chat_id, user_id)["balance"]
    farm = get_farm(chat_id, user_id)
    farm["grain"] += STARTER_KIT["grain"]
    farm["hay"] += STARTER_KIT["hay"]
    farm["mix"] += STARTER_KIT["mix"]
    farm["potato_seed"] += STARTER_KIT["potato_seed"]
    farm["chickens"] += STARTER_KIT["chickens"]
    farm["roosters"] += STARTER_KIT["roosters"]
    farm["pigs"] += STARTER_KIT["pigs"]
    farm["cows"] += STARTER_KIT["cows"]
    save_farm(chat_id, user_id)
    wd = get_wheat(chat_id, user_id)
    wd["plots"] += STARTER_KIT["plots"]
    wd["wheat_seed"] += STARTER_KIT["wheat_seed"]
    wd["silos"] = wd.get("silos", 0) + STARTER_KIT.get("silos", 0)
    save_wheat(chat_id, user_id)
    for wkey in STARTER_WORKERS:
        hire_worker(chat_id, user_id, wkey, hours=STARTER_WORKERS_HOURS)
    conn = db_connect()
    try:
        conn.execute("INSERT OR REPLACE INTO user_starter (chat_id, user_id, claimed_at) VALUES (?, ?, ?)",
                     (chat_id, user_id, datetime.now(KYIV_TZ).isoformat()))
        conn.commit()
    finally:
        conn.close()
    db_log(chat_id, user_id, "starter_kit", STARTER_KIT["balance"], after,
           "Стартовий набір", balance_before=before)
    return True


def render_starter_kit_text():
    return (
        "🎉 <b>СТАРТОВИЙ НАБІР ФЕРМЕРА</b>\n\n"
        f"💰 <b>{STARTER_KIT['balance']:,}</b> 🪙 на баланс\n\n"
        "🌾 <b>Ресурси:</b>\n"
        f"   🌾 {STARTER_KIT['grain']:,} зерна · 🌿 {STARTER_KIT['hay']:,} сіна\n"
        f"   🥣 {STARTER_KIT['mix']:,} комбікорму\n"
        f"   🥔 {STARTER_KIT['potato_seed']:,} насіння · 🌾 {STARTER_KIT['wheat_seed']:,} пшениці\n\n"
        "🐾 <b>Тварини:</b>\n"
        f"   🐔 +{STARTER_KIT['chickens']} курей · 🐓 +{STARTER_KIT['roosters']} півень\n"
        f"   🐷 +{STARTER_KIT['pigs']} свині · 🐄 +{STARTER_KIT['cows']} корова\n\n"
        "🌾 <b>Поле:</b>\n"
        f"   🏞️ +{STARTER_KIT['plots']} ділянка (+{STARTER_KIT['plots']*WHEAT_PLOT_CAPACITY} т)\n"
        f"   🏭 +{STARTER_KIT.get('silos', 1)} силос (+{STARTER_KIT.get('silos', 1)*WHEAT_SILO_CAPACITY} т)\n\n"
        "👷 <b>Робітники на 24 год:</b> 🚜 Тракторист · 🌾 Комбайнер\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📚 <b>ЯК ПОЧАТИ:</b>\n"
        "1️⃣ <code>Гусь ферма</code>\n"
        "2️⃣ 🌱 Посадити картоплю\n"
        "3️⃣ 🌾 Поле пшениці → 🌱 Посадити все\n"
        "4️⃣ Зачекай → 🧺 Зібрати все\n"
        "5️⃣ Продай урожай\n"
        "6️⃣ <code>Гусь продати 5 пшеницю 100</code> — для гравців\n"
        "7️⃣ Купуй 🏢 бізнеси — пасивний дохід\n"
        "8️⃣ Качай 💎 престиж\n\n"
        "🎯 <b>Ціль:</b> 💼 Монополія та ⭐ Безсмертний престиж!\n\n"
        "⚠️ <b>Це одноразово.</b>"
    )


# ================= ПОЛЕ ПШЕНИЦІ =================
_wheat_cache: dict = {}


def get_wheat(chat_id, user_id):
    key = (chat_id, user_id)
    if key in _wheat_cache:
        return _wheat_cache[key]
    conn = db_connect()
    try:
        row = conn.execute("""SELECT plots, wheat, wheat_seed, planted_count, planted_at,
                              eu_sold_today, eu_reset_date, silos
                              FROM wheat_fields WHERE chat_id=? AND user_id=?""",
                           (chat_id, user_id)).fetchone()
        if not row:
            conn.execute("INSERT OR IGNORE INTO wheat_fields (chat_id, user_id) VALUES (?, ?)", (chat_id, user_id))
            conn.commit()
            row = (0, 0, 0, 0, None, 0, None, 0)
    finally:
        conn.close()
    d = {"plots": row[0], "wheat": row[1], "wheat_seed": row[2], "planted_count": row[3],
         "planted_at": row[4], "eu_sold_today": row[5], "eu_reset_date": row[6],
         "silos": row[7] if len(row) > 7 else 0}
    _wheat_cache[key] = d
    return d


def save_wheat(chat_id, user_id):
    d = _wheat_cache.get((chat_id, user_id))
    if not d:
        return
    conn = db_connect()
    try:
        conn.execute("""INSERT INTO wheat_fields
            (chat_id, user_id, plots, wheat, wheat_seed, planted_count, planted_at, eu_sold_today, eu_reset_date, silos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
            plots=excluded.plots, wheat=excluded.wheat, wheat_seed=excluded.wheat_seed,
            planted_count=excluded.planted_count, planted_at=excluded.planted_at,
            eu_sold_today=excluded.eu_sold_today, eu_reset_date=excluded.eu_reset_date,
            silos=excluded.silos""",
                     (chat_id, user_id, d["plots"], d["wheat"], d["wheat_seed"], d["planted_count"],
                      d["planted_at"], d["eu_sold_today"], d["eu_reset_date"], d.get("silos", 0)))
        conn.commit()
    finally:
        conn.close()


def wheat_capacity(chat_id, user_id):
    d = get_wheat(chat_id, user_id)
    plots_bonus = d["plots"] * WHEAT_PLOT_CAPACITY if WHEAT_AUTO_SILO_FROM_PLOTS else 0
    silos = d.get("silos", 0)
    return plots_bonus + silos * WHEAT_SILO_CAPACITY


def wheat_collect(chat_id, user_id):
    d = get_wheat(chat_id, user_id)
    if d["planted_count"] <= 0 or not d["planted_at"]:
        return 0, 0, wheat_capacity(chat_id, user_id)
    planted = _parse_dt(d["planted_at"])
    if not planted:
        return 0, 0, wheat_capacity(chat_id, user_id)
    elapsed = (datetime.now(KYIV_TZ) - planted).total_seconds()
    if elapsed < WHEAT_GROW_SEC:
        return 0, 0, wheat_capacity(chat_id, user_id)
    got = d["planted_count"] * WHEAT_YIELD_PER_PLOT
    cap = wheat_capacity(chat_id, user_id)
    free = max(0, cap - d["wheat"])
    kept = min(got, free)
    wasted = got - kept
    d["wheat"] += kept
    d["planted_count"] = 0
    d["planted_at"] = None
    save_wheat(chat_id, user_id)
    return kept, wasted, cap


def wheat_next_plot_price(plots):
    return int(PLOT_BASE_PRICE * (PLOT_PRICE_GROWTH ** plots))


def wheat_next_silo_price(silos):
    return int(WHEAT_SILO_PRICE * (1.1 ** silos))


# ================= ПРЕСТИЖ / БАНК / ДЖЕКПОТ / БІЗНЕС =================
prestige_cache: dict = {}


def get_prestige_level(chat_id, user_id):
    k = (chat_id, user_id)
    if k in prestige_cache:
        return prestige_cache[k]
    conn = db_connect()
    try:
        row = conn.execute("SELECT level FROM prestige WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
    finally:
        conn.close()
    lvl = row[0] if row else 0
    prestige_cache[k] = lvl
    return lvl


def set_prestige_level(chat_id, user_id, lvl):
    prestige_cache[(chat_id, user_id)] = lvl
    conn = db_connect()
    try:
        conn.execute("INSERT INTO prestige (chat_id, user_id, level) VALUES (?, ?, ?) ON CONFLICT(chat_id, user_id) DO UPDATE SET level=excluded.level",
                     (chat_id, user_id, lvl))
        conn.commit()
    finally:
        conn.close()


def get_prestige_bonus_pct(chat_id, user_id):
    lvl = get_prestige_level(chat_id, user_id)
    if lvl <= 0:
        return 0
    for p in PRESTIGE_LEVELS:
        if p["lvl"] == lvl:
            return p["bonus_pct"]
    return 0


def apply_prestige(chat_id, user_id, amount):
    pct = get_prestige_bonus_pct(chat_id, user_id)
    return int(amount * (1 + pct / 100.0))


bank_cache: dict = {}


def get_bank(chat_id, user_id):
    k = (chat_id, user_id)
    if k in bank_cache:
        return bank_cache[k]
    conn = db_connect()
    try:
        row = conn.execute("SELECT deposit, deposited_at FROM bank WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
    finally:
        conn.close()
    d = {"deposit": row[0] if row else 0, "deposited_at": row[1] if row else None}
    bank_cache[k] = d
    return d


def save_bank(chat_id, user_id):
    d = bank_cache.get((chat_id, user_id))
    if not d:
        return
    conn = db_connect()
    try:
        conn.execute("""INSERT INTO bank (chat_id, user_id, deposit, deposited_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(chat_id, user_id) DO UPDATE SET
                        deposit=excluded.deposit, deposited_at=excluded.deposited_at""",
                     (chat_id, user_id, d["deposit"], d["deposited_at"]))
        conn.commit()
    finally:
        conn.close()


def bank_accrue(chat_id, user_id):
    d = get_bank(chat_id, user_id)
    if d["deposit"] <= 0 or not d["deposited_at"]:
        return 0, 0
    deposited = _parse_dt(d["deposited_at"])
    if not deposited:
        return 0, 0
    hours = (datetime.now(KYIV_TZ) - deposited).total_seconds() / 3600.0
    hours = min(hours, BANK_MAX_HOURS)
    if hours < 1:
        return 0, hours
    profit = int(d["deposit"] * BANK_RATE_PER_HOUR * hours)
    profit = apply_prestige(chat_id, user_id, profit)
    return profit, hours


jackpot_cache: dict = {}


def get_jackpot(chat_id):
    if chat_id in jackpot_cache:
        return jackpot_cache[chat_id]
    conn = db_connect()
    try:
        row = conn.execute("SELECT pot, last_draw FROM jackpot WHERE chat_id=?", (chat_id,)).fetchone()
        if not row:
            conn.execute("INSERT OR IGNORE INTO jackpot (chat_id, pot, last_draw) VALUES (?, 0, NULL)", (chat_id,))
            conn.commit()
            row = (0, None)
    finally:
        conn.close()
    d = {"pot": row[0], "last_draw": row[1]}
    jackpot_cache[chat_id] = d
    return d


def save_jackpot(chat_id):
    d = jackpot_cache.get(chat_id)
    if not d:
        return
    conn = db_connect()
    try:
        conn.execute("INSERT INTO jackpot (chat_id, pot, last_draw) VALUES (?, ?, ?) ON CONFLICT(chat_id) DO UPDATE SET pot=excluded.pot, last_draw=excluded.last_draw",
                     (chat_id, d["pot"], d["last_draw"]))
        conn.commit()
    finally:
        conn.close()


def get_user_tickets(chat_id, user_id):
    conn = db_connect()
    try:
        row = conn.execute("SELECT tickets FROM jackpot_tickets WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
    finally:
        conn.close()
    return row[0] if row else 0


def add_user_tickets(chat_id, user_id, n):
    conn = db_connect()
    try:
        conn.execute("INSERT INTO jackpot_tickets (chat_id, user_id, tickets) VALUES (?, ?, ?) ON CONFLICT(chat_id, user_id) DO UPDATE SET tickets = tickets + ?",
                     (chat_id, user_id, n, n))
        conn.commit()
    finally:
        conn.close()


def get_all_tickets(chat_id):
    conn = db_connect()
    try:
        rows = conn.execute("SELECT user_id, tickets FROM jackpot_tickets WHERE chat_id=? AND tickets>0", (chat_id,)).fetchall()
    finally:
        conn.close()
    return rows


def reset_tickets(chat_id):
    conn = db_connect()
    try:
        conn.execute("DELETE FROM jackpot_tickets WHERE chat_id=?", (chat_id,))
        conn.commit()
    finally:
        conn.close()


biz_cache: dict = {}


def _biz_get(chat_id, user_id, key):
    k = (chat_id, user_id, key)
    if k in biz_cache:
        return biz_cache[k]
    conn = db_connect()
    try:
        row = conn.execute("SELECT qty, last_collect FROM businesses WHERE chat_id=? AND user_id=? AND biz_key=?",
                           (chat_id, user_id, key)).fetchone()
    finally:
        conn.close()
    d = {"qty": row[0] if row else 0, "last_collect": row[1] if row else None}
    biz_cache[k] = d
    return d


def _biz_save(chat_id, user_id, key):
    d = biz_cache.get((chat_id, user_id, key))
    if not d:
        return
    conn = db_connect()
    try:
        conn.execute("""INSERT INTO businesses (chat_id, user_id, biz_key, qty, last_collect)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(chat_id, user_id, biz_key) DO UPDATE SET
                        qty=excluded.qty, last_collect=excluded.last_collect""",
                     (chat_id, user_id, key, d["qty"], d["last_collect"]))
        conn.commit()
    finally:
        conn.close()


def collect_business_income(chat_id, user_id):
    now = datetime.now(KYIV_TZ)
    total = 0
    details = []
    for key, data in BUSINESSES.items():
        d = _biz_get(chat_id, user_id, key)
        if d["qty"] <= 0:
            continue
        last = _parse_dt(d["last_collect"]) if d["last_collect"] else None
        if last is None:
            d["last_collect"] = now.isoformat()
            _biz_save(chat_id, user_id, key)
            continue
        hours = min((now - last).total_seconds() / 3600.0, BANK_MAX_HOURS)
        if hours < 0.25:
            continue
        earned = int(d["qty"] * data["hourly"] * hours)
        earned = apply_prestige(chat_id, user_id, earned)
        if earned > 0:
            total += earned
            details.append(f"{data['emoji']} ×{d['qty']} → +{earned}")
            d["last_collect"] = now.isoformat()
            _biz_save(chat_id, user_id, key)
    if total > 0:
        before = get_economy(chat_id, user_id)["balance"]
        new_bal = db_add_balance(chat_id, user_id, total)
        db_log(chat_id, user_id, "biz_collect", total, new_bal,
               "; ".join(details)[:200], balance_before=before)
    return total, details


# ================= МАРКЕТПЛЕЙС =================
def create_listing(chat_id, seller_id, item_key, qty, price):
    conn = db_connect()
    try:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute(
                "INSERT INTO marketplace (chat_id, seller_id, item_key, qty, price, created_at, active) "
                "VALUES (?, ?, ?, ?, ?, ?, 1) RETURNING listing_id",
                (chat_id, seller_id, item_key, qty, price, datetime.now(KYIV_TZ).isoformat()))
            row = cur.fetchone()
            listing_id = row[0] if row else None
            cur.close()
            conn.commit()
            return listing_id
        else:
            cur.execute(
                "INSERT INTO marketplace (chat_id, seller_id, item_key, qty, price, created_at, active) "
                "VALUES (?, ?, ?, ?, ?, ?, 1)",
                (chat_id, seller_id, item_key, qty, price, datetime.now(KYIV_TZ).isoformat()))
            listing_id = cur.lastrowid
            cur.close()
            conn.commit()
            return listing_id
    finally:
        conn.close()


def get_listings(chat_id, limit=20):
    conn = db_connect()
    try:
        rows = conn.execute("SELECT listing_id, seller_id, item_key, qty, price FROM marketplace WHERE chat_id=? AND active=1 ORDER BY listing_id DESC LIMIT ?", (chat_id, limit)).fetchall()
    finally:
        conn.close()
    return rows


def get_listing(listing_id):
    conn = db_connect()
    try:
        row = conn.execute("SELECT listing_id, chat_id, seller_id, item_key, qty, price FROM marketplace WHERE listing_id=? AND active=1", (listing_id,)).fetchone()
    finally:
        conn.close()
    return row


def close_listing(listing_id):
    conn = db_connect()
    try:
        conn.execute("UPDATE marketplace SET active=0 WHERE listing_id=?", (listing_id,))
        conn.commit()
    finally:
        conn.close()


def create_pending_trade(chat_id, seller_id, buyer_id, item_key, qty, price):
    tid = f"{chat_id}_{random.randint(100000, 999999)}"
    conn = db_connect()
    try:
        conn.execute("""INSERT INTO pending_trades
            (trade_id, chat_id, seller_id, buyer_id, item_key, qty, price, created_at, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                     (tid, chat_id, seller_id, buyer_id, item_key, qty, price, datetime.now(KYIV_TZ).isoformat()))
        conn.commit()
    finally:
        conn.close()
    return tid


def get_pending_trade(tid):
    conn = db_connect()
    try:
        row = conn.execute("SELECT trade_id, chat_id, seller_id, buyer_id, item_key, qty, price FROM pending_trades WHERE trade_id=? AND active=1", (tid,)).fetchone()
    finally:
        conn.close()
    return row


def close_pending_trade(tid):
    conn = db_connect()
    try:
        conn.execute("UPDATE pending_trades SET active=0 WHERE trade_id=?", (tid,))
        conn.commit()
    finally:
        conn.close()


def parse_item_name(text):
    t = text.strip().lower()
    aliases = {
        "картоп": "potato", "яйц": "eggs", "молок": "milk",
        "м'яс": "meat", "мяс": "meat", "сало": "lard", "сир": "cheese",
        "пір": "feather", "перо": "feather", "страус": "ostrich_egg",
        "пшениц": "wheat", "зерн": "grain", "сін": "hay", "комбі": "mix",
        "курк": "chicken", "кури": "chicken", "півн": "rooster",
        "свин": "pig", "коров": "cow", "курч": "chick",
    }
    for alias, key in aliases.items():
        if alias in t:
            return key
    return None


def get_user_item_count(chat_id, user_id, item_key):
    if item_key not in SELLABLE_ITEMS:
        return 0
    _, col = SELLABLE_ITEMS[item_key]
    if col == "__wheat__":
        return get_wheat(chat_id, user_id)["wheat"]
    farm = get_farm(chat_id, user_id)
    return farm.get(col, 0)


def change_user_item(chat_id, user_id, item_key, delta):
    if item_key not in SELLABLE_ITEMS:
        return False
    _, col = SELLABLE_ITEMS[item_key]
    if col == "__wheat__":
        d = get_wheat(chat_id, user_id)
        if d["wheat"] + delta < 0:
            return False
        d["wheat"] += delta
        save_wheat(chat_id, user_id)
        return True
    farm = get_farm(chat_id, user_id)
    if farm.get(col, 0) + delta < 0:
        return False
    farm[col] = farm.get(col, 0) + delta
    save_farm(chat_id, user_id)
    return True


# ================= КОНТРАКТИ =================
def get_active_contract(chat_id, user_id):
    conn = db_connect()
    try:
        row = conn.execute("SELECT contract_id, product, need, reward, deadline, text FROM contracts WHERE chat_id=? AND user_id=? AND active=1 ORDER BY contract_id DESC LIMIT 1", (chat_id, user_id)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {"id": row[0], "product": row[1], "need": row[2], "reward": row[3], "deadline": row[4], "text": row[5]}


def create_new_contract(chat_id, user_id):
    tmpl = random.choice(CONTRACT_TEMPLATES)
    text, product, (lo, hi), per, hours = tmpl
    need = random.randint(lo, hi)
    reward = per * need
    deadline = (datetime.now(KYIV_TZ) + timedelta(hours=hours)).isoformat()
    conn = db_connect()
    try:
        conn.execute("INSERT INTO contracts (chat_id, user_id, product, need, reward, deadline, text, active) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                     (chat_id, user_id, product, need, reward, deadline, text))
        conn.commit()
    finally:
        conn.close()
    return get_active_contract(chat_id, user_id)


def expire_old_contracts(chat_id, user_id):
    now = datetime.now(KYIV_TZ).isoformat()
    conn = db_connect()
    try:
        conn.execute("UPDATE contracts SET active=0 WHERE chat_id=? AND user_id=? AND active=1 AND deadline < ?", (chat_id, user_id, now))
        conn.commit()
    finally:
        conn.close()


def ensure_contract(chat_id, user_id):
    expire_old_contracts(chat_id, user_id)
    c = get_active_contract(chat_id, user_id)
    if not c:
        c = create_new_contract(chat_id, user_id)
    return c


def try_fulfill_contract(chat_id, user_id):
    c = get_active_contract(chat_id, user_id)
    if not c:
        return "📋 Немає активного контракту."
    try:
        dl = _parse_dt(c["deadline"])
        if dl and dl < datetime.now(KYIV_TZ):
            conn = db_connect()
            try:
                conn.execute("UPDATE contracts SET active=0 WHERE contract_id=?", (c["id"],))
                conn.commit()
            finally:
                conn.close()
            create_new_contract(chat_id, user_id)
            return "⏰ Контракт прострочено! Створив новий."
    except Exception:
        pass
    farm = get_farm(chat_id, user_id)
    col = FARM_PRODUCT_TO_COLUMN.get(c["product"], c["product"])
    have = farm.get(col, 0)
    if have < c["need"]:
        return f"📦 У тебе {have}/{c['need']}. Недостатньо."
    farm[col] = have - c["need"]
    save_farm(chat_id, user_id)
    reward = apply_prestige(chat_id, user_id, c["reward"])
    before = get_economy(chat_id, user_id)["balance"]
    new_bal = db_add_balance(chat_id, user_id, reward)
    conn = db_connect()
    try:
        conn.execute("UPDATE contracts SET active=0 WHERE contract_id=?", (c["id"],))
        conn.commit()
    finally:
        conn.close()
    farm_add_xp(chat_id, user_id, 100)
    db_log(chat_id, user_id, "contract", reward, new_bal, f"{c['text']}", balance_before=before)
    create_new_contract(chat_id, user_id)
    return f"✅ Контракт виконано!\n💰 +{reward} 🪙\n⭐ +100 XP"


# ================= ГЛОБАЛЬНІ ЕКОНОМІЧНІ ПОДІЇ =================
GLOBAL_EVENTS = [
    {"key": "warehouse_wipe", "title": "🚨 ОБВАЛ СКЛАДІВ!",
     "text": "🔻 <b>25% пшениці</b> втрачено у всіх фермерів.\n\n💡 Розвивай поля, став силоси, розподіляй розумно!",
     "effect": "wipe_wheat"},
    {"key": "tax", "title": "🏦 НАЦБАНК СТЯГНУВ ПОДАТОК",
     "text": "🔻 З кожного балансу знято <b>3%</b> (мін. 50 🪙).\n\n💡 Тримай гроші в банку або вкладай у бізнеси!",
     "effect": "tax"},
    {"key": "drought", "title": "☀️ ЗАСУХА!",
     "text": "🔻 Посіви картоплі й пшениці загинули у всіх.\n\n💡 Запасайся кормом!",
     "effect": "drought"},
    {"key": "wheat_boom", "title": "📈 АЖІОТАЖ НА ПШЕНИЦЮ!",
     "text": "🟢 Кожен фермер отримав <b>+500 т пшениці</b>.\n\n💡 Продавай в ЄС, поки ціна висока!",
     "effect": "free_wheat"},
    {"key": "rich_day", "title": "💸 ДЕНЬ ЩЕДРОСТІ!",
     "text": "🟢 Кожен фермер отримав <b>+2,000 🪙</b>.",
     "effect": "free_money"},
    {"key": "market_panic", "title": "🌪️ РИНОК ПАНІКУЄ!",
     "text": "🔻 Усі лоти знято, товар повернуто продавцям.",
     "effect": "clear_market"},
    {"key": "animal_bonus", "title": "🐣 БУМ НАРОДЖУВАНОСТІ!",
     "text": "🟢 Кожен отримав <b>+3 курки та +1 півник</b>.",
     "effect": "free_animals"},
    {"key": "wheat_tax", "title": "🚫 ЕКСПОРТНЕ ЕМБАРГО!",
     "text": "🔻 У кожного вилучено <b>15% пшениці</b>.",
     "effect": "wheat_tax"},
]


async def apply_event_effect(chat_id: int, effect: str) -> str:
    conn = db_connect()
    affected = ""
    try:
        cur = conn.cursor()
        if effect == "wipe_wheat":
            cur.execute("UPDATE wheat_fields SET wheat = CAST(wheat * 0.75 AS INTEGER) WHERE wheat > 0")
            affected = f"📉 Постраждало: {cur.rowcount} ферм."
        elif effect == "tax":
            cur.execute("SELECT COUNT(*) FROM economy WHERE balance > 100")
            n = cur.fetchone()[0]
            cur.execute("UPDATE economy SET balance = GREATEST(0, balance - GREATEST(50, CAST(balance * 0.03 AS INTEGER))) WHERE balance > 100")
            affected = f"💸 Оштрафовано: {n} ферм."
        elif effect == "drought":
            cur.execute("UPDATE farm SET planted_count = 0, planted_at = NULL WHERE planted_count > 0")
            n1 = cur.rowcount
            cur.execute("UPDATE wheat_fields SET planted_count = 0, planted_at = NULL WHERE planted_count > 0")
            n2 = cur.rowcount
            affected = f"☀️ Знищено посівів: {n1 + n2}."
        elif effect == "free_wheat":
            cur.execute("UPDATE wheat_fields SET wheat = wheat + 500")
            affected = "🌾 +500 т усім."
        elif effect == "free_money":
            cur.execute("SELECT user_id FROM economy")
            users = [r[0] for r in cur.fetchall()]
            for u in users:
                conn.execute("UPDATE economy SET balance = balance + 2000 WHERE chat_id=? AND user_id=?", (chat_id, u))
            affected = "💰 +2,000 🪙 кожному."
        elif effect == "clear_market":
            rows = cur.execute("SELECT listing_id, seller_id, item_key, qty FROM marketplace WHERE chat_id=? AND active=1", (chat_id,)).fetchall()
            for lid, seller, item, qty in rows:
                conn.execute("UPDATE marketplace SET active=0 WHERE listing_id=?", (lid,))
            affected = f"🛍️ Знято {len(rows)} оголошень."
        elif effect == "free_animals":
            cur.execute("SELECT user_id FROM farm")
            users = [r[0] for r in cur.fetchall()]
            for u in users:
                conn.execute("UPDATE farm SET chickens = chickens + 3, roosters = roosters + 1 WHERE chat_id=? AND user_id=?", (chat_id, u))
            affected = "🐔 +3 курки, +1 півень."
        elif effect == "wheat_tax":
            cur.execute("UPDATE wheat_fields SET wheat = CAST(wheat * 0.85 AS INTEGER) WHERE wheat > 0")
            affected = "📦 Забрано 15%."
        conn.commit()
        economy_cache.clear()
        farm_cache.clear()
        _wheat_cache.clear()
        load_state_from_db()
    except Exception as e:
        logging.error(f"[EVENT] {e}")
    finally:
        conn.close()
    return affected


async def trigger_random_event():
    chat_id_str = db_get_setting("main_chat_id")
    if not chat_id_str:
        return
    try:
        chat_id = int(chat_id_str)
    except ValueError:
        return
    topic_id_str = db_get_setting(GAMES_TOPIC_KEY)
    ev = random.choice(GLOBAL_EVENTS)
    extra = await apply_event_effect(chat_id, ev["effect"])
    text = f"<b>{ev['title']}</b>\n\n{ev['text']}\n\n{extra}\n\n<i>Подія сталась автоматично.</i>"
    kwargs = {"parse_mode": "HTML", "disable_web_page_preview": True}
    if topic_id_str:
        try:
            kwargs["message_thread_id"] = int(topic_id_str)
        except ValueError:
            pass
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logging.error(f"[EVENT] send: {e}")


async def global_events_loop():
    await asyncio.sleep(120)
    while True:
        try:
            wait = random.randint(2 * 3600, 4 * 3600)
            await asyncio.sleep(wait)
            await trigger_random_event()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"[EVENT LOOP] {e}")
            await asyncio.sleep(600)


# ================= МІДЛВАР =================
class TrackUsersMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        chat = getattr(event, "chat", None)
        if chat is None and isinstance(event, CallbackQuery):
            msg = getattr(event, "message", None)
            if msg is not None:
                chat = getattr(msg, "chat", None)
        if user and chat and getattr(chat, "type", None) in ("group", "supergroup"):
            chat_id = chat.id
            if db_get_setting("main_chat_id") is None:
                db_save_setting("main_chat_id", chat_id)
            chat_users = known_users.setdefault(chat_id, {})
            name = user.full_name or user.username or str(user.id)
            username = (user.username or "").lower() or None
            prev = chat_users.get(user.id)
            if username:
                for uid2, info2 in chat_users.items():
                    if uid2 != user.id and info2.get("username") == username:
                        info2["username"] = None
            chat_users[user.id] = {"name": name, "username": username}
            try:
                if prev is None or prev.get("name") != name or prev.get("username") != username:
                    db_upsert_user_unique(chat_id, user.id, name, username)
                if prev is None:
                    db_ensure_user_rows(chat_id, user.id)
            except Exception as e:
                logging.error(f"[DB] user: {e}")
        return await handler(event, data)


class AdminStates(StatesGroup):
    waiting_for_schedule_text = State()
    waiting_for_new_link = State()


class ShopStates(StatesGroup):
    waiting_qty = State()
    waiting_custom_tag = State()
    waiting_plant_count = State()
    waiting_sell_qty = State()


bot_session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else AiohttpSession()
bot = Bot(token=BOT_TOKEN, session=bot_session)
dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(TrackUsersMiddleware())
dp.callback_query.middleware(TrackUsersMiddleware())
scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")


async def safe_answer(callback, text=None, show_alert=False):
    try:
        if text:
            await callback.answer(text, show_alert=show_alert)
        else:
            await callback.answer()
    except Exception as e:
        logging.debug(f"[ANSWER] {e}")


async def ensure_owner(cb, owner_id):
    if cb.from_user.id != owner_id:
        await safe_answer(cb, "🚫 Це не твоя ферма! Напиши «Гусь ферма».", show_alert=True)
        return False
    return True


def parse_owner(cb):
    try:
        return int(cb.data.split("|")[-1])
    except (ValueError, IndexError, AttributeError):
        return None


@dp.errors()
async def errors_handler(event, exception=None):
    try:
        if exception is None:
            exception = getattr(event, "exception", None)
        if exception is not None:
            logging.error(f"[ERROR] {type(exception).__name__}: {exception}")
        else:
            logging.error(f"[ERROR] {event}")
    except Exception as e:
        logging.error(f"[ERROR handler] {e}")
    return True


# ================= ФОТО З КЕШЕМ file_id =================
async def send_photo_cached(target, url: str, caption: str, kb, reply=False):
    file_id = _banner_file_id_cache.get(url)
    if file_id == "FAILED":
        return None
    try:
        if file_id:
            if reply:
                return await target.reply_photo(photo=file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
            else:
                return await target.answer_photo(photo=file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
        else:
            if reply:
                msg = await target.reply_photo(photo=url, caption=caption, parse_mode="HTML", reply_markup=kb)
            else:
                msg = await target.answer_photo(photo=url, caption=caption, parse_mode="HTML", reply_markup=kb)
            if msg and msg.photo:
                _banner_file_id_cache[url] = msg.photo[-1].file_id
                logging.info(f"[BANNER] cached file_id for {url[:50]}...")
            return msg
    except TelegramBadRequest as e:
        s = str(e).lower()
        if "failed to get http url content" in s or "wrong file identifier" in s or "wrong remote file identifier" in s:
            _banner_file_id_cache[url] = "FAILED"
            logging.warning(f"[BANNER] marked FAILED: {url[:60]}")
        else:
            logging.warning(f"[PHOTO] {url[:60]}: {e}")
        return None
    except Exception as e:
        logging.warning(f"[PHOTO] err {url[:60]}: {e}")
        return None


# ============ ФЕРМА + Web App (головна зміна!) ============
def _build_farm_webapp_kb(uid):
    """Кнопка Web App + текстова версія + швидкі дії."""
    url = db_get_setting("webapp_url") or WEBAPP_PUBLIC_URL
    rows = []
    if url and url.startswith("https://"):
        rows.append([InlineKeyboardButton(text="🌐 Відкрити Web App", web_app=WebAppInfo(url=url))])
    rows.append([InlineKeyboardButton(text="📋 Текстова версія ферми", callback_data=f"farmtext|{uid}")])
    rows.append([
        InlineKeyboardButton(text="🧺 Зібрати все", callback_data=f"farm|collect|{uid}"),
        InlineKeyboardButton(text="🛒 Магазин", callback_data=f"shop|main|{uid}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_farm_webapp_prompt(chat_id, user_id, reply_target):
    """
    Головна функція для групи: показує Web App кнопку + кнопку текстової ферми.
    """
    text = (
        "🐄 <b>ФЕРМА А-11</b>\n\n"
        "🌐 Натисни <b>«Відкрити Web App»</b> — повноцінна гра з тим самим балансом,\n"
        "   тваринами, бізнесами й полем. Працює як справжній застосунок.\n\n"
        "📋 Або <b>«Текстова версія»</b> — стара ферма просто в чаті.\n\n"
        "💡 Web App можна також закріпити: правий клік на кнопці → «Закріпити»."
    )
    kb = _build_farm_webapp_kb(user_id)
    msg = await send_photo_cached(reply_target, FARM_BANNER_URL, text, kb, reply=True)
    if msg is None:
        try:
            await reply_target.reply(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


async def send_shop_photo(chat_id, user_id, reply_target):
    text = render_shop_main()
    kb = build_shop_main_kb(user_id)
    msg = await send_photo_cached(reply_target, SHOP_BANNER_URL, text, kb, reply=True)
    if msg is None:
        await reply_target.reply(text, parse_mode="HTML", reply_markup=kb)


async def send_market_photo(chat_id, user_id, reply_target):
    text = render_market_main()
    kb = build_market_main_kb(user_id)
    msg = await send_photo_cached(reply_target, MARKET_BANNER_URL, text, kb, reply=True)
    if msg is None:
        await reply_target.reply(text, parse_mode="HTML", reply_markup=kb)


# ================= СТАРТОВИЙ НАБІР — ПОВІДОМЛЕННЯ =================
async def send_starter_notification(chat_id, user_id):
    text = render_starter_kit_text()
    try:
        await bot.send_message(user_id, text, parse_mode="HTML", disable_web_page_preview=True)
        return True
    except Exception as e:
        logging.info(f"[STARTER] DM failed: {e}")
    try:
        topic_id = db_get_setting(GAMES_TOPIC_KEY)
        mention = mention_html(chat_id, user_id)
        full_text = f"🎁 {mention}\n\n{text}"
        kwargs = {"parse_mode": "HTML", "disable_web_page_preview": True}
        if topic_id:
            try:
                kwargs["message_thread_id"] = int(topic_id)
            except ValueError:
                pass
        await bot.send_message(chat_id, full_text, **kwargs)
        return True
    except Exception as e:
        logging.error(f"[STARTER] Group fallback: {e}")
        return False


async def _grant_and_notify_starter(chat_id, user_id):
    try:
        ok = claim_starter_kit(chat_id, user_id)
        if not ok:
            return
        await asyncio.sleep(1)
        await send_starter_notification(chat_id, user_id)
    except Exception as e:
        logging.error(f"[STARTER] grant+notify: {e}")


async def migrate_starter_to_existing():
    if db_get_setting("starter_migration_v1_done") == "1":
        logging.info("[STARTER] Міграція вже виконувалась")
        return
    conn = db_connect()
    try:
        rows = conn.execute("""
            SELECT DISTINCT f.chat_id, f.user_id FROM farm f
            WHERE (f.chickens > 0 OR f.pigs > 0 OR f.cows > 0 OR f.ostriches > 0
                   OR f.roosters > 0 OR f.chicks > 0 OR f.eggs > 0 OR f.milk > 0
                   OR f.meat > 0 OR f.potato > 0 OR f.planted_count > 0
                   OR f.grain > 0 OR f.hay > 0 OR f.mix > 0 OR f.farm_xp > 0)
              AND NOT EXISTS (SELECT 1 FROM user_starter s WHERE s.chat_id = f.chat_id AND s.user_id = f.user_id)
        """).fetchall()
    finally:
        conn.close()
    count = 0
    for chat_id, user_id in rows:
        try:
            ok = claim_starter_kit(chat_id, user_id)
            if ok:
                count += 1
                await send_starter_notification(chat_id, user_id)
                await asyncio.sleep(2.5)
        except Exception as e:
            logging.error(f"[STARTER MIGRATION] {chat_id}/{user_id}: {e}")
    db_save_setting("starter_migration_v1_done", "1")
    logging.info(f"[STARTER] Видано {count} стартових наборів")


# ================= ШІ =================
AI_CHAT_SYSTEM_PROMPT = ("Ти — 'Гусь', саркастичний і дотепний бот-товариш шкільної групи А-11. "
                          "Відповідай українською, коротко (1-4 речення), з чорним гумором. "
                          "СУВОРО ЗАБОРОНЕНО: лайка, образи, погрози, сексуальний підтекст.")
DAILY_QUOTE_SYSTEM_PROMPT = "Згенеруй ОДНУ коротку (до 2 речень) кумедну українськомовну мотивуючу цитату для школярів. Виведи ЛИШЕ текст."
FALLBACK_QUOTES = [
    "Пари самі себе не проженуть — вставай, бо кава охолоне швидше за твою мотивацію!",
    "Сьогодні саме той день, коли можна встигнути все, окрім проспати першу пару.",
    "Дедлайни не сплять, і твій будильник теж не повинен.",
    "Хто рано встає — тому силка на пару вже прогріта.",
    "Найкращий конспект — той, що хоч трохи написаний ДО іспиту.",
]


async def call_groq(system_prompt, user_prompt, max_tokens=200):
    if not GROQ_API_KEY:
        return None
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": GROQ_MODEL, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "max_tokens": max_tokens, "temperature": 0.9}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_API_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(f"[GROQ] {e}")
        return None


async def get_daily_quote():
    quote = await call_groq(DAILY_QUOTE_SYSTEM_PROMPT, "Згенеруй нову цитату.")
    return quote or random.choice(FALLBACK_QUOTES)


# ================= ПРАВА =================
async def check_permissions(user, chat):
    if not user:
        return False
    if user.id == SUPER_ADMIN_ID:
        return True
    user_username = (user.username or "").replace("@", "").strip().lower()
    starosta = (state_data.get("starosta_username") or "").lower()
    if user_username and starosta and user_username == starosta:
        return True
    if chat and chat.type in ["group", "supergroup"]:
        try:
            member = await bot.get_chat_member(chat.id, user.id)
            if member.status in ["creator", "administrator"]:
                return True
        except Exception as e:
            logging.error(f"perm: {e}")
    return False


async def is_admin_owner_or_starosta(message):
    return await check_permissions(message.from_user, message.chat)


def add_subject_link(name, url, persist=True):
    keyword = name.strip().lower()
    key = re.sub(r"\W+", "_", keyword).strip("_") or f"subject_{len(SUBJECT_LINKS) + 1}"
    title = f"{name.strip()} (А-11)"
    SUBJECT_LINKS[key] = {"title": title, "url": url.strip(), "keywords": [keyword]}
    SUBJECT_LINKS[key]["_patterns"] = [(kw, re.compile(r"\b" + re.escape(kw), re.IGNORECASE)) for kw in SUBJECT_LINKS[key]["keywords"]]
    if persist:
        db_save_subject_link(key, title, url.strip(), keyword)
    return key


def find_subject(text_lower):
    best_data, best_len = None, -1
    for key, data in SUBJECT_LINKS.items():
        for kw, pattern in data["_patterns"]:
            if pattern.search(text_lower) and len(kw) > best_len:
                best_data, best_len = data, len(kw)
    return best_data


def build_mentions(chat_id, limit=100):
    users = known_users.get(chat_id, {})
    muted = muted_users.get(chat_id, set())
    mentions, seen_usernames = [], set()
    for uid, info in list(users.items())[:limit]:
        uname = (info.get("username") or "").lower()
        if uname:
            seen_usernames.add(uname)
        if uid in muted:
            continue
        name = info.get("name") or str(uid)
        mentions.append(f'<a href="tg://user?id={uid}">{html.escape(name)}</a>')
    for uname in DEFAULT_USERNAMES:
        if uname.lower() in seen_usernames:
            continue
        mentions.append(f"@{uname}")
    return " ".join(mentions) if mentions else "Хлопці"


def get_display_name(chat_id, user_id):
    info = known_users.get(chat_id, {}).get(user_id)
    return info["name"] if info else str(user_id)


def resolve_user_by_username(chat_id, username):
    uname = username.lstrip("@").lower()
    for uid, info in known_users.get(chat_id, {}).items():
        if info.get("username") == uname:
            return uid
    return None


def resolve_user_target(chat_id, arg):
    arg = (arg or "").strip().lstrip("@")
    if not arg:
        return None
    if arg.isdigit() and len(arg) >= 6:
        return int(arg)
    return resolve_user_by_username(chat_id, arg)


def mention_html(chat_id, user_id):
    return f'<a href="tg://user?id={user_id}">{html.escape(get_display_name(chat_id, user_id))}</a>'


def format_schedule_for_date(chat_id, target_date):
    entry = chat_schedules.get(chat_id)
    if not entry or entry["date"] != target_date:
        return None
    lines = []
    for idx, subject_text in enumerate(entry["subjects"]):
        h, m = compute_lesson_time(idx)
        found = find_subject(subject_text.lower())
        if found and found.get("url"):
            lines.append(f"🕐 {h:02d}:{m:02d} — {found['title']}\n🔗 {found['url']}")
        else:
            lines.append(f"🕐 {h:02d}:{m:02d} — {subject_text} (силки немає)")
    return "\n\n".join(lines)


def get_current_lesson(chat_id):
    entry = chat_schedules.get(chat_id)
    if not entry:
        return None
    now = datetime.now(KYIV_TZ)
    if entry["date"] != now.date():
        return None
    for idx, subject_text in enumerate(entry["subjects"]):
        h, m = compute_lesson_time(idx)
        start_dt = datetime(now.year, now.month, now.day, h, m, tzinfo=KYIV_TZ)
        if start_dt <= now < start_dt + timedelta(minutes=LESSON_DURATION_MINUTES):
            return idx, subject_text
    return None


def get_next_lesson(chat_id):
    entry = chat_schedules.get(chat_id)
    if not entry or not entry["subjects"]:
        return None
    now = datetime.now(KYIV_TZ)
    td = entry["date"]
    for idx, subject_text in enumerate(entry["subjects"]):
        h, m = compute_lesson_time(idx)
        start_dt = datetime(td.year, td.month, td.day, h, m, tzinfo=KYIV_TZ)
        if start_dt > now:
            return td, idx, subject_text
    return None


def new_challenge_id(chat_id):
    return f"{chat_id}_{random.randint(100000, 999999)}"


def build_dice_duel_keyboard(challenge_id):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎲 Кинути кубик", callback_data=f"dice|{challenge_id}|roll")]])


def build_rps_keyboard(challenge_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪨 Камінь", callback_data=f"rps|{challenge_id}|камінь"),
         InlineKeyboardButton(text="✂️ Ножиці", callback_data=f"rps|{challenge_id}|ножиці")],
        [InlineKeyboardButton(text="📄 Папір", callback_data=f"rps|{challenge_id}|папір"),
         InlineKeyboardButton(text="🕳️ Колодязь", callback_data=f"rps|{challenge_id}|колодязь")],
    ])


async def send_lesson_ping(chat_id, subject_text, is_first):
    tags = build_mentions(chat_id)
    quote = await get_daily_quote()
    found = find_subject(subject_text.lower())
    if found and found.get("url"):
        template = FIRST_LESSON_TEMPLATE if is_first else NEXT_LESSON_TEMPLATE
        text = template.format(tags=tags, title=found["title"], url=found["url"], quote=quote, mins=PRE_LESSON_PING_MINUTES, footer=FOOTER_TEXT)
    else:
        text = NO_LINK_TEMPLATE.format(tags=tags, subject=subject_text, quote=quote, mins=PRE_LESSON_PING_MINUTES, footer=FOOTER_TEXT)
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logging.error(f"ping: {e}")


async def send_break_ping(chat_id, finished_subject, next_time, next_subject):
    tags = build_mentions(chat_id)
    text = BREAK_TEMPLATE.format(tags=tags, finished=finished_subject, next_time=next_time, next_subject=next_subject, footer=FOOTER_TEXT)
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logging.error(f"break: {e}")


async def send_day_end_ping(chat_id):
    tags = build_mentions(chat_id)
    text = DAY_END_TEMPLATE.format(tags=tags, footer=FOOTER_TEXT)
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logging.error(f"dayend: {e}")


def schedule_lessons_for_date(chat_id, subjects, target_date, persist=True):
    for job in scheduler.get_jobs():
        if job.id.startswith(f"a11_{chat_id}_"):
            job.remove()
    chat_schedules[chat_id] = {"date": target_date, "subjects": list(subjects)}
    if persist:
        db_save_schedule(chat_id, target_date, subjects)
    now = datetime.now(KYIV_TZ)
    n = len(subjects)
    with_link = without_link = 0
    catch_up_lesson = None
    for idx, subject_text in enumerate(subjects):
        found = find_subject(subject_text.lower())
        if found and found.get("url"):
            with_link += 1
        else:
            without_link += 1
        start_h, start_m = compute_lesson_time(idx)
        run_dt = datetime(target_date.year, target_date.month, target_date.day, start_h, start_m, tzinfo=KYIV_TZ)
        lesson_end_dt = run_dt + timedelta(minutes=LESSON_DURATION_MINUTES)
        ping_dt = run_dt - timedelta(minutes=PRE_LESSON_PING_MINUTES)
        if lesson_end_dt <= now:
            pass
        elif ping_dt <= now < lesson_end_dt:
            catch_up_lesson = (subject_text, idx == 0)
        else:
            scheduler.add_job(send_lesson_ping, trigger="date", run_date=ping_dt, id=f"a11_{chat_id}_lesson_{idx}", replace_existing=True, args=[chat_id, subject_text, idx == 0])
        break_total = start_h * 60 + start_m + LESSON_DURATION_MINUTES
        break_h, break_m = (break_total // 60) % 24, break_total % 60
        break_dt = datetime(target_date.year, target_date.month, target_date.day, break_h, break_m, tzinfo=KYIV_TZ)
        if break_total >= 24 * 60:
            break_dt += timedelta(days=1)
        if break_dt <= now:
            continue
        if idx == n - 1:
            scheduler.add_job(send_day_end_ping, trigger="date", run_date=break_dt, id=f"a11_{chat_id}_dayend_{idx}", replace_existing=True, args=[chat_id])
        else:
            next_h, next_m = compute_lesson_time(idx + 1)
            scheduler.add_job(send_break_ping, trigger="date", run_date=break_dt, id=f"a11_{chat_id}_break_{idx}", replace_existing=True, args=[chat_id, subject_text, f"{next_h:02d}:{next_m:02d}", subjects[idx + 1]])
    return {"with_link": with_link, "without_link": without_link, "catch_up_lesson": catch_up_lesson}


def build_admin_keyboard(chat_id):
    ai_on = ai_chat_enabled.get(chat_id, False)
    ai_label = "🤖 Вимкнути ШІ" if ai_on else "🤖 Увімкнути ШІ"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Розклад на день", callback_data="btn_send_schedule")],
        [InlineKeyboardButton(text="➕ Додати силку", callback_data="btn_add_link")],
        [InlineKeyboardButton(text=ai_label, callback_data="btn_toggle_ai")],
        [InlineKeyboardButton(text="🎤 Цитата дня", callback_data="btn_send_quote")],
    ])


# ================= ФІКС RENDER =================
async def render_screen(cb, banner, caption, kb):
    msg = cb.message
    if msg is None:
        return
    banner_failed = _banner_file_id_cache.get(banner) == "FAILED"
    if msg.photo and not banner_failed:
        file_id = _banner_file_id_cache.get(banner)
        try:
            if file_id and file_id != "FAILED":
                await msg.edit_media(media=InputMediaPhoto(media=file_id, caption=caption, parse_mode="HTML"), reply_markup=kb)
            else:
                await msg.edit_media(media=InputMediaPhoto(media=banner, caption=caption, parse_mode="HTML"), reply_markup=kb)
                if msg.photo:
                    _banner_file_id_cache[banner] = msg.photo[-1].file_id
            return
        except TelegramBadRequest as e:
            s = str(e).lower()
            if "not modified" in s:
                try:
                    await msg.edit_reply_markup(reply_markup=kb)
                except Exception:
                    pass
                return
            if "failed to get http url content" in s or "wrong file identifier" in s:
                _banner_file_id_cache[banner] = "FAILED"
            logging.warning(f"[RENDER] edit_media: {e}")
        except Exception as e:
            logging.warning(f"[RENDER] edit_media err: {e}")
    try:
        await msg.edit_text(caption, parse_mode="HTML", reply_markup=kb)
        return
    except TelegramBadRequest as e:
        s = str(e).lower()
        if "not modified" in s:
            try:
                await msg.edit_reply_markup(reply_markup=kb)
            except Exception:
                pass
            return
        if "there is no text in the message" in s:
            return
        logging.warning(f"[RENDER] edit_text: {e}")
    except Exception as e:
        logging.warning(f"[RENDER] edit_text err: {e}")


# ================= МАГАЗИН / РИНОК =================
SHOP_CATEGORIES = {
    "animals": ("🐾 Тварини", [
        ("chicken", "🐔 Курка", "Несе яйця. Потрібне 🌾 зерно."),
        ("rooster", "🐓 Півень", "Для розмноження."),
        ("pig", "🐷 Свиня", "🥓 м'ясо + сало."),
        ("cow", "🐄 Корова", "🥛 молоко → 🧀 сир."),
        ("ostrich", "🦤 Страус", "🪶 пір'я + яйця."),
    ]),
    "feed": ("🌾 Корм", [
        ("grain", "🌾 Зерно", "Для курей."),
        ("hay", "🌿 Сіно", "Для свиней і корів."),
        ("mix", "🥣 Комбікорм", "Для страусів."),
    ]),
    "seeds": ("🌱 Насіння", [
        ("seed", "🥔 Насіння картоплі", "Посади → збери через 2 год."),
    ]),
    "tags": ("🏷️ Титули", [
        ("kucher", "🌾 Кучеравець", "Для тих, хто виріс на землі."),
        ("traktor", "🚜 Тракторний", "Пахне соляркою."),
        ("agronom", "🌱 Агроном", "Знаєш, коли садити."),
        ("moloko", "🥛 Молочник", "Твоє молоко — золото."),
        ("pasechnik", "🐝 Пасічник", "Бджоли тебе люблять."),
        ("fermer", "🌾 Фермер", "Справжній господар."),
        ("baron", "👑 Барон", "Твоя земля — твої правила."),
        ("korol", "🎩 Король ферми", "Хтось має правити."),
        ("magnat", "💎 Магнат", "Гроші — не все, але майже."),
        ("agrarniy", "🦅 Аграрний Орел", "З висоти."),
        ("millioner", "💰 Мільйонер", "Купа грошей."),
        ("custom", "✍️ Свій тег", "Напиши власний (до 16 символів)."),
    ]),
}
SHOP_ITEM_TO_CAT = {}
SHOP_ITEM_NAMES = {}
for _cat, (_, _items) in SHOP_CATEGORIES.items():
    for _k, _n, _d in _items:
        SHOP_ITEM_TO_CAT[_k] = _cat
        SHOP_ITEM_NAMES[_k] = _n


def get_dynamic_price(key, default):
    v = db_get_setting(f"price_{key}")
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def shop_item_price(item_key):
    if item_key in FARM_BUY_PRICE:
        return get_dynamic_price(item_key, FARM_BUY_PRICE[item_key])
    if item_key in FARM_FEED_PRICE:
        return get_dynamic_price(item_key, FARM_FEED_PRICE[item_key])
    if item_key == "seed":
        return get_dynamic_price("seed", FARM_SEED_PRICE)
    if item_key in BRAND_TAGS:
        return BRAND_TAGS[item_key]["price"]
    return 0


MARKET_PRODUCTS = {
    "eggs": ("🥚 Яйця", FARM_PRODUCT_PRICE["eggs"]),
    "milk": ("🥛 Молоко", FARM_PRODUCT_PRICE["milk"]),
    "meat": ("🥓 М'ясо", FARM_PRODUCT_PRICE["meat"]),
    "lard": ("🥓 Сало", FARM_PRODUCT_PRICE["lard"]),
    "cheese": ("🧀 Сир", FARM_PRODUCT_PRICE["cheese"]),
    "potato": ("🥔 Картопля", FARM_PRODUCT_PRICE["potato"]),
    "feather": ("🪶 Пір'я", FARM_PRODUCT_PRICE["feather"]),
    "ostrich_egg": ("🥚 Страусине яйце", FARM_PRODUCT_PRICE["ostrich_egg"]),
}
MARKET_ANIMALS = {
    "chicken": ("🐔 Курка", FARM_SELL_PRICE["chicken"]),
    "rooster": ("🐓 Півень", FARM_SELL_PRICE["rooster"]),
    "pig": ("🐷 Свиня", FARM_SELL_PRICE["pig"]),
    "cow": ("🐄 Корова", FARM_SELL_PRICE["cow"]),
    "ostrich": ("🦤 Страус", FARM_SELL_PRICE["ostrich"]),
    "chick": ("🐤 Курча", FARM_SELL_PRICE["chick"]),
}


def build_farm_main_kb(uid, chat_id=0):
    url = db_get_setting("webapp_url") or WEBAPP_PUBLIC_URL
    rows = []
    if url and url.startswith("https://"):
        rows.append([InlineKeyboardButton(text="🌐 Відкрити Web App", web_app=WebAppInfo(url=url))])
    rows += [
        [InlineKeyboardButton(text="🛒 Магазин «Агроном»", callback_data=f"shop|main|{uid}"),
         InlineKeyboardButton(text="💱 Ринок", callback_data=f"market|main|{uid}")],
        [InlineKeyboardButton(text="🛍️ Маркетплейс (гравці)", callback_data=f"mkt|menu|{uid}")],
        [InlineKeyboardButton(text="🏢 Бізнес-імперія", callback_data=f"biz|menu|{uid}"),
         InlineKeyboardButton(text="👷 Робітники", callback_data=f"work|menu|{uid}")],
        [InlineKeyboardButton(text="🌾 Поле пшениці", callback_data=f"wheat|menu|{uid}"),
         InlineKeyboardButton(text="📊 Їжа та норми", callback_data=f"food|menu|{uid}")],
        [InlineKeyboardButton(text="🌱 Посадити картоплю", callback_data=f"farm|plant|{uid}"),
         InlineKeyboardButton(text="🧺 Зібрати все", callback_data=f"farm|collect|{uid}")],
        [InlineKeyboardButton(text="🔪 Забій свині", callback_data=f"farm|slaughter|{uid}"),
         InlineKeyboardButton(text="🧀 Сироварня", callback_data=f"farm|cheese|{uid}")],
        [InlineKeyboardButton(text="🐓 Розмноження", callback_data=f"farm|breed|{uid}"),
         InlineKeyboardButton(text="🐤 Виростити курчат", callback_data=f"farm|raise|{uid}")],
        [InlineKeyboardButton(text="📋 Контракти", callback_data=f"market|contracts|{uid}"),
         InlineKeyboardButton(text="🔄 Оновити", callback_data=f"farm|menu|{uid}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_shop_main_kb(uid):
    rows = [[InlineKeyboardButton(text=title, callback_data=f"shop|cat|{key}|{uid}")] for key, (title, _) in SHOP_CATEGORIES.items()]
    rows.append([InlineKeyboardButton(text="◀️ До ферми", callback_data=f"farm|menu|{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_shop_category_kb(cat_key, uid, chat_id=0):
    _, items = SHOP_CATEGORIES[cat_key]
    rows = []
    for key, name, _ in items:
        stock_txt = ""
        if key in SHOP_STOCK and chat_id:
            stock_txt = f" [{int(get_stock(chat_id, key)):,}]"
        rows.append([InlineKeyboardButton(text=f"{name} — {shop_item_price(key)} 🪙{stock_txt}", callback_data=f"shop|buy|{cat_key}|{key}|{uid}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"shop|main|{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_shop_item_kb(cat_key, item_key, uid):
    if cat_key == "tags":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Купити", callback_data=f"tag|buy|{item_key}|{uid}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"shop|cat|{cat_key}|{uid}")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data=f"shop|qty|{cat_key}|{item_key}|1|{uid}"),
         InlineKeyboardButton(text="5", callback_data=f"shop|qty|{cat_key}|{item_key}|5|{uid}"),
         InlineKeyboardButton(text="10", callback_data=f"shop|qty|{cat_key}|{item_key}|10|{uid}")],
        [InlineKeyboardButton(text="💯 Купити 100", callback_data=f"shop|qty|{cat_key}|{item_key}|100|{uid}")],
        [InlineKeyboardButton(text="✍️ Інша кількість", callback_data=f"shop|custom|{cat_key}|{item_key}|{uid}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"shop|cat|{cat_key}|{uid}")],
    ])


def build_market_main_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Продати продукти", callback_data=f"market|cat|products|{uid}")],
        [InlineKeyboardButton(text="🐾 Продати тварин", callback_data=f"market|cat|animals|{uid}")],
        [InlineKeyboardButton(text="🛍️ Маркетплейс", callback_data=f"mkt|menu|{uid}")],
        [InlineKeyboardButton(text="📋 Контракти", callback_data=f"market|contracts|{uid}")],
        [InlineKeyboardButton(text="◀️ До ферми", callback_data=f"farm|menu|{uid}")],
    ])


def build_market_products_kb(uid):
    rows = [[InlineKeyboardButton(text=f"{name} — {price} 🪙", callback_data=f"market|sell|{key}|{uid}")] for key, (name, price) in MARKET_PRODUCTS.items()]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"market|main|{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_market_animals_kb(uid):
    rows = [[InlineKeyboardButton(text=f"{name} — {price} 🪙", callback_data=f"market|sellA|{key}|{uid}")] for key, (name, price) in MARKET_ANIMALS.items()]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"market|main|{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_market_product_detail_kb(item_key, have, uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Продати 1", callback_data=f"market|do|{item_key}|1|{uid}"),
         InlineKeyboardButton(text="Продати 5", callback_data=f"market|do|{item_key}|5|{uid}")],
        [InlineKeyboardButton(text=f"Продати ВСЕ ({have})", callback_data=f"market|do|{item_key}|all|{uid}")],
        [InlineKeyboardButton(text="✍️ Інша кількість", callback_data=f"market|custom|prod|{item_key}|{uid}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"market|cat|products|{uid}")],
    ])


def build_market_animal_detail_kb(item_key, have, uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Продати 1", callback_data=f"market|sellA_do|{item_key}|1|{uid}")],
        [InlineKeyboardButton(text=f"Продати ВСЕ ({have})", callback_data=f"market|sellA_do|{item_key}|all|{uid}")],
        [InlineKeyboardButton(text="✍️ Інша кількість", callback_data=f"market|custom|animal|{item_key}|{uid}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"market|cat|animals|{uid}")],
    ])


# ================= ФЕРМА =================
def render_farm_text_v2(chat_id, user_id):
    farm = get_farm(chat_id, user_id)
    now = datetime.now(KYIV_TZ)
    res = farm_collect_v2(farm, now)
    save_farm(chat_id, user_id)
    lvl, lvl_name = farm_level_from_xp(farm.get("farm_xp", 0))

    lines = ["🐄 <b>ФЕРМА А-11</b>", f"🏅 {lvl_name} · рівень {lvl} · ⭐ {farm.get('farm_xp', 0)} XP", ""]
    lines += ["🐾 <b>Тварини</b>",
              f"   🐔 Кури: <b>{farm['chickens']}</b>",
              f"   🐓 Півні: <b>{farm.get('roosters', 0)}</b>",
              f"   🐤 Курчата: <b>{farm.get('chicks', 0)}</b>",
              f"   🐷 Свині: <b>{farm['pigs']}</b>",
              f"   🐄 Корови: <b>{farm['cows']}</b>",
              f"   🦤 Страуси: <b>{farm.get('ostriches', 0)}</b>", ""]
    lines += ["🌾 <b>Корм і насіння</b>",
              f"   🌾 Зерно: <b>{farm.get('grain', 0):,}</b>",
              f"   🌿 Сіно: <b>{farm.get('hay', 0):,}</b>",
              f"   🥣 Комбікорм: <b>{farm.get('mix', 0):,}</b>",
              f"   🥔 Насіння: <b>{farm.get('potato_seed', 0):,}</b>", ""]
    lines += ["📦 <b>Склад</b>",
              f"   🥚 Яйця: <b>{farm['eggs']:,}</b>",
              f"   🥛 Молоко: <b>{farm['milk']:,}</b>",
              f"   🥓 М'ясо: <b>{farm['meat']:,}</b>",
              f"   🥓 Сало: <b>{farm.get('lard', 0):,}</b>",
              f"   🧀 Сир: <b>{farm.get('cheese', 0):,}</b>",
              f"   🥔 Картопля: <b>{farm['potato']:,}</b>",
              f"   🪶 Пір'я: <b>{farm.get('feathers', 0):,}</b>",
              f"   🥚 Страусині яйця: <b>{farm.get('ostrich_eggs', 0):,}</b>"]

    tag_row = db_get_user_tag(chat_id, user_id)
    if tag_row:
        lines += ["", f"🏷️ <b>Твій тег:</b> {tag_row[1]}"]

    if farm.get("cheese_started") and farm.get("cheese_batch", 0) > 0:
        started = _parse_dt(farm["cheese_started"])
        if started:
            remain = FARM_CHEESE_SEC - (now - started).total_seconds()
            lines.append("")
            if remain > 0:
                lines.append(f"🧀 <b>Сироварня:</b> {farm['cheese_batch']} шт. — залишилось {_fmt_duration(remain)}")
            else:
                lines.append("🧀 <b>Сироварня:</b> ГОТОВО! Тисни «🧺 Зібрати все».")

    if farm["planted_count"] > 0:
        if farm["planted_at"]:
            planted = _parse_dt(farm["planted_at"])
            if planted:
                remain = FARM_POTATO_GROW_SEC - (now - planted).total_seconds()
                lines.append("")
                if remain > 0:
                    lines.append(f"🌱 <b>Картопля:</b> {farm['planted_count']} шт. — залишилось {_fmt_duration(remain)}")
                else:
                    lines.append("🌱 <b>Картопля:</b> ГОТОВО! Тисни «🧺 Зібрати все».")

    ws = get_workers(chat_id, user_id)
    if ws:
        lines.append("")
        worker_names = ", ".join(f"{WORKERS[w]['emoji']}" for w in ws if w in WORKERS)
        total_wage = get_total_wage_per_hour(chat_id, user_id)
        lines.append(f"👷 <b>Робітники:</b> {worker_names}")
        lines.append(f"   💸 Зарплата: -{total_wage} 🪙/год")

    wd = get_wheat(chat_id, user_id)
    wheat_collect(chat_id, user_id)
    wd = get_wheat(chat_id, user_id)
    cap = wheat_capacity(chat_id, user_id)
    if wd["plots"] > 0 or wd["wheat"] > 0 or wd.get("silos", 0) > 0:
        lines.append("")
        lines.append(f"🌾 <b>Поле:</b> {wd['plots']} ділянок · {wd.get('silos', 0)} силосів")
        lines.append(f"   📦 Сховище: <b>{wd['wheat']:,} / {cap:,} т</b>")
        if wd["planted_count"] > 0 and wd["planted_at"]:
            planted = _parse_dt(wd["planted_at"])
            if planted:
                remain = WHEAT_GROW_SEC - (datetime.now(KYIV_TZ) - planted).total_seconds()
                if remain > 0:
                    lines.append(f"   🌱 Росте: {wd['planted_count']}× (~{wd['planted_count'] * WHEAT_YIELD_PER_PLOT} т) — {_fmt_duration(remain)}")
                else:
                    lines.append("   🌾 ДОЗРІЛО!")

    c = get_active_contract(chat_id, user_id)
    if c:
        try:
            dl = _parse_dt(c["deadline"])
            if dl:
                left_min = int((dl - now).total_seconds() // 60)
                left_str = _fmt_duration(left_min * 60) if left_min > 0 else "прострочено"
            else:
                left_str = "?"
        except Exception:
            left_str = "?"
        lines += ["", f"📋 <b>Контракт:</b> {c['text']}",
                  f"   Треба: {c['need']}× {FARM_PRODUCT_UA.get(c['product'], c['product'])} → {c['reward']:,} 🪙",
                  f"   ⏰ {left_str}"]
    return "\n".join(lines)


def farm_collect_v2(farm, now):
    result = {"collected": False, "eggs": 0, "milk": 0, "meat": 0, "potato": 0, "feed_used": 0,
              "feathers": 0, "ostrich_eggs": 0, "chicks": 0, "cheese_done": 0}
    if farm["last_collect"] is None:
        farm["last_collect"] = now.isoformat()
    else:
        last = _parse_dt(farm["last_collect"]) or now
        elapsed = min((now - last).total_seconds(), FARM_MAX_ELAPSED_HOURS * 3600)
        if elapsed >= 30 * 60:
            c_cyc = int(elapsed // FARM_CYCLE["chicken"])
            p_cyc = int(elapsed // FARM_CYCLE["pig"])
            w_cyc = int(elapsed // FARM_CYCLE["cow"])
            o_cyc = int(elapsed // FARM_CYCLE["ostrich"])
            eggs_pot = farm["chickens"] * c_cyc
            grain_need = eggs_pot
            grain_have = farm.get("grain", 0)
            grain_ratio = max(0.0, min(1.0, (grain_have / grain_need) if grain_need > 0 else 1.0))
            eggs = int(eggs_pot * grain_ratio)
            grain_used = int(grain_need * grain_ratio)
            meat_pot = farm["pigs"] * p_cyc
            milk_pot = farm["cows"] * w_cyc
            hay_need = meat_pot * 3 + milk_pot * 3
            hay_have = farm.get("hay", 0)
            hay_ratio = max(0.0, min(1.0, (hay_have / hay_need) if hay_need > 0 else 1.0))
            meat = int(meat_pot * hay_ratio)
            milk = int(milk_pot * hay_ratio)
            hay_used = int(hay_need * hay_ratio)
            feathers_pot = farm.get("ostriches", 0) * o_cyc
            oeggs_pot = farm.get("ostriches", 0) * o_cyc
            mix_need = (feathers_pot + oeggs_pot)
            mix_have = farm.get("mix", 0)
            mix_ratio = max(0.0, min(1.0, (mix_have / mix_need) if mix_need > 0 else 1.0))
            feathers = int(feathers_pot * mix_ratio)
            oeggs = int(oeggs_pot * mix_ratio)
            mix_used = int(mix_need * mix_ratio)
            if eggs + meat + milk + feathers + oeggs > 0:
                farm["grain"] = max(0, farm.get("grain", 0) - grain_used)
                farm["hay"] = max(0, farm.get("hay", 0) - hay_used)
                farm["mix"] = max(0, farm.get("mix", 0) - mix_used)
                farm["eggs"] += eggs
                farm["meat"] += meat
                farm["milk"] += milk
                farm["feathers"] = farm.get("feathers", 0) + feathers
                farm["ostrich_eggs"] = farm.get("ostrich_eggs", 0) + oeggs
                farm["last_collect"] = now.isoformat()
                result.update({"collected": True, "eggs": eggs, "meat": meat, "milk": milk,
                               "feathers": feathers, "ostrich_eggs": oeggs,
                               "feed_used": grain_used + hay_used + mix_used})
    roosters = farm.get("roosters", 0)
    if roosters >= 1 and farm["chickens"] >= 1 and farm.get("last_breed"):
        last_b = _parse_dt(farm["last_breed"])
        if last_b:
            cycles = int((now - last_b).total_seconds() // FARM_BREED_SEC)
            if cycles > 0:
                max_pairs = min(roosters, farm["chickens"])
                new_chicks = max_pairs * cycles
                if new_chicks > 0:
                    farm["chicks"] = farm.get("chicks", 0) + new_chicks
                    farm["last_breed"] = now.isoformat()
                    result["chicks"] = new_chicks
                    result["collected"] = True
    if farm.get("cheese_started") and farm.get("cheese_batch", 0) > 0:
        started = _parse_dt(farm["cheese_started"])
        if started and (now - started).total_seconds() >= FARM_CHEESE_SEC:
            produced = farm["cheese_batch"]
            farm["cheese"] = farm.get("cheese", 0) + produced
            farm["cheese_batch"] = 0
            farm["cheese_started"] = None
            result["cheese_done"] = produced
            result["collected"] = True
    if farm["planted_count"] > 0 and farm["planted_at"]:
        planted = _parse_dt(farm["planted_at"])
        if planted and (now - planted).total_seconds() >= FARM_POTATO_GROW_SEC:
            got = farm["planted_count"]
            farm["potato"] += got
            farm["planted_count"] = 0
            farm["planted_at"] = None
            result["potato"] += got
            result["collected"] = True
    return result


def farm_slaughter_pig(chat_id, user_id, count=1):
    farm = get_farm(chat_id, user_id)
    if farm["pigs"] < count:
        return f"🙅 У тебе тільки {farm['pigs']} свиней."
    farm["pigs"] -= count
    farm["meat"] = farm.get("meat", 0) + count
    farm["lard"] = farm.get("lard", 0) + count
    save_farm(chat_id, user_id)
    farm_add_xp(chat_id, user_id, 15 * count)
    db_log(chat_id, user_id, "slaughter", 0, None, f"Забив {count} свиней")
    return f"🔪 Забив {count} свиней.\n🥓 +{count} м'ясо | 🥓 +{count} сало\n🐷 Залишилось: {farm['pigs']}"


def farm_start_cheese(chat_id, user_id):
    farm = get_farm(chat_id, user_id)
    if farm.get("cheese_started"):
        return "🧀 Сироварня вже працює."
    if farm["milk"] < FARM_CHEESE_MILK_COST:
        return f"🙅 Треба {FARM_CHEESE_MILK_COST} 🥛, у тебе {farm['milk']}."
    farm["milk"] -= FARM_CHEESE_MILK_COST
    farm["cheese_batch"] = FARM_CHEESE_YIELD
    farm["cheese_started"] = datetime.now(KYIV_TZ).isoformat()
    save_farm(chat_id, user_id)
    farm_add_xp(chat_id, user_id, 25)
    db_log(chat_id, user_id, "cheese_start", 0, None, f"-{FARM_CHEESE_MILK_COST}🥛 → {FARM_CHEESE_YIELD}🧀")
    return f"🧀 Запустив варіння з {FARM_CHEESE_MILK_COST} 🥛. Отримаєш {FARM_CHEESE_YIELD} 🧀 через {FARM_CHEESE_SEC // 60} хв."


def farm_start_breeding(chat_id, user_id):
    farm = get_farm(chat_id, user_id)
    if farm.get("roosters", 0) < 1:
        return "🙅 Треба хоча б 1 🐓 півень."
    if farm["chickens"] < 1:
        return "🙅 Немає курей."
    farm["last_breed"] = datetime.now(KYIV_TZ).isoformat()
    save_farm(chat_id, user_id)
    return f"🐓 Півень почав роботу!\nКожні {FARM_BREED_SEC // 3600} год нове курча."


def farm_raise_chicks(chat_id, user_id):
    farm = get_farm(chat_id, user_id)
    chicks = farm.get("chicks", 0)
    if chicks <= 0:
        return "🙅 Немає курчат."
    max_afford = farm.get("grain", 0) // 20
    can_raise = min(chicks, max_afford)
    if can_raise <= 0:
        return f"🙅 Треба зерно (20 🌾 за курча). У тебе {farm.get('grain', 0)}"
    farm["chicks"] -= can_raise
    farm["chickens"] += can_raise
    farm["grain"] -= can_raise * 20
    save_farm(chat_id, user_id)
    farm_add_xp(chat_id, user_id, 5 * can_raise)
    db_log(chat_id, user_id, "raise_chicks", 0, None, f"+{can_raise}🐔, -{can_raise * 20}🌾")
    return f"🐤 Вирощено {can_raise} курчат!\n🌾 -{can_raise * 20} | 🐔 {farm['chickens']}"


def farm_plant_potato(chat_id, user_id, count=None):
    farm = get_farm(chat_id, user_id)
    if farm.get("planted_count", 0) > 0:
        return f"🙅 Вже посаджено {farm['planted_count']} шт. Спочатку збери."
    seeds = farm.get("potato_seed", 0)
    if seeds <= 0:
        return "🙅 Немає насіння. Купи 🥔 Насіння у магазині."
    if count is None:
        count = seeds
    count = min(int(count), seeds)
    if count <= 0:
        return "⚠️ Треба хоча б 1."
    farm["potato_seed"] = seeds - count
    farm["planted_count"] = count
    farm["planted_at"] = datetime.now(KYIV_TZ).isoformat()
    save_farm(chat_id, user_id)
    db_log(chat_id, user_id, "plant_potato", 0, None, f"Посадив {count}🥔")
    return f"🌱 Посадив {count} 🥔. Дозріє через 2 год."


# ================= РЕНДЕРИ =================
def render_shop_main():
    return "🛒 <b>Маркетплейс «Агроном»</b>\n\nТут усе для ферми + ексклюзивні титули.\n\nОбери категорію:"


def render_shop_category(cat_key):
    title, _ = SHOP_CATEGORIES[cat_key]
    if cat_key == "tags":
        return f"🏷️ <b>{title}</b>\n\nБот видасть тег у групі.\n\n⚠️ До 16 символів, без емодзі."
    return f"🛒 <b>{title}</b>\n\nОбери товар:\n<i>(лімітовано складом)</i>"


def render_shop_item(cat_key, item_key, chat_id=0):
    _, items = SHOP_CATEGORIES[cat_key]
    name, desc = "?", ""
    for k, n, d in items:
        if k == item_key:
            name, desc = n, d
            break
    price = shop_item_price(item_key)
    stock_line = ""
    if item_key in SHOP_STOCK and chat_id:
        stock = get_stock(chat_id, item_key)
        stock_line = f"\n🏭 На складі: <b>{int(stock):,}/{SHOP_STOCK[item_key]['max']:,}</b>"
    if cat_key == "tags":
        real_tag = BRAND_TAGS.get(item_key, {}).get("tag")
        tag_line = f"\n🏷️ Тег: <b>{real_tag}</b>" if real_tag else ""
        return f"<b>{name}</b>\n\n{desc}\n{tag_line}\n💰 <b>{price}</b> 🪙\n\nНатисни «Купити»."
    return f"<b>{name}</b>\n\n{desc}\n\n💰 <b>{price}</b> 🪙 / шт.{stock_line}\n\nОбери кількість:"


def render_market_main():
    return "💱 <b>РИНОК А-11</b>\n\nЩо робимо?"


def render_market_products():
    return "📦 <b>Продаж продуктів</b>\n\nОбери, що продати:"


def render_market_animals():
    return "🐾 <b>Продаж тварин</b>\n\nОбери, кого продати:"


def render_market_product_detail(chat_id, user_id, item_key):
    if item_key not in MARKET_PRODUCTS:
        return "🙅 Невідомий товар."
    name, _default = MARKET_PRODUCTS[item_key]
    price = get_dynamic_price(item_key, _default)
    col = FARM_PRODUCT_TO_COLUMN.get(item_key, item_key)
    have = get_farm(chat_id, user_id).get(col, 0)
    return f"{name}\n\n💰 {price} 🪙 / шт.\n📦 У тебе: <b>{have:,}</b> шт.\n\nОбери скільки:"


def render_market_animal_detail(chat_id, user_id, item_key):
    if item_key not in MARKET_ANIMALS:
        return "🙅 Невідома тварина."
    name, price = MARKET_ANIMALS[item_key]
    col = FARM_ANIMAL_TO_MARKET_COL.get(item_key, item_key)
    have = get_farm(chat_id, user_id).get(col, 0)
    return f"{name}\n\n💰 {price} 🪙 / шт.\n📦 У тебе: <b>{have:,}</b> шт.\n\nОбери скільки:"


def render_contracts(chat_id, user_id):
    c = ensure_contract(chat_id, user_id)
    if not c:
        return "📋 Немає активних контрактів."
    dl = _parse_dt(c["deadline"])
    if dl:
        left_min = int((dl - datetime.now(KYIV_TZ)).total_seconds() // 60)
        left_str = _fmt_duration(left_min * 60) if left_min > 0 else "прострочено"
    else:
        left_str = "?"
    farm = get_farm(chat_id, user_id)
    col = FARM_PRODUCT_TO_COLUMN.get(c["product"], c["product"])
    have = farm.get(col, 0)
    return (f"📋 <b>Активний контракт</b>\n\n{c['text']}\n\n"
            f"📦 Треба: <b>{c['need']}×</b> {FARM_PRODUCT_UA.get(c['product'], c['product'])}\n"
            f"✅ У тебе: <b>{have}</b>\n"
            f"💰 <b>{c['reward']:,}</b> 🪙\n"
            f"⌛ {left_str}")


def build_contracts_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Здати контракт", callback_data=f"market|fulfill|{uid}")],
        [InlineKeyboardButton(text="🔄 Новий контракт", callback_data=f"market|newcontract|{uid}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"market|main|{uid}")],
    ])


def render_workers_menu(chat_id, user_id):
    ws = get_workers(chat_id, user_id)
    lines = ["👷 <b>РОБІТНИКИ</b>", "",
             "<i>Робітники працюють автоматично. Зарплата списується з кожного збору врожаю.</i>",
             "<i>💡 Можна купити назавжди або взяти в оренду на 24 год.</i>", ""]
    total_wage = 0
    for key, w in WORKERS.items():
        hired = key in ws
        mark = "✅" if hired else "🔒"
        if hired:
            total_wage += w["wage"]
        lines.append(f"{mark} {w['name']} — {w['price']:,} 🪙 (оренда {w['rent_24h']:,})")
        lines.append(f"    {w['desc']} 💸 -{w['wage']} 🪙/год")
    lines.append("")
    if total_wage:
        lines.append(f"💸 Загальна зарплата: <b>{total_wage}</b> 🪙/год")
    return "\n".join(lines)


def build_workers_kb(uid, chat_id):
    ws = get_workers(chat_id, uid)
    rows = []
    for key, w in WORKERS.items():
        hired = key in ws
        if hired:
            rows.append([InlineKeyboardButton(text=f"✅ {w['name']} — працює", callback_data=f"work|hire|{key}|{uid}")])
        else:
            rows.append([
                InlineKeyboardButton(text=f"💰 Купити {w['name']} — {w['price']:,}", callback_data=f"work|hire|{key}|{uid}"),
                InlineKeyboardButton(text=f"⏰ Оренда 24г — {w['rent_24h']:,}", callback_data=f"work|rent|{key}|{uid}"),
            ])
    rows.append([InlineKeyboardButton(text="◀️ До ферми", callback_data=f"farm|menu|{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_wheat_menu(chat_id, user_id):
    d = get_wheat(chat_id, user_id)
    now = datetime.now(KYIV_TZ)
    collected, wasted, cap = wheat_collect(chat_id, user_id)
    lines = ["🌾 <b>ПШЕНИЧНЕ ПОЛЕ</b>", ""]
    if collected > 0:
        lines.append(f"✨ Зібрано: <b>+{collected} т</b> пшениці")
        if wasted > 0:
            lines.append(f"⚠️ Втрачено (нема місця): {wasted} т")
        lines.append("")
    lines.append(f"🏞️ Ділянок: <b>{d['plots']}</b> (дають +{d['plots'] * WHEAT_PLOT_CAPACITY} т місця)")
    lines.append(f"🏭 Силосів: <b>{d.get('silos', 0)}</b> (дають +{d.get('silos', 0) * WHEAT_SILO_CAPACITY} т місця)")
    lines.append("")
    filled_pct = int((d['wheat'] / cap) * 100) if cap > 0 else 0
    bar = "█" * (filled_pct // 10) + "░" * (10 - filled_pct // 10)
    lines.append(f"📦 <b>Сховище:</b> {d['wheat']:,} / {cap:,} т  [{bar}] {filled_pct}%")
    lines.append(f"🌱 Насіння: <b>{d['wheat_seed']}</b>")
    lines.append("")
    if d["planted_count"] > 0 and d["planted_at"]:
        planted = _parse_dt(d["planted_at"])
        if planted:
            remain = WHEAT_GROW_SEC - (now - planted).total_seconds()
            if remain > 0:
                lines.append(f"🌱 Росте: {d['planted_count']}× — {_fmt_duration(remain)}")
                lines.append(f"   Очікуваний врожай: <b>~{d['planted_count'] * WHEAT_YIELD_PER_PLOT} т</b>")
            else:
                lines.append("🌾 <b>ДОЗРІЛО!</b> Тисни «Зібрати».")
    lines.append("")
    lines.append(f"💰 Локальна ціна: <b>{get_dynamic_price('wheat_local', WHEAT_LOCAL_PRICE)}</b> 🪙/т")
    lines.append(f"🇪🇺 Ціна в ЄС: <b>{get_dynamic_price('wheat_eu', WHEAT_EU_PRICE)}</b> 🪙/т (ліміт {EU_DAILY_LIMIT}/добу)")
    lines.append(f"🛍️ Гравцям: <code>Гусь продати N пшеницю ЦІНА</code>")
    lines.append("")
    lines.append(f"🏞️ Наступна ділянка: <b>{wheat_next_plot_price(d['plots']):,}</b> 🪙")
    lines.append(f"🏭 Наступний силос (+{WHEAT_SILO_CAPACITY} т): <b>{wheat_next_silo_price(d.get('silos', 0)):,}</b> 🪙")
    return "\n".join(lines)


def build_wheat_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏞️ Купити ділянку", callback_data=f"wheat|buyplot|{uid}"),
         InlineKeyboardButton(text="🏭 Купити силос", callback_data=f"wheat|buysilo|{uid}")],
        [InlineKeyboardButton(text="🌱 Посадити все", callback_data=f"wheat|plant|{uid}"),
         InlineKeyboardButton(text="🌾 Зібрати", callback_data=f"wheat|collect|{uid}")],
        [InlineKeyboardButton(text="🇪🇺 Продати в ЄС (все)", callback_data=f"wheat|sell_eu|{uid}")],
        [InlineKeyboardButton(text="💰 Продати локально", callback_data=f"wheat|sell_local|{uid}")],
        [InlineKeyboardButton(text="🛒 Купити насіння ×10", callback_data=f"wheat|buyseed|{uid}")],
        [InlineKeyboardButton(text="◀️ До ферми", callback_data=f"farm|menu|{uid}")],
    ])


def render_marketplace(chat_id):
    rows = get_listings(chat_id, 20)
    if not rows:
        return ("🛍️ <b>Маркетплейс А-11</b>\n\n"
                "<i>Оголошень немає. Будь першим — напиши:</i>\n"
                "<code>Гусь продати 5 пшеницю 100</code>")
    lines = ["🛍️ <b>Маркетплейс А-11</b>", ""]
    for lid, seller, item_key, qty, price in rows:
        name = SELLABLE_ITEMS.get(item_key, (item_key, ""))[0]
        seller_name = get_display_name(chat_id, seller)
        lines.append(f"#{lid} · {name} ×{qty} — <b>{price}</b> 🪙/шт")
        lines.append(f"   👤 {html.escape(seller_name)}")
    return "\n".join(lines)


def build_marketplace_kb(uid, chat_id):
    rows = get_listings(chat_id, 10)
    kbs = []
    for lid, seller, item_key, qty, price in rows:
        if seller == uid:
            kbs.append([InlineKeyboardButton(text=f"❌ Зняти #{lid} ({SELLABLE_ITEMS[item_key][0]} ×{qty})", callback_data=f"mkt|cancel|{lid}|{uid}")])
        else:
            kbs.append([InlineKeyboardButton(text=f"✅ Купити #{lid} {SELLABLE_ITEMS[item_key][0]} ×{qty} ({price*qty} 🪙)", callback_data=f"mkt|buy|{lid}|{uid}")])
    kbs.append([InlineKeyboardButton(text="◀️ До ферми", callback_data=f"farm|menu|{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=kbs)


def render_food_table():
    lines = ["📊 <b>ХТО СКІЛЬКИ ЇСТЬ І ЩО ДАЄ</b>", ""]
    lines.append("<b>🐾 Тварини:</b>")
    for name, time_, eat, prod in ANIMAL_FACTS[:5]:
        lines.append(f"  {name} · ⏱ {time_}")
        lines.append(f"    🍽 {eat}  →  {prod}")
    lines.append("")
    lines.append("<b>🌾 Поле:</b>")
    name, time_, eat, prod = ANIMAL_FACTS[5]
    lines.append(f"  {name} · ⏱ {time_}")
    lines.append(f"    🍽 {eat}  →  {prod}")
    lines.append("")
    lines.append("<b>💡 Порада:</b> без 🌾 зерна кури не несуть яєць,")
    lines.append("без 🌿 сіна немає молока та м'яса,")
    lines.append("без 🥣 комбікорму страуси не дають пір'я та яєць.")
    return "\n".join(lines)


def render_business_menu(chat_id, user_id):
    lines = ["🏢 <b>БІЗНЕС-ІМПЕРІЯ</b>", ""]
    lvl = get_prestige_level(chat_id, user_id)
    bonus = get_prestige_bonus_pct(chat_id, user_id)
    if bonus:
        lines.append(f"💎 Престиж рів. {lvl}: +{bonus}% до всього доходу")
        lines.append("")
    total_hourly = 0
    for key, data in BUSINESSES.items():
        d = _biz_get(chat_id, user_id, key)
        qty = d["qty"]
        if qty > 0:
            total_hourly += qty * data["hourly"]
            lines.append(f"{data['emoji']} {data['name']} × <b>{qty}</b> — {data['hourly'] * qty:,} 🪙/год")
    if total_hourly == 0:
        lines.append("<i>У тебе ще немає бізнесів. Купи перший!</i>")
    else:
        lines.append("")
        lines.append(f"💰 Разом: <b>{total_hourly:,}</b> 🪙/год")
    return "\n".join(lines)


def build_business_kb(uid, chat_id):
    rows = []
    for key, data in BUSINESSES.items():
        d = _biz_get(chat_id, uid, key)
        qty = d["qty"]
        rows.append([InlineKeyboardButton(text=f"{data['emoji']} {data['name']} — {data['price']:,} 🪙 (у тебе {qty})", callback_data=f"biz|buy|{key}|{uid}")])
    rows.append([InlineKeyboardButton(text="💰 Зібрати дохід", callback_data=f"biz|collect|{uid}")])
    rows.append([InlineKeyboardButton(text="💎 Престиж", callback_data=f"prestige|menu|{uid}")])
    rows.append([InlineKeyboardButton(text="🏦 Банк", callback_data=f"bank|menu|{uid}")])
    rows.append([InlineKeyboardButton(text="🎰 Джекпот", callback_data=f"jackpot|menu|{uid}")])
    rows.append([InlineKeyboardButton(text="◀️ До ферми", callback_data=f"farm|menu|{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_prestige_menu(chat_id, user_id):
    cur = get_prestige_level(chat_id, user_id)
    bonus = get_prestige_bonus_pct(chat_id, user_id)
    lines = ["💎 <b>ПРЕСТИЖ</b>", "", f"Поточний рівень: <b>{cur}</b> (+{bonus}%)", "",
             "<i>Кожен рівень дає постійний % до всього доходу.</i>", ""]
    for p in PRESTIGE_LEVELS:
        if p["lvl"] > cur:
            lines.append(f"🔒 {p['name']} (рів. {p['lvl']}) — {p['price']:,} 🪙 → +{p['bonus_pct']}%")
            break
    return "\n".join(lines)


def build_prestige_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Прокачати престиж", callback_data=f"prestige|upgrade|{uid}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"biz|menu|{uid}")],
    ])


def render_bank_menu(chat_id, user_id):
    d = get_bank(chat_id, user_id)
    profit, hours = bank_accrue(chat_id, user_id)
    lines = ["🏦 <b>БАНК А-11</b>", "",
             f"💵 Вклад: <b>{d['deposit']:,}</b> 🪙",
             f"📈 Ставка: {int(BANK_RATE_PER_HOUR * 100)}%/год (макс. {BANK_MAX_HOURS} год)", ""]
    if d["deposit"] > 0 and d["deposited_at"]:
        deposited = _parse_dt(d["deposited_at"])
        if deposited:
            elapsed_h = (datetime.now(KYIV_TZ) - deposited).total_seconds() / 3600.0
            lines.append(f"⏱️ Пройшло: {elapsed_h:.1f} год")
            lines.append(f"💰 Накопичено: <b>+{profit:,}</b> 🪙")
    return "\n".join(lines)


def build_bank_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Покласти 10к", callback_data=f"bank|dep|10000|{uid}"),
         InlineKeyboardButton(text="💵 Покласти 100к", callback_data=f"bank|dep|100000|{uid}")],
        [InlineKeyboardButton(text="💵 Покласти ВСЕ", callback_data=f"bank|dep|all|{uid}")],
        [InlineKeyboardButton(text="🏧 Зняти з %", callback_data=f"bank|withdraw|{uid}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"biz|menu|{uid}")],
    ])


def render_jackpot_menu(chat_id, user_id):
    jp = get_jackpot(chat_id)
    my = get_user_tickets(chat_id, user_id)
    all_t = get_all_tickets(chat_id)
    total_tickets = sum(t for _, t in all_t)
    lines = ["🎰 <b>ДЖЕКПОТ</b>", "",
             f"💰 Банк: <b>{jp['pot']:,}</b> 🪙",
             f"🎫 Всього квитків: <b>{total_tickets}</b>",
             f"🎟️ Твої: <b>{my}</b>", ""]
    if total_tickets > 0:
        my_chance = my / total_tickets * 100
        lines.append(f"🎯 Твій шанс: <b>{my_chance:.2f}%</b>")
    lines.append("")
    lines.append(f"Квиток — <b>{JACKPOT_TICKET_PRICE:,}</b> 🪙")
    return "\n".join(lines)


def build_jackpot_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 Купити 1", callback_data=f"jackpot|buy|1|{uid}"),
         InlineKeyboardButton(text="🎫 Купити 5", callback_data=f"jackpot|buy|5|{uid}")],
        [InlineKeyboardButton(text="🎫 Купити 25", callback_data=f"jackpot|buy|25|{uid}")],
        [InlineKeyboardButton(text="🎲 РОЗІГРАТИ ЗАРАЗ", callback_data=f"jackpot|draw|{uid}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"biz|menu|{uid}")],
    ])


# ================= ХЕНДЛЕРИ =================
# Обробник кнопки "📋 Текстова версія ферми"
@dp.callback_query(F.data.startswith("farmtext|"))
async def cb_farmtext(cb):
    uid = parse_owner(cb)
    if uid is None:
        await safe_answer(cb)
        return
    if cb.from_user.id != uid:
        await safe_answer(cb, "🚫 Це не твоя ферма! Напиши «Гусь ферма».", show_alert=True)
        return
    chat_id = cb.message.chat.id
    await safe_answer(cb)
    text = render_farm_text_v2(chat_id, uid)
    kb = build_farm_main_kb(uid, chat_id)
    try:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    except Exception as e:
        logging.error(f"[FARMTEXT] {e}")


@dp.callback_query(F.data.startswith("farm|"))
async def cb_farm_router(cb):
    owner_id = parse_owner(cb)
    if owner_id is None or not await ensure_owner(cb, owner_id):
        return
    action = cb.data.split("|")[1]
    chat_id = cb.message.chat.id
    uid = cb.from_user.id

    if action == "menu":
        await render_screen(cb, FARM_BANNER_URL, render_farm_text_v2(chat_id, uid), build_farm_main_kb(uid, chat_id))
        await safe_answer(cb)
        return
    if action == "collect":
        farm = get_farm(chat_id, uid)
        res = farm_collect_v2(farm, datetime.now(KYIV_TZ))
        parts = []
        if res["collected"]:
            if res["eggs"] > 0:
                bonus = int(res["eggs"] * (get_worker_mult(chat_id, uid, "eggs") - 1))
                if bonus > 0:
                    farm["eggs"] += bonus
                    res["eggs"] += bonus
            if res["milk"] > 0:
                bonus = int(res["milk"] * (get_worker_mult(chat_id, uid, "milk") - 1))
                if bonus > 0:
                    farm["milk"] += bonus
                    res["milk"] += bonus
            if res["potato"] > 0:
                bonus = int(res["potato"] * (get_worker_mult(chat_id, uid, "potato") - 1))
                if bonus > 0:
                    farm["potato"] += bonus
                    res["potato"] += bonus
            save_farm(chat_id, uid)
            if res["eggs"]: parts.append(f"🥚 +{res['eggs']}")
            if res["milk"]: parts.append(f"🥛 +{res['milk']}")
            if res["meat"]: parts.append(f"🥓 +{res['meat']}")
            if res["feathers"]: parts.append(f"🪶 +{res['feathers']}")
            if res["ostrich_eggs"]: parts.append(f"🥚(стр) +{res['ostrich_eggs']}")
            if res.get("chicks"): parts.append(f"🐤 +{res['chicks']}")
            if res.get("cheese_done"): parts.append(f"🧀 +{res['cheese_done']}")
            if res.get("potato"): parts.append(f"🥔 +{res['potato']}")
            wage = get_total_wage_per_hour(chat_id, uid)
            if wage > 0:
                econ = get_economy(chat_id, uid)
                before = econ["balance"]
                econ["balance"] = max(0, econ["balance"] - wage)
                save_economy(chat_id, uid)
                db_log(chat_id, uid, "worker_wage", -wage, econ["balance"], "Зарплата робітникам", balance_before=before)
                parts.append(f"💸 -{wage} зарплата")
        else:
            farm2 = get_farm(chat_id, uid)
            last = _parse_dt(farm2.get("last_collect"))
            if last:
                elapsed = (datetime.now(KYIV_TZ) - last).total_seconds()
                if elapsed < 30*60:
                    parts.append(f"⏱ Ще зачекай {_fmt_duration(30*60 - elapsed)}")
            if not parts:
                parts.append("😴 Нема що збирати")
        await render_screen(cb, FARM_BANNER_URL, render_farm_text_v2(chat_id, uid), build_farm_main_kb(uid, chat_id))
        await safe_answer(cb, " | ".join(parts), show_alert=True)
        return
    if action == "slaughter":
        res = farm_slaughter_pig(chat_id, uid, 1)
        await render_screen(cb, FARM_BANNER_URL, render_farm_text_v2(chat_id, uid), build_farm_main_kb(uid, chat_id))
        await safe_answer(cb, res, show_alert=True)
        return
    if action == "cheese":
        res = farm_start_cheese(chat_id, uid)
        await render_screen(cb, FARM_BANNER_URL, render_farm_text_v2(chat_id, uid), build_farm_main_kb(uid, chat_id))
        await safe_answer(cb, res, show_alert=True)
        return
    if action == "breed":
        res = farm_start_breeding(chat_id, uid)
        await render_screen(cb, FARM_BANNER_URL, render_farm_text_v2(chat_id, uid), build_farm_main_kb(uid, chat_id))
        await safe_answer(cb, res, show_alert=True)
        return
    if action == "raise":
        res = farm_raise_chicks(chat_id, uid)
        await render_screen(cb, FARM_BANNER_URL, render_farm_text_v2(chat_id, uid), build_farm_main_kb(uid, chat_id))
        await safe_answer(cb, res, show_alert=True)
        return
    if action == "plant":
        farm = get_farm(chat_id, uid)
        seeds = farm.get("potato_seed", 0)
        if seeds <= 0:
            await safe_answer(cb, "🙅 Немає насіння. Купи в магазині.", show_alert=True)
            return
        if farm.get("planted_count", 0) > 0:
            await safe_answer(cb, f"🙅 Вже посаджено {farm['planted_count']} шт.", show_alert=True)
            return
        if seeds == 1:
            res = farm_plant_potato(chat_id, uid, 1)
            await render_screen(cb, FARM_BANNER_URL, render_farm_text_v2(chat_id, uid), build_farm_main_kb(uid, chat_id))
            await safe_answer(cb, res, show_alert=True)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Все ({seeds})", callback_data=f"farm|plantn|{seeds}|{uid}"),
             InlineKeyboardButton(text="1", callback_data=f"farm|plantn|1|{uid}")],
            [InlineKeyboardButton(text="✍️ Своя к-сть", callback_data=f"farm|plantc|{uid}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"farm|menu|{uid}")],
        ])
        await safe_answer(cb)
        await cb.message.answer(f"🌱 Скільки посадити? У тебе {seeds:,} 🥔.", reply_markup=kb)
        return
    if action == "plantn":
        parts = cb.data.split("|")
        try:
            n = int(parts[2])
        except (ValueError, IndexError):
            await safe_answer(cb)
            return
        res = farm_plant_potato(chat_id, uid, n)
        await render_screen(cb, FARM_BANNER_URL, render_farm_text_v2(chat_id, uid), build_farm_main_kb(uid, chat_id))
        await safe_answer(cb, res, show_alert=True)
        return
    await safe_answer(cb)


@dp.callback_query(F.data.startswith("farm|plantc|"))
async def cb_farm_plant_custom(cb, state: FSMContext):
    parts = cb.data.split("|")
    try:
        owner_id = int(parts[2])
    except (ValueError, IndexError):
        await safe_answer(cb)
        return
    if cb.from_user.id != owner_id:
        await safe_answer(cb, "🚫 Це не твоя ферма!", show_alert=True)
        return
    await state.set_state(ShopStates.waiting_plant_count)
    await state.update_data(plant_owner=cb.from_user.id, plant_chat=cb.message.chat.id)
    await safe_answer(cb)
    await cb.message.answer("✍️ Введи число — скільки картоплин посадити:")


@dp.message(ShopStates.waiting_plant_count, F.text)
async def msg_plant_count(message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    owner_id = data.get("plant_owner")
    if owner_id is not None and message.from_user.id != owner_id:
        await message.reply("🚫 Чужий діалог.")
        return
    try:
        count = int((message.text or "").strip())
    except ValueError:
        await message.reply("⚠️ Ціле число.")
        return
    res = farm_plant_potato(message.chat.id, message.from_user.id, count)
    await message.reply(res)


@dp.callback_query(F.data.startswith("food|"))
async def cb_food_menu(cb):
    owner_id = parse_owner(cb)
    if owner_id is None or not await ensure_owner(cb, owner_id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ До ферми", callback_data=f"farm|menu|{cb.from_user.id}")]])
    await render_screen(cb, FARM_BANNER_URL, render_food_table(), kb)
    await safe_answer(cb)


# ================= МАГАЗИН =================
@dp.callback_query(F.data.startswith("shop|"))
async def cb_shop_router(cb, state: FSMContext):
    owner_id = parse_owner(cb)
    if owner_id is None or not await ensure_owner(cb, owner_id):
        return
    parts = cb.data.split("|")
    action = parts[1]
    uid = cb.from_user.id
    chat_id = cb.message.chat.id

    if action == "main" and len(parts) == 3:
        await render_screen(cb, SHOP_BANNER_URL, render_shop_main(), build_shop_main_kb(uid))
        await safe_answer(cb)
        return
    if action == "cat" and len(parts) == 4:
        cat = parts[2]
        if cat not in SHOP_CATEGORIES:
            await safe_answer(cb)
            return
        await render_screen(cb, SHOP_BANNER_URL, render_shop_category(cat), build_shop_category_kb(cat, uid, chat_id))
        await safe_answer(cb)
        return
    if action == "buy" and len(parts) == 5:
        cat, item = parts[2], parts[3]
        if cat not in SHOP_CATEGORIES or item not in SHOP_ITEM_NAMES:
            await safe_answer(cb)
            return
        await render_screen(cb, SHOP_BANNER_URL, render_shop_item(cat, item, chat_id), build_shop_item_kb(cat, item, uid))
        await safe_answer(cb)
        return
    if action == "qty" and len(parts) == 6:
        cat, item, n = parts[2], parts[3], parts[4]
        try:
            count = int(n)
        except ValueError:
            await safe_answer(cb, "Помилка кількості.", show_alert=True)
            return
        res = apply_purchase(chat_id, uid, item, count)
        await safe_answer(cb, res, show_alert=True)
        return
    if action == "custom" and len(parts) == 5:
        _, _, cat, item, _ = parts
        if cat not in SHOP_CATEGORIES or item not in SHOP_ITEM_NAMES:
            await safe_answer(cb)
            return
        await state.set_state(ShopStates.waiting_qty)
        await state.update_data(shop_item=item, shop_cat=cat, shop_owner=uid)
        await safe_answer(cb)
        await cb.message.answer(f"✍️ Введи число — скільки купити «{SHOP_ITEM_NAMES.get(item, item)}»:")
        return
    await safe_answer(cb)


@dp.message(ShopStates.waiting_qty, F.text)
async def msg_shop_custom_qty(message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    item = data.get("shop_item")
    owner_id = data.get("shop_owner")
    if not item:
        await message.reply("⚠️ Помилка.")
        return
    if owner_id is not None and message.from_user.id != owner_id:
        await message.reply("🚫 Чужий магазин.")
        return
    try:
        count = int((message.text or "").strip())
    except ValueError:
        await message.reply("⚠️ Ціле число.")
        return
    if count <= 0 or count > 100_000:
        await message.reply("⚠️ 1..100000.")
        return
    await message.reply(apply_purchase(message.chat.id, message.from_user.id, item, count))


# ================= ТИТУЛИ =================
@dp.callback_query(F.data.startswith("tag|"))
async def cb_tag_router(cb, state: FSMContext):
    parts = cb.data.split("|")
    if len(parts) < 3:
        await safe_answer(cb)
        return
    action = parts[1]
    uid = cb.from_user.id

    if action == "buy":
        if len(parts) != 4:
            await safe_answer(cb)
            return
        item_key, owner_str = parts[2], parts[3]
        try:
            owner_id = int(owner_str)
        except ValueError:
            await safe_answer(cb)
            return
        if owner_id != uid:
            await safe_answer(cb, "🚫 Не твій магазин!", show_alert=True)
            return
        if item_key not in BRAND_TAGS:
            await safe_answer(cb, "Невідомий титул.", show_alert=True)
            return
        chat_id = cb.message.chat.id
        info = BRAND_TAGS[item_key]
        price = info["price"]
        econ = get_economy(chat_id, uid)
        if econ["balance"] < price:
            await safe_answer(cb, f"🙅 Треба {price:,}, у тебе {econ['balance']:,}.", show_alert=True)
            return
        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Так, купити за {price:,} 🪙", callback_data=f"tag|confirm|{item_key}|{uid}")],
            [InlineKeyboardButton(text="❌ Я передумав", callback_data=f"tag|cancel|{uid}")],
        ])
        text = (f"❓ <b>Підтверди покупку</b>\n\n{info['name']}\n"
                f"💰 <b>{price:,}</b> 🪙\n👛 У тебе: <b>{econ['balance']:,}</b> 🪙\n\nТочно купуємо?")
        await render_screen(cb, SHOP_BANNER_URL, text, kb)
        await safe_answer(cb)
        return

    if action == "cancel":
        if len(parts) != 3:
            await safe_answer(cb)
            return
        try:
            owner_id = int(parts[2])
        except ValueError:
            await safe_answer(cb)
            return
        if owner_id != uid:
            await safe_answer(cb, "🚫 Не твій діалог!", show_alert=True)
            return
        await state.clear()
        await render_screen(cb, SHOP_BANNER_URL, render_shop_category("tags"), build_shop_category_kb("tags", uid, cb.message.chat.id))
        await safe_answer(cb, "❌ Скасовано.", show_alert=True)
        return

    if action == "confirm":
        if len(parts) != 4:
            await safe_answer(cb)
            return
        item_key, owner_str = parts[2], parts[3]
        try:
            owner_id = int(owner_str)
        except ValueError:
            await safe_answer(cb)
            return
        if owner_id != uid:
            await safe_answer(cb, "🚫 Не твій діалог!", show_alert=True)
            return
        if item_key not in BRAND_TAGS:
            await safe_answer(cb, "Невідомий титул.", show_alert=True)
            return
        chat_id = cb.message.chat.id
        info = BRAND_TAGS[item_key]
        price = info["price"]
        econ = get_economy(chat_id, uid)
        if econ["balance"] < price:
            await safe_answer(cb, f"🙅 Треба {price:,}.", show_alert=True)
            await render_screen(cb, SHOP_BANNER_URL, render_shop_category("tags"), build_shop_category_kb("tags", uid, chat_id))
            return
        if item_key == "custom":
            await state.set_state(ShopStates.waiting_custom_tag)
            await state.update_data(tag_owner=uid, tag_chat=chat_id, tag_price=price)
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Я передумав", callback_data=f"tag|abort|{uid}")]])
            await safe_answer(cb)
            await cb.message.answer(
                f"✍️ Купуємо кастомний тег за <b>{price:,}</b> 🪙.\n\n"
                f"Напиши текст тегу (до 16 символів, без емодзі):\n"
                f"💡 Гроші спишуться тільки після видачі тегу.",
                parse_mode="HTML", reply_markup=kb)
            return
        real_tag = info["tag"]
        if not real_tag:
            await safe_answer(cb, "Помилка: тег не заданий.", show_alert=True)
            return
        ok, err = await try_set_member_tag(chat_id, uid, real_tag)
        if not ok:
            await safe_answer(cb, f"⚠️ Не вдалось: {err}", show_alert=True)
            return
        before = econ["balance"]
        econ["balance"] -= price
        save_economy(chat_id, uid)
        db_save_user_tag(chat_id, uid, item_key, real_tag)
        db_log(chat_id, uid, "tag_buy", -price, econ["balance"], f"{info['name']} → «{real_tag}»", balance_before=before)
        await render_screen(cb, SHOP_BANNER_URL, render_shop_category("tags"), build_shop_category_kb("tags", uid, chat_id))
        await safe_answer(cb, f"✅ Титул активовано! Тег: {real_tag}", show_alert=True)
        return

    if action == "abort":
        if len(parts) != 3:
            await safe_answer(cb)
            return
        try:
            owner_id = int(parts[2])
        except ValueError:
            await safe_answer(cb)
            return
        if owner_id != uid:
            await safe_answer(cb, "🚫 Не твій діалог!", show_alert=True)
            return
        await state.clear()
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await safe_answer(cb, "❌ Скасовано.", show_alert=True)
        return

    await safe_answer(cb)


@dp.message(ShopStates.waiting_custom_tag, F.text)
async def msg_custom_tag(message, state: FSMContext):
    data = await state.get_data()
    owner_id = data.get("tag_owner")
    if owner_id is not None and message.from_user.id != owner_id:
        await message.reply("🚫 Чужий діалог.")
        return
    tag_text = (message.text or "").strip()
    if NAME_PATTERN.match(tag_text):
        await message.reply("⚠️ Це схоже на команду бота. Натисни «❌ Я передумав».")
        return
    if not tag_text:
        await message.reply("⚠️ Порожній тег.")
        return
    if len(tag_text) > 16:
        await message.reply(f"⚠️ Задовгий ({len(tag_text)}/16).")
        return
    if any(ord(ch) > 0x2100 for ch in tag_text):
        await message.reply("⚠️ Емодзі заборонені.")
        return
    chat_id = data.get("tag_chat") or message.chat.id
    uid = message.from_user.id
    price = int(data.get("tag_price", 0) or 0)
    econ = get_economy(chat_id, uid)
    if econ["balance"] < price:
        await state.clear()
        await message.reply("⚠️ Недостатньо 🪙. Скасовано.")
        return
    ok, err = await try_set_member_tag(chat_id, uid, tag_text)
    if not ok:
        await message.reply(f"⚠️ Не вдалось: {err}\nСпробуй інший текст.")
        return
    before = econ["balance"]
    econ["balance"] -= price
    save_economy(chat_id, uid)
    db_save_user_tag(chat_id, uid, "custom", tag_text)
    db_log(chat_id, uid, "tag_custom_set", -price, econ["balance"], f"«{tag_text}»", balance_before=before)
    await state.clear()
    await message.reply(f"✅ Кастомний тег «{tag_text}» видано за {price:,} 🪙!")


async def try_set_member_tag(chat_id, user_id, tag):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setChatMemberTag"
    payload = {"chat_id": chat_id, "user_id": user_id, "tag": tag}
    kwargs = {"json": payload, "timeout": aiohttp.ClientTimeout(total=15)}
    if PROXY_URL:
        kwargs["proxy"] = PROXY_URL
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, **kwargs) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return True, ""
                return False, data.get("description", "Помилка Telegram")
    except Exception as e:
        return False, str(e)


def apply_purchase(chat_id, user_id, item, count):
    farm = get_farm(chat_id, user_id)
    econ = get_economy(chat_id, user_id)
    price = shop_item_price(item)
    if price <= 0:
        return "🙅 Невідомий товар."
    total = price * count
    if econ["balance"] < total:
        return f"🙅 Треба {total:,}, у тебе {econ['balance']:,}."
    if item in SHOP_STOCK:
        stock = get_stock(chat_id, item)
        if stock < count:
            return f"🏭 На складі замало ({int(stock):,} шт)."
    if item in FARM_BUY_PRICE:
        col = FARM_ANIMAL_TO_COLUMN[item]
        farm[col] = farm.get(col, 0) + count
    elif item in FARM_FEED_PRICE:
        farm[item] = farm.get(item, 0) + count
    elif item == "seed":
        farm["potato_seed"] = farm.get("potato_seed", 0) + count
    else:
        return "🙅 Не продається тут."
    if item in SHOP_STOCK:
        consume_stock(chat_id, item, count)
    before = econ["balance"]
    econ["balance"] -= total
    if item in FARM_BUY_PRICE:
        farm_add_xp(chat_id, user_id, 10 * count)
    elif item in FARM_FEED_PRICE:
        farm_add_xp(chat_id, user_id, 2 * count)
    save_economy(chat_id, user_id)
    save_farm(chat_id, user_id)
    db_log(chat_id, user_id, "purchase", -total, econ["balance"],
           f"{count}x {SHOP_ITEM_NAMES.get(item, item)}", balance_before=before)
    if item in FARM_BUY_PRICE:
        return f"✅ Купив {count}× {FARM_ANIMALS_UA[item]}\n💰 -{total:,} | 👛 {econ['balance']:,}"
    if item in FARM_FEED_PRICE:
        return f"✅ Купив {count}× {FARM_FEED_UA[item]}\n💰 -{total:,} | 👛 {econ['balance']:,}"
    if item == "seed":
        return f"✅ Купив {count}× 🥔\n💰 -{total:,} | 👛 {econ['balance']:,}"
    return "🙅 Невідомий."


# ================= РИНОК =================
@dp.callback_query(F.data.startswith("market|"))
async def cb_market_router(cb, state: FSMContext):
    owner_id = parse_owner(cb)
    if owner_id is None or not await ensure_owner(cb, owner_id):
        return
    parts = cb.data.split("|")
    action = parts[1]
    uid = cb.from_user.id
    chat_id = cb.message.chat.id

    if action == "main" and len(parts) == 3:
        await render_screen(cb, MARKET_BANNER_URL, render_market_main(), build_market_main_kb(uid))
        await safe_answer(cb)
        return
    if action == "cat" and len(parts) == 4:
        cat = parts[2]
        if cat == "products":
            await render_screen(cb, MARKET_BANNER_URL, render_market_products(), build_market_products_kb(uid))
        elif cat == "animals":
            await render_screen(cb, MARKET_BANNER_URL, render_market_animals(), build_market_animals_kb(uid))
        else:
            await safe_answer(cb)
            return
        await safe_answer(cb)
        return
    if action == "sell" and len(parts) == 4:
        item = parts[2]
        if item not in MARKET_PRODUCTS:
            await safe_answer(cb)
            return
        farm = get_farm(chat_id, uid)
        col = FARM_PRODUCT_TO_COLUMN.get(item, item)
        have = farm.get(col, 0)
        await render_screen(cb, MARKET_BANNER_URL, render_market_product_detail(chat_id, uid, item), build_market_product_detail_kb(item, have, uid))
        await safe_answer(cb)
        return
    if action == "do" and len(parts) == 5:
        item, n = parts[2], parts[3]
        if item not in MARKET_PRODUCTS:
            await safe_answer(cb)
            return
        farm = get_farm(chat_id, uid)
        col = FARM_PRODUCT_TO_COLUMN.get(item, item)
        have = farm.get(col, 0)
        count = have if n == "all" else int(n)
        if count <= 0:
            await safe_answer(cb, "🙅 Немає що продавати.", show_alert=True)
            return
        if have < count:
            await safe_answer(cb, f"🙅 У тебе тільки {have}.", show_alert=True)
            return
        unit = get_dynamic_price(item, FARM_PRODUCT_PRICE[item])
        gain = apply_prestige(chat_id, uid, unit * count)
        farm[col] = have - count
        save_farm(chat_id, uid)
        before = get_economy(chat_id, uid)["balance"]
        new_bal = db_add_balance(chat_id, uid, gain)
        farm_add_xp(chat_id, uid, 3 * count)
        db_log(chat_id, uid, "sale", gain, new_bal, f"{count}x {FARM_PRODUCT_UA.get(item, item)}", balance_before=before)
        farm = get_farm(chat_id, uid)
        have_new = farm.get(col, 0)
        await render_screen(cb, MARKET_BANNER_URL, render_market_product_detail(chat_id, uid, item), build_market_product_detail_kb(item, have_new, uid))
        await safe_answer(cb, f"✅ +{gain:,} 🪙 за {count} шт. | 👛 {new_bal:,}", show_alert=True)
        return
    if action == "sellA" and len(parts) == 4:
        item = parts[2]
        if item not in MARKET_ANIMALS:
            await safe_answer(cb)
            return
        farm = get_farm(chat_id, uid)
        col = FARM_ANIMAL_TO_MARKET_COL.get(item, item)
        have = farm.get(col, 0)
        await render_screen(cb, MARKET_BANNER_URL, render_market_animal_detail(chat_id, uid, item), build_market_animal_detail_kb(item, have, uid))
        await safe_answer(cb)
        return
    if action == "sellA_do" and len(parts) == 5:
        item, n = parts[2], parts[3]
        if item not in MARKET_ANIMALS:
            await safe_answer(cb)
            return
        farm = get_farm(chat_id, uid)
        col = FARM_ANIMAL_TO_MARKET_COL.get(item, item)
        have = farm.get(col, 0)
        count = have if n == "all" else int(n)
        if count <= 0:
            await safe_answer(cb, "🙅 Немає кого продавати.", show_alert=True)
            return
        if have < count:
            await safe_answer(cb, f"🙅 Тільки {have}.", show_alert=True)
            return
        gain = apply_prestige(chat_id, uid, FARM_SELL_PRICE[item] * count)
        farm[col] = have - count
        save_farm(chat_id, uid)
        before = get_economy(chat_id, uid)["balance"]
        new_bal = db_add_balance(chat_id, uid, gain)
        db_log(chat_id, uid, "sale_animal", gain, new_bal, f"{count}x {FARM_ANIMALS_UA.get(item, item)}", balance_before=before)
        farm = get_farm(chat_id, uid)
        have_new = farm.get(col, 0)
        await render_screen(cb, MARKET_BANNER_URL, render_market_animal_detail(chat_id, uid, item), build_market_animal_detail_kb(item, have_new, uid))
        await safe_answer(cb, f"✅ +{gain:,} 🪙 за {count} шт. | 👛 {new_bal:,}", show_alert=True)
        return
    if action == "custom" and len(parts) == 5:
        _, _, kind, item, owner_str = parts
        try:
            owner_id_check = int(owner_str)
        except ValueError:
            await safe_answer(cb)
            return
        if owner_id_check != uid:
            await safe_answer(cb, "🚫 Не твій діалог!", show_alert=True)
            return
        if kind == "prod" and item not in MARKET_PRODUCTS:
            await safe_answer(cb)
            return
        if kind == "animal" and item not in MARKET_ANIMALS:
            await safe_answer(cb)
            return
        await state.set_state(ShopStates.waiting_sell_qty)
        await state.update_data(sell_item=item, sell_kind=kind, sell_owner=uid, sell_chat=chat_id)
        await safe_answer(cb)
        name = MARKET_PRODUCTS.get(item, ("?",))[0] if kind == "prod" else MARKET_ANIMALS.get(item, ("?",))[0]
        await cb.message.answer(f"✍️ Введи число — скільки продати «{name}»:")
        return
    if action == "contracts" and len(parts) == 3:
        await render_screen(cb, MARKET_BANNER_URL, render_contracts(chat_id, uid), build_contracts_kb(uid))
        await safe_answer(cb)
        return
    if action == "fulfill" and len(parts) == 3:
        res = try_fulfill_contract(chat_id, uid)
        await render_screen(cb, MARKET_BANNER_URL, render_contracts(chat_id, uid), build_contracts_kb(uid))
        await safe_answer(cb, res, show_alert=True)
        return
    if action == "newcontract" and len(parts) == 3:
        expire_old_contracts(chat_id, uid)
        if get_active_contract(chat_id, uid):
            await safe_answer(cb, "У тебе вже є контракт.", show_alert=True)
            return
        create_new_contract(chat_id, uid)
        await render_screen(cb, MARKET_BANNER_URL, render_contracts(chat_id, uid), build_contracts_kb(uid))
        await safe_answer(cb, "🆕 Створено!", show_alert=True)
        return
    await safe_answer(cb)


@dp.message(ShopStates.waiting_sell_qty, F.text)
async def msg_market_sell_qty(message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    owner_id = data.get("sell_owner")
    if owner_id is not None and message.from_user.id != owner_id:
        await message.reply("🚫 Чужий діалог.")
        return
    try:
        count = int((message.text or "").strip())
    except ValueError:
        await message.reply("⚠️ Ціле число.")
        return
    if count <= 0:
        await message.reply("⚠️ Число > 0.")
        return
    kind = data.get("sell_kind")
    item = data.get("sell_item")
    chat_id = data.get("sell_chat") or message.chat.id
    uid = message.from_user.id
    farm = get_farm(chat_id, uid)
    if kind == "prod":
        if item not in MARKET_PRODUCTS:
            await message.reply("⚠️ Невідомий товар.")
            return
        col = FARM_PRODUCT_TO_COLUMN.get(item, item)
        have = farm.get(col, 0)
        if have < count:
            await message.reply(f"🙅 У тебе тільки {have}.")
            return
        unit = get_dynamic_price(item, FARM_PRODUCT_PRICE[item])
        gain = apply_prestige(chat_id, uid, unit * count)
        farm[col] = have - count
        save_farm(chat_id, uid)
        before = get_economy(chat_id, uid)["balance"]
        new_bal = db_add_balance(chat_id, uid, gain)
        farm_add_xp(chat_id, uid, 3 * count)
        db_log(chat_id, uid, "sale", gain, new_bal, f"{count}x {FARM_PRODUCT_UA.get(item, item)}", balance_before=before)
        await message.reply(f"✅ +{gain:,} 🪙 за {count} шт. | 👛 {new_bal:,}")
    elif kind == "animal":
        if item not in MARKET_ANIMALS:
            await message.reply("⚠️ Невідома тварина.")
            return
        col = FARM_ANIMAL_TO_MARKET_COL.get(item, item)
        have = farm.get(col, 0)
        if have < count:
            await message.reply(f"🙅 У тебе тільки {have}.")
            return
        gain = apply_prestige(chat_id, uid, FARM_SELL_PRICE[item] * count)
        farm[col] = have - count
        save_farm(chat_id, uid)
        before = get_economy(chat_id, uid)["balance"]
        new_bal = db_add_balance(chat_id, uid, gain)
        db_log(chat_id, uid, "sale_animal", gain, new_bal, f"{count}x {FARM_ANIMALS_UA.get(item, item)}", balance_before=before)
        await message.reply(f"✅ +{gain:,} 🪙 за {count} шт. | 👛 {new_bal:,}")
    else:
        await message.reply("⚠️ Невідомий тип.")


# ================= РОБІТНИКИ =================
@dp.callback_query(F.data.startswith("work|"))
async def cb_workers_router(cb):
    owner_id = parse_owner(cb)
    if owner_id is None or not await ensure_owner(cb, owner_id):
        return
    parts = cb.data.split("|")
    action = parts[1]
    chat_id = cb.message.chat.id
    uid = cb.from_user.id

    if action == "menu":
        await render_screen(cb, FARM_BANNER_URL, render_workers_menu(chat_id, uid), build_workers_kb(uid, chat_id))
        await safe_answer(cb)
        return
    if action == "hire":
        try:
            wkey = parts[2]
        except IndexError:
            await safe_answer(cb)
            return
        if wkey not in WORKERS:
            await safe_answer(cb)
            return
        w = WORKERS[wkey]
        ws = get_workers(chat_id, uid)
        if wkey in ws:
            await safe_answer(cb, "Вже найнятий!", show_alert=True)
            return
        econ = get_economy(chat_id, uid)
        if econ["balance"] < w["price"]:
            await safe_answer(cb, f"🙅 Треба {w['price']:,} 🪙.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Так, найняти за {w['price']:,} 🪙", callback_data=f"work|confirm|{wkey}|{uid}")],
            [InlineKeyboardButton(text="❌ Я передумав", callback_data=f"work|menu|{uid}")],
        ])
        text = (f"❓ <b>Підтверди найм</b>\n\n{w['name']}\n"
                f"💰 Ціна: <b>{w['price']:,}</b> 🪙 (назавжди)\n"
                f"💸 Зарплата: <b>-{w['wage']}</b> 🪙/год\n"
                f"📈 {w['desc']}\n\nТочно?")
        await render_screen(cb, FARM_BANNER_URL, text, kb)
        await safe_answer(cb)
        return
    if action == "rent":
        try:
            wkey = parts[2]
        except IndexError:
            await safe_answer(cb)
            return
        if wkey not in WORKERS:
            await safe_answer(cb)
            return
        w = WORKERS[wkey]
        ws = get_workers(chat_id, uid)
        if wkey in ws:
            await safe_answer(cb, "Вже працює!", show_alert=True)
            return
        econ = get_economy(chat_id, uid)
        price = w["rent_24h"]
        if econ["balance"] < price:
            await safe_answer(cb, f"🙅 Треба {price:,} 🪙.", show_alert=True)
            return
        before = econ["balance"]
        econ["balance"] -= price
        save_economy(chat_id, uid)
        hire_worker(chat_id, uid, wkey, hours=24)
        db_log(chat_id, uid, "worker_rent", -price, econ["balance"], f"{wkey} 24h", balance_before=before)
        await render_screen(cb, FARM_BANNER_URL, render_workers_menu(chat_id, uid), build_workers_kb(uid, chat_id))
        await safe_answer(cb, f"⏰ {w['name']} працює 24 години!", show_alert=True)
        return
    if action == "confirm":
        try:
            wkey = parts[2]
        except IndexError:
            await safe_answer(cb)
            return
        w = WORKERS.get(wkey)
        if not w:
            await safe_answer(cb)
            return
        econ = get_economy(chat_id, uid)
        if econ["balance"] < w["price"]:
            await safe_answer(cb, "🙅 Вже не вистачає.", show_alert=True)
            return
        before = econ["balance"]
        econ["balance"] -= w["price"]
        save_economy(chat_id, uid)
        hire_worker(chat_id, uid, wkey)
        db_log(chat_id, uid, "worker_hire", -w["price"], econ["balance"], wkey, balance_before=before)
        await render_screen(cb, FARM_BANNER_URL, render_workers_menu(chat_id, uid), build_workers_kb(uid, chat_id))
        await safe_answer(cb, f"✅ {w['name']} найнятий!", show_alert=True)
        return
    await safe_answer(cb)


# ================= ПОЛЕ ПШЕНИЦІ =================
@dp.callback_query(F.data.startswith("wheat|"))
async def cb_wheat_router(cb, state: FSMContext):
    owner_id = parse_owner(cb)
    if owner_id is None or not await ensure_owner(cb, owner_id):
        return
    parts = cb.data.split("|")
    action = parts[1]
    chat_id = cb.message.chat.id
    uid = cb.from_user.id
    d = get_wheat(chat_id, uid)

    if action == "menu":
        await render_screen(cb, FARM_BANNER_URL, render_wheat_menu(chat_id, uid), build_wheat_kb(uid))
        await safe_answer(cb)
        return
    if action == "buyplot":
        if "combine" not in get_workers(chat_id, uid):
            await safe_answer(cb, "🙅 Спочатку найми 🌾 Комбайнера!", show_alert=True)
            return
        price = wheat_next_plot_price(d["plots"])
        econ = get_economy(chat_id, uid)
        if econ["balance"] < price:
            await safe_answer(cb, f"🙅 Треба {price:,} 🪙.", show_alert=True)
            return
        before = econ["balance"]
        econ["balance"] -= price
        save_economy(chat_id, uid)
        d["plots"] += 1
        save_wheat(chat_id, uid)
        db_log(chat_id, uid, "wheat_buy_plot", -price, econ["balance"], f"plot #{d['plots']}", balance_before=before)
        await safe_answer(cb, f"🏞️ Куплено ділянку #{d['plots']}! +{WHEAT_PLOT_CAPACITY} т місця", show_alert=True)
        await render_screen(cb, FARM_BANNER_URL, render_wheat_menu(chat_id, uid), build_wheat_kb(uid))
        return
    if action == "buysilo":
        price = wheat_next_silo_price(d.get("silos", 0))
        econ = get_economy(chat_id, uid)
        if econ["balance"] < price:
            await safe_answer(cb, f"🙅 Треба {price:,} 🪙.", show_alert=True)
            return
        before = econ["balance"]
        econ["balance"] -= price
        save_economy(chat_id, uid)
        d["silos"] = d.get("silos", 0) + 1
        save_wheat(chat_id, uid)
        db_log(chat_id, uid, "wheat_buy_silo", -price, econ["balance"], f"silo #{d['silos']}", balance_before=before)
        await safe_answer(cb, f"🏭 Куплено силос! Місткість +{WHEAT_SILO_CAPACITY} т", show_alert=True)
        await render_screen(cb, FARM_BANNER_URL, render_wheat_menu(chat_id, uid), build_wheat_kb(uid))
        return
    if action == "buyseed":
        if d["plots"] <= 0:
            await safe_answer(cb, "🙅 Спочатку купи ділянку.", show_alert=True)
            return
        econ = get_economy(chat_id, uid)
        cost = WHEAT_SEED_PRICE * 10
        if econ["balance"] < cost:
            await safe_answer(cb, f"🙅 Треба {cost:,}.", show_alert=True)
            return
        if not consume_stock(chat_id, "wheat_seed", 10):
            await safe_answer(cb, "🏭 На складі замало насіння!", show_alert=True)
            return
        before = econ["balance"]
        econ["balance"] -= cost
        save_economy(chat_id, uid)
        d["wheat_seed"] += 10
        save_wheat(chat_id, uid)
        db_log(chat_id, uid, "wheat_buy_seed", -cost, econ["balance"], "+10 насіння", balance_before=before)
        await safe_answer(cb, f"🌱 +10 насіння!", show_alert=True)
        await render_screen(cb, FARM_BANNER_URL, render_wheat_menu(chat_id, uid), build_wheat_kb(uid))
        return
    if action == "plant":
        if d["plots"] <= 0:
            await safe_answer(cb, "🙅 Немає ділянок.", show_alert=True)
            return
        if d["planted_count"] > 0:
            await safe_answer(cb, "🙅 Вже посаджено.", show_alert=True)
            return
        seeds = d["wheat_seed"]
        if seeds <= 0:
            await safe_answer(cb, "🙅 Немає насіння.", show_alert=True)
            return
        to_plant = min(seeds, d["plots"])
        d["wheat_seed"] -= to_plant
        d["planted_count"] = to_plant
        d["planted_at"] = datetime.now(KYIV_TZ).isoformat()
        save_wheat(chat_id, uid)
        await safe_answer(cb, f"🌱 Посаджено {to_plant}× (~{to_plant * WHEAT_YIELD_PER_PLOT} т)!", show_alert=True)
        await render_screen(cb, FARM_BANNER_URL, render_wheat_menu(chat_id, uid), build_wheat_kb(uid))
        return
    if action == "collect":
        collected, wasted, cap = wheat_collect(chat_id, uid)
        if collected > 0 or wasted > 0:
            total = collected + wasted
            d2 = get_wheat(chat_id, uid)
            lines = ["🌾 <b>ЗБІР ВРОЖАЮ</b>", ""]
            lines.append(f"Цього разу вдалося зібрати <b>{total} т пшениці</b>!")
            lines.append("")
            lines.append(f"📦 На склад: <b>+{collected} т</b>")
            if wasted > 0:
                lines.append(f"⚠️ Втрачено (нема місця): <b>{wasted} т</b>")
            lines.append(f"🏭 Сховище: <b>{d2['wheat']:,} / {cap:,} т</b>")
            lines.append("")
            lines.append("💡 <b>Рекомендація розподілу:</b>")
            keep = min(200, d2['wheat'])
            sell_eu = max(0, d2['wheat'] - 200)
            lines.append(f"   • Залиш <b>{keep} т</b> на склад (для контрактів)")
            if sell_eu > 0:
                eu_price = get_dynamic_price("wheat_eu", WHEAT_EU_PRICE)
                lines.append(f"   • Продай <b>{sell_eu} т</b> в 🇪🇺 ЄС — це <b>{sell_eu * eu_price:,} 🪙</b>")
            free = cap - d2['wheat']
            if free <= 0:
                lines.append(f"   • ⚠️ Сховище ПОВНЕ! Купи 🏭 силос або продай")
            else:
                lines.append(f"   • Вільно: <b>{free} т</b> — встигни продати до наступного врожаю")
            lines.append("")
            lp = get_dynamic_price("wheat_local", WHEAT_LOCAL_PRICE)
            ep = get_dynamic_price("wheat_eu", WHEAT_EU_PRICE)
            lines.append(f"💰 Локально все: <b>{d2['wheat'] * lp:,}</b> 🪙")
            lines.append(f"💰 В ЄС все: <b>{d2['wheat'] * ep:,}</b> 🪙")
            await cb.message.answer("\n".join(lines), parse_mode="HTML")
        else:
            await safe_answer(cb, "😴 Ще не дозріло.", show_alert=True)
        await render_screen(cb, FARM_BANNER_URL, render_wheat_menu(chat_id, uid), build_wheat_kb(uid))
        return
    if action == "sell_eu":
        wheat_collect(chat_id, uid)
        d = get_wheat(chat_id, uid)
        if d["wheat"] <= 0:
            await safe_answer(cb, "🙅 Немає пшениці.", show_alert=True)
            return
        today = datetime.now(KYIV_TZ).date().isoformat()
        if d.get("eu_reset_date") != today:
            d["eu_sold_today"] = 0
            d["eu_reset_date"] = today
        left = EU_DAILY_LIMIT - d.get("eu_sold_today", 0)
        if left <= 0:
            await safe_answer(cb, f"🙅 Денний ліміт ЄС ({EU_DAILY_LIMIT}) вичерпано.", show_alert=True)
            return
        sell = min(d["wheat"], left)
        unit = get_dynamic_price("wheat_eu", WHEAT_EU_PRICE)
        gain = apply_prestige(chat_id, uid, sell * unit)
        d["wheat"] -= sell
        d["eu_sold_today"] = d.get("eu_sold_today", 0) + sell
        save_wheat(chat_id, uid)
        before = get_economy(chat_id, uid)["balance"]
        new_bal = db_add_balance(chat_id, uid, gain)
        db_log(chat_id, uid, "wheat_sell_eu", gain, new_bal, f"{sell}x 🌾", balance_before=before)
        await safe_answer(cb, f"🇪🇺 +{gain:,} 🪙 за {sell} т!", show_alert=True)
        await render_screen(cb, FARM_BANNER_URL, render_wheat_menu(chat_id, uid), build_wheat_kb(uid))
        return
    if action == "sell_local":
        wheat_collect(chat_id, uid)
        d = get_wheat(chat_id, uid)
        if d["wheat"] <= 0:
            await safe_answer(cb, "🙅 Немає пшениці.", show_alert=True)
            return
        sell = d["wheat"]
        unit = get_dynamic_price("wheat_local", WHEAT_LOCAL_PRICE)
        gain = apply_prestige(chat_id, uid, sell * unit)
        d["wheat"] = 0
        save_wheat(chat_id, uid)
        before = get_economy(chat_id, uid)["balance"]
        new_bal = db_add_balance(chat_id, uid, gain)
        db_log(chat_id, uid, "wheat_sell_local", gain, new_bal, f"{sell}x 🌾", balance_before=before)
        await safe_answer(cb, f"💰 +{gain:,} 🪙 за {sell} т!", show_alert=True)
        await render_screen(cb, FARM_BANNER_URL, render_wheat_menu(chat_id, uid), build_wheat_kb(uid))
        return
    await safe_answer(cb)


# ================= МАРКЕТПЛЕЙС =================
@dp.callback_query(F.data.startswith("mkt|"))
async def cb_marketplace_router(cb):
    parts = cb.data.split("|")
    action = parts[1]
    chat_id = cb.message.chat.id
    uid = cb.from_user.id

    if action == "menu":
        owner_id = parse_owner(cb)
        if owner_id != uid:
            await safe_answer(cb, "🚫 Не твій діалог!", show_alert=True)
            return
        await render_screen(cb, MARKET_BANNER_URL, render_marketplace(chat_id), build_marketplace_kb(uid, chat_id))
        await safe_answer(cb)
        return
    if action == "buy":
        try:
            lid = int(parts[2])
        except (ValueError, IndexError):
            await safe_answer(cb)
            return
        row = get_listing(lid)
        if not row:
            await safe_answer(cb, "❌ Оголошення зникло.", show_alert=True)
            return
        _, l_chat, seller, item_key, qty, price = row
        if seller == uid:
            await safe_answer(cb, "🙅 Не можна купити власне.", show_alert=True)
            return
        total = qty * price
        econ = get_economy(chat_id, uid)
        if econ["balance"] < total:
            await safe_answer(cb, f"🙅 Треба {total:,} 🪙.", show_alert=True)
            return
        if not change_user_item(chat_id, seller, item_key, -qty):
            await safe_answer(cb, "❌ У продавця вже немає товару.", show_alert=True)
            close_listing(lid)
            return
        before_b = econ["balance"]
        econ["balance"] -= total
        save_economy(chat_id, uid)
        change_user_item(chat_id, uid, item_key, qty)
        new_bal = db_add_balance(chat_id, seller, total)
        close_listing(lid)
        db_log(chat_id, uid, "mkt_buy", -total, econ["balance"], f"#{lid} {qty}x {item_key}", balance_before=before_b)
        db_log(chat_id, seller, "mkt_sell", total, new_bal, f"#{lid} {qty}x {item_key}")
        await safe_answer(cb, f"✅ Куплено {qty}× за {total:,} 🪙!", show_alert=True)
        await render_screen(cb, MARKET_BANNER_URL, render_marketplace(chat_id), build_marketplace_kb(uid, chat_id))
        return
    if action == "cancel":
        try:
            lid = int(parts[2])
        except (ValueError, IndexError):
            await safe_answer(cb)
            return
        row = get_listing(lid)
        if not row:
            await safe_answer(cb)
            return
        _, _, seller, item_key, qty, price = row
        if seller != uid:
            await safe_answer(cb, "🚫 Це не твоє оголошення.", show_alert=True)
            return
        change_user_item(chat_id, uid, item_key, qty)
        close_listing(lid)
        await safe_answer(cb, "❌ Знято. Товар повернуто.", show_alert=True)
        await render_screen(cb, MARKET_BANNER_URL, render_marketplace(chat_id), build_marketplace_kb(uid, chat_id))
        return
    await safe_answer(cb)


@dp.callback_query(F.data.startswith("trade|"))
async def cb_trade_router(cb):
    parts = cb.data.split("|")
    action = parts[1]
    tid = parts[2] if len(parts) > 2 else None
    uid = cb.from_user.id
    chat_id = cb.message.chat.id
    if not tid:
        await safe_answer(cb)
        return
    row = get_pending_trade(tid)
    if not row:
        await safe_answer(cb, "❌ Пропозиція зникла.", show_alert=True)
        return
    _, t_chat, seller, buyer, item_key, qty, price = row
    if uid not in (seller, buyer):
        await safe_answer(cb, "🚫 Не твоя угода!", show_alert=True)
        return
    if action == "accept":
        if uid != buyer:
            await safe_answer(cb, "🚫 Ти не покупець.", show_alert=True)
            return
        total = qty * price
        econ_b = get_economy(chat_id, buyer)
        if econ_b["balance"] < total:
            await safe_answer(cb, f"🙅 Треба {total:,} 🪙.", show_alert=True)
            return
        if not change_user_item(chat_id, seller, item_key, -qty):
            await safe_answer(cb, "❌ У продавця вже немає товару.", show_alert=True)
            close_pending_trade(tid)
            return
        before_b = econ_b["balance"]
        econ_b["balance"] -= total
        save_economy(chat_id, buyer)
        change_user_item(chat_id, buyer, item_key, qty)
        new_bal_s = db_add_balance(chat_id, seller, total)
        close_pending_trade(tid)
        db_log(chat_id, buyer, "p2p_buy", -total, econ_b["balance"], f"від {seller} {qty}x {item_key}", balance_before=before_b)
        db_log(chat_id, seller, "p2p_sell", total, new_bal_s, f"→ {buyer} {qty}x {item_key}")
        try:
            await cb.message.edit_text(
                f"✅ <b>Угоду виконано!</b>\n\n"
                f"{mention_html(chat_id, seller)} → {mention_html(chat_id, buyer)}\n"
                f"{SELLABLE_ITEMS[item_key][0]} ×{qty} за <b>{total:,}</b> 🪙",
                parse_mode="HTML")
        except Exception:
            pass
        await safe_answer(cb, "✅ Куплено!", show_alert=True)
        return
    if action == "reject":
        if uid != buyer:
            await safe_answer(cb, "🚫 Ти не покупець.", show_alert=True)
            return
        close_pending_trade(tid)
        try:
            await cb.message.edit_text(f"❌ {mention_html(chat_id, buyer)} відмовився.", parse_mode="HTML")
        except Exception:
            pass
        await safe_answer(cb, "Відхилено.", show_alert=True)
        return
    if action == "cancel":
        if uid != seller:
            await safe_answer(cb, "🚫 Ти не продавець.", show_alert=True)
            return
        close_pending_trade(tid)
        try:
            await cb.message.edit_text(f"❌ {mention_html(chat_id, seller)} скасував угоду.", parse_mode="HTML")
        except Exception:
            pass
        await safe_answer(cb, "Скасовано.", show_alert=True)
        return
    await safe_answer(cb)


# ================= БІЗНЕС =================
@dp.callback_query(F.data.startswith("biz|"))
async def cb_biz_router(cb):
    owner_id = parse_owner(cb)
    if owner_id is None or not await ensure_owner(cb, owner_id):
        return
    action = cb.data.split("|")[1]
    chat_id = cb.message.chat.id
    uid = cb.from_user.id
    if action == "menu":
        await render_screen(cb, FARM_BANNER_URL, render_business_menu(chat_id, uid), build_business_kb(uid, chat_id))
        await safe_answer(cb)
        return
    if action == "collect":
        total, details = collect_business_income(chat_id, uid)
        if total > 0:
            await safe_answer(cb, f"💰 +{total:,} 🪙!", show_alert=True)
        else:
            await safe_answer(cb, "😴 Ще немає що збирати (мін. 15 хв).", show_alert=True)
        await render_screen(cb, FARM_BANNER_URL, render_business_menu(chat_id, uid), build_business_kb(uid, chat_id))
        return
    if action == "buy":
        try:
            key = cb.data.split("|")[2]
        except IndexError:
            await safe_answer(cb)
            return
        if key not in BUSINESSES:
            await safe_answer(cb)
            return
        data = BUSINESSES[key]
        econ = get_economy(chat_id, uid)
        price = data["price"]
        if econ["balance"] < price:
            await safe_answer(cb, f"🙅 Треба {price:,} 🪙.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Так, купити за {price:,} 🪙", callback_data=f"biz|buyc|{key}|{uid}")],
            [InlineKeyboardButton(text="❌ Я передумав", callback_data=f"biz|menu|{uid}")],
        ])
        text = (f"❓ <b>Підтверди покупку</b>\n\n{data['emoji']} <b>{data['name']}</b>\n"
                f"💰 Ціна: <b>{price:,}</b> 🪙\n📈 Дохід: <b>{data['hourly']:,}</b> 🪙/год\n\nТочно?")
        await render_screen(cb, FARM_BANNER_URL, text, kb)
        await safe_answer(cb)
        return
    if action == "buyc":
        parts = cb.data.split("|")
        if len(parts) != 4:
            await safe_answer(cb)
            return
        key = parts[2]
        if key not in BUSINESSES:
            await safe_answer(cb)
            return
        data = BUSINESSES[key]
        econ = get_economy(chat_id, uid)
        if econ["balance"] < data["price"]:
            await safe_answer(cb, "🙅 Грошей вже не вистачає.", show_alert=True)
            return
        before = econ["balance"]
        econ["balance"] -= data["price"]
        save_economy(chat_id, uid)
        d = _biz_get(chat_id, uid, key)
        d["qty"] = d.get("qty", 0) + 1
        if not d.get("last_collect"):
            d["last_collect"] = datetime.now(KYIV_TZ).isoformat()
        _biz_save(chat_id, uid, key)
        db_log(chat_id, uid, "biz_buy", -data["price"], econ["balance"], f"{key} ×1", balance_before=before)
        await safe_answer(cb, f"✅ Куплено {data['emoji']} {data['name']}!", show_alert=True)
        await render_screen(cb, FARM_BANNER_URL, render_business_menu(chat_id, uid), build_business_kb(uid, chat_id))
        return
    await safe_answer(cb)


# ================= ПРЕСТИЖ =================
@dp.callback_query(F.data.startswith("prestige|"))
async def cb_prestige_router(cb):
    owner_id = parse_owner(cb)
    if owner_id is None or not await ensure_owner(cb, owner_id):
        return
    action = cb.data.split("|")[1]
    chat_id = cb.message.chat.id
    uid = cb.from_user.id
    if action == "menu":
        await render_screen(cb, FARM_BANNER_URL, render_prestige_menu(chat_id, uid), build_prestige_kb(uid))
        await safe_answer(cb)
        return
    if action == "upgrade":
        cur = get_prestige_level(chat_id, uid)
        nxt = None
        for p in PRESTIGE_LEVELS:
            if p["lvl"] == cur + 1:
                nxt = p
                break
        if not nxt:
            await safe_answer(cb, "🏆 Максимальний рівень!", show_alert=True)
            return
        econ = get_economy(chat_id, uid)
        if econ["balance"] < nxt["price"]:
            await safe_answer(cb, f"🙅 Треба {nxt['price']:,} 🪙.", show_alert=True)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Так, качаємо за {nxt['price']:,} 🪙", callback_data=f"prestige|confirm|{uid}")],
            [InlineKeyboardButton(text="❌ Я передумав", callback_data=f"prestige|menu|{uid}")],
        ])
        text = (f"❓ <b>Підтверди прокачку</b>\n\n"
                f"🎯 Новий рівень: <b>{nxt['name']}</b>\n"
                f"💰 Ціна: <b>{nxt['price']:,}</b> 🪙\n"
                f"📈 Бонус: <b>+{nxt['bonus_pct']}%</b>\n\nТочно?")
        await render_screen(cb, FARM_BANNER_URL, text, kb)
        await safe_answer(cb)
        return
    if action == "confirm":
        cur = get_prestige_level(chat_id, uid)
        nxt = None
        for p in PRESTIGE_LEVELS:
            if p["lvl"] == cur + 1:
                nxt = p
                break
        if not nxt:
            await safe_answer(cb)
            return
        econ = get_economy(chat_id, uid)
        if econ["balance"] < nxt["price"]:
            await safe_answer(cb, "🙅 Вже не вистачає.", show_alert=True)
            return
        before = econ["balance"]
        econ["balance"] -= nxt["price"]
        save_economy(chat_id, uid)
        set_prestige_level(chat_id, uid, nxt["lvl"])
        db_log(chat_id, uid, "prestige_up", -nxt["price"], econ["balance"], f"lvl {nxt['lvl']}", balance_before=before)
        await safe_answer(cb, f"💎 Престиж {nxt['lvl']}! +{nxt['bonus_pct']}%!", show_alert=True)
        await render_screen(cb, FARM_BANNER_URL, render_prestige_menu(chat_id, uid), build_prestige_kb(uid))
        return
    await safe_answer(cb)


# ================= БАНК =================
@dp.callback_query(F.data.startswith("bank|"))
async def cb_bank_router(cb):
    owner_id = parse_owner(cb)
    if owner_id is None or not await ensure_owner(cb, owner_id):
        return
    parts = cb.data.split("|")
    action = parts[1]
    chat_id = cb.message.chat.id
    uid = cb.from_user.id
    if action == "menu":
        await render_screen(cb, FARM_BANNER_URL, render_bank_menu(chat_id, uid), build_bank_kb(uid))
        await safe_answer(cb)
        return
    if action == "dep":
        try:
            amount_str = parts[2]
        except IndexError:
            await safe_answer(cb)
            return
        econ = get_economy(chat_id, uid)
        if amount_str == "all":
            amount = econ["balance"]
        else:
            try:
                amount = int(amount_str)
            except ValueError:
                await safe_answer(cb)
                return
        if amount < BANK_MIN_DEPOSIT:
            await safe_answer(cb, f"🙅 Мінімум {BANK_MIN_DEPOSIT:,} 🪙.", show_alert=True)
            return
        if econ["balance"] < amount:
            await safe_answer(cb, f"🙅 У тебе тільки {econ['balance']:,}.", show_alert=True)
            return
        d = get_bank(chat_id, uid)
        profit, _ = bank_accrue(chat_id, uid)
        if profit > 0:
            db_add_balance(chat_id, uid, profit)
            db_log(chat_id, uid, "bank_interest_auto", profit, None, "Авто-нарахування")
        before = econ["balance"]
        econ["balance"] -= amount
        save_economy(chat_id, uid)
        d["deposit"] = d.get("deposit", 0) + amount
        d["deposited_at"] = datetime.now(KYIV_TZ).isoformat()
        save_bank(chat_id, uid)
        db_log(chat_id, uid, "bank_deposit", -amount, econ["balance"], f"+{amount:,} на вклад", balance_before=before)
        msg = f"💵 +{amount:,} 🪙 на вклад."
        if profit > 0:
            msg += f"\n💸 Нараховано: +{profit:,} 🪙"
        await safe_answer(cb, msg, show_alert=True)
        await render_screen(cb, FARM_BANNER_URL, render_bank_menu(chat_id, uid), build_bank_kb(uid))
        return
    if action == "withdraw":
        d = get_bank(chat_id, uid)
        if d["deposit"] <= 0:
            await safe_answer(cb, "🙅 Вклад порожній.", show_alert=True)
            return
        profit, hours = bank_accrue(chat_id, uid)
        body = d["deposit"]
        total = body + profit
        db_add_balance(chat_id, uid, total)
        db_log(chat_id, uid, "bank_withdraw", total, None, f"{body:,} + {profit:,}%")
        d["deposit"] = 0
        d["deposited_at"] = None
        save_bank(chat_id, uid)
        await safe_answer(cb, f"🏧 Знято {total:,} 🪙", show_alert=True)
        await render_screen(cb, FARM_BANNER_URL, render_bank_menu(chat_id, uid), build_bank_kb(uid))
        return
    await safe_answer(cb)


# ================= ДЖЕКПОТ =================
@dp.callback_query(F.data.startswith("jackpot|"))
async def cb_jackpot_router(cb):
    owner_id = parse_owner(cb)
    if owner_id is None or not await ensure_owner(cb, owner_id):
        return
    parts = cb.data.split("|")
    action = parts[1]
    chat_id = cb.message.chat.id
    uid = cb.from_user.id
    if action == "menu":
        await render_screen(cb, FARM_BANNER_URL, render_jackpot_menu(chat_id, uid), build_jackpot_kb(uid))
        await safe_answer(cb)
        return
    if action == "buy":
        try:
            n = int(parts[2])
        except (ValueError, IndexError):
            await safe_answer(cb)
            return
        if n <= 0 or n > 100:
            await safe_answer(cb, "🙅 1..100.", show_alert=True)
            return
        cost = JACKPOT_TICKET_PRICE * n
        econ = get_economy(chat_id, uid)
        if econ["balance"] < cost:
            await safe_answer(cb, f"🙅 Треба {cost:,} 🪙.", show_alert=True)
            return
        before = econ["balance"]
        econ["balance"] -= cost
        save_economy(chat_id, uid)
        add_user_tickets(chat_id, uid, n)
        jp = get_jackpot(chat_id)
        jp["pot"] = jp.get("pot", 0) + cost
        save_jackpot(chat_id)
        db_log(chat_id, uid, "jackpot_buy", -cost, econ["balance"], f"+{n} квитків", balance_before=before)
        await safe_answer(cb, f"🎫 Куплено {n} квитків!", show_alert=True)
        await render_screen(cb, FARM_BANNER_URL, render_jackpot_menu(chat_id, uid), build_jackpot_kb(uid))
        return
    if action == "draw":
        jp = get_jackpot(chat_id)
        all_t = get_all_tickets(chat_id)
        total_tickets = sum(t for _, t in all_t)
        if total_tickets < 3:
            await safe_answer(cb, f"🙅 Мінімум 3 квитки (зараз {total_tickets}).", show_alert=True)
            return
        if jp["pot"] <= 0:
            await safe_answer(cb, "🙅 Банк порожній.", show_alert=True)
            return
        pool = []
        for user_id, t in all_t:
            pool.extend([user_id] * t)
        winner = random.choice(pool)
        pot = jp["pot"]
        db_add_balance(chat_id, winner, pot)
        db_log(chat_id, winner, "jackpot_win", pot, None, "Розіграш")
        jp["pot"] = 0
        jp["last_draw"] = datetime.now(KYIV_TZ).isoformat()
        save_jackpot(chat_id)
        reset_tickets(chat_id)
        try:
            await bot.send_message(chat_id,
                f"🎉 <b>ДЖЕКПОТ РОЗІГРАНО!</b>\n\n"
                f"🏆 {mention_html(chat_id, winner)}\n"
                f"💰 Виграш: <b>{pot:,}</b> 🪙\n"
                f"🎫 Квитків: {total_tickets}",
                parse_mode="HTML")
        except Exception as e:
            logging.error(f"jackpot: {e}")
        await safe_answer(cb, f"🎉 {pot:,} 🪙!", show_alert=True)
        return
    await safe_answer(cb)


# ================= КОМАНДИ =================
@dp.message(CommandStart())
async def cmd_start(message):
    if message.chat.type == "private":
        kb = None
        url = db_get_setting("webapp_url") or WEBAPP_PUBLIC_URL
        if url and url.startswith("https://"):
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🐄 Грати у Ферму", web_app=WebAppInfo(url=url))]
            ])
        await message.answer(
            "👋 Привіт! Додай мене в групу А-11 та надай права адміна!\n\n"
            "📋 Усі команди — /infoagro\n"
            "🌐 Або тисни кнопку нижче — грай у веб-версії з тим самим балансом!",
            parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer("Привіт. Слідкую за розкладом. `/lid2 @username` для старости. Усі команди — /infoagro")


@dp.message(Command("infoagro"))
async def cmd_infoagro(message):
    await message.answer(INFO_TEXT, parse_mode="HTML")


@dp.message(Command("setwebapp"))
async def cmd_setwebapp(message):
    if not await is_admin_owner_or_starosta(message):
        await message.reply("❌ Тільки адмін.")
        return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().startswith("https://"):
        await message.reply("Формат: <code>/setwebapp https://твій-домен.com</code>", parse_mode="HTML")
        return
    url = args[1].strip()
    db_save_setting("webapp_url", url)
    await message.reply(f"✅ Веб-гру підключено: {url}\nТепер у групі «Гусь ферма» відкриватиме Web App.")


@dp.message(Command("settopic"))
async def cmd_settopic(message):
    if not await is_admin_owner_or_starosta(message):
        await message.reply("❌ Тільки адмін.")
        return
    thread_id = getattr(message, "message_thread_id", None)
    if not thread_id:
        await message.reply("⚠️ Ця команда має бути в <b>гілці</b> (тема).", parse_mode="HTML")
        return
    db_save_setting(GAMES_TOPIC_KEY, thread_id)
    db_save_setting("main_chat_id", message.chat.id)
    await message.reply(
        f"✅ Гілку встановлено!\n"
        f"📌 chat_id: <code>{message.chat.id}</code>\n"
        f"📌 thread_id: <code>{thread_id}</code>",
        parse_mode="HTML")


@dp.message(Command("event"))
async def cmd_event(message):
    if not await is_admin_owner_or_starosta(message):
        await message.reply("❌ Тільки адмін.")
        return
    db_save_setting("main_chat_id", message.chat.id)
    await message.reply("🎲 Запускаю випадкову подію...")
    await trigger_random_event()


@dp.message(Command("reload"))
async def cmd_reload(message):
    if not await is_admin_owner_or_starosta(message):
        await message.reply("❌ Тільки адмін.")
        return
    economy_cache.clear()
    farm_cache.clear()
    _stock_cache.clear()
    _wheat_cache.clear()
    prestige_cache.clear()
    bank_cache.clear()
    jackpot_cache.clear()
    biz_cache.clear()
    known_users.clear()
    muted_users.clear()
    ai_chat_enabled.clear()
    chat_schedules.clear()
    load_state_from_db()
    db_info = "PostgreSQL" if USE_POSTGRES else "SQLite"
    await message.reply(
        f"🔄 <b>Перезавантажено з БД ({db_info})!</b>\n\n"
        f"👥 Юзерів: {sum(len(v) for v in known_users.values())}\n"
        f"🐄 Ферм: {len(farm_cache)}\n"
        f"💰 Балансів: {len(economy_cache)}",
        parse_mode="HTML")


@dp.message(Command("setprice"))
async def cmd_setprice(message):
    if not await is_admin_owner_or_starosta(message):
        await message.reply("❌ Тільки адмін.")
        return
    args = (message.text or "").split()
    if len(args) < 3:
        await message.reply(
            "Формат: <code>/setprice КЛЮЧ ЦІНА</code>\n\n"
            "Ключі:\n"
            "• eggs, milk, meat, lard, cheese, potato, feather, ostrich_egg\n"
            "• wheat_local, wheat_eu\n"
            "• grain, hay, mix, seed\n"
            "• chicken, rooster, pig, cow, ostrich",
            parse_mode="HTML")
        return
    key = args[1].lower()
    try:
        value = int(args[2])
    except ValueError:
        await message.reply("Ціна — ціле число.")
        return
    if value < 0:
        await message.reply("Ціна >= 0.")
        return
    db_save_setting(f"price_{key}", value)
    await message.reply(f"✅ Ціна <code>{key}</code> = <b>{value:,}</b> 🪙")


@dp.message(Command("money_trace"))
async def cmd_money_trace(message):
    if not await is_admin_owner_or_starosta(message):
        await message.reply("❌ Тільки адмін.")
        return
    args = (message.text or "").split()
    if len(args) < 2:
        await message.reply("Формат: <code>/money_trace @user|ID [N днів]</code>", parse_mode="HTML")
        return
    uid = resolve_user_target(message.chat.id, args[1])
    if uid is None:
        await message.reply(f"🙅 Не бачив {args[1]}.")
        return
    days = 1
    if len(args) > 2:
        try:
            days = max(1, min(30, int(args[2])))
        except ValueError:
            pass
    rows = db_get_user_transactions(message.chat.id, uid, days=days)
    if not rows:
        await message.reply(f"Немає транзакцій за {days} дн.")
        return
    lines = [f"💰 <b>Транзакції {mention_html(message.chat.id, uid)}</b> ({len(rows)}):\n"]
    total = 0
    for ts, ev, amt, b_before, b_after, det, status in rows:
        try:
            t = datetime.fromisoformat(ts).strftime("%d.%m %H:%M")
        except Exception:
            t = "?"
        icon = "🟢" if amt > 0 else ("🔴" if amt < 0 else "⚪")
        before_s = f"{b_before:,}→" if b_before is not None else ""
        after_s = f"{b_after:,}" if b_after is not None else "?"
        lines.append(f"{icon} <code>{t}</code> · {ev} · <b>{amt:+,}</b> 🪙")
        lines.append(f"    {before_s}{after_s} | {html.escape(det[:50])}")
        total += amt
    lines.append(f"\n📊 <b>Чиста зміна: {total:+,} 🪙</b>")
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n…"
    await message.reply(text, parse_mode="HTML")


@dp.message(Command("lid2"))
async def set_starosta(message):
    try:
        if await is_admin_owner_or_starosta(message):
            args = message.text.split()
            if len(args) > 1:
                ns = args[1].replace("@", "").strip()
                state_data["starosta_username"] = ns
                db_save_starosta(ns)
                await message.reply(f"✅ Старосту: @{ns}")
            else:
                await message.reply("⚠️ `/lid2 @username`", parse_mode="Markdown")
        else:
            await message.reply("❌ Тільки Власник/Адмін/староста.")
    except Exception as e:
        await message.reply(f"⚠️ {e}")


@dp.message(Command("give"))
async def cmd_give(message):
    if not await is_admin_owner_or_starosta(message):
        await message.reply("❌ Немає доступу!")
        return
    args = (message.text or "").split()
    if len(args) < 3:
        await message.reply("Формат: <code>/give @username|user_id N</code>", parse_mode="HTML")
        return
    try:
        amount = int(args[2])
    except ValueError:
        await message.reply("Сума — ціле число.")
        return
    if amount <= 0:
        await message.reply("Сума > 0.")
        return
    uid = resolve_user_target(message.chat.id, args[1])
    if uid is None:
        await message.reply(f"🙅 Не бачив {args[1]}.")
        return
    before = get_economy(message.chat.id, uid)["balance"]
    new_bal = db_add_balance(message.chat.id, uid, amount)
    db_log(message.chat.id, uid, "admin_give", amount, new_bal, f"від @{message.from_user.username}", balance_before=before)
    await message.reply(f"✅ {mention_html(message.chat.id, uid)} +{amount:,} 🪙. Баланс: <b>{new_bal:,}</b>", parse_mode="HTML")


@dp.message(Command("take"))
async def cmd_take(message):
    if not await is_admin_owner_or_starosta(message):
        await message.reply("❌ Немає доступу!")
        return
    args = (message.text or "").split()
    if len(args) < 3:
        await message.reply("Формат: <code>/take @username|user_id N</code>", parse_mode="HTML")
        return
    try:
        amount = int(args[2])
    except ValueError:
        await message.reply("Сума — ціле число.")
        return
    if amount <= 0:
        await message.reply("Сума > 0.")
        return
    uid = resolve_user_target(message.chat.id, args[1])
    if uid is None:
        await message.reply(f"🙅 Не бачив {args[1]}.")
        return
    before = get_economy(message.chat.id, uid)["balance"]
    new_bal = db_add_balance(message.chat.id, uid, -amount)
    db_log(message.chat.id, uid, "admin_take", -amount, new_bal, f"від @{message.from_user.username}", balance_before=before)
    await message.reply(f"✅ -{amount:,} 🪙. Баланс: <b>{new_bal:,}</b>", parse_mode="HTML")


@dp.message(Command("setbal"))
async def cmd_setbal(message):
    if not await is_admin_owner_or_starosta(message):
        await message.reply("❌ Немає доступу!")
        return
    args = (message.text or "").split()
    if len(args) < 3:
        await message.reply("Формат: <code>/setbal @username|user_id N</code>", parse_mode="HTML")
        return
    try:
        amount = int(args[2])
    except ValueError:
        await message.reply("Сума — ціле число.")
        return
    if amount < 0:
        await message.reply("Сума >= 0.")
        return
    uid = resolve_user_target(message.chat.id, args[1])
    if uid is None:
        await message.reply(f"🙅 Не бачив {args[1]}.")
        return
    before = get_economy(message.chat.id, uid)["balance"]
    db_set_balance(message.chat.id, uid, amount)
    db_log(message.chat.id, uid, "admin_setbal", amount - before, amount, f"від @{message.from_user.username}", balance_before=before)
    await message.reply(f"✅ Баланс = <b>{amount:,}</b> 🪙", parse_mode="HTML")


@dp.message(Command("settag"))
async def cmd_settag(message):
    if not await is_admin_owner_or_starosta(message):
        await message.reply("❌ Немає доступу!")
        return
    args = (message.text or "").split(maxsplit=2)
    if len(args) < 3:
        await message.reply("Формат: <code>/settag @username|user_id ТЕКСТ</code>", parse_mode="HTML")
        return
    tag_text = args[2].strip()
    if not tag_text or len(tag_text) > 16 or any(ord(ch) > 0x2100 for ch in tag_text):
        await message.reply("⚠️ Тег: 1..16 символів, без емодзі.")
        return
    uid = resolve_user_target(message.chat.id, args[1])
    if uid is None:
        await message.reply(f"🙅 Не бачив {args[1]}.")
        return
    ok, err = await try_set_member_tag(message.chat.id, uid, tag_text)
    if not ok:
        await message.reply(f"⚠️ Не вдалось: {err}")
        return
    db_save_user_tag(message.chat.id, uid, "admin", tag_text)
    db_log(message.chat.id, uid, "tag_admin_set", 0, None, f"«{tag_text}»")
    await message.reply(f"✅ Тег «{tag_text}» для {mention_html(message.chat.id, uid)}.", parse_mode="HTML")


@dp.message(Command("userinfo"))
async def cmd_userinfo(message):
    if not await is_admin_owner_or_starosta(message):
        await message.reply("❌ Немає доступу!")
        return
    args = (message.text or "").split()
    if len(args) < 2:
        await message.reply("Формат: <code>/userinfo @username|user_id</code>", parse_mode="HTML")
        return
    uid = resolve_user_target(message.chat.id, args[1])
    if uid is None:
        await message.reply(f"🙅 Не бачив {args[1]}.")
        return
    info = db_get_user_info(message.chat.id, uid)
    name = info["name"] or str(uid)
    wd = get_wheat(message.chat.id, uid)
    lines = [
        f"👤 <b>{html.escape(name)}</b>",
        f"🆔 <code>{uid}</code>",
        f"📛 @{info['username'] or '—'}",
        "", f"💰 Баланс: <b>{info['balance_econ']:,}</b> 🪙",
        f"🏷️ Тег: <b>{info['tag'] or 'немає'}</b>",
        f"💎 Престиж: {get_prestige_level(message.chat.id, uid)}",
        f"🌾 Пшениця: {wd['wheat']:,} т ({wd['plots']} діл., {wd.get('silos',0)} силосів)",
    ]
    await message.reply("\n".join(lines), parse_mode="HTML")


@dp.message(Command("logs"))
async def cmd_logs(message):
    if not await is_admin_owner_or_starosta(message):
        await message.reply("❌ Немає доступу!")
        return
    args = (message.text or "").split()
    limit = 30
    if len(args) > 1:
        try:
            limit = max(5, min(200, int(args[1])))
        except ValueError:
            pass
    rows = db_get_logs(message.chat.id, limit)
    if not rows:
        await message.reply("📜 Логів немає.")
        return
    lines = [f"📜 <b>Останні {len(rows)}</b>\n"]
    for ts, uid, event, amount, bal, details in rows:
        try:
            t = datetime.fromisoformat(ts).strftime("%d.%m %H:%M")
        except Exception:
            t = "?"
        name = get_display_name(message.chat.id, uid)
        sign = f"+{amount}" if amount > 0 else (str(amount) if amount else "")
        bal_str = f" | 👛 {bal}" if bal is not None else ""
        lines.append(f"<code>{t}</code> · <b>{html.escape(name)}</b> · {event} {sign}{bal_str}")
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n…"
    await message.reply(text, parse_mode="HTML")


@dp.message(Command("balances"))
async def cmd_balances(message):
    if not await is_admin_owner_or_starosta(message):
        await message.reply("❌ Немає доступу!")
        return
    rows = db_get_all_balances(message.chat.id)
    if not rows:
        await message.reply("🙅 Ніхто ще не грав.")
        return
    lines = ["💰 <b>Баланси</b>\n"]
    for uid, bal in rows[:50]:
        lines.append(f"{mention_html(message.chat.id, uid)} — <b>{bal:,}</b> 🪙")
    await message.reply("\n".join(lines), parse_mode="HTML")


@dp.message(Command("admin"))
async def cmd_admin(message):
    try:
        if not await is_admin_owner_or_starosta(message):
            await message.reply("❌ Доступ заборонено!")
            return
        await message.reply("⚙️ Панель:", reply_markup=build_admin_keyboard(message.chat.id))
    except Exception as e:
        logging.error(f"admin: {e}")
        await message.reply(f"⚠️ {e}")


@dp.callback_query(F.data == "btn_send_schedule")
async def process_btn_send_schedule(callback, state: FSMContext):
    if not await check_permissions(callback.from_user, callback.message.chat):
        await safe_answer(callback, "❌ Немає доступу!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_schedule_text)
    await callback.message.answer("✍️ Список пар:\n\n<code>1 пара - Укр мова</code>", parse_mode="HTML")
    await safe_answer(callback)


@dp.message(AdminStates.waiting_for_schedule_text, F.text)
async def process_schedule_text(message, state: FSMContext):
    await state.clear()
    subjects = parse_schedule_text(message.text)
    if not subjects:
        await message.reply("⚠️ Формат: <code>1 пара - Укр мова</code>", parse_mode="HTML")
        return
    target_date = determine_target_date(len(subjects))
    result = schedule_lessons_for_date(message.chat.id, subjects, target_date)
    lines = "\n".join(f"  {compute_lesson_time(i)[0]:02d}:{compute_lesson_time(i)[1]:02d} — {s}" for i, s in enumerate(subjects))
    await message.reply(f"✅ Розклад на {target_date.strftime('%d.%m.%Y')}:\n\n{lines}\n\n🔗 {result['with_link']} · 🙅 {result['without_link']}")
    if result["catch_up_lesson"]:
        st, first = result["catch_up_lesson"]
        await send_lesson_ping(message.chat.id, st, first)


@dp.callback_query(F.data == "btn_add_link")
async def process_btn_add_link(callback, state: FSMContext):
    if not await check_permissions(callback.from_user, callback.message.chat):
        await safe_answer(callback, "❌ Немає доступу!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_new_link)
    await callback.message.answer("✍️ <code>Назва предмета | посилання</code>", parse_mode="HTML")
    await safe_answer(callback)


@dp.message(AdminStates.waiting_for_new_link, F.text)
async def process_new_link(message, state: FSMContext):
    await state.clear()
    if "|" not in message.text:
        await message.reply("⚠️ Формат: <code>Назва | посилання</code>", parse_mode="HTML")
        return
    name_part, url_part = message.text.split("|", 1)
    name, url = name_part.strip(), url_part.strip()
    if not name or not (url.startswith("http://") or url.startswith("https://")):
        await message.reply("⚠️ Перевір формат.")
        return
    add_subject_link(name, url)
    await message.reply(f"✅ Додав «{name}»!")


@dp.callback_query(F.data == "btn_toggle_ai")
async def process_btn_toggle_ai(callback):
    if not await check_permissions(callback.from_user, callback.message.chat):
        await safe_answer(callback, "❌ Немає доступу!", show_alert=True)
        return
    chat_id = callback.message.chat.id
    new_state = not ai_chat_enabled.get(chat_id, False)
    ai_chat_enabled[chat_id] = new_state
    db_set_ai_chat(chat_id, new_state)
    await safe_answer(callback, f"ШІ {'увімкнено ✅' if new_state else 'вимкнено ❌'}", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=build_admin_keyboard(chat_id))
    except Exception:
        pass


@dp.callback_query(F.data == "btn_send_quote")
async def process_btn_send_quote(callback):
    if not await check_permissions(callback.from_user, callback.message.chat):
        await safe_answer(callback, "❌ Немає доступу!", show_alert=True)
        return
    await safe_answer(callback, "Генерую...")
    quote = await get_daily_quote()
    tags = build_mentions(callback.message.chat.id)
    try:
        await bot.send_message(callback.message.chat.id, f"{tags}\n\n💬 {quote}", parse_mode="HTML")
    except Exception as e:
        logging.error(f"quote: {e}")


@dp.message(Command("links"))
async def show_links(message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=item["title"], url=item["url"])] for item in SUBJECT_LINKS.values()])
    await message.answer("📚 Посилання А-11:", reply_markup=kb)


# ================= ДУЕЛІ =================
@dp.callback_query(F.data.startswith("dice|"))
async def process_dice_roll(callback):
    parts = callback.data.split("|", 2)
    if len(parts) != 3:
        await safe_answer(callback)
        return
    _, challenge_id, _ = parts
    duel = pending_duels.get(challenge_id)
    if not duel or duel.get("type") != "dice":
        await safe_answer(callback, "Дуель неактуальна.", show_alert=True)
        return
    uid = callback.from_user.id
    if uid not in duel["players"]:
        await safe_answer(callback, "Не твоя дуель!", show_alert=True)
        return
    if uid in duel["rolls"]:
        await safe_answer(callback, "Вже кинув.", show_alert=True)
        return
    duel["rolls"][uid] = random.randint(1, 6)
    await safe_answer(callback, f"🎲 Твій кубик: {duel['rolls'][uid]}", show_alert=True)
    if len(duel["rolls"]) < 2:
        try:
            waiting = [p for p in duel["players"] if p not in duel["rolls"]][0]
            await callback.message.edit_text(f"{callback.message.html_text or callback.message.text}\n\n⏳ {mention_html(duel['chat_id'], waiting)}...",
                                              parse_mode="HTML", reply_markup=build_dice_duel_keyboard(challenge_id))
        except Exception:
            pass
        return
    chat_id = duel["chat_id"]
    bet = duel["bet"]
    a_id, b_id = list(duel["players"])
    ra, rb = duel["rolls"][a_id], duel["rolls"][b_id]
    ea = get_economy(chat_id, a_id)
    eb = get_economy(chat_id, b_id)
    if ra == rb:
        result_text = "🤝 Нічия."
    elif ea["balance"] < bet or eb["balance"] < bet:
        result_text = "⚠️ Забракло 🪙."
    elif ra > rb:
        win = apply_prestige(chat_id, a_id, bet)
        before_a = ea["balance"]
        before_b = eb["balance"]
        ea["balance"] += win; eb["balance"] -= bet
        save_economy(chat_id, a_id); save_economy(chat_id, b_id)
        result_text = f"🏆 {mention_html(chat_id, a_id)}! +{win}"
        db_log(chat_id, a_id, "duel_dice_win", win, ea["balance"], f"vs {b_id}", balance_before=before_a)
        db_log(chat_id, b_id, "duel_dice_lose", -bet, eb["balance"], f"vs {a_id}", balance_before=before_b)
    else:
        win = apply_prestige(chat_id, b_id, bet)
        before_a = ea["balance"]
        before_b = eb["balance"]
        eb["balance"] += win; ea["balance"] -= bet
        save_economy(chat_id, a_id); save_economy(chat_id, b_id)
        result_text = f"🏆 {mention_html(chat_id, b_id)}! +{win}"
        db_log(chat_id, b_id, "duel_dice_win", win, eb["balance"], f"vs {a_id}", balance_before=before_b)
        db_log(chat_id, a_id, "duel_dice_lose", -bet, ea["balance"], f"vs {b_id}", balance_before=before_a)
    pending_duels.pop(challenge_id, None)
    try:
        await callback.message.edit_text(f"🎲 Дуель!\n{mention_html(chat_id, a_id)}: {ra}\n{mention_html(chat_id, b_id)}: {rb}\n{result_text}", parse_mode="HTML")
    except Exception:
        pass


@dp.callback_query(F.data.startswith("rps|"))
async def process_rps_choice(callback):
    parts = callback.data.split("|", 2)
    if len(parts) != 3:
        await safe_answer(callback)
        return
    _, challenge_id, choice = parts
    duel = pending_duels.get(challenge_id)
    if not duel or duel.get("type") != "rps":
        await safe_answer(callback, "Неактуальна.", show_alert=True)
        return
    uid = callback.from_user.id
    if uid not in duel["players"]:
        await safe_answer(callback, "Не твоя дуель!", show_alert=True)
        return
    if uid in duel["choices"]:
        await safe_answer(callback, "Вже обрав.", show_alert=True)
        return
    if choice not in RPS_CHOICES:
        await safe_answer(callback)
        return
    duel["choices"][uid] = choice
    await safe_answer(callback, f"Твій вибір: {RPS_EMOJI[choice]} {choice}", show_alert=True)
    if len(duel["choices"]) < 2:
        try:
            waiting = [p for p in duel["players"] if p not in duel["choices"]][0]
            await callback.message.edit_text(f"{callback.message.html_text or callback.message.text}\n\n⏳ {mention_html(duel['chat_id'], waiting)}...",
                                              parse_mode="HTML", reply_markup=build_rps_keyboard(challenge_id))
        except Exception:
            pass
        return
    chat_id = duel["chat_id"]
    bet = duel["bet"]
    a_id, b_id = list(duel["players"])
    ca, cb_ = duel["choices"][a_id], duel["choices"][b_id]
    ea = get_economy(chat_id, a_id)
    eb = get_economy(chat_id, b_id)
    if ca == cb_:
        result_text = "🤝 Нічия."
    elif ea["balance"] < bet or eb["balance"] < bet:
        result_text = "⚠️ Забракло 🪙."
    elif cb_ in RPS_BEATS[ca]:
        win = apply_prestige(chat_id, a_id, bet)
        before_a = ea["balance"]; before_b = eb["balance"]
        ea["balance"] += win; eb["balance"] -= bet
        save_economy(chat_id, a_id); save_economy(chat_id, b_id)
        result_text = f"🏆 {mention_html(chat_id, a_id)}! +{win}"
        db_log(chat_id, a_id, "duel_rps_win", win, ea["balance"], f"{ca} vs {cb_}", balance_before=before_a)
        db_log(chat_id, b_id, "duel_rps_lose", -bet, eb["balance"], f"{cb_} vs {ca}", balance_before=before_b)
    else:
        win = apply_prestige(chat_id, b_id, bet)
        before_a = ea["balance"]; before_b = eb["balance"]
        eb["balance"] += win; ea["balance"] -= bet
        save_economy(chat_id, a_id); save_economy(chat_id, b_id)
        result_text = f"🏆 {mention_html(chat_id, b_id)}! +{win}"
        db_log(chat_id, b_id, "duel_rps_win", win, eb["balance"], f"{cb_} vs {ca}", balance_before=before_b)
        db_log(chat_id, a_id, "duel_rps_lose", -bet, ea["balance"], f"{ca} vs {cb_}", balance_before=before_a)
    pending_duels.pop(challenge_id, None)
    try:
        await callback.message.edit_text(f"🪨✂️📄🕳️\n{mention_html(chat_id, a_id)}: {RPS_EMOJI[ca]} {ca}\n{mention_html(chat_id, b_id)}: {RPS_EMOJI[cb_]} {cb_}\n{result_text}", parse_mode="HTML")
    except Exception:
        pass


# ================= ГОЛОВНИЙ ОБРОБНИК =================
SCHEDULE_QUERY_RE = re.compile(r"(розклад\w*|пар[аи]\w*|урок\w*|заняст?т\w*|занятт\w*)", re.IGNORECASE)
TOMORROW_RE = re.compile(r"завтр", re.IGNORECASE)
CURRENT_RE = re.compile(r"зараз|поточн|цю\s+пар|цей\s+урок", re.IGNORECASE)
NEXT_RE = re.compile(r"наступн|слідуюч|следующ|дальш", re.IGNORECASE)
LINK_REQUEST_RE = re.compile(r"(силк\w*|посилан\w*|лінк\w*|link\w*)", re.IGNORECASE)
BONUS_RE = re.compile(r"^(бонус|фарм)\b", re.IGNORECASE)
BALANCE_RE = re.compile(r"^(баланс|гаманець)\b", re.IGNORECASE)
SLOTS_RE = re.compile(r"^(крутити|слоти)\b(?:\s+(\d+))?", re.IGNORECASE)
DUEL_DICE_RE = re.compile(r"^дуель\s+@?(\S+)(?:\s+(\d+))?", re.IGNORECASE)
DUEL_RPS_RE = re.compile(r"^(?:цуефа|цуєфа|кнп)\s+@?(\S+)(?:\s+(\d+))?", re.IGNORECASE)
FARM_RE = re.compile(r"^(ферм\w*)", re.IGNORECASE)
TOP_RE = re.compile(r"^(топ|багатії)\b", re.IGNORECASE)
MYTAG_RE = re.compile(r"^(мій\s*тег|який\s*мій\s*тег)\b", re.IGNORECASE)


@dp.message()
async def handle_group_messages(message):
    if not message.text:
        return
    match = NAME_PATTERN.match(message.text)
    if not match:
        return
    rest = message.text[match.end():].strip().lower().replace("’", "'").replace("ʼ", "'").replace("`", "'")
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None

    if rest == "мовчати":
        if user_id:
            muted_users.setdefault(chat_id, set()).add(user_id)
            db_set_muted(chat_id, user_id, True)
        await message.reply("🤫 Блять я думав ми друзі, більше не тегатиму тебе.")
        return
    if rest == "говорити":
        if user_id:
            muted_users.setdefault(chat_id, set()).discard(user_id)
            db_set_muted(chat_id, user_id, False)
        await message.reply("🔊 Ну нарешті, скучив сука? Ладно знову тегатиму.")
        return

    # 🌐 ГОЛОВНА ЗМІНА: "Гусь ферма" → показуємо Web App + кнопку текстової версії
    if FARM_RE.match(rest) and user_id:
        if not has_claimed_starter(chat_id, user_id):
            asyncio.create_task(_grant_and_notify_starter(chat_id, user_id))
        await send_farm_webapp_prompt(chat_id, user_id, message)
        return
    if rest.startswith("магазин") and user_id:
        await send_shop_photo(chat_id, user_id, message)
        return
    if (rest.startswith("ринок") or rest.startswith("маркет")) and user_id:
        await send_market_photo(chat_id, user_id, message)
        return
    if MYTAG_RE.match(rest) and user_id:
        tag_row = db_get_user_tag(chat_id, user_id)
        if tag_row:
            await message.reply(f"🏷️ Твій тег: <b>{tag_row[1]}</b>", parse_mode="HTML")
        else:
            await message.reply("🏷️ Немає тегу. Заглянь у магазин → 🏷️ Титули.")
        return

    if SCHEDULE_QUERY_RE.search(rest):
        today = datetime.now(KYIV_TZ).date()
        if CURRENT_RE.search(rest):
            cur = get_current_lesson(chat_id)
            if cur:
                idx, st = cur
                found = find_subject(st.lower())
                h, m = compute_lesson_time(idx)
                text = f"🔴 Зараз ({h:02d}:{m:02d}): {found['title']}\n🔗 {found['url']}" if found and found.get("url") else f"🔴 Зараз: {st}"
            else:
                text = "🙅 Зараз пари немає."
            await message.reply(text, parse_mode="HTML", disable_web_page_preview=True)
            return
        if NEXT_RE.search(rest):
            nxt = get_next_lesson(chat_id)
            if nxt:
                td, idx, st = nxt
                found = find_subject(st.lower())
                h, m = compute_lesson_time(idx)
                dl = "сьогодні" if td == today else td.strftime('%d.%m.%Y')
                text = f"⏭️ ({dl}, {h:02d}:{m:02d}): {found['title']}\n🔗 {found['url']}" if found and found.get("url") else f"⏭️ ({dl}, {h:02d}:{m:02d}): {st}"
            else:
                text = "🙅 Немає."
            await message.reply(text, parse_mode="HTML", disable_web_page_preview=True)
            return
        if TOMORROW_RE.search(rest):
            td, label = today + timedelta(days=1), "завтра"
        else:
            td, label = today, "сьогодні"
        body = format_schedule_for_date(chat_id, td)
        if body:
            await message.reply(f"📅 {label} ({td.strftime('%d.%m.%Y')}):\n\n{body}", parse_mode="HTML", disable_web_page_preview=True)
        else:
            await message.reply(f"🙅 На {label} розкладу немає.")
        return

    if LINK_REQUEST_RE.search(rest):
        found = find_subject(rest)
        if found and found.get("url"):
            await message.reply(f"🔗 {found['title']}\n{found['url']}", parse_mode="HTML", disable_web_page_preview=True)
        else:
            await message.reply("🙅 Не зрозумів. /links")
        return

    if user_id is None:
        return

    if rest in ("бізнес", "бизнес", "мої бізнеси"):
        await message.reply(render_business_menu(chat_id, user_id), parse_mode="HTML", reply_markup=build_business_kb(user_id, chat_id))
        return
    if rest in ("престиж", "прокачка"):
        await message.reply(render_prestige_menu(chat_id, user_id), parse_mode="HTML", reply_markup=build_prestige_kb(user_id))
        return
    if rest in ("банк", "вклад"):
        await message.reply(render_bank_menu(chat_id, user_id), parse_mode="HTML", reply_markup=build_bank_kb(user_id))
        return
    if rest in ("джекпот", "лотерея", "казино"):
        await message.reply(render_jackpot_menu(chat_id, user_id), parse_mode="HTML", reply_markup=build_jackpot_kb(user_id))
        return
    if rest in ("їжа", "їжa", "норми", "таблиця"):
        await message.reply(render_food_table(), parse_mode="HTML")
        return
    if rest in ("маркетплейс", "барахолка", "оголошення"):
        await message.reply(render_marketplace(chat_id), parse_mode="HTML", reply_markup=build_marketplace_kb(user_id, chat_id))
        return
    if rest in ("робітники", "рабочие"):
        await message.reply(render_workers_menu(chat_id, user_id), parse_mode="HTML", reply_markup=build_workers_kb(user_id, chat_id))
        return
    if rest in ("поле", "пшениця"):
        await message.reply(render_wheat_menu(chat_id, user_id), parse_mode="HTML", reply_markup=build_wheat_kb(user_id))
        return
    if rest in ("набір", "старт", "стартовий", "стартовий набір"):
        claimed = has_claimed_starter(chat_id, user_id)
        if claimed:
            await message.reply("✅ Ти вже отримав стартовий набір раніше.\nКачай ферму, бізнеси і престиж!", parse_mode="HTML")
        else:
            await _grant_and_notify_starter(chat_id, user_id)
            await message.reply("🎁 Нараховую стартовий набір...")
        return

    if user_id:
        sell_m = re.match(r"^(продати|передати|подарувати)\s+(.+)$", rest, re.IGNORECASE)
        if sell_m:
            action_word = sell_m.group(1).lower()
            rest_part = sell_m.group(2).strip()
            target_user = None
            tg = re.match(r"^@?(\S+)\s+(.+)$", rest_part)
            if tg:
                candidate = tg.group(1).lstrip("@")
                uid_cand = resolve_user_by_username(chat_id, candidate)
                if uid_cand:
                    target_user = uid_cand
                    rest_part = tg.group(2).strip()
            tokens = rest_part.split()
            if len(tokens) >= 2:
                try:
                    qty = int(tokens[0])
                except ValueError:
                    await message.reply("⚠️ Формат: <code>Гусь продати [@user] 5 пшеницю [100]</code>", parse_mode="HTML")
                    return
                if qty <= 0:
                    await message.reply("⚠️ Кількість > 0.")
                    return
                item_key = None
                for tok in tokens[1:]:
                    ik = parse_item_name(tok)
                    if ik:
                        item_key = ik
                        break
                price = None
                try:
                    price = int(tokens[-1])
                except ValueError:
                    price = None
                if not item_key:
                    await message.reply("🙅 Не розпізнав предмет.", parse_mode="HTML")
                    return
                have = get_user_item_count(chat_id, user_id, item_key)
                if have < qty:
                    await message.reply(f"🙅 У тебе тільки {have} шт. {SELLABLE_ITEMS[item_key][0]}.")
                    return
                if action_word in ("передати", "подарувати"):
                    if not target_user:
                        await message.reply("🙅 Вкажи @username.")
                        return
                    if target_user == user_id:
                        await message.reply("🙅 Собі?")
                        return
                    if not change_user_item(chat_id, user_id, item_key, -qty):
                        await message.reply("🙅 Не вдалось.")
                        return
                    change_user_item(chat_id, target_user, item_key, qty)
                    db_log(chat_id, user_id, "gift_send", 0, None, f"{qty}x {item_key} → {target_user}")
                    await message.reply(f"🎁 {mention_html(chat_id, user_id)} → {mention_html(chat_id, target_user)}\n{SELLABLE_ITEMS[item_key][0]} ×{qty}", parse_mode="HTML")
                    return
                if target_user:
                    if target_user == user_id:
                        await message.reply("🙅 Собі?")
                        return
                    if price is None or price <= 0:
                        await message.reply("⚠️ Вкажи ціну: <code>Гусь продати @user 5 пшеницю 100</code>", parse_mode="HTML")
                        return
                    tid = create_pending_trade(chat_id, user_id, target_user, item_key, qty, price)
                    total = qty * price
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=f"✅ Купити за {total:,} 🪙", callback_data=f"trade|accept|{tid}")],
                        [InlineKeyboardButton(text="❌ Відмовити", callback_data=f"trade|reject|{tid}")],
                        [InlineKeyboardButton(text="🚫 Скасувати (продавець)", callback_data=f"trade|cancel|{tid}")],
                    ])
                    await message.reply(
                        f"🤝 <b>Пропозиція угоди</b>\n\n"
                        f"Продавець: {mention_html(chat_id, user_id)}\n"
                        f"Покупець: {mention_html(chat_id, target_user)}\n"
                        f"{SELLABLE_ITEMS[item_key][0]} ×{qty}\n"
                        f"Ціна: <b>{price:,}</b> 🪙/шт (всього {total:,})",
                        parse_mode="HTML", reply_markup=kb)
                    return
                if price is None or price <= 0:
                    await message.reply("⚠️ Вкажи ціну: <code>Гусь продати 5 пшеницю 100</code>", parse_mode="HTML")
                    return
                if not change_user_item(chat_id, user_id, item_key, -qty):
                    await message.reply("🙅 Не вдалось виставити.")
                    return
                lid = create_listing(chat_id, user_id, item_key, qty, price)
                db_log(chat_id, user_id, "mkt_list", 0, None, f"#{lid} {qty}x {item_key} @ {price}")
                await message.reply(f"🛍️ <b>Оголошення #{lid} створено!</b>\n\n{SELLABLE_ITEMS[item_key][0]} ×{qty} за <b>{price:,}</b> 🪙/шт", parse_mode="HTML")
                return

    if SLOTS_RE.match(rest):
        m = SLOTS_RE.match(rest)
        bet = int(m.group(2)) if m.group(2) else DEFAULT_SLOT_BET
        if bet <= 0:
            await message.reply("⚠️ Ставка > 0.")
            return
        allowed, wait_sec = check_slot_limit(chat_id, user_id)
        if not allowed:
            mins, secs = divmod(wait_sec, 60)
            await message.reply(f"⏳ Ліміт {SLOT_SPINS_LIMIT}/20 хв. Спробуй через {mins} хв {secs} с.")
            return
        econ = get_economy(chat_id, user_id)
        if econ["balance"] < bet:
            await message.reply(f"🙅 Мало 🪙. Баланс: {econ['balance']}")
            return
        before = econ["balance"]
        result = roll_slot_symbols()
        econ["balance"] -= bet
        base_win, desc, is_quad = calc_slot_base_win(result, bet)
        bonus_text = ""
        total_win = base_win
        if is_quad and base_win > 0 and random.random() < SLOT_BONUS_CHANCE:
            mult = roll_slot_bonus()
            total_win = base_win * mult
            bonus_text = f"\n✨ БОНУС x{mult}! ({base_win} × {mult} = {total_win} 🪙)"
        if total_win > 0:
            total_win = apply_prestige(chat_id, user_id, total_win)
        econ["balance"] += total_win
        save_economy(chat_id, user_id)
        if total_win > 0:
            net = total_win - bet
            ns = f"+{net}" if net >= 0 else f"{net}"
            outcome = f"{desc}{bonus_text}\n💰 {total_win} 🪙 (чистий {ns})"
            db_log(chat_id, user_id, "slot_win", total_win - bet, econ["balance"], f"{' | '.join(result)}", balance_before=before)
        else:
            outcome = f"{desc}\n😢 -{bet} 🪙"
            db_log(chat_id, user_id, "slot_lose", -bet, econ["balance"], f"{' | '.join(result)}", balance_before=before)
        history = slot_spin_history.get((chat_id, user_id), [])
        now_ts = time.time()
        history = [t for t in history if now_ts - t < SLOT_SPINS_WINDOW_SEC]
        left = SLOT_SPINS_LIMIT - len(history)
        await message.reply(f"🎰 {' | '.join(result)}\n{outcome}\n👛 {econ['balance']} 🪙\n🎟️ {max(left, 0)}/{SLOT_SPINS_LIMIT}")
        return

    if BONUS_RE.match(rest):
        econ = get_economy(chat_id, user_id)
        now = datetime.now(KYIV_TZ)
        if econ["last_bonus"]:
            try:
                last_dt = _parse_dt(econ["last_bonus"])
                if last_dt:
                    cooldown = timedelta(hours=BONUS_COOLDOWN_HOURS)
                    elapsed = now - last_dt
                    if elapsed < cooldown:
                        rem = cooldown - elapsed
                        hrs, r = divmod(int(rem.total_seconds()), 3600)
                        mins = r // 60
                        await message.reply(f"⏳ Бонус вже забирав. Наступний через {hrs} год {mins} хв.")
                        return
            except Exception:
                pass
        amount = random.randint(BONUS_MIN, BONUS_MAX)
        before = econ["balance"]
        econ["balance"] += amount
        econ["last_bonus"] = now.isoformat()
        save_economy(chat_id, user_id)
        db_log(chat_id, user_id, "bonus", amount, econ["balance"], "Щоденний бонус", balance_before=before)
        await message.reply(f"🎁 +{amount} 🪙. Баланс: {econ['balance']} 🪙")
        return

    if BALANCE_RE.match(rest):
        econ = get_economy(chat_id, user_id)
        await message.reply(f"👛 Баланс: {econ['balance']:,} 🪙")
        return

    if DUEL_RPS_RE.match(rest):
        m = DUEL_RPS_RE.match(rest)
        tgt = m.group(1)
        bet = int(m.group(2)) if m.group(2) else DEFAULT_DUEL_BET
        opp = resolve_user_target(chat_id, tgt)
        if opp is None or opp == user_id:
            await message.reply("🙅 Некоректний суперник.")
            return
        if bet <= 0:
            await message.reply("⚠️ Ставка > 0.")
            return
        ea = get_economy(chat_id, user_id)
        eb = get_economy(chat_id, opp)
        if ea["balance"] < bet or eb["balance"] < bet:
            await message.reply("🙅 Мало 🪙.")
            return
        cid = new_challenge_id(chat_id)
        pending_duels[cid] = {"type": "rps", "chat_id": chat_id, "players": {user_id, opp}, "bet": bet, "choices": {}}
        await message.reply(f"🪨✂️📄🕳️ {mention_html(chat_id, user_id)} викликає {mention_html(chat_id, opp)} на цуефу! Ставка: {bet} 🪙", parse_mode="HTML", reply_markup=build_rps_keyboard(cid))
        return

    if DUEL_DICE_RE.match(rest):
        m = DUEL_DICE_RE.match(rest)
        tgt = m.group(1)
        bet = int(m.group(2)) if m.group(2) else DEFAULT_DUEL_BET
        opp = resolve_user_target(chat_id, tgt)
        if opp is None or opp == user_id:
            await message.reply("🙅 Некоректний суперник.")
            return
        if bet <= 0:
            await message.reply("⚠️ Ставка > 0.")
            return
        ea = get_economy(chat_id, user_id)
        eb = get_economy(chat_id, opp)
        if ea["balance"] < bet or eb["balance"] < bet:
            await message.reply("🙅 Мало 🪙.")
            return
        cid = new_challenge_id(chat_id)
        pending_duels[cid] = {"type": "dice", "chat_id": chat_id, "players": {user_id, opp}, "bet": bet, "rolls": {}}
        await message.reply(f"🎲 {mention_html(chat_id, user_id)} викликає {mention_html(chat_id, opp)}! Ставка: {bet} 🪙", parse_mode="HTML", reply_markup=build_dice_duel_keyboard(cid))
        return

    if TOP_RE.match(rest):
        entries = [(uid, econ["balance"]) for (cid, uid), econ in economy_cache.items() if cid == chat_id]
        entries.sort(key=lambda x: x[1], reverse=True)
        top = entries[:10]
        if not top:
            await message.reply("🙅 Ніхто ще не грав.")
            return
        medals = ["🥇", "🥈", "🥉"]
        lines = ["🏆 <b>Топ багатіїв</b>\n"]
        for i, (uid, bal) in enumerate(top):
            prefix = medals[i] if i < 3 else f"{i + 1}."
            lines.append(f"{prefix} {mention_html(chat_id, uid)} — {bal:,} 🪙")
        await message.reply("\n".join(lines), parse_mode="HTML")
        return

    if ai_chat_enabled.get(chat_id, False):
        reply = await call_groq(AI_CHAT_SYSTEM_PROMPT, message.text)
        if reply:
            await message.reply(reply)
        else:
            await message.reply("🤖 ШІ недоступний.")


# ================= WEB APP API =================
def verify_telegram_init_data(init_data: str, bot_token: str, max_age_sec: int = 86400):
    if not init_data:
        return None
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None
    recv_hash = parsed.pop("hash", None)
    if not recv_hash:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, recv_hash):
        return None
    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except ValueError:
        return None
    if time.time() - auth_date > max_age_sec:
        return None
    user_raw = parsed.get("user")
    if not user_raw:
        return None
    try:
        return json.loads(user_raw)
    except json.JSONDecodeError:
        return None


def get_web_chat_id():
    cid = db_get_setting("main_chat_id")
    return int(cid) if cid else None


def _json_error(message, status=400):
    return web.json_response({"error": message}, status=status)


@web.middleware
async def cors_middleware(request, handler):
    origin = request.headers.get("Origin", "")
    allow_origin = origin if (origin in WEBAPP_CORS_ORIGINS or "*" in WEBAPP_CORS_ORIGINS) else (WEBAPP_CORS_ORIGINS[0] if WEBAPP_CORS_ORIGINS else "*")
    if request.method == "OPTIONS":
        resp = web.Response(status=204)
    else:
        try:
            resp = await handler(request)
        except web.HTTPException as e:
            resp = e
    resp.headers["Access-Control-Allow-Origin"] = allow_origin
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Vary"] = "Origin"
    return resp


@web.middleware
async def auth_middleware(request, handler):
    if not request.path.startswith("/api/"):
        return await handler(request)
    if request.path == "/api/auth" or request.method == "OPTIONS":
        return await handler(request)
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user = verify_telegram_init_data(init_data, BOT_TOKEN)
    if not user:
        return _json_error("unauthorized: invalid or missing Telegram initData", status=401)
    request["tg_user"] = user
    return await handler(request)


async def api_auth(request):
    try:
        body = await request.json()
    except Exception:
        return _json_error("bad json body")
    init_data = body.get("initData", "")
    user = verify_telegram_init_data(init_data, BOT_TOKEN)
    if not user:
        return _json_error("bad_signature: could not verify Telegram initData", status=401)
    chat_id = get_web_chat_id()
    if chat_id is None:
        return _json_error("bot_not_configured", status=503)
    uid = user["id"]
    first = user.get("first_name", "") or ""
    last = user.get("last_name", "") or ""
    name = (first + " " + last).strip() or str(uid)
    username = (user.get("username") or "").lower() or None
    db_upsert_user_unique(chat_id, uid, name, username)
    db_ensure_user_rows(chat_id, uid)
    is_new = not has_claimed_starter(chat_id, uid)
    if is_new:
        claim_starter_kit(chat_id, uid)
    return web.json_response({
        "ok": True, "chat_id": chat_id, "user_id": uid,
        "name": name, "username": username, "is_new_player": is_new,
    })


def _serialize_farm_state(chat_id, uid):
    farm = get_farm(chat_id, uid)
    farm_collect_v2(farm, datetime.now(KYIV_TZ))
    save_farm(chat_id, uid)
    econ = get_economy(chat_id, uid)
    wheat_collect(chat_id, uid)
    wheat = get_wheat(chat_id, uid)
    workers = list(get_workers(chat_id, uid))
    biz = {k: _biz_get(chat_id, uid, k)["qty"] for k in BUSINESSES}
    tag = db_get_user_tag(chat_id, uid)
    lvl, lvl_name = farm_level_from_xp(farm.get("farm_xp", 0))
    contract = get_active_contract(chat_id, uid)
    return {
        "farm": farm, "economy": {"balance": econ["balance"]},
        "wheat": {**wheat, "capacity": wheat_capacity(chat_id, uid)},
        "workers": workers, "worker_wage_per_hour": get_total_wage_per_hour(chat_id, uid),
        "business": biz, "prestige_level": get_prestige_level(chat_id, uid),
        "tag": tag[1] if tag else None, "level": lvl, "level_name": lvl_name,
        "contract": contract,
    }


async def api_state(request):
    user = request["tg_user"]
    chat_id = get_web_chat_id()
    uid = user["id"]
    if chat_id is None:
        return _json_error("bot_not_configured", status=503)
    return web.json_response(_serialize_farm_state(chat_id, uid))


async def api_action(request):
    user = request["tg_user"]
    chat_id = get_web_chat_id()
    uid = user["id"]
    if chat_id is None:
        return _json_error("bot_not_configured", status=503)
    try:
        body = await request.json()
    except Exception:
        body = {}
    action = body.get("action")
    if action == "plant_potato":
        msg = farm_plant_potato(chat_id, uid, body.get("count"))
    elif action == "collect_farm":
        farm = get_farm(chat_id, uid)
        res = farm_collect_v2(farm, datetime.now(KYIV_TZ))
        save_farm(chat_id, uid)
        msg = "OK" if res["collected"] else "Нема що збирати"
    elif action == "slaughter":
        msg = farm_slaughter_pig(chat_id, uid, int(body.get("count", 1)))
    elif action == "cheese":
        msg = farm_start_cheese(chat_id, uid)
    elif action == "breed":
        msg = farm_start_breeding(chat_id, uid)
    elif action == "raise_chicks":
        msg = farm_raise_chicks(chat_id, uid)
    elif action == "shop_buy":
        msg = apply_purchase(chat_id, uid, body.get("item"), int(body.get("count", 1)))
    elif action == "fulfill_contract":
        msg = try_fulfill_contract(chat_id, uid)
    elif action == "new_contract":
        expire_old_contracts(chat_id, uid)
        if get_active_contract(chat_id, uid):
            msg = "У тебе вже є контракт."
        else:
            create_new_contract(chat_id, uid)
            msg = "Новий контракт створено."
    elif action == "sell_product":
        item = body.get("item")
        count = int(body.get("count", 0))
        if item not in MARKET_PRODUCTS or count <= 0:
            return _json_error("invalid item/count")
        col = FARM_PRODUCT_TO_COLUMN.get(item, item)
        farm = get_farm(chat_id, uid)
        have = farm.get(col, 0)
        if have < count:
            msg = f"У тебе тільки {have}."
        else:
            unit = get_dynamic_price(item, FARM_PRODUCT_PRICE[item])
            gain = apply_prestige(chat_id, uid, unit * count)
            farm[col] = have - count
            save_farm(chat_id, uid)
            before = get_economy(chat_id, uid)["balance"]
            new_bal = db_add_balance(chat_id, uid, gain)
            farm_add_xp(chat_id, uid, 3 * count)
            db_log(chat_id, uid, "sale", gain, new_bal, f"{count}x {item} (web)", balance_before=before)
            msg = f"+{gain} 🪙"
    elif action == "sell_animal":
        item = body.get("item")
        count = int(body.get("count", 0))
        if item not in MARKET_ANIMALS or count <= 0:
            return _json_error("invalid item/count")
        col = FARM_ANIMAL_TO_MARKET_COL.get(item, item)
        farm = get_farm(chat_id, uid)
        have = farm.get(col, 0)
        if have < count:
            msg = f"У тебе тільки {have}."
        else:
            gain = apply_prestige(chat_id, uid, FARM_SELL_PRICE[item] * count)
            farm[col] = have - count
            save_farm(chat_id, uid)
            before = get_economy(chat_id, uid)["balance"]
            new_bal = db_add_balance(chat_id, uid, gain)
            db_log(chat_id, uid, "sale_animal", gain, new_bal, f"{count}x {item} (web)", balance_before=before)
            msg = f"+{gain} 🪙"
    elif action == "hire_worker":
        wkey = body.get("worker")
        if wkey not in WORKERS:
            return _json_error("unknown worker")
        econ = get_economy(chat_id, uid)
        w = WORKERS[wkey]
        if econ["balance"] < w["price"]:
            msg = f"Треба {w['price']} 🪙."
        else:
            before = econ["balance"]
            econ["balance"] -= w["price"]
            save_economy(chat_id, uid)
            hire_worker(chat_id, uid, wkey)
            db_log(chat_id, uid, "worker_hire", -w["price"], econ["balance"], wkey, balance_before=before)
            msg = f"Найнято {w['name']}"
    elif action == "wheat_plant":
        d = get_wheat(chat_id, uid)
        if d["plots"] <= 0:
            msg = "Немає ділянок."
        elif d["planted_count"] > 0:
            msg = "Вже посаджено."
        elif d["wheat_seed"] <= 0:
            msg = "Немає насіння."
        else:
            to_plant = min(d["wheat_seed"], d["plots"])
            d["wheat_seed"] -= to_plant
            d["planted_count"] = to_plant
            d["planted_at"] = datetime.now(KYIV_TZ).isoformat()
            save_wheat(chat_id, uid)
            msg = f"Посаджено {to_plant}×"
    elif action == "wheat_collect":
        collected, wasted, cap = wheat_collect(chat_id, uid)
        msg = f"+{collected} т (втрачено {wasted} т)" if (collected or wasted) else "Ще не дозріло."
    elif action == "wheat_sell_local":
        d = get_wheat(chat_id, uid)
        wheat_collect(chat_id, uid)
        d = get_wheat(chat_id, uid)
        if d["wheat"] <= 0:
            msg = "Немає пшениці."
        else:
            sell = d["wheat"]
            unit = get_dynamic_price("wheat_local", WHEAT_LOCAL_PRICE)
            gain = apply_prestige(chat_id, uid, sell * unit)
            d["wheat"] = 0
            save_wheat(chat_id, uid)
            before = get_economy(chat_id, uid)["balance"]
            new_bal = db_add_balance(chat_id, uid, gain)
            db_log(chat_id, uid, "wheat_sell_local", gain, new_bal, f"{sell}x (web)", balance_before=before)
            msg = f"+{gain} 🪙"
    else:
        return _json_error(f"unknown_action: {action}")
    return web.json_response({"ok": True, "message": str(msg), "state": _serialize_farm_state(chat_id, uid)})


async def api_leaderboard(request):
    chat_id = get_web_chat_id()
    if chat_id is None:
        return _json_error("bot_not_configured", status=503)
    rows = db_get_all_balances(chat_id)[:50]
    out = []
    for uid, bal in rows:
        farm = farm_cache.get((chat_id, uid)) or get_farm(chat_id, uid)
        lvl, lvl_name = farm_level_from_xp(farm.get("farm_xp", 0))
        out.append({"user_id": uid, "name": get_display_name(chat_id, uid),
                    "balance": bal, "level": lvl, "level_name": lvl_name})
    return web.json_response({"leaderboard": out})


async def api_me(request):
    user = request["tg_user"]
    chat_id = get_web_chat_id()
    uid = user["id"]
    if chat_id is None:
        return _json_error("bot_not_configured", status=503)
    info = db_get_user_info(chat_id, uid)
    return web.json_response({
        "user_id": uid, "name": info["name"] or str(uid),
        "username": info["username"], "balance": info["balance_econ"], "tag": info["tag"],
    })


async def set_webapp_menu_button():
    """
    У групах ставимо звичайне меню з командами (щоб не було кнопки "Грати" в чаті),
    а в приватних — залишаємо Web App кнопку через /start.
    """
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logging.info("[WEBAPP] Меню бота → команди")
    except Exception as e:
        logging.warning(f"[WEBAPP] set_chat_menu_button: {e}")


# ================= ЗАГРУЗКА / MAIN =================
def load_state_from_db():
    starosta = db_load_starosta()
    if starosta:
        state_data["starosta_username"] = starosta
    for key, title, url, keyword in db_load_subject_links():
        SUBJECT_LINKS[key] = {"title": title, "url": url, "keywords": [keyword]}
        SUBJECT_LINKS[key]["_patterns"] = [(kw, re.compile(r"\b" + re.escape(kw), re.IGNORECASE)) for kw in SUBJECT_LINKS[key]["keywords"]]
    for chat_id, user_id in db_load_muted():
        muted_users.setdefault(chat_id, set()).add(user_id)
    for chat_id, enabled in db_load_ai_chat():
        ai_chat_enabled[chat_id] = bool(enabled)
    for chat_id, user_id, balance, last_bonus, active_title in db_load_economy():
        economy_cache[(chat_id, user_id)] = {"balance": balance, "last_bonus": last_bonus, "active_title": active_title}
    loaded_user_count = 0
    for row in db_load_users():
        chat_id, user_id, name, username = row[0], row[1], row[2], row[3]
        u_low = (username or "").lower() or None
        chat_users = known_users.setdefault(chat_id, {})
        if u_low:
            for uid2, info2 in chat_users.items():
                if uid2 != user_id and info2.get("username") == u_low:
                    info2["username"] = None
        chat_users[user_id] = {"name": name or str(user_id), "username": u_low}
        loaded_user_count += 1
    logging.info(f"[DB] Користувачів: {loaded_user_count}")
    loaded_farms = 0
    try:
        for row in db_load_farm():
            chat_id, user_id = row[0], row[1]
            f = {}
            for i, col in enumerate(FARM_COLUMNS, start=2):
                v = row[i]
                f[col] = v if col in FARM_DATETIME_COLS else (int(v) if v is not None else 0)
            farm_cache[(chat_id, user_id)] = f
            loaded_farms += 1
    except Exception as e:
        logging.error(f"[DB] farm: {e}")
    logging.info(f"[DB] Ферм: {loaded_farms}")
    schedules = db_load_schedules()
    for chat_id, entry in schedules.items():
        chat_schedules[chat_id] = entry
        schedule_lessons_for_date(chat_id, entry["subjects"], entry["date"], persist=False)
    logging.info(f"[DB] Розклад завантажено")


def check_slot_limit(chat_id, user_id):
    key = (chat_id, user_id)
    now = time.time()
    history = slot_spin_history.get(key, [])
    history = [t for t in history if now - t < SLOT_SPINS_WINDOW_SEC]
    if len(history) >= SLOT_SPINS_LIMIT:
        slot_spin_history[key] = history
        return False, int(SLOT_SPINS_WINDOW_SEC - (now - min(history))) + 1
    history.append(now)
    slot_spin_history[key] = history
    return True, 0


def roll_slot_symbols():
    return random.choices(SLOT_EMOJIS, weights=SLOT_WEIGHTS, k=SLOT_REELS)


def roll_slot_bonus():
    return random.choices(SLOT_BONUS_VALUES, weights=SLOT_BONUS_WEIGHTS, k=1)[0]


def calc_slot_base_win(result, bet):
    counts = {}
    for r in result:
        counts[r] = counts.get(r, 0) + 1
    for emoji, cnt in counts.items():
        if cnt == 4:
            s = SLOT_BY_EMOJI[emoji]
            return int(bet * s["quad_mult"]), f"🎉 ЧОТИРИ {s['name'].upper()}! x{s['quad_mult']}", True
    for emoji, cnt in counts.items():
        if cnt == 3:
            s = SLOT_BY_EMOJI[emoji]
            return int(bet * s["triple_mult"]), f"✨ ТРИ {s['name'].upper()}! x{s['triple_mult']}", False
    return 0, "😢 Не збіглось (треба мінімум 3 однакові)", False


async def main():
    global BOT_USERNAME
    init_db()
    migrate_farm_v2()
    migrate_users_v3()
    migrate_workers_expiry()
    migrate_wheat_silos()
    migrate_logs_v2()
    load_state_from_db()
    scheduler.start()
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    me = await bot.get_me()
    BOT_USERNAME = me.username
    db_mode = "PostgreSQL (Supabase)" if USE_POSTGRES else "SQLite (local file)"
    print(f"🚀 Бот запущено як @{BOT_USERNAME}")
    print(f"🗄️  БД: {db_mode}")
    print(f"👥 Користувачів: {sum(len(v) for v in known_users.values())}")
    print(f"🐄 Ферм: {len(farm_cache)}")

    asyncio.create_task(migrate_starter_to_existing())
    asyncio.create_task(global_events_loop())

    port = int(os.environ.get("PORT", 8080))
    render_url = (os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")

    app = web.Application(middlewares=[cors_middleware, auth_middleware])
    app.router.add_post("/api/auth", api_auth)
    app.router.add_get("/api/state", api_state)
    app.router.add_post("/api/action", api_action)
    app.router.add_get("/api/leaderboard", api_leaderboard)
    app.router.add_get("/api/me", api_me)
    for route in ["/api/auth", "/api/state", "/api/action", "/api/leaderboard", "/api/me"]:
        app.router.add_route("OPTIONS", route, lambda r: web.Response(status=204))

    async def _health(_req):
        return web.Response(text="OK")
    app.router.add_get("/", _health)
    app.router.add_get("/health", _health)

    if render_url:
        webhook_path = "/webhook"
        webhook_url = f"{render_url}{webhook_path}"
        try:
            await bot.set_webhook(url=webhook_url, drop_pending_updates=True,
                                  allowed_updates=dp.resolve_used_update_types())
            logging.info(f"[WEBHOOK] Встановлено: {webhook_url}")
        except Exception as e:
            logging.error(f"[WEBHOOK] Помилка: {e}")
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
        setup_application(app, dp, bot=bot)
    else:
        logging.info("[MODE] RENDER_EXTERNAL_URL не задано → polling")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"[SERVER] Слухає 0.0.0.0:{port}")

    try:
        await set_webapp_menu_button()
    except Exception as e:
        logging.warning(f"[WEBAPP] menu button: {e}")

    if render_url:
        while True:
            await asyncio.sleep(3600)
    else:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
        except Exception:
            pass
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
