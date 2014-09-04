import os
from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext_noop
from django.core.urlresolvers import reverse

from mptt.models import MPTTModel

from tagging.fields import TagField
from tagging.utils import parse_tag_input
from tagging.models import Tag

from zorna.models import ZornaEntity
from zorna.fileman.managers import ZornaFolderManager
from zorna.utilit import get_upload_library

FOLDER_NOTIFICATIONS = (
    (0, _(u'No email notification')),
    (1, _(u'Send email notification')),
    (2, _(u'Let the author decide')),
)


class ZornaFolder(MPTTModel, ZornaEntity):
    parent = models.ForeignKey(
        'self', null=True, blank=True, related_name='children')
    name = models.CharField(_('name'), max_length=255)
    slug = models.SlugField(_('slug'), max_length=255, null=True, blank=True)
    inherit_permissions = models.BooleanField(_(u'Inherit permissions'))
    email_notification = models.IntegerField(max_length=1, choices=FOLDER_NOTIFICATIONS, default=0, help_text=_(
        u'Users will receive email notification when a file is uploaded or updated'))
    objects = ZornaFolderManager()

    class Meta:
        verbose_name = _('folder')
        verbose_name_plural = _('folders')
        ordering = ['tree_id', 'lft']
        db_table = settings.TABLE_PREFIX + "folders"

    def __unicode__(self):
        return self.name

    def get_complete_slug(self):
        url = u''
        for ancestor in self.get_ancestors(ascending=True):
            url = ancestor.slug + u'/' + url
        return url

    def get_acl_permissions():
        return {
            'reader': ugettext_noop(u'Who can browse this folder'),
            'writer': ugettext_noop(u'Who can upload files to this folder'),
            'manager': ugettext_noop(u'Who can manage this folder'),
        }
    get_acl_permissions = staticmethod(get_acl_permissions)


class ZornaFile(ZornaEntity):
    description = models.CharField(max_length=255)
    folder = models.CharField(_(
        'root_folder'), max_length=255, default='', editable=False)
    tags = TagField()

    class Meta:
        verbose_name = _('file')
        db_table = settings.TABLE_PREFIX + "files"

    def __unicode__(self):
        return _(u'file %s') % self.description

    def delete(self):
        # Deleting all asociated tags.
        Tag.objects.update_tags(self, None)
        super(ZornaFile, self).delete()

    def get_tag_list(self):
        return parse_tag_input(self.tags)

    def get_file_info(self):
        root_path = get_upload_library()
        info = {}
        fullpath = u"%s/%s" % (root_path, self.folder)
        for dirName, subdirList, fileList in os.walk(fullpath):
            for file_name in fileList:
                tab = file_name.split(',')
                if len(tab) > 1 and tab[0].isdigit():
                    pk, filename = tab[0], ','.join(tab[1:])
                    if int(pk) == self.pk:
                        info['filename'] = filename
                        url_component = dirName[len(
                                root_path) + 1:].replace('\\', '/')
                        info['url'] = reverse('get_file') + '?file=' + url_component + '/%s,%s' % (self.pk, filename)
                        info['path'] = url_component
                        return info
        return info
