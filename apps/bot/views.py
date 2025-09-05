# views.py
import logging

from asgiref.sync import sync_to_async
from django.core.paginator import Paginator, Page
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
from apps.multiparser.models import Document, Product
from .utils import (channel_subscribe, get_user,
                    update_or_create_user)
from telegram.error import TelegramError


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
    user_text = update.message.text.strip()
    print("user_text: ", user_text)

    if user_text == translation.deep_search[language]:
        print("Deep search")
        new_mode = 'deep'
    elif user_text == translation.search[language]:
        print("Normal search")
        new_mode = 'normal'
    else:
        new_mode = context.user_data.get('default_search_mode', 'normal')

    # faqat sessionga yozamiz
    context.user_data['default_search_mode'] = new_mode

    response_text = (
        translation.deep_search_mode_on[language]
        if new_mode == 'deep'
        else translation.normal_search_mode_on[language]
    )
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

# apps/bot/views.py fayliga o'zgartirishlar

# ... (faylning yuqori qismi o'zgarishsiz)

# apps/bot/views.py fayliga o'zgartirishlar

# ... (faylning yuqori qismi o'zgarishsiz)

# apps/bot/views.py

# ...importlar...
from elasticsearch_dsl import Q  # <-- Q obyektini import qilamiz

FIFTY_MB_IN_BYTES = 50 * 1024 * 1024

@channel_subscribe
@get_user
async def main_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, language: str):
    text = update.message.text.strip()
    print("text: ", text)
    search_mode = context.user_data.get('default_search_mode', 'normal')
    page_number = 1
    page_size = 10
    print("search_mode: ", search_mode)

    # 🔎 Deep yoki normal qidiruv
    # Build a combined query: boosted exact phrase matches first, then fuzzy/similar matches.
    # Exact phrase has higher boost so will appear earlier in results; fuzzy clause ensures
    # we still return similar documents when exact phrase not present.
    if search_mode == 'deep':
        exact_fields = ["product_title^10", "product_slug^8", "content^6"]
        fuzzy_fields = ["product_title^5", "product_slug^4", "content^3"]
    else:
        exact_fields = ["product_title^10", "product_slug^8"]
        fuzzy_fields = ["product_title^5", "product_slug^4"]

    exact_clause = Q("multi_match", query=text, fields=exact_fields, type="phrase", boost=5)
    fuzzy_clause = Q("multi_match", query=text, fields=fuzzy_fields, fuzziness="AUTO", boost=1)

    # Combine: at least one should match; exact matches get higher score due to boost
    q = Q('bool', should=[exact_clause, fuzzy_clause], minimum_should_match=1)

    s = DocumentDocument.search().query(q)

    # --- Filtrlash mantiqi ---
    filter_query = Q(
        'bool',
        should=[
            Q('range', file_size_bytes={'lte': FIFTY_MB_IN_BYTES}),
            Q('term', download_status='downloaded')
        ],
        minimum_should_match=1
    )
    s = s.filter(filter_query)

    total_results = await sync_to_async(s.count)()
    if total_results == 0:
        await SearchQuery.objects.acreate(
            user=user, query_text=text, found_results=False, is_deep_search=(search_mode == 'deep')
        )
        await update.message.reply_text(translation.search_no_results[language].format(query=text))
        return

    # Paginatsiya
    start_index = (page_number - 1) * page_size
    end_index = start_index + page_size
    search_results = await sync_to_async(lambda: s[start_index:end_index].execute())()

    all_files_ids = [hit.meta.id for hit in search_results]

    await SearchQuery.objects.acreate(
        user=user, query_text=text, found_results=True, is_deep_search=(search_mode == 'deep')
    )

    context.user_data['last_search_query'] = text

    paginator = Paginator(range(total_results), page_size)
    page_obj = Page(all_files_ids, page_number, paginator)

    files_from_db = await sync_to_async(list)(
        Product.objects.filter(document_id__in=page_obj.object_list).select_related('document')
    )
    files_map = {str(product.document.id): product for product in files_from_db}
    products_on_page = [files_map[doc_id] for doc_id in all_files_ids if doc_id in files_map]

    response_text = translation.search_results_found[language].format(query=text, count=total_results)
    reply_markup = build_search_results_keyboard(page_obj, products_on_page, search_mode, language)
    await update.message.reply_text(response_text, reply_markup=reply_markup)


