import asyncio
import logging
import urllib.parse
import aiohttp
import hashlib
import time
import sys
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.enums import ParseMode, ChatType

# ════════════════════════════════════════════════════════════════
#                     ⚙️ CONFIGURATION
# ════════════════════════════════════════════════════════════════
API_TOKEN     = "8354048442:AAGwTXhT9O3fA4m30ulMkCtEkLmn0_Umil4"
ADMIN_ID      = 8381570120
WELCOME_IMAGE = "https://raw.githubusercontent.com/ApkNebulix/Daroid-AN/refs/heads/main/Img/PixellabShimulXD/pixellab_shimulxd_logo.jpeg"
FIREBASE_URL  = "https://pixellabshimulxd-default-rtdb.firebaseio.com/download_link_psxd.json"

# ── Force Join চ্যানেল লিস্ট ──────────────────────────────────
# প্রতিটি dict: {"username": "@...", "url": "https://t.me/..."}
CHANNELS = [
    {"username": "@FreePLPFileShareCommunityXD",  "url": "https://t.me/FreePLPFileShareCommunityXD"},
    {"username": "@PixellabShimulXDChat",          "url": "https://t.me/PixellabShimulXDChat"},
    {"username": "@PixellabShimulXD",              "url": "https://t.me/PixellabShimulXD"},
    {"username": "@HunterGraphicsDesign",          "url": "https://t.me/HunterGraphicsDesign"},
    {"username": "@ShimulGraphicsBD",              "url": "https://t.me/ShimulGraphicsBD"},
]

# ════════════════════════════════════════════════════════════════
#                     🗄️ DATABASE SETUP
# ════════════════════════════════════════════════════════════════
try:
    encoded_pass = urllib.parse.quote_plus("@%aN%#404%App@")
    MONGO_URI = (
        f"mongodb+srv://apknebulix_modz:{encoded_pass}"
        f"@apknebulix.suopcnt.mongodb.net/?appName=ApkNebulix"
    )
    mongo_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db        = mongo_client['BlutterUltra']
    users_col = db['users']
except Exception as e:
    logging.critical(f"❌ MongoDB সংযোগ ব্যর্থ: {e}")
    sys.exit(1)

bot = Bot(token=API_TOKEN)
dp  = Dispatcher()

# ════════════════════════════════════════════════════════════════
#                     🔒 STATES
# ════════════════════════════════════════════════════════════════
class AdminState(StatesGroup):
    waiting_for_broadcast = State()

# ════════════════════════════════════════════════════════════════
#                    🛡️ SECURITY MIDDLEWARE
# ════════════════════════════════════════════════════════════════
# গ্রুপ / সুপারগ্রুপ থেকে বট রেসপন্ড করবে না
@dp.message.middleware()
async def group_block_middleware(handler, event: Message, data: dict):
    if event.chat and event.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
        return  # গ্রুপে সম্পূর্ণ নিরব
    return await handler(event, data)

@dp.callback_query.middleware()
async def callback_group_block(handler, event: CallbackQuery, data: dict):
    if event.message and event.message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
        return
    return await handler(event, data)

# ════════════════════════════════════════════════════════════════
#                   ✨ HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════

async def typing_effect(chat_id: int, duration: float = 1.2):
    """স্মুথ টাইপিং ইফেক্ট"""
    try:
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(duration)
    except Exception:
        pass


async def is_subscribed(user_id: int) -> tuple[bool, list[dict]]:
    """
    সব চ্যানেল চেক করে। 
    Returns: (all_joined: bool, not_joined_channels: list)
    """
    missing = []
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch["username"], user_id=user_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except Exception:
            missing.append(ch)  # চ্যানেল অ্যাক্সেস না হলে মিস ধরা হবে
    return len(missing) == 0, missing


