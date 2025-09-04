# apps/bot/documents.py
import os

from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from tika import parser
from apps.multiparser.models import Document as DocumentModel
from django.conf import settings

@registry.register_document
class DocumentDocument(Document):
    # Product modelidan olinadigan yangi maydonlar
    product_title = fields.TextField(attr="product.title")
    product_slug = fields.TextField(attr="product.slug")

    # Fayl ichidagi matn uchun maydon
    content = fields.TextField(analyzer="standard")
    download_status = fields.TextField(attr='download_status')
    file_size_bytes = fields.LongField(attr='file_size_bytes')

    class Index:
        # Indeks nomi (sozlamalardan olinishi mumkin)
        name = 'documents'
        settings = {'number_of_shards': 1,
                    'number_of_replicas': 0}

    class Django:
        model = DocumentModel
        fields = [
            'file_type',
            'created_at',
        ]

    def prepare_content(self, instance):
        # Ruxsat etilgan fayl turlari (MIME + extension)
        text_based_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # pptx
            "application/vnd.ms-powerpoint",  # ppt
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
            "application/vnd.ms-excel",  # xls
            "text/plain",
            ".ppt",
            ".pptx",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".txt",
            ".pdf"
        ]

        # Fayl turi extension yoki MIME ichida bo‘lishi kerak
        if not any(text_type in instance.file_type for text_type in text_based_types):
            return ""

        if instance.file_path:
            file_path = os.path.join(settings.MEDIA_ROOT, instance.file_path)
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                try:
                    parsed = parser.from_file(file_path)
                    if parsed and parsed.get("content"):
                        return " ".join(str(parsed["content"]).split())
                except Exception as e:
                    print(f"Tika error reading file {instance.file_path}: {e}")
        return ""
