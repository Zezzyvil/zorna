from django.template import TemplateSyntaxError
from django import template
from django.template import Variable


from zorna.acl.models import get_acl_for_model
from zorna.forms.models import FormsForm, FormsFormEntry
from zorna.forms.api import forms_get_entries, isUserManager, forms_get_entry

register = template.Library()


class check_form_permission_node(template.Node):

    def __init__(self, form, permission, var_name):
        self.form = template.Variable(form)
        self.var_name = var_name
        self.permission = permission

    def render(self, context):
        request = context['request']
        try:
            slug = self.form.resolve(context)
        except template.VariableDoesNotExist:
            if self.form[0] == self.form[-1] and self.form[0] in ('"', "'"):
                slug = self.form[1:-1]
            else:
                slug = self.form
        try:
            if slug.isdigit():
                form = FormsForm.objects.get(pk=slug)
            else:
                form = FormsForm.objects.get(slug=slug)
        except Exception, e:
            return ''

        try:
            check = get_acl_for_model(form)
            func = getattr(check, '%s_formsform' % self.permission, None)
            if func is None:
                raise Exception("No handler for type %r" % self.permission)
            else:
                context[self.var_name] = func(form, request.user)
        except Exception as e:
            pass
        return ''


@register.tag(name="check_form_permission")
def check_permission(parser, token):
    bits = token.split_contents()
    if 5 != len(bits):
        raise TemplateSyntaxError('%r expects 5 arguments' % bits[0])
    if bits[-2] != 'as':
        raise TemplateSyntaxError(
            '%r expects "as" as the second argument' % bits[0])
    form = bits[1]
    permission = bits[2]
    varname = bits[-1]
    return check_form_permission_node(form, permission, varname)


class forms_get_entries_node(template.Node):

    def __init__(self, slug, columns, rows, where_field, where_id, q, o, ot):
        self.columns = columns
        self.slug = slug
        self.rows = rows
        self.o = o
        self.ot = ot
        self.q = q
        self.where_field = where_field
        self.where_id = where_id

    def render(self, context):
        kwargs = {}
        try:
            kwargs['q'] = self.q.resolve(context)
        except:
            kwargs['q'] = self.q
        try:
            kwargs['o'] = self.o.resolve(context)
        except:
            kwargs['o'] = self.o
        try:
            kwargs['ot'] = self.ot.resolve(context)
        except:
            kwargs['ot'] = self.ot

        if self.where_field:
            try:
                wf = Variable(self.where_field)
                where_field = wf.resolve(context)
            except Exception as e:
                where_field = self.where_field

            try:
                wd = Variable(self.where_id)
                where_id = wd.resolve(context)
            except Exception as e:
                where_id = self.where_id
            kwargs['where'] = where_field + '.dummy:' + str(where_id)
        cols, rows = forms_get_entries(self.slug, **kwargs)
        context[self.columns] = cols
        context[self.rows] = rows
        return ''


@register.tag(name="forms_get_entries")
def do_forms_get_entries(parser, token):
    bits = token.split_contents()
    if 5 > len(bits):
        raise TemplateSyntaxError(
            "%r tag follows form %r slug [q <search_string] [o <asc|desc>]  [ot <column_to_sort>] as <column_var> <rows_var>" % bits[0])
    if bits[-3] != 'as':
        raise TemplateSyntaxError(
            '%r expects "as" as argument' % bits[0])
    columns = bits[-2]
    rows = bits[-1]
    slug = bits[1]
    if 'q' in bits:
        index = bits.index('q')
        q = bits[index + 1]
    else:
        q = ''
    if 'o' in bits:
        index = bits.index('o')
        o = bits[index + 1]
    else:
        o = ''
    if 'ot' in bits:
        index = bits.index('ot')
        ot = bits[index + 1]
    else:
        ot = 'asc'

    if 'where' in bits:
        index = bits.index('where')
        where_field = bits[index + 1]
        where_id = bits[index + 2]
    else:
        where_field = where_id = None
    return forms_get_entries_node(slug, columns, rows, where_field, where_id, q, o, ot)


