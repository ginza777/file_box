# apps/webapp/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from apps.multiparser.models import Document


class TgFileSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9  # Fayl sahifalari muhim bo'lgani uchun priority'ni oshiramiz

    def items(self):
        # Faqat ochiq va obunani talab qilmaydigan fayllarni sitemap'ga qo'shish yaxshiroq
        # Agar barcha fayllar chiqishi kerak bo'lsa, .all() qoldiring
        return Document.objects.filter(require_subscription=False).order_by('-uploaded_at')

    def lastmod(self, obj):
        return obj.uploaded_at

    def location(self, obj):
        # Bu yerda har bir fayl uchun to'g'ri URL manzilini hosil qilamiz
        return reverse('file-detail', kwargs={'pk': obj.pk})