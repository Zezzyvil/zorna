import os
import stat
from datetime import datetime
from django.core.urlresolvers import reverse

from django.utils.translation import ugettext_lazy as _
from zorna.fileman.models import ZornaFile
from zorna.acl.models import get_allowed_objects, get_acl_for_model
from zorna.communities.models import Community
from zorna.fileman.models import ZornaFolder
from zorna.site.models import SiteOptions
from zorna.utilit import get_upload_library


def split_file_name(name):
    tab = name.split(',')
    if len(tab) > 1 and tab[0].isdigit():
        return tab[0], ','.join(tab[1:])
    else:
        return False, name


def get_allowed_shared_folders(user, perms):
    ao = set([])
    for perm in perms:
        objects = get_allowed_objects(user, ZornaFolder, perm)
        ao = ao.union(set(objects))
    return list(ao)


def get_user_access_to_path(user, path):
    dirs = path.split('/')
    if dirs[0][0] == "U":
        if not user.is_anonymous() and int(dirs[0][1:]) == user.pk:
            return True, True
        else:
            return False, False
    elif dirs[0][0] == "C":
        check = get_acl_for_model(Community)
        try:
            com = Community.objects.get(pk=int(dirs[0][1:]))
            bmanager = check.manage_community(com, user)
            buser = check.member_community(com, user)
            return buser or bmanager, bmanager
        except:
            return False, False
    elif dirs[0][0] == "F":
        check = get_acl_for_model(ZornaFolder)
        try:
            folder = ZornaFolder.objects.get(pk=int(dirs[0][1:]))
            if folder.inherit_permissions:
                parents = folder.get_ancestors()
                for f in parents:
                    if f.inherit_permissions is False:
                        folder = f
                        break
            buser = check.reader_zornafolder(folder, user)
            bmanager = check.manager_zornafolder(
                folder, user) or check.writer_zornafolder(folder, user)
            return buser or bmanager, bmanager
        except:
            return False, False
    return False, False


def get_path_components(path, default=_(u'Recent files')):
    if not path:
        return [{'rel': '', 'text': default}]

    cdir_components = []
    dirs = path.split('/')
    cpath = dirs.pop(0)
    if cpath[0] == 'F':
        folder = ZornaFolder.objects.get(pk=int(cpath[1:]))
        parents = folder.get_ancestors()
        for f in parents:
            cdir_components.append({'rel': 'F%s' % f.pk, 'text': f.name})
        what = folder.name
    elif cpath[0] == 'C':
        com = Community.objects.get(pk=int(cpath[1:]))
        what = com.name
    else:
        what = u"My Documents"

    cdir_components.append({'rel': cpath, 'text': what})
    for d in dirs:
        cpath += '/' + d
        cdir_components.append({'rel': cpath, 'text': d})
    return cdir_components


def get_files_from_query(request, query_result):
    results = {}
    roots_folder = []
    id_files = []
    for f in query_result:
        if f.folder not in roots_folder:
            roots_folder.append(f.folder)
        id_files.append(f.pk)
    path = get_upload_library()
    for p in roots_folder:
        buser, bmanager = get_user_access_to_path(request.user, p)
        ret = get_path_components(p)
        human_path = '/'.join([c['text'] for c in ret])
        for dirname, dirs, filenames in os.walk(os.path.join(path, p)):
            for f in filenames:
                pk, fname = split_file_name(f)
                pk = int(pk)
                if pk and pk in id_files:
                    url_component = dirname[len(
                        path) + 1:].replace('\\', '/')
                    file_path = human_path + url_component[len(p):]
                    statinfo = os.stat(os.path.join(dirname, f))
                    fileinfo = {'name': fname,
                                'realname': f,
                                'size': statinfo[stat.ST_SIZE],
                                'creation': datetime.fromtimestamp(statinfo[stat.ST_CTIME]),
                                'modification': datetime.fromtimestamp(statinfo[stat.ST_MTIME]),
                                'ext': os.path.splitext(f)[1][1:],
                                'path': url_component,
                                'manager': bmanager,
                                }
                    results[pk] = (
                        fname, url_component, file_path, fileinfo)
                    id_files.remove(pk)
                    if not len(id_files):
                        break
            if not len(id_files):
                break
        if not len(id_files):
            break
    for f in query_result:
        try:
            f.file_name = results[f.pk][0]
            f.file_url = reverse('get_file') + '?file=' + results[
                f.pk][1] + '/%s,%s' % (f.pk, f.file_name)
            f.file_path = results[f.pk][2]
            f.file_info = results[f.pk][3]
        except:
            pass
    return query_result


def recent_files_folders(request, roots, limit):
    if roots:
        files = ZornaFile.objects.filter(
            folder__in=roots).order_by('-time_updated')[:int(limit)]
        return get_files_from_query(request, files)
    else:
        return []

def get_allowed_folders(request, what='all'):

    roots = []
    if what == 'all' or what == 'personal':
        bpersonal = SiteOptions.objects.is_access_valid(
            request.user, 'zorna_personal_documents')
        if bpersonal:
            roots.extend(['U%s' % request.user.pk])
    if what == 'all' or what == 'shared':
        aof = get_allowed_shared_folders(
            request.user, ['writer', 'reader', 'manager'])
        roots.extend(['F%s' % f for f in aof])
        for f in aof:
            for d in ZornaFolder.objects.get(pk=f).get_descendants().exclude(inherit_permissions=False):
                roots.append('F%s' % d.pk)
    if what == 'all' or what == 'communities':
        aof = get_allowed_objects(
            request.user, Community, ['manage', 'member'])
        roots.extend(['C%s' % f for f in aof])

    return roots


def recent_files(request, what, limit):
    roots = get_allowed_folders(request, what)
    return recent_files_folders(request, roots, limit)



def get_folder_files(folder, limit=None):
    fullpath = get_upload_library() + '/%s' % folder

    fileList = {}
    files_id = []
    if os.path.isdir(fullpath):
        for f in os.listdir(fullpath):
            ff = os.path.join(fullpath, f)
            if os.path.isdir(ff):
                continue
            pk, fname = split_file_name(f)
            if pk is False:
                continue
            else:
                files_id.append(int(pk))

            statinfo = os.stat(ff)
            fileList[pk] = {'name': fname,
                            'realname': f,
                            'size': statinfo[stat.ST_SIZE],
                            'creation': datetime.fromtimestamp(statinfo[stat.ST_CTIME]),
                            'modification': datetime.fromtimestamp(statinfo[stat.ST_MTIME]),
                            'ext': os.path.splitext(f)[1][1:],
                            }

        files = ZornaFile.objects.filter(
            pk__in=files_id).order_by('-time_updated')
        if limit:
            files = files[:int(limit)]
        for f in files:
            f.file_name = fileList[str(f.pk)]['name']
            f.file_url = reverse(
                'get_file') + '?file=' + folder + '/%s,%s' % (f.pk, f.file_name)
            f.file_info = fileList[str(f.pk)]
        return files
    else:
        return []
