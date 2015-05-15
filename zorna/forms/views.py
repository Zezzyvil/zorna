import os
from os.path import join
from mimetypes import guess_type
from django.conf import settings
from django.utils.encoding import smart_unicode, smart_str
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext_noop
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext, loader, Template, TemplateDoesNotExist
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory
from django.core.urlresolvers import reverse
from django.utils import simplejson
from django.http import HttpResponse
from django.db.models import Max
from csv import writer
from datetime import datetime
from django.template.defaultfilters import slugify
from django.core.files.storage import FileSystemStorage
from django.contrib.auth.decorators import login_required
try:
    from PIL import Image
except ImportError:
    import Image

from zorna.forms import fields
from zorna.acl.models import get_acl_for_model
from zorna.acl.models import get_allowed_objects
from zorna.utilit import get_upload_forms_attachments, resize_image
from zorna.forms.api import isUserManager, forms_form_browse_entries, forms_get_entry, forms_delete_entry
from zorna.forms.models import FormsList, FormsListEntry, FormsWorkspace, FormsFormPanel, \
    FormsForm, FormsFormField, FormsFieldEntry, FormsFormAction, FormsFormActionMessage, FormsFormActionUrl
from zorna.forms.forms import FormsListForm, FormsListEntryForm, FormsWorkspaceForm, \
    FormsFormForm, FormsFormFieldForm, FormForForm, FormsExportForm, FormsFormTemplateForm, FormsFormEntry, \
    FormsFormImportCsv, forms_factory, FormsFormFormEmail, FormsFormActionMessageForm, FormsFormActionUrlForm, \
    FormsFormPanelForm, FormsFormDuplicate


def get_user_workspaces(request):
    ao = get_allowed_objects(request.user, FormsWorkspace, 'manager')
    return FormsWorkspace.objects.filter(pk__in=ao)


@login_required()
def list_workspaces(request):
    if request.user.is_superuser:
        ob_list = FormsWorkspace.objects.all()
        extra_context = {}
        extra_context['workspace_list'] = ob_list
        context = RequestContext(request)
        return render_to_response('forms/list_workspaces.html', extra_context, context_instance=context)
    else:
        return HttpResponseRedirect('/')


@login_required()
def admin_add_workspace(request):
    if request.user.is_superuser:
        if request.method == 'POST':
            form = FormsWorkspaceForm(request.POST)
            if form.is_valid():
                ws = form.save(commit=False)
                ws.owner = request.user
                ws.save()
                return HttpResponseRedirect(reverse('list_workspaces'))
            else:
                form = FormsWorkspaceForm(request.POST)
        else:
            form = FormsWorkspaceForm()

        context = RequestContext(request)
        extra_context = {'form': form, 'curworkspace': False}
        return render_to_response('forms/edit_workspace.html', extra_context, context_instance=context)
    else:
        return HttpResponseRedirect('/')


@login_required()
def admin_edit_workspace(request, workspace):
    if request.user.is_superuser:
        c = get_object_or_404(FormsWorkspace, pk=workspace)
        if request.method == 'POST':
            form = FormsWorkspaceForm(request.POST, instance=c)
            if form.is_valid():
                form.save()
                return HttpResponseRedirect(reverse('list_workspaces'))
        else:
            form = FormsWorkspaceForm(instance=c)

        context = RequestContext(request)
        extra_context = {'form': form, 'curworkspace': c}
        return render_to_response('forms/edit_workspace.html', extra_context, context_instance=context)
    else:
        return HttpResponseRedirect('/')


def forms_view_design_form(request, form):
    args = (form, None, None)
    form_for_form = FormForForm(*args)
    t = loader.get_template("forms/form_body.html")
    c = RequestContext(request, {"form": form, "form_for_form":
                       form_for_form, "form_design": True})
    return t.render(c)


def get_forms_navigation(request, slug, form=None):
    fw = isUserManager(request, slug)
    if fw:
        ob_list = FormsForm.objects.filter(workspace=fw)
        t = loader.get_template('forms/forms_navigation.html')
        for ob in ob_list:
            ob.zfields = ob.fields.all()
        if len(ob_list) and form is None:
            current_form = ob_list[0]
        else:
            current_form = form
        lists = FormsList.objects.filter(workspace=fw)
        c = RequestContext(request, {
                           "forms_list": ob_list, 'workspace': fw, 'current_form': current_form, 'lists': lists})
        return t.render(c)
    else:
        return ''


def forms_json_forms(request, slug):
    fw = isUserManager(request, slug)
    if fw and request.user.is_authenticated() :
        ret = {}
        ob_list = FormsForm.objects.filter(workspace=fw)
        for ob in ob_list:
            ob.zfields = ob.fields.all()
        source = []

        for item in ob_list:
            items = {}
            items['title'] = item.name
            items['isFolder'] = True
            items['children'] = []
            items['pk'] = item.pk
            items['url'] = reverse('forms_form', args=[item.pk])
            for field in item.fields.all():
                items['children'].append(
                    {'title': field.label,
                    'url': reverse('forms_form_edit_field', args=[field.pk]),
                    'pk':field.pk})
            source.append(items)
        json_data = simplejson.dumps(source)
        return HttpResponse(json_data)
    else:
        return HttpResponseForbidden()


def forms_json_lists(request, slug):
    fw = isUserManager(request, slug)
    if fw and request.user.is_authenticated() :
        ret = {}
        lists = FormsList.objects.filter(workspace=fw)
        source = []

        items = {}
        items['title'] = u'Lists'
        items['isFolder'] = True
        items['children'] = []
        items['url'] = reverse('forms_lists_list', args=[slug])
        for item in lists:
            items['children'].append(
                {'title': item.name,
                'url': reverse('forms_edit_list', args=[item.pk]),
                'pk':item.pk})
        source.append(items)
        json_data = simplejson.dumps(source)
        return HttpResponse(json_data)
    else:
        return HttpResponseForbidden()

@login_required()
def forms_home(request, slug, form=None):
    if request.user.is_authenticated():
        fw = isUserManager(request, slug)
        if fw:
            extra_context = {}
            context = RequestContext(request)
            extra_context['zorna_title_page'] = _(u'Forms')
            extra_context['workspace'] = fw
            if form:
                extra_context['url_frame'] = reverse('forms_form', args=[form])
            else:
                try:
                    extra_context['url_frame'] = reverse('forms_form', args=[
                                                         FormsForm.objects.filter(workspace=fw)[0].pk])
                except:
                    extra_context['url_frame'] = ''
            return render_to_response('forms/home.html', extra_context, context_instance=context)
        else:
            return HttpResponseForbidden()
    else:
        return HttpResponseForbidden()


