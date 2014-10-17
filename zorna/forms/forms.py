import os
import re
from os.path import join
import time
import datetime
from uuid import uuid4
from django.forms import ModelForm
from django.utils.translation import ugettext_lazy as _
from django import forms
from django.core.files.storage import FileSystemStorage
from django.core.urlresolvers import reverse
from django.utils.encoding import smart_str
from django.template.defaultfilters import slugify
from django.contrib.auth.models import User
from django.conf import settings
from django.core.mail import EmailMessage
from django.template import RequestContext, Template, loader
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from ckeditor.widgets import CKEditorWidget

from zorna.utilit import get_upload_forms_attachments
from zorna.acl.models import get_acl_for_model
from zorna.forms import form_entry_post_save
from zorna.forms import fields as fc
from zorna.forms.models import FormsList, FormsForm, FormsFormField, FormsFormEntry, FormsFieldEntry, FormsWorkspace, \
    forms_format_entries, FormsFormActionMessage, FormsFormActionUrl, FormsFormPanel
from zorna.communities.api import ZornaCommunityAddons, get_messages_extra_by_content_type
from zorna.site.models import SiteOptions

'''
Largement inspired by the code stephenmcd / django-forms-builder
https://github.com/stephenmcd/django-forms-builder
'''


class FormsWorkspaceForm(ModelForm):

    class Meta:
        model = FormsWorkspace
        exclude = ('sort_order',)

    def clean_slug(self):
        if 'slug' in self.cleaned_data and 'name' in self.cleaned_data:
            if self.cleaned_data['slug'] != '':
                pass
            else:
                self.cleaned_data['slug'] = self.cleaned_data['name']
            self.cleaned_data['slug'] = slugify(self.cleaned_data['slug'])
            return self.cleaned_data['slug']
        else:
            raise forms.ValidationError(_(
                u'You must provide a slug or a workspace name'))


class FormsListForm(ModelForm):
    name = forms.CharField(label=_(
        u'Name'), widget=forms.TextInput(attrs={'size': '80'}))
    description = forms.CharField(label=_(u'Description'), widget=forms.TextInput(
        attrs={'size': '80'}), required=False)

    class Meta:
        model = FormsList


class FormsListEntryForm(forms.Form):
    value = forms.CharField(label=_(
        u'Value'), widget=forms.TextInput(attrs={'size': '80'}))


class FormsFormForm(ModelForm):
    name = forms.CharField(label=_(
        u'Name'), widget=forms.TextInput(attrs={'size': 80}))
    slug = forms.CharField(widget=forms.TextInput(attrs={'size': 80}))
    # description = forms.CharField(widget=forms.Textarea(attrs={'rows':'3',
    # 'cols':'80'}), required=False)
    button_text = forms.CharField(label=_(u'Button text'), initial=_(
        "Submit"), widget=forms.TextInput(attrs={'size': 80}))
    bind_to_entry = forms.CharField(label=_(u'Bind to entry'), widget=forms.TextInput(attrs={
                                    'size': 80}), help_text=_("If filled, each record will be linked to target form entry"), required=False)
    description = forms.CharField(_(u'Description'), widget=forms.Textarea(
        attrs={'rows': '5', 'cols': '80'}))

    # bind_display =
    # forms.CharField(widget=forms.TextInput(attrs={'size':80}),
    # required=False)

    class Meta:
        model = FormsForm

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request')
        super(FormsFormForm, self).__init__(*args, **kwargs)
        self.fields['description'] = forms.CharField(label=_(u'body'), widget=CKEditorWidget(config_name=SiteOptions.objects.get_ckeditor_config(request)))


class FormsFormFormEmail(forms.Form):
    send_email = forms.BooleanField(label=_(
        "Send email"), required=False, help_text=_("If checked, an email will be sent"))
    email_from = forms.CharField(label=_(u'From address'), widget=forms.TextInput(attrs={
                                 'size': 80}), required=False, help_text=_("The address the email will be sent from"))
    email_copies = forms.CharField(label=_(u'Send copies to'), widget=forms.TextInput(attrs={
                                   'size': 80}), required=False, help_text=_("One or more email addresses, separated by commas"))
    email_subject = forms.CharField(label=_(
        u'Subject'), widget=forms.TextInput(attrs={'size': 80}), required=False)
    email_message = forms.CharField(label=_(u'Message'), widget=forms.Textarea(
        attrs={'rows': '3', 'cols': '80'}), required=False)


