import asyncio
import logging
import urllib.parse
import aiohttp
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError
from aiogram.enums import ParseMode

# --- CONFIGURATION ---
API_TOKEN = "8354048442:AAGwTXhT9O3fA4m30ulMkCtEkLmn0_Umil4"
ADMIN_ID = 8381570120
CHANNELS = ["@FreePLPFileShareCommunityXD", "@PixellabShimulXDChat", "@PixellabShimulXD"]
WELCOME_IMAGE = "https://raw.githubusercontent.com/ApkNebulix/Daroid-AN/refs/heads/main/Img/PixellabShimulXD/pixellab_shimulxd_logo.jpeg"
# Firebase URL - সরাসরি JSON এন্ডপয়েন্ট
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

# --- STATES ---
class AdminState(StatesGroup):
    waiting_for_broadcast = State()

# --- FUNCTIONS ---

async def apply_typing(chat_id, duration=1.0):
    """স্মুথ টাইপিং এনিমেশন"""
    try:
        await bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(duration)
    except Exception:
        pass

async def is_subscribed(user_id):
    """ফোর্স জয়েন ভেরিফিকেশন"""
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

async def fetch_live_link():
    """Firebase থেকে নির্ভুলভাবে লিঙ্ক সংগ্রহ (Bug Fixed)"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FIREBASE_URL, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if not data:
                        return None
                    
                    # Firebase সরাসরি ডাটা পাঠালে এভাবে চেক করবে
                    if isinstance(data, dict):
                        # যদি ডাটা { "link": "..." } এই ফরম্যাটে থাকে
                        if "link" in data:
                            return data["link"]
                        # যদি ডাটা { "download_link_psxd": { "link": "..." } } এই ফরম্যাটে থাকে
                        elif "download_link_psxd" in data:
                            return data["download_link_psxd"].get("link")
                    return None
    except Exception as e:
        logging.error(f"Firebase Error: {e}")
        return None

# --- KEYBOARDS ---

def main_menu_kb(is_admin=False):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📥 Download Latest Version 🚀", callback_data="get_download"))
    builder.row(InlineKeyboardButton(text="📢 Join Official Channel", url="https://t.me/PixellabShimulXD"))
    builder.row(InlineKeyboardButton(text="💬 Support Group", url="https://t.me/PixellabShimulXDChat"))
    if is_admin:
        builder.row(InlineKeyboardButton(text="🛠 Admin Control Panel", callback_data="admin_panel"))
    return builder.as_markup()

def force_join_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Join Channel 1", url="https://t.me/FreePLPFileShareCommunityXD"))
    builder.row(InlineKeyboardButton(text="💬 Join Group 2", url="https://t.me/PixellabShimulXDChat"))
    builder.row(InlineKeyboardButton(text="📢 Join Channel 3", url="https://t.me/PixellabShimulXD"))
    builder.row(InlineKeyboardButton(text="✅ ভেরিফাই করুন (Verify)", callback_data="verify_sub"))
    return builder.as_markup()

def admin_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Broadcast Message", callback_data="start_broadcast"))
    builder.row(InlineKeyboardButton(text="📊 Total Users", callback_data="user_stats"))
    builder.row(InlineKeyboardButton(text="⬅️ Back to Menu", callback_data="back_to_home"))
    return builder.as_markup()

# --- HANDLERS ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = message.from_user
    # DB Save
    if not await users_col.find_one({"user_id": user.id}):
        await users_col.insert_one({
            "user_id": user.id, "name": user.full_name,
            "username": f"@{user.username}" if user.username else "N/A",
            "date": datetime.now()
        })

    await apply_typing(message.chat.id, 1.2)
    
    if not await is_subscribed(user.id):
        caption = (
            f"👋 <b>হ্যালো বন্ধু {user.first_name}!</b>\n\n"
            f"বটটি ব্যবহার করতে নিচের চ্যানেলগুলোতে জয়েন থাকতে হবে।\n"
            f"<i>জয়েন না থাকলে ডাউনলোড লিঙ্ক কাজ করবে না।</i>"
        )
        await message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=force_join_kb())
    else:
        caption = (
            f"❝ <b>Pixellab - ShimulXD</b> | এডভান্স ফিচার সমৃদ্ধ শক্তিশালী ডিজাইন অ্যাপ ❞\n\n"
            f"👋 <b>স্বাগতম বন্ধু!</b>\n\n"
            f"নিচের বাটন থেকে সরাসরি <b>Firebase Realtime</b> এর মাধ্যমে লেটেস্ট ভার্সন ডাউনলোড করুন।"
        )
        await message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(user.id == ADMIN_ID))

@dp.callback_query(F.data == "verify_sub")
async def verify_sub(callback: CallbackQuery):
    await apply_typing(callback.message.chat.id, 0.8)
    if await is_subscribed(callback.from_user.id):
        await callback.answer("✅ ভেরিফিকেশন সফল!", show_alert=False)
        await callback.message.delete()
        # Show Main Menu
        caption = "❝ <b>Pixellab - ShimulXD</b> ❞\n\n✅ <b>ধন্যবাদ!</b> আপনি এখন ডাউনলোড করতে পারবেন।"
        await callback.message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(callback.from_user.id == ADMIN_ID))
    else:
        await callback.answer("⚠️ বন্ধু, আগে সব চ্যানেলে জয়েন করুন!", show_alert=True)

@dp.callback_query(F.data == "get_download")
async def download_now(callback: CallbackQuery):
    # এনিমেশন ইফেক্ট
    await callback.answer("🔍 ফাইলটি খোঁজা হচ্ছে...", show_alert=False)
    await apply_typing(callback.message.chat.id, 1.5)
    
    link = await fetch_live_link()
    
    if link:
        text = (
            f"🚀 <b>আপনার ফাইল ডাউনলোড করতে নিচের লিঙ্কে ক্লিক করুন:</b>\n\n"
            f"🔗 <b>লিঙ্ক:</b> <a href='{link}'>{link}</a>\n\n"
            f"🛡 <i>বটটি সরাসরি Firebase থেকে রিয়েল-টাইম ডাটা সংগ্রহ করেছে।</i>"
        )
        await callback.message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    else:
        # যদি কোনো কারণে লিঙ্ক না পায়
        await callback.answer("❌ Error: Firebase Link Not Found!", show_alert=True)
        await callback.message.answer("❌ <b>দুঃখিত বন্ধু!</b>\nসার্ভার থেকে লিঙ্কটি পাওয়া যায়নি। দয়া করে এডমিন @ShimulXD এর সাথে যোগাযোগ করুন।", parse_mode=ParseMode.HTML)

# --- ADMIN PANEL ---

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await apply_typing(callback.message.chat.id, 0.5)
    await callback.message.edit_caption(
        caption="🛠 <b>অ্যাডভান্সড এডমিন কন্ট্রোল প্যানেল</b>\n\nইউজার সংখ্যা দেখুন বা ব্রডকাস্ট করুন। ডাউনলোড লিঙ্ক সরাসরি আপনার Firebase ডাটাবেস থেকে ম্যানেজ করুন।",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_kb()
    )

@dp.callback_query(F.data == "user_stats")
async def user_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    count = await users_col.count_documents({})
    await callback.answer(f"📊 মোট ইউজার: {count} জন", show_alert=True)

@dp.callback_query(F.data == "start_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("📢 <b>ব্রডকাস্ট মেসেজটি লিখুন বন্ধু:</b>\n(Text/Photo/Video সব সাপোর্ট করবে)")
    await state.set_state(AdminState.waiting_for_broadcast)

@dp.message(AdminState.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    
    users = users_col.find({})
    success, failed = 0, 0
    msg = await message.answer("⏳ <b>ব্রডকাস্ট শুরু হয়েছে...</b>")
    
    async for user in users:
        try:
            await bot.copy_message(chat_id=user['user_id'], from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
            
    await msg.edit_text(f"✅ <b>ব্রডকাস্ট শেষ!</b>\n\n🟢 সফল: {success}\n🔴 ব্যর্থ: {failed}", parse_mode=ParseMode.HTML)
    await state.clear()

@dp.callback_query(F.data == "back_to_home")
async def back_to_home(callback: CallbackQuery):
    await callback.message.delete()
    await apply_typing(callback.message.chat.id, 0.5)
    user = callback.from_user
    caption = "❝ <b>Pixellab - ShimulXD</b> ❞\n\n👋 <b>স্বাগতম বন্ধু!</b>\nনিচের বাটন থেকে ডাউনলোড করুন।"
    await callback.message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(user.id == ADMIN_ID))

# --- RUN ---
async def main():
    logging.basicConfig(level=logging.INFO)
    print("✅ Pixellab Bot is Running perfectly!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
