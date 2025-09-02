# views.py (Refactored Version)

import csv
import io
import logging
import os
import subprocess
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.utils.timezone import now
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, ContextTypes, ConversationHandler
from .tasks import start_broadcast_task
# Loyihaning lokal modullari
from .keyboard import *
from .models import User, Location, Language, Broadcast  # Language modelini import qilish
from .utils import update_or_create_user, admin_only

logger = logging.getLogger(__name__)


async def get_user_statistics(bot_username: str) -> dict:
    """Foydalanuvchilarning umumiy va faol soni haqida statistika qaytaradi."""
    user_count = await User.objects.filter(bot__username=bot_username).acount()
    active_24_count = await User.objects.filter(
        bot__username=bot_username,
        updated_at__gte=now() - timedelta(hours=24)
    ).acount()
    return {"total": user_count, "active_24h": active_24_count}


async def perform_database_backup():
    """
    Ma'lumotlar bazasining zaxira nusxasini yaratadi.

    WARNING: Tashqi shell komandalarini to'g'ridan-to'g'ri `subprocess` orqali ishga tushirish,
    ayniqsa `shell=True` bilan, xavfsizlik zaifliklariga (masalan, shell injection) olib
    kelishi mumkin. Iloji bo'lsa, Django management commands yoki maxsus kutubxonalardan
    foydalanish tavsiya etiladi.
    """
    db_engine = settings.DATABASES['default']['ENGINE']
    db_config = settings.DATABASES['default']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dump_file = None
    command = None

    try:
        if 'postgresql' in db_engine:
            dump_file = f"backup_{timestamp}.sql"
            os.environ['PGPASSWORD'] = db_config['PASSWORD']
            command = (
                f"pg_dump -U {db_config['USER']} -h {db_config['HOST']} "
                f"-p {db_config['PORT']} {db_config['NAME']} > {dump_file}"
            )
        elif 'sqlite3' in db_engine:
            dump_file = f"backup_{timestamp}.sqlite3"
            command = f"sqlite3 {db_config['NAME']} .dump > {dump_file}"
        else:
            return None, "Unsupported database engine."

        process = await sync_to_async(subprocess.run)(
            command, shell=True, check=True, capture_output=True, text=True
        )
        return dump_file, None
    except subprocess.CalledProcessError as e:
        logger.error(f"Backup failed. Return code: {e.returncode}\nError: {e.stderr}")
        return None, e.stderr
    except Exception as e:
        logger.error(f"An unexpected error occurred during backup: {e}")
        return None, str(e)


def generate_csv_from_users(users_data) -> io.BytesIO:
    """Foydalanuvchilar ma'lumotidan CSV fayl yaratadi."""
    if not users_data:
        return io.BytesIO(b"No data available")

    string_io = io.StringIO()
    writer = csv.DictWriter(string_io, fieldnames=users_data[0].keys())
    writer.writeheader()
    writer.writerows(users_data)
    string_io.seek(0)
    return io.BytesIO(string_io.getvalue().encode('utf-8'))


# --- User Handlers ---

@update_or_create_user
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, user, language):
    if user.selected_language is None:
        await ask_language(update, context)
        return

    full_name = user.full_name
    await update.message.reply_text(
        translation.start_not_created[language].format(full_name),
        reply_markup=default_keyboard(language, admin=user.is_admin)
    )


@update_or_create_user
async def ask_language(update: Update, context: ContextTypes.DEFAULT_TYPE, user, language):
    await update.message.reply_text(translation.ask_language_text[language], reply_markup=language_list_keyboard())


@update_or_create_user
async def language_choice_handle(update: Update, context: CallbackContext, user, language):
    query = update.callback_query
    lang_code = query.data.split("language_setting_")[-1]

    # Til nomini hardcode qilish o'rniga, modeldagi `choices`dan olish mumkin
    # Masalan: lang_name = Language(lang_code).label
    lang_name = dict(Language.choices).get(lang_code, lang_code.capitalize())

    user.selected_language = lang_code
    await sync_to_async(user.save)()

    await query.answer(f"{translation.choice_language[lang_code]} {lang_name}")
    await query.edit_message_text(f"{translation.choice_language[lang_code]} {lang_name}")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=translation.restart_text[lang_code],
        reply_markup=restart_keyboard(lang=lang_code)
    )


@update_or_create_user
async def about(update: Update, context: CallbackContext, user, language) -> None:
    reply_markup = make_keyboard_for_about_command(language, admin=user.is_admin)
    await update.message.reply_text(
        translation.about_message[language],
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )


@update_or_create_user
async def help(update: Update, context: CallbackContext, user, language) -> None:
    text = translation.start_not_created[language].format(user.full_name)
    await update.message.reply_text(
        text + translation.help_message[language],
        parse_mode=ParseMode.HTML,
        reply_markup=make_keyboard_for_help_command()
    )


@update_or_create_user
async def share_bot(update: Update, context: CallbackContext, user, language) -> None:
    await update.message.reply_text(
        translation.share_bot_text[language],
        reply_markup=share_bot_keyboard(lang=language)
    )


@update_or_create_user
async def ask_for_location(update: Update, context: CallbackContext, user, language) -> None:
    await context.bot.send_message(
        chat_id=user.telegram_id,
        text=translation.share_location,
        reply_markup=send_location_keyboard()
    )