class FormsFormActionMessageForm(ModelForm):
    message = forms.CharField(_(u'Message'), widget=forms.Textarea(
        attrs={'rows': '5', 'cols': '80'}))

    class Meta:
        model = FormsFormActionMessage

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request')
        super(FormsFormActionMessageForm, self).__init__(*args, **kwargs)
        self.fields['message'] = forms.CharField(label=_(u'body'),
            widget=CKEditorWidget(config_name=SiteOptions.objects.get_ckeditor_config(request)))


class FormsFormActionUrlForm(ModelForm):
    url = forms.CharField(widget=forms.TextInput(attrs={'size': 80}))

    class Meta:
        model = FormsFormActionUrl


class FormsFormFieldForm(ModelForm):
    label = forms.CharField(widget=forms.TextInput(attrs={'size': 80}))
    slug = forms.CharField(widget=forms.TextInput(attrs={'size': 80}))
    help_text = forms.CharField(widget=forms.TextInput(
        attrs={'size': 80}), required=False)
    reference = forms.CharField(widget=forms.TextInput(
        attrs={'size': 80}), required=False)
    reference_display = forms.CharField(widget=forms.TextInput(
        attrs={'size': 80}), required=False)

    class Meta:
        model = FormsFormField


class FormsFormFieldFormBase(forms.Form):
    label = forms.CharField(widget=forms.TextInput(attrs={'size': 80}))
    help_text = forms.CharField(widget=forms.TextInput(
        attrs={'size': 80}), required=False)
    panel = forms.ChoiceField(label=_("Panel"), required=False)


class FormsFormTemplateForm(forms.Form):
    template = forms.CharField(widget=forms.Textarea(
        attrs={'rows': '20', 'cols': '80'}), required=False)


class FormsFormPanelForm(ModelForm):
    name = forms.CharField(widget=forms.TextInput(
        attrs={'size': 80}), help_text=_("Control name"))
    label = forms.CharField(widget=forms.TextInput(attrs={
                            'size': 80}), help_text=_("Panel title"), required=False)
    width = forms.CharField(widget=forms.TextInput(attrs={
                            'size': 30}), help_text=_("Width including units (px, %, ...)"), required=False)
    height = forms.CharField(widget=forms.TextInput(attrs={
                             'size': 30}), help_text=_("Height including units (px, %, ...)"), required=False)
    margin = forms.CharField(widget=forms.TextInput(attrs={
                             'size': 30}), help_text=_("Margin including units (px, %, ...)"), required=False)
    css_class = forms.CharField(widget=forms.TextInput(attrs={
                                'size': 80}), help_text=_("Css classes"), required=False)
    panel_header = forms.CharField(_(
        u'Panel header'), widget=CKEditorWidget(), required=False)
    panel_footer = forms.CharField(_(
        u'Panel footer'), widget=CKEditorWidget(), required=False)

    class Meta:
        model = FormsFormPanel

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request')
        ckeditor_config_name = SiteOptions.objects.get_ckeditor_config(request)
        super(FormsFormPanelForm, self).__init__(*args, **kwargs)
        self.fields['panel_header'] = forms.CharField(label=_(u'body'), required=False,
            widget=CKEditorWidget(config_name=ckeditor_config_name))
        self.fields['panel_footer'] = forms.CharField(label=_(u'body'), required=False,
            widget=CKEditorWidget(config_name=ckeditor_config_name))


class FormsFormDuplicate(forms.Form):
    name = forms.CharField(label=_(
        u'Name'), widget=forms.TextInput(attrs={'size': 80}))
    slug = forms.CharField(widget=forms.TextInput(attrs={'size': 80}))
    workspace = forms.ModelChoiceField(queryset=FormsWorkspace.objects.none(), label=_(u'Workspace'), empty_label=None, required=True)



SEPARATOR_CHOICES = (
    (";", _("Semicolon")),
    (",", _("Comma")),
    ("tab", _("Tabulation")))

ENCODING_CHOICES = (
    ("UTF-8", _("UTF-8")),
    ("ISO-8859-1", _("ISO-8859-1")),)


