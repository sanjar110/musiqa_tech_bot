import os
import asyncio
import logging
import re
import time
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from yt_dlp import YoutubeDL
from shazamio import Shazam

# --- 1. SOZLAMALAR ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

# O'zgaruvchilarni olish va himoyalash
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
try:
    # Railway Variables'da ADMIN_ID bo'sh bo'lsa xato bermasligi uchun default 0
    ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
except (ValueError, TypeError):
    ADMIN_ID = 0

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
shazam = Shazam()

BOT_USERNAME = "@tech_musiqa_bot"
CAPTION_TEXT = f"🎶 {BOT_USERNAME} orqali yuklandi. ✅\n💻 Dasturchi: TECHPRO"

# Yuklamalar uchun papka (To'liq yo'l bilan)
DOWNLOAD_PATH = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# Foydalanuvchilar bazasi
users_db = []

# --- 2. YORDAMCHI FUNKSIYALAR ---
def clean_filename(title):
    """Fayl nomidagi taqiqlangan belgilarni tozalash"""
    return re.sub(r'[\\/*?:"<>|]', "", title).strip()

async def check_sub(user_id):
    """Kanalga obunani tekshirish (Agar CHANNEL_ID bo'lmasa True qaytaradi)"""
    if not CHANNEL_ID:
        return True
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

def progress_hook(d, message, last_update_time):
    """Yuklash foizini ko'rsatuvchi hook"""
    if d['status'] == 'downloading':
        p = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', '0KB/s')
        eta = d.get('_eta_str', '00:00')
        total = d.get('_total_bytes_str', d.get('_total_bytes_estimate_str', 'Noma\'lum'))
        
        current_time = time.time()
        # Har 2 soniyada yangilash (Telegram Flood limitdan himoya)
        if current_time - last_update_time[0] > 2.0:
            text = (f"🚀 **Yuklanmoqda:** {p}\n"
                    f"📦 **Hajmi:** {total}\n"
                    f"⚡ **Tezlik:** {speed}\n"
                    f"⏳ **Qolgan vaqt:** {eta}")
            
            loop = asyncio.get_event_loop()
            loop.create_task(message.edit_text(text, parse_mode="Markdown"))
            last_update_time[0] = current_time
    
    elif d['status'] == 'finished':
        loop = asyncio.get_event_loop()
        loop.create_task(message.edit_text("✅ Yuklash yakunlandi! Fayl qayta ishlanmoqda..."))

# --- 3. YUKLASH MARKAZI ---
async def universal_downloader(call, action, url):
    sent_msg = await call.message.edit_text("📥 Yuklashga tayyorlanmoqda, kuting... ⌛️")
    last_update = [time.time()]
    
    try:
        ext = "mp3" if action == "dl_aud" else "mp4"
        ydl_opts = {
            'format': 'bestaudio/best' if action == "dl_aud" else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': f'{DOWNLOAD_PATH}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [lambda d: progress_hook(d, sent_msg, last_update)],
            'prefer_ffmpeg': True,
        }
        
        if action == "dl_aud":
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        with YoutubeDL(ydl_opts) as ydl:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            title = clean_filename(info.get('title', 'media_file'))
            
            old_path = ydl.prepare_filename(info)
            if action == "dl_aud":
                old_path = old_path.rsplit(".", 1)[0] + ".mp3"
            
            new_path = os.path.join(DOWNLOAD_PATH, f"{title}.{ext}")
            if os.path.exists(old_path):
                os.rename(old_path, new_path)

        file = FSInputFile(new_path)
        if action == "dl_aud":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📹 Klipni yuklash", callback_data=f"get_clip|{title}")]
            ])
            await call.message.answer_audio(file, caption=CAPTION_TEXT, reply_markup=kb)
        else:
            await call.message.answer_video(file, caption=CAPTION_TEXT)
        
        await sent_msg.delete()
        if os.path.exists(new_path):
            os.remove(new_path)
        
    except Exception as e:
        logging.error(f"Download Error: {e}")
        await sent_msg.edit_text("❌ Xatolik: Fayl juda katta yoki serverda FFmpeg o'rnatilmagan.")

