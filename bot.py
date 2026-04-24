import asyncio
import logging
import urllib.parse
import aiohttp
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode, ChatAction

# --- CONFIGURATION ---
API_TOKEN = "8354048442:AAGwTXhT9O3fA4m30ulMkCtEkLmn0_Umil4"
ADMIN_ID = 8381570120

# নতুন চ্যানেল লিস্ট (ইউজারকে অবশ্যই এগুলোতে থাকতে হবে)
CHANNELS = [
    "@FreePLPFileShareCommunityXD", 
    "@PixellabShimulXDChat", 
    "@PixellabShimulXD",
    "@HunterGraphicsDesign",
    "@ShimulGraphicsBD"
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

# --- STATES ---
class AdminState(StatesGroup):
    waiting_for_broadcast = State()

# --- HELPER FUNCTIONS ---

async def send_with_typing(message: types.Message, text: str, reply_markup=None, photo=None):
    """স্মুথ টাইপিং এনিমেশন সহ মেসেজ পাঠানো"""
    try:
        await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        await asyncio.sleep(1.5) # বাস্তবসম্মত টাইপিং টাইম
        if photo:
            return await message.answer_photo(photo=photo, caption=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        else:
            return await message.answer(text=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Typing Effect Error: {e}")

async def is_subscribed(user_id):
    """উন্নত ফোর্স জয়েন ভেরিফিকেশন"""
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            # যদি বট কোনো চ্যানেলে অ্যাডমিন না থাকে তবে এই চেকটি কাজ নাও করতে পারে
            return False
    return True

async def fetch_firebase_link():
    """Firebase থেকে ডাউনলোড লিংক ফেচ করা"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FIREBASE_URL, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, dict):
                        return data.get("link") or data.get("download_link_psxd", {}).get("link")
    except Exception as e:
        logging.error(f"Firebase Fetch Error: {e}")
    return None

# --- KEYBOARDS ---

def main_menu_kb(is_admin=False):
    builder = InlineKeyboardBuilder()
    # আকর্ষণীয় ইমোজি ব্যবহার করে 'কালারফুল' লুক দেওয়া হয়েছে
    builder.row(InlineKeyboardButton(text="💎 DOWNLOAD LATEST VERSION 🚀", callback_data="get_download_process"))
    builder.row(
        InlineKeyboardButton(text="📢 Channel", url="https://t.me/PixellabShimulXD"),
        InlineKeyboardButton(text="💬 Group", url="https://t.me/PixellabShimulXDChat")
    )
    builder.row(InlineKeyboardButton(text="🔥 More PLP Files", url="https://t.me/HunterGraphicsDesign"))
    
    if is_admin:
        builder.row(InlineKeyboardButton(text="🛠️ ADMIN CONTROL PANEL 🛠️", callback_data="admin_panel"))
    
    return builder.as_markup()

def force_join_kb():
    builder = InlineKeyboardBuilder()
    # সব চ্যানেলের জন্য বাটন তৈরি
    builder.row(InlineKeyboardButton(text="📍 Join Our Main Channel", url="https://t.me/PixellabShimulXD"))
    builder.row(InlineKeyboardButton(text="📍 Join Graphics Design BD", url="https://t.me/ShimulGraphicsBD"))
    builder.row(InlineKeyboardButton(text="📍 Join Hunter Graphics", url="https://t.me/HunterGraphicsDesign"))
    
    builder.row(InlineKeyboardButton(text="✅ VERIFY MEMBERSHIP ✅", callback_data="verify_sub"))
    return builder.as_markup()

# --- HANDLERS ---

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    # সিকিউরিটি: গ্রুপ চেক (বটটি গ্রুপে কাজ করবে না)
    if message.chat.type != "private":
        return # গ্রুপে কোনো রিপ্লাই দিবে না

    user = message.from_user
    
    # ইউজার ডাটাবেজে সেভ করা
    existing_user = await users_col.find_one({"user_id": user.id})
    if not existing_user:
        await users_col.insert_one({
            "user_id": user.id, 
            "name": user.full_name,
            "username": f"@{user.username}" if user.username else "N/A",
            "date": datetime.now()
        })

    # সাবস্ক্রিপশন চেক
    if not await is_subscribed(user.id):
        caption = (
            f"👋 <b>হ্যালো বন্ধু {user.first_name}!</b>\n\n"
            f"বটটি ব্যবহার করতে নিচের চ্যানেলগুলোতে জয়েন থাকা বাধ্যতামূলক।\n\n"
            f"⚠️ <i>জয়েন না করলে ডাউনলোড লিংক জেনারেট হবে না।</i>"
        )
        await send_with_typing(message, caption, reply_markup=force_join_kb(), photo=WELCOME_IMAGE)
    else:
        caption = (
            f"🌟 <b>Pixellab ShimulXD Official Bot</b> 🌟\n\n"
            f"স্বাগতম বন্ধু <b>{user.first_name}</b>!\n"
            f"এখানে আপনি Pixellab এর প্রিমিয়াম ও লেটেস্ট ভার্সনগুলো পাবেন।\n\n"
            f"🚀 <b>নিচের বাটনে ক্লিক করে ডাউনলোড শুরু করুন:</b>"
        )
        await send_with_typing(message, caption, reply_markup=main_menu_kb(user.id == ADMIN_ID), photo=WELCOME_IMAGE)

@dp.callback_query(F.data == "verify_sub")
async def verify_sub(callback: CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.answer("✅ ভেরিফিকেশন সফল বন্ধু!", show_alert=False)
        await callback.message.delete()
        
        caption = "🎉 <b>অভিনন্দন!</b> আপনার ভেরিফিকেশন সফল হয়েছে।\nএখন আপনি বটটি ব্যবহার করতে পারেন।"
        await send_with_typing(callback.message, caption, reply_markup=main_menu_kb(callback.from_user.id == ADMIN_ID), photo=WELCOME_IMAGE)
    else:
        await callback.answer("⚠️ বন্ধু, আপনি এখনো সবগুলো চ্যানেলে জয়েন করেননি!", show_alert=True)

@dp.callback_query(F.data == "get_download_process")
async def get_download_process(callback: CallbackQuery):
    # সাবস্ক্রিপশন চেক (পুনরায় সিকিউরিটির জন্য)
    if not await is_subscribed(callback.from_user.id):
        await callback.answer("❌ আগে জয়েন করুন!", show_alert=True)
        return

    await callback.answer("🔍 ফাইলটি সার্ভারে খোঁজা হচ্ছে...", show_alert=False)
    
    # Firebase থেকে লিংক আনা
    live_link = await fetch_firebase_link()
    
    if live_link:
        dl_builder = InlineKeyboardBuilder()
        dl_builder.row(InlineKeyboardButton(text="📥 CLICK HERE TO DOWNLOAD 📥", url=live_link))
        
        await send_with_typing(callback.message, 
            f"✅ <b>ফাইল পাওয়া গেছে!</b>\n\n"
            f"নিচের বাটনে ক্লিক করলে সরাসরি আপনার ব্রাউজারে ডাউনলোড শুরু হবে।",
            reply_markup=dl_builder.as_markup()
        )
    else:
        await callback.message.answer("⚠️ <b>দুঃখিত!</b> বর্তমানে ডাউনলোড লিংকটি আপডেট করা হচ্ছে। দয়া করে কিছুক্ষণ পর চেষ্টা করুন।")

# --- ADMIN PANEL ---

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Broadcast Message", callback_data="start_broadcast"))
    builder.row(InlineKeyboardButton(text="📊 View Bot Stats", callback_data="user_stats"))
    builder.row(InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_home"))
    
    await callback.message.edit_caption(
        caption="⚙️ <b>অ্যাডমিন কন্ট্রোল প্যানেল</b>\n\nইউজার সংখ্যা দেখুন অথবা সবার কাছে নোটিফিকেশন পাঠান।",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "user_stats")
async def user_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    count = await users_col.count_documents({})
    await callback.answer(f"📊 বটের মোট ইউজার: {count} জন", show_alert=True)

@dp.callback_query(F.data == "start_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("🖋️ <b>ব্রডকাস্ট মেসেজটি লিখুন:</b>\n(এটি সবার কাছে চলে যাবে)")
    await state.set_state(AdminState.waiting_for_broadcast)

@dp.message(AdminState.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    users = users_col.find({})
    success, failed = 0, 0
    progress_msg = await message.answer("⏳ ব্রডকাস্টিং শুরু হয়েছে...")
    
    async for user in users:
        try:
            await bot.copy_message(
                chat_id=user['user_id'], 
                from_chat_id=message.chat.id, 
                message_id=message.message_id
            )
            success += 1
            await asyncio.sleep(0.05) # ফ্লাড এভয়েড করার জন্য
        except Exception:
            failed += 1
            
    await progress_msg.edit_text(f"✅ <b>ব্রডকাস্ট সম্পন্ন!</b>\n\n🟢 সফল: {success}\n🔴 ব্যর্থ: {failed}")
    await state.clear()

@dp.callback_query(F.data == "back_to_home")
async def back_to_home(callback: CallbackQuery):
    await callback.message.delete()
    # নতুন করে স্টার্ট ট্রিগার করা
    await start_cmd(callback.message)

# --- RUN BOT ---
async def main():
    logging.basicConfig(level=logging.INFO)
    print("✅ Pixellab ShimulXD Bot is Online!")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Polling Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot Stopped!")
