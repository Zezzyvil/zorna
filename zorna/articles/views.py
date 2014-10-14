import shutil
import os
from datetime import date
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render_to_response
from django.template import loader, RequestContext
from django.core.urlresolvers import reverse
from django.template import Template
from django.http import HttpResponse, Http404
from django.forms.formsets import formset_factory
from django.utils.text import truncate_words
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.core.paginator import Paginator, InvalidPage
from django.template.loader import render_to_string
from django.template.defaultfilters import slugify

from zorna.acl.models import get_allowed_objects, get_acl_by_object
from zorna.site.email import ZornaEmail
from zorna.articles.models import ArticleCategory, ArticleStory, ArticleAttachments, ArticleComments, ArticleTags
from zorna.articles.forms import ArticleCategoryForm, ArticleStoryForm, ArticleAttachmentsForm, ArticleCommentsForm, ArticleTagForm
from zorna.utilit import get_upload_articles_images, get_upload_articles_files, resize_image
from zorna.account.models import UserAvatar


def admin_list_articles_tags(request):
    if request.user.is_superuser:
        ob_list = ArticleTags.objects.all()
        extra_context = {}
        extra_context['tags_list'] = ob_list
        context = RequestContext(request)
        return render_to_response('articles/list_tags.html', extra_context, context_instance=context)
    else:
        return HttpResponseRedirect('/')

@login_required()
def admin_add_articles_tag(request):
    if request.user.is_superuser:
        if request.method == 'POST':
            form = ArticleTagForm(request.POST)
            if form.is_valid():
                tag_name = form.cleaned_data['tag']

                if not tag_name in ArticleTags.objects.values_list('name', flat=True):
                    tag = ArticleTags(name=tag_name, slug=slugify(tag_name))
                    tag.save()
                return HttpResponseRedirect(reverse('admin_list_articles_tags'))
            else:
                form = ArticleTagForm(request.POST)
        else:
            form = ArticleTagForm()

        context = RequestContext(request)
        extra_context = {'form': form, 'curtag': False}
        return render_to_response('articles/edit_tag.html', extra_context, context_instance=context)
    else:
        return HttpResponseRedirect('/')


@login_required()
def admin_edit_articles_tag(request, tag):
    if request.user.is_superuser:
        tag = ArticleTags.objects.get(pk=tag)
        if request.method == 'POST':
            if request.POST.has_key('bdelete'):
                tag.delete()
                return HttpResponseRedirect(reverse('admin_list_articles_tags'))
            form = ArticleTagForm(request.POST, initial={'tag': tag.name})
            if form.is_valid():
                tag_name = form.cleaned_data['tag']
                tag.name = tag_name
                tag.slug = slugify(tag_name)
                tag.save()
                return HttpResponseRedirect(reverse('admin_list_articles_tags'))
        else:
            form = ArticleTagForm(initial={'tag': tag.name})

        context = RequestContext(request)
        extra_context = {'form': form, 'curtag': tag}
        return render_to_response('articles/edit_tag.html', extra_context, context_instance=context)
    else:
        return HttpResponseRedirect('/')



@login_required()
def admin_list_categories(request):
    if request.user.is_superuser:
        ob_list = ArticleCategory.objects.all()
        extra_context = {}
        extra_context['categories_list'] = ob_list
        context = RequestContext(request)
        return render_to_response('articles/list_categories.html', extra_context, context_instance=context)
    else:
        return HttpResponseRedirect('/')


@login_required()
def admin_add_category(request):
    if request.user.is_superuser:
        if request.method == 'POST':
            form = ArticleCategoryForm(request.POST)
            if form.is_valid():
                category = form.save(commit=False)
                category.owner = request.user
                category.save()
                ct = ContentType.objects.get_for_model(category)
                return HttpResponseRedirect(reverse('acl_groups_object', args=[ct.pk, category.pk]) + '?next=' + reverse('admin_list_categories'))
                # return HttpResponseRedirect(reverse('admin_list_categories'))
            else:
                form = ArticleCategoryForm(request.POST)
        else:
            form = ArticleCategoryForm()

        context = RequestContext(request)
        extra_context = {'form': form, 'curcategory': False}
        return render_to_response('articles/edit_category.html', extra_context, context_instance=context)
    else:
        return HttpResponseRedirect('/')


