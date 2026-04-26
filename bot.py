import asyncio
import logging
import urllib.parse
import aiohttp
import signal
import sys
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, BotCommand
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.enums import ParseMode, ChatType
from aiogram.middlewares.base import BaseMiddleware

# ══════════════════════════════════════════════
#              CONFIGURATION
# ══════════════════════════════════════════════
API_TOKEN     = "8354048442:AAGwTXhT9O3fA4m30ulMkCtEkLmn0_Umil4"
ADMIN_ID      = 8381570120
WELCOME_IMAGE = "https://raw.githubusercontent.com/ApkNebulix/Daroid-AN/refs/heads/main/Img/PixellabShimulXD/pixellab_shimulxd_logo.jpeg"
FIREBASE_URL  = "https://pixellabshimulxd-default-rtdb.firebaseio.com/download_link_psxd.json"

# ফোর্স জয়েন চ্যানেল / গ্রুপ লিস্ট
CHANNELS = [
    {"id": "@FreePLPFileShareCommunityXD", "url": "https://t.me/FreePLPFileShareCommunityXD", "label": "📢 Channel 1"},
    {"id": "@PixellabShimulXDChat",        "url": "https://t.me/PixellabShimulXDChat",        "label": "💬 Group 2"},
    {"id": "@PixellabShimulXD",            "url": "https://t.me/PixellabShimulXD",            "label": "📢 Channel 3"},
    {"id": "@HunterGraphicsDesign",        "url": "https://t.me/HunterGraphicsDesign",        "label": "🎨 Channel 4"},
    {"id": "@ShimulGraphicsBD",            "url": "https://t.me/ShimulGraphicsBD",            "label": "🖼️ Channel 5"},
]

# ══════════════════════════════════════════════
#              DATABASE SETUP
# ══════════════════════════════════════════════
try:
    encoded_pass = urllib.parse.quote_plus("@%aN%#404%App@")
    MONGO_URI = (
        f"mongodb+srv://apknebulix_modz:{encoded_pass}"
        f"@apknebulix.suopcnt.mongodb.net/?appName=ApkNebulix"
    )
    mongo_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db           = mongo_client["BlutterUltra"]
    users_col    = db["users"]
    logs_col     = db["activity_logs"]
    logging.info("✅ MongoDB Connected")
except Exception as e:
    logging.critical(f"❌ DB Connection Error: {e}")
    sys.exit(1)

bot = Bot(token=API_TOKEN)
dp  = Dispatcher()

# ══════════════════════════════════════════════
#  PRIVATE-ONLY MIDDLEWARE
#  গ্রুপ / সুপারগ্রুপ / চ্যানেলে বট নীরব থাকবে
# ══════════════════════════════════════════════
class PrivateOnlyMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message):
            if event.chat.type != ChatType.PRIVATE:
                return  # গ্রুপে কোনো রেসপন্স নয়
        if isinstance(event, types.CallbackQuery):
            if event.message and event.message.chat.type != ChatType.PRIVATE:
                await event.answer("⚠️ এই বটটি শুধুমাত্র প্রাইভেট চ্যাটে কাজ করে।", show_alert=True)
                return
        return await handler(event, data)

dp.message.middleware(PrivateOnlyMiddleware())
dp.callback_query.middleware(PrivateOnlyMiddleware())

# ══════════════════════════════════════════════
#            STATES
# ══════════════════════════════════════════════
class AdminState(StatesGroup):
    waiting_for_broadcast = State()

# ══════════════════════════════════════════════
#            HELPER FUNCTIONS
# ══════════════════════════════════════════════

async def apply_typing(chat_id: int, duration: float = 1.2):
    """স্মুথ টাইপিং অ্যানিমেশন"""
    try:
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(duration)
    except Exception:
        pass


async def is_subscribed(user_id: int):
    """
    প্রতিটি চ্যানেল / গ্রুপ যাচাই করে।
    Returns: (all_joined: bool, missing_channels: list)
    """
    missing = []
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch["id"], user_id=user_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except Exception:
            missing.append(ch)
    return (len(missing) == 0), missing


