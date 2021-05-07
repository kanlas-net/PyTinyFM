from hashlib import sha512
from hashlib import pbkdf2_hmac
import base64
import os
import getpass
import config
import secrets


def check_cookie(req):
    username = req.cookies.get('sessionID')
    if username is not None:
        return auth(username, None)
    return False


def add_cookie(resp, username, password):
    if auth(username, password):
        resp.set_cookie('sessionID', gen_hash(username, with_salt=True), max_age=cookie_expiration)
        return resp
    return False


def delete_cookie(resp):
    resp.set_cookie('sessionID', '', expires=0)
    return resp


def auth(username, password):
    if password:
        if username == admin_user and gen_hash(password) == admin_pass:
            return True
        else:
            return False
    elif password is None:
        if username == gen_hash(admin_user, with_salt=True):
            return True
    return False


def basic_auth(header):
    if header is not None:
        props = header.split(' ')
        if props[0] == 'Basic':
            creds = base64.b64decode(props[1]).decode('UTF-8').split(':')
            if auth(creds[0], creds[1]):
                return True
    return False


def gen_hash(string, with_salt=False):
    if with_salt:
        return pbkdf2_hmac('sha512', string.encode('utf-8'), salt.encode('utf-8'), 1000).hex()
    return sha512(string.encode('utf-8')).hexdigest()


def get_published():
    return published


def add_public(path):
    if not is_public(path):
        reindex(path)
        published.add(path)
        save_published()
        return True
    return False


def remove_public(path):
    published.discard(path)
    save_published()


def is_public(path):
    while not path == '':
        if path in published:
            return True
        elif path.find('/') > -1:
            path = path[:path.rindex('/')]
        else:
            path = ''
    return False


def reindex(path):
    for item in published.copy():
        if path in item and path != item:
            published.remove(item)


def check_rights(req, public=False):
    if check_cookie(req) or basic_auth(req.headers.get('Authorization')):
        return True
    if public:
        if req.args.get('path'):
            path = req.args.get('path')
        else:
            path = req.path
        if is_public(path):
            return True
    return False


def save_published():
    with open('published.list', 'w') as file:
        for element in published:
            file.write(element + "\n")


def secure_path(string):
    for char in bad_chars:
        string = string.replace(char, '')
    if upload_dir in os.path.abspath(string) and upload_dir != os.path.abspath(string).rstrip('..'):
        return string
    return None


if __name__ == '__main__':
    passw = gen_hash(getpass.getpass('Enter new admin password: '))
    print('----------------------\nSave this hash to ADMIN_PASS variable in config.py\n>>> ' + passw)
    print('----------------------\nSave this salt to SALT variable in config.py\n>>> ' + secrets.token_hex(8))
else:
    if os.path.exists('published.list'):
        with open('published.list', 'r') as file:
            published = set(file.read().splitlines())
    else:
        published = set()
    admin_user = config.ADMIN_USER
    admin_pass = config.ADMIN_PASS
    salt = config.SALT
    cookie_expiration = config.COOKIE_EXPIRATION
    bad_chars = ['^', ':', '\"', '\'', ';', '<', '>', '|', '#', '?', '$']
    upload_dir = os.path.dirname(os.path.abspath(__file__)) + os.sep + config.UPLOAD_DIR