class FormsFormImportCsv(forms.Form):
    file = forms.CharField(label=_(
        u'File'), widget=forms.FileInput(attrs={'size': '80'}))
    separator = forms.ChoiceField(label=_(
        "Separator"), choices=SEPARATOR_CHOICES, required=True)
    other = forms.CharField(widget=forms.TextInput(attrs={
                            'size': 1}), label=_(u'Other'), max_length=1, required=False)
    encoding = forms.ChoiceField(label=_(
        "Encoding"), choices=ENCODING_CHOICES, required=True)


fs = FileSystemStorage(location=get_upload_forms_attachments())


def format_value(value, type):
    if type == fc.ZORNA_USER:
        return User.objects.get(pk=value).get_full_name()
    elif type == fc.DATE_TIME:
        return datetime.datetime(*time.strptime(value, "%Y-%m-%d %H:%M:%S")[0:5])
    elif type == fc.DATE:
        return datetime.datetime(*time.strptime(value, "%Y-%m-%d")[0:5])
    elif type == fc.CHECKBOX_MULTIPLE or type == fc.SELECT_MULTIPLE:
        return value.split(',')
    else:
        return value


class FormForForm(forms.ModelForm):

    class Meta:
        model = FormsFormEntry
        exclude = ("form", "entry_time")

    def __init__(self, form, *args, **kwargs):
        """
        Dynamically add each of the form fields for the given form model
        instance and its related field model instances.

        accept in kwargs:
            - hidden=field1,field2
            or
            - field1=value1 ...

        if there is an instance hidden fields are removed from form
        Otherwise we try to initialize fields with given values
        """
        self.form = form
        rget = kwargs.pop('rget', {})
        self.form_fields = form.fields.visible()
        super(FormForForm, self).__init__(*args, **kwargs)
        # Attention: see account.views
        if form.bind_to_account:
            if not self.instance.id:
                self.fields['zorna_owner-id'] = forms.CharField(
                    widget=forms.HiddenInput())
                self.fields['zorna_owner'] = forms.CharField(label=_(
                    'User'), widget=forms.TextInput(attrs={'class': 'required zorna_user charfield'}))
            else:
                self.fields['zorna_owner'] = forms.CharField(
                    label=_('User'), initial=self.instance.account.get_full_name(), required=False,
                    widget=forms.TextInput(attrs={'class': 'charfield', 'disabled': 'disabled'}))
            self.fields['zorna_owner'].slug = 'zorna_owner'

        where = rget.get('where', '')
        r = where.split(':')
        if len(r) == 2:
            where_field = r[0]
            where_id = r[1]
        else:
            where_field = None

        url_redirect_to = rget.get('url_redirect_to', '')
        print rget
        if url_redirect_to:
            self.fields['url_redirect_to'] = forms.CharField(
                widget=forms.HiddenInput(), initial=url_redirect_to)

        if form.bind_to_entry:
            try:
                if self.instance.id:
                    initial = self.instance.entry_id
                else:
                    initial = ''
                r = form.bind_to_entry.split('.')
                choices = []
                badd = True
                form.bind_to_entry_slug = '%s_%s' % (r[1], r[0])
                if r[1] == 'zorna_owner':
                    form_target = FormsForm.objects.get(slug=r[0])
                    label = _(u"User")
                    for form_entry in FormsFormEntry.objects.filter(form=form_target):
                        choices.append([
                                       form_entry.pk, form_entry.get_account_full_name()])
                # else not where_field or where_field != form.bind_to_entry:
                else:
                    field = FormsFormField.objects.get(
                        slug=r[1], form__slug=r[0])
                    label = field.label
                    if where_field and where_field == form.bind_to_entry_slug:
                        if not self.instance.id:
                            self.fields[
                                form.bind_to_entry_slug] = forms.CharField(label=label, widget=forms.TextInput(), initial=initial)
                            self.initial[form.bind_to_entry_slug] = initial
                            self.fields[
                                form.bind_to_entry_slug].slug = form.bind_to_entry_slug
                        else:
                            badd = False
                    else:
                        form_target = FormsForm.objects.get(slug=r[0])
                        if form_target.bind_to_entry:
                            rt = form_target.bind_to_entry.split('.')
                            rfield = FormsFormField.objects.get(
                                slug=rt[1], form__slug=rt[0])
                            if rget.has_key('where'):
                                form_target.bind_to_entry_slug = '%s_%s' % (rt[1], rt[
                                                                            0])
                                if where_field and form_target.bind_to_entry_slug == where_field:
                                    rfield_entries = FormsFieldEntry.objects.filter(
                                        field=rfield, form_entry__id=where_id).order_by("value")
                                else:
                                    rfield_entries = FormsFieldEntry.objects.filter(
                                        field=rfield).order_by("value")
                            else:
                                rfield_entries = FormsFieldEntry.objects.filter(
                                    field=rfield).order_by("value")
                            for rfield_entry in rfield_entries:
                                c = []
                                for field_entry in FormsFieldEntry.objects.filter(field=field, form_entry__entry=rfield_entry.form_entry).order_by("value"):
                                    try:
                                        iv = format_value(
                                                field_entry.value, field.field_type)
                                        c.append([field_entry.form_entry_id, iv])
                                    except:
                                        pass
                                try:
                                    choices.append([
                                                   format_value(rfield_entry.value, rfield.field_type), c])
                                except Exception, e:
                                    pass

                        else:
                            for field_entry in FormsFieldEntry.objects.filter(field=field).order_by("value"):
                                try:
                                    iv = format_value(
                                        field_entry.value, field.field_type)
                                    choices.append([field_entry.form_entry_id, iv])
                                except Exception, e:
                                    pass
                if badd:
                    self.fields[form.bind_to_entry_slug] = forms.ChoiceField(
                        label=label, choices=choices, initial=initial)
                    self.initial[form.bind_to_entry_slug] = initial
                    self.fields[
                        form.bind_to_entry_slug].slug = form.bind_to_entry_slug

            except Exception as e:
                pass

        if self.instance.id:
            try:
                fe = FormsFieldEntry.objects.filter(form_entry=self.instance)
                instance_fields = {}
                for e in fe:
                    try:
                        instance_fields[e.field.pk] = format_value(
                            e.value, e.field.field_type)
                    except:
                        instance_fields[e.field.pk] = None
            except FormsFieldEntry.DoesNotExist:
                instance_fields = None

        for field in self.form_fields:
            if field.field_type == fc.ZORNA_USER_SINGLETON:
                self.fields[field.slug].panel = field.panel
                self.fields[field.slug].label = field.label
                self.fields[field.slug].help_text = field.help_text
            elif field.field_type == fc.FORM_ENTRY:
                self.fields[form.bind_to_entry_slug].panel = field.panel
                self.fields[form.bind_to_entry_slug].label = field.label
                self.fields[
                    form.bind_to_entry_slug].help_text = field.help_text
            else:
                field_key = field.slug
                field_class = fc.CLASSES[field.field_type]
                field_widget = fc.WIDGETS.get(field.field_type)
                field_entry = None
                initial = ''
                if self.instance.id:
                    if instance_fields.has_key(field.pk):
                        initial = instance_fields[field.pk]
                elif field.is_a(fc.REFERENCE):
                    continue
                elif field.reference and '.' in field.reference:
                    try:
                        r = field.reference.split('.')
                        if kwargs.has_key('initial') and kwargs['initial'].has_key(r[1]):
                            initial = kwargs['initial'][r[1]]
                    except:
                        pass
                else:
                    initial = field.default_value
                field_args = {"label": field.label, "required": field.required,
                              "help_text": field.help_text}
                arg_names = field_class.__init__.im_func.func_code.co_varnames
                if "choices" in arg_names:
                    if not field.field_type in [fc.CHECKBOX_MULTIPLE, fc.RADIO_MULTIPLE]:
                        ic = '---%s---' % field.label
                    else:
                        ic = ''
                    field_args["choices"] = field.get_choices(include_all=ic)
                if field_widget is not None:
                    field_args["widget"] = field_widget
                self.initial[field_key] = initial
                self.fields[field_key] = field_class(**field_args)
                # Add identifying CSS classes to the field.
                css_class = field_class.__name__.lower()
                if field.required:
                    css_class += " required"
                if field.is_a(fc.ZORNA_USER):
                    fe = FormsFieldEntry.objects.get(field=field,
                                                     form_entry=self.instance) if self.instance.id else None
                    self.fields[field_key + '-id'] = forms.CharField(
                        widget=forms.HiddenInput(), initial=fe.value if fe else '')
                    css_class += " zorna_user"
                self.fields[field_key].widget.attrs["class"] = css_class
                self.fields[field_key].slug = field.slug
                self.fields[field_key].panel = field.panel
                if field.is_a(fc.REFERENCE):
                    self.fields[field_key].widget.attrs['readonly'] = True

                style = ''
                if field.width:
                    style += 'width: %s;' % field.width
                if field.border_width:
                    style += 'border-width: %s;' % field.border_width
                if field.border_style:
                    style += 'border-style: %s;' % field.border_style
                if field.border_color:
                    style += 'border-color: %s;' % field.border_color
                if style:
                    if field.field_type in fc.STYLED_CONTROLS:
                        self.fields[field_key].widget.attrs['style'] = style
                    else:
                        self.fields[field_key].control_style = style

                style = ''
                if field.italic:
                    style += 'font-style: italic;'
                if field.bold:
                    style += 'font-weight: bold;'
                if field.label_color:
                    style += 'color: %s;' % field.label_color
                if field.label_size:
                    style += 'font-size: %s;' % field.label_size
                if style:
                    self.fields[field_key].label_style = style

                style = ''
                if field.margin:
                    style += 'margin: %s;' % field.margin
                if field.padding:
                    style += 'padding: %s;' % field.padding
                if field.bg_color:
                    style += 'background-color: %s;' % field.bg_color
                if style:
                    self.fields[field_key].boundary_style = style

                if field.css_class:
                    self.fields[field_key].css_class = field.css_class

        if rget:
            try:
                if self.instance.id:
                    h = rget.get('hidden', '')
                    # w_fields = {k:'' for k in h.split(',')}
                    w_fields = {}
                    for k in h.split(','):
                        w_fields[k] = ''
                else:
                    h = rget.get('where', '').split(':')
                    w_fields = {h[0]: h[1]}

                # if there is an instance remove fields otherwise re create
                # them as hidden fields with initial value
                for f, v in w_fields.iteritems():
                    try:
                        del(self.fields[f])
                        if not self.instance.id:
                            self.fields[f] = forms.CharField(
                                widget=forms.HiddenInput())
                            self.initial[f] = v
                    except Exception as e:
                        pass
            except:
                pass

    def clean(self):
        """
        Verify that owner field and user field are correctly filled
        """
        for field in self.form_fields:
            field_key = field.slug
            if field.is_a(fc.ZORNA_USER):
                try:
                    User.objects.get(pk=int(
                        self.cleaned_data[field_key + '-id']))
                except:
                    self._errors[field_key] = self.error_class(
                        [_(u'You must provide a registered user')])
                    if field_key in self.cleaned_data:
                        del self.cleaned_data[field_key]

        if self.form.bind_to_account and not self.instance.id and self.fields['zorna_owner-id'].required:
            try:
                u = User.objects.get(pk=int(
                    self.cleaned_data['zorna_owner-id']))
                # Try to see if this record already exist. If so raise an error
                try:
                    FormsFormEntry.objects.get(form=self.form, account=u)
                    self._errors['zorna_owner'] = self.error_class(
                        [_(u'A record with this user already exist')])
                    del self.cleaned_data['zorna_owner']
                except:
                    pass
            except:
                self._errors['zorna_owner'] = self.error_class(
                    [_(u'You must provide a registered user')])
                if 'zorna_owner' in self.cleaned_data:
                    del self.cleaned_data['zorna_owner']

        if self.form.bind_to_entry and self.form.bind_to_entry_slug in self.cleaned_data:
            try:
                FormsFormEntry.objects.get(pk=int(
                    self.cleaned_data[self.form.bind_to_entry_slug]))
            except:
                self._errors[self.form.bind_to_entry_slug] = self.error_class(
                    [_(u'You must provide a valid form entry')])
                del self.cleaned_data[self.form.bind_to_entry_slug]

        return self.cleaned_data

    def save(self, request, **kwargs):
        """
        Create a FormEntry instance and related FieldEntry instances for each
        form field.
        """
        entry = super(FormForForm, self).save(commit=False)
        entry.form = self.form
        if not request.user.is_anonymous():
            entry.modifier = request.user
            entry.owner = request.user
        if self.form.bind_to_account and not self.instance.id:
            try:
                entry.account_id = int(self.cleaned_data['zorna_owner-id'])
            except:
                pass
        if self.form.bind_to_entry:
            try:
                entry.entry_id = int(self.cleaned_data[
                                     self.form.bind_to_entry_slug])
            except:
                pass
        entry.save()
        fields_values = {}
        for field in self.form_fields:
            if field.field_type < fc.ZORNA_USER_SINGLETON:
                bdelete_file = False
                field_key = field.slug
                if not field_key in self.cleaned_data:
                    if field.is_a(fc.REFERENCE):
                        now = datetime.datetime.now()
                        value = now.strftime(field.default_value)
                        value = value.replace('{ID}', str(entry.pk))
                    else:
                        continue
                else:
                    value = self.cleaned_data[field_key]
                if field.is_a(fc.ZORNA_USER):
                    value = self.cleaned_data[field_key + '-id']
                if value and hasattr(value, 'name') and self.fields[field_key].widget.needs_multipart_form:
                    s = os.path.splitext(value.name)
                    filename = u"%s%s" % (slugify(s[0]), s[1])
                    value = fs.save(join(str(self.form.pk), str(
                        entry.pk), str(uuid4()), filename), value)
                    bdelete_file = True
                if isinstance(value, list):
                    value = ",".join([v.strip() for v in value])
                if self.instance.id:
                    try:
                        fe = entry.fields.get(field=field.pk,
                                              form_entry=self.instance)
                        if bdelete_file:
                            fs.delete(fe.value)
                            os.rmdir(os.path.dirname(fs.path(fe.value)))
                        fe.value = value if value else ''
                        fe.save()
                    except FormsFieldEntry.DoesNotExist:
                        if value:
                            entry.fields.create(field_id=field.id, value=value)
                elif value:
                    entry.fields.create(field_id=field.id, value=value)
                try:
                    v = float(value)
                except:
                    pass
                else:
                    fields_values[field.slug] = value

        if self.form.bind_to_entry:
            r = self.form.bind_to_entry.split('.')
            if len(r) == 2:
                try:
                    col, row = FormsFieldEntry.objects.forms_get_entries(r[
                                                                         0], entries=[int(self.cleaned_data[self.form.bind_to_entry_slug])])
                    row = row[0]
                    for v in row['fields']:
                        try:
                            float(v['value'])
                        except:
                            pass
                        else:
                            if v.has_key('form_bind'):
                                fields_values[v['form_bind'] + '.' + v[
                                    'field_bind']] = v['value']
                            else:
                                fields_values[r[0] + '.' + v[
                                    'slug']] = v['value']
                except Exception as e:
                    pass

        for field in self.form.fields.not_visible():
            value = None
            if field.reference and (field.is_a(fc.DECIMAL) or field.is_a(fc.INTEGER)):
                # tre = re.compile(r'([a-z0-9-_]+\.[a-z0-9-_]+)')
                value = field.reference
                for s, v in fields_values.iteritems():
                    value = re.sub(s, str(v), value)
                value = eval(value, {"__builtins__": None}, {
                             "__builtins__": None})
                value = '%.2f' % round(value, 2)
            else:
                value = field.default_value
            if value is not None and self.instance.id:
                try:
                    fe = entry.fields.get(field=field.pk,
                                          form_entry=self.instance)
                    fe.value = value
                    fe.save()
                except FormsFieldEntry.DoesNotExist:
                    entry.fields.create(field_id=field.id, value=value)
            elif value is not None:
                entry.fields.create(field_id=field.id, value=value)

        #if there is no field delete entry
        if not entry.fields.all():
            entry.delete()
            return None

        cols, row = FormsFieldEntry.objects.forms_get_entry(entry)
        form_entry_post_save.send(sender=entry, cols=cols, row=row)
        ec = {}
        for v in row['fields']:
            ec[v['slug']] = {'label': v['label'], 'value': v['value']}
        if self.form.send_email:
            c = RequestContext(request, ec)
            if entry.form.email_message:
                t = Template(entry.form.email_message)
                body = t.render(c)
            else:
                fields = ["%s: %s" % (v.label, self.cleaned_data[k])
                          for (k, v) in self.fields.items()]
                body = "\n".join(fields)

            subject = self.form.email_subject
            if not subject:
                subject = "%s - %s" % (self.form.name, entry.time_created)
            else:
                t = Template(subject)
                subject = t.render(c)

            email_from = self.form.email_from or settings.DEFAULT_FROM_EMAIL
            t = Template(self.form.email_copies)
            email_copies = t.render(c)
            email_copies = [e.strip() for e in email_copies.split(",")
                            if e.strip()]
            if email_copies:
                msg = EmailMessage(subject, body, email_from, email_copies)
                for f in self.files.values():
                    f.seek(0)
                    msg.attach(f.name, f.read())
                msg.send()
        return entry