# --- 4. HANDLERLAR ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    if not any(u['ID'] == user_id for u in users_db):
        users_db.append({
            "T/r": len(users_db) + 1,
            "ID": user_id,
            "Ism": message.from_user.first_name or "User",
            "Sana": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    if await check_sub(user_id):
        await message.answer(f"Xush kelibsiz! 😊\nQo'shiq nomi yoki havolani yuboring.")
    else:
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Obuna bo'lish 📢", url=f"https://t.me/{CHANNEL_ID[1:]}")],
            [InlineKeyboardButton(text="Tasdiqlash ✅", callback_data="check_sub")]
        ])
        await message.answer("Botdan foydalanish uchun kanalimizga obuna bo'ling:", reply_markup=btn)

@dp.callback_query(F.data == "check_sub")
async def sub_callback(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        await call.message.answer("Tasdiqlandi! ✅ Marhamat, foydalanishingiz mumkin.")
    else:
        await call.answer("Siz hali obuna bo'lmagansiz! ❌", show_alert=True)

@dp.message(F.text)
async def handle_text(message: types.Message):
    if message.text.startswith("/") or not await check_sub(message.from_user.id):
        return

    query = message.text.strip()
    sent_msg = await message.answer("🔍 Qidirilmoqda... kuting.")

    if query.startswith("http"):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📹 Video", callback_data=f"dl_vid|{query}"),
             InlineKeyboardButton(text="🎵 MP3", callback_data=f"dl_aud|{query}")],
            [InlineKeyboardButton(text="🔍 Shazam", callback_data=f"shazam|{query}")]
        ])
        await sent_msg.edit_text(f"🎬 Media aniqlandi!\nNima yuklaymiz?", reply_markup=kb)
    else:
        try:
            with YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                info = ydl.extract_info(f"ytsearch7:{query}", download=False)
                res = info.get('entries', [])
                if not res: return await sent_msg.edit_text("Topilmadi. 😔")
                
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"🎵 {r['title'][:40]}", callback_data=f"dl_aud|{r['url']}")] for r in res
                ])
                await sent_msg.edit_text(f"🔍 '{query}' bo'yicha natijalar:", reply_markup=kb)
        except Exception:
            await sent_msg.edit_text("Qidiruvda xato bo'ldi. 😔")

@dp.callback_query(F.data.startswith("dl_"))
async def direct_dl(call: types.CallbackQuery):
    action, url = call.data.split("|", 1)
    await universal_downloader(call, action, url)

@dp.callback_query(F.data.startswith("get_clip|"))
async def clip_dl(call: types.CallbackQuery):
    title = call.data.split("|", 1)[1]
    with YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
        info = ydl.extract_info(f"ytsearch1:{title} official video", download=False)
        if info['entries']:
            await universal_downloader(call, "dl_vid", info['entries'][0]['url'])
        else:
            await call.answer("Klip topilmadi. 😔", show_alert=True)

@dp.callback_query(F.data.startswith("shazam|"))
async def shazam_dl(call: types.CallbackQuery):
    url = call.data.split("|", 1)[1]
    msg = await call.message.edit_text("🔍 Qo'shiqni tahlil qilyapman... 🎧")
    temp = os.path.join(DOWNLOAD_PATH, f"shazam_{call.from_user.id}.mp3")
    
    try:
        with YoutubeDL({'format': 'bestaudio', 'outtmpl': temp, 'quiet': True, 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]}) as ydl:
            ydl.download([url])
        
        out = await shazam.recognize(temp)
        if 'track' in out:
            t, a = out['track']['title'], out['track']['subtitle']
            with YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                sh_res = ydl.extract_info(f"ytsearch1:{a} {t}", download=False)
                if sh_res['entries']:
                    await universal_downloader(call, "dl_aud", sh_res['entries'][0]['url'])
        else:
            await msg.edit_text("Asli topilmadi. 🤷‍♂️")
    finally:
        if os.path.exists(temp): os.remove(temp)

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Excel yuklash", callback_data="get_excel")]
        ])
        await message.answer(f"📊 **Statistika**\n\nFoydalanuvchilar: {len(users_db)}", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "get_excel")
async def excel_export(call: types.CallbackQuery):
    if not users_db: return await call.answer("Baza bo'sh!")
    df = pd.DataFrame(users_db)
    path = "users.xlsx"
    df.to_excel(path, index=False)
    await call.message.answer_document(FSInputFile(path), caption="Foydalanuvchilar ro'yxati")
    os.remove(path)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot TECHPRO tomonidan ishga tushirildi! ✅")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        print("Bot to'xtadi.")