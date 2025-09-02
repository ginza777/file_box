from django.urls import path
from .webhook import bot_webhook

urlpatterns = [
    path('bot', bot_webhook, name='bot_webhook'),
]