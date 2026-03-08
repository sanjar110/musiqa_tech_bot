import os
import asyncio
import logging
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from yt_dlp import YoutubeDL

# 1. SOZLAMALAR
load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Bot brendingi
BOT_USERNAME = "@musiqa_tech_bot"
CAPTION_TEXT = f"🎶 {BOT_USERNAME} orqali yuklandi. Eng sara musiqalar bizda! ✅"

if not os.path.exists("downloads"):
    os.makedirs("downloads")

users_db = [] # Foydalanuvchilar bazasi (Railway-da vaqtinchalik)

# --- YORDAMCHI FUNKSIYALAR ---
async def check_sub(user_id):
    """Kanalga obunani tekshirish"""
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except:
        return False

# --- ASOSIY HANDLERLAR ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    name = message.from_user.first_name or "Do'stim"
    
    if not any(u['ID'] == user_id for u in users_db):
        users_db.append({
            "T/r": len(users_db) + 1, "ID": user_id, "Ism": name,
            "Username": f"@{message.from_user.username}" if message.from_user.username else "",
            "Sana": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    if await check_sub(user_id):
        await message.answer(f"Xush kelibsiz, {name}! 😊\nQo'shiq nomi yoki havola yuboring, men darhol topaman! ✨")
    else:
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Obuna bo'lish 📢", url=f"https://t.me/{CHANNEL_ID[1:]}")],
            [InlineKeyboardButton(text="Tasdiqlash ✅", callback_data="check_sub")]
        ])
        await message.answer(f"Assalomu alaykum, {name}! ✨\nBotdan foydalanish uchun kanalga obuna bo'ling:", reply_markup=btn)

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        await call.message.answer("Obuna tasdiqlandi! ✅\nEndi bemalol qo'shiq qidirishingiz mumkin. ✨")
    else:
        await call.answer("Siz hali obuna bo'lmagansiz! ❌", show_alert=True)

@dp.message(F.text)
async def search_handler(message: types.Message):
    if message.text.startswith("/"): return
    name = message.from_user.first_name or "Do'stim"
    
    if not await check_sub(message.from_user.id):
        return await message.answer(f"Kechirasiz {name}, avval kanalga obuna bo'ling! ☺️")

    query = message.text
    
    if query.startswith("http"):
        sent_msg = await message.answer(f"🔗 {name}, havola tahlil qilinmoqda... ⌛️")
        try:
            with YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(query, download=False)
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📹 Videoni yuklash (Klip)", callback_data=f"dl_vid|{query}")],
                    [InlineKeyboardButton(text="🎵 Audioni ajratish (MP3)", callback_data=f"dl_aud|{query}")],
                    [InlineKeyboardButton(text="🔍 Qo'shiqni topish (Shazam)", callback_data=f"shazam|{query}")]
                ])
                await sent_msg.edit_text(f"✅ Havola aniqlandi, {name}!\n\n📌 **{info.get('title')}**\n\nNima yuklaymiz? 👇", reply_markup=kb)
        except:
            await sent_msg.edit_text(f"Uzr {name}, havolada xatolik bor. 😔")
    else:
        sent_msg = await message.answer(f"🔍 {name}, '{query}' qidirilmoqda... ⌛️")
        try:
            ydl_opts = {'quiet': True, 'noplaylist': True}
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch10:{query}", download=False)
                results = info.get('entries', [])
                if not results: return await sent_msg.edit_text("Hech narsa topilmadi. 😔")
                
                kb_list = [[InlineKeyboardButton(text=f"{i+1}. {res['title'][:45]}...", callback_data=f"select|{res['webpage_url']}")] for i, res in enumerate(results)]
                await sent_msg.edit_text(f"🌟 {name}, 10 ta variant topildi: 👇", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))
        except:
            await sent_msg.edit_text("Qidiruvda xatolik yuz berdi... ✨")

@dp.callback_query(F.data.startswith("select|"))
async def select_callback(call: types.CallbackQuery):
    url = call.data.split("|")[1]
    name = call.from_user.first_name
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎵 MP3 yuklash", callback_data=f"dl_aud|{url}")],
        [InlineKeyboardButton(text="📹 Videoni yuklash (Klip)", callback_data=f"dl_vid|{url}")]
    ])
    await call.message.edit_text(f"Ajoyib tanlov, {name}! 😍\nFormatni tanlang: 👇", reply_markup=kb)

@dp.callback_query(F.data.startswith("dl_"))
async def download_callback(call: types.CallbackQuery):
    action, url = call.data.split("|")
    name = call.from_user.first_name
    file_type = "MP3" if action == "dl_aud" else "Klip"
    
    msg = await call.message.answer(f"🚀 Xo'p bo'ladi, {name}! \n{file_type} tayyorlanmoqda... ⌛️")

    try:
        ydl_opts = {
            'format': 'bestaudio/best' if action == "dl_aud" else 'bestvideo+bestaudio/best',
            'outtmpl': f'downloads/%(title)s {BOT_USERNAME}.%(ext)s',
            'quiet': True,
        }
        
        if action == "dl_aud":
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
            if action == "dl_aud":
                path = path.rsplit(".", 1)[0] + ".mp3"

        file = FSInputFile(path)
        
        if action == "dl_aud":
            # MP3 tagida Klip tugmasi (rasmdagi kabi)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📹 Klipni ham yuklaysizmi?", callback_data=f"dl_vid|{url}")]
            ])
            await call.message.answer_audio(file, caption=CAPTION_TEXT, reply_markup=kb)
        else:
            await call.message.answer_video(file, caption=CAPTION_TEXT)
        
        await msg.delete()
        if os.path.exists(path): os.remove(path)

    except Exception as e:
        logging.error(e)
        await call.message.answer(f"Kechirasiz {name}, yuklashda xato bo'ldi. 😔")

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Excel yuklash", callback_data="get_excel")]
        ])
        await message.answer(f"📊 **Statistika**\n\nFoydalanuvchilar: {len(users_db)}", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "get_excel")
async def export_excel(call: types.CallbackQuery):
    df = pd.DataFrame(users_db)
    df.to_excel("users.xlsx", index=False)
    await call.message.answer_document(FSInputFile("users.xlsx"))
    os.remove("users.xlsx")

# --- BOTNI ISHGA TUSHIRISH ---
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("-" * 30)
    print("TECHPRO: Bot muvaffaqiyatli ishga tushdi! ✅")
    print(f"Boshlangan vaqt: {datetime.now().strftime('%H:%M:%S')}")
    print("-" * 30)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())