# handler.py

from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ConversationHandler,
)

from .views import (
    start, ask_language, language_choice_handle,
    toggle_search_mode, help_handler, about_handler, share_bot_handler,
    main_text_handler, handle_search_pagination, send_file_by_callback
)
from .admin_views import (
    admin_panel, stats, backup_db, export_users, secret_level,
    ask_location, location_handler  # YANGI FUNKSIYALARNI IMPORT QILAMIZ
)
from .broadcast_views import (
    start_broadcast_conversation, receive_broadcast_message,
    cancel_broadcast_conversation, handle_broadcast_confirmation,
    AWAIT_BROADCAST_MESSAGE
)
from .translation import (
    search, deep_search, help_text, about_us,
    share_bot_button, change_language, admin_button_text, text as restart_text
)

telegram_applications = {}


def get_application(token: str) -> Application:
    if token not in telegram_applications:
        application = Application.builder().token(token).build()

        def handler_wrapper(func):
            async def wrapper(update, context):
                # Try to extract user and language from context.user_data if available
                user = context.user_data.get('user')
                language = context.user_data.get('language')
                # If not available, call without them (decorators will handle)
                try:
                    return await func(update, context, user, language)
                except TypeError:
                    return await func(update, context)
            return wrapper

        broadcast_conv = ConversationHandler(
            entry_points=[CommandHandler("broadcast", handler_wrapper(start_broadcast_conversation))],
            states={AWAIT_BROADCAST_MESSAGE: [MessageHandler(~filters.COMMAND, handler_wrapper(receive_broadcast_message))]},
            fallbacks=[CommandHandler("cancel", handler_wrapper(cancel_broadcast_conversation))],
        )

        all_button_texts = [
            *search.values(), *deep_search.values(), *help_text.values(),
            *about_us.values(), *share_bot_button.values(), *change_language.values(),
            admin_button_text, *restart_text.values()
        ]
        button_filter = filters.Text(all_button_texts)

        handlers = [
            broadcast_conv,
            CommandHandler("start", handler_wrapper(start)),
            CommandHandler("help", handler_wrapper(help_handler)),
            CommandHandler("about", handler_wrapper(about_handler)),
            CommandHandler("language", handler_wrapper(ask_language)),
            CommandHandler("admin", handler_wrapper(admin_panel)),
            CommandHandler("stats", handler_wrapper(stats)),
            CommandHandler("backup_db", handler_wrapper(backup_db)),
            CommandHandler("export_users", handler_wrapper(export_users)),
            CommandHandler("ask_location", handler_wrapper(ask_location)),
            CallbackQueryHandler(handler_wrapper(handle_broadcast_confirmation), pattern="^brdcast_"),
            CallbackQueryHandler(handler_wrapper(handle_search_pagination), pattern="^search_"),
            CallbackQueryHandler(handler_wrapper(send_file_by_callback), pattern="^getfile_"),
            CallbackQueryHandler(handler_wrapper(language_choice_handle), pattern="^language_setting_"),
            CallbackQueryHandler(handler_wrapper(secret_level), pattern="^SCRT_LVL"),
            MessageHandler(filters.Regex(f"^({'|'.join(search.values())}|{'|'.join(deep_search.values())})$"), handler_wrapper(toggle_search_mode)),
            MessageHandler(filters.Regex(f"^({'|'.join(help_text.values())})$"), handler_wrapper(help_handler)),
            MessageHandler(filters.Regex(f"^({'|'.join(about_us.values())})$"), handler_wrapper(about_handler)),
            MessageHandler(filters.Regex(f"^({'|'.join(share_bot_button.values())})$"), handler_wrapper(share_bot_handler)),
            MessageHandler(filters.Regex(f"^({'|'.join(change_language.values())})$"), handler_wrapper(ask_language)),
            MessageHandler(filters.Text(admin_button_text), handler_wrapper(admin_panel)),
            MessageHandler(filters.Regex(f"^({'|'.join(restart_text.values())})$"), handler_wrapper(start)),
            MessageHandler(filters.LOCATION, handler_wrapper(location_handler)),
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~button_filter, handler_wrapper(main_text_handler)),
        ]

        application.add_handlers(handlers)
        telegram_applications[token] = application

    return telegram_applications[token]