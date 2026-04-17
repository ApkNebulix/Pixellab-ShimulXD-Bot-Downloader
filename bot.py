import asyncio
import logging
import urllib.parse
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
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

# --- DATABASE SETUP (Secure & Permanent) ---
try:
    encoded_pass = urllib.parse.quote_plus("@%aN%#404%App@")
    MONGO_URI = f"mongodb+srv://apknebulix_modz:{encoded_pass}@apknebulix.suopcnt.mongodb.net/?appName=ApkNebulix"
    client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['BlutterUltra']
    users_col = db['users']
    settings_col = db['settings']
except Exception as e:
    print(f"❌ DB Error: {e}")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- STATES ---
class AdminState(StatesGroup):
    waiting_for_link = State()
    waiting_for_broadcast = State()

# --- UTILS ---
async def send_typing(message: types.Message, duration=1.5):
    """টাইপিং এনিমেশন ইফেক্ট"""
    await bot.send_chat_action(message.chat.id, "typing")
    await asyncio.sleep(duration)

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

async def get_db_link():
    """ডাটাবেস থেকে লিঙ্ক সংগ্রহ"""
    data = await settings_col.find_one({"type": "download_config"})
    return data.get("url") if data else None

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
    builder.row(InlineKeyboardButton(text="🔗 Update Download Link", callback_data="set_link"))
    builder.row(InlineKeyboardButton(text="📢 Global Broadcast", callback_data="start_broadcast"))
    builder.row(InlineKeyboardButton(text="📊 User Statistics", callback_data="user_stats"))
    builder.row(InlineKeyboardButton(text="🗑 Delete Link", callback_data="delete_link"))
    builder.row(InlineKeyboardButton(text="⬅️ Back to Home", callback_data="back_to_home"))
    return builder.as_markup()

# --- HANDLERS ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = message.from_user
    # ডাটাবেস চেক ও সেভ
    if not await users_col.find_one({"user_id": user.id}):
        await users_col.insert_one({
            "user_id": user.id,
            "name": user.full_name,
            "username": f"@{user.username}" if user.username else "N/A",
            "joined_at": datetime.now()
        })

    await send_typing(message)
    
    if not await is_subscribed(user.id):
        caption = (
            f"👋 <b>হ্যালো বন্ধু {user.first_name}!</b>\n\n"
            f"বটটি ব্যবহার করার জন্য আপনাকে অবশ্যই আমাদের চ্যানেলগুলোতে জয়েন থাকতে হবে।\n\n"
            f"<i>নিচের বাটনগুলো ব্যবহার করে জয়েন করুন এবং ভেরিফাই বাটনে ক্লিক করুন।</i>"
        )
        await message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=force_join_kb())
    else:
        caption = (
            f"❝ <b>Pixellab - ShimulXD</b> | এডভান্স ফিচার সমৃদ্ধ একটি শক্তিশালী গ্রাফিক্স ডিজাইন অ্যাপ ❞\n\n"
            f"👋 <b>স্বাগতম বন্ধু!</b> বটের সকল প্রিমিয়াম ফিচার এখন আপনার জন্য আনলক করা হয়েছে।\n\n"
            f"🚀 <b>নিচের বাটন থেকে লেটেস্ট ভার্সন ডাউনলোড করে নিন।</b>"
        )
        await message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(user.id == ADMIN_ID))

@dp.callback_query(F.data == "verify_sub")
async def verify_callback(callback: CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.answer("✅ ভেরিফিকেশন সফল বন্ধু!", show_alert=False)
        await callback.message.delete()
        # রি-ডাইরেক্ট টু স্টার্ট
        user = callback.from_user
        caption = (
            f"❝ <b>Pixellab - ShimulXD</b> ❞\n\n"
            f"✅ <b>ধন্যবাদ বন্ধু!</b> আপনার ভেরিফিকেশন সফল হয়েছে। এখন আপনি অ্যাপটি ডাউনলোড করতে পারবেন।"
        )
        await callback.message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(user.id == ADMIN_ID))
    else:
        await callback.answer("⚠️ বন্ধু, আপনি এখনো সব চ্যানেলে জয়েন করেননি!", show_alert=True)

