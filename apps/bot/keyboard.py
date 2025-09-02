from asgiref.sync import sync_to_async
from telegram import Bot
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.error import BadRequest

from . import translation
from .models import SubscribeChannel


def language_list_keyboard():
    button_list = [
        {"name": "🇺🇿 Uzbek", "id": "uz"},
        {"name": "🇬🇧 English", "id": "en"},
        {"name": "🇷🇺 Russian", "id": "ru"},
        {"name": "🇹🇷 Turkish", "id": "tr"},

    ]
    keyboard = []
    for button in button_list:
        keyboard.append([InlineKeyboardButton(button['name'], callback_data=f"language_setting_{button['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"setting_back")])

    return InlineKeyboardMarkup(keyboard)


def restart_keyboard(lang) -> ReplyKeyboardMarkup:
    text = {
        "uz": "boshlash",
        "en": "restart",
        "ru": "перезапуск",
        "tr": "yeniden başlat"
    }

    buttons = [
        [KeyboardButton(text[lang])]
    ]

    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def make_movie_share_keyboard_with_code(bot_username, code, lang) -> InlineKeyboardMarkup:
    share_bot = {
        "uz": f"Ushbu kinoni ulashing  📤 ",
        "ru": f"Поделиться этим фильмом  📤",
        "en": f"Share this Movie 📤",
        "tr": f"Bu Filmi Paylaş 📤",
    }
    buttons = [[
        InlineKeyboardButton(share_bot[lang], switch_inline_query=f"https://t.me/{bot_username}?start={code}")
    ]]
    return InlineKeyboardMarkup(buttons)


def share_post_inline_button(post_id, lang) -> InlineKeyboardMarkup:
    share_text = {
        "uz": f"Ushbu postni ulashing 📤",
        "ru": f"Поделиться этим постом 📤",
        "en": f"Share this post 📤",
        "tr": f"Bu Gönderi Paylaş ��",
    }
    buttons = [[
        InlineKeyboardButton(share_text[lang], switch_inline_query=f"share_post_{post_id}")
    ]]
    return InlineKeyboardMarkup(buttons)


def start_with_code_keyboard(bot_username, code, lang) -> InlineKeyboardMarkup:
    share_bot = {
        "uz": f"Ushbu kinoni ulashing  📤 ",
        "ru": f"Поделиться этим фильмом  📤",
        "en": f"Share this Movie 📤",
        "tr": f"Bu Filmi Paylaş 📤",
    }
    buttons = [[
        InlineKeyboardButton(share_bot[lang], switch_inline_query=f"https://t.me/{bot_username}?start={code}")
    ]]
    return InlineKeyboardMarkup(buttons)


def make_movie_share_keyboard(lang) -> InlineKeyboardMarkup:
    share_bot = {
        "uz": f"Ushbu kinoni ulashing  📤 ",
        "ru": f"Поделиться этим фильмом  📤",
        "en": f"Share this Movie 📤",
        "tr": f"Bu Filmi Paylaş ��",
    }
    text = """🍀Bot"""
    buttons = [[
        InlineKeyboardButton(share_bot[lang], switch_inline_query=f"\n\n{text}")
    ]]
    return InlineKeyboardMarkup(buttons)


def share_bot_keyboard(lang) -> InlineKeyboardMarkup:
    share_bot = {
        "uz": f"Ushbu kinoni ulashing  📤 ",
        "ru": f"Поделиться этим фильмом  📤",
        "en": f"Share this Movie 📤",
        "tr": f"Bu Filmi Paylaş 📤",
    }
    text = """🍀Bot"""
    buttons = [[
        InlineKeyboardButton(share_bot[lang], switch_inline_query=f"\n\n{text}")
    ]]
    return InlineKeyboardMarkup(buttons)


def default_keyboard(lang, admin=False) -> ReplyKeyboardMarkup:
    change_language = {
        "uz": "🌍 Tilni o'zgartirish",
        "ru": "🌍 Изменить язык",
        "en": "🌍 Change Language",
        "tr": "🌍 Dil değiştir"
    }
    help = {
        "uz": "📚 Yordam",
        "ru": "📚 Помощь",
        "en": "📚 Help",
        "tr": "📚 Yardım"
    }
    share_bot = {
        "uz": "📤 Botni ulashish",
        "ru": "📤 Поделиться ботом",
        "en": "📤 Share Bot",
        "tr": "📤 Botu paylaş"
    }

    about_us = {
        "uz": "📞 Biz haqimizda",
        "ru": "📞 О_нас",
        "en": "📞 About Us",
        "tr": "📞 Hakkımızda"
    }

    buttons = [
        # Random movie
        [KeyboardButton(change_language[lang]), KeyboardButton(help[lang])],
        # Share the bot
        [KeyboardButton(share_bot[lang]), KeyboardButton(about_us[lang])]

    ]
    if admin:
        buttons.append([KeyboardButton(translation.admin_button_text)])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def make_keyboard_for_about_command(lang, admin=False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(translation.admin_button_text, url="https://t.me/@sherzamon_m")]
    ]

    if admin:
        buttons.append(
            [InlineKeyboardButton(translation.github_button_text, url="https://github.com/GinzaPro/CommonBot.git")])
        buttons.append([InlineKeyboardButton(translation.secret_level_button_text[lang], callback_data='SCRT_LVL')])

    return InlineKeyboardMarkup(buttons)


def make_keyboard_for_help_command() -> InlineKeyboardMarkup:
    buttons = [[
        InlineKeyboardButton(translation.admin_button_text, url="https://t.me/@sherzamon_m")
    ]]

    return InlineKeyboardMarkup(buttons)


async def keyboard_checked_subscription_channel(user_id, bot):
    channels = await sync_to_async(list)(SubscribeChannel.objects.filter(active=True))
    buttons = []
    is_subscribed = True

    for idx, channel in enumerate(channels):
        try:
            # Telegram Bot obyekti yaratish
            token = channel.token
            bot_instance = Bot(token=token)

            # Foydalanuvchining obunachiligini tekshirish
            chat_member = await bot_instance.get_chat_member(chat_id=channel.channel_id, user_id=user_id)
            subscribed = chat_member.status != 'left'

        except BadRequest as e:
            print(f"Error checking subscription: {e}")
            subscribed = False
        except Exception as e:
            print(f"Unexpected error: {e}")
            subscribed = False

        subscription_status = "✅" if subscribed else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"Channel {idx + 1} {subscription_status}",
                url=channel.channel_link if channel.private else f"https://t.me/{channel.channel_username}"
            )
        ])
        if not subscribed:
            is_subscribed = False

    check_channels_button = InlineKeyboardButton(translation.check_subscribing, callback_data="check_subscription")
    buttons.append([check_channels_button])

    return InlineKeyboardMarkup(buttons), is_subscribed


def send_location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text=translation.SEND_LOCATION, request_location=True)]],
        resize_keyboard=True
    )


def keyboard_check_subscription_channel() -> InlineKeyboardMarkup:
    """
    Foydalanuvchiga kanalga obuna bo'lishni taklif qiluvchi klaviatura.
    Qaytaradi: InlineKeyboardMarkup
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="🔔 Obuna bo‘lish",
                url="https://t.me/YOUR_CHANNEL_USERNAME"  # Kanal username yoki link
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Tekshirish",
                callback_data="check_subscription"
            )
        ]
    ]

    return InlineKeyboardMarkup(buttons)