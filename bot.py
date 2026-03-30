import logging
import asyncio
import aiosqlite
import aiohttp
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_TOKEN = os.getenv("8672506327:AAG7t6eMuh5V6vVzzwD79Cw5IRlxpt1Ie1Y")
CRYPTO_TOKEN = os.getenv("559689:AAoU9aAM7atuAtFiEpkCnUmJzqSYlYm9ZwC")
ADMIN_ID = 6265881106

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ---------- DATABASE ----------

async def init_db():
    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            bought_basic INTEGER DEFAULT 0,
            bought_pro INTEGER DEFAULT 0
        )
        """)
        await db.commit()

async def add_user(user_id):
    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def has_bought(user_id, product):
    async with aiosqlite.connect("db.sqlite") as db:
        cursor = await db.execute("SELECT bought_basic, bought_pro FROM users WHERE user_id=?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return False
        return row[0] if product == "basic" else row[1]

async def update_purchase(user_id, product):
    async with aiosqlite.connect("db.sqlite") as db:
        if product == "basic":
            await db.execute("UPDATE users SET bought_basic=1 WHERE user_id=?", (user_id,))
        else:
            await db.execute("UPDATE users SET bought_pro=1 WHERE user_id=?", (user_id,))
        await db.commit()

# ---------- GUIDES ----------

BASIC_GUIDE = "📘 БАЗА\n\nУход, стиль, осанка"
PRO_GUIDE = "📗 PRO\n\nСтиль, харизма, общение"

# ---------- UI ----------

def main_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📘 200₽", callback_data="buy_basic"))
    kb.add(InlineKeyboardButton("📗 500₽", callback_data="buy_pro"))
    return kb

# ---------- START ----------

@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await add_user(msg.from_user.id)
    await msg.answer("Выбери:", reply_markup=main_kb())

# ---------- CRYPTO ----------

async def create_invoice(amount, user_id):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    data = {
        "asset": "USDT",
        "amount": amount,
        "payload": str(user_id)
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as resp:
                return await resp.json()
    except:
        return None

# ---------- BUY ----------

@dp.callback_query_handler(lambda c: c.data == "buy_basic")
async def buy_basic(call: types.CallbackQuery):
    invoice = await create_invoice(200, call.from_user.id)
    if not invoice:
        await call.message.answer("Ошибка")
        return

    url = invoice["result"]["pay_url"]
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Оплатить", url=url))
    await call.message.answer("Оплата:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "buy_pro")
async def buy_pro(call: types.CallbackQuery):
    invoice = await create_invoice(500, call.from_user.id)
    if not invoice:
        await call.message.answer("Ошибка")
        return

    url = invoice["result"]["pay_url"]
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Оплатить", url=url))
    await call.message.answer("Оплата:", reply_markup=kb)

# ---------- CHECK PAYMENTS ----------

async def check_payments():
    while True:
        try:
            url = "https://pay.crypt.bot/api/getInvoices"
            headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    data = await resp.json()

                    for inv in data["result"]["items"]:
                        if inv["status"] != "paid":
                            continue

                        user_id = int(inv["payload"])
                        amount = int(float(inv["amount"]))

                        if amount == 200:
                            if not await has_bought(user_id, "basic"):
                                await update_purchase(user_id, "basic")
                                await bot.send_message(user_id, BASIC_GUIDE)

                        elif amount == 500:
                            if not await has_bought(user_id, "pro"):
                                await update_purchase(user_id, "pro")
                                await bot.send_message(user_id, PRO_GUIDE)

        except Exception as e:
            print("Ошибка:", e)

        await asyncio.sleep(15)

# ---------- ADMIN ----------

@dp.message_handler(commands=['admin'])
async def admin(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    await msg.answer("/stats\n/broadcast текст")

@dp.message_handler(commands=['stats'])
async def stats(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect("db.sqlite") as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        users = (await cursor.fetchone())[0]

    await msg.answer(f"{users}")

@dp.message_handler(commands=['broadcast'])
async def broadcast(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return

    text = msg.get_args()

    async with aiosqlite.connect("db.sqlite") as db:
        cursor = await db.execute("SELECT user_id FROM users")
        users = await cursor.fetchall()

    for user in users:
        try:
            await bot.send_message(user[0], text)
        except:
            pass

# ---------- RUN ----------

async def main():
    await init_db()
    asyncio.create_task(check_payments())
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