async def fetch_firebase_link():
    """Firebase থেকে ডাউনলোড লিঙ্ক আনে"""
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
                            inner = data["download_link_psxd"]
                            return inner.get("link") if isinstance(inner, dict) else inner
                    if isinstance(data, str):
                        return data
    except asyncio.TimeoutError:
        logging.warning("Firebase Fetch Timeout")
    except Exception as e:
        logging.error(f"Firebase Fetch Error: {e}")
    return None


async def save_user(user: types.User):
    """ইউজার সেভ / আপডেট করে"""
    try:
        existing = await users_col.find_one({"user_id": user.id})
        if not existing:
            await users_col.insert_one({
                "user_id":   user.id,
                "name":      user.full_name,
                "username":  f"@{user.username}" if user.username else "N/A",
                "joined":    datetime.now(),
                "last_seen": datetime.now(),
                "blocked":   False,
            })
        else:
            await users_col.update_one(
                {"user_id": user.id},
                {"$set": {
                    "last_seen": datetime.now(),
                    "name": user.full_name,
                    "blocked": False,
                }}
            )
    except Exception as e:
        logging.error(f"Save User Error: {e}")


async def log_activity(user_id: int, action: str):
    """অ্যাক্টিভিটি লগ"""
    try:
        await logs_col.insert_one({
            "user_id": user_id,
            "action":  action,
            "time":    datetime.now(),
        })
    except Exception:
        pass


# ══════════════════════════════════════════════
#            KEYBOARDS
# ══════════════════════════════════════════════

def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text="💎 Download Latest Version 🚀",
        callback_data="get_download_process"
    ))
    b.row(
        InlineKeyboardButton(text="📢 Official Channel", url="https://t.me/PixellabShimulXD"),
        InlineKeyboardButton(text="💬 Support Group",    url="https://t.me/PixellabShimulXDChat"),
    )
    b.row(
        InlineKeyboardButton(text="🎨 Hunter Graphics",  url="https://t.me/HunterGraphicsDesign"),
        InlineKeyboardButton(text="🖼️ Shimul Graphics",  url="https://t.me/ShimulGraphicsBD"),
    )
    if is_admin:
        b.row(InlineKeyboardButton(text="🛠️ Admin Panel", callback_data="admin_panel"))
    return b.as_markup()


