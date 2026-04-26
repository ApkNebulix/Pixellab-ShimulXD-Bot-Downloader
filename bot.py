import asyncio
import logging
import urllib.parse
import aiohttp
import time
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.enums import ParseMode

# --- CONFIGURATION ---
API_TOKEN = "8354048442:AAGwTXhT9O3fA4m30ulMkCtEkLmn0_Umil4"
ADMIN_ID = 8381570120

# ডায়নামিক চ্যানেল ও গ্রুপ লিস্ট (URL এবং Username)
REQUIRED_CHANNELS = [
    {"name": "Hunter Graphics", "url": "https://t.me/HunterGraphicsDesign", "username": "@HunterGraphicsDesign"},
    {"name": "Shimul Graphics", "url": "https://t.me/ShimulGraphicsBD", "username": "@ShimulGraphicsBD"},
    {"name": "Free PLP Share", "url": "https://t.me/FreePLPFileShareCommunityXD", "username": "@FreePLPFileShareCommunityXD"},
    {"name": "Pixellab Chat", "url": "https://t.me/PixellabShimulXDChat", "username": "@PixellabShimulXDChat"},
    {"name": "Pixellab Channel", "url": "https://t.me/PixellabShimulXD", "username": "@PixellabShimulXD"}
]

WELCOME_IMAGE = "https://raw.githubusercontent.com/ApkNebulix/Daroid-AN/refs/heads/main/Img/PixellabShimulXD/pixellab_shimulxd_logo.jpeg"
FIREBASE_URL = "https://pixellabshimulxd-default-rtdb.firebaseio.com/download_link_psxd.json"

# --- DATABASE SETUP ---
try:
    encoded_pass = urllib.parse.quote_plus("@%aN%#404%App@")
    MONGO_URI = f"mongodb+srv://apknebulix_modz:{encoded_pass}@apknebulix.suopcnt.mongodb.net/?appName=ApkNebulix"
    client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['BlutterUltra']
    users_col = db['users']
except Exception as e:
    logging.error(f"❌ DB Error: {e}")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- SECURITY: ANTI-SPAM MIDDLEWARE ---
user_cooldowns = {}
class ThrottlingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        now = time.time()
        # ১ সেকেন্ডের মধ্যে ডাবল ক্লিক করলে ইগনোর করবে
        if user_id in user_cooldowns and now - user_cooldowns[user_id] < 1.5:
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ একটু অপেক্ষা করুন...", show_alert=False)
            return
        user_cooldowns[user_id] = now
        return await handler(event, data)

dp.message.middleware(ThrottlingMiddleware())
dp.callback_query.middleware(ThrottlingMiddleware())

# --- STATES ---
class AdminState(StatesGroup):
    waiting_for_broadcast = State()

# --- HELPER FUNCTIONS ---
async def apply_typing(chat_id, duration=1.2):
    """স্মুথ টাইপিং এনিমেশন ইফেক্ট"""
    try:
        await bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(duration)
    except Exception:
        pass