class FormsExportForm(forms.Form):

    """
    Form with a set of fields dynamically assigned that can be used to
    filter responses for the given ``forms.models.Form`` instance.
    """
    start_date = forms.DateField(label=_("Start date"), required=False)
    end_date = forms.DateField(label=_("End date"), required=False)

    def __init__(self, form, request, *args, **kwargs):
        self.form = form
        self.request = request
        self.columns, self.rows = forms_format_entries(
            form, FormsFormEntry.objects.none())
        self.form_fields = form.fields.select_related().all()
        super(FormsExportForm, self).__init__(*args, **kwargs)
        for field in self.columns['fields']:
            # Checkbox for including in export.
            if form.bind_to_account and field['slug'] == 'zorna_owner':
                self.fields['field_nickname'] = forms.BooleanField(
                    label=_(u'Nickname'), initial=True, required=False)
            self.fields[field['slug']] = forms.BooleanField(
                label=field['label'], initial=True, required=False)

        # Checkbox for including date creation.
        self.fields["field_time_created"] = forms.BooleanField(
            label=_("Creation date"), initial=True, required=False)
        self.fields["field_id"] = forms.BooleanField(
            label=_("Row ID"), initial=True, required=False)

    def get_entries(self):
        q = FormsFieldEntry.objects.select_related(depth=1).filter(Q(
            form_entry__form=self.form)).order_by("-form_entry__time_created")
        if self.cleaned_data["start_date"] and self.cleaned_data["end_date"]:
            time_from = self.cleaned_data["start_date"]
            time_to = self.cleaned_data["end_date"]
            if time_from and time_to:
                q = q.filter(
                    form_entry__time_created__range=(time_from, time_to))
        columns, rows = forms_format_entries(self.form, q)
        cols = self.get_columns()
        entries = []
        for r in rows:
            row = []
            if self.form.bind_to_account and self.cleaned_data["field_nickname"]:
                row.append({'value': r[
                           'entity'].account.username, 'type': fc.TEXT})
            for f in self.columns['fields']:
                if self.cleaned_data[f['slug']]:
                    row.append(r[f['slug']])
            if self.cleaned_data["field_time_created"]:
                row.append({'value': r[
                           'entity'].time_created, 'type': fc.DATE_TIME})
            if self.cleaned_data["field_id"]:
                row.append({'value': r['entity'].pk, 'type': fc.INTEGER})
            entries.append(row)

        return entries

    def get_columns(self):
        """
        Returns the list of selected column names.
        """
        f = []
        if self.form.bind_to_account and self.cleaned_data["field_nickname"]:
            f.append(smart_str(_(u"Nickname")))
        f.extend([smart_str(g['label'])
                 for g in self.columns['fields'] if self.cleaned_data[g['slug']]])
        if self.cleaned_data["field_time_created"]:
            f.append(smart_str(_(u"Creation date")))
        if self.cleaned_data["field_id"]:
            f.append(smart_str(_(u"Row ID")))
        return f


