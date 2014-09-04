import os
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.paginator import Paginator, InvalidPage
from django.http import Http404
from django.conf import settings

from haystack.query import SearchQuerySet

from zorna.acl.models import get_allowed_objects
from zorna.articles.models import ArticleCategory, ArticleStory
from zorna.faq.models import FaqQuestion, Faq
from zorna.fileman.models import ZornaFile
from zorna.fileman.api import get_allowed_folders
from zorna.search.form import SearchForm

RESULTS_PER_PAGE = 15


def search(request):
    results_articles = None
    results_faqs = None
    results = {}
    query = ''
    if request.GET.get('q'):
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['q']
            query = "*"+query+"*" if query else query
            what = request.GET.get('what', None)
            if what == 'articles' or what is None:
                ao = get_allowed_objects(
                    request.user, ArticleCategory, 'reader')
                ao = [str(p) for p in ao]
                results_articles = SearchQuerySet().filter(
                    content=query).filter(categories__in=ao).models(ArticleStory)
                if results_articles:
                    paginator = Paginator(results_articles, RESULTS_PER_PAGE)
                    try:
                        page = paginator.page(int(request.GET.get('page', 1)))
                    except InvalidPage:
                        raise Http404("No such page of results!")
                    results['articles'] = {
                        'results': results_articles, 'page': page, 'paginator': paginator}

            if what == 'faqs' or what is None:
                ao = get_allowed_objects(request.user, Faq, 'reader')
                ao = [str(p) for p in ao]
                results_faqs = SearchQuerySet().filter(
                    content=query).filter(faq__in=ao).models(FaqQuestion)
                if results_faqs:
                    paginator = Paginator(results_faqs, RESULTS_PER_PAGE)
                    try:
                        page = paginator.page(int(request.GET.get('page', 1)))
                    except InvalidPage:
                        raise Http404("No such page of results!")
                    results['faqs'] = {
                        'results': results_faqs, 'page': page, 'paginator': paginator}
            if what == 'files' or what is None:
                folders = get_allowed_folders(request)
                results_files = SearchQuerySet().filter(
                    content=query).filter(folder__in=folders).models(ZornaFile)
                if results_files:
                    paginator = Paginator(results_files, RESULTS_PER_PAGE)
                    try:
                        page = paginator.page(int(request.GET.get('page', 1)))
                    except InvalidPage:
                        raise Http404("No such page of results!")
                    results['files'] = {
                        'results': results_files, 'page': page, 'paginator': paginator}
            if what == 'pages' or what is None:
                from whoosh.index import open_dir
                from whoosh.qparser import QueryParser
                ix = open_dir(settings.HAYSTACK_WHOOSH_PATH, indexname="ZORNA_PAGES")
                with ix.searcher() as searcher:
                    qp = QueryParser("content", schema=ix.schema)
                    q = qp.parse(query)
                    pages = searcher.search(q)
                    if len(pages):
                        pages_result = []
                        for p in pages:
                            doc = os.path.splitext(p['url'])[0]
                            pages_result.append({'title': p['title'], 'url': '/content/%s/' % doc, 'highlights': p.highlights("content") })
                        paginator = Paginator(pages_result, RESULTS_PER_PAGE)
                        try:
                            page = paginator.page(int(request.GET.get('page', 1)))
                        except InvalidPage:
                            raise Http404("No such page of results!")
                        results['pages'] = {
                            'results': pages_result, 'page': page, 'paginator': paginator}
    else:
        form = SearchForm()

    context = RequestContext(request)
    extra_context = {
        'form': form,
        'results': results,
        'query': query,
    }
    return render_to_response(['search.html', 'search/search.html'], extra_context, context_instance=context)