@login_required()
def admin_edit_category(request, category):
    if request.user.is_superuser:
        c = ArticleCategory.objects.get(pk=category)
        if request.method == 'POST':
            form = ArticleCategoryForm(request.POST, instance=c)
            if form.is_valid():
                form.save()
                if 'childs_ids' in request.POST and request.POST['childs_ids']:
                    ids = request.POST['childs_ids'].split(',')
                    last_m = ArticleCategory.objects.get(pk=ids.pop(0))
                    last_m.move_to(last_m.parent, position='first-child')
                    for id in ids:
                        last_m = ArticleCategory.objects.get(pk=last_m.id)
                        m = ArticleCategory.objects.get(pk=id)
                        m.move_to(last_m, position='right')
                        last_m = m
                return HttpResponseRedirect(reverse('admin_list_categories'))
        else:
            form = ArticleCategoryForm(instance=c)

        context = RequestContext(request)
        extra_context = {'form': form, 'curcategory': c}
        return render_to_response('articles/edit_category.html', extra_context, context_instance=context)
    else:
        return HttpResponseRedirect('/')


def admin_order_categories(request):
    if request.user.is_superuser:
        fields = request.GET.getlist('category-table-dnd[]')
        if len(fields):
            last_m = ArticleCategory.objects.get(pk=fields.pop(0))
            last_m.move_to(last_m.parent, position='first-child')
            for id in fields:
                last_m = ArticleCategory.objects.get(pk=last_m.id)
                m = ArticleCategory.objects.get(pk=id)
                m.move_to(last_m, position='right')
                last_m = m
            return HttpResponseRedirect(reverse('admin_list_categories'))
        ob_list = ArticleCategory.objects.filter(parent__isnull=True)
        extra_context = {}
        extra_context['categories_list'] = ob_list
        context = RequestContext(request)
        return render_to_response('articles/order_categories.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def view_category(request, category, year=None, month=None):
    allowed_objects = get_allowed_objects(
        request.user, ArticleCategory, 'reader')
    if category.pk in allowed_objects:
        template = None
        if category.template == '':
            anc = category.get_ancestors(True)
            for parent in anc:
                if parent.template != '':
                    template = parent.template
                    break
        else:
            template = category.template

        extra_context = {}
        extra_context['category'] = category
        extra_context['zorna_title_page'] = category.name
        if year and month:
            story_lists = ArticleStory.objects.filter(
                categories__exact=category, time_created__year=year, time_created__month=month).order_by('-time_updated')
            extra_context['category_archive_date'] = date(
                int(year), int(month), 1)
        else:
            extra_context['category_archive_date'] = None
            story_lists = ArticleStory.objects.filter(
                categories__exact=category).order_by('-time_updated')

        extra_context['category_archive_dates'] = ArticleStory.objects.filter(
            categories=category).annotate(Count('title')).dates('time_created', 'month', order='DESC')
        extra_context['ancestors'] = category.get_ancestors()
        extra_context['object_list'] = story_lists
        if template:
            t = Template(template)
        else:
            try:
                t = loader.get_template('category_default.html')
            except:
                t = loader.get_template("articles/category_default.html")

        paginate_by = 10
        paginator = Paginator(
            story_lists._clone(), paginate_by, allow_empty_first_page=True)
        page = request.GET.get('page', 1)
        try:
            page_number = int(page)
        except ValueError:
            if page == 'last':
                page_number = paginator.num_pages
            else:
                # Page is not 'last', nor can it be converted to an int.
                raise Http404
        try:
            page_obj = paginator.page(page_number)
        except InvalidPage:
            raise Http404

        extra_context['paginator'] = paginator
        extra_context['page_obj'] = page_obj

        c = RequestContext(request, extra_context)
        return HttpResponse(t.render(c))
    else:
        return HttpResponseRedirect('/')


def view_category_archive(request, category, year, month):
    return view_category(request, category, year, month)


def notify_users(request, story, categories, new_article=True):
    bnotify = request.POST.get('notify_users', 0)
    users_email = []
    for cat in categories:
        if cat.email_notification and (cat.email_notification == 1 or bnotify):
            acl_users = get_acl_by_object(cat, 'reader')
            if acl_users:
                users_email.extend([u.email for u in acl_users])

    users_email = list(set(users_email))
    if users_email:
        email = ZornaEmail()
        url = request.build_absolute_uri(reverse(
            'view_story', args=[categories[0].pk, story.pk, story.slug]))
        ec = {"story": story, 'url': url, 'new_article':
              new_article, 'user': request.user}
        body_text = render_to_string(
            'articles/email_notification_text.html', ec)
        body_html = render_to_string(
            'articles/email_notification_html.html', ec)
        if new_article:
            subject = _(u'A new article has been published')
        else:
            subject = _(u'An article has been updated')
        step = getattr(settings, "ZORNA_MAIL_MAXPERPACKET", 25)
        for n in range(0, len(users_email) / step + 1):
            email.append(subject, body_text, body_html, settings.DEFAULT_FROM_EMAIL, bcc=users_email[
                         n * step:(n + 1) * step])
        email.send()


@login_required()
def add_new_story(request):
    allowed_objects = get_allowed_objects(
        request.user, ArticleCategory, 'writer')
    if len(allowed_objects) == 0:
        return HttpResponseRedirect('/')

    if request.method == 'POST':
        form_story = ArticleStoryForm(request.POST, request.FILES, request=request)
        fa_set = formset_factory(ArticleAttachmentsForm, extra=2)
        form_attachments_set = fa_set(request.POST, request.FILES)
        if form_story.is_valid():
            if 'image' in request.FILES:
                image_file = request.FILES['image']
                mimetype = image_file.content_type
            else:
                image_file = None
                mimetype = ''

            if image_file:
                story = form_story.save()
                upload_path = get_upload_articles_images()
                path_src = u"%s/%s" % (upload_path, story.image)
                path_dest = u"%s/%s" % (upload_path, story.pk)
                os.makedirs(path_dest)
                shutil.move(path_src, path_dest)
                s = os.path.splitext(image_file.name)
                filename = u"%s%s" % (slugify(s[0]), s[1])
                story.image = "%s/%s" % (story.pk, filename)
            else:
                story = form_story.save(commit=False)

            story.mimetype = mimetype
            story.owner = request.user
            story.save()

            story.categories.clear()
            selected_categories = request.POST.getlist('_selected_action')
            story.categories = selected_categories

            if form_attachments_set.is_valid():
                for i in range(0, form_attachments_set.total_form_count()):
                    form = form_attachments_set.forms[i]
                    try:
                        file = request.FILES['form-' + str(
                            i) + '-attached_file']
                        attachment = ArticleAttachments(description=form.cleaned_data[
                                                        'description'], mimetype=file.content_type)
                        attachment.article = story
                        attachment.save()
                        attachment.attached_file.save(file.name, file)
                    except:
                        pass

            tags = map(int, request.POST.getlist('article_tags[]'))
            tags = ArticleTags.objects.filter(pk__in=tags)
            story.tags.add(*tags)

            if story.categories:
                notify_users(request, story, story.categories.all(), True)

            return HttpResponseRedirect(reverse('writer_stories_list', args=[]))
    else:
        form_story = ArticleStoryForm(request=request)
        fa_set = formset_factory(ArticleAttachmentsForm, extra=2)
        form_attachments_set = fa_set()

    tags = ArticleTags.objects.all()
    context = RequestContext(request)
    extra_context = {'form_story': form_story,
                    'form_attachments': form_attachments_set,
                    'tags': tags,
                    }
    return render_to_response('articles/new_article.html', extra_context, context_instance=context)


@login_required()
def edit_story(request, story):
    allowed_objects = get_allowed_objects(
            request.user, ArticleCategory, 'manager')
    try:
        story = ArticleStory.objects.select_related().get(pk=story)
        categories = story.categories.all()
        intersect = set(allowed_objects).intersection( set([category.pk for category in categories]))
        if story.owner != request.user and not intersect:
            return HttpResponseRedirect('/')
    except Exception as e:
        print e
        return HttpResponseRedirect('/')

    attachments = story.articleattachments_set.all()
    if request.method == 'POST':
        if 'bdelstory' in request.POST:
            story.articleattachments_set.all().delete()
            pk = story.pk
            story.delete()
            try:
                shutil.rmtree(u"%s/%s" % (get_upload_articles_images(), pk))
            except:
                pass
            try:
                shutil.rmtree(u"%s/%s" % (get_upload_articles_files(), pk))
            except:
                pass
            return HttpResponseRedirect(reverse('writer_stories_list', args=[]))

        form_story = ArticleStoryForm(
            request.POST, request.FILES, instance=story, request=request)
        if form_story.is_valid():
            if 'selected_image' in request.POST:
                story.image.delete()
                try:
                    shutil.rmtree(u"%s/%s" % (get_upload_articles_images(), story.pk))
                except:
                    pass
            if 'image' in request.FILES:
                story.mimetype = request.FILES['image'].content_type
            else:
                image_file = None

            story.modifier = request.user
            story.save()

            story.categories.clear()
            selected_categories = request.POST.getlist('_selected_action')
            story.categories = selected_categories

        form_story = ArticleStoryForm(instance=story, request=request)

        if len(attachments) < 2:
            fa_set = formset_factory(
                ArticleAttachmentsForm, extra=2 - len(attachments))
            form_attachments_set = fa_set(request.POST, request.FILES)
            if form_attachments_set.is_valid():
                for i in range(0, form_attachments_set.total_form_count()):
                    form = form_attachments_set.forms[i]
                    try:
                        file = request.FILES['form-' + str(
                            i) + '-attached_file']
                        attachment = ArticleAttachments(description=form.cleaned_data[
                                                        'description'], mimetype=file.content_type)
                        attachment.article = story
                        attachment.save()
                        attachment.attached_file.save(file.name, file)
                    except:
                        pass

        if 'selected_attachments' in request.POST:
            att = request.POST.getlist('selected_attachments')
            ArticleAttachments.objects.filter(pk__in=att).delete()
        attachments = story.articleattachments_set.all()
        extra = len(attachments)
        if extra < 2:
            fa_set = formset_factory(ArticleAttachmentsForm, extra=2 - extra)
            form_attachments_set = fa_set()
        else:
            form_attachments_set = None

        tags = map(int, request.POST.getlist('article_tags[]'))
        story.tags.clear()
        tags = ArticleTags.objects.filter(pk__in=tags)
        story.tags.add(*tags)
        if story.categories:
            notify_users(request, story, story.categories.all(), False)

    else:
        form_story = ArticleStoryForm(instance=story, request=request)
        extra = len(attachments)
        if extra < 2:
            fa_set = formset_factory(ArticleAttachmentsForm, extra=2 - extra)
            form_attachments_set = fa_set()
        else:
            form_attachments_set = None

    tags = ArticleTags.objects.all()
    story_tags = story.tags.all()
    for tag in tags:
        if tag in story_tags:
            tag.checked = True
    context = RequestContext(request)
    extra_context = {'form_story': form_story,
                     'story': story,
                     'tags': tags,
                     'form_attachments': form_attachments_set,
                     'attachments': attachments,
                     'categories': [c.pk for c in categories],
                     }
    return render_to_response('articles/edit_article.html', extra_context, context_instance=context)


def get_story_image(request, story, size=None):
    try:
        story = ArticleStory.objects.select_related().get(pk=story)
        allowed_objects = get_allowed_objects(
            request.user, ArticleCategory, 'reader')
        al = story.categories.filter(pk__in=allowed_objects)
        if len(al) == 0:
            return HttpResponseRedirect('/')
    except:
        return HttpResponseRedirect('/')

    path = u"%s/%s" % (get_upload_articles_images(), story.image)
    if size:
        miniature = resize_image(story.image.path, size)
        split = path.rsplit('/', 1)
        path = '%s/%s' % (split[0], miniature)

    try:
        image_data = open(path, "rb").read()
        return HttpResponse(image_data, mimetype=story.mimetype)
    except:
        return HttpResponse('')


def get_story_file(request, file_id):
    try:
        file = ArticleAttachments.objects.get(pk=file_id)
        story = file.article
        allowed_objects = get_allowed_objects(
            request.user, ArticleCategory, 'reader')
        al = story.categories.filter(pk__in=allowed_objects)
        if len(al) == 0:
            return HttpResponseForbidden()
    except:
        return HttpResponseForbidden()

    path = "%s/%s" % (get_upload_articles_files(), file.attached_file.name)
    fp = open(path, 'rb')
    content_type = file.mimetype
    response = HttpResponse(fp.read(), content_type=content_type)
    response['Content-Length'] = os.path.getsize(path)
    response['Content-Disposition'] = "attachment; filename=%s" % os.path.basename(
        file.attached_file.name)
    return response


def view_story(request, category, story, slug):
    allowed_objects = get_allowed_objects(
        request.user, ArticleCategory, 'reader')
    category = int(category)
    if category in allowed_objects:
        category = ArticleCategory.objects.get(pk=category)
        try:
            story = ArticleStory.objects.get(pk=story, categories=category)
        except ArticleStory.DoesNotExist:
            return HttpResponseForbidden()
        story.edit_url = story.get_edit_url(request.user)
        extra_context = {}
        extra_context['ancestors'] = category.get_ancestors()
        extra_context['category'] = category
        extra_context['story'] = story
        extra_context['story_comments'] = ArticleComments.objects.filter(
            article=story)
        extra_context['zorna_title_page'] = story.title
        try:
            avatar_user = UserAvatar.objects.get(user=story.owner)
        except UserAvatar.DoesNotExist:
            avatar_user = None
        extra_context['avatar_user'] = avatar_user
        extra_context['recent_stories'] = ArticleStory.objects.filter(
            owner=story.owner, categories__in=allowed_objects).distinct().exclude(pk=story.pk).order_by('-time_created')[0:10]
        for s in extra_context['recent_stories']:
            s.category = s.categories.all()[0]
        context = RequestContext(request)
        return render_to_response(['story_%s.html' % category.slug, 'story_default.html', 'articles/story_default.html'], extra_context, context_instance=context)
    else:
        return HttpResponseRedirect('/')


def add_story_comment(request, story):
    # TODO check if comment is authorized on this story
    if request.method == 'POST':
        form = ArticleCommentsForm(request.POST)
        if form.is_valid():
            com = form.save(commit=False)
            if form.cleaned_data['title'] == '':
                com.title = truncate_words(com.comment, 4, '')
            com.article_id = story
            com.owner = request.user
            com.save()
    return HttpResponseRedirect(request.META['HTTP_REFERER'])


@login_required()
def writer_stories_list(request):
    q = request.GET.get('q', None)
    aom = get_allowed_objects(
            request.user, ArticleCategory, 'manager')
    aow = get_allowed_objects(
            request.user, ArticleCategory, 'writer')
    if q:
        ob_list = ArticleStory.objects.filter(Q(title__icontains=q) & (Q(owner=request.user) | Q(categories__in=aom))).annotate(
        Count('categories')).order_by('-time_updated')
    else:
        ob_list = ArticleStory.objects.filter(Q(owner=request.user) | Q(categories__in=aom)).annotate(
        Count('categories')).order_by('-time_updated')
    extra_context = {}
    context = RequestContext(request)
    if ob_list or aow:
        extra_context['stories_list'] = ob_list
        return render_to_response('articles/writer_stories_list.html', extra_context, context_instance=context)

    return HttpResponseForbidden()
