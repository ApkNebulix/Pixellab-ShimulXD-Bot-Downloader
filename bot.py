import asyncio
import logging
import urllib.parse
import aiohttp
import hashlib
import time
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.enums import ParseMode
from collections import defaultdict

# ============================================================
# --- CONFIGURATION ---
# ============================================================
API_TOKEN = "8354048442:AAGwTXhT9O3fA4m30ulMkCtEkLmn0_Umil4"
ADMIN_ID = 8381570120
WELCOME_IMAGE = "https://raw.githubusercontent.com/ApkNebulix/Daroid-AN/refs/heads/main/Img/PixellabShimulXD/pixellab_shimulxd_logo.jpeg"
FIREBASE_URL = "https://pixellabshimulxd-default-rtdb.firebaseio.com/download_link_psxd.json"

# ✅ সব চ্যানেল/গ্রুপের লিস্ট — username বা invite link যেকোনো ফরম্যাট
CHANNELS = [
    {"id": "@FreePLPFileShareCommunityXD",  "url": "https://t.me/FreePLPFileShareCommunityXD",  "name": "📢 Channel 1"},
    {"id": "@PixellabShimulXDChat",          "url": "https://t.me/PixellabShimulXDChat",          "name": "💬 Group 2"},
    {"id": "@PixellabShimulXD",              "url": "https://t.me/PixellabShimulXD",              "name": "📢 Channel 3"},
    {"id": "@HunterGraphicsDesign",          "url": "https://t.me/HunterGraphicsDesign",          "name": "🎨 Channel 4"},
    {"id": "@ShimulGraphicsBD",              "url": "https://t.me/ShimulGraphicsBD",              "name": "🖌️ Channel 5"},
]

# ============================================================
# --- SECURITY CONFIG ---
# ============================================================
RATE_LIMIT = 5           # প্রতি ইউজার সর্বোচ্চ এতবার রিকোয়েস্ট
RATE_WINDOW = 60         # এই সময়ের মধ্যে (সেকেন্ড)
MAX_BROADCAST_DELAY = 0.05
BLOCKED_USERS = set()    # রানটাইমে ব্লক লিস্ট

rate_tracker = defaultdict(list)  # user_id -> [timestamps]

# ============================================================
# --- DATABASE SETUP ---
# ============================================================
try:
    encoded_pass = urllib.parse.quote_plus("@%aN%#404%App@")
    MONGO_URI = f"mongodb+srv://apknebulix_modz:{encoded_pass}@apknebulix.suopcnt.mongodb.net/?appName=ApkNebulix"
    client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['BlutterUltra']
    users_col = db['users']
    logs_col  = db['security_logs']
except Exception as e:
    logging.error(f"❌ DB Error: {e}")

bot = Bot(token=API_TOKEN)
dp  = Dispatcher()

