# handler.py

from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler
)
# Funksiyalarni to'g'ri import qilish
from .views import (
    start, about, help, share_bot, ask_language, language_choice_handle,
    admin, stats, backup_db, export_users, ask_for_location, location_handler,
    secret_level, check_subscription_channel,
    # Suhbat uchun yangi funksiyalar
    start_broadcast_conversation, receive_broadcast_message,
    cancel_broadcast_conversation, handle_broadcast_confirmation,
    # Suhbat holatlari
    AWAIT_BROADCAST_MESSAGE
)

telegram_applications = {}


def get_application(token: str) -> Application:
    """
    Bot tokeni uchun Telegram Application obyektini yaratadi yoki keshdan qaytaradi.
    """
    if token not in telegram_applications:
        application = Application.builder().token(token).build()

        # Reklama yaratish uchun suhbat handler'ini yaratamiz
        # Yangi ConversationHandler:
        broadcast_conversation_handler = ConversationHandler(
            entry_points=[CommandHandler("broadcast", start_broadcast_conversation)],
            states={
                AWAIT_BROADCAST_MESSAGE: [
                    # O'ZGARISH: Endi buyruq bo'lmagan (~filters.COMMAND) har qanday xabarni
                    # `receive_broadcast_message` funksiyasiga yuboradi.
                    MessageHandler(~filters.COMMAND, receive_broadcast_message)
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel_broadcast_conversation)],
        )
        handlers = [
            # ... (CommandHandler("start", start) dan boshlab barcha eski handler'lar) ...
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & filters.Regex(r"^(перезапуск|restart|boshlash|yeniden başlat)$"), start),
            CommandHandler("about", about),
            MessageHandler(filters.TEXT & filters.Regex(r"^📞 (Biz haqimizda|О_нас|About Us|Hakkımızda)$"), about),
            CommandHandler("help", help),
            MessageHandler(filters.TEXT & filters.Regex(r"^📚 (Help|Помощь|Yordam|Yardım)$"), help),
            MessageHandler(filters.TEXT & filters.Regex(r"^📤 (Share Bot|Поделиться ботом|Botni ulashish|Botu paylaş)$"),
                           share_bot),
            CommandHandler("language", ask_language),
            MessageHandler(
                filters.TEXT & filters.Regex(r"^🌍 (Tilni o'zgartirish|Изменить язык|Change Language|Dil değiştir)$"),
                ask_language),
            CallbackQueryHandler(language_choice_handle, pattern="^language_setting_"),
            MessageHandler(filters.TEXT & filters.Regex(r"^Admin 🤖"), admin),
            CommandHandler("stats", stats),
            CommandHandler("admin", admin),
            CommandHandler("backup_db", backup_db),
            CommandHandler("export_users", export_users),
            CommandHandler("ask_location", ask_for_location),
            MessageHandler(filters.LOCATION, location_handler),
            CallbackQueryHandler(secret_level, pattern="^SCRT_LVL"),
            CallbackQueryHandler(check_subscription_channel, pattern="^check_subscription"),

            # --- REKLAMA ---
            # Eskisini o'chirib, o'rniga ConversationHandler'ni qo'shamiz
            broadcast_conversation_handler,
            # Tasdiqlash tugmalarini qayta ishlovchi handler o'z joyida qoladi
            CallbackQueryHandler(handle_broadcast_confirmation, pattern="^brdcast_")
        ]

        application.add_handlers(handlers)
        telegram_applications[token] = application

    return telegram_applications[token]