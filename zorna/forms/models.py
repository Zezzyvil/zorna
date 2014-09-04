import datetime
import time
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext_noop
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.template import Context, Template
from django.db.models import Q
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.utils import formats

from zorna.forms import fields
from zorna.models import ZornaEntity


class FormsWorkspace(ZornaEntity):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150)

    class Meta:
        ordering = ['name']
        db_table = settings.TABLE_PREFIX + "forms_workspace"

    def __unicode__(self):
        return self.name

    def get_acl_permissions():
        return {
            u'manager': ugettext_noop(u'Who can use this workspace'),
        }
    get_acl_permissions = staticmethod(get_acl_permissions)


class FormsList(models.Model):

    """
    """
    name = models.CharField(_("Name"), max_length=255)
    description = models.CharField(_(
        "Description"), blank=True, max_length=255)
    workspace = models.ForeignKey(FormsWorkspace, editable=False)

    class Meta:
        verbose_name = _('list')
        verbose_name_plural = _('lists')
        db_table = settings.TABLE_PREFIX + "forms_list"

    def __unicode__(self):
        return self.name


class FormsListEntry(models.Model):

    """
    """
    value = models.CharField(_("Value"), max_length=255)
    list = models.ForeignKey(FormsList, editable=False)

    class Meta:
        verbose_name = _('list')
        verbose_name_plural = _('lists')
        db_table = settings.TABLE_PREFIX + "forms_list_entry"

    def __unicode__(self):
        return self.value


