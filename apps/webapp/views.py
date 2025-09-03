# apps/webapp/views.py
from django.shortcuts import render
from apps.multiparser.models import Document
from django_elasticsearch_dsl.search import Search
from apps.bot.documents import DocumentDocument
from elasticsearch_dsl.query import MultiMatch
from django.views.generic import DetailView
from elasticsearch_dsl.query import MoreLikeThis
class FileListView(ListView):
    model = Document
    template_name = 'file_list.html'
    context_object_name = 'files'
    paginate_by = 30 # Foydalanuvchi talabiga ko'ra 30 taga o'zgartirdik

    def get_queryset(self):
        query = self.request.GET.get('q')
        if query:
            # Agar qidiruv so'rovi bo'lsa, Elasticsearch'dan qidiramiz
            s = DocumentDocument.search().query(
                MultiMatch(query=query, fields=['title^4', 'description^2', 'file_name', 'content'], fuzziness='AUTO')
            )
            # Faqat ID'larni olamiz
            all_files_ids = [int(hit.meta.id) for hit in s.scan()]
            # Bazadan shu ID'lar bo'yicha fayllarni olamiz
            queryset = Document.objects.filter(id__in=all_files_ids)
            return queryset
        # Agar qidiruv so'rovi bo'lmasa, barcha fayllarni qaytaramiz
        return Document.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bot_username'] = settings.TELEGRAM_BOT_USERNAME
        # Qidiruv so'rovini ham template'ga yuboramiz
        context['search_query'] = self.request.GET.get('q', '')
        return context

class FileDetailView(DetailView):
    model = Document
    template_name = 'file_detail.html'
    context_object_name = 'file'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bot_username'] = settings.TELEGRAM_BOT_USERNAME

        # Elasticsearch orqali o'xshash fayllarni topish
        file_object = self.get_object()
        s = DocumentDocument.search().query(
            MoreLikeThis(
                like={'_id': file_object.id},
                fields=['title', 'description', 'content']
            )
        )
        # Birinchi 10 ta o'xshash faylni olamiz
        related_files_search = s[:10].execute()
        related_files_ids = [int(hit.meta.id) for hit in related_files_search]

        context['related_files'] = Document.objects.filter(id__in=related_files_ids)
        return context