async def is_subscribed(user_id):
    """ফোর্স জয়েন ভেরিফিকেশন (নতুন লিস্ট অনুযায়ী)"""
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel["username"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

async def fetch_firebase_link():
    """Firebase থেকে ডাউনলোড লিংক সংগ্রহ"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FIREBASE_URL, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if not data: return None
                    if isinstance(data, dict):
                        if "link" in data: return data["link"]
                        elif "download_link_psxd" in data: return data["download_link_psxd"].get("link")
    except Exception as e:
        logging.error(f"Firebase Fetch Error: {e}")
    return None

# --- KEYBOARDS ---
def main_menu_kb(is_admin=False):
    builder = InlineKeyboardBuilder()
    # কালারফুল ইমোজি দিয়ে বাটনের গুরুত্ব বোঝানো হয়েছে
    builder.row(InlineKeyboardButton(text="💎 Download Latest Version 🚀", callback_data="get_download_process"))
    builder.row(
        InlineKeyboardButton(text="🔵 Official Channel", url="https://t.me/PixellabShimulXD"),
        InlineKeyboardButton(text="🟢 Support Group", url="https://t.me/PixellabShimulXDChat")
    )
    if is_admin:
        builder.row(InlineKeyboardButton(text="🛠 Admin Control Panel 🔴", callback_data="admin_panel"))
    return builder.as_markup()

def force_join_kb():
    builder = InlineKeyboardBuilder()
    for ch in REQUIRED_CHANNELS:
        builder.row(InlineKeyboardButton(text=f"📢 Join {ch['name']}", url=ch["url"]))
    builder.row(InlineKeyboardButton(text="✅ Verify Membership 🟢", callback_data="verify_sub"))
    return builder.as_markup()

# --- HANDLERS (Private Chat Only) ---

# F.chat.type == "private" এর মাধ্যমে গ্রুপ ডিটেকশন বন্ধ করা হয়েছে
@dp.message(Command("start"), F.chat.type == "private")
async def start_cmd(message: types.Message):
    user = message.from_user
    # Save User
    if not await users_col.find_one({"user_id": user.id}):
        await users_col.insert_one({
            "user_id": user.id, "name": user.full_name,
            "username": f"@{user.username}" if user.username else "N/A",
            "date": datetime.now()
        })

    await apply_typing(message.chat.id)
    
    if not await is_subscribed(user.id):
        caption = (
            f"👋 <b>হ্যালো বন্ধু {user.first_name}!</b>\n\n"
            f"বটটি ব্যবহার করতে আমাদের নিচের চ্যানেলগুলোতে জয়েন থাকতে হবে।\n"
            f"<i>ভেরিফাই না করলে ডাউনলোড বাটন কাজ করবে না বন্ধু।</i>"
        )
        await message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=force_join_kb())
    else:
        caption = (
            f"❝ <b>Pixellab - ShimulXD</b> | এডভান্স ফিচার সমৃদ্ধ শক্তিশালী ডিজাইন অ্যাপ ❞\n\n"
            f"👋 <b>স্বাগতম বন্ধু {user.first_name}!</b>\n\n"
            f"🚀 <b>নিচের বাটন থেকে সরাসরি লেটেস্ট ভার্সন ডাউনলোড করে নিন।</b>"
        )
        await message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(user.id == ADMIN_ID))

@dp.callback_query(F.data == "verify_sub", F.message.chat.type == "private")
async def verify_sub(callback: CallbackQuery):
    await apply_typing(callback.message.chat.id, 0.5)
    if await is_subscribed(callback.from_user.id):
        await callback.answer("✅ ভেরিফিকেশন সফল!", show_alert=False)
        await callback.message.delete()
        caption = f"❝ <b>Pixellab - ShimulXD</b> ❞\n\n✅ <b>ধন্যবাদ বন্ধু!</b> আপনার ভেরিফিকেশন সফল হয়েছে।"
        await callback.message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(callback.from_user.id == ADMIN_ID))
    else:
        await callback.answer("⚠️ বন্ধু, আগে সব চ্যানেলে জয়েন করুন!", show_alert=True)

@dp.callback_query(F.data == "get_download_process", F.message.chat.type == "private")
async def get_download_process(callback: CallbackQuery):
    """লিঙ্ক খোঁজা এবং স্মুথ এনিমেশন"""
    await callback.answer()
    
    # এনিমেটেড টেক্সট ইফেক্ট
    msg = await callback.message.answer("🔍 <i>সার্ভারের সাথে কানেক্ট করা হচ্ছে...</i>", parse_mode=ParseMode.HTML)
    await asyncio.sleep(0.8)
    await msg.edit_text("🔄 <i>ডাটাবেস থেকে ফাইল খোঁজা হচ্ছে...</i>", parse_mode=ParseMode.HTML)
    await asyncio.sleep(0.8)
    
    live_link = await fetch_firebase_link()
    
    if live_link:
        dl_builder = InlineKeyboardBuilder()
        dl_builder.row(InlineKeyboardButton(text="📥 DOWNLOAD NOW 🚀", url=live_link))
        
        await msg.edit_text(
            f"✨ <b>আপনার ফাইলটি প্রস্তুত বন্ধু!</b>\n\n"
            f"নিচের <b>Download Now</b> বাটনে ক্লিক করলে সরাসরি আপনার ব্রাউজারে ডাউনলোড শুরু হবে।",
            parse_mode=ParseMode.HTML,
            reply_markup=dl_builder.as_markup()
        )
    else:
        await msg.edit_text("⚠️ <b>দুঃখিত বন্ধু!</b> সার্ভার থেকে লিঙ্কটি পাওয়া যাচ্ছে না। এডমিনকে জানান।", parse_mode=ParseMode.HTML)

# --- ADMIN PANEL ---
@dp.callback_query(F.data == "admin_panel", F.message.chat.type == "private")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Broadcast", callback_data="start_broadcast"))
    builder.row(InlineKeyboardButton(text="📊 Total Users", callback_data="user_stats"))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_home"))
    
    await callback.message.edit_caption(
        caption="🛠 <b>এডমিন প্যানেল</b>\n\nডাউনলোড লিঙ্ক এখন সরাসরি Firebase থেকে কন্ট্রোল হয়।",
        parse_mode=ParseMode.HTML,
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "user_stats")
async def user_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    count = await users_col.count_documents({})
    await callback.answer(f"📊 মোট ইউজার: {count} জন", show_alert=True)

@dp.callback_query(F.data == "start_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("📢 <b>ব্রডকাস্ট মেসেজটি দিন:</b>", parse_mode=ParseMode.HTML)
    await state.set_state(AdminState.waiting_for_broadcast)

@dp.message(AdminState.waiting_for_broadcast, F.chat.type == "private")
async def process_broadcast(message: types.Message, state: FSMContext):
    users = users_col.find({})
    success, failed = 0, 0
    msg = await message.answer("⏳ <b>প্রসেসিং...</b>", parse_mode=ParseMode.HTML)
    
    async for user in users:
        try:
            await bot.copy_message(chat_id=user['user_id'], from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
            await asyncio.sleep(0.05)
        except Exception: failed += 1
            
    await msg.edit_text(f"✅ সম্পন্ন!\n🟢 সফল: {success}\n🔴 ব্যর্থ: {failed}")
    await state.clear()

@dp.callback_query(F.data == "back_to_home")
async def back_to_home(callback: CallbackQuery):
    await callback.message.delete()
    caption = "❝ <b>Pixellab - ShimulXD</b> ❞\n\n👋 <b>স্বাগতম বন্ধু!</b>"
    await callback.message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(callback.from_user.id == ADMIN_ID))

# --- RUN ---
async def main():
    logging.basicConfig(level=logging.INFO)
    print("🚀 Bot with Anti-Spam & Group Protection is Ready!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
