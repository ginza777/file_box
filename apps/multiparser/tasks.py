import os
import random
import time
from pathlib import Path

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from apps.multiparser.models import Document
import logging
from telegram import Bot
from telegram.error import TelegramError
from tika import parser as tika_parser
from elasticsearch import Elasticsearch, ElasticsearchError as es_exceptions

logger = logging.getLogger(__name__)

# Sozlamalardan Elasticsearch klientini sozlab olamiz
try:
    if hasattr(settings, 'ES_URL'):
        es_client = Elasticsearch(settings.ES_URL)
    else:
        es_client = None
except Exception as e:
    logger.error(f"Could not initialize Elasticsearch client: {e}")
    es_client = None


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_document(self, document_id):
    """
    Bu asosiy vazifa bo'lib, boshqa vazifalarni kerakli tartibda chaqiradi.
    1. Faylni yuklaydi.
    2. Telegram'ga yuboradi.
    3. Faylni indekslaydi.
    4. Lokal faylni o'chiradi.
    """
    try:
        document = Document.objects.get(id=document_id)
        if not document.file_url:
            logger.warning(f"Document {document_id} has no file_url. Skipping.")
            return f"Document {document_id}: Skipped"

        # 1. Faylni yuklash
        file_path_str = download_file(document_id)
        if not file_path_str:
            raise Exception("File download failed.")

        # 2. Telegram'ga yuborish
        send_to_telegram_channel(document_id)

        # 3. Elasticsearch uchun indekslash
        index_document_content(document_id)

        # 4. Lokal faylni o'chirish
        try:
            document.refresh_from_db()
            if document.file_path:
                file_path = Path(settings.MEDIA_ROOT) / document.file_path
                if file_path.exists():
                    os.remove(file_path)
                    logger.info(f"Successfully deleted local file: {file_path}")
                    document.file_path = None
                    document.save(update_fields=['file_path'])
        except Exception as e:
            logger.error(f"Error deleting local file for document {document_id}: {e}")

        return f"Document {document_id} processed successfully."
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found in process_document task.")
        return f"Document {document_id}: Not found"
    except Exception as exc:
        logger.error(f"Error processing document {document_id}: {exc}")
        self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


def download_file(document_id):
    """
    1-QADAM: Hujjatni URL orqali `media` papkasiga yuklab oladi.
    """
    try:
        document = Document.objects.get(id=document_id)
        document.download_status = 'downloading'
        document.download_started_at = timezone.now()
        document.save(update_fields=['download_status', 'download_started_at'])

        time.sleep(random.uniform(1, 3))  # Serverga og'irlik tushmasligi uchun pauza

        response = requests.get(document.file_url, stream=True, timeout=60)
        response.raise_for_status()

        # Fayl nomini va yo'lini aniqlash
        file_name = Path(document.file_url).name
        upload_dir = Path(settings.MEDIA_ROOT) / 'documents' / str(document.id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / file_name

        # Faylni diskka yozish
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Modelga fayl yo'lini va statusni saqlash
        document.file_path = str(file_path.relative_to(settings.MEDIA_ROOT))
        document.download_status = 'downloaded'
        document.download_completed_at = timezone.now()
        document.save(update_fields=['file_path', 'download_status', 'download_completed_at'])

        logger.info(f"Document {document_id}: Downloaded successfully to {file_path}")
        return document.file_path
    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {e}")
        try:
            document.download_status = 'failed'
            document.download_error = str(e)
            document.save(update_fields=['download_status', 'download_error'])
        except Document.DoesNotExist:
            pass
        return None


def send_to_telegram_channel(document_id):
    """
    2-QADAM: Fayl hajmi 50MB dan kichik bo'lsa, uni Telegram kanalga yuboradi.
    """
    try:
        document = Document.objects.get(id=document_id)
        if not document.file_path:
            logger.warning(f"Cannot send to Telegram: No file_path for document {document_id}")
            return

        bot_token = settings.BOT_TOKEN
        channel_id = settings.FORCE_CHANNEL_USERNAME  # .env faylidagi o'zgaruvchi
        if not bot_token or not channel_id:
            logger.error("BOT_TOKEN or FORCE_CHANNEL_USERNAME not configured in settings.")
            return

        file_path = Path(settings.MEDIA_ROOT) / document.file_path
        if not file_path.exists():
            logger.error(f"File not found for sending to Telegram: {file_path}")
            return

        # Fayl hajmini tekshirish (50 MB = 50 * 1024 * 1024 bytes)
        file_size_bytes = os.path.getsize(file_path)
        if file_size_bytes > 50 * 1024 * 1024:
            logger.info(f"File {document_id} is larger than 50MB. Skipping Telegram send.")
            # Fayl lokal saqlanib qoladi
            return

        bot = Bot(token=bot_token)
        product = document.product

        caption = f"📄 {product.title or 'Hujjat'}\n\n" \
                  f"👤 Sotuvchi: {product.seller.fullname if product and product.seller else 'N/A'}"

        with open(file_path, 'rb') as f:
            message = bot.send_document(
                chat_id=channel_id,
                document=f,
                filename=file_path.name,
                caption=caption
            )

        # Telegram'dan qaytgan file_id'ni saqlab qo'yamiz
        document.file_id = message.document.file_id
        document.sent_to_channel = True
        document.sent_at = timezone.now()
        document.save(update_fields=['file_id', 'sent_to_channel', 'sent_at'])

        logger.info(f"Document {document_id} sent to channel successfully.")

    except TelegramError as e:
        logger.error(f"Telegram error sending document {document_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in send_to_telegram_channel for doc {document_id}: {e}")


def index_document_content(document_id):
    """
    3-QADAM: Tika orqali fayl tarkibini o'qib, Elasticsearch'da indekslaydi.
    """
    if not es_client:
        logger.warning("Elasticsearch client is not configured. Skipping indexing.")
        return

    try:
        document = Document.objects.get(id=document_id)
        if not document.file_path:
            logger.warning(f"Cannot index: No file_path for document {document_id}")
            return

        file_path = Path(settings.MEDIA_ROOT) / document.file_path
        if not file_path.exists():
            logger.error(f"File not found for indexing: {file_path}")
            return

        # Tika yordamida fayl ichidagi matnni olish
        try:
            parsed = tika_parser.from_file(str(file_path))
            content = parsed.get('content', '') if parsed else ''
        except Exception as e:
            logger.error(f"Tika parsing failed for {document_id}: {e}")
            content = ""

        # Elasticsearch uchun ma'lumot tayyorlash
        product = document.product
        doc_data = {
            'document_id': str(document.id),
            'title': product.title if product else '',
            'content': content.strip() if content else '',
            'file_type': document.file_type,
            'content_type': document.content_type,
            'created_at': document.created_at,
            'product_id': product.id if product else None,
            'seller_id': product.seller.id if product and product.seller else None,
            'seller_name': product.seller.fullname if product and product.seller else None,
        }

        # Ma'lumotni Elasticsearch'ga indekslash
        index_name = settings.ES_INDEX
        es_client.index(index=index_name, id=str(document.id), document=doc_data)
        logger.info(f"Document {document_id} indexed successfully.")

    except es_exceptions.ElasticsearchException as e:
        logger.error(f"Elasticsearch indexing failed for document {document_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in index_document_content for doc {document_id}: {e}")
