# apps/multiparser/management/commands/reindex_documents.py

from django.core.management.base import BaseCommand
from tqdm import tqdm
from apps.multiparser.models import Document
from apps.multiparser.tasks import index_document_task


class Command(BaseCommand):
    """
    Statusi 'downloaded' bo'lgan barcha hujjatlar uchun
    qayta indekslash vazifasini Celery navbatiga qo'shadi.
    """
    help = "Schedules a re-indexing task for all documents with 'downloaded' status."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "Qayta indekslash uchun 'downloaded' statusidagi hujjatlar qidirilmoqda..."
        ))

        # Faqat serverga yuklab olingan hujjatlarni tanlab olamiz
        documents_to_reindex = Document.objects.filter(download_status='downloaded')

        count = documents_to_reindex.count()
        if count == 0:
            self.stdout.write(self.style.WARNING("Qayta indekslash uchun hujjatlar topilmadi."))
            return

        self.stdout.write(self.style.SUCCESS(
            f"Jami {count} ta hujjat qayta indekslash uchun navbatga qo'shiladi."
        ))

        # Jarayonni chiroyli ko'rsatish uchun tqdm'dan foydalanamiz
        with tqdm(total=count, desc="Indekslash vazifalari yaratilmoqda") as pbar:
            for document in documents_to_reindex.iterator():
                # Har bir hujjat uchun indekslash vazifasini navbatga qo'shamiz
                index_document_task.delay(document.id)
                pbar.update(1)

        self.stdout.write(self.style.SUCCESS(
            "\nBarcha qayta indekslash vazifalari Celery navbatiga muvaffaqiyatli qo'shildi! ✅"
        ))
        self.stdout.write(self.style.NOTICE(
            "Vazifalar bajarilishi uchun Celery worker'laringiz ishlab turganiga ishonch hosil qiling."
        ))