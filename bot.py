import asyncio
import logging
import urllib.parse
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError

# --- CONFIGURATION ---
API_TOKEN = "8354048442:AAGwTXhT9O3fA4m30ulMkCtEkLmn0_Umil4"
ADMIN_ID = 8381570120
CHANNELS = ["@FreePLPFileShareCommunityXD", "@PixellabShimulXDChat", "@PixellabShimulXD"]
WELCOME_IMAGE = "https://raw.githubusercontent.com/ApkNebulix/Daroid-AN/refs/heads/main/Img/PixellabShimulXD/pixellab_shimulxd_logo.jpeg"

# --- DATABASE SETUP ---
try:
    encoded_pass = urllib.parse.quote_plus("@%aN%#404%App@")
    MONGO_URI = f"mongodb+srv://apknebulix_modz:{encoded_pass}@apknebulix.suopcnt.mongodb.net/?appName=ApkNebulix"
    client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['BlutterUltra']
    users_col = db['users']
    settings_col = db['settings'] # For storing download link
except Exception as e:
    print(f"❌ DB Notice: {e}")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- STATES ---
class AdminState(StatesGroup):
    waiting_for_link = State()
    waiting_for_broadcast = State()

# --- FUNCTIONS ---
async def is_subscribed(user_id):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

async def get_download_link():
    data = await settings_col.find_one({"type": "config"})
    return data.get("link") if data else None

# --- KEYBOARDS ---
def welcome_kb(is_admin=False):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📥 Download Latest Version", callback_query_id="dl_btn", callback_data="get_download"))
    builder.row(InlineKeyboardButton(text="📢 Join TG Channel", url="https://t.me/PixellabShimulXD"))
    if is_admin:
        builder.row(InlineKeyboardButton(text="🛠 Admin Panel", callback_data="admin_panel"))
    return builder.as_markup()

def force_join_kb():
    builder = InlineKeyboardBuilder()
    for i, channel in enumerate(CHANNELS, 1):
        builder.row(InlineKeyboardButton(text=f"Join Channel {i}", url=f"https://t.me/{channel.replace('@', '')}"))
    builder.row(InlineKeyboardButton(text="✅ Joined (Verify)", callback_data="verify_sub"))
    return builder.as_markup()

def admin_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Add/Update Link", callback_data="set_link"))
    builder.row(InlineKeyboardButton(text="📢 Broadcast", callback_data="start_broadcast"))
    builder.row(InlineKeyboardButton(text="👥 User Count", callback_data="user_count"))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_home"))
    return builder.as_markup()

# --- HANDLERS ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user = message.from_user
    # Save User to DB
    existing_user = await users_col.find_one({"user_id": user.id})
    if not existing_user:
        await users_col.insert_one({
            "user_id": user.id,
            "name": user.full_name,
            "username": f"@{user.username}" if user.username else "N/A",
            "date": datetime.now()
        })

    # Typing Animation
    await bot.send_chat_action(message.chat.id, "typing")
    await asyncio.sleep(1)

    if not await is_subscribed(user.id):
        await message.answer_photo(
            photo=WELCOME_IMAGE,
            caption=f"👋 স্বাগতম বন্ধু **{user.first_name}**!\n\nবটটি ব্যবহার করতে নিচের চ্যানেলগুলোতে জয়েন থাকতে হবে। জয়েন করে 'Verify' বাটনে ক্লিক কর।",
            reply_markup=force_join_kb()
        )
    else:
        await message.answer_photo(
            photo=WELCOME_IMAGE,
            caption="❝\nPixellab - ShimulXD | এডভান্স ফিচার সমৃদ্ধ একটি শক্তিশালী গ্রাফিক্স ডিজাইন অ্যাপ\n❞\n\nনিচের বাটন থেকে লেটেস্ট ভার্সন ডাউনলোড করে নাও বন্ধু।",
            reply_markup=welcome_kb(user.id == ADMIN_ID)
        )

@dp.callback_query(F.data == "verify_sub")
async def verify_sub(callback: CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.message.delete()
        await start_cmd(callback.message)
    else:
        await callback.answer("❌ তুমি এখনও সব চ্যানেলে জয়েন করোনি বন্ধু!", show_alert=True)

@dp.callback_query(F.data == "get_download")
async def send_download(callback: CallbackQuery):
    link = await get_download_link()
    if link:
        await callback.answer("প্রসেসিং হচ্ছে...", show_alert=False)
        await callback.message.answer(f"🚀 **আপনার ডাউনলোড লিঙ্ক প্রস্তুত বন্ধু:**\n\n🔗 {link}\n\nধন্যবাদ আমাদের সাথে থাকার জন্য।")
    else:
        await callback.answer("⚠️ দুঃখিত বন্ধু, এখনো কোন লিঙ্ক সেট করা হয়নি। এডমিনের সাথে যোগাযোগ করুন।", show_alert=True)

# --- ADMIN FUNCTIONS ---

@dp.callback_query(F.data == "admin_panel")
async def open_admin(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.edit_caption(caption="⚡ **এডমিন প্যানেলে স্বাগতম বন্ধু!**\nএখান থেকে বট কন্ট্রোল করো।", reply_markup=admin_kb())

@dp.callback_query(F.data == "set_link")
async def set_link_init(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("🔗 দয়া করে নতুন ডাউনলোড লিঙ্কটি সেন্ড করো বন্ধু:")
    await state.set_state(AdminState.waiting_for_link)

@dp.message(AdminState.waiting_for_link)
async def process_link(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    new_link = message.text
    await settings_col.update_one({"type": "config"}, {"$set": {"link": new_link}}, upsert=True)
    await message.answer(f"✅ সফলভাবে নতুন লিঙ্ক সেট হয়েছে:\n{new_link}")
    await state.clear()

@dp.callback_query(F.data == "user_count")
async def show_users(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    count = await users_col.count_documents({})
    await callback.answer(f"📊 বটের মোট ইউজার: {count} জন", show_alert=True)

@dp.callback_query(F.data == "start_broadcast")
async def broadcast_init(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("📢 ব্রডকাস্ট মেসেজটি দাও বন্ধু (Text, Photo, Video সব সাপোর্ট করবে):")
    await state.set_state(AdminState.waiting_for_broadcast)

@dp.message(AdminState.waiting_for_broadcast)
async def perform_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    
    users = users_col.find({})
    success = 0
    failed = 0
    await message.answer("⏳ ব্রডকাস্ট শুরু হয়েছে...")
    
    async for user in users:
        try:
            await bot.copy_message(chat_id=user['user_id'], from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
            await asyncio.sleep(0.05) # Anti-flood
        except TelegramForbiddenError:
            failed += 1
        except Exception:
            failed += 1
            
    await message.answer(f"✅ ব্রডকাস্ট শেষ!\n\n🟢 সফল: {success}\n🔴 ব্যর্থ: {failed}")
    await state.clear()

@dp.callback_query(F.data == "back_to_home")
async def back_home(callback: CallbackQuery):
    await callback.message.delete()
    # Logic to send welcome screen again
    user = callback.from_user
    await bot.send_photo(
        chat_id=callback.message.chat.id,
        photo=WELCOME_IMAGE,
        caption="❝\nPixellab - ShimulXD | এডভান্স ফিচার সমৃদ্ধ একটি শক্তিশালী গ্রাফিক্স ডিজাইন অ্যাপ\n❞\n\nনিচের বাটন থেকে লেটেস্ট ভার্সন ডাউনলোড করে নাও বন্ধু।",
        reply_markup=welcome_kb(user.id == ADMIN_ID)
    )

async def main():
    print("✅ Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