class get_panel_fields_node(template.Node):

    def __init__(self, form, panel, varname):
        self.form = Variable(form)
        if not (panel[0] == panel[-1] and panel[0] in ('"', "'")):
            self.panel = Variable(panel)
        else:
            self.panel = panel[1:-1]
        self.var_name = varname

    def render(self, context):
        if isinstance(self.panel, Variable):
            form_panel = self.panel.resolve(context)
        else:
            form_panel = self.panel
        form = self.form.resolve(context)
        context[self.var_name] = []
        for f in form.visible_fields():
            f.zcontrol_class = f.field.widget.__class__.__name__
            if form.instance.id:
                if f.zcontrol_class in ['CheckboxSelectMultiple', 'RadioSelect', 'SelectMultiple', 'Select']:
                        for e in f.field.choices:
                            if isinstance(e[1], (list, tuple)):
                                for c in e[1]:
                                    if c[0] == f.value():
                                        f.zcontrol_value = '%s - %s' % (
                                            e[0], c[1])
                                        break
                            else:
                                if e[0] == f.value():
                                    f.zcontrol_value = e[1]
                                    break
            panel = f.field.panel
            if panel and panel.name == form_panel:
                context[self.var_name].append(f)
            elif not panel and not form_panel:
                context[self.var_name].append(f)

        # context[self.var_name] = [f for f in form.visible_fields() if
        # f.field.panel and f.field.panel.name == self.panel]
        return ''


@register.tag(name="get_panel_fields")
def get_panel_fields(parser, token):
    bits = token.split_contents()
    if 5 != len(bits):
        raise TemplateSyntaxError('%r expects 5 arguments' % bits[0])
    if bits[-2] != 'as':
        raise TemplateSyntaxError(
            '%r expects "as" as the second argument' % bits[0])
    form = bits[1]
    panel = bits[2]
    varname = bits[-1]
    return get_panel_fields_node(form, panel, varname)


def show_form_test(context, slug):
    """Display a content form for test.

    Example::

        {% show_content 'form-slug' %}

    """
    from zorna.forms.views import forms_view_design_form
    request = context.get('request', None)
    try:
        form = FormsForm.objects.get(slug=slug)
        return {'content': forms_view_design_form(request, form)}
    except FormsForm.DoesNotExist:
        return {'content': ''}

show_form_test = register.inclusion_tag('forms/form_body_test.html',
                                        takes_context=True)(show_form_test)



class get_form_entry_node(template.Node):

    def __init__(self, entry, var_name):
        self.var_name = var_name
        self.entry = entry

    def render(self, context):
        request = context['request']
        try:
            entry = FormsFormEntry.objects.select_related(depth=1).get(pk=self.entry)
            form = entry.form
            check = get_acl_for_model(form)
            if not check.viewer_formsform(form, request.user) and not isUserManager(request, form.workspace.slug):
                return ''
        except Exception as e:
            print e
            return ''
        columns, row = forms_get_entry(entry)
        panels = {'':{}}
        for panel in form.formsformpanel_set.all():
            panel.fields = []
            panels[panel.label] = panel
        for f in form.fields.visible():
            if f.panel:
                panels[f.panel.label].fields.append(row[f.slug])
            else:
                panels[''].setdefault('fields', []).append(row[f.slug])
        context[self.var_name] = panels
        return ''


@register.tag(name="get_form_entry")
def get_form_entry(parser, token):
    '''
    {% get_form_entry 10 as entry %}
    {% for label,panel in entry.items %}
    <span>{{panel.panel_header|safe}}</span><br />
    <div>
        <span>{{label}}</span><br />
        {% for f in panel.fields %}
        <span>{{f.label}}</span>:<span>{{f.value}}</span><br />
        {% endfor %}
    </div>
    <span>{{panel.panel_footer|safe}}</span><br />
    {% endfor %}
    '''
    bits = token.split_contents()
    if 4 != len(bits):
        raise TemplateSyntaxError('%r expects 4 arguments' % bits[0])
    if bits[-2] != 'as':
        raise TemplateSyntaxError(
            '%r expects "as" as the second argument' % bits[0])
    entry = bits[1]
    varname = bits[-1]
    return get_form_entry_node(entry, varname)


@register.filter(name='zstr')
def str_(value):
    return str(value)