def force_join_kb(missing: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for ch in missing:
        b.row(InlineKeyboardButton(text=f"➕ {ch['label']}", url=ch["url"]))
    b.row(InlineKeyboardButton(
        text="✅ সব জয়েন করেছি — Verify করুন",
        callback_data="verify_sub"
    ))
    return b.as_markup()


def admin_panel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📢 Broadcast Message",   callback_data="start_broadcast"))
    b.row(InlineKeyboardButton(text="📊 Total Users",         callback_data="user_stats"))
    b.row(InlineKeyboardButton(text="🔗 Firebase Guide",      callback_data="firebase_guide"))
    b.row(InlineKeyboardButton(text="⬅️ Back to Home",        callback_data="back_to_home"))
    return b.as_markup()


# ══════════════════════════════════════════════
#             HANDLERS
# ══════════════════════════════════════════════

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    if message.chat.type != ChatType.PRIVATE:
        return  # গ্রুপে কাজ করবে না

    user = message.from_user
    await save_user(user)
    await log_activity(user.id, "start")
    await apply_typing(message.chat.id, 1.0)

    all_joined, missing = await is_subscribed(user.id)

    if not all_joined:
        caption = (
            f"👋 <b>হ্যালো বন্ধু {user.first_name}!</b>\n\n"
            f"🔒 বটটি ব্যবহার করতে নিচের <b>{len(missing)}টি</b> চ্যানেল/গ্রুপে জয়েন করুন।\n\n"
            f"<i>✅ জয়েন করার পর <b>Verify</b> বাটনে ক্লিক করুন।</i>"
        )
        await message.answer_photo(
            photo=WELCOME_IMAGE,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=force_join_kb(missing)
        )
    else:
        caption = (
            f"❝ <b>Pixellab — ShimulXD</b> ❞\n"
            f"<i>অ্যাডভান্স ফিচার সমৃদ্ধ শক্তিশালী ডিজাইন অ্যাপ</i>\n\n"
            f"👋 <b>স্বাগতম বন্ধু {user.first_name}!</b>\n\n"
            f"🚀 নিচের বাটন থেকে সরাসরি <b>লেটেস্ট ভার্সন</b> ডাউনলোড করুন।"
        )
        await message.answer_photo(
            photo=WELCOME_IMAGE,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_kb(user.id == ADMIN_ID)
        )


@dp.callback_query(F.data == "verify_sub")
async def verify_sub(callback: CallbackQuery):
    await apply_typing(callback.message.chat.id, 0.6)
    user = callback.from_user
    all_joined, missing = await is_subscribed(user.id)

    if all_joined:
        await callback.answer("✅ ভেরিফিকেশন সফল!", show_alert=False)
        await log_activity(user.id, "verified")
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        caption = (
            f"❝ <b>Pixellab — ShimulXD</b> ❞\n\n"
            f"✅ <b>ধন্যবাদ {user.first_name} বন্ধু!</b>\n"
            f"ভেরিফিকেশন সম্পন্ন হয়েছে। 🎉"
        )
        await callback.message.answer_photo(
            photo=WELCOME_IMAGE,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_kb(user.id == ADMIN_ID)
        )
    else:
        names = " | ".join(ch["label"] for ch in missing)
        await callback.answer(
            f"⚠️ এখনও {len(missing)}টি বাকি:\n{names}",
            show_alert=True
        )


@dp.callback_query(F.data == "get_download_process")
async def get_download_process(callback: CallbackQuery):
    user = callback.from_user
    all_joined, missing = await is_subscribed(user.id)
    if not all_joined:
        await callback.answer("⚠️ আগে সব চ্যানেলে জয়েন করুন!", show_alert=True)
        return

    await callback.answer("🔍 ফাইল খোঁজা হচ্ছে...", show_alert=False)
    await apply_typing(callback.message.chat.id, 1.5)

    live_link = await fetch_firebase_link()

    if live_link:
        await log_activity(user.id, "download")
        dl = InlineKeyboardBuilder()
        dl.row(InlineKeyboardButton(text="⚡ DOWNLOAD NOW ⚡", url=live_link))
        dl.row(InlineKeyboardButton(text="🏠 Home", callback_data="back_to_home_simple"))
        await callback.message.answer(
            text=(
                f"✨ <b>ফাইল প্রস্তুত বন্ধু!</b>\n\n"
                f"👇 নিচের <b>DOWNLOAD NOW</b> বাটনে ট্যাপ করুন।\n"
                f"<i>⚠️ ডাউনলোড না হলে ভিন্ন ব্রাউজার ব্যবহার করুন।</i>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=dl.as_markup()
        )
    else:
        await callback.answer("❌ সার্ভার থেকে লিঙ্ক পাওয়া যাচ্ছে না!", show_alert=True)
        await callback.message.answer(
            "⚠️ <b>দুঃখিত বন্ধু!</b>\n"
            "Firebase থেকে লিঙ্ক পাওয়া যাচ্ছে না।\n"
            "এডমিনকে জানান: @PixellabShimulXD",
            parse_mode=ParseMode.HTML
        )


# ══════ ADMIN PANEL ══════

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 অ্যাক্সেস নেই!", show_alert=True)
        return
    try:
        await callback.message.edit_caption(
            caption=(
                "🛠️ <b>Admin Control Panel</b>\n\n"
                "🔗 ডাউনলোড লিঙ্ক → Firebase থেকে নিয়ন্ত্রিত\n"
                "নিচের অপশন থেকে কাজ করুন।"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_panel_kb()
        )
    except TelegramBadRequest:
        await callback.message.answer(
            "🛠️ <b>Admin Panel</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_panel_kb()
        )


@dp.callback_query(F.data == "user_stats")
async def user_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫", show_alert=True)
        return
    total = await users_col.count_documents({})
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today = await users_col.count_documents({"joined": {"$gte": today_start}})
    blocked = await users_col.count_documents({"blocked": True})
    await callback.answer(
        f"📊 মোট ইউজার: {total} জন\n"
        f"📅 আজ যোগ দিয়েছে: {today} জন\n"
        f"🚫 বট ব্লক করেছে: {blocked} জন",
        show_alert=True
    )


@dp.callback_query(F.data == "firebase_guide")
async def firebase_guide(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫", show_alert=True)
        return
    await callback.answer(
        "Firebase Console → Realtime DB → download_link_psxd → link\n(value পরিবর্তন করুন)",
        show_alert=True
    )


@dp.callback_query(F.data == "start_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫", show_alert=True)
        return
    await apply_typing(callback.message.chat.id, 0.5)
    await callback.message.answer(
        "📢 <b>ব্রডকাস্ট মেসেজটি পাঠান:</b>\n"
        "<i>(ছবি, ভিডিও, টেক্সট — যেকোনো ধরন)</i>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.waiting_for_broadcast)


@dp.message(AdminState.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.clear()
        return
    await apply_typing(message.chat.id, 0.5)
    status_msg = await message.answer("⏳ <b>ব্রডকাস্ট শুরু হচ্ছে...</b>", parse_mode=ParseMode.HTML)

    success, failed = 0, 0
    async for user in users_col.find({"blocked": {"$ne": True}}):
        try:
            await bot.copy_message(
                chat_id=user["user_id"],
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            success += 1
        except TelegramForbiddenError:
            await users_col.update_one({"user_id": user["user_id"]}, {"$set": {"blocked": True}})
            failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ <b>ব্রডকাস্ট সম্পন্ন!</b>\n\n"
        f"🟢 সফল: <b>{success}</b> জন\n"
        f"🔴 ব্যর্থ: <b>{failed}</b> জন",
        parse_mode=ParseMode.HTML
    )
    await state.clear()


@dp.callback_query(F.data == "back_to_home")
async def back_to_home(callback: CallbackQuery):
    user = callback.from_user
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await apply_typing(callback.message.chat.id, 0.5)
    caption = (
        f"❝ <b>Pixellab — ShimulXD</b> ❞\n\n"
        f"👋 <b>স্বাগতম {user.first_name}!</b>\n"
        f"🚀 নিচের বাটন থেকে ডাউনলোড করুন।"
    )
    await callback.message.answer_photo(
        photo=WELCOME_IMAGE,
        caption=caption,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(user.id == ADMIN_ID)
    )


@dp.callback_query(F.data == "back_to_home_simple")
async def back_to_home_simple(callback: CallbackQuery):
    await callback.answer()
    user = callback.from_user
    await apply_typing(callback.message.chat.id, 0.5)
    caption = (
        f"❝ <b>Pixellab — ShimulXD</b> ❞\n\n"
        f"👋 <b>স্বাগতম {user.first_name}!</b>\n"
        f"🚀 নিচের বাটন থেকে ডাউনলোড করুন।"
    )
    await callback.message.answer_photo(
        photo=WELCOME_IMAGE,
        caption=caption,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(user.id == ADMIN_ID)
    )


# ══════ FALLBACK HANDLERS ══════

@dp.callback_query()
async def unknown_callback(callback: CallbackQuery):
    await callback.answer("⚠️ অপরিচিত অ্যাকশন!", show_alert=False)


@dp.message()
async def unknown_message(message: types.Message):
    if message.chat.type != ChatType.PRIVATE:
        return
    await apply_typing(message.chat.id, 0.8)
    await message.answer(
        "❓ <b>আমি এই কমান্ডটি বুঝতে পারিনি।</b>\n"
        "/start লিখে বটটি শুরু করুন।",
        parse_mode=ParseMode.HTML
    )


# ══════════════════════════════════════════════
#        BOT COMMANDS + GRACEFUL SHUTDOWN
# ══════════════════════════════════════════════

async def set_bot_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="বট শুরু করুন"),
    ])


async def graceful_shutdown(sig=None):
    logging.info(f"🛑 Shutdown signal received. Stopping bot...")
    await dp.stop_polling()
    await bot.session.close()
    mongo_client.close()
    logging.info("✅ Bot stopped cleanly.")


# ══════════════════════════════════════════════
#              MAIN RUNNER
# ══════════════════════════════════════════════

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    loop = asyncio.get_event_loop()
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                s, lambda sig=s: asyncio.create_task(graceful_shutdown(sig))
            )
        except NotImplementedError:
            pass  # Windows-এ SignalHandler কাজ নাও করতে পারে

    await set_bot_commands()
    await bot.delete_webhook(drop_pending_updates=True)

    logging.info("🚀 Pixellab ShimulXD Bot is Running!")

    await dp.start_polling(
        bot,
        allowed_updates=["message", "callback_query"],
        close_bot_session=True
    )


if __name__ == "__main__":
    asyncio.run(main())