class FormsForm(ZornaEntity):

    """
    """
    name = models.CharField(_("Name"), max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    bind_to_account = models.BooleanField(_("Bind to account"), default=False, help_text=_(
        "If checked, each record will be linked to user account"))
    bind_to_entry = models.CharField(_("Bind to entry"), default='', max_length=255, help_text=_(
        "If filled, each record will be linked to target form entry"))
    bind_display = models.CharField(_(
        "Bind display"), default='', max_length=255, editable=False)
    button_text = models.CharField(_(
        "Button text"), max_length=50, default=_("Submit"))
    description = models.TextField(_('Description'), blank=True)
    send_email = models.BooleanField(_("Send email"), default=False, help_text=_(
        "If checked, an email will be sent"), editable=False)
    email_from = models.EmailField(_("From address"), blank=True, help_text=_(
        "The address the email will be sent from"), editable=False)
    email_copies = models.CharField(_("Send copies to"), blank=True, help_text=_(
        "One or more email addresses, separated by commas"), max_length=200, editable=False)
    email_subject = models.CharField(_(
        "Subject"), max_length=200, blank=True, editable=False)
    email_message = models.TextField(_("Message"), blank=True, editable=False)
    template = models.TextField(_('Template'), editable=False, blank=True)
    workspace = models.ForeignKey(FormsWorkspace, editable=False)

    class Meta:
        verbose_name = _('forms form')
        verbose_name_plural = _('forms form')
        db_table = settings.TABLE_PREFIX + "forms_form"

    def __unicode__(self):
        return self.name

    def get_url_path(self):
        return reverse('forms_add_form_entry', args=[self.slug])

    def get_url_browse_path(self):
        return reverse('form_browse_entries_view', args=[self.slug])

    def get_acl_permissions():
        return {
            u'viewer': ugettext_noop(u'Who can see the list of recordings of this form'),
            u'creator': ugettext_noop(u'Who can create new records'),
            u'modifier': ugettext_noop(u'Who can modify records'),
        }
    get_acl_permissions = staticmethod(get_acl_permissions)


class FormsFormAction(models.Model):
    form = models.ForeignKey(FormsForm, null=True, editable=False)
    content_type = models.ForeignKey(ContentType, editable=False)
    object_id = models.IntegerField(editable=False)
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = _('form action')
        verbose_name_plural = _('form actions')
        db_table = settings.TABLE_PREFIX + "forms_form_actions"

    def __unicode__(self):
        return u'%s [%s]' % (self.content_object, self.form.name)


class FormsFormActionMessage(models.Model):
    form = models.ForeignKey(FormsForm, null=True, editable=False)
    message = models.TextField(_("Message"))

    class Meta:
        verbose_name = _('message form action')
        verbose_name_plural = _('message form actions')
        db_table = settings.TABLE_PREFIX + "forms_form_action_messages"

    def __unicode__(self):
        return u'%s' % self.message


class FormsFormActionUrl(models.Model):
    form = models.ForeignKey(FormsForm, null=True, editable=False)
    url = models.CharField(_("Url"), max_length=255)

    class Meta:
        verbose_name = _('url form action')
        verbose_name_plural = _('url form actions')
        db_table = settings.TABLE_PREFIX + "forms_form_action_urls"

    def __unicode__(self):
        return u'%s' % self.url


class FormsFormPanel(models.Model):
    form = models.ForeignKey(FormsForm, null=True, editable=False)
    name = models.CharField(_(
        "Name"), max_length=255, help_text=_("Control name"))
    label = models.CharField(_("Title"), max_length=255, help_text=_(
        "Panel title"), null=True, blank=True)
    width = models.CharField(_("Width"), max_length=255, help_text=_(
        "Width including units (px, %, ...)"), null=True, blank=True)
    height = models.CharField(_("Height"), max_length=255, help_text=_(
        "Height including units (px, %, ...)"), null=True, blank=True)
    margin = models.CharField(_("Margin"), max_length=255, help_text=_(
        "Margin including units (px, %, ...)"), null=True, blank=True)
    css_class = models.CharField(_("Css Class"), max_length=255, help_text=_(
        "Css classes"), null=True, blank=True)
    stacked = models.BooleanField(_("Stacked"), help_text=_(
        "Label and control are stacked"), default=False)
    sort_order = models.IntegerField(_(
        'sort order'), default=0, editable=False, help_text='The order you would like panels to be displayed.')
    panel_header = models.TextField(_('Panel header'), blank=True)
    panel_footer = models.TextField(_('Panel footer'), blank=True)

    class Meta:
        verbose_name = _('form panel')
        verbose_name_plural = _('form panels')
        ordering = ['sort_order']
        db_table = settings.TABLE_PREFIX + "forms_form_panels"

    def __unicode__(self):
        return u'%s (%s)' % (self.name, self.label)


class FormsFormFieldManager(models.Manager):

    """
    Only show visible fields when displaying actual form..
    """
    def visible(self):
        return self.filter(visible=True)

    def not_visible(self):
        return self.filter(visible=False)

BORDER_STYLES = (
    ('', ''),
    ('none', 'none'),
    ('dotted', 'dotted'),
    ('dashed', 'dashed'),
    ('solid', 'solid'),
    ('double', 'double'),
    ('groove', 'groove'),
    ('ridge', 'ridge'),
    ('inset', 'inset'),
    ('outset', 'outset'),
)

LABEL_SIZE = (
    ('', ''),
    ('x-small', 'x-small'),
    ('small', 'small'),
    ('dashed', 'dashed'),
    ('medium', 'medium'),
    ('large', 'large'),
    ('x-large', 'x-large'),
)


class FormsFormField(models.Model):

    """
    """
    form = models.ForeignKey(FormsForm, related_name="fields", editable=False)
    label = models.CharField(_("Label"), max_length=255)
    slug = models.SlugField(max_length=100)
    help_text = models.CharField(_("Help text"), blank=True, max_length=255)
    required = models.BooleanField(_("Required"), default=True)
    visible = models.BooleanField(_("Visible"), default=True)
    default_value = models.CharField(_(
        "Default value"), blank=True, max_length=255)
    sort_order = models.IntegerField(_(
        'sort order'), default=0, editable=False, help_text='The order you would like fields to be displayed.')
    field_type = models.IntegerField(_(
        "Type"), choices=fields.NAMES, default=fields.TEXT)
    list = models.ForeignKey(FormsList, null=True, blank=True,)
    reference = models.CharField(_(
        "Reference"), max_length=255, blank=True, default='')
    reference_display = models.CharField(_(
        "Reference display"), max_length=255, blank=True, default='')
    panel = models.ForeignKey(FormsFormPanel, null=True, blank=True)
    visible_in_list = models.BooleanField(_(
        "Visible in list"), default=True, editable=False)
    sort_order_list = models.IntegerField(_(
        'sort order list'), default=0, editable=False, help_text='The order you would like fields to be displayed in lists.')
    for_sort = models.BooleanField(_(
        "Use this field to sort"), default=False, editable=False)
    width = models.CharField(_("Width"), max_length=255, help_text=_(
        "Width including units (px, %, ...)"), null=True, blank=True)
    margin = models.CharField(_("Margin"), max_length=255, help_text=_(
        "Margin including units (px, %, ...)"), null=True, blank=True)
    padding = models.CharField(_("Height"), max_length=255, help_text=_(
        "Padding including units (px, %, ...)"), null=True, blank=True)
    css_class = models.CharField(_("Css Class"), max_length=255, help_text=_(
        "Css classes"), null=True, blank=True)
    bg_color = models.CharField(_("Background color"), max_length=255, help_text=_(
        "Background color ( string or hex )"), null=True, blank=True)
    border_width = models.CharField(_("Border width"), max_length=255, help_text=_(
        "Border width including units (px, %, ...)"), null=True, blank=True)
    border_style = models.CharField(_(
        "Border style"), max_length=20, choices=BORDER_STYLES, default='', help_text=_("Border style"), blank=True)
    border_color = models.CharField(_("Border color"), max_length=255, help_text=_(
        "Background color ( string or hex )"), null=True, blank=True)
    label_color = models.CharField(_("Label color"), max_length=255, help_text=_(
        "Label color ( string or hex )"), null=True, blank=True)
    label_size = models.CharField(_(
        "Label size"), max_length=20, choices=LABEL_SIZE, default='', help_text=_("Label size"), blank=True)
    bold = models.BooleanField(_("Bold"), help_text=_(
        "Check this checkbox to make the control's label bold"), default=False)
    italic = models.BooleanField(_("Italic"), help_text=_(
        "Check this checkbox to italicize the control's label"), default=False)

    objects = FormsFormFieldManager()

    class Meta:
        verbose_name = _('forms field')
        verbose_name_plural = _('forms fields')
        ordering = ['sort_order']
        db_table = settings.TABLE_PREFIX + "forms_form_field"

    def __unicode__(self):
        return self.label

    def get_choices(self, value=False, include_all=''):
        if self.list:
            if include_all:
                yield '', include_all
            for v in self.list.formslistentry_set.all():
                yield v.value, v.value
        elif self.reference and '.' in self.reference:
            r = self.reference.split('.')
            try:
                form_target = FormsForm.objects.get(slug=r[0])
                columns, entries = FormsFieldEntry.objects.forms_get_entries(
                    form_target, **{'ot': 'asc', 'o': r[1]})
            except:
                entries = []

            if include_all:
                yield '', include_all
            if self.reference_display:
                t = Template(self.reference_display)
            else:
                t = None
            for e in entries:
                if value:
                    f = e[r[1]]['value']
                else:
                    f = e['entity'].pk
                if t:
                    ec = {}
                    for fd in e['fields']:
                        ec[fd['slug']] = {'label': fd[
                            'label'], 'value': fd['value']}
                    c = Context(ec)
                    yield f, t.render(c)
                else:
                    yield f, e[r[1]]['value']

    def is_a(self, *args):
        """
        Helper that returns True if the field's type is given in any arg.
        """
        return self.field_type in args


class FormsFormEntry(ZornaEntity):
    form = models.ForeignKey(FormsForm, related_name="entries")
    account = models.ForeignKey(User, editable=False, null=True, blank=True)
    entry = models.ForeignKey('self', editable=False, null=True, blank=True)

    class Meta:
        verbose_name = _('form entry')
        verbose_name_plural = _('form entries')
        db_table = settings.TABLE_PREFIX + "forms_form_entry"

    def __unicode__(self):
        return self.form.name

    def get_account_avatar(self):
        return self.get_user_avatar(self.account_id)

    def get_account_full_name(self):
        return self.get_user_full_name(self.account_id)

    def get_entries(self, slug):
        entries = self.formsformentry_set.filter(form__slug=slug)
        return FormsFieldEntry.objects.forms_get_entries(slug, entries=entries)

"""
class FormsFormEntryExtra(models.Model):
    entry = models.ForeignKey(FormsFormEntry, null=True, editable=False)
    content_type = models.ForeignKey(ContentType, editable=False)
    object_id = models.IntegerField(editable=False)
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = _('forms entry extra info')
        verbose_name_plural = _('forms entries extra info')
        db_table = settings.TABLE_PREFIX + "forms_form_entry_extra"

    def __unicode__(self):
        return u'%s [%s]' % (self.content_object, self.message)
"""


class FormsFieldEntryManager(models.Manager):

    def forms_get_entries(self, slug_or_form, *args, **kwargs):
        if isinstance(slug_or_form, FormsForm):
            form = slug_or_form
        else:
            try:
                form = FormsForm.objects.select_related(
                    depth=1).get(slug=slug_or_form)
            except Exception as e:
                return [], []

        form_fields = form.fields.all()
        filterFields = None
        form.fields_reference = {}
        filterFieldsEntries = None
        for f in form_fields:
            if kwargs.has_key(f.slug):
                value = kwargs[f.slug]
            else:
                value = None
            if '.' in f.reference and f.is_a(*fields.CHOICES):
                form.fields_reference[f.pk] = []
                for e in f.get_choices():
                    form.fields_reference[f.pk].append(e)
                    if value and value == e[1]:
                        value = e[0]
            if kwargs.has_key(f.slug):
                if filterFieldsEntries:
                    filterFieldsEntries = FormsFieldEntry.objects.filter(form_entry__form=form, value=value, field__slug=f.slug,
                        form_entry__pk__in = [f.form_entry_id for f in filterFieldsEntries])
                else:
                    filterFieldsEntries = FormsFieldEntry.objects.filter(form_entry__form=form, value=value, field__slug=f.slug)
        try:
            if not filterFieldsEntries.exists():
                return [],[]
        except:
            pass


        entries = kwargs.get('entries', None)
        f = kwargs.get('f', None)
        q = kwargs.get('q', None)
        o = kwargs.get('o', None)
        ot = kwargs.get('ot', 'asc')
        hidden = kwargs.get('hidden', '')
        if hidden:
            hidden = hidden.split(',')
        else:
            hidden = []
        filter = None
        if q:
            if q[0] == q[-1] and q[0] in ('"', "'"):
                q = q[1:-1]
                if f:
                    filter = Q(field__slug=f) & Q(value__iexact=q)
                else:
                    filter = Q(form_entry__account__last_name__iexact=q) | \
                        Q(form_entry__account__first_name__iexact=q) | \
                        Q(value__iexact=q)
            else:
                if f:
                    filter = Q(field__slug=f) & Q(value__icontains=q)
                else:
                    filter = Q(form_entry__account__last_name__icontains=q) | \
                        Q(form_entry__account__first_name__icontains=q) | \
                        Q(value__icontains=q)

        if filter or filterFieldsEntries:
            if filter and filterFieldsEntries:
                field_entries = FormsFieldEntry.objects.filter(Q(form_entry__form=form) & filter, pk__in = [f.pk for f in filterFieldsEntries])
            elif filterFieldsEntries:
                field_entries = FormsFieldEntry.objects.filter(Q(form_entry__form=form), pk__in = [f.pk for f in filterFieldsEntries])
            else:
                field_entries = FormsFieldEntry.objects.filter(Q(
                    form_entry__form=form) & filter)
            filter = Q(form_entry__in=[f.form_entry_id for f in field_entries])
        else:
            filter = Q(form_entry__form=form)
        # Aggregate each column
        # FormsFormEntry.objects.filter(form=form).values('fields__field__label').annotate(Avg('fields__value'))
        where = kwargs.get('where', '')
        if where:
            try:
                r = where.split(':')
                entry_id = r[1]
                r = r[0].split('.')
                form_slug = r[0]

                fr = ''
                slug = form.bind_to_entry.split('.')[0]
                while True:
                    f = FormsForm.objects.get(slug=slug)
                    if not f:
                        break
                    fr = fr + '__entry'
                    if f.slug == r[0] or not f.bind_to_entry:
                        break
                    slug = f.bind_to_entry.split('.')[0]

                entry = FormsFormEntry.objects.select_related().get(
                    pk=entry_id)
                if entry.form.slug == form_slug:
                    fr = 'form_entry%s' % fr
                    filter = filter & Q(**{fr: entry})
                else:
                    return [], []
            except:
                return [], []

        def entry_sort(entry):
            try:
                return float(entry[o]['value'])
            except:
                return entry[o]['value'].lower()

        if entries is None:
            field_entries = FormsFieldEntry.objects.select_related(
                depth=1).filter(filter)
        else:
            field_entries = FormsFieldEntry.objects.select_related(
                depth=1).filter(filter, form_entry__in=entries)
        columns, entries = forms_format_entries(form, field_entries, hidden)
        if o:
            try:
                entries.sort(
                    key=entry_sort, reverse=False if ot == 'asc' else True)
            except Exception as e:
                print e
                pass
        return columns, entries

    def forms_get_entry(self, entry):
        columns, entries = self.forms_get_entries(
            entry.form, entries=[entry.pk])
        return columns, entries[0]


class FormsFieldEntry(models.Model):
    field = models.ForeignKey(FormsFormField)
    form_entry = models.ForeignKey(FormsFormEntry, related_name="fields")
    value = models.CharField(max_length=2000)

    objects = FormsFieldEntryManager()

    class Meta:
        verbose_name = _('form entry')
        verbose_name_plural = _('form entries')
        db_table = settings.TABLE_PREFIX + "forms_field_entry"


def format_field_value(field_entry, field):
    type = field.field_type
    if type == fields.ZORNA_USER:
        value = User.objects.get(pk=field_entry.value).get_profile().__unicode()
    elif type == fields.FILE:
        value = reverse("file_view", args=(field_entry.id,))
    elif type in fields.DATES:
        value = field_entry.value
    elif type in fields.CHOICES:
        if field.target_entries:
            if type in fields.MULTIPLE_CHOICES:
                d = field_entry.value.split(',')
                val = []
                for v in d:
                    val.append(field.target_entries[int(v)]['value'])
                value = val
            else:
                value = field.target_entries[int(field_entry.value)]['value']
        elif type in fields.MULTIPLE_CHOICES:
            d = field_entry.value.split(',')
            val = []
            for v in d:
                val.append(v)
            value = val
        else:
            value = field_entry.value
    elif type == fields.DECIMAL:
        value = float(field_entry.value)
    elif type == fields.INTEGER:
        value = int(field_entry.value)
    else:
        value = field_entry.value

    return {'value': value, 'type': fields.NAMES_TPL[type]}


def get_form_field_values_old(field):
    return FormsFieldEntry.objects.raw('select * from zorna_forms_field_entry where field_id=%s order by value', [field.pk])


def get_form_field_values(field, visited=[]):
    if not field.reference:
        return FormsFieldEntry.objects.raw('select * from zorna_forms_field_entry where field_id=%s order by value', [field.pk])
    elif field.reference in visited:
        # if circular return values of original field
        r = visited[0].split('.')
        field = FormsFormField.objects.get(form__slug=r[0], slug=r[1])
        return FormsFieldEntry.objects.raw('select * from zorna_forms_field_entry where field_id=%s order by value', [field.pk])
    else:
        visited.append(field.reference)
        r = field.reference.split('.')
        field = FormsFormField.objects.get(form__slug=r[0], slug=r[1])
        return get_form_field_values(field, visited)


def deepish_copy(org):
    '''
    much, much faster than deepcopy, for a dict of the simple python types.
    '''
    out = dict().fromkeys(org)
    for k, v in org.iteritems():
        try:
            out[k] = v.copy()   # dicts, sets
        except AttributeError:
            try:
                out[k] = v[:]   # lists, tuples, strings, unicode
            except TypeError:
                out[k] = v      # ints

    return out


def forms_format_entries(form, query_set, hidden=[]):
    '''
    return columns and rows from FormFormEntry queryset
    if a form is bind to account, two fields are added:
        - zorna_owner_last_name
        - zorna_owner_first_name
    if a form is bind to another another form field, a new field is added with slug='slug of target field':

    columns are formated as follow:
        - columns[slug] = label . This let you access label directly from slug
        - columns['fields'] = [ { 'slug':slug, 'label': label }, ...] list of columns

    rows is a list where each entry is like this:
        - entry['entity'] is FormsFormEntry record
        - entry['id'] is pk  of FormsFormEntry record
        - for each field with slug='slug' in columns:
            - entry['slug'] = { 'value': value of field, 'type': type of field}
                where type=text|url|date|list
        - entry[fields] is a list of fields in the same order as columns where each entry is:
            - { 'value': value of field, 'type': type of field, 'slug':'slug'}
                where type=text|url|date|list
    '''
    cols = {}
    columns = {'fields': []}
    forms_entry_fields = {}
    forms_binds = []
    forms_fields = {}

    form_fields = FormsFormField.objects.filter(
        form=form).order_by('sort_order_list')
    for f in form_fields:
        forms_fields[f.pk] = f
        # if records are bind to users, add owner column
        if f.field_type == fields.ZORNA_USER_SINGLETON and form.bind_to_account:
            slug = 'zorna_owner'
            columns[slug] = _(u'User')
            columns['fields'].append({'label': columns[
                                     slug], 'slug': slug, 'type': fields.ZORNA_USER, 'values': []})
            cols[slug] = {'label': columns[
                slug], 'help_text': '', 'type': fields.ZORNA_USER, 'value': ''}
        elif f.field_type == fields.FORM_ENTRY and form.bind_to_entry:
            # if records are bind to entries of an another form
            if form.bind_to_entry:
                bind = form.bind_to_entry.split('.')
                tmp = []
                while len(bind) == 2:
                    if bind[1] == 'zorna_owner':
                        form_target = FormsForm.objects.get(slug=bind[0])
                        tmp.append([bind, form_target])
                        bind = form_target.bind_to_entry.split('.')
                    else:
                        target_field = FormsFormField.objects.get(
                            slug=bind[1], form__slug=bind[0])
                        tmp.append([bind, target_field])
                        bind = target_field.form.bind_to_entry.split('.')

                tmp.reverse()

                for b in tmp:
                    bind = b[0]
                    if bind[1] == 'zorna_owner':
                        target_slug = 'zorna_owner_%s' % bind[0]
                        forms_entry_fields[target_slug] = {}
                        columns[target_slug] = _("User")
                        columns['fields'].append({'label': columns[
                                                 target_slug], 'slug': target_slug, 'type': fields.ZORNA_USER, 'values': []})
                        cols[target_slug] = {'label': columns[target_slug], 'help_text': '', 'form_bind': bind[
                            0], 'field_bind': bind[1], 'type': fields.ZORNA_USER, 'value': ''}
                        form_target = b[1]
                        tgcols, tgrows = FormsFieldEntry.objects.forms_get_entries(
                            form_target, entries=[e.id for e in FormsFormEntry.objects.filter(form=form_target)])
                        for r in tgrows:
                            forms_entry_fields[target_slug][r['id']] = r
                    else:
                        target_field = b[1]
                        target_slug = target_field.slug
                        forms_entry_fields[target_slug] = {}
                        columns[target_slug] = target_field.label
                        columns['fields'].append({'label': columns[
                                                 target_slug], 'slug': target_slug, 'type': target_field.field_type, 'values': []})
                        cols[target_slug] = {'label': columns[target_slug], 'help_text': '', 'form_bind': bind[
                            0], 'field_bind': bind[1], 'type': target_field.field_type, 'value': ''}
                        tgcols, tgrows = forms_format_entries(
                            target_field.form, FormsFieldEntry.objects.select_related(depth=1).filter(field=target_field))
                        for r in tgrows:
                            forms_entry_fields[target_slug][r['id']] = r
                    forms_binds.append(target_slug)
        else:
            columns['fields'].append({
                                     'label': f.label, 'slug': f.slug, 'type': f.field_type, 'total': 0, 'values': []})
            columns[f.slug] = f.label
            cols[f.slug] = {'label': f.label, 'help_text':
                            f.help_text, 'type': fields.NAMES_TPL[f.field_type], 'value': ''}
            f.target_entries = None
            try:
                form.fields_reference
            except:
                form.fields_reference = {}

            if f.field_type in fields.CHOICES and '.' in f.reference and f.slug not in hidden:
                try:
                    form.fields_reference[f.pk]
                except:
                    form.fields_reference[f.pk] = [e for e in f.get_choices()]

                f.target_entries = {}
                for e in form.fields_reference[f.pk]:
                    # f.target_entries[e.form_entry_id] = {'value': e.value,
                    # 'type':field_target.field_type}
                    f.target_entries[e[0]] = {
                        'value': e[1], 'type': f.field_type}

    forms_binds.reverse()
    rows = {}
    rows_order = []
    rows_set = set()  # for fast search
    for field_entry in query_set:
        try:
            rows[field_entry.form_entry_id]
        except KeyError:
            rows[field_entry.form_entry_id] = deepish_copy(cols)

        try:
            val = format_field_value(field_entry,
                                     forms_fields[field_entry.field_id])
        except:
            val = {'value': '', 'type':
                   forms_fields[field_entry.field_id].field_type}
        # if type == fields.FILE:
        #    val['value'] = request.build_absolute_uri(val['value'])
        # rows[field_entry.form_entry_id][forms_fields[field_entry.field_id].slug].update(val)
        rows[field_entry.form_entry_id][
            forms_fields[field_entry.field_id].slug]['value'] = val['value']
        rows[field_entry.form_entry_id][
            forms_fields[field_entry.field_id].slug]['type'] = val['type']
        rows[field_entry.form_entry_id][
            forms_fields[field_entry.field_id].slug]['id'] = field_entry.pk
        if field_entry.form_entry_id not in rows_set:
            rows_order.append(field_entry.form_entry_id)
            rows_set.add(field_entry.form_entry_id)
            rows[field_entry.form_entry_id][
                'zorna_entity'] = field_entry.form_entry
            if form.bind_to_account:
                # rows[field_entry.form_entry_id]['zorna_owner'].update({'value':field_entry.form_entry.account.get_full_name(),
                # 'type':fields.NAMES_TPL[fields.ZORNA_USER]})
                rows[field_entry.form_entry_id]['zorna_owner'][
                    'value'] = field_entry.form_entry.account.get_profile().__unicode__()
                rows[field_entry.form_entry_id]['zorna_owner'][
                    'type'] = fields.NAMES_TPL[fields.ZORNA_USER]
            if form.bind_to_entry:
                e_id = field_entry.form_entry.entry_id
                for t in forms_binds:
                    if e_id and e_id in forms_entry_fields[t]:
                        if t.rfind('zorna_owner_') == 0:
                            # rows[field_entry.form_entry_id][t].update({'value':forms_entry_fields[t][e_id]['zorna_owner']['value'],
                            # 'type':fields.NAMES_TPL[fields.TEXT],
                            # 'entry_bind':forms_entry_fields[t][e_id]})
                            rows[field_entry.form_entry_id][t][
                                'value'] = forms_entry_fields[t][e_id]['zorna_owner']['value']
                            rows[field_entry.form_entry_id][t][
                                'type'] = fields.NAMES_TPL[fields.TEXT]
                            rows[field_entry.form_entry_id][t][
                                'entry_bind'] = forms_entry_fields[t][e_id]
                        else:
                            # rows[field_entry.form_entry_id][t].update({'value':forms_entry_fields[t][e_id][t]['value'],
                            # 'type':fields.NAMES_TPL[fields.TEXT],
                            # 'entry_bind':forms_entry_fields[t][e_id]})
                            rows[field_entry.form_entry_id][t][
                                'value'] = forms_entry_fields[t][e_id][t]['value']
                            rows[field_entry.form_entry_id][t][
                                'type'] = fields.NAMES_TPL[fields.TEXT]
                            rows[field_entry.form_entry_id][t][
                                'entry_bind'] = forms_entry_fields[t][e_id]
                        e_id = forms_entry_fields[t][e_id]['entity'].entry_id
                    else:
                        # rows[field_entry.form_entry_id][t].update({'value':'',
                        # 'type':fields.NAMES_TPL[fields.TEXT]})
                        rows[field_entry.form_entry_id][t]['value'] = ''
                        rows[field_entry.form_entry_id][t][
                            'type'] = fields.NAMES_TPL[fields.TEXT]

    for h in hidden:
        if h:
            for i in range(len(columns['fields'])):
                slug = columns['fields'][i]['slug']
                if slug == h:
                    del columns['fields'][i]
                    del columns[slug]
                    break
    # reorder records
    entries = []
    for row in rows_order:
        entry = {}
        entry['entity'] = rows[row]['zorna_entity']
        entry['id'] = rows[row]['zorna_entity'].pk
        # for f in FormsFormEntry._meta.fields:
        #    entry[f.name] = getattr(rows[row]['zorna_entity'], f.name)
        r = []
        for c in columns['fields']:
            if c['type'] in [fields.DECIMAL, fields.INTEGER]:
                try:
                    if c['type'] == fields.INTEGER and rows[row][c['slug']]['value']:
                        c['total'] = c['total'] + int(
                            rows[row][c['slug']]['value'])
                    else:
                        c['total'] = c['total'] + Decimal(
                            str(rows[row][c['slug']]['value']))
                except InvalidOperation:
                    pass
            elif c['type'] == fields.DATE_TIME:
                try:
                    rows[row][c['slug']]['value'] = formats.date_format(
                        datetime.datetime(*time.strptime(rows[row][c['slug']]['value'], "%Y-%m-%d %H:%M:%S")[0:5]), "SHORT_DATETIME_FORMAT")
                except Exception, e:
                    rows[row][c['slug']]['value'] = ''
            elif c['type'] == fields.DATE:
                try:
                    rows[row][c['slug']]['value'] = formats.date_format(
                        datetime.datetime(*time.strptime(rows[row][c['slug']]['value'], "%Y-%m-%d")[0:5]), "SHORT_DATE_FORMAT")
                except Exception, e:
                    rows[row][c['slug']]['value'] = ''
            c['values'].append(rows[row][c['slug']]['value'])

            entry[c['slug']] = rows[row][c['slug']]
            rows[row][c['slug']].update({'slug': c['slug']})
            r.append(rows[row][c['slug']])
        entry['fields'] = r
        entries.append(entry)
    return columns, entries