async def fetch_firebase_link() -> str | None:
    """Firebase থেকে ডাউনলোড লিঙ্ক আনে — retry সহ"""
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                async with session.get(FIREBASE_URL) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        if not data:
                            return None
                        if isinstance(data, dict):
                            if "link" in data:
                                return data["link"]
                            nested = data.get("download_link_psxd")
                            if isinstance(nested, dict):
                                return nested.get("link")
                        if isinstance(data, str):
                            return data
        except Exception as e:
            logging.warning(f"Firebase Fetch attempt {attempt+1} failed: {e}")
            await asyncio.sleep(1.5)
    return None


async def safe_delete(message: types.Message):
    """নিরাপদে মেসেজ ডিলিট"""
    try:
        await message.delete()
    except Exception:
        pass

# ════════════════════════════════════════════════════════════════
#                   🎨 KEYBOARDS (রঙিন বাটন)
# ════════════════════════════════════════════════════════════════

def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # 💎 Download Button — চওড়া একা
    builder.row(
        InlineKeyboardButton(
            text="💎 Download Latest Version 🚀",
            callback_data="get_download_process"
        )
    )
    # 📢 + 💬 একই সারি
    builder.row(
        InlineKeyboardButton(text="📢 Official Channel", url="https://t.me/PixellabShimulXD"),
        InlineKeyboardButton(text="💬 Support Group",    url="https://t.me/PixellabShimulXDChat"),
    )
    if is_admin:
        builder.row(
            InlineKeyboardButton(text="🛠 Admin Control Panel", callback_data="admin_panel")
        )
    return builder.as_markup()


