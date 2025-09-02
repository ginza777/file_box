# apps/bot/documents.py
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from tika import parser
from apps.multiparser.models import Document as DocumentModel


@registry.register_document
class DocumentDocument(Document):
    content = fields.TextField(attr='content')

    class Index:
        name = 'documents'
        settings = {'number_of_shards': 1, 'number_of_replicas': 0}

    class Django:
        model = DocumentModel
        fields = [
            'file_type',
            'file_size',
            'content_type',
            'page_count',
        ]

    def prepare_content(self, instance):
        """
        Extract content from text-based documents using Tika
        """
        # Only process text-based documents
        text_based_types = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        
        # Check if this is a text-based document
        if not any(text_type in instance.file_type for text_type in text_based_types):
            return ""

        # If file exists locally, extract content
        if instance.file_path:
            try:
                from django.conf import settings
                import os
                
                file_path = os.path.join(settings.MEDIA_ROOT, instance.file_path)
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    with open(file_path, 'rb') as f:
                        parsed = parser.from_buffer(f.read())

                    if parsed and 'content' in parsed and parsed['content']:
                        # Clean up text content
                        return ' '.join(str(parsed['content']).split())
            except Exception as e:
                print(f"Tika error reading file {instance.file_path}: {e}")

        return ""