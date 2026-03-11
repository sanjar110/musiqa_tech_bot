import os
import asyncio
import logging
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

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
shazam = Shazam()

# Bot brendingi
BOT_USERNAME = "@tech_musiqa_bot"
CAPTION_TEXT = f"🎶 {BOT_USERNAME} orqali yuklandi. Eng sara musiqalar bizda! ✅\n💻 Dasturchi: TECHPRO"

if not os.path.exists("downloads"):
    os.makedirs("downloads")

users_db = [] # Vaqtinchalik baza (Idealda SQLite yoki PostgreSQL ishlatish tavsiya etiladi)

# --- YORDAMCHI FUNKSIYALAR ---
async def check_sub(user_id):
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f"Kanalni tekshirishda xatolik: {e}")
        return False

def clean_filename(title):
    keepcharacters = (' ', '.', '_')
    return "".join(c for c in title if c.isalnum() or c in keepcharacters).rstrip()

# --- ASOSIY HANDLERLAR ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    username = f"@{message.from_user.username}" if message.from_user.username else "Yo'q"
    
    if not any(u['ID'] == user_id for u in users_db):
        users_db.append({
            "T/r": len(users_db) + 1, 
            "ID": user_id, 
            "Ism": first_name,
            "Familiya": last_name,
            "Username": username,
            "Qo'shilgan sana": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    if await check_sub(user_id):
        await message.answer(f"Xush kelibsiz, {first_name}! 😊\nQo'shiq nomi, YouTube yoki Instagram havolasini yuboring! ✨")
    else:
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Obuna bo'lish 📢", url=f"https://t.me/{CHANNEL_ID[1:]}")],
            [InlineKeyboardButton(text="Tasdiqlash ✅", callback_data="check_sub")]
        ])
        await message.answer(f"Assalomu alaykum, {first_name}! ✨\nBotdan foydalanish uchun kanalga obuna bo'ling:", reply_markup=btn)

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        await call.message.answer("Obuna tasdiqlandi! ✅\nEndi bemalol izlash va yuklash imkoniyatidan foydalanishingiz mumkin. ✨")
    else:
        await call.answer("Siz hali obuna bo'lmagansiz! ❌", show_alert=True)

@dp.message(F.text)
async def search_handler(message: types.Message):
    if message.text.startswith("/"): return
    name = message.from_user.first_name or "Do'stim"
    
    if not await check_sub(message.from_user.id):
        return await message.answer(f"Kechirasiz {name}, avval kanalga obuna bo'ling! ☺️")

    query = message.text.strip()
    sent_msg = await message.answer("Biroz kuting, ma'lumot olinmoqda... ⌛️")
    
    # 1. HAVOLA YUBORILGANDA
    if query.startswith("http"):
        try:
            with YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(query, download=False)
                
                # Agar havola Instagram rasmi bo'lsa (video bo'lmasa)
                if info.get('ext') in ['jpg', 'jpeg', 'png', 'webp'] or not info.get('is_video', True):
                    await sent_msg.edit_text("🖼 Rasm yuklanmoqda...")
                    filepath = f"downloads/image_{message.message_id}.jpg"
                    ydl_opts = {'outtmpl': filepath, 'quiet': True}
                    with YoutubeDL(ydl_opts) as img_ydl:
                        img_ydl.download([query])
                    await message.answer_photo(FSInputFile(filepath), caption=CAPTION_TEXT)
                    os.remove(filepath)
                    await sent_msg.delete()
                    return

                # Agar havola video bo'lsa (YouTube/Instagram)
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📥 Videoni yuklash", callback_data=f"dl_vid|{query}")],
                    [InlineKeyboardButton(text="🎵 Audioni ajratish (MP3)", callback_data=f"dl_aud|{query}")],
                    [InlineKeyboardButton(text="🔍 Qo'shiqni topish (Shazam)", callback_data=f"shazam|{query}")]
                ])
                title = info.get('title', 'Video')
                await sent_msg.edit_text(f"✅ Havola aniqlandi!\n\n📌 **{title}**\n\nNima amal bajaramiz? 👇", reply_markup=kb)
        except Exception as e:
            logging.error(e)
            await sent_msg.edit_text("Uzr, havolani o'qishda xatolik yuz berdi. Bu yopiq profil yoki noto'g'ri havola bo'lishi mumkin. 😔")
            
    # 2. MATN ORQALI QIDIRUV (Qo'shiq / Artist)
    else:
        try:
            ydl_opts = {'quiet': True, 'noplaylist': True, 'extract_flat': True}
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch10:{query}", download=False)
                results = info.get('entries', [])
                if not results: return await sent_msg.edit_text("Hech narsa topilmadi. 😔")
                
                kb_list = [[InlineKeyboardButton(text=f"🎵 {res['title'][:35]}...", callback_data=f"dl_aud|{res['url']}")] for res in results]
                await sent_msg.edit_text(f"🌟 '{query}' bo'yicha natijalar:\n(Yuklash uchun ustiga bosing) 👇", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))
        except Exception as e:
            logging.error(e)
            await sent_msg.edit_text("Qidiruv tizimida xatolik yuz berdi... ✨")

