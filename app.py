import os
import shutil
import urllib.parse
from flask import render_template, abort, send_file, request, redirect, make_response
from flask import Flask
from converter import convert_props, get_file_type, get_prefix, hash_dict
from presets import Filetype, Iconpack
from guardian import check_cookie, add_cookie, delete_cookie, get_published, add_public,\
    is_public, remove_public, check_rights, secure_path
import config
from functools import lru_cache


app = Flask(__name__)


@app.errorhandler(404)
def code404(message='Not found'):
    return render_template('error.html', message=str(message)), 404


@app.errorhandler(403)
def code403(message='Forbidden'):
    return render_template('error.html', message=str(message)), 403


@app.errorhandler(400)
def code400(message='Bad request'):
    return render_template('error.html', message=str(message)), 403


@app.route('/', defaults={'req_path': ''}, endpoint='index')
@app.route('/<path:req_path>')
def dir_listing(req_path):
    if check_rights(request, public=True):
        req_path = urllib.parse.unquote(req_path)
        if req_path == '':
            abs_path = upload_dir
        else:
            abs_path = form_path(req_path)
            if abs_path is None:
                return abort(403)
        if not os.path.exists(abs_path):
            return abort(404)
        if os.path.isfile(abs_path):
            return send_file(abs_path, as_attachment=True)
        dirs, files = discover_files(abs_path)
        if request.args.get('sort') == 'date':
            element = 1
        elif request.args.get('sort') == 'size':
            element = 2
        else:
            element = -1
        if request.args.get('reverse') == 'True':
            reverse = True
        else:
            reverse = False
        files = convert_props(sort_dict(files, reverse=reverse, element=element))
        dirs = convert_props(sort_dict(dirs, reverse=False if request.args.get('sort') == 'size' else reverse,
                                       element=-1 if element > 1 else element), size_index=-1)
        return render_template('browser.html', files=files, dirs=dirs, iconpack=Iconpack, reverse=not reverse,
                               public=get_published(), parent_is_public=is_public(request.path))
    return redirect(request.host_url + root + 'login')


@app.route('/upload', methods=['POST', 'GET'])
def upload_file():
    if check_rights(request):
        if request.method == 'POST':
            prefix = get_prefix(request.host_url + config.PREFIX.lstrip('/'), request.referrer)
            if prefix == '' and config.RESTRICT_UPLOAD_TO_ROOT:
                return abort(403, description='You should not upload files to root folder, '
                                              'please create subfolder to upload them')
            else:
                files = request.files.getlist('file')
                for file in files:
                    saving_path = secure_path(upload_dir + os.sep + prefix + file.filename)
                    if saving_path is None:
                        return abort(400)
                    file.save(saving_path)
                return redirect(request.referrer, code=302)
        else:
            return abort(400)
    return redirect(request.host_url + root + 'login')


@app.route('/create_dir', methods=['POST'])
def create_dir():
    if check_rights(request):
        print(request.referrer)
        prefix = get_prefix(request.host_url + config.PREFIX.lstrip('/'), request.referrer)
        dir_path = secure_path(upload_dir + os.sep + prefix + request.form['directory'])
        if dir_path is None:
            return abort(403)
        os.makedirs(dir_path)
        return redirect(request.referrer, code=302)
    return redirect(request.host_url + root + 'login')


@app.route('/raw', methods=['GET'], endpoint='raw')
def raw_file():
    if check_rights(request, public=True):
        abs_path = form_path(request.args.get('path'))
        if abs_path is None:
            return abort(403)
        with open(abs_path) as f:
            content = f.read().replace('\r\n', '\n')
        return render_template('rawfile.html', file_content=content, filename=abs_path.split(os.sep)[-1])
    return redirect(request.host_url + root + 'login')


@app.route('/delete', methods=['GET'])
def delete():
    if check_rights(request):
        abs_path = form_path(request.args.get('path'))
        if abs_path is None:
            return abort(403, description='Wrong path')
        if os.path.isdir(abs_path):
            shutil.rmtree(abs_path)
        else:
            os.remove(abs_path)
        remove_public(request.args.get('path'))
        return redirect(request.referrer, code=302)
    return redirect(request.host_url + root + 'login')