@get_user
async def handle_search_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, language: str):
    query = update.callback_query
    await query.answer()
    page_size = 10

    query_text = context.user_data.get('last_search_query')
    if not query_text:
        await query.edit_message_text(translation.search_no_results[language].format(query=""))
        return

    _, search_mode, page_number_str = query.data.split('_')
    page_number = int(page_number_str)

    # 🔎 Deep yoki normal qidiruv
    if search_mode == 'deep':
        exact_fields = ["product_title^10", "product_slug^8", "content^6"]
        fuzzy_fields = ["product_title^5", "product_slug^4", "content^3"]
    else:
        exact_fields = ["product_title^10", "product_slug^8"]
        fuzzy_fields = ["product_title^5", "product_slug^4"]

    exact_clause = Q("multi_match", query=query_text, fields=exact_fields, type="phrase", boost=5)
    fuzzy_clause = Q("multi_match", query=query_text, fields=fuzzy_fields, fuzziness="AUTO", boost=1)

    # Combine: at least one should match; exact matches get higher score due to boost
    q = Q('bool', should=[exact_clause, fuzzy_clause], minimum_should_match=1)

    s = DocumentDocument.search().query(q)

    # --- Filtrlash mantiqi ---
    filter_query = Q(
        'bool',
        should=[
            Q('range', file_size_bytes={'lte': FIFTY_MB_IN_BYTES}),
            Q('term', download_status='downloaded')
        ],
        minimum_should_match=1
    )
    s = s.filter(filter_query)

    total_results = await sync_to_async(s.count)()

    # Paginatsiya
    start_index = (page_number - 1) * page_size
    end_index = start_index + page_size
    search_results = await sync_to_async(lambda: s[start_index:end_index].execute())()

    all_files_ids = [hit.meta.id for hit in search_results]

    paginator = Paginator(range(total_results), page_size)
    page_obj = Page(all_files_ids, page_number, paginator)

    files_from_db = await sync_to_async(list)(
        Product.objects.filter(document_id__in=page_obj.object_list).select_related('document')
    )
    files_map = {str(product.document.id): product for product in files_from_db}
    products_on_page = [files_map[doc_id] for doc_id in all_files_ids if doc_id in files_map]

    response_text = translation.search_results_found[language].format(query=query_text, count=total_results)
    reply_markup = build_search_results_keyboard(page_obj, products_on_page, search_mode, language)
    await query.edit_message_text(text=response_text, reply_markup=reply_markup)



@get_user
async def send_file_by_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User, language: str):
    """
    Callback orqali faylni Telegramning o'zidagi file_id yordamida yuboradi.
    Bu usul ancha tez va faylning serverda mavjud bo'lishini talab qilmaydi.
    """
    query = update.callback_query

    # --- 1. ID ni int() ga o'girish olib tashlandi, chunki u UUID ---
    document_uuid = query.data.split('_')[1]
    await query.answer(text=translation.file_is_being_sent[language])

    try:
        # Hujjatni bazadan olamiz
        document = await Document.objects.select_related('product').aget(id=document_uuid)

        # --- 2. Faylni Telegram file_id orqali yuborish ---
        if document.file_id:
            # Agar file_id mavjud bo'lsa (ya'ni, fayl kanalga yuborilgan bo'lsa)
            await context.bot.send_document(
                chat_id=user.telegram_id,
                document=document.file_id,  # Eng asosiy o'zgarish!
                caption=f"<b>{document.product.title}</b>",
                parse_mode=ParseMode.HTML
            )
        else:
            # Agar file_id mavjud bo'lmasa (fayl >50MB yoki kanalga yuborishda xatolik bo'lgan)
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text=translation.file_not_available_for_sending[language]
            )

    except Document.DoesNotExist:
        await context.bot.send_message(chat_id=user.telegram_id,
                                       text="Xatolik: Bunday fayl ma'lumotlar bazasida topilmadi.")
    except TelegramError as e:
        logger.error(f"Telegram fayl yuborishda xatolik (file_id orqali): {e}")
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=f"Faylni yuborishda Telegram bilan bog'liq xatolik yuz berdi: {e.message}"
        )
    except Exception as e:
        logger.exception(f"Fayl yuborishda (file_id orqali) kutilmagan xatolik: {e}")
        await context.bot.send_message(chat_id=user.telegram_id, text="Faylni yuborishda noma'lum xatolik yuz berdi.")