@update_or_create_user
async def location_handler(update: Update, context: CallbackContext, user, language) -> None:
    location = update.message.location
    await Location.objects.acreate(user=user, latitude=location.latitude, longitude=location.longitude)
    await update.message.reply_text(
        translation.thanks_for_location,
        reply_markup=default_keyboard(language, admin=user.is_admin)
    )


@update_or_create_user
async def check_subscription_channel(update: Update, context: CallbackContext, user, language) -> None:
    query = update.callback_query
    reply_markup, subscribed_status = await keyboard_checked_subscription_channel(user.telegram_id, context.bot)

    if query.message.reply_markup == reply_markup:
        await query.answer()  # Foydalanuvchiga hech narsa o'zgarmaganini bildirish
        return

    if subscribed_status:
        await query.edit_message_text(translation.full_permission[language])
    else:
        await query.edit_message_reply_markup(reply_markup)
        await query.answer(translation.not_subscribed[language], show_alert=True)


# --- Admin Handlers ---

@admin_only
async def admin(update: Update, context: CallbackContext, user) -> None:
    await update.message.reply_text(translation.secret_admin_commands)


@admin_only
async def stats(update: Update, context: CallbackContext, user) -> None:
    stats_data = await get_user_statistics(context.bot.username)
    text = translation.users_amount_stat.format(
        user_count=stats_data["total"],
        active_24=stats_data["active_24h"]
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


@admin_only
async def backup_db(update: Update, context: CallbackContext, user) -> None:
    await update.message.reply_text("⏳ Starting database backup...")
    dump_file, error = await perform_database_backup()

    if dump_file and not error:
        try:
            with open(dump_file, 'rb') as f:
                await update.message.reply_document(document=f, filename=dump_file,
                                                    caption="Database backup successful.")
        finally:
            os.remove(dump_file)  # Faylni yuborilgandan keyin o'chirish
    else:
        await update.message.reply_text(f"🔴 Failed to perform database backup. Error:\n{error}")


@admin_only
async def export_users(update: Update, context: CallbackContext, user) -> None:
    users_data = await sync_to_async(list)(User.objects.values())
    csv_file = await sync_to_async(generate_csv_from_users)(users_data)

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=csv_file,
        filename="users_export.csv",
        caption="Exported user data."
    )


@admin_only
async def secret_level(update: Update, context: CallbackContext, user) -> None:
    query = update.callback_query
    stats_data = await get_user_statistics(context.bot.username)
    lang = user.selected_language or user.stock_language
    text = translation.unlock_secret_room[lang].format(
        user_count=stats_data["total"],
        active_24=stats_data["active_24h"]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML)


# Suhbat holatlari uchun konstantalar
AWAIT_BROADCAST_MESSAGE = 1


# ... (get_user_statistics, backup_db kabi servis funksiyalari o'zgarishsiz qoladi) ...

# --- User Handlers (start, ask_language, about, etc. o'zgarishsiz qoladi) ---
# ...

# --- Broadcast Conversation Handlers ---

@admin_only
async def start_broadcast_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE, user) -> int:
    """Admindan reklama xabarini forward qilishni so'raydi."""
    await update.message.reply_text(
        "Reklama uchun tayyor xabarni forward qiling.\n"
        "Suhbatni bekor qilish uchun /cancel buyrug'ini bering."
    )
    return AWAIT_BROADCAST_MESSAGE


@admin_only
async def receive_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user) -> int:
    """Admin tomonidan yuborilgan xabarni inline tugmalar bilan tasdiqlashga chiqaradi."""
    message = update.message
    callback_prefix = f"brdcast_{message.chat_id}_{message.message_id}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Hozir yuborish", callback_data=f"{callback_prefix}_send_now")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data=f"{callback_prefix}_cancel")]
    ])

    await update.message.reply_text(
        "Ushbu xabar barcha foydalanuvchilarga yuborilsinmi?", reply_markup=keyboard
    )
    return ConversationHandler.END


@admin_only
async def cancel_broadcast_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE, user) -> int:
    """Suhbatni bekor qiladi."""
    await update.message.reply_text("Reklama yaratish bekor qilindi.")
    return ConversationHandler.END


@admin_only
async def handle_broadcast_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, user) -> None:
    """Tasdiqlash tugmasi bosilganda ishga tushadi."""
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    action = data[-1]
    from_chat_id = int(data[1])
    message_id = int(data[2])

    bot_instance = context.bot_data.get("bot_instance")
    print("Action:", action)

    if action == "cancel":
        await query.edit_message_text("❌ Reklama bekor qilindi.")
        return

    if action == "now":
        await query.edit_message_text("⏳ Yuborilmoqda...")
        broadcast = await Broadcast.objects.acreate(
            bot=bot_instance,
            from_chat_id=from_chat_id,
            message_id=message_id,
            scheduled_time=timezone.now(),
            status=Broadcast.Status.PENDING
        )

        # Bazaga yozilishi tugashini kutib bo'lgach, Celery task chaqirish
        start_broadcast_task.delay(broadcast.id)
        await query.edit_message_text(f"✅ Reklama (ID: {broadcast.id}) navbatga qo'yildi!")