def force_join_kb(missing_channels: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    emojis = ["📢", "💬", "🌟", "🎨", "✨"]
    for i, ch in enumerate(missing_channels):
        emoji = emojis[i % len(emojis)]
        builder.row(
            InlineKeyboardButton(
                text=f"{emoji} Join {ch['username']}",
                url=ch["url"]
            )
        )
    builder.row(
        InlineKeyboardButton(text="✅ Verify Membership", callback_data="verify_sub")
    )
    return builder.as_markup()


def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Broadcast Message",  callback_data="start_broadcast"))
    builder.row(InlineKeyboardButton(text="📊 Total Users",        callback_data="user_stats"))
    builder.row(InlineKeyboardButton(text="🔄 Restart Bot",        callback_data="restart_bot"))
    builder.row(InlineKeyboardButton(text="⬅️ Back to Home",       callback_data="back_to_home"))
    return builder.as_markup()

# ════════════════════════════════════════════════════════════════
#                   📩 HANDLERS — USER
# ════════════════════════════════════════════════════════════════

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = message.from_user

    # ── ১. ইউজার সেভ (upsert) ─────────────────────────────────
    await users_col.update_one(
        {"user_id": user.id},
        {"$setOnInsert": {
            "user_id":  user.id,
            "name":     user.full_name,
            "username": f"@{user.username}" if user.username else "N/A",
            "joined":   datetime.now()
        }},
        upsert=True
    )

    # ── ২. টাইপিং ─────────────────────────────────────────────
    await typing_effect(message.chat.id, 1.0)

    # ── ৩. সাবস্ক্রিপশন চেক ───────────────────────────────────
    all_joined, missing = await is_subscribed(user.id)

    if not all_joined:
        caption = (
            f"👋 <b>হ্যালো বন্ধু {user.first_name}!</b>\n\n"
            f"🔒 বটটি ব্যবহার করতে নিচের <b>{len(missing)}টি</b> চ্যানেলে জয়েন করুন।\n"
            f"<i>জয়েন শেষে ✅ Verify বাটনে চাপুন।</i>"
        )
        await message.answer_photo(
            photo=WELCOME_IMAGE,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=force_join_kb(missing)
        )
    else:
        caption = (
            f"❝ <b>Pixellab - ShimulXD</b> | এডভান্স ফিচার সমৃদ্ধ শক্তিশালী ডিজাইন অ্যাপ ❞\n\n"
            f"👋 <b>স্বাগতম বন্ধু {user.first_name}!</b>\n\n"
            f"🚀 <b>নিচের বাটন থেকে সরাসরি লেটেস্ট ভার্সন ডাউনলোড করে নিন।</b>"
        )
        await message.answer_photo(
            photo=WELCOME_IMAGE,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_kb(user.id == ADMIN_ID)
        )


@dp.callback_query(F.data == "verify_sub")
async def cb_verify_sub(callback: CallbackQuery):
    await typing_effect(callback.message.chat.id, 0.6)
    all_joined, missing = await is_subscribed(callback.from_user.id)

    if all_joined:
        await callback.answer("✅ ভেরিফিকেশন সফল! স্বাগতম!", show_alert=False)
        await safe_delete(callback.message)
        user    = callback.from_user
        caption = (
            f"❝ <b>Pixellab - ShimulXD</b> ❞\n\n"
            f"✅ <b>ধন্যবাদ বন্ধু!</b> ভেরিফিকেশন সফল হয়েছে।\n"
            f"🚀 এখন ডাউনলোড বাটন ব্যবহার করুন।"
        )
        await callback.message.answer_photo(
            photo=WELCOME_IMAGE,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_kb(user.id == ADMIN_ID)
        )
    else:
        names = ", ".join(ch["username"] for ch in missing)
        await callback.answer(
            f"⚠️ এখনও জয়েন করা হয়নি:\n{names}",
            show_alert=True
        )


@dp.callback_query(F.data == "get_download_process")
async def cb_download(callback: CallbackQuery):
    # সাবস্ক্রিপশন রি-চেক
    all_joined, missing = await is_subscribed(callback.from_user.id)
    if not all_joined:
        await callback.answer("⚠️ আগে সব চ্যানেলে জয়েন করুন!", show_alert=True)
        return

    await callback.answer("🔍 ফাইলটি খোঁজা হচ্ছে...", show_alert=False)
    await typing_effect(callback.message.chat.id, 1.8)

    live_link = await fetch_firebase_link()

    if live_link:
        dl_builder = InlineKeyboardBuilder()
        dl_builder.row(
            InlineKeyboardButton(text="⚡ DOWNLOAD NOW ⚡", url=live_link)
        )
        dl_builder.row(
            InlineKeyboardButton(text="🔙 Back", callback_data="back_to_home_inline")
        )
        await callback.message.answer(
            f"✨ <b>আপনার ফাইলটি প্রস্তুত বন্ধু!</b>\n\n"
            f"নিচের <b>⚡ Download Now</b> বাটনে ক্লিক করলে সরাসরি ডাউনলোড শুরু হবে।\n\n"
            f"<i>সমস্যা হলে Support Group-এ জানান।</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=dl_builder.as_markup()
        )
    else:
        await callback.answer("❌ Firebase Link পাওয়া যাচ্ছে না!", show_alert=True)
        await callback.message.answer(
            "⚠️ <b>দুঃখিত বন্ধু!</b>\n\nসার্ভার থেকে লিঙ্ক পাওয়া যাচ্ছে না।\n"
            "একটু পরে আবার চেষ্টা করুন অথবা এডমিনকে জানান।",
            parse_mode=ParseMode.HTML
        )


@dp.callback_query(F.data == "back_to_home_inline")
async def cb_back_inline(callback: CallbackQuery):
    """ডাউনলোড মেসেজ থেকে হোমে ফেরা"""
    await safe_delete(callback.message)
    user    = callback.from_user
    caption = (
        f"❝ <b>Pixellab - ShimulXD</b> ❞\n\n"
        f"👋 <b>স্বাগতম বন্ধু {user.first_name}!</b>\n\n"
        f"🚀 নিচের বাটন থেকে ডাউনলোড করুন।"
    )
    await callback.message.answer_photo(
        photo=WELCOME_IMAGE,
        caption=caption,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(user.id == ADMIN_ID)
    )

# ════════════════════════════════════════════════════════════════
#                   🛠️ ADMIN PANEL
# ════════════════════════════════════════════════════════════════

def admin_only(func):
    """এডমিন গার্ড ডেকোরেটর"""
    async def wrapper(callback: CallbackQuery, *args, **kwargs):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("⛔ আপনার অ্যাক্সেস নেই!", show_alert=True)
            return
        return await func(callback, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


@dp.callback_query(F.data == "admin_panel")
@admin_only
async def cb_admin_panel(callback: CallbackQuery):
    try:
        await callback.message.edit_caption(
            caption=(
                "🛠 <b>Admin Control Panel</b>\n\n"
                "📌 Firebase থেকে ডাউনলোড লিঙ্ক কন্ট্রোল হয়।\n"
                "📢 Broadcast দিয়ে সব ইউজারকে মেসেজ করুন।"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_panel_kb()
        )
    except TelegramBadRequest:
        await callback.answer("Admin panel লোড হয়েছে।")


@dp.callback_query(F.data == "user_stats")
@admin_only
async def cb_user_stats(callback: CallbackQuery):
    count = await users_col.count_documents({})
    await callback.answer(f"📊 মোট রেজিস্টার্ড ইউজার: {count} জন", show_alert=True)


@dp.callback_query(F.data == "restart_bot")
@admin_only
async def cb_restart_bot(callback: CallbackQuery):
    await callback.answer("🔄 বট রিস্টার্ট হচ্ছে...", show_alert=True)
    await callback.message.answer("♻️ <b>Bot restarting...</b>", parse_mode=ParseMode.HTML)
    os.execv(sys.executable, [sys.executable] + sys.argv)


@dp.callback_query(F.data == "start_broadcast")
@admin_only
async def cb_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📢 <b>ব্রডকাস্ট মেসেজটি পাঠান:</b>\n"
        "<i>(ছবি, ভিডিও, টেক্সট সব কিছুই পাঠানো যাবে)</i>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminState.waiting_for_broadcast)


@dp.message(AdminState.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.clear()
        return

    status_msg = await message.answer("⏳ <b>ব্রডকাস্ট শুরু হচ্ছে...</b>", parse_mode=ParseMode.HTML)
    success = failed = 0

    async for user in users_col.find({}):
        try:
            await bot.copy_message(
                chat_id=user["user_id"],
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            success += 1
        except TelegramForbiddenError:
            failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # Flood control

    await status_msg.edit_text(
        f"✅ <b>ব্রডকাস্ট সম্পন্ন!</b>\n\n"
        f"🟢 সফল: <b>{success}</b>\n"
        f"🔴 ব্যর্থ: <b>{failed}</b>",
        parse_mode=ParseMode.HTML
    )
    await state.clear()


@dp.callback_query(F.data == "back_to_home")
async def cb_back_home(callback: CallbackQuery):
    await safe_delete(callback.message)
    user    = callback.from_user
    caption = (
        f"❝ <b>Pixellab - ShimulXD</b> ❞\n\n"
        f"👋 <b>স্বাগতম বন্ধু {user.first_name}!</b>"
    )
    await callback.message.answer_photo(
        photo=WELCOME_IMAGE,
        caption=caption,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(user.id == ADMIN_ID)
    )

# ════════════════════════════════════════════════════════════════
#                  🚀 BOT STARTUP / SHUTDOWN
# ════════════════════════════════════════════════════════════════

async def on_startup():
    logging.info("✅ MongoDB সংযোগ পরীক্ষা করা হচ্ছে...")
    await mongo_client.admin.command("ping")
    logging.info("✅ MongoDB সংযুক্ত!")
    logging.info("🚀 Pixellab ShimulXD Bot চালু হয়েছে!")

    # এডমিনকে স্টার্টআপ নোটিফিকেশন
    try:
        await bot.send_message(
            ADMIN_ID,
            "✅ <b>Bot সফলভাবে চালু হয়েছে!</b>\n"
            f"🕐 সময়: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass


async def on_shutdown():
    logging.info("⛔ Bot বন্ধ হচ্ছে...")
    await bot.session.close()


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("bot.log", encoding="utf-8")
        ]
    )

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(
        bot,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot বন্ধ করা হয়েছে।")
