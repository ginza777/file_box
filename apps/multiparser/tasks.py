import os
import random
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from apps.multiparser.models import Document, Product, Seller
import logging
import re
from django.db import transaction
from django.utils import timezone
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import magic
from elasticsearch import Elasticsearch
from tika import parser as tika_parser

logger = logging.getLogger(__name__)

# Initialize Elasticsearch client
es_client = Elasticsearch([settings.ES_URL]) if hasattr(settings, 'ES_URL') else None

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def download_and_save_file(self, document_id):
    """
    Download file from URL and save it locally
    """
    try:
        document = Document.objects.get(id=document_id)
        
        # Update status to downloading
        document.download_status = 'downloading'
        document.download_started_at = timezone.now()
        document.save(update_fields=['download_status', 'download_started_at'])
        
        # Random delay to avoid blocking
        time.sleep(random.uniform(1, 5))
        
        if not document.file_url:
            document.download_status = 'skipped'
            document.download_error = 'No file URL available'
            document.save(update_fields=['download_status', 'download_error'])
            return f"Document {document_id}: No file URL available"
        
        # Download file
        response = requests.get(document.file_url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Create upload directory
        upload_dir = Path(settings.MEDIA_ROOT) / 'documents' / str(document.id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine file extension from URL or content
        file_extension = Path(document.file_url).suffix
        if not file_extension:
            # Try to get from content-type
            content_type = response.headers.get('content-type', '')
            if 'pdf' in content_type:
                file_extension = '.pdf'
            elif 'doc' in content_type:
                file_extension = '.doc'
            elif 'docx' in content_type:
                file_extension = '.docx'
            else:
                file_extension = '.pdf'  # Default
        
        filename = f"document_{document.id}{file_extension}"
        file_path = upload_dir / filename
        
        # Save file
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Update document with file path
        document.file_path = str(file_path.relative_to(settings.MEDIA_ROOT))
        document.download_status = 'downloaded'
        document.download_completed_at = timezone.now()
        document.save(update_fields=['file_path', 'download_status', 'download_completed_at'])
        
        # Trigger indexing task
        index_document.delay(document_id)
        
        # Trigger send to channel task
        send_to_telegram_channel.delay(document_id)
        
        return f"Document {document_id}: Downloaded successfully to {file_path}"
        
    except Document.DoesNotExist:
        return f"Document {document_id}: Not found"
    except Exception as exc:
        logger.error(f"Error downloading document {document_id}: {exc}")
        
        # Update document with error
        try:
            document = Document.objects.get(id=document_id)
            document.download_status = 'failed'
            document.download_error = str(exc)
            document.save(update_fields=['download_status', 'download_error'])
        except:
            pass
        
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def index_document(self, document_id):
    """
    Index document using Elasticsearch and Tika for content extraction
    """
    try:
        document = Document.objects.get(id=document_id)
        
        if not document.file_path:
            return f"Document {document_id}: No file path available"
        
        file_path = Path(settings.MEDIA_ROOT) / document.file_path
        
        if not file_path.exists():
            return f"Document {document_id}: File not found at {file_path}"
        
        # Extract text content using Tika
        try:
            parsed = tika_parser.from_file(str(file_path))
            content = parsed.get('content', '')
            metadata = parsed.get('metadata', {})
        except Exception as e:
            logger.warning(f"Tika parsing failed for {document_id}: {e}")
            content = ""
            metadata = {}
        
        # Prepare document for indexing
        doc_data = {
            'id': document.id,
            'title': document.title or '',
            'description': document.description or '',
            'content': content,
            'file_path': document.file_path,
            'file_url': document.file_url,
            'mime_type': metadata.get('Content-Type', ''),
            'file_size': metadata.get('Content-Length', 0),
            'created_at': document.created_at.isoformat() if document.created_at else None,
            'product_id': document.product.id if document.product else None,
            'seller_id': document.product.seller.id if document.product and document.product.seller else None,
        }
        
        # Index in Elasticsearch
        if es_client:
            try:
                index_name = getattr(settings, 'ES_INDEX', 'documents')
                es_client.index(
                    index=index_name,
                    id=document.id,
                    body=doc_data
                )
                logger.info(f"Document {document_id} indexed successfully")
            except Exception as e:
                logger.error(f"Elasticsearch indexing failed for {document_id}: {e}")
                raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
        return f"Document {document_id}: Indexed successfully"
        
    except Document.DoesNotExist:
        return f"Document {document_id}: Not found"
    except Exception as exc:
        logger.error(f"Error indexing document {document_id}: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_to_telegram_channel(self, document_id):
    """
    Send document to Telegram channel and save file_id
    """
    try:
        document = Document.objects.get(id=document_id)
        
        if not document.file_path:
            return f"Document {document_id}: No file path available"
        
        # Get bot token and channel ID from settings
        bot_token = getattr(settings, 'BOT_TOKEN', None)
        channel_id = getattr(settings, 'FORCE_CHANNEL_ID', None)
        
        if not bot_token or not channel_id:
            logger.error("BOT_TOKEN or FORCE_CHANNEL_ID not configured")
            return f"Document {document_id}: Bot configuration missing"
        
        file_path = Path(settings.MEDIA_ROOT) / document.file_path
        
        if not file_path.exists():
            return f"Document {document_id}: File not found at {file_path}"
        
        # Send file to channel
        try:
            bot = Bot(token=bot_token)
            
            # Send as document
            with open(file_path, 'rb') as f:
                result = bot.send_document(
                    chat_id=channel_id,
                    document=f,
                    filename=file_path.name,
                    caption=f"📄 {document.title or 'Document'}\n\n"
                           f"📝 Description: {document.description or 'No description'}\n"
                           f"🏷️ Product: {document.product.title if document.product else 'N/A'}\n"
                           f"👤 Seller: {document.product.seller.fullname if document.product and document.product.seller else 'N/A'}"
                )
            
            # Save file_id and mark as sent
            document.file_id = result.document.file_id
            document.sent_to_channel = True
            document.sent_at = timezone.now()
            document.save(update_fields=['file_id', 'sent_to_channel', 'sent_at'])
            
            logger.info(f"Document {document_id} sent to channel successfully")
            
            # Delete local file after sending
            try:
                os.remove(file_path)
                document.file_path = None
                document.save(update_fields=['file_path'])
                logger.info(f"Local file deleted for document {document_id}")
            except Exception as e:
                logger.warning(f"Failed to delete local file for {document_id}: {e}")
            
            return f"Document {document_id}: Sent to channel successfully"
            
        except TelegramError as e:
            logger.error(f"Telegram error sending document {document_id}: {e}")
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
    except Document.DoesNotExist:
        return f"Document {document_id}: Not found"
    except Exception as exc:
        logger.error(f"Error sending document {document_id} to channel: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def cleanup_old_files():
    """
    Clean up old downloaded files that are no longer needed
    """
    try:
        # Find documents that were sent to channel more than 1 day ago
        cutoff_date = timezone.now() - timezone.timedelta(days=1)
        old_documents = Document.objects.filter(
            sent_to_channel=True,
            sent_at__lt=cutoff_date,
            file_path__isnull=False
        )
        
        cleaned_count = 0
        for document in old_documents:
            try:
                file_path = Path(settings.MEDIA_ROOT) / document.file_path
                if file_path.exists():
                    os.remove(file_path)
                    document.file_path = None
                    document.save(update_fields=['file_path'])
                    cleaned_count += 1
            except Exception as e:
                logger.error(f"Failed to clean up file for document {document.id}: {e}")
        
        logger.info(f"Cleaned up {cleaned_count} old files")
        return f"Cleaned up {cleaned_count} old files"
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_files: {e}")
        return f"Cleanup failed: {e}"


@shared_task
def update_parsed_data_periodic():
    """
    Periodic task to update parsed data every 3 days
    """
    try:
        # This would be your existing parsing logic
        # For now, just trigger download tasks for documents that need processing
        pending_documents = Document.objects.filter(
            download_status='pending',
            file_url__isnull=False
        ).exclude(
            product__id=327540  # Skip this specific product ID as requested
        )
        
        for document in pending_documents:
            download_and_save_file.delay(document.id)
        
        logger.info(f"Triggered download for {pending_documents.count()} pending documents")
        return f"Triggered download for {pending_documents.count()} pending documents"
        
    except Exception as e:
        logger.error(f"Error in update_parsed_data_periodic: {e}")
        return f"Periodic update failed: {e}"
