# apps/multiparser/tasks.py

import os
import time
import logging
import requests
from pathlib import Path
from celery import shared_task, chain
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from elasticsearch import Elasticsearch
from .models import Document

# --- Logger ---
logger = logging.getLogger(__name__)

# --- Elasticsearch client (Elasticsearch 8.x uchun) ---
es_client = Elasticsearch(
    settings.ES_URL,
    request_timeout=60,
    retry_on_timeout=True,
    max_retries=5
)

# --- Retry session helper (HTTP so‘rovlar uchun) ---
def make_retry_session(total=5, backoff=0.5, pool_connections=3, pool_maxsize=3):
    session = requests.Session()
    retry = Retry(
        total=total,
        read=total,
        connect=total,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(['GET', 'POST'])
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=pool_connections, pool_maxsize=pool_maxsize)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# ======================
# PARSE DOCUMENT
# ======================
import tika
from tika import parser
tika.initVM()

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    acks_late=True
)
def parse_document_task(self, document_id):
    logger.info(f"[Parse] Starting for document {document_id}")

    with transaction.atomic():
        document = Document.objects.select_for_update(skip_locked=True).get(id=document_id)

        if document.parsed_content:
            logger.info(f"[Parse] Already parsed {document_id}")
            return str(document_id)

        if not document.file_path:
            raise Exception(f"[Parse] No file found for document {document_id}")

    file_path = Path(settings.MEDIA_ROOT) / document.file_path
    if not file_path.exists():
        raise Exception(f"[Parse] File not found on disk: {file_path}")

    try:
        parsed = parser.from_file(str(file_path))
    except Exception as e:
        logger.error(f"[Parse] Tika error for {document_id}: {e}")
        raise

    content = parsed.get("content", "")
    metadata = parsed.get("metadata", {})

    if not content or not content.strip():
        # 🔥 Retry qilinsin
        raise Exception(f"[Parse] Empty content for {document_id}. "
                        f"File type={metadata.get('Content-Type')}, path={file_path}")

    # Normalize
    content = content.strip()
    Document.objects.filter(id=document_id).update(parsed_content=content)

    logger.info(f"[Parse] Completed {document_id}, length={len(content)} chars, "
                f"type={metadata.get('Content-Type')}")
    return str(document_id)



# ======================
# DOWNLOAD FILE
# ======================
@shared_task(
    bind=True,
    autoretry_for=(requests.RequestException, Exception),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    acks_late=True
)
def download_file_task(self, document_id):
    logger.info(f"[Download] Starting for document {document_id}")

    with transaction.atomic():
        document = Document.objects.select_for_update(skip_locked=True).get(id=document_id)
        if document.download_status == "downloaded" and document.file_path:
            logger.info(f"[Download] Already downloaded {document_id}")
            return str(document_id)

        document.download_status = "downloading"
        document.save(update_fields=["download_status"])

    session = make_retry_session()
    file_path = Path(settings.MEDIA_ROOT) / f"documents/{document_id}.bin"
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with session.get(document.file_url, stream=True, timeout=180) as r:
            r.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
    except Exception as e:
        logger.error(f"[Download] Failed for {document_id}: {e}")
        raise

    Document.objects.filter(id=document_id).update(
        file_path=str(file_path.relative_to(settings.MEDIA_ROOT)),
        download_status="downloaded"
    )
    logger.info(f"[Download] Completed {document_id}")
    return str(document_id)


# ======================
# INDEX DOCUMENT
# ======================
# INDEX DOCUMENT
@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    acks_late=True
)
def index_document_task(self, document_id):
    logger.info(f"[Index] Starting for document {document_id}")

    with transaction.atomic():
        document = Document.objects.select_for_update(skip_locked=True).get(id=document_id)
        if document.is_indexed:
            logger.info(f"[Index] Already indexed {document_id}")
            return str(document_id)

        if not document.file_path:
            raise Exception(f"[Index] No file found for document {document_id}")

    product = getattr(document, "product", None)
    body = {
        "document_id": str(document.id),
        "parsed_content": document.parsed_content or "",
    }

    if product:
        body.update({
            "product_id": product.id,
            "product_title": product.title,
            "product_slug": product.slug,
        })

    # 🔥 ES 8.x da 'document' parametri ishlatiladi
    es_client.index(index="documents", id=str(document.id), document=body)

    Document.objects.filter(id=document_id).update(is_indexed=True)
    logger.info(f"[Index] Completed {document_id}")
    return str(document_id)



