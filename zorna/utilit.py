import os
try:
    from PIL import Image
except ImportError:
    import Image
from django.conf import settings


def get_upload_path():
    return settings.ZORNA_UPLOAD_PATH


def get_upload_library():
    path = u"%s/%s" % (settings.ZORNA_UPLOAD_PATH, "library")
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def get_upload_communities():
    path = u"%s/%s" % (get_upload_library(), "communities")
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def get_upload_user(user):
    path = u"%s/%s" % (get_upload_library(), u"U%s" % user.pk)
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def get_upload_avatars():
    return get_upload_path()


def get_upload_menus():
    path = u"%s/%s" % (get_upload_path(), "menus")
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def get_upload_articles():
    path = u"%s/%s" % (settings.ZORNA_UPLOAD_PATH, "articles")
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def get_upload_articles_images():
    path = u"%s/%s" % (get_upload_articles(), "images")
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def get_upload_articles_files():
    path = u"%s/%s" % (get_upload_articles(), "files")
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def get_upload_notes_attachments():
    path = u"%s/%s" % (settings.ZORNA_UPLOAD_PATH, "notes")
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def get_upload_forms_attachments():
    path = u"%s/%s" % (settings.ZORNA_UPLOAD_PATH, "forms")
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def get_upload_plugins():
    path = u"%s/%s" % (settings.ZORNA_UPLOAD_PATH, "plugins")
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def resize_image(path, size=None):
    """
    This method resize an image
    based on the parameter ``path``

    :param path: The image's path to resize
    :param size: The size as a tuple (W, H)

    :return: The thumbnail

    """
    def scale(max_x, pair):
        x, y = pair
        new_y = (float(max_x) / x) * y
        return (int(max_x), int(new_y))

    csize = size
    if (size.lower().endswith('h')):
        mode = 'h'
        size = size[:-1]
        max_size = int(size.strip())
    elif (size.lower().endswith('w')):
        mode = 'w'
        size = size[:-1]
        max_size = int(size.strip())
    else:
        mode = 'both'

    # defining the filename and the miniature filename

    # FIXME: Bug seen at: http://demo.zornaproject.com/account/user/settings/
    # FIXME: using "demo" as login/password
    # FIXME: the filename may not exist in some cases
    # FIXME: no check at all is done the filename !
    # FIXME: If the filename does not exists,
    # FIXME: a default thumbnail should be taken as default,
    # FIXME: or something else...
    filename = (path
                if path and os.path.exists(path)
                else os.path.join(settings.MEDIA_ROOT,
                                  'images', 'icon_no_photo.png'))

    filehead, filetail = os.path.split(path)
    basename, format = os.path.splitext(filetail)
    miniature = basename + '_' + csize + format
    miniature_filename = os.path.join(filehead, miniature)
    filehead, filetail = os.path.split(filetail)
    miniature_url = filehead + '/' + miniature
    if (os.path.exists(miniature_filename) and
            os.path.getmtime(filename) > os.path.getmtime(miniature_filename)):
        os.unlink(miniature_filename)
    # if the image wasn't already resized, resize it
    if not os.path.exists(miniature_filename):
        # FIXME: Or a path existence condition,
        # FIXME: Or a try/except (IOError) statement ?
        image = Image.open(filename)
        image_x, image_y = image.size

        if mode == 'h':
            image_y, image_x = scale(max_size, (image_y, image_x))
        elif mode == 'w':
            image_x, image_y = scale(max_size, (image_x, image_y))
        elif mode == 'both':
            image_x, image_y = [int(x) for x in size.split('x')]
        else:
            raise Exception(
                "Thumbnail size must be in ##w, ##h, or ##x## format.")

        image.thumbnail([image_x, image_y], Image.ANTIALIAS)
        try:
            image.save(
                miniature_filename, image.format, quality=90, optimize=1)
        except:
            image.save(miniature_filename, image.format, quality=90)
    return miniature