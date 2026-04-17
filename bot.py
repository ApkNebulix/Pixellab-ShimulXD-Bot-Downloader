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
FIREBASE_JSON_URL = "https://pixellabshimulxd-default-rtdb.firebaseio.com/download_link_psxd.json"

# --- DATABASE SETUP (For Users Only) ---
try:
    encoded_pass = urllib.parse.quote_plus("@%aN%#404%App@")
    MONGO_URI = f"mongodb+srv://apknebulix_modz:{encoded_pass}@apknebulix.suopcnt.mongodb.net/?appName=ApkNebulix"
    client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['BlutterUltra']
    users_col = db['users']
except Exception as e:
    print(f"❌ DB Error: {e}")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- STATES ---
class AdminState(StatesGroup):
    waiting_for_broadcast = State()

# --- HELPER FUNCTIONS ---

async def apply_typing(chat_id, duration=1.5):
    """টাইপিং এনিমেশন ইফেক্ট"""
    await bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(duration)

async def is_subscribed(user_id):
    """জয়েন চেক ফাংশন"""
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

async def fetch_firebase_link():
    """Firebase থেকে রিয়েল টাইম ডাউনলোড লিঙ্ক সংগ্রহ"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FIREBASE_JSON_URL, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # JSON ফরম্যাট: {"download_link_psxd": {"link": "..."}}
                    return data.get("download_link_psxd", {}).get("link")
    except Exception as e:
        print(f"Firebase Fetch Error: {e}")
    return None

# --- KEYBOARDS ---

def main_menu_kb(is_admin=False):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💎 Download Latest Version 🚀", callback_data="get_download"))
    builder.row(InlineKeyboardButton(text="📢 Join Official Channel", url="https://t.me/PixellabShimulXD"))
    builder.row(InlineKeyboardButton(text="💬 Support Group", url="https://t.me/PixellabShimulXDChat"))
    if is_admin:
        builder.row(InlineKeyboardButton(text="🛠 Advanced Admin Panel", callback_data="admin_panel"))
    return builder.as_markup()

def force_join_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Join Channel 1", url="https://t.me/FreePLPFileShareCommunityXD"))
    builder.row(InlineKeyboardButton(text="💬 Join Group 2", url="https://t.me/PixellabShimulXDChat"))
    builder.row(InlineKeyboardButton(text="📢 Join Channel 3", url="https://t.me/PixellabShimulXD"))
    builder.row(InlineKeyboardButton(text="✅ Verify Membership", callback_data="verify_sub"))
    return builder.as_markup()

def admin_panel_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Global Broadcast", callback_data="start_broadcast"))
    builder.row(InlineKeyboardButton(text="📊 User Statistics", callback_data="user_stats"))
    builder.row(InlineKeyboardButton(text="⬅️ Back to Home", callback_data="back_to_home"))
    return builder.as_markup()

# --- HANDLERS ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = message.from_user
    # Save user to DB
    if not await users_col.find_one({"user_id": user.id}):
        await users_col.insert_one({
            "user_id": user.id,
            "name": user.full_name,
            "username": f"@{user.username}" if user.username else "N/A",
            "date": datetime.now()
        })

    await apply_typing(message.chat.id)
    
    if not await is_subscribed(user.id):
        caption = (
            f"👋 <b>হ্যালো বন্ধু {user.first_name}!</b>\n\n"
            f"বটটি ব্যবহার করার জন্য আপনাকে অবশ্যই নিচের ৩টি চ্যানেলে জয়েন থাকতে হবে।\n\n"
            f"<i>জয়েন না করলে আপনি অ্যাপ ডাউনলোড লিঙ্ক পাবেন না।</i>"
        )
        await message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=force_join_kb())
    else:
        caption = (
            f"❝ <b>Pixellab - ShimulXD</b> | এডভান্স ফিচার সমৃদ্ধ শক্তিশালী ডিজাইন অ্যাপ ❞\n\n"
            f"👋 <b>স্বাগতম বন্ধু {user.first_name}!</b>\n\n"
            f"🚀 <b>ডাউনলোড বাটন এ ক্লিক করে রিয়েল টাইম লেটেস্ট ভার্সন সংগ্রহ করুন।</b>"
        )
        await message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(user.id == ADMIN_ID))

@dp.callback_query(F.data == "verify_sub")
async def verify_callback(callback: CallbackQuery):
    await apply_typing(callback.message.chat.id, 1.0)
    if await is_subscribed(callback.from_user.id):
        await callback.answer("✅ ভেরিফিকেশন সফল বন্ধু!", show_alert=False)
        await callback.message.delete()
        user = callback.from_user
        caption = (
            f"❝ <b>Pixellab - ShimulXD</b> ❞\n\n"
            f"✅ <b>ভেরিফিকেশন সম্পন্ন!</b> এখন আপনি আপনার প্রয়োজনীয় ফাইলটি ডাউনলোড করতে পারবেন।"
        )
        await callback.message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(user.id == ADMIN_ID))
    else:
        await callback.answer("⚠️ বন্ধু, আপনি এখনও সব চ্যানেলে জয়েন করেননি!", show_alert=True)

@dp.callback_query(F.data == "get_download")
async def download_trigger(callback: CallbackQuery):
    await apply_typing(callback.message.chat.id, 2.0)
    
    # সরাসরি Firebase থেকে লিঙ্ক আনা
    live_link = await fetch_firebase_link()
    
    if live_link:
        text = (
            f"✨ <b>আপনার কাঙ্খিত অ্যাপ লিঙ্ক প্রস্তুত বন্ধু!</b>\n\n"
            f"🔗 <b>ডাউনলোড লিঙ্ক:</b> <a href='{live_link}'>{live_link}</a>\n\n"
            f"🛡 <i>এটি রিয়েল টাইম ডাটাবেস থেকে সরাসরি প্রদান করা হয়েছে।</i>"
        )
        await callback.message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        await callback.answer("✅ লিঙ্ক পাওয়া গেছে!")
    else:
        await callback.message.answer("❌ <b>দুঃখিত বন্ধু!</b>\nসার্ভার থেকে লিঙ্ক সংগ্রহ করা সম্ভব হচ্ছে না। কিছুক্ষণ পর আবার চেষ্টা করুন।", parse_mode=ParseMode.HTML)
        await callback.answer("Error: Firebase Link Not Found", show_alert=True)

# --- ADMIN PANEL HANDLERS ---

@dp.callback_query(F.data == "admin_panel")
async def admin_main(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await apply_typing(callback.message.chat.id, 0.5)
    await callback.message.edit_caption(
        caption="⚡ <b>প্রিমিয়াম এডমিন কন্ট্রোল প্যানেল</b>\n\n"
                "<i>দ্রষ্টব্য: ডাউনলোড লিঙ্ক এখন সরাসরি Firebase থেকে নিয়ন্ত্রিত হয়।</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_panel_kb()
    )

@dp.callback_query(F.data == "user_stats")
async def stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    count = await users_col.count_documents({})
    await callback.answer(f"📊 বটের মোট ইউজার: {count} জন", show_alert=True)

@dp.callback_query(F.data == "start_broadcast")
async def broadcast_step1(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("📢 <b>ব্রডকাস্ট মেসেজটি দিন বন্ধু:</b>\n(টেক্সট, ফটো বা ভিডিও যা দিবেন সব ইউজারের কাছে চলে যাবে)")
    await state.set_state(AdminState.waiting_for_broadcast)

@dp.message(AdminState.waiting_for_broadcast)
async def broadcast_step2(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    
    users = users_col.find({})
    success, failed = 0, 0
    progress_msg = await message.answer("⏳ <b>ব্রডকাস্ট প্রসেসিং...</b>")
    
    async for user in users:
        try:
            await bot.copy_message(chat_id=user['user_id'], from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
            await asyncio.sleep(0.05) 
        except TelegramForbiddenError:
            failed += 1
        except Exception:
            failed += 1
            
    await progress_msg.edit_text(f"✅ <b>ব্রডকাস্ট সম্পন্ন!</b>\n\n🟢 সফল: {success}\n🔴 ব্যর্থ: {failed}", parse_mode=ParseMode.HTML)
    await state.clear()

@dp.callback_query(F.data == "back_to_home")
async def back_home(callback: CallbackQuery):
    user = callback.from_user
    await callback.message.delete()
    await apply_typing(callback.message.chat.id, 0.8)
    caption = (
        f"❝ <b>Pixellab - ShimulXD</b> ❞\n\n"
        f"👋 <b>স্বাগতম বন্ধু!</b> হোম মেনুতে ফিরে এসেছেন।"
    )
    await callback.message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(user.id == ADMIN_ID))

# --- RUN BOT ---
async def main():
    print("🚀 Pixellab ShimulXD Bot is Live with Firebase Realtime Support!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
