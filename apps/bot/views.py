# views.py
import logging
from asgiref.sync import sync_to_async
from django.core.paginator import Paginator
from elasticsearch_dsl.query import QueryString
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
logger = logging.getLogger(__name__)
from . import translation
from .documents import DocumentDocument
from .keyboard import (build_search_results_keyboard, default_keyboard,
                       language_list_keyboard, restart_keyboard)
from .models import SearchQuery, User
from apps.multiparser.models import Document
from .utils import (channel_subscribe, get_user,
                    update_or_create_user)


# --- Asosiy Foydalanuvchi Funksiyalari ---

@update_or_create_user
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, language: str):
    """
    /start buyrug'i uchun. Foydalanuvchini yaratadi yoki oxirgi faolligini yangilaydi.
    """
    if not user.selected_language:
        await ask_language(update, context)
    else:
        await update.message.reply_text(
            translation.start_not_created[language].format(user.full_name),
            reply_markup=default_keyboard(language, admin=user.is_admin)
        )


@get_user
async def ask_language(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, language: str):
    """
    Tilni tanlash menyusini yuboradi.
    """
    await update.message.reply_text(
        translation.ask_language_text[language],
        reply_markup=language_list_keyboard()
    )


@get_user
async def language_choice_handle(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, language: str):
    """
    Callback orqali til tanlovini qayta ishlaydi.
    """
    query = update.callback_query
    await query.answer()

    lang_code = query.data.split("language_setting_")[-1]
    user.selected_language = lang_code
    await user.asave(update_fields=['selected_language'])

    await query.edit_message_text(translation.choice_language[lang_code])
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=translation.restart_text[lang_code],
        reply_markup=restart_keyboard(lang=lang_code)
    )


# --- Tugmalar uchun alohida, kichik funksiyalar ---

@update_or_create_user
async def toggle_search_mode(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, language: str):
    """
    'Search' va 'Advanced Search' tugmalari bosilganda ishlaydi.
    Talabga ko'ra, bu funksiya foydalanuvchini yangilaydi.
    """
    is_deep = translation.deep_search[language].lower() in update.message.text.lower()
    new_mode = 'deep' if is_deep else 'normal'
    context.user_data['default_search_mode'] = new_mode

    response_text = translation.deep_search_mode_on[language] if new_mode == 'deep' else \
        translation.normal_search_mode_on[language]
    await update.message.reply_text(response_text)


@get_user
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, language: str):
    """
    'Help' tugmasi uchun ishlaydi.
    """
    await update.message.reply_text(translation.help_message[language])


@get_user
async def about_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, language: str):
    """
    'About Us' tugmasi uchun ishlaydi.
    """
    await update.message.reply_text(translation.about_message[language])


@get_user
async def share_bot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, language: str):
    """
    'Share Bot' tugmasi uchun ishlaydi.
    """
    await update.message.reply_text(translation.share_bot_text[language])


# --- Qidiruv va Fayllar Bilan Ishlash ---

@channel_subscribe
@get_user
async def main_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, language: str):
    """
    Faqat matnli qidiruv so'rovlari uchun ishlaydi. Obunani tekshiradi.
    Pagination endi Elasticsearch'da samarali bajariladi.
    """
    text = update.message.text.strip()
    search_mode = context.user_data.get('default_search_mode', 'normal')
    page_number = 1
    page_size = 10

    search_fields = ['title^5', 'description^1', 'file_name^4']
    if search_mode == 'deep':
        search_fields.append('content^3')

    s = DocumentDocument.search().query(
        QueryString(query=f"*{text}*", fields=search_fields, default_operator='AND')
    )

    # Natijalar sonini olish
    total_results = s.count()

    if total_results == 0:
        await SearchQuery.objects.acreate(
            user=user, query_text=text, found_results=False, is_deep_search=(search_mode == 'deep')
        )
        await update.message.reply_text(translation.search_no_results[language].format(query=text))
        return

    # Kerakli sahifani olish (slicing)
    start_index = (page_number - 1) * page_size
    end_index = start_index + page_size
    search_results = s[start_index:end_index].execute()

    all_files_ids = [int(hit.meta.id) for hit in search_results]

    await SearchQuery.objects.acreate(
        user=user, query_text=text, found_results=True, is_deep_search=(search_mode == 'deep')
    )

    context.user_data['last_search_query'] = text
    # Django Paginator o'rniga to'g'ridan-to'g'ri ma'lumotlar bilan ishlash
    # Sahifalash uchun maxsus Paginator-ga o'xshash obyekt yaratish mumkin yoki
    # kerakli ma'lumotlarni (umumiy soni, joriy sahifa) to'g'ridan-to'g'ri uzatish
    from django.core.paginator import Paginator, Page
    paginator = Paginator(range(total_results), page_size)  # Dummy paginator for page range
    page_obj = Page(all_files_ids, page_number, paginator)

    files_on_page = await sync_to_async(list)(
        Document.objects.filter(id__in=page_obj.object_list).order_by('-uploaded_at'))

    response_text = translation.search_results_found[language].format(query=text, count=total_results)
    reply_markup = build_search_results_keyboard(page_obj, files_on_page, search_mode, language)
    await update.message.reply_text(response_text, reply_markup=reply_markup)


