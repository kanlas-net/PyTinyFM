from datetime import datetime
from presets import Filetype
from presets import Mimetypes
import mimetypes
import os
import urllib.parse
from functools import lru_cache, wraps
import config


def hash_dict(func):
    """Transform mutable dictionnary
    Into immutable
    Useful to be compatible with cache
    https://stackoverflow.com/a/44776960
    """
    class HDict(dict):
        def __hash__(self):
            return hash(frozenset(self.items()))

    @wraps(func)
    def wrapped(*args, **kwargs):
        args = tuple([HDict(arg) if isinstance(arg, dict) else arg for arg in args])
        kwargs = {k: HDict(v) if isinstance(v, dict) else v for k, v in kwargs.items()}
        return func(*args, **kwargs)
    return wrapped


def convert_unit(size):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    index = 0
    while size > 1024 and index < 4:
        index += 1
        size = size/1024.0
    return "%.*f%s" % (2, size, suffixes[index])


def convert_time(timestamp):
    return datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


@hash_dict
@lru_cache(config.LRU_CACHE_MAXSIZE)  # Cache every folder content
def convert_props(dictionary, time_index=1, size_index=2):
    for key, value in dictionary.items():
        i = 0
        temp = []
        for val in value:
            if i == time_index:
                val = convert_time(val)
            elif i == size_index:
                val = convert_unit(val)
            temp.append(val)
            i += 1
        dictionary[key] = tuple(temp)
    return dictionary


@lru_cache(config.LRU_CACHE_MAXSIZE * 10)  # Returns only string for one file so cache is bigger
def get_file_type(file_path):
    extension = os.path.splitext(file_path)[1].lstrip('.')
    for m in Mimetypes:
        if extension in m.value:
            return Filetype[str(m)]
    mime = mimetypes.guess_type(file_path)[0]
    if mime is not None:
        mime = mime.split('/')
        for f in Filetype:
            if mime[0] in str(f):
                return Filetype[str(f)]
    else:
        text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
        file = open(file_path, 'rb')
        try:
            chunk = file.read(1024)
            if chunk.translate(None, text_chars):
                return Filetype.binary
        finally:
            file.close()
    return Filetype.text


def get_prefix(host_url, referrer_url):
    prefix = ''
    if '?' in referrer_url:
        referrer_url = referrer_url[:referrer_url.index('?')]
    if not referrer_url == host_url:
        for entry in referrer_url.split(host_url, 1)[1].split('/'):
            if entry:
                prefix = prefix + entry + os.sep
    return urllib.parse.unquote(prefix)
