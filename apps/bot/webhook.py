# webhook.py
import json
import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from telegram import Update

from .handler import get_application


logger = logging.getLogger(__name__)


@csrf_exempt
async def bot_webhook(request):
    """
    Telegram'dan webhook so'rovlarini qabul qiladi, tekshiradi va
    update'ni qayta ishlash uchun application'ga yuboradi.
    """
    bot_token = getattr(settings, 'BOT_TOKEN', None)
    if not bot_token:
        logger.error("BOT_TOKEN sozlamalarda topilmadi.")
        return JsonResponse({"status": "BOT_TOKEN not configured"}, status=500)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        logger.warning("Webhook orqali yaroqsiz JSON qabul qilindi.")
        return JsonResponse({"status": "invalid json"}, status=400)

    application = get_application(bot_token)
    update = Update.de_json(data, application.bot)

    # bot_instance'ni bu yerda contextga qo'shish shart emas.
    # Har bir handler'ga qo'shilgan 'inject_bot_instance' dekoratori
    # bu vazifani o'zi bajaradi.

    await application.initialize()
    await application.process_update(update)

    return JsonResponse({"status": "ok"})