# --- MEDIANI YUKLASH (Audio/Video) ---
@dp.callback_query(F.data.startswith("dl_"))
async def download_callback(call: types.CallbackQuery):
    action, url = call.data.split("|", 1)
    file_type = "MP3" if action == "dl_aud" else "Klip"
    msg = await call.message.edit_text(f"🚀 {file_type} tayyorlanmoqda, kuting... ⌛️")

    try:
        ydl_opts = {
            'format': 'bestaudio/best' if action == "dl_aud" else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': f'downloads/%(title)s.%(ext)s',
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
            original_title = info.get('title', 'Audio')
            clean_title = clean_filename(original_title)
            
            # Fayl nomini to'g'rilash
            if action == "dl_aud":
                path = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp3"
            else:
                path = ydl.prepare_filename(info)

            new_path = f"downloads/{clean_title}.{'mp3' if action == 'dl_aud' else 'mp4'}"
            if os.path.exists(path) and path != new_path:
                os.rename(path, new_path)
            else:
                new_path = path

        file = FSInputFile(new_path)
        
        if action == "dl_aud":
            # MP3 tagida rasmiy klipni yuklash tugmasi
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📹 Klipni ham yuklaysizmi?", callback_data=f"get_clip|{original_title}")]
            ])
            await call.message.answer_audio(file, caption=CAPTION_TEXT, reply_markup=kb)
        else:
            await call.message.answer_video(file, caption=CAPTION_TEXT)
        
        await msg.delete()
        if os.path.exists(new_path): os.remove(new_path)

    except Exception as e:
        logging.error(e)
        await msg.edit_text("Kechirasiz, mediani yuklashda serverda xato bo'ldi. 😔")

# --- SHAZAM (Videodan qo'shiqni topish) ---
@dp.callback_query(F.data.startswith("shazam|"))
async def shazam_callback(call: types.CallbackQuery):
    url = call.data.split("|", 1)[1]
    msg = await call.message.edit_text("🔍 Audiodan qo'shiq aslini qidiryapman, biroz kuting... 🎧")
    
    temp_audio = f"downloads/temp_{call.from_user.id}.mp3"
    try:
        # Videodan kichik qismini audiosini olish
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': temp_audio,
            'quiet': True,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
        
        # Shazam orqali tekshirish
        out = await shazam.recognize(temp_audio)
        if 'track' in out:
            track_title = out['track']['title']
            track_subtitle = out['track']['subtitle']
            full_name = f"{track_subtitle} - {track_title}"
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📥 Aslini MP3 qilib yuklash", callback_data=f"dl_shazam_aud|{full_name}")]
            ])
            await msg.edit_text(f"🎉 Topildi!\n\n🎤 Ijrochi: {track_subtitle}\n🎵 Qo'shiq: {track_title}", reply_markup=kb)
        else:
            await msg.edit_text("Kechirasiz, ushbu videodagi qo'shiq bazadan topilmadi. 🤷‍♂️")
            
        if os.path.exists(temp_audio): os.remove(temp_audio)
            
    except Exception as e:
        logging.error(e)
        await msg.edit_text("Xatolik yuz berdi. Boshqa havola sinab ko'ring.")
        if os.path.exists(temp_audio): os.remove(temp_audio)

@dp.callback_query(F.data.startswith("dl_shazam_aud|"))
async def dl_shazam_aud(call: types.CallbackQuery):
    query = call.data.split("|", 1)[1]
    await call.message.edit_text(f"🔍 '{query}' aslini qidiryapman...")
    
    try:
        with YoutubeDL({'quiet': True, 'noplaylist': True, 'extract_flat': True}) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if not info.get('entries'): return await call.message.edit_text("Asli topilmadi.")
            vid_url = info['entries'][0]['url']
            
        # Tap-tayyor download funksiyasiga yuboramiz
        call.data = f"dl_aud|{vid_url}"
        await download_callback(call)
    except:
        await call.message.edit_text("Qo'shiqni yuklab bo'lmadi.")

# --- RASMIY KLIPNI YUKLASH ---
@dp.callback_query(F.data.startswith("get_clip|"))
async def get_clip_callback(call: types.CallbackQuery):
    song_title = call.data.split("|", 1)[1]
    search_query = f"{song_title} official music video"
    msg = await call.message.edit_text(f"🎬 '{song_title}' klipi qidirilmoqda... ⌛️")
    
    try:
        with YoutubeDL({'quiet': True, 'noplaylist': True, 'extract_flat': True}) as ydl:
            info = ydl.extract_info(f"ytsearch1:{search_query}", download=False)
            if not info.get('entries'): return await msg.edit_text("Kechirasiz, ushbu qo'shiqning rasmiy klipi topilmadi. 😔")
            vid_url = info['entries'][0]['url']
            
        call.data = f"dl_vid|{vid_url}"
        await msg.delete()
        await download_callback(call)
    except Exception as e:
        logging.error(e)
        await msg.edit_text("Klipni yuklashda texnik xato yuz berdi. 😔")

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Excel formatda yuklash", callback_data="get_excel")]
        ])
        await message.answer(f"📊 **Statistika**\n\nJami foydalanuvchilar: {len(users_db)} ta", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "get_excel")
async def export_excel(call: types.CallbackQuery):
    if not users_db:
        return await call.answer("Baza hozircha bo'sh!", show_alert=True)
        
    df = pd.DataFrame(users_db)
    file_path = "users_stat.xlsx"
    df.to_excel(file_path, index=False)
    await call.message.answer_document(FSInputFile(file_path), caption="📊 Barcha foydalanuvchilar ro'yxati")
    os.remove(file_path)

# --- BOTNI ISHGA TUSHIRISH ---
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("-" * 40)
    print(f"{BOT_USERNAME} muvaffaqiyatli ishga tushdi! ✅")
    print(f"Vaqt: {datetime.now().strftime('%H:%M:%S')}")
    print("Dasturchi: TECHPRO")
    print("-" * 40)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nBot to'xtatildi! ❌")