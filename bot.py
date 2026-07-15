# ============================================================
# ربات تلگرام دانلود یوتوب
# فایل: bot.py
# ============================================================
# توکن ربات را اینجا قرار دهید ↓↓↓
#BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
# ============================================================
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set.")

#import os
import re
import asyncio
import tempfile
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import yt_dlp

# ذخیره URL موقت برای هر کاربر
user_urls: dict = {}

def is_youtube_url(url: str) -> bool:
    pattern = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+'
    return bool(re.match(pattern, url))

def get_video_info(url: str) -> dict:
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! به ربات دانلود یوتوب خوش آمدید\n\n"
        "🔗 کافیه لینک یوتوب رو برام بفرستی\n"
        "📥 بعدش کیفیت دانلود رو انتخاب کن\n\n"
        "✅ پشتیبانی از:\n"
        "• ویدیو در کیفیت‌های مختلف (144p تا 1080p)\n"
        "• فایل صوتی MP3\n\n"
        "⚠️ حداکثر حجم فایل: 50 مگابایت",
        parse_mode='Markdown'
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not is_youtube_url(url):
        await update.message.reply_text("❌ لینک یوتوب معتبر نیست! لطفاً لینک صحیح ارسال کنید.")
        return

    msg = await update.message.reply_text("⏳ در حال دریافت اطلاعات ویدیو...")
    try:
        info = get_video_info(url)
        title = info.get('title', 'ویدیو')
        duration = info.get('duration', 0)
        uploader = info.get('uploader', 'نامشخص')
        thumbnail = info.get('thumbnail', '')
        
        minutes = duration // 60
        seconds = duration % 60
        
        # ذخیره URL برای استفاده بعدی
        user_id = update.effective_user.id
        user_urls[user_id] = url
        
        # ساخت کیبورد انتخاب کیفیت
        keyboard = [
            [
                InlineKeyboardButton("🎵 MP3 صوتی", callback_data=f"audio|mp3"),
            ],
            [
                InlineKeyboardButton("📱 144p", callback_data=f"video|144"),
                InlineKeyboardButton("📱 240p", callback_data=f"video|240"),
                InlineKeyboardButton("📺 360p", callback_data=f"video|360"),
            ],
            [
                InlineKeyboardButton("📺 480p", callback_data=f"video|480"),
                InlineKeyboardButton("🖥️ 720p", callback_data=f"video|720"),
                InlineKeyboardButton("🖥️ 1080p", callback_data=f"video|1080"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        caption = (
            f"🎬 *{title}*\n\n"
            f"👤 کانال: {uploader}\n"
            f"⏱️ مدت: {minutes}:{seconds:02d}\n\n"
            f"📥 کیفیت دانلود را انتخاب کنید:"
        )
        
        await msg.delete()
        if thumbnail:
            await update.message.reply_photo(
                photo=thumbnail,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                caption,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        await msg.edit_text(f"❌ خطا در دریافت اطلاعات: {str(e)}")

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    url = user_urls.get(user_id)
    
    if not url:
        await query.edit_message_text("❌ لینک یوتوب یافت نشد. دوباره لینک ارسال کنید.")
        return
    
    data = query.data.split("|")
    dl_type = data[0]  # audio یا video
    quality = data[1] if len(data) > 1 else "best"
    
    await query.edit_message_caption(
        caption="⏳ در حال دانلود... لطفاً صبر کنید",
        reply_markup=None
    ) if hasattr(query.message, 'caption') else await query.edit_message_text(
        "⏳ در حال دانلود... لطفاً صبر کنید"
    )
    
    chat_id = update.effective_chat.id
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            if dl_type == "audio":
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'quiet': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    title = info.get('title', 'audio')
                    fname = os.path.join(tmpdir, f"{title}.mp3")
                    # پیدا کردن فایل
                    files = os.listdir(tmpdir)
                    mp3_files = [f for f in files if f.endswith('.mp3')]
                    if mp3_files:
                        fname = os.path.join(tmpdir, mp3_files[0])
                    
                    if os.path.exists(fname):
                        size_mb = os.path.getsize(fname) / (1024 * 1024)
                        if size_mb > 50:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=f"❌ فایل بزرگتر از 50 مگابایت است ({size_mb:.1f}MB). دانلود ممکن نیست."
                            )
                            return
                        await context.bot.send_audio(
                            chat_id=chat_id,
                            audio=open(fname, 'rb'),
                            caption=f"🎵 {title}",
                            read_timeout=120,
                            write_timeout=120
                        )
            else:
                # دانلود ویدیو با کیفیت انتخابی
                if quality == "1080":
                    fmt = f'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best'
                elif quality == "720":
                    fmt = f'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
                elif quality == "480":
                    fmt = f'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best'
                elif quality == "360":
                    fmt = f'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best'
                elif quality == "240":
                    fmt = f'bestvideo[height<=240][ext=mp4]+bestaudio[ext=m4a]/best[height<=240][ext=mp4]/best'
                elif quality == "144":
                    fmt = f'bestvideo[height<=144][ext=mp4]+bestaudio[ext=m4a]/best[height<=144][ext=mp4]/best'
                else:
                    fmt = 'best[ext=mp4]/best'
                
                ydl_opts = {
                    'format': fmt,
                    'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
                    'merge_output_format': 'mp4',
                    'quiet': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    title = info.get('title', 'video')
                    files = os.listdir(tmpdir)
                    mp4_files = [f for f in files if f.endswith('.mp4')]
                    if mp4_files:
                        fname = os.path.join(tmpdir, mp4_files[0])
                        size_mb = os.path.getsize(fname) / (1024 * 1024)
                        if size_mb > 50:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=f"❌ فایل {size_mb:.1f}MB است و از 50MB بیشتر است. کیفیت پایین‌تری انتخاب کنید."
                            )
                            return
                        await context.bot.send_video(
                            chat_id=chat_id,
                            video=open(fname, 'rb'),
                            caption=f"🎬 {title} ({quality}p)",
                            supports_streaming=True,
                            read_timeout=120,
                            write_timeout=120
                        )
        except Exception as e:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ خطا در دانلود:\n{str(e)}"
            )
        finally:
            # پاک کردن URL کاربر
            if user_id in user_urls:
                del user_urls[user_id]

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_download))
    print("✅ ربات در حال اجراست...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