@get_user
async def handle_search_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, language: str):
    """
    Qidiruv natijalari sahifalarini o'zgartiradi (samarali usulda).
    """
    query = update.callback_query
    await query.answer()
    page_size = 10

    query_text = context.user_data.get('last_search_query')
    if not query_text:
        await query.edit_message_text(translation.search_no_results[language].format(query=""))
        return

    _, search_mode, page_number_str = query.data.split('_')
    page_number = int(page_number_str)

    search_fields = ['title^5', 'description^1', 'file_name^4']
    if search_mode == 'deep':
        search_fields.append('content^3')

    s = DocumentDocument.search().query(
        QueryString(query=f"*{query_text}*", fields=search_fields, default_operator='AND')
    )
    total_results = s.count()

    # Kerakli sahifani olish (slicing)
    start_index = (page_number - 1) * page_size
    end_index = start_index + page_size
    search_results = s[start_index:end_index].execute()
    all_files_ids = [int(hit.meta.id) for hit in search_results]

    from django.core.paginator import Paginator, Page
    paginator = Paginator(range(total_results), page_size)
    page_obj = Page(all_files_ids, page_number, paginator)

    files_on_page = await sync_to_async(list)(
        Document.objects.filter(id__in=page_obj.object_list).order_by('-uploaded_at'))

    response_text = translation.search_results_found[language].format(query=query_text, count=total_results)
    reply_markup = build_search_results_keyboard(page_obj, files_on_page, search_mode, language)
    await query.edit_message_text(text=response_text, reply_markup=reply_markup)


from telegram.error import TelegramError


@get_user
async def send_file_by_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, language: str):
    """
    Callback orqali faylni yuboradi. Xatoliklar aniqroq ushlanadi.
    """
    query = update.callback_query
    file_id = int(query.data.split('_')[1])
    await query.answer()

    try:
        document = await Document.objects.aget(id=file_id)
        await context.bot.send_document(
            chat_id=user.telegram_id,
            document=document.file.path,
            caption=f"<b>{document.title}</b>\n\n{document.description or ''}",
            parse_mode=ParseMode.HTML
        )
    except Document.DoesNotExist:
        await context.bot.send_message(chat_id=user.telegram_id, text="Xatolik: Fayl topilmadi.")
    except TelegramError as e:
        # Telegram API tomonidan qaytarilgan xatoliklarni ushlaymiz
        logger.error(f"Telegram fayl yuborishda xatolik: {e}")
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=f"Faylni yuborishda xatolik yuz berdi: {e.message}"
        )
    except FileNotFoundError:
        # Agar fayl diskda mavjud bo'lmasa
        logger.error(f"Fayl tizimida fayl topilmadi: ID={file_id}, Path={document.file.path}")
        await context.bot.send_message(chat_id=user.telegram_id, text="Xatolik: Fayl manbasi topilmadi.")
    except Exception as e:
        # Boshqa kutilmagan xatoliklar uchun
        logger.exception(f"Fayl yuborishda kutilmagan xatolik: {e}")
        await context.bot.send_message(chat_id=user.telegram_id, text="Faylni yuborishda noma'lum xatolik yuz berdi.")