def forms_form(request, form, extra={}):
    try:
        form = FormsForm.objects.select_related(depth=1).get(pk=form)
        fw = isUserManager(request, form.workspace.slug)
        if fw is False:
            return HttpResponseForbidden()
    except:
        return HttpResponseForbidden()

    if request.user.is_authenticated():
        extra_context = dict(**extra)
        t = loader.get_template('forms/forms_path.html')
        c = RequestContext(request,
                           {'path_url': reverse('forms_form', args=[form.pk]),
                            'path_url_text': form.name,
                            'item_name': None,
                            'workspaces': get_user_workspaces(request),
                            'current_workspace': fw.slug,
                            })
        extra_context['forms_path'] = t.render(c)

        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['current_form'] = form
        extra_context['form_details'] = forms_view_design_form(request, form)
        return render_to_response('forms/forms_form.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_form_test(request, form, extra={}):
    try:
        form = FormsForm.objects.select_related(depth=1).get(pk=form)
        fw = isUserManager(request, form.workspace.slug)
        if fw is False:
            return HttpResponseForbidden()
    except:
        return HttpResponseForbidden()

    args = (form,)
    form_for_form = FormForForm(*args)
    if request.user.is_authenticated():
        extra_context = dict(**extra)
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['form'] = form
        extra_context['form_for_form'] = form_for_form
        extra_context['form_design'] = True
        return render_to_response('forms/forms_form_test.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_form_print(request, form, entry=None, extra={}):
    try:
        form = FormsForm.objects.select_related(depth=1).get(pk=form)
        check = get_acl_for_model(form)
        if not check.viewer_formsform(form, request.user) and not check.creator_formsform(form, request.user) and not isUserManager(request, form.workspace.slug):
            return HttpResponseForbidden()
    except:
        return HttpResponseForbidden()

    if entry:
        entry = FormsFormEntry.objects.get(pk=entry)

    args = (form, request.POST or None, None)
    form_for_form = FormForForm(*args, instance=entry)
    extra_context = dict(**extra)
    context = RequestContext(request)
    extra_context['zorna_title_page'] = _(u'Forms')
    extra_context['form'] = form
    extra_context['form_for_form'] = form_for_form
    extra_context['form_design'] = True
    extra_context['form_print'] = True
    extra_context['controls_multiple'] = [
        'CheckboxSelectMultiple', 'RadioSelect', 'SelectMultiple']
    return render_to_response('forms/forms_form_print.html', extra_context, context_instance=context)


def add_bind_entry_field(form, bind):
    r = bind.split('.')
    slug = '%s_%s' % (r[1], r[0])
    if r[1] == 'zorna_owner':
        label = _(u"User")
        form_field = FormsFormField(
            form=form, label=label, slug=slug, field_type=fields.ZORNA_USER_SINGLETON)
        form_field.save()
    else:
        field = FormsFormField.objects.get(slug=r[1], form__slug=r[0])
        label = field.label
        form_field = FormsFormField(
            form=form, label=label, slug=r[1], field_type=fields.FORM_ENTRY)
        form_field.save()


def delete_bind_entry_field(form, bind):
    r = bind.split('.')
    if r[1] == 'zorna_owner':
        FormsFormField.objects.get(
            form=form, field_type=fields.ZORNA_USER_SINGLETON).delete()
    else:
        FormsFormField.objects.get(
            form=form, field_type=fields.FORM_ENTRY).delete()
    FormsFormEntry.objects.filter(form=form).update(entry=None)


def update_bind_entry_field(form, bind):
    r = bind.split('.')
    if r[1] != 'zorna_owner':
        field = FormsFormField.objects.get(slug=r[1], form__slug=r[0])
        label = field.label
        form_field = FormsFormField.objects.get(
            form=form, field_type=fields.FORM_ENTRY)
        form_field.label = label
        form_field.slug = r[1]
        form_field.save()
    FormsFormEntry.objects.filter(form=form).update(entry=None)


@login_required()
def forms_add_form(request, slug):
    fw = isUserManager(request, slug)
    if request.user.is_authenticated() and fw:
        if request.method == 'POST':
            form = FormsFormForm(request.POST, request=request)
            if form.is_valid():
                f = form.save(commit=False)
                f.owner = f.modifier = request.user
                f.workspace = fw
                f.save()
                if f.bind_to_account:
                    form_field = FormsFormField(
                        form=f, label=ugettext_noop(u'User'), slug='zorna_owner', field_type=fields.ZORNA_USER_SINGLETON)
                    form_field.save()
                if f.bind_to_entry:
                    add_bind_entry_field(form, f.bind_to_entry)
                return forms_form(request, f.pk, extra={'load_navigation': True})
        else:
            form = FormsFormForm(request=request)

        extra_context = {}
        extra_context['form'] = form
        extra_context['current_form'] = None
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        return render_to_response('forms/new_form.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_edit_form(request, form):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        extra_context = {}
        context = RequestContext(request)
        if request.method == 'POST':
            if request.POST.has_key('bdelete'):
                fs = FileSystemStorage(location=get_upload_forms_attachments())
                path = join(fs.location, str(form.pk))
                if os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path)
                form.delete()
                try:
                    f = FormsForm.objects.filter(workspace=fw)[0].pk
                    return forms_form(request, f.pk, extra={'load_navigation': True})
                except:
                    return render_to_response('forms/empty_frame.html', {'load_navigation': True}, context_instance=context)

            bind_to_account = form.bind_to_account
            bind_to_entry = form.bind_to_entry
            form_form = FormsFormForm(request.POST, instance=form, request=request)
            if form_form.is_valid():
                f = form_form.save(commit=False)
                f.modifier = request.user
                if not bind_to_account and f.bind_to_account:
                    form_field = FormsFormField(
                        form=f, label=ugettext_noop(u'User'), slug='zorna_owner', field_type=fields.ZORNA_USER_SINGLETON)
                    form_field.save()
                elif bind_to_account and not f.bind_to_account:
                    FormsFormField.objects.get(
                        form=f, field_type=fields.ZORNA_USER_SINGLETON).delete()

                if not bind_to_entry and f.bind_to_entry:
                    add_bind_entry_field(form, f.bind_to_entry)
                elif bind_to_entry and not f.bind_to_entry:
                    delete_bind_entry_field(form, bind_to_entry)
                elif bind_to_entry and f.bind_to_entry and bind_to_entry != f.bind_to_entry:
                    update_bind_entry_field(form, f.bind_to_entry)
                f.save()
                return forms_form(request, f.pk, extra={'load_navigation': True})
        else:
            form_form = FormsFormForm(instance=form, request=request)

        extra_context['form'] = form_form
        extra_context['current_form'] = form
        extra_context['zorna_title_page'] = _(u'Forms')
        return render_to_response('forms/new_form.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


TAB_STYLES = ['width', 'margin', 'padding',
              'css_class', 'bg_color',
              'border_width', 'border_style',
              'border_color', 'label_color',
              'label_size', 'bold',
              'italic']


def forms_form_add_field(request, form):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        extra_context = {}
        if request.method == 'POST':
            field_form = FormsFormFieldForm(request.POST)
            if field_form.is_valid():
                fmax = FormsFormField.objects.filter(
                    form=form).aggregate(max_sort_order=Max('sort_order'))
                max_order = fmax['max_sort_order'] if fmax[
                    'max_sort_order'] else 0
                fmax = FormsFormField.objects.filter(
                    form=form).aggregate(max_sort_order=Max('sort_order_list'))
                max_order_list = fmax['max_sort_order'] if fmax[
                    'max_sort_order'] else 0
                ff = field_form.save(commit=False)
                ff.sort_order = max_order
                ff.sort_order_list = max_order_list
                ff.form = form
                ff.save()
                if request.POST.has_key('bcontinue'):
                    # return
                    # HttpResponseRedirect(reverse('forms_form_add_field',
                    # args=[form.pk]))
                    field_form = FormsFormFieldForm(initial={'form': form})
                    extra_context['load_navigation'] = True
                else:
                    return forms_form(request, form.pk, {'load_navigation': True})

        field_form = FormsFormFieldForm(
            request.POST or None, initial={'form': form})
        field_form.fields['list'].queryset = FormsList.objects.filter(
            workspace=form.workspace)
        field_form.fields['panel'].queryset = FormsFormPanel.objects.filter(
            form=form)

        t = loader.get_template('forms/forms_path.html')
        c = RequestContext(request, {
                           'path_url': reverse('forms_form', args=[form.pk]),
                           'path_url_text': form.name,
                           'item_name': None,
                           'workspaces': get_user_workspaces(request),
                           'current_workspace': fw.slug,
                           })
        extra_context['forms_path'] = t.render(c)

        extra_context['tab_style'] = TAB_STYLES
        extra_context['form'] = field_form
        extra_context['current_field'] = None
        extra_context['current_form'] = form
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        return render_to_response('forms/new_field.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_form_edit_field(request, field):
    if request.user.is_authenticated():
        try:
            field = FormsFormField.objects.select_related(
                depth=1).get(pk=field)
            fw = isUserManager(request, field.form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        field_form = FormsFormFieldForm(request.POST or None, instance=field)
        if field.field_type >= fields.ZORNA_USER_SINGLETON:
            for f in ['slug', 'field_type', 'required', 'visible', 'default_value', 'reference', 'reference_display', 'list']:
                del field_form.fields[f]
        else:
            field_form.fields['list'].queryset = FormsList.objects.filter(
                workspace=field.form.workspace)
        field_form.fields['panel'].queryset = FormsFormPanel.objects.filter(
            form=field.form)

        if request.method == 'POST':
            extra = {'load_navigation': True}
            form_pk = field.form_id
            if field.field_type >= fields.ZORNA_USER_SINGLETON:
                if field_form.is_valid():
                    field.label = field_form.cleaned_data['label']
                    field.help_text = field_form.cleaned_data['help_text']
                    field.panel_id = field_form.cleaned_data['panel']
                    field.save()
                    return forms_form(request, form_pk, extra)
            else:
                if request.POST.has_key('bdelete'):
                    field.delete()
                    return forms_form(request, form_pk, extra)

                if field_form.is_valid():
                    field_form.save()
                    return forms_form(request, field.form_id, extra)

        extra_context = {}
        t = loader.get_template('forms/forms_path.html')
        c = RequestContext(request, {
                           'path_url': reverse('forms_form', args=[field.form_id]),
                           'path_url_text': field.form.name,
                           'item_name': field.label,
                           'workspaces': get_user_workspaces(request),
                           'current_workspace': fw.slug,
                           })
        extra_context['forms_path'] = t.render(c)

        extra_context['tab_style'] = TAB_STYLES
        extra_context['form'] = field_form
        extra_context['current_field'] = field
        extra_context['current_form'] = field.form
        if field.field_type >= fields.ZORNA_USER_SINGLETON:
            extra_context['delete_button'] = False
        else:
            extra_context['delete_button'] = True

        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        return render_to_response('forms/new_field.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_lists_list(request, slug, extra={}):
    if request.user.is_authenticated():
        fw = isUserManager(request, slug)
        if fw:
            extra_context = dict(**extra)
            t = loader.get_template('forms/forms_path.html')
            c = RequestContext(request, {'path_url': reverse('forms_lists_list', args=[
                               slug]), 'path_url_text': _(u'Lists'), 'item_name': None})
            extra_context['forms_path'] = t.render(c)

            extra_context['lists'] = FormsList.objects.filter(workspace=fw)
            context = RequestContext(request)
            extra_context['zorna_title_page'] = _(u'Forms')
            extra_context['workspace'] = fw
            return render_to_response('forms/list_lists.html', extra_context, context_instance=context)
        else:
            return HttpResponseForbidden()
    else:
        return HttpResponseForbidden()


def forms_add_list(request, slug):
    if request.user.is_authenticated():
        fw = isUserManager(request, slug)
        if fw is False:
            return HttpResponseForbidden()

        if request.method == 'POST':
            form_list = FormsListForm(request.POST)
            entry_form_set = formset_factory(FormsListEntryForm)
            form_set = entry_form_set(request.POST)
            if form_list.is_valid():
                if form_set.is_valid():
                    fl = form_list.save(commit=False)
                    fl.workspace = fw
                    fl.save()
                    for i in range(0, form_set.total_form_count()):
                        form = form_set.forms[i]
                        try:
                            value = form.cleaned_data['value']
                            if value:
                                entry = FormsListEntry(
                                    value=form.cleaned_data['value'])
                                entry.list = fl
                                entry.save()
                        except:
                            pass
                    return forms_lists_list(request, slug, extra={'load_navigation': True})
        else:
            form_list = FormsListForm()
            entry_form_set = formset_factory(FormsListEntryForm, extra=2)
            form_set = entry_form_set()

        extra_context = {}
        t = loader.get_template('forms/forms_path.html')
        c = RequestContext(request, {'path_url': reverse('forms_lists_list', args=[
                           slug]), 'path_url_text': _(u'Lists'), 'item_name': None})
        extra_context['forms_path'] = t.render(c)

        extra_context['form'] = form_list
        extra_context['form_set'] = form_set
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        return render_to_response('forms/new_list.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_edit_list(request, list):
    if request.user.is_authenticated():
        try:
            list = FormsList.objects.get(pk=list)
            ao = get_allowed_objects(request.user, FormsWorkspace, 'manager')
            fw = list.workspace
            if fw.pk not in ao:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        if request.method == 'POST':
            form_list = FormsListForm(request.POST, instance=list)
            entry_form_set = inlineformset_factory(
                FormsList, FormsListEntry, can_delete=True)
            form_set = entry_form_set(request.POST, instance=list)
            if form_list.is_valid():
                form_list.save()
                if form_set.is_valid():
                    instances = form_set.save(commit=False)
                    for instance in instances:
                        instance.list = list
                        instance.save()
                    return forms_lists_list(request, fw.slug, extra={'load_navigation': True})
        else:
            form_list = FormsListForm(instance=list)
            entry_form_set = inlineformset_factory(
                FormsList, FormsListEntry, can_delete=True, extra=1)
            form_set = entry_form_set(instance=list)

        extra_context = {}
        extra_context['form'] = form_list
        extra_context['form_set'] = form_set

        t = loader.get_template('forms/forms_path.html')
        c = RequestContext(request, {'path_url': reverse('forms_lists_list', args=[
                           fw.slug]), 'path_url_text': _(u'Lists'), 'item_name': list.name})
        extra_context['forms_path'] = t.render(c)

        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        return render_to_response('forms/new_list.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_edit_form_entry(request, entry):

    try:
        entry = FormsFormEntry.objects.get(pk=entry)
        form = entry.form
        check = get_acl_for_model(form)
        if not check.modifier_formsform(form, request.user):
            return HttpResponseForbidden()
    except:
        return HttpResponseForbidden()

    rget = request.GET  # {'lot.designation': '110'}
    args = (form, request.POST or None, request.FILES or None)
    form_for_form = FormForForm(*args, instance=entry, rget=rget)
    bdelete = True
    try:
        if settings.ZORNA_CRM_CUSTOMERS_FORM.split('.')[0] == form.slug:
            bdelete = False
    except:
        pass

    if request.method == "POST":
        if 'bdelete' in request.POST and bdelete:
            forms_delete_entry(entry)
            return HttpResponseRedirect(reverse('form_browse_entries_view', args=[form.slug]))

        if form_for_form.is_valid():
            entry = form_for_form.save(request=request)
            return HttpResponseRedirect(reverse('form_browse_entries_view', args=[form.slug]) + '?where=' + request.POST.get('where', ''))

    if form.template:
        t = Template(form.template)
    else:
        try:
            t = loader.get_template('forms_edit_%s.html' % form.slug)
        except:
            t = loader.get_template("forms/form_details.html")

    extra_context = {"form": form, "form_for_form":
                     form_for_form, 'bdelete': bdelete}
    extra_context['where'] = rget.get('where', '')
    extra_context['entry'] = entry
    extra_context['parents'] = []
    if entry.entry:
        try:
            bte = form.bind_to_entry.split('.')
            while entry.entry:
                e = FormsFormEntry.objects.select_related().get(
                    pk=entry.entry.pk, form__slug=bte[0])
                c, r = forms_get_entry(e)
                extra_context['parents'].append({'row': r[bte[1]], 'entry': e})
                if not e.form.bind_to_entry:
                    break
                bte = e.form.bind_to_entry.split('.')
                entry = e
        except Exception as e:
            extra_context['parents'] = []
    extra_context['parents'].reverse()

    c = RequestContext(request, extra_context)
    return HttpResponse(t.render(c))


def forms_add_form_entry(request, slug):
    """
    Display a built form and handle submission.
    """
    try:
        form = FormsForm.objects.get(slug=slug)
        check = get_acl_for_model(form)
        if not check.creator_formsform(form, request.user):
            return HttpResponseForbidden()
    except:
        return HttpResponseForbidden()

    rget = {}
    rget['where'] = request.GET.get('where', '')
    rget['url_redirect_to'] = request.GET.get('form_next', '')
    args = (form, request.POST or None, request.FILES or None)
    form_for_form = FormForForm(*args, rget=rget)
    if request.method == "POST":
        if form_for_form.is_valid():
            entry = form_for_form.save(request=request)
            if rget['url_redirect_to']:
                return HttpResponseRedirect(rget['url_redirect_to'])
            elif check.viewer_formsform(form, request.user):
                return HttpResponseRedirect(reverse('form_browse_entries_view',
                    args=[form.slug]) + '?where=' + request.POST.get('where', ''))
            else:
                return HttpResponseRedirect(reverse('form_sent',
                    args=[entry.pk]))

    if form.template:
        t = Template(form.template)
    else:
        try:
            t = loader.get_template('forms_new_%s.html' % form.slug)
        except:
            t = loader.get_template("forms/form_details.html")

    extra_context = {"form": form, "form_for_form": form_for_form}
    extra_context['entry'] = None
    extra_context['where'] = rget['where']
    extra_context['parents'] = []
    if rget['where']:
        try:
            d = rget['where'].split(':')
            bte = d[0].split('.')
            pk = d[1]
            while True:
                e = FormsFormEntry.objects.select_related().get(
                    pk=pk, form__slug=bte[0])
                c, r = forms_get_entry(e)
                extra_context['parents'].append({'row': r[bte[1]], 'entry': e})
                if not e.form.bind_to_entry:
                    break
                bte = e.form.bind_to_entry.split('.')
                pk = e.entry_id
        except Exception as e:
            extra_context['parents'] = []
    extra_context['parents'].reverse()

    if not check.viewer_formsform(form, request.user) and not isUserManager(request, form.workspace.slug):
        extra_context['can_browse'] = False
    else:
        extra_context['can_browse'] = True

    ctx = RequestContext(request, extra_context)
    return HttpResponse(t.render(ctx))


def forms_add_formset_entry(request, slug):
    """
    Display a built form and handle submission.
    """
    try:
        form = FormsForm.objects.get(slug=slug)
        check = get_acl_for_model(form)
        if not check.creator_formsform(form, request.user):
            return HttpResponseForbidden()
    except:
        return HttpResponseForbidden()

    rget = {}
    rget['where'] = request.GET.get('where', '')
    ff = forms_factory(form, rget=rget)
    fs = formset_factory(ff, extra=1)
    args = (request.POST or None, request.FILES or None)
    form_set = fs(*args)
    if request.method == "POST":
        if form_set.is_valid():
            for f in form_set.forms:
                if f.cleaned_data and f.is_valid():
                    f.save(request=request)
            if check.viewer_formsform(form, request.user):
                return HttpResponseRedirect(reverse('form_browse_entries_view',
                    args=[form.slug]) + '?where=' + request.POST.get('where', ''))
            else:
                return HttpResponseRedirect('/')

    extra_context = {"form": form, "formset": form_set}
    extra_context['parents'] = []
    if rget['where']:
        try:
            d = rget['where'].split(':')
            bte = d[0].split('.')
            pk = d[1]
            while True:
                e = FormsFormEntry.objects.select_related().get(
                    pk=pk, form__slug=bte[0])
                c, r = forms_get_entry(e)
                extra_context['parents'].append({'row': r[bte[1]], 'entry': e})
                if not e.form.bind_to_entry:
                    break
                bte = e.form.bind_to_entry.split('.')
                pk = e.entry_id
        except Exception as e:
            extra_context['parents'] = []
    extra_context['parents'].reverse()

    t = loader.get_template("forms/formset_details.html")
    c = RequestContext(request, extra_context)
    return HttpResponse(t.render(c))


def form_sent(request, entry, template="forms/form_sent.html"):
    """
    Show the response message.
    """
    try:
        entry = FormsFormEntry.objects.select_related(depth=1).get(pk=entry)
        form = entry.form
        check = get_acl_for_model(form)
        if not check.creator_formsform(form, request.user):
            return HttpResponseForbidden()
    except:
        return HttpResponseForbidden()
    columns, row = forms_get_entry(entry)

    ec = {}
    for field in row['fields']:
        ec[field['slug']] = {'label': field['label'], 'value': field['value']}

    try:
        ffa = FormsFormAction.objects.get(form=form)
        c = RequestContext(request, ec)
        if isinstance(ffa.content_object, FormsFormActionUrl):
            t = Template(ffa.content_object.url)
            return HttpResponseRedirect(t.render(c))
        else:
            t = Template(ffa.content_object.message)
    except FormsFormAction.DoesNotExist:
        return HttpResponseRedirect('/')

    context = {'body': t.render(c), 'form': form}
    return render_to_response(template, context, RequestContext(request))


def form_process_import_fields(request, form):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()
        import csv

        tempfile = request.POST.get('tempfile', None)
        if tempfile:
            separator = request.POST.get('separator', ';')
            encoding = request.POST.get('encoding', 'UTF-8')

            if form.bind_to_account:
                from django.contrib.auth.models import User
                users = {}
                for u in User.objects.all():
                    users[u.username] = u.pk
            else:
                users = None

            csv_file = open(tempfile, 'rb')
            csv_reader = csv.reader(csv_file, delimiter=smart_str(separator))
            rows = 0
            fields_columns = {}
            lists = {}
            col_lists = {}
            col_targets = {}
            form_entries = []
            form_bind_entries = {}
            col_bind_account = None
            constaint_set = set()
            bconstraint = 0
            for row in csv_reader:
                i = 0
                if rows == 0:
                    for col in row:
                        col = smart_unicode(col, encoding)
                        col_slug = slugify(col).replace('-', '_')
                        ft = request.POST.get(
                            'field_type_%s' % i, str(fields.TEXT))
                        uq = request.POST.get('field_unique_%s' % i, 0)
                        bconstraint += int(uq)
                        fl = None
                        col_lists[i] = 0
                        if ft == 'id_zorna_account':  # ignore
                            col_bind_account = i
                            i = i + 1
                            continue
                        if ft == '0':  # ignore
                            i = i + 1
                            continue
                        elif ft == str(fields.SELECT):  # list
                            fl = FormsList.objects.create(
                                name=col, workspace=fw)
                            lists[fl.pk] = []
                            col_lists[i] = fl.pk
                            fl = FormsFormField.objects.create(
                                form=form, label=col, slug=col_slug, required=1, field_type=fields.SELECT, list=fl)
                        elif ft[0:2] == 'f-':
                            try:
                                fl = form.fields.get(pk=int(ft[2:]))
                                if fl.reference:
                                    r = fl.reference.split('.')
                                    fl.form_target = FormsForm.objects.get(
                                        slug=r[0])
                                    fl.slug_target = r[1]
                                    fl.target_entries = {}
                                elif fl.field_type in fields.LISTS:
                                    flist = FormsList.objects.create(
                                        name=col, workspace=fw)
                                    lists[flist.pk] = []
                                    col_lists[i] = flist.pk
                                    fl.list = flist
                                    fl.save()
                            except Exception as e:
                                fl = FormsFormField.objects.create(
                                    form=form, label=col, slug=col_slug, required=1, field_type=fields.TEXT)
                        elif ft[0:3] == 'ff-':  # bind_entry
                            try:
                                if form.bind_to_entry:
                                    fl = FormsFormField.objects.get(
                                        pk=int(ft[3:]))
                                    r = form.bind_to_entry.split('.')
                                    fl.form_target = FormsForm.objects.get(
                                        slug=r[0])
                                    fl.slug_target = r[1]
                                    fl.target_entries = {}
                                    fl.bind_entry = True
                            except Exception as e:
                                fl = None
                        else:
                            fl = FormsFormField.objects.create(
                                form=form, label=col, slug=col_slug, required=1, field_type=int(ft))
                        if fl:
                            fl.unique_constraint = uq
                            fields_columns[i] = fl
                        i = i + 1
                    for idx, fl in fields_columns.iteritems():
                        try:
                            if fl.form_target:
                                if fl.form_target.pk not in col_targets:
                                    col_targets[fl.form_target.pk] = FormsFieldEntry.objects.forms_get_entries(
                                        fl.form_target)
                                entries = col_targets[fl.form_target.pk][1]
                                for e in entries:
                                    fl.target_entries[e[fl.slug_target][
                                        'value'].lower()] = e['entity'].pk
                        except Exception as e:
                            fl.target_entries = None
                else:  # line > 0
                    # create form entry
                    constraint = ''
                    for col in row:
                        # create field entry
                        col = col.strip()
                        if i in fields_columns:
                            col = smart_unicode(col, encoding)
                            lower_col = col.lower()
                            if fields_columns[i].target_entries and lower_col in fields_columns[i].target_entries:
                                col = fields_columns[
                                    i].target_entries[lower_col]
                                try:
                                    if fields_columns[i].bind_entry:
                                        form_bind_entries[rows - 1] = col
                                except Exception as e:
                                    pass
                            if fields_columns[i].unique_constraint:
                                constraint += col.lower()
                        i = i + 1
                    if not bconstraint:
                        form_entries.append((rows - 1, row))
                    elif constraint not in constaint_set:
                        form_entries.append((rows - 1, row))
                        constaint_set.add(constraint)
                rows = rows + 1

            # prepare to execute bulk insert
            rows_entries = {}
            for i, row in form_entries:
                kwargs = {'form':
                          form, 'modifier': request.user, 'owner': request.user}
                if col_bind_account is not None and row[col_bind_account] in users:
                    kwargs['account_id'] = users[row[col_bind_account]]
                if i in form_bind_entries:
                    kwargs['entry_id'] = form_bind_entries[i]
                entry = FormsFormEntry.objects.create(**kwargs)
                rows_entries[i] = entry

            bulk_values = []
            for k, row in form_entries:
                i = 0
                # entry = FormsFormEntry.objects.create(form=form,
                # modifier=request.user)
                for col in row:
                    col = col.strip()
                    # create field entry
                    if i in fields_columns:
                        try:
                            if fields_columns[i].bind_entry:
                                pass  # dont' create field it's an entry bind to anther form entry
                        except Exception as e:
                            col = smart_unicode(col, encoding)
                            if fields_columns[i].target_entries:
                                lower_col = col.lower()
                                if lower_col in fields_columns[i].target_entries:
                                    col = fields_columns[
                                        i].target_entries[lower_col]
                                else:
                                    col = None
                            elif not col and fields_columns[i].default_value:
                                col = fields_columns[i].default_value
                            # entry.fields.create(field=fields_columns[i],
                            # value=col)
                            if not col is None:
                                bulk_values.extend([fields_columns[
                                                   i].pk, rows_entries[k].pk, col])
                                if col_lists[i] and col not in lists[col_lists[i]]:  # list
                                    lists[col_lists[i]].append(col)
                    i = i + 1
            if bulk_values:
                from django.db import connection, transaction
                qn = connection.ops.quote_name
                cursor = connection.cursor()
                fe_fields = ['field_id', 'form_entry_id', 'value']
                flds = ', '.join([qn(f) for f in fe_fields])
                arg_string = ', '.join([u'(' + ', '.join(['%s'] * len(
                    fe_fields)) + ')'] * (len(bulk_values) / len(fe_fields)))
                sql = "INSERT INTO %s (%s) VALUES %s" % (
                    FormsFieldEntry._meta.db_table, flds, arg_string,)
                cursor.execute(sql, bulk_values)
                transaction.commit_unless_managed()
                cursor.close()

                for list, values in lists.iteritems():
                    for v in values:
                        FormsListEntry.objects.create(value=v, list_id=list)
            csv_file.close()
            os.unlink(tempfile)
        return forms_form(request, form.pk, extra={'load_navigation': True})
    else:
        return HttpResponseForbidden()


def form_map_import_fields(request, form, tempfile, separator, encoding='utf-8'):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        import csv
        extra_context = {}
        csv_reader = csv.reader(open(
            tempfile, 'rb'), delimiter=smart_str(separator))
        for headers in csv_reader:
            break
        i = 0
        extra_context['csv_header'] = []
        for col in headers:
            extra_context['csv_header'].append({
                                               'id': i, 'label': smart_unicode(col, encoding)})
            i = i + 1
        extra_context['tempfile'] = tempfile
        extra_context['separator'] = separator
        extra_context['encoding'] = encoding
        extra_context['type_choices'] = [
            {'id': fields.TEXT, 'label': _(
             "Single line text")},
            {'id': fields.TEXTAREA, 'label': _(
             "Multi line text")},
            {'id': fields.EMAIL, 'label': _(
             "Email")},
            {'id': fields.DATE, 'label': _(
             "Date")},
            {'id': fields.DATE_TIME, 'label': _(
             "Date/time")},
            {'id': fields.SELECT, 'label': _(
             "List")},
        ]
        extra_context['field_choices'] = []

        form_fields = form.fields.all()
        for f in form_fields:
            if f.field_type == fields.ZORNA_USER_SINGLETON:
                extra_context['field_choices'].append({
                                                      'id': 'id_zorna_account', 'label': _(u'Nickname')})
            elif f.field_type == fields.FORM_ENTRY:
                bte = form.bind_to_entry.split('.')
                ff = FormsFormField.objects.get(slug=bte[1], form__slug=bte[0])
                extra_context['field_choices'].append({
                                                      'id': 'ff-%s' % ff.pk, 'label': ff.label})
            else:
                extra_context['field_choices'].append({
                                                      'id': 'f-%s' % f.pk, 'label': f.label})

        extra_context['current_form'] = form
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['workspace'] = fw
        return render_to_response('forms/import_process_file_csv.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def form_import_fields(request, form):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()
        form_csv = FormsFormImportCsv(
            request.POST or None, request.FILES or None)
        if request.method == 'POST':
            if request.POST.has_key('tempfile'):
                return form_process_import_fields(request, form.pk)
            elif form_csv.is_valid() and request.FILES.has_key('file'):
                import tempfile
                f = request.FILES['file']
                temp = tempfile.NamedTemporaryFile(suffix='.csv', delete=False)
                for chunk in f.chunks():
                    temp.write(chunk)
                temp.close()
                delimiter = request.POST.get('other', None)
                encoding = request.POST.get('encoding', 'UTF-8')
                if not delimiter:
                    delimiter = request.POST.get('separator', ';')
                    delimiter = '\t' if delimiter == 't' else delimiter
                return form_map_import_fields(request, form.pk, temp.name, delimiter, encoding)

        extra_context = {}
        extra_context['current_form'] = form
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['workspace'] = fw
        extra_context['form'] = form_csv
        return render_to_response('forms/import_file_csv.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_form_order_fields(request, form):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        fields = request.GET.getlist('field-table-dnd[]')
        if len(fields):
            sort_order = 1
            try:
                for f in fields:
                    if f:
                        c = FormsFormField.objects.get(pk=f)
                        c.sort_order = sort_order
                        c.save()
                        sort_order += 1
            except:
                pass
            return forms_form(request, form.pk, extra={'load_navigation': True})

        extra_context = {}
        extra_context['current_form'] = form
        extra_context['fields'] = form.fields.all()
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['workspace'] = fw
        return render_to_response('forms/order_fields.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_table_order_fields(request, form):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        fields = [int(f)
                  for f in request.GET.getlist('field-table-dnd[]') if f]
        fdisp = [int(f) for f in request.GET.getlist('fdisp[]') if f]
        fsort = request.GET.get('fsort', None)
        form_fields = {}
        extra_context = {}
        extra_context['fields'] = form.fields.all().order_by('sort_order_list')
        for f in extra_context['fields']:
            form_fields[f.pk] = f

        if len(fields):
            sort_order = 1
            try:
                for f in fields:
                    if f:
                        form_fields[f].sort_order_list = sort_order
                        if fsort and f == int(fsort):
                            form_fields[f].for_sort = True
                        else:
                            form_fields[f].for_sort = False
                        if f in fdisp:
                            form_fields[f].visible_in_list = True
                        else:
                            form_fields[f].visible_in_list = False
                        form_fields[f].save()
                        sort_order += 1
            except Exception as e:
                pass
            return forms_form(request, form.pk, extra={'load_navigation': True})

        extra_context['current_form'] = form
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['workspace'] = fw
        return render_to_response('forms/table_fields.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_edit_form_template(request, form):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        if request.method == 'POST':
            tpl_form = FormsFormTemplateForm(request.POST)
            if tpl_form.is_valid():
                form.template = tpl_form.cleaned_data['template']
                form.save()
                return forms_form(request, form.pk)
            else:
                tpl_form = FormsFormTemplateForm(request.POST)
        else:
            tpl_form = FormsFormTemplateForm(
                initial={'template': form.template})

        extra_context = {}
        extra_context['form'] = tpl_form
        extra_context['current_form'] = form
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['workspace'] = fw
        return render_to_response('forms/edit_form_template.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_edit_form_email_settings(request, form):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        if request.method == 'POST':
            tpl_form = FormsFormFormEmail(request.POST)
            if tpl_form.is_valid():
                form.send_email = tpl_form.cleaned_data['send_email']
                form.email_from = tpl_form.cleaned_data['email_from']
                form.email_copies = tpl_form.cleaned_data['email_copies']
                form.email_subject = tpl_form.cleaned_data['email_subject']
                form.email_message = tpl_form.cleaned_data['email_message']
                form.save()
                return forms_form(request, form.pk)
            else:
                tpl_form = FormsFormFormEmail(request.POST)
        else:
            initial_data = {'send_email': form.send_email,
                            'email_from': form.email_from,
                            'email_copies': form.email_copies,
                            'email_subject': form.email_subject,
                            'email_message': form.email_message,
                            }
            tpl_form = FormsFormFormEmail(initial=initial_data)

        extra_context = {}
        extra_context['form'] = tpl_form
        extra_context['current_form'] = form
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['workspace'] = fw
        return render_to_response('forms/edit_form_email.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_form_export_entries(request, form):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        export_form = FormsExportForm(form, request, request.POST or None)
        submitted = export_form.is_valid()
        if submitted:
            if request.POST.get("export"):
                delimiter = request.POST.get('oseparator', None)
                if not delimiter:
                    delimiter = request.POST.get('separator', ';')
                    delimiter = '\t' if delimiter == 't' else delimiter

                response = HttpResponse(mimetype="text/csv")
                fname = "%s-%s.csv" % (
                    form.slug, slugify(datetime.now().ctime()))
                response[
                    "Content-Disposition"] = "attachment; filename=%s" % fname
                csv = writer(response, delimiter=';')
                csv.writerow(export_form.get_columns())
                for row in export_form.get_entries():
                    result = []
                    for r in row:
                        if r['type'] in ['checkbox_multiple', 'select_multiple', 'radio_multiple']:
                            result.append(smart_str(','.join(r['value'])))
                        else:
                            result.append(smart_str(r['value']))
                    csv.writerow(result)
                return response
            else:
                template = "forms/view_entries.html"
        else:
            template = "forms/export_form.html"

        extra_context = {
            "title": _("Export Entries"), "export_form": export_form,
            "submitted": submitted}
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['current_form'] = form
        return render_to_response(template, extra_context, RequestContext(request))


def file_view(request, file, size=None):
    """
    Output the file for the requested field entry.
    """
    try:
        field_entry = FormsFieldEntry.objects.select_related(
            depth=1).get(pk=file)
        form = field_entry.form_entry.form
        check = get_acl_for_model(form)
        if not check.viewer_formsform(form, request.user) and not isUserManager(request, form.workspace.slug):
            return HttpResponseForbidden()
    except:
        return HttpResponseForbidden()

    fs = FileSystemStorage(location=get_upload_forms_attachments())
    path = join(fs.location, field_entry.value)
    if size:
        filehead, filetail = os.path.split(path)
        basename, extension = os.path.splitext(filetail)
        miniature = basename + '_' + size + extension
        miniature = os.path.join(filehead, miniature)
        if not os.path.exists(miniature):
            try:
                Image.open(path).verify()
                if size:
                    miniature = resize_image(path, size)
                    split = path.rsplit('/', 1)
                    path = '%s/%s' % (split[0], miniature)
            except:
                pass
        else:
            path = miniature
    response = HttpResponse(mimetype=guess_type(path)[0])
    f = open(path, "r+b")
    inline = request.GET.get('inline', None)
    attachment = 'inline' if inline else 'attachment'
    response["Content-Disposition"] = "%s; filename=\"%s\"" % (attachment, smart_str(path.rsplit('/', 1)[1]))
    response.write(f.read())
    f.close()
    return response


def get_entries(entries, parent=None):
    ret = []
    for entry in entries:
        if parent is None:
            if 'entry_bind' not in entry['fields'][0]:
                ret.append(entry)
            elif entry['fields'][0]['entry_bind'] not in ret:
                ret.append(entry['fields'][0]['entry_bind'])
        else:
            for i, f in enumerate(entry['fields']):
                if 'entry_bind' in f:
                    if f['entry_bind']['id'] == parent:
                        if 'entry_bind' in entry['fields'][i + 1]:
                            if entry['fields'][i + 1]['entry_bind'] not in ret:
                                ret.append(entry['fields'][
                                           i + 1]['entry_bind'])
                                break
                        else:
                            ret.append(entry)
                            break
                else:
                    break
    return ret

def form_browse_entries_view_by_id(request, form_id):
    form = FormsForm.objects.get(pk= form_id)
    return form_browse_entries_view(request, form.slug)


def form_browse_entries_view(request, slug, template=None):
    try:
        form = FormsForm.objects.select_related(depth=1).get(slug=slug)
        check = get_acl_for_model(form)
        if not check.viewer_formsform(form, request.user) and not isUserManager(request, form.workspace.slug):
            return HttpResponseForbidden()
    except:
        return HttpResponseForbidden()

    ec = forms_form_browse_entries(request, slug)
    ec['zorna_title_page'] = form.name
    if not ec:
        return HttpResponseForbidden()
    if template:
        t = loader.get_template(template)
    else:
        try:
            t = loader.get_template('forms_list_entries_%s.html' % slug)
        except TemplateDoesNotExist:
            t = loader.get_template("forms/browse_entries.html")
    c = RequestContext(request, ec)
    return HttpResponse(t.render(c))

def form_browse_entries_raw_view(request, slug):
    return form_browse_entries_view(request, slug, "forms/browse_entries.html")

def forms_form_view_entry(request, entry):

    try:
        entry = FormsFormEntry.objects.select_related(depth=1).get(pk=entry)
        form = entry.form
        check = get_acl_for_model(form)
        if not check.viewer_formsform(form, request.user) and not isUserManager(request, form.workspace.slug):
            return HttpResponseForbidden()
    except:
        return HttpResponseForbidden()
    columns, row = forms_get_entry(entry)

    extra_context = {}
    extra_context['zorna_title_page'] = _(u'Forms')
    extra_context['form'] = form
    extra_context['columns'] = columns
    extra_context['row'] = row
    extra_context['parents'] = []
    if row['entity'].account_id:
        extra_context['user_avatar'] = row[
            'entity'].get_user_avatar(row['entity'].account_id)
    else:
        extra_context['user_avatar'] = None

    if entry.entry:
        try:
            bte = form.bind_to_entry.split('.')
            while entry.entry:
                e = FormsFormEntry.objects.select_related().get(
                    pk=entry.entry.pk, form__slug=bte[0])
                c, r = forms_get_entry(e)
                extra_context['parents'].append({'row': r[bte[1]], 'entry': e})
                if not e.form.bind_to_entry:
                    break
                bte = e.form.bind_to_entry.split('.')
                entry = e
        except Exception as e:
            extra_context['parents'] = []
    extra_context['parents'].reverse()
    try:
        t = loader.get_template('forms_view_entry_%s.html' % form.slug)
    except Exception as e:
        t = loader.get_template("forms/view_entry.html")
    c = RequestContext(request, extra_context)
    return HttpResponse(t.render(c))


def browse_references(request, workspace_slug):
    fw = isUserManager(request, workspace_slug)
    if fw:
        forms = FormsForm.objects.filter()
        extra_context = {'forms':
                         forms, 'target': request.GET.get('target', '')}
        context = RequestContext(request)
        return render_to_response('forms/reference.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def browse_fields(request, form_pk):
    try:
        form = FormsForm.objects.get(pk=form_pk)
        fw = isUserManager(request, form.workspace.slug)
        if fw is False:
            return HttpResponseForbidden()
    except:
        return HttpResponseForbidden()

    if form:
        extra_context = {'form': form, 'target': request.GET.get('target', '')}
        context = RequestContext(request)
        return render_to_response('forms/reference_form_fields.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def form_form_action_home(request, form_pk):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form_pk)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        try:
            ffa = FormsFormAction.objects.get(form=form)
            if isinstance(ffa.content_object, FormsFormActionUrl):
                selected = 'url'
            else:
                selected = 'message'
        except FormsFormAction.DoesNotExist:
            selected = None

        extra_context = {}
        extra_context['current_form'] = form
        extra_context['action_selected'] = selected
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['workspace'] = fw
        return render_to_response('forms/form_action_home.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_action_edit_message(request, form_pk):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form_pk)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        try:
            ffam = FormsFormActionMessage.objects.get(form=form)
        except FormsFormActionMessage.DoesNotExist:
            ffam = None

        if request.method == 'POST':
            tpl_form = FormsFormActionMessageForm(request.POST, instance=ffam, request=request)
            if tpl_form.is_valid():
                ffam = tpl_form.save(commit=False)
                ffam.form = form
                ffam.save()
                try:
                    ffa = FormsFormAction.objects.get(form=form)
                    ffa.content_object = ffam
                    ffa.save()
                except FormsFormAction.DoesNotExist:
                    FormsFormAction.objects.create(
                        form=form, content_object=ffam)
                return form_form_action_home(request, form.pk)
            else:
                tpl_form = FormsFormActionMessageForm(
                    request.POST, instance=ffam, request=request)
        else:
            tpl_form = FormsFormActionMessageForm(instance=ffam, request=request)

        extra_context = {}
        extra_context['form'] = tpl_form
        extra_context['current_form'] = form
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['workspace'] = fw
        return render_to_response('forms/edit_form_action_message.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_action_edit_url(request, form_pk):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form_pk)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        try:
            ffam = FormsFormActionUrl.objects.get(form=form)
        except FormsFormActionUrl.DoesNotExist:
            ffam = None

        if request.method == 'POST':
            tpl_form = FormsFormActionUrlForm(request.POST, instance=ffam)
            if tpl_form.is_valid():
                ffam = tpl_form.save(commit=False)
                ffam.form = form
                ffam.save()
                try:
                    ffa = FormsFormAction.objects.get(form=form)
                    ffa.content_object = ffam
                    ffa.save()
                except FormsFormAction.DoesNotExist:
                    FormsFormAction.objects.create(
                        form=form, content_object=ffam)
                return form_form_action_home(request, form.pk)
            else:
                tpl_form = FormsFormActionUrlForm(request.POST, instance=ffam)
        else:
            tpl_form = FormsFormActionUrlForm(instance=ffam)

        extra_context = {}
        extra_context['form'] = tpl_form
        extra_context['current_form'] = form
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['workspace'] = fw
        return render_to_response('forms/edit_form_action_url.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()


def forms_form_panels(request, form_pk):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form_pk)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        fields = request.GET.getlist('field-table-dnd[]')
        if len(fields):
            sort_order = 1
            try:
                for f in fields:
                    if f:
                        c = FormsFormPanel.objects.get(pk=f)
                        c.sort_order = sort_order
                        c.save()
                        sort_order += 1
            except:
                pass
            return forms_form(request, form.pk, extra={})

        extra_context = {}
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['current_form'] = form
        extra_context['panels'] = form.formsformpanel_set.all()
        return render_to_response('forms/form_panels.html', extra_context, RequestContext(request))


def forms_form_panel_add(request, form_pk):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form_pk)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        extra_context = {}
        if request.method == 'POST':
            ff = FormsFormPanelForm(request.POST, request=request)
            if ff.is_valid():
                fmax = FormsFormPanel.objects.filter(
                    form=form).aggregate(max_sort_order=Max('sort_order'))
                max_order = fmax['max_sort_order'] if fmax[
                    'max_sort_order'] else 0
                ff = ff.save(commit=False)
                ff.sort_order = max_order
                ff.form = form
                ff.save()
                return HttpResponseRedirect(reverse('forms_form_panels', args=[form_pk]))
        else:
            ff = FormsFormPanelForm(request=request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['current_form'] = form
        extra_context['form'] = ff
        extra_context['bdelete'] = False
        return render_to_response('forms/edit_form_panel.html', extra_context, RequestContext(request))


def forms_form_panel_edit(request, panel_pk):
    if request.user.is_authenticated():
        try:
            panel = FormsFormPanel.objects.select_related(
                depth=1).get(pk=panel_pk)
            form = panel.form
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        extra_context = {}
        if request.method == 'POST':
            ff = FormsFormPanelForm(request.POST, instance=panel, request=request)
            if request.POST.has_key('bdelete'):
                panel.delete()
                return HttpResponseRedirect(reverse('forms_form_panels', args=[form.pk]))
            elif ff.is_valid():
                ff.save()
                return HttpResponseRedirect(reverse('forms_form_panels', args=[form.pk]))
        else:
            ff = FormsFormPanelForm(instance=panel, request=request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['current_form'] = form
        extra_context['form'] = ff
        extra_context['bdelete'] = True
        return render_to_response('forms/edit_form_panel.html', extra_context, RequestContext(request))

def forms_form_duplicate(request, form_pk):
    if request.user.is_authenticated():
        try:
            form = FormsForm.objects.select_related(depth=1).get(pk=form_pk)
            fw = isUserManager(request, form.workspace.slug)
            if fw is False:
                return HttpResponseForbidden()
        except:
            return HttpResponseForbidden()

        tpl_form = FormsFormDuplicate(request.POST if request.method == 'POST' else None)
        tpl_form.fields['workspace'].queryset = get_user_workspaces(request)
        if request.method == 'POST' and tpl_form.is_valid():
            try:
                print request.POST.get('slug','')
                FormsForm.objects.get(slug=request.POST.get('slug',''))
            except FormsForm.DoesNotExist:
                original_form = FormsForm.objects.get(pk=form_pk)
                original_form.pk = None
                original_form.workspace = FormsWorkspace.objects.get(
                                pk=request.POST.get('workspace', ''))
                original_form.bind_to_entry = ''
                original_form.display = ''
                original_form.slug = request.POST.get('slug','')
                original_form.name = request.POST.get('name','')
                original_form.modifier = original_form.owner = request.user
                original_form.save()
                form_action_set = form.formsformaction_set.all()
                if form_action_set:
                    form_action = form_action_set[0]
                    form_action.content_object.pk=None
                    form_action.content_object.form=original_form
                    form_action.content_object.save()
                    FormsFormAction.objects.create(
                        form=original_form, content_object=form_action.content_object)
                panels = {}
                for panel in form.formsformpanel_set.all():
                    panel_id=panel.pk
                    panel.pk = None
                    panel.form = original_form
                    panel.save()
                    panels[panel_id] = panel

                for field in form.fields.all():
                    field.pk = None
                    field.form = original_form
                    if field.panel and field.panel.pk in panels:
                        field.panel = panels[field.panel.pk]
                    field.save()
                return forms_form(request, original_form.pk, extra={'load_navigation': True})
            else:
                tpl_form.errors['__all__'] = tpl_form.error_class([_(u"A form with this slug already exist")])
                pass

        extra_context = {}
        extra_context['form'] = tpl_form
        extra_context['current_form'] = form
        context = RequestContext(request)
        extra_context['zorna_title_page'] = _(u'Forms')
        extra_context['workspace'] = fw
        return render_to_response('forms/edit_form_duplicate.html', extra_context, context_instance=context)
    else:
        return HttpResponseForbidden()