# ======================
# SEND TO TELEGRAM
# ======================
@shared_task(
    bind=True,
    autoretry_for=(requests.RequestException, Exception),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
    rate_limit="5/m"
)
def send_telegram_task(self, document_id):
    logger.info(f"[Telegram] Starting for document {document_id}")

    with transaction.atomic():
        document = Document.objects.select_for_update(skip_locked=True).get(id=document_id)

        if document.telegram_status == "sent" and document.file_id:
            logger.info(f"[Telegram] Already sent {document_id}")
            return str(document_id)

        if not document.file_path:
            raise Exception(f"[Telegram] No file to send for {document_id}")

        if not document.is_indexed:
            raise Exception(f"[Telegram] Not indexed yet {document_id}")

        document.telegram_status = "sending"
        document.save(update_fields=["telegram_status"])

    bot_token = getattr(settings, "BOT_TOKEN", None)
    channel_id = getattr(settings, "FORCE_CHANNEL_USERNAME", None)
    file_path = Path(settings.MEDIA_ROOT) / document.file_path
    product = getattr(document, "product", None)

    caption = (
        f"📄 **ID:** `{product.id if product else document.id}`\n"
        f"✍️ **Title:** {getattr(product, 'title', 'Hujjat')}\n\n"
        f"👤 **Seller:** {getattr(getattr(product, 'seller', None), 'fullname', 'N/A')}"
    )
    caption = caption[:1000]  # Telegram limit

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    session = make_retry_session()

    try:
        with open(file_path, "rb") as f:
            files = {"document": (file_path.name, f)}
            data = {"chat_id": channel_id, "caption": caption, "parse_mode": "Markdown"}
            response = session.post(url, files=files, data=data, timeout=180)

        resp = response.json()
        if response.status_code == 429:
            retry_after = int(resp.get("parameters", {}).get("retry_after", 5))
            time.sleep(retry_after)
            raise Exception(f"[Telegram] 429 Too Many Requests, retry after {retry_after}s")

        if not resp.get("ok"):
            raise Exception(f"[Telegram] Error {resp}")
    except Exception as e:
        logger.error(f"[Telegram] Failed for {document_id}: {e}")
        raise

    file_id = resp["result"]["document"]["file_id"]
    Document.objects.filter(id=document_id).update(
        file_id=file_id,
        telegram_file_id=file_id,
        telegram_status="sent",
        sent_at=timezone.now(),
        sent_to_channel=True
    )
    logger.info(f"[Telegram] Completed {document_id}")
    return str(document_id)


# ======================
# DELETE LOCAL FILE
# ======================
@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    acks_late=True
)
def delete_local_file_task(self, document_id):
    logger.info(f"[Delete] Starting for document {document_id}")

    with transaction.atomic():
        document = Document.objects.select_for_update(skip_locked=True).get(id=document_id)

        if document.delete_from_server:
            logger.info(f"[Delete] Already deleted {document_id}")
            return str(document_id)

        if not (document.is_indexed and document.telegram_status == "sent"):
            raise Exception(f"[Delete] Cannot delete {document_id}, not indexed or not sent")

    file_path = Path(settings.MEDIA_ROOT) / document.file_path
    if file_path.exists() and not getattr(settings, "KEEP_LOCAL_FILES", False):
        try:
            os.remove(file_path)
        except Exception as e:
            logger.error(f"[Delete] Failed to remove {file_path}: {e}")
            raise

    Document.objects.filter(id=document_id).update(
        file_path=None,
        delete_from_server=True
    )
    logger.info(f"[Delete] Completed {document_id}")
    return str(document_id)


# ======================
# CHAIN RUNNER
# ======================
def process_document(document_id):
    """
    To'liq pipeline:
    Download -> Parse -> Index -> Telegram -> Delete
    """
    return chain(
        download_file_task.s(document_id),
        parse_document_task.s(),
        index_document_task.s(),
        send_telegram_task.s(),
        delete_local_file_task.s()
    ).apply_async()