@app.route('/move', methods=['GET', 'POST'], endpoint='move')
@app.route('/copy', methods=['GET', 'POST'], endpoint='copy')
def move_or_copy():
    if check_rights(request):
        if request.method == 'POST':
            new_abs_path = form_path(request.form['new_path'])
            old_abs_path = form_path(request.form['old_path'])
            if new_abs_path is None or old_abs_path is None:
                return abort(403, description='Wrong path')
            if not os.path.exists(new_abs_path):
                new_abs_root = os.sep.join(new_abs_path.split(os.sep)[:-1])
                if new_abs_root == upload_dir and config.RESTRICT_UPLOAD_TO_ROOT:
                    return abort(403, description='You should not move or copy files to root folder, '
                                                  'please create subfolder for them')
                if not os.path.exists(new_abs_root):
                    os.makedirs(new_abs_root)
                if request.path == '/move':
                    os.rename(old_abs_path, new_abs_path)
                    if is_public(request.form['old_path']):
                        remove_public(request.form['old_path'])
                        add_public(request.form['new_path'])
                elif request.path == '/copy':
                    if os.path.isdir(old_abs_path):
                        shutil.copytree(old_abs_path, new_abs_path)
                    else:
                        shutil.copy2(old_abs_path, new_abs_path)
                return redirect(request.form.get('home'), code=302)
            else:
                abort(403, description="This path already exists")
        else:
            return render_template('move&copy.html', home=request.referrer,
                                   path=request.args.get('path'), action=request.path.lstrip('/'))
    return redirect(request.host_url + root + 'login')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        response = make_response(redirect(request.host_url + root.strip('/'), code=302))
        if add_cookie(response, request.form.get('username'), request.form.get('password')):
            return response
        else:
            return render_template('login.html')
    else:
        if check_cookie(request):
            return redirect(request.host_url + root.strip('/'), code=302)
    return render_template('login.html')


@app.route('/logout', methods=['GET'])
def logout():
    response = make_response(redirect(request.host_url + root.strip('/'), code=302))
    delete_cookie(response)
    return response


@app.route('/share', methods=['GET'])
def share():
    if check_rights(request):
        if request.args.get('action') == 'share':
            if not add_public(request.args.get('path')):
                return abort(403, description='Parent folder already published')
        elif request.args.get('action') == 'unshare':
            remove_public(request.args.get('path'))
        return redirect(request.referrer, code=302)
    return redirect(request.host_url + root + 'login')


@app.route('/shares', methods=['GET'])
def shares():
    if check_rights(request):
        files = {}
        dirs = {}
        for item in get_published():
            abs_path = form_path(item)
            if abs_path is None:
                return abort(403)
            if os.path.isdir(abs_path):
                dirs[item.lstrip('/')] = Filetype.folder.value
            else:
                files[item.lstrip('/')] = get_file_type(abs_path).value
        return render_template('shares.html', public={** dirs, **files}, iconpack=Iconpack)
    return redirect(request.host_url + root + 'login')


@hash_dict  # Cache every folder * number of sorted props * number of sorting orders = LRU_CACHE_MAXSIZE * 3 * 2
@lru_cache(config.LRU_CACHE_MAXSIZE * 6)
def sort_dict(dictionary, element, reverse=False):
    if element < 0:
        sorted_tuples = sorted(dictionary.items(), reverse=reverse)
    else:
        sorted_tuples = sorted(dictionary.items(), key=lambda e: e[1][element], reverse=reverse)
    return {k: v for k, v in sorted_tuples}


def discover_files(abs_path):
    dirs = {}
    files = {}
    for entry in os.listdir(abs_path):
        item = abs_path + os.sep + entry
        if os.path.isdir(item):
            dirs[entry] = tuple([Filetype.folder.value, os.path.getmtime(item)])
        else:
            filetype = get_file_type(item)
            if filetype is not Filetype.text:
                files[entry] = tuple([filetype.value, os.path.getmtime(item), os.path.getsize(item), False])
            else:
                files[entry] = tuple([filetype.value, os.path.getmtime(item), os.path.getsize(item), True])
    return dirs, files


def form_path(path):
    sub_path = os.path.normpath(path.lstrip('/'))
    return secure_path(os.path.join(upload_dir, sub_path))


upload_dir = os.path.dirname(os.path.abspath(__file__)) + os.sep + config.UPLOAD_DIR
if not os.path.exists(upload_dir):
    os.mkdir(upload_dir)
for item in get_published().copy():
    if item is None or not os.path.exists(form_path(item)):
        remove_public(item)
root = config.PREFIX if config.PREFIX == '/' else config.PREFIX.lstrip('/') + '/'
if __name__ == '__main__':
    app.config['APPLICATION_ROOT'] = config.PREFIX
    app.run()