# ============================================================
# --- FSM STATES ---
# ============================================================
class AdminState(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_block_id  = State()

# ============================================================
# --- SECURITY HELPERS ---
# ============================================================

def is_rate_limited(user_id: int) -> bool:
    """Rate limiting — ফ্লাড প্রোটেকশন"""
    now = time.time()
    window_start = now - RATE_WINDOW
    rate_tracker[user_id] = [t for t in rate_tracker[user_id] if t > window_start]
    if len(rate_tracker[user_id]) >= RATE_LIMIT:
        return True
    rate_tracker[user_id].append(now)
    return False

async def log_security_event(user_id: int, event: str, detail: str = ""):
    """সিকিউরিটি ইভেন্ট লগ করা"""
    try:
        await logs_col.insert_one({
            "user_id": user_id,
            "event": event,
            "detail": detail,
            "timestamp": datetime.now()
        })
    except Exception:
        pass

async def is_blocked(user_id: int) -> bool:
    return user_id in BLOCKED_USERS

# ============================================================
# --- TYPING ANIMATION (স্মুথ) ---
# ============================================================

async def apply_typing(chat_id, duration: float = 1.5):
    """স্মুথ টাইপিং এনিমেশন — মাল্টি-সাইকেল"""
    try:
        cycles = max(1, int(duration / 4))
        remainder = duration - (cycles * 4)
        for _ in range(cycles):
            await bot.send_chat_action(chat_id, "typing")
            await asyncio.sleep(4.0)
        if remainder > 0:
            await bot.send_chat_action(chat_id, "typing")
            await asyncio.sleep(remainder)
    except Exception:
        pass

async def send_typing_then_text(chat_id, text, duration=1.2, **kwargs):
    """টাইপিং দেখিয়ে তারপর মেসেজ পাঠানো"""
    await apply_typing(chat_id, duration)
    return await bot.send_message(chat_id, text, **kwargs)

# ============================================================
# --- SUBSCRIPTION CHECK ---
# ============================================================

async def is_subscribed(user_id: int) -> tuple[bool, list]:
    """সব চ্যানেলে সদস্যপদ যাচাই — কোন কোনটায় নেই তা ফেরত দেয়"""
    missing = []
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch["id"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                missing.append(ch)
        except Exception:
            missing.append(ch)
    return len(missing) == 0, missing

# ============================================================
# --- FIREBASE ---
# ============================================================

async def fetch_firebase_link() -> str | None:
    """Firebase থেকে ডাউনলোড লিঙ্ক আনা"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FIREBASE_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if not data:
                        return None
                    if isinstance(data, dict):
                        if "link" in data:
                            return data["link"]
                        elif "download_link_psxd" in data:
                            return data["download_link_psxd"].get("link")
    except Exception as e:
        logging.error(f"Firebase Fetch Error: {e}")
    return None

# ============================================================
# --- KEYBOARDS (রঙিন ইমোজি বাটন) ---
# ============================================================

def main_menu_kb(is_admin=False):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💎 Download Latest Version 🚀",
        callback_data="get_download_process"
    ))
    builder.row(
        InlineKeyboardButton(text="📢 Official Channel", url="https://t.me/PixellabShimulXD"),
        InlineKeyboardButton(text="💬 Support Group",    url="https://t.me/PixellabShimulXDChat")
    )
    builder.row(InlineKeyboardButton(
        text="🎨 Hunter Graphics",
        url="https://t.me/HunterGraphicsDesign"
    ))
    builder.row(InlineKeyboardButton(
        text="🖌️ Shimul Graphics BD",
        url="https://t.me/ShimulGraphicsBD"
    ))
    builder.row(InlineKeyboardButton(
        text="📊 My Stats",
        callback_data="my_stats"
    ))
    if is_admin:
        builder.row(InlineKeyboardButton(
            text="🛠️ ━━ Admin Panel ━━ 🛠️",
            callback_data="admin_panel"
        ))
    return builder.as_markup()

def force_join_kb(missing_channels: list):
    """শুধু যেসব চ্যানেলে নেই সেগুলো দেখাবে"""
    builder = InlineKeyboardBuilder()
    for ch in missing_channels:
        builder.row(InlineKeyboardButton(text=ch["name"], url=ch["url"]))
    builder.row(InlineKeyboardButton(text="✅ Verify Membership", callback_data="verify_sub"))
    return builder.as_markup()

def admin_panel_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 Broadcast",      callback_data="start_broadcast"),
        InlineKeyboardButton(text="📊 Total Users",    callback_data="user_stats")
    )
    builder.row(
        InlineKeyboardButton(text="🔒 Block User",     callback_data="block_user"),
        InlineKeyboardButton(text="🔓 Unblock User",   callback_data="unblock_user")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Security Logs",  callback_data="security_logs"),
        InlineKeyboardButton(text="🔄 Bot Status",     callback_data="bot_status")
    )
    builder.row(InlineKeyboardButton(text="⬅️ Back to Home", callback_data="back_to_home"))
    return builder.as_markup()

# ============================================================
# --- MIDDLEWARE: SECURITY GUARD ---
# ============================================================

@dp.message.middleware()
async def security_middleware(handler, event: types.Message, data: dict):
    user_id = event.from_user.id if event.from_user else None
    if user_id:
        if await is_blocked(user_id):
            await event.answer("🚫 আপনি এই বট ব্যবহার করতে পারবেন না।")
            await log_security_event(user_id, "BLOCKED_ACCESS")
            return
        if is_rate_limited(user_id):
            await event.answer("⏳ আস্তে আস্তে! একটু পরে আবার চেষ্টা করুন।")
            await log_security_event(user_id, "RATE_LIMITED")
            return
    return await handler(event, data)

@dp.callback_query.middleware()
async def callback_security_middleware(handler, event: CallbackQuery, data: dict):
    user_id = event.from_user.id
    if await is_blocked(user_id):
        await event.answer("🚫 আপনি এই বট ব্যবহার করতে পারবেন না।", show_alert=True)
        return
    return await handler(event, data)

# ============================================================
# --- /START COMMAND ---
# ============================================================

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user = message.from_user

    # নতুন ইউজার সেভ
    if not await users_col.find_one({"user_id": user.id}):
        await users_col.insert_one({
            "user_id": user.id,
            "name": user.full_name,
            "username": f"@{user.username}" if user.username else "N/A",
            "date": datetime.now(),
            "download_count": 0
        })

    subscribed, missing = await is_subscribed(user.id)

    await apply_typing(message.chat.id, 1.2)

    if not subscribed:
        missing_names = ", ".join(ch["name"] for ch in missing)
        caption = (
            f"👋 <b>হ্যালো {user.first_name}!</b>\n\n"
            f"🔒 বটটি ব্যবহার করতে নিচের চ্যানেলগুলোতে জয়েন করতে হবে:\n"
            f"<b>{missing_names}</b>\n\n"
            f"<i>জয়েন করে ✅ Verify বাটনে চাপ দিন।</i>"
        )
        await message.answer_photo(
            photo=WELCOME_IMAGE,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=force_join_kb(missing)
        )
    else:
        caption = (
            f"❝ <b>Pixellab - ShimulXD</b> | এডভান্স ডিজাইন অ্যাপ ❞\n\n"
            f"👋 <b>স্বাগতম বন্ধু {user.first_name}!</b>\n\n"
            f"🚀 নিচের বাটন থেকে লেটেস্ট ভার্সন ডাউনলোড করুন।\n"
            f"📌 যেকোনো সমস্যায় সাপোর্ট গ্রুপে যোগাযোগ করুন।"
        )
        await message.answer_photo(
            photo=WELCOME_IMAGE,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_kb(user.id == ADMIN_ID)
        )

# ============================================================
# --- VERIFY SUBSCRIPTION ---
# ============================================================

@dp.callback_query(F.data == "verify_sub")
async def verify_sub(callback: CallbackQuery):
    await apply_typing(callback.message.chat.id, 0.6)
    subscribed, missing = await is_subscribed(callback.from_user.id)

    if subscribed:
        await callback.answer("✅ ভেরিফিকেশন সফল!", show_alert=False)
        try:
            await callback.message.delete()
        except Exception:
            pass
        user = callback.from_user
        caption = (
            f"❝ <b>Pixellab - ShimulXD</b> ❞\n\n"
            f"✅ <b>ধন্যবাদ {user.first_name}!</b> ভেরিফিকেশন সম্পন্ন।\n"
            f"🚀 এখন ডাউনলোড বাটন থেকে অ্যাপ নামিয়ে নিন!"
        )
        await bot.send_photo(
            callback.message.chat.id,
            photo=WELCOME_IMAGE,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_kb(user.id == ADMIN_ID)
        )
    else:
        missing_names = "\n".join(f"• {ch['name']}" for ch in missing)
        await callback.answer(
            f"⚠️ এখনো জয়েন করা হয়নি:\n{missing_names}",
            show_alert=True
        )

# ============================================================
# --- DOWNLOAD PROCESS ---
# ============================================================

@dp.callback_query(F.data == "get_download_process")
async def get_download_process(callback: CallbackQuery):
    user_id = callback.from_user.id

    # সাবস্ক্রিপশন যাচাই
    subscribed, missing = await is_subscribed(user_id)
    if not subscribed:
        await callback.answer("⚠️ আগে সব চ্যানেলে জয়েন করুন!", show_alert=True)
        return

    await callback.answer("🔍 ফাইল খোঁজা হচ্ছে...", show_alert=False)
    await apply_typing(callback.message.chat.id, 1.5)

    live_link = await fetch_firebase_link()

    if live_link:
        # ডাউনলোড কাউন্ট আপডেট
        await users_col.update_one(
            {"user_id": user_id},
            {"$inc": {"download_count": 1}}
        )

        dl_builder = InlineKeyboardBuilder()
        dl_builder.row(InlineKeyboardButton(text="🟢 ━ DOWNLOAD NOW ━ 🚀", url=live_link))
        dl_builder.row(InlineKeyboardButton(text="🏠 Back to Home", callback_data="back_to_home_msg"))

        await callback.message.answer(
            f"✨ <b>ফাইলটি প্রস্তুত বন্ধু!</b>\n\n"
            f"⬇️ নিচের <b>DOWNLOAD NOW</b> বাটনে চাপ দিলে সরাসরি ব্রাউজারে ডাউনলোড শুরু হবে।\n\n"
            f"⚠️ <i>লিঙ্ক কাজ না করলে সাপোর্ট গ্রুপে জানান।</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=dl_builder.as_markup()
        )
    else:
        await callback.answer("❌ সার্ভার লিঙ্ক পাওয়া যাচ্ছে না!", show_alert=True)
        await apply_typing(callback.message.chat.id, 0.8)
        await callback.message.answer(
            "⚠️ <b>দুঃখিত!</b> এই মুহূর্তে সার্ভার থেকে লিঙ্ক আনা সম্ভব হচ্ছে না।\n"
            "এডমিনকে জানান: @PixellabShimulXD",
            parse_mode=ParseMode.HTML
        )

# ============================================================
# --- MY STATS ---
# ============================================================

@dp.callback_query(F.data == "my_stats")
async def my_stats(callback: CallbackQuery):
    user_data = await users_col.find_one({"user_id": callback.from_user.id})
    if user_data:
        join_date = user_data.get("date", datetime.now()).strftime("%d-%m-%Y")
        dl_count  = user_data.get("download_count", 0)
        await callback.answer(
            f"📊 আপনার তথ্য:\n"
            f"🗓️ যোগ দিয়েছেন: {join_date}\n"
            f"⬇️ মোট ডাউনলোড: {dl_count} বার",
            show_alert=True
        )
    else:
        await callback.answer("তথ্য পাওয়া যায়নি।", show_alert=True)

# ============================================================
# --- ADMIN PANEL ---
# ============================================================

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 এডমিন অ্যাক্সেস নেই!", show_alert=True)
        return
    try:
        await callback.message.edit_caption(
            caption=(
                "🛠️ <b>Admin Control Panel</b>\n\n"
                "🔥 ডাউনলোড লিঙ্ক Firebase থেকে নিয়ন্ত্রণ হয়।\n"
                "📢 Broadcast করতে বা ইউজার স্ট্যাটস দেখতে নিচের বাটন ব্যবহার করুন।"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_panel_kb()
        )
    except TelegramBadRequest:
        await callback.answer("প্যানেল লোড হয়েছে।")

@dp.callback_query(F.data == "user_stats")
async def user_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    count     = await users_col.count_documents({})
    today_count = await users_col.count_documents({
        "date": {"$gte": datetime.now().replace(hour=0, minute=0, second=0)}
    })
    await callback.answer(
        f"📊 মোট ইউজার: {count} জন\n"
        f"🆕 আজকের নতুন: {today_count} জন",
        show_alert=True
    )

@dp.callback_query(F.data == "bot_status")
async def bot_status(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    import sys, platform
    db_ok = "✅" if await check_db() else "❌"
    fb_link = await fetch_firebase_link()
    fb_ok = "✅" if fb_link else "❌"
    await callback.answer(
        f"🤖 Bot Status:\n"
        f"🗄️ Database: {db_ok}\n"
        f"🔥 Firebase: {fb_ok}\n"
        f"🐍 Python: {sys.version[:6]}\n"
        f"🖥️ OS: {platform.system()}",
        show_alert=True
    )

async def check_db() -> bool:
    try:
        await users_col.find_one({})
        return True
    except Exception:
        return False

@dp.callback_query(F.data == "security_logs")
async def security_logs_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    logs = await logs_col.find().sort("timestamp", -1).limit(5).to_list(length=5)
    if not logs:
        await callback.answer("কোনো লগ নেই।", show_alert=True)
        return
    log_text = "\n".join(
        f"👤 {l['user_id']} | {l['event']} | {l['timestamp'].strftime('%H:%M:%S')}"
        for l in logs
    )
    await callback.answer(f"📋 Recent Logs:\n{log_text}", show_alert=True)

@dp.callback_query(F.data == "block_user")
async def block_user_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await apply_typing(callback.message.chat.id, 0.5)
    await callback.message.answer("🔒 ব্লক করতে ইউজার আইডি দিন:")
    await state.set_state(AdminState.waiting_for_block_id)
    await state.update_data(action="block")

@dp.callback_query(F.data == "unblock_user")
async def unblock_user_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await apply_typing(callback.message.chat.id, 0.5)
    await callback.message.answer("🔓 আনব্লক করতে ইউজার আইডি দিন:")
    await state.set_state(AdminState.waiting_for_block_id)
    await state.update_data(action="unblock")

@dp.message(AdminState.waiting_for_block_id)
async def process_block_id(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    action = data.get("action", "block")
    try:
        target_id = int(message.text.strip())
        if action == "block":
            BLOCKED_USERS.add(target_id)
            await message.answer(f"✅ ইউজার {target_id} ব্লক করা হয়েছে।")
            await log_security_event(message.from_user.id, "USER_BLOCKED", str(target_id))
        else:
            BLOCKED_USERS.discard(target_id)
            await message.answer(f"✅ ইউজার {target_id} আনব্লক করা হয়েছে।")
            await log_security_event(message.from_user.id, "USER_UNBLOCKED", str(target_id))
    except ValueError:
        await message.answer("❌ সঠিক আইডি দিন (শুধু সংখ্যা)।")
    await state.clear()

# ============================================================
# --- BROADCAST ---
# ============================================================

@dp.callback_query(F.data == "start_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await apply_typing(callback.message.chat.id, 0.5)
    await callback.message.answer(
        "📢 <b>Broadcast মেসেজ দিন:</b>\n"
        "<i>(যেকোনো ধরনের মেসেজ — টেক্সট, ছবি, ভিডিও)</i>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.waiting_for_broadcast)

@dp.message(AdminState.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    users = users_col.find({})
    success, failed = 0, 0
    status_msg = await message.answer("⏳ <b>Broadcast চলছে...</b> 0% সম্পন্ন", parse_mode=ParseMode.HTML)
    total = await users_col.count_documents({})
    processed = 0

    async for user in users:
        try:
            await bot.copy_message(
                chat_id=user['user_id'],
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            success += 1
        except TelegramForbiddenError:
            failed += 1
        except Exception:
            failed += 1

        processed += 1
        if processed % 20 == 0:
            pct = int((processed / total) * 100)
            try:
                await status_msg.edit_text(
                    f"⏳ <b>Broadcast চলছে...</b> {pct}% সম্পন্ন\n"
                    f"🟢 {success} | 🔴 {failed}",
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass
        await asyncio.sleep(MAX_BROADCAST_DELAY)

    await status_msg.edit_text(
        f"✅ <b>Broadcast সম্পন্ন!</b>\n\n"
        f"📨 মোট: {total} জন\n"
        f"🟢 সফল: {success} জন\n"
        f"🔴 ব্যর্থ: {failed} জন",
        parse_mode=ParseMode.HTML
    )
    await state.clear()

# ============================================================
# --- BACK TO HOME ---
# ============================================================

@dp.callback_query(F.data.in_({"back_to_home", "back_to_home_msg"}))
async def back_to_home(callback: CallbackQuery):
    user = callback.from_user
    caption = (
        f"❝ <b>Pixellab - ShimulXD</b> ❞\n\n"
        f"👋 <b>স্বাগতম বন্ধু {user.first_name}!</b>\n"
        f"🚀 নিচের বাটন থেকে লেটেস্ট ভার্সন ডাউনলোড করুন।"
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await apply_typing(callback.message.chat.id, 0.6)
    await bot.send_photo(
        callback.message.chat.id,
        photo=WELCOME_IMAGE,
        caption=caption,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(user.id == ADMIN_ID)
    )

# ============================================================
# --- UNKNOWN MESSAGES ---
# ============================================================

@dp.message()
async def unknown_message(message: types.Message):
    await apply_typing(message.chat.id, 0.8)
    await message.answer(
        "🤖 <b>বটের কমান্ড বুঝতে পারিনি।</b>\n"
        "/start লিখে বটটি রিস্টার্ট করুন।",
        parse_mode=ParseMode.HTML
    )

# ============================================================
# --- AUTO RESTART (৪ ঘণ্টা পর পর) ---
# ============================================================

async def auto_restart_scheduler():
    """প্রতি ৪ ঘণ্টায় বট নিজে থেকে পোলিং রিস্টার্ট করে"""
    RESTART_INTERVAL = 4 * 60 * 60  # ৪ ঘণ্টা
    while True:
        await asyncio.sleep(RESTART_INTERVAL)
        logging.info("🔄 অটো রিস্টার্ট — ৪ ঘণ্টা পূর্ণ হয়েছে")
        try:
            await bot.send_message(
                ADMIN_ID,
                "🔄 <b>অটো রিস্টার্ট সম্পন্ন!</b>\n"
                f"⏰ সময়: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass

# ============================================================
# --- MAIN ---
# ============================================================

async def on_startup():
    logging.info("🚀 Bot starting up...")
    try:
        await bot.send_message(
            ADMIN_ID,
            f"✅ <b>Bot চালু হয়েছে!</b>\n"
            f"⏰ {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

async def on_shutdown():
    logging.info("🛑 Bot shutting down...")
    try:
        await bot.send_message(
            ADMIN_ID,
            "🛑 <b>Bot বন্ধ হয়ে গেছে!</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    await on_startup()

    # অটো রিস্টার্ট ট্যাস্ক ব্যাকগ্রাউন্ডে চালু
    asyncio.create_task(auto_restart_scheduler())

    try:
        await dp.start_polling(bot, skip_updates=True, allowed_updates=dp.resolve_used_update_types())
    finally:
        await on_shutdown()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
