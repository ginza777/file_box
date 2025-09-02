from django.urls import path, re_path
from .webhook import bot_webhook
from .api import DocumentListCreateView, DocumentRetrieveUpdateDestroyView

urlpatterns = [
    path('', bot_webhook, name='bot_webhook'),
    path('files/', DocumentListCreateView.as_view(), name='document-list-create'),
    path('files/<int:pk>/', DocumentRetrieveUpdateDestroyView.as_view(), name='document-detail'),
]
