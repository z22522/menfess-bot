CHANNEL_ID = -1003977431320

import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler, MessageHandler,
    CommandHandler, ContextTypes, filters)

users = {}
banned_users = set()
message_tracker = {}

user_last_active = {}
user_tasks = {}
cancel_flag = set()

IDLE_TIME = 180

def check_limit(user_id):
    today = datetime.now().date()

    if user_id not in users:
        users[user_id] = {"count": 0, "date": today}

    if users[user_id]["date"] != today:
        users[user_id]["count"] = 0
        users[user_id]["date"] = today

        if user_id in banned_users:
            banned_users.remove(user_id)

    return users[user_id]["count"] < 2

async def track_message(msg, user_id):
    if user_id not in message_tracker:
        message_tracker[user_id] = []

    if msg:
        message_tracker[user_id].append(msg.message_id)

    if len(message_tracker[user_id]) > 30:
        message_tracker[user_id].pop(0)

async def clear_chat(update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    for msg_id in message_tracker.get(user_id, []):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except:
            pass

    message_tracker[user_id] = []

async def idle_reset(user_id, context, chat_id):
    await asyncio.sleep(IDLE_TIME)

    if user_last_active.get(user_id) != "active":
        return

    user_last_active.pop(user_id, None)

    for msg_id in message_tracker.get(user_id, []):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except:
            pass

    message_tracker[user_id] = []


def restart_idle(user_id, context, chat_id):
    user_last_active[user_id] = "active"

    task = user_tasks.get(user_id)
    if task:
        task.cancel()

    user_tasks[user_id] = asyncio.create_task(
        idle_reset(user_id, context, chat_id)
    )


async def remove_inline_kb(context, chat_id, message_id):
    await asyncio.sleep(6)

    try:
        await context.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None)
    except:
        pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Kirim Menfess💌", callback_data="start_mf")]]

    msg = await update.message.reply_text(
        "Halo, selamat datang di KPS Menfess",
        reply_markup=InlineKeyboardMarkup(keyboard))
    await track_message(msg, update.effective_user.id)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    restart_idle(user_id, context, query.message.chat.id)

    if query.data == "start_mf":
        context.user_data.clear()
        cancel_flag.discard(user_id)

        msg = await query.message.reply_text("Isi username tujuan (contoh @sawit)")
        await track_message(msg, user_id)

        context.user_data["step"] = "to"

    elif query.data == "cancel":
        cancel_flag.add(user_id)

        msg = await query.message.reply_text("<i>❌ Menfess dibatalkan</i>", parse_mode="HTML")

        context.user_data.clear()
        await clear_chat(query, context)

    elif query.data == "media_text":
        msg = await query.message.reply_text("Ketik pesan kamu")
        await track_message(msg, user_id)
        context.user_data["step"] = "message"

    elif query.data == "media_photo":
        msg = await query.message.reply_text("Kirim foto kamu")
        await track_message(msg, user_id)
        context.user_data["step"] = "photo"

    elif query.data == "media_video":
        msg = await query.message.reply_text("Kirim video kamu")
        await track_message(msg, user_id)
        context.user_data["step"] = "video"

    elif query.data == "media_audio":
        msg = await query.message.reply_text("Kirim audio kamu")
        await track_message(msg, user_id)
        context.user_data["step"] = "audio"

    elif query.data == "anon":
        context.user_data["from"] = "Anonymous"

        asyncio.create_task(
            remove_inline_kb(
                context,
                query.message.chat.id,
                query.message.message_id
            )
        )

        await lanjut_kirim(query, context)

    elif query.data == "show_user":
        username = query.from_user.username or "user"
        context.user_data["from"] = f"@{username}"

        asyncio.create_task(
            remove_inline_kb(
                context,
                query.message.chat.id,
                query.message.message_id
            )
        )

        await lanjut_kirim(query, context)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    restart_idle(user_id, context, update.effective_chat.id)

    if user_id in banned_users or user_id in cancel_flag:
        return

    step = context.user_data.get("step")

    if step == "to":
        target = update.message.text.strip()

        if not target.startswith("@"):
            msg = await update.message.reply_text("Username tidak ditemukan")
            await track_message(msg, user_id)
            return

        context.user_data["to"] = target

        keyboard = [
            [InlineKeyboardButton("Hanya Pesan", callback_data="media_text")],
            [InlineKeyboardButton("Foto", callback_data="media_photo")],
            [InlineKeyboardButton("Video", callback_data="media_video")],
            [InlineKeyboardButton("Audio", callback_data="media_audio")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]

        msg = await update.message.reply_text(
            "Pilih jenis menfess",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await track_message(msg, user_id)

    elif step in ["message", "final_message"]:
        context.user_data["message"] = update.message.text

        keyboard = [
            [InlineKeyboardButton("Anonymous", callback_data="anon")],
            [InlineKeyboardButton("Tampilkan Username", callback_data="show_user")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]

        msg = await update.message.reply_text(
            "Kirim sebagai",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await track_message(msg, user_id)


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    restart_idle(user_id, context, update.effective_chat.id)

    if user_id in banned_users or user_id in cancel_flag:
        return

    step = context.user_data.get("step")

    if step not in ["photo", "video", "audio"]:
        return

    context.user_data["file"] = update.message

    msg = await update.message.reply_text("Ketik pesan kamu")
    await track_message(msg, user_id)

    context.user_data["step"] = "final_message"


async def lanjut_kirim(query, context):
    user_id = query.from_user.id

    if user_id in banned_users or user_id in cancel_flag:
        return

    if not check_limit(user_id):
        banned_users.add(user_id)

        msg = await query.message.reply_text(
            "<i>Kuota menfess kamu sudah habis hari ini</i>",
            parse_mode="HTML"
        )
        await track_message(msg, user_id)
        return

    users[user_id]["count"] += 1

    await send_menfess(query, context, context.user_data.get("file"))


async def send_menfess(query, context, msg):
    data = context.user_data

    caption = f"""💌 MENFESS MESSAGE

From : {data.get("from") or "Anonymous"}
To : {data.get("to") or "-"}
Pesan :
{data.get("message") or "-"}
"""

    if msg and msg.photo:
        await context.bot.send_photo(CHANNEL_ID, msg.photo[-1].file_id, caption=caption)

    elif msg and msg.video:
        await context.bot.send_video(CHANNEL_ID, msg.video.file_id, caption=caption)

    elif msg and msg.audio:
        await context.bot.send_audio(CHANNEL_ID, msg.audio.file_id, caption=caption)

    else:
        await context.bot.send_message(CHANNEL_ID, caption)

    done = await query.message.reply_text("<i>✅ berhasil dikirim</i>", parse_mode="HTML")
    await track_message(done, query.from_user.id)

    await clear_chat(query, context)

    context.user_data.clear()
    cancel_flag.discard(query.from_user.id)


app = ApplicationBuilder().token("8747893603:AAErGjDLwqKvuW5oLlptWaq-ei8kboPt2dE").build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO, handle_media))

app.run_polling()