class FormForFormSet(FormForForm):

    def __init__(self, *args, **kwargs):
        kwargs['rget'] = self.rget
        super(FormForFormSet, self).__init__(self.form, *args, **kwargs)


def forms_factory(form, rget={}, *args, **kwargs):
    return type(str(form.slug) + 'FormsForm', (FormForFormSet,), {'form': form, 'rget': rget})


class comforms_community(ZornaCommunityAddons):

    _forms = {}

    def __init__(self, request):
        try:
            for slug in settings.ZORNA_COMMUNITY_FORMS:
                try:
                    form = FormsForm.objects.get(slug=slug)
                    self._forms[slug] = form
                except FormsForm.DoesNotExist:
                    pass
        except:
            pass

    def get_title(self, id):
        return _(self._forms[id].name)

    def get_content_type(self, id):
        ct = ContentType.objects.get_by_natural_key('forms', 'formsformentry')
        return ct

    def get_content_types(self):
        ct = ContentType.objects.get_by_natural_key('forms', 'formsformentry')
        return [ct]

    def get_content_type_id(self, id):
        ct = ContentType.objects.get_by_natural_key('forms', 'formsformentry')
        return ct.pk

    def get_tabs(self, request, community_id=0):
        tabs = []
        for form in self._forms.values():
            check = get_acl_for_model(form)
            if check.creator_formsform(form, request.user):
                tabs.append(form.slug)
        return tabs

    def get_menus(self, request, community_id=0):
        menus = []
        for form in self._forms.values():
            check = get_acl_for_model(form)
            if check.viewer_formsform(form, request.user):
                id = 'comforms_%s_menu' % form.slug
                menus.append({'title': form.name, 'url': reverse(
                    'communities_home_plugin', args=(id,)), 'id': id})
        return menus

    def get_page_title(self, request, id):
        return self._forms[id].name

    def save(self, request, id, form, message=None):
        return form.save(request=request)

    def render_form_by_id(self, request, id, post=False):
        try:
            form = self.get_form(request, id, post)
            return self.render_form(request, form)
        except FormsForm.DoesNotExist:
            return ''

    def render_form(self, request, form):
        try:
            t = loader.get_template("comforms/templates/forms_form.html")
            c = RequestContext(request, {'form_extra': form})
            return t.render(c)
        except FormsForm.DoesNotExist:
            return ''

    def get_form(self, request, id, post=False, instance_id=None):
        try:
            if instance_id:
                entry = FormsFormEntry.objects.select_related().get(
                    pk=instance_id)
                ff = entry.form
            else:
                ff = FormsForm.objects.get(slug=id)
                entry = None
            if post:
                args = (ff, request.POST, request.FILES or None)
            else:
                args = (ff,)
            form_extra = FormForForm(*args, instance=entry)
            return form_extra
        except FormsForm.DoesNotExist:
            return None

    def render_message(self, request, message_extra):
        try:
            entry = message_extra
            columns, entry = FormsFieldEntry.objects.forms_get_entries(
                entry.form, entries=[entry.pk])
            entry = entry[0]
            extra_context = {}
            extra_context['form'] = entry['entity'].form
            extra_context['columns'] = columns
            extra_context['row'] = entry
            t = loader.get_template(
                'forms_community_entry_%s.html' % entry['entity'].form.slug)
            c = RequestContext(request, extra_context)
            return t.render(c)
        except Exception as e:
            return ''

    def render_widget(self, request, id, community_id):
        ct = ContentType.objects.get_for_model(FormsFormEntry)
        # m =
        # MessageCommunityExtra.objects.select_related().filter(content_type =
        # ct).order_by('-message_time_updated')
        ff = self._forms[id]
        messages = get_messages_extra_by_content_type(
            request, ct, community_id)
        messages = messages.order_by('-message__time_updated')
        if len(messages):
            ids = {}
            for m in messages:
                ids[m.content_object.pk] = m.message
            field_entries = FormsFormEntry.objects.filter(
                form=ff, pk__in=ids.keys())
            columns, entries = FormsFieldEntry.objects.forms_get_entries(
                ff, entries=field_entries)
            for e in entries:
                e['community_message'] = ids[e['entity'].pk]
            t = loader.get_template('forms_community_widget_%s.html' % ff.slug)
            c = RequestContext(request, {
                               'entries': entries, 'community_id': community_id})
            return self.get_title(id), t.render(c)
        return '', ''

    def render_page(self, request, id, context={}):
        ct = ContentType.objects.get_for_model(FormsFormEntry)
        # m =
        # MessageCommunityExtra.objects.select_related().filter(content_type =
        # ct).order_by('-message_time_updated')
        community_id = context.get('community_id', 0)
        kwargs = {'q': context.get('search_string', '')}
        messages = get_messages_extra_by_content_type(
            request, ct, community_id)
        extra = {}
        for m in messages:
            extra[m.object_id] = m
        ff = FormsForm.objects.get(slug=id)
        field_entries = FormsFormEntry.objects.filter(
            form=ff, pk__in=extra.keys())
        columns, entries = FormsFieldEntry.objects.forms_get_entries(
            ff, entries=field_entries, **kwargs)
        t = loader.get_template('forms_community_entry_%s.html' % ff.slug)
        q = []
        for e in entries:
            extra_context = {}
            extra_context['form'] = e['entity'].form
            extra_context['columns'] = columns
            extra_context['row'] = e
            c = RequestContext(request, extra_context)
            q.append({'html': t.render(c), 'message': extra[
                     e['id']].message, 'id': e['entity'].pk})
        return q