@dp.callback_query(F.data == "get_download")
async def download_trigger(callback: CallbackQuery):
    link = await get_db_link()
    if link:
        text = (
            f"✨ <b>আপনার ফাইলটি প্রস্তুত বন্ধু!</b>\n\n"
            f"🔗 <b>ডাউনলোড লিঙ্ক:</b> <a href='{link}'>এখানে ক্লিক করুন</a>\n\n"
            f"🛡 <i>নিরাপদ এবং লেটেস্ট ভার্সন ডাউনলোড নিশ্চিত করুন।</i>"
        )
        await callback.message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    else:
        await callback.answer("❌ দুঃখিত বন্ধু! বর্তমানে কোনো ডাউনলোড লিঙ্ক সেট করা নেই। এডমিনের সাথে যোগাযোগ করুন।", show_alert=True)

# --- ADMIN PANEL LOGIC ---

@dp.callback_query(F.data == "admin_panel")
async def admin_main(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.edit_caption(caption="⚡ <b>প্রিমিয়াম এডমিন কন্ট্রোল প্যানেল</b>\n\nআপনার বটের সকল সেটিংস এখান থেকে নিয়ন্ত্রণ করুন বন্ধু।", parse_mode=ParseMode.HTML, reply_markup=admin_panel_kb())

@dp.callback_query(F.data == "set_link")
async def set_link_step1(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("📥 <b>নতুন ডাউনলোড লিঙ্কটি সেন্ড করুন বন্ধু:</b>\n(পুরাতন লিঙ্কটি অটোমেটিক ডিলিট হয়ে যাবে)", parse_mode=ParseMode.HTML)
    await state.set_state(AdminState.waiting_for_link)

@dp.message(AdminState.waiting_for_link)
async def set_link_step2(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    new_url = message.text
    await settings_col.update_one({"type": "download_config"}, {"$set": {"url": new_url}}, upsert=True)
    await message.answer(f"✅ <b>সফলভাবে লিঙ্ক আপডেট হয়েছে!</b>\n\nনতুন লিঙ্ক: <code>{new_url}</code>", parse_mode=ParseMode.HTML)
    await state.clear()

@dp.callback_query(F.data == "delete_link")
async def del_link(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await settings_col.delete_one({"type": "download_config"})
    await callback.answer("🗑 ডাউনলোড লিঙ্ক ডিলিট করা হয়েছে!", show_alert=True)

@dp.callback_query(F.data == "user_stats")
async def stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    count = await users_col.count_documents({})
    await callback.answer(f"📊 বটের মোট ইউজার: {count} জন", show_alert=True)

@dp.callback_query(F.data == "start_broadcast")
async def broadcast_step1(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("📢 <b>ব্রডকাস্ট মেসেজটি দিন:</b>\n(টেক্সট, ফটো বা ভিডিও যা দিবেন সব ইউজারের কাছে চলে যাবে)")
    await state.set_state(AdminState.waiting_for_broadcast)

@dp.message(AdminState.waiting_for_broadcast)
async def broadcast_step2(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    
    users = users_col.find({})
    success, failed = 0, 0
    progress_msg = await message.answer("⏳ <b>ব্রডকাস্ট শুরু হয়েছে...</b>")
    
    async for user in users:
        try:
            await bot.copy_message(chat_id=user['user_id'], from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
            await asyncio.sleep(0.05) 
        except TelegramForbiddenError:
            failed += 1
        except Exception:
            failed += 1
            
    await progress_msg.edit_text(f"✅ <b>ব্রডকাস্ট সম্পন্ন!</b>\n\n🟢 সফল: {success}\n🔴 ব্লক/ব্যর্থ: {failed}", parse_mode=ParseMode.HTML)
    await state.clear()

@dp.callback_query(F.data == "back_to_home")
async def back_home(callback: CallbackQuery):
    user = callback.from_user
    await callback.message.delete()
    caption = (
        f"❝ <b>Pixellab - ShimulXD</b> ❞\n\n"
        f"👋 <b>স্বাগতম বন্ধু!</b> বটের সকল প্রিমিয়াম ফিচার এখন আপনার জন্য আনলক করা হয়েছে।"
    )
    await callback.message.answer_photo(photo=WELCOME_IMAGE, caption=caption, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(user.id == ADMIN_ID))

# --- MAIN RUNNER ---
async def main():
    print("🚀 Bot Started & Ready!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
