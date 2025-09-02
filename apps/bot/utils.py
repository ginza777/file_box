# utils.py

from functools import wraps
from typing import Callable

from telegram import Update, Bot
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from . import translation


async def check_bot_is_admin_in_channel(channel_id: str, bot_token: str) -> bool:
    """
    Check if bot is admin in the specified channel
    """
    try:
        bot = Bot(token=bot_token)
        chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=bot.id)
        return chat_member.status in ['administrator', 'creator']
    except TelegramError as e:
        print(f"Error checking bot admin status: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error checking bot admin status: {e}")
        return False


async def get_bot_details_from_telegram(token: str) -> tuple:
    """
    Get bot details from Telegram API
    """
    try:
        bot = Bot(token=token)
        bot_info = await bot.get_me()
        return bot_info.first_name, bot_info.username
    except Exception as e:
        print(f"Error getting bot details: {e}")
        return "", ""


async def register_bot_webhook(token: str, webhook_url: str) -> str:
    """
    Register webhook URL with Telegram
    """
    try:
        bot = Bot(token=token)
        await bot.set_webhook(url=webhook_url)
        return webhook_url
    except Exception as e:
        print(f"Error setting webhook: {e}")
        return ""


def update_or_create_user(func: Callable):
    """
    Foydalanuvchini topadi yoki yaratadi. Faqat asosiy kirish nuqtalarida
    (masalan, /start) ishlatilishi kerak.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_data = update.effective_user
        if not user_data:
            return

        # Lazy import to avoid circular dependency
        from .models import User
        
        user, _ = await User.objects.aupdate_or_create(
            telegram_id=user_data.id,
            defaults={
                "first_name": user_data.first_name or "",
                "last_name": user_data.last_name or "",
                "username": user_data.username,
                "stock_language": user_data.language_code,
            }
        )
        user_language = user.selected_language or user.stock_language
        return await func(update, context, user=user, language=user_language, *args, **kwargs)

    return wrapper


def get_user(func: Callable):
    """
    Mavjud foydalanuvchini bazadan oladi. Agar topilmasa, /start ga yo'naltiradi.
    Bu tezkor dekorator bo'lib, bazaga yozish amalini bajarmaydi.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_data = update.effective_user
        if not user_data:
            return

        # Lazy import to avoid circular dependency
        from .models import User
        
        user = await User.objects.filter(telegram_id=user_data.id).afirst()
        if not user:
            await update.message.reply_text(translation.start_first)
            return

        user_language = user.selected_language or user.stock_language
        return await func(update, context, user=user, language=user_language, *args, **kwargs)

    return wrapper


def admin_only(func: Callable):
    """
    Decorator to check if user is admin before allowing access to admin functions
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_data = update.effective_user
        if not user_data:
            return

        # Lazy import to avoid circular dependency
        from .models import User
        
        user = await User.objects.filter(telegram_id=user_data.id).afirst()
        if not user or not user.is_admin:
            await update.message.reply_text("❌ Bu buyruq faqat adminlar uchun!")
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


def channel_subscribe(func: Callable):
    """
    Kanalga obunani tekshiradi. Faqat qidiruv vaqtida ishlatiladi.
    O'zidan oldin @get_user yoki @update_or_create_user ishlatilishiga tayanadi.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = kwargs.get('user')
        user_language = kwargs.get('language')
        if not user or not user_language:
            return await func(update, context, *args, **kwargs)

        # Lazy import to avoid circular dependency
        from .models import SubscribeChannel
        from .keyboard import keyboard_checked_subscription_channel
        
        has_active_channels = await SubscribeChannel.objects.filter(active=True).aexists()
        if has_active_channels:
            reply_markup, subscribed_status = await keyboard_checked_subscription_channel(user.telegram_id, context.bot)
            if not subscribed_status:
                await update.message.reply_text(
                    translation.subscribe_channel_text.get(user_language),
                    reply_markup=reply_markup
                )
                return
        return await func(update, context, *args, **kwargs)

    return wrapper
