
# Copyright (c) 2013 Calin Crisan
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>. 

import datetime
import errno
import fcntl
import functools
import hashlib
import logging
import multiprocessing
import os.path
import re
import stat
import StringIO
import subprocess
import time
import tornado
import zipfile

from PIL import Image
from tornado import ioloop

import config
import settings
import utils


_PICTURE_EXTS = ['.jpg']
_MOVIE_EXTS = ['.avi', '.mp4']

# a cache list of paths to movies without preview
_previewless_movie_files = []

# a cache of prepared files (whose preparing time is significant)
_prepared_files = {}

_timelapse_process = None
_timelapse_data = None


def _list_media_files(dir, exts, prefix=None):
    media_files = []
    
    if prefix is not None:
        if prefix == 'ungrouped':
            prefix = ''
        
        root = os.path.join(dir, prefix)
        for name in os.listdir(root):
            if name == 'lastsnap.jpg' or name.startswith('.'): # ignore the lastsnap.jpg and hidden files
                continue
                
            full_path = os.path.join(root, name)
            try:
                st = os.stat(full_path)
            
            except Exception as e:
                logging.error('stat failed: ' + unicode(e))
                continue
                
            if not stat.S_ISREG(st.st_mode): # not a regular file
                continue

            full_path_lower = full_path.lower()
            if not [e for e in exts if full_path_lower.endswith(e)]:
                continue
            
            media_files.append((full_path, st))

    else:    
        for root, dirs, files in os.walk(dir):  # @UnusedVariable # TODO os.walk can be rewritten to return stat info
            for name in files:
                if name == 'lastsnap.jpg' or name.startswith('.'): # ignore the lastsnap.jpg and hidden files
                    continue
                
                full_path = os.path.join(root, name)
                try:
                    st = os.stat(full_path)
                
                except Exception as e:
                    logging.error('stat failed: ' + unicode(e))
                    continue
                
                if not stat.S_ISREG(st.st_mode): # not a regular file
                    continue
                 
                full_path_lower = full_path.lower()
                if not [e for e in exts if full_path_lower.endswith(e)]:
                    continue
                
                media_files.append((full_path, st))

    return media_files


def _remove_older_files(dir, moment, exts):
    for (full_path, st) in _list_media_files(dir, exts):
        file_moment = datetime.datetime.fromtimestamp(st.st_mtime)
        if file_moment < moment:
            logging.debug('removing file %(path)s...' % {'path': full_path})
            
            # remove the file itself
            try:
                os.remove(full_path)
            
            except OSError as e:
                if e.errno == errno.ENOENT:
                    pass # the file might have been removed in the meantime
                
                else:
                    logging.error('failed to remove %s: %s' % (full_path, e))

            # remove the parent directories if empty or contain only thumb files
            dir_path = os.path.dirname(full_path)
            if not os.path.exists(dir_path):
                continue
            
            listing = os.listdir(dir_path)
            thumbs = [l for l in listing if l.endswith('.thumb')]
            
            if len(listing) == len(thumbs): # only thumbs
                for p in thumbs:
                    try:
                        os.remove(os.path.join(dir_path, p))
                    
                    except:
                        logging.error('failed to remove %s: %s' % (p, e))

            if not listing or len(listing) == len(thumbs):
                # this will possibly cause following paths that are in the media files for loop
                # to be removed in advance; the os.remove call will raise ENOENT which is silently ignored 
                logging.debug('removing empty directory %(path)s...' % {'path': dir_path})
                try:
                    os.removedirs(dir_path)
                
                except:
                    logging.error('failed to remove %s: %s' % (dir_path, e))


def find_ffmpeg():
    try:
        return subprocess.check_output('which ffmpeg', stderr=open('/dev/null'), shell=True).strip()
    
    except subprocess.CalledProcessError: # not found
        return None


def cleanup_media(media_type):
    logging.debug('cleaning up %(media_type)ss...' % {'media_type': media_type})
    
    if media_type == 'picture':
        exts = _PICTURE_EXTS
        
    elif media_type == 'movie':
        exts = _MOVIE_EXTS + ['.thumb']
        
    for camera_id in config.get_camera_ids():
        camera_config = config.get_camera(camera_id)
        if not utils.local_motion_camera(camera_config):
            continue
        
        preserve_media = camera_config.get('@preserve_%(media_type)ss' % {'media_type': media_type}, 0)
        if preserve_media == 0:
            return # preserve forever
        
        still_images_enabled = bool(
                ((camera_config['emulate_motion'] or camera_config['output_pictures']) and camera_config['picture_filename']) or
                (camera_config['snapshot_interval'] and camera_config['snapshot_filename']))
        
        movies_enabled = camera_config['ffmpeg_output_movies']

        if media_type == 'picture' and not still_images_enabled:
            continue # only cleanup pictures for cameras with still images enabled
        
        elif media_type == 'movie' and not movies_enabled:
            continue # only cleanup movies for cameras with movies enabled

        preserve_moment = datetime.datetime.now() - datetime.timedelta(days=preserve_media)

        target_dir = camera_config.get('target_dir')
        if os.path.exists(target_dir):
            # create a sentinel file to make sure the target dir is never removed
            open(os.path.join(target_dir, '.keep'), 'w').close()

        _remove_older_files(target_dir, preserve_moment, exts=exts)


def make_movie_preview(camera_config, full_path):
    framerate = camera_config['framerate']
    pre_capture = camera_config['pre_capture']
    offs = pre_capture / framerate
    offs = max(4, offs * 2)
    
    logging.debug('creating movie preview for %(path)s with an offset of %(offs)s seconds...' % {
            'path': full_path, 'offs': offs})

    cmd = 'ffmpeg -i "%(path)s" -f mjpeg -vframes 1 -ss %(offs)s -y %(path)s.thumb'
    
    try:
        subprocess.check_output(cmd % {'path': full_path, 'offs': offs}, shell=True, stderr=subprocess.STDOUT)
    
    except subprocess.CalledProcessError as e:
        logging.error('failed to create movie preview for %(path)s: %(msg)s' % {
                'path': full_path, 'msg': unicode(e)})
        
        return None
    
    try:
        st = os.stat(full_path + '.thumb')
    
    except os.error:
        logging.error('failed to create movie preview for %(path)s: ffmpeg error' % {
                'path': full_path})

        return None

    if st.st_size == 0:
        logging.debug('movie is too short, grabbing first frame from %(path)s...' % {'path': full_path})
        
        # try again, this time grabbing the very first frame
        try:
            subprocess.check_output(cmd % {'path': full_path, 'offs': 0}, shell=True, stderr=subprocess.STDOUT)
        
        except subprocess.CalledProcessError as e:
            logging.error('failed to create movie preview for %(path)s: %(msg)s' % {
                    'path': full_path, 'msg': unicode(e)})
            
            return None
    
    return full_path + '.thumb'


def make_next_movie_preview():
    global _previewless_movie_files
    
    logging.debug('making preview for the next movie...')
    
    if _previewless_movie_files:
        (camera_config, path) = _previewless_movie_files.pop(0)
        
        make_movie_preview(camera_config, path)
    
    else:
        logging.debug('gathering movies without preview...')
        
        count = 0
        for camera_id in config.get_camera_ids():
            camera_config = config.get_camera(camera_id)
            if not utils.local_motion_camera(camera_config):
                continue
            
            target_dir = camera_config['target_dir']
            
            for (full_path, st) in _list_media_files(target_dir, _MOVIE_EXTS):  # @UnusedVariable
                if os.path.exists(full_path + '.thumb'):
                    continue
                
                logging.debug('found a movie without preview: %(path)s' % {
                        'path': full_path})
                
                _previewless_movie_files.append((camera_config, full_path))
                count += 1
        
        logging.debug('found %(count)d movies without preview' % {'count': count})    
        
        if count:
            make_next_movie_preview()


def list_media(camera_config, media_type, callback, prefix=None):
    target_dir = camera_config.get('target_dir')

    if media_type == 'picture':
        exts = _PICTURE_EXTS
        
    elif media_type == 'movie':
        exts = _MOVIE_EXTS

    # create a subprocess to retrieve media files
    def do_list_media(pipe):
        mf = _list_media_files(target_dir, exts=exts, prefix=prefix)
        for (p, st) in mf:
            path = p[len(target_dir):]
            if not path.startswith('/'):
                path = '/' + path
    
            timestamp = st.st_mtime
            size = st.st_size
            
            pipe.send({
                'path': path,
                'momentStr': utils.pretty_date_time(datetime.datetime.fromtimestamp(timestamp)),
                'momentStrShort': utils.pretty_date_time(datetime.datetime.fromtimestamp(timestamp), short=True),
                'sizeStr': utils.pretty_size(size),
                'timestamp': timestamp
            })
        
        pipe.close()
    
    logging.debug('starting media listing process...')
    
    (parent_pipe, child_pipe) = multiprocessing.Pipe(duplex=False)
    process = multiprocessing.Process(target=do_list_media, args=(child_pipe, ))
    process.start()
    
    # poll the subprocess to see when it has finished
    started = datetime.datetime.now()
    media_list = []
    
    def read_media_list():
        while parent_pipe.poll():
            media_list.append(parent_pipe.recv())
    
    def poll_process():
        ioloop = tornado.ioloop.IOLoop.instance()
        if process.is_alive(): # not finished yet
            now = datetime.datetime.now()
            delta = now - started
            if delta.seconds < 120:
                ioloop.add_timeout(datetime.timedelta(seconds=0.5), poll_process)
                read_media_list()
            
            else: # process did not finish within 2 minutes
                logging.error('timeout waiting for the media listing process to finish')
                
                callback(None)

        else: # finished
            read_media_list()
            logging.debug('media listing process has returned %(count)s files' % {'count': len(media_list)})
            callback(media_list)
    
    poll_process()


def get_media_content(camera_config, path, media_type):
    target_dir = camera_config.get('target_dir')

    full_path = os.path.join(target_dir, path)
    
    try:
        with open(full_path) as f:
            return f.read()
    
    except Exception as e:
        logging.error('failed to read file %(path)s: %(msg)s' % {
                'path': full_path, 'msg': unicode(e)})
        
        return None


def get_zipped_content(camera_config, media_type, group, callback):
    target_dir = camera_config.get('target_dir')

    if media_type == 'picture':
        exts = _PICTURE_EXTS
        
    elif media_type == 'movie':
        exts = _MOVIE_EXTS
        
    working = multiprocessing.Value('b')
    working.value = True

    # create a subprocess to add files to zip
    def do_zip(pipe):
        mf = _list_media_files(target_dir, exts=exts, prefix=group)
        paths = []
        for (p, st) in mf:  # @UnusedVariable
            path = p[len(target_dir):]
            if path.startswith('/'):
                path = path[1:]

            paths.append(path)
            
        zip_filename = os.path.join(settings.MEDIA_PATH, '.zip-%s' % int(time.time()))
        logging.debug('adding %d files to zip file "%s"' % (len(paths), zip_filename))

        try:
            with zipfile.ZipFile(zip_filename, mode='w') as f:
                for path in paths:
                    full_path = os.path.join(target_dir, path)
                    f.write(full_path, path)

        except Exception as e:
            logging.error('failed to create zip file "%s": %s' % (zip_filename, e))

            working.value = False
            pipe.close()
            return

        logging.debug('reading zip file "%s" into memory' % zip_filename)

        try:
            with open(zip_filename, mode='r') as f:
                data = f.read()

            working.value = False
            pipe.send(data)
            logging.debug('zip data ready')

        except Exception as e:
            logging.error('failed to read zip file "%s": %s' % (zip_filename, e))
            working.value = False

        finally:
            os.remove(zip_filename)
            pipe.close()

    logging.debug('starting zip process...')

    (parent_pipe, child_pipe) = multiprocessing.Pipe(duplex=False)
    process = multiprocessing.Process(target=do_zip, args=(child_pipe, ))
    process.start()

    # poll the subprocess to see when it has finished
    started = datetime.datetime.now()

    def poll_process():
        ioloop = tornado.ioloop.IOLoop.instance()
        if working.value:
            now = datetime.datetime.now()
            delta = now - started
            if delta.seconds < settings.ZIP_TIMEOUT:
                ioloop.add_timeout(datetime.timedelta(seconds=0.5), poll_process)

            else: # process did not finish within 2 minutes
                logging.error('timeout waiting for the zip process to finish')

                callback(None)

        else: # finished
            try:
                data = parent_pipe.recv()
                logging.debug('zip process has returned %d bytes' % len(data))
                
            except:
                data = None
            
            callback(data)

    poll_process()


def make_timelapse_movie(camera_config, framerate, interval, group):
    global _timelapse_process
    global _timelapse_data
    
    target_dir = camera_config.get('target_dir')
    
    # create a subprocess to retrieve media files
    def do_list_media(pipe):
        mf = _list_media_files(target_dir, exts=_PICTURE_EXTS, prefix=group)
        for (p, st) in mf:
            timestamp = st.st_mtime

            pipe.send({
                'path': p,
                'timestamp': timestamp
            })

        pipe.close()

    logging.debug('starting media listing process...')
    
    (parent_pipe, child_pipe) = multiprocessing.Pipe(duplex=False)
    _timelapse_process = multiprocessing.Process(target=do_list_media, args=(child_pipe, ))
    _timelapse_process.progress = 0
    _timelapse_process.start()
    _timelapse_data = None

    started = [datetime.datetime.now()]
    media_list = []
    
    tmp_filename = os.path.join(settings.MEDIA_PATH, '.%s.avi' % int(time.time()))

    def read_media_list():
        while parent_pipe.poll():
            media_list.append(parent_pipe.recv())
        
    def poll_media_list_process():
        ioloop = tornado.ioloop.IOLoop.instance()
        if _timelapse_process.is_alive(): # not finished yet
            now = datetime.datetime.now()
            delta = now - started[0]
            if delta.seconds < 300: # the subprocess has 5 minutes to complete its job
                ioloop.add_timeout(datetime.timedelta(seconds=0.5), poll_media_list_process)
                read_media_list()

            else: # process did not finish within 2 minutes
                logging.error('timeout waiting for the media listing process to finish')
                
                _timelapse_process.progress = -1

        else: # finished
            read_media_list()
            logging.debug('media listing process has returned %(count)s files' % {'count': len(media_list)})
            
            if not media_list:
                _timelapse_process.progress = -1
                
                return

            pictures = select_pictures(media_list)
            make_movie(pictures)

    def select_pictures(media_list):
        media_list.sort(key=lambda e: e['timestamp'])
        start = media_list[0]['timestamp']
        slices = {}
        max_idx = 0
        for m in media_list:
            offs = m['timestamp'] - start
            pos = float(offs) / interval - 0.5
            idx = int(round(pos))
            max_idx = idx
            m['delta'] = abs(pos - idx)
            slices.setdefault(idx, []).append(m)

        selected = []
        for i in xrange(max_idx + 1):
            slice = slices.get(i)
            if not slice:
                continue

            selected.append(min(slice, key=lambda m: m['delta']))

        logging.debug('selected %d/%d media files' % (len(selected), len(media_list)))
        
        return selected

    def make_movie(pictures):
        global _timelapse_process

        cmd =  'rm -f %(tmp_filename)s;'
        cmd += 'cat %(jpegs)s | ffmpeg -framerate %(framerate)s -f image2pipe -vcodec mjpeg -i - -vcodec mpeg4 -b:v %(bitrate)s -qscale:v 0.1 -f avi %(tmp_filename)s'

        bitrate = 9999999

        cmd = cmd % {
            'tmp_filename': tmp_filename,
            'jpegs': ' '.join((('"' + p['path'] + '"') for p in pictures)),
            'framerate': framerate,
            'bitrate': bitrate
        }
        
        logging.debug('executing "%s"' % cmd)
        
        _timelapse_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        _timelapse_process.progress = 0.01 # 1%
        
        # make subprocess stdout pipe non-blocking
        fd = _timelapse_process.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        poll_movie_process(pictures)

    def poll_movie_process(pictures):
        global _timelapse_process
        global _timelapse_data
        
        ioloop = tornado.ioloop.IOLoop.instance()
        if _timelapse_process.poll() is None: # not finished yet
            ioloop.add_timeout(datetime.timedelta(seconds=0.5), functools.partial(poll_movie_process, pictures))

            try:
                output = _timelapse_process.stdout.read()
            
            except IOError as e:
                if e.errno == errno.EAGAIN:
                    output = ''
                
                else:
                    raise
                
            frame_index = re.findall('frame=\s*(\d+)', output)
            try:
                frame_index = int(frame_index[-1])
            
            except (IndexError, ValueError):
                return

            _timelapse_process.progress = max(0.01, float(frame_index) / len(pictures))
            
            logging.debug('timelapse progress: %s' % int(100 * _timelapse_process.progress))

        else: # finished
            exit_code = _timelapse_process.poll()
            _timelapse_process = None
            
            if exit_code != 0:
                logging.error('ffmpeg process failed')
                _timelapse_data = None

                try:
                    os.remove(tmp_filename)

                except:
                    pass

            else:
                logging.debug('reading timelapse movie file "%s" into memory' % tmp_filename)
    
                try:
                    with open(tmp_filename, mode='r') as f:
                        _timelapse_data = f.read()
    
                    logging.debug('timelapse movie process has returned %d bytes' % len(_timelapse_data))
    
                except Exception as e:
                    logging.error('failed to read timelapse movie file "%s": %s' % (tmp_filename, e))
    
                finally:
                    try:
                        os.remove(tmp_filename)

                    except:
                        pass

    poll_media_list_process()


def check_timelapse_movie():
    if _timelapse_process:
        if ((hasattr(_timelapse_process, 'poll') and _timelapse_process.poll() is None) or
            (hasattr(_timelapse_process, 'is_alive') and _timelapse_process.is_alive())):
        
            return {'progress': _timelapse_process.progress, 'data': None}
        
        else:
            return {'progress': _timelapse_process.progress, 'data': _timelapse_data}

    else:
        return {'progress': -1, 'data': _timelapse_data}


def get_media_preview(camera_config, path, media_type, width, height):
    target_dir = camera_config.get('target_dir')
    full_path = os.path.join(target_dir, path)
    
    if media_type == 'movie':
        if not os.path.exists(full_path + '.thumb'):
            if not make_movie_preview(camera_config, full_path):
                return None
        
        full_path += '.thumb'
    
    try:
        with open(full_path) as f:
            content = f.read()
    
    except Exception as e:
        logging.error('failed to read file %(path)s: %(msg)s' % {
                'path': full_path, 'msg': unicode(e)})
        
        return None
    
    if width is height is None:
        return content
    
    sio = StringIO.StringIO(content)
    image = Image.open(sio)
    width = width and int(width) or image.size[0]
    height = height and int(height) or image.size[1]
    
    image.thumbnail((width, height), Image.LINEAR)

    sio = StringIO.StringIO()
    image.save(sio, format='JPEG')

    return sio.getvalue()


def del_media_content(camera_config, path, media_type):
    target_dir = camera_config.get('target_dir')

    full_path = os.path.join(target_dir, path)
    
    try:
        # remove the file itself
        os.remove(full_path)

        # remove the parent directories if empty or contains only thumb files
        dir_path = os.path.dirname(full_path)
        listing = os.listdir(dir_path)
        thumbs = [l for l in listing if l.endswith('.thumb')]
        
        if len(listing) == len(thumbs): # only thumbs
            for p in thumbs:
                os.remove(os.path.join(dir_path, p))

        if not listing or len(listing) == len(thumbs):
            logging.debug('removing empty directory %(path)s...' % {'path': dir_path})
            os.removedirs(dir_path)
    
    except Exception as e:
        logging.error('failed to remove file %(path)s: %(msg)s' % {
                'path': full_path, 'msg': unicode(e)})
        
        raise


def del_media_group(camera_config, group, media_type):
    if media_type == 'picture':
        exts = _PICTURE_EXTS
        
    elif media_type == 'movie':
        exts = _MOVIE_EXTS
        
    target_dir = camera_config.get('target_dir')
    full_path = os.path.join(target_dir, group)

    mf = _list_media_files(target_dir, exts=exts, prefix=group)
    for (path, st) in mf:  # @UnusedVariable
        try:
            os.remove(path)
    
        except Exception as e:
            logging.error('failed to remove file %(path)s: %(msg)s' % {
                    'path': full_path, 'msg': unicode(e)})

            raise

    # remove the group directory if empty or contains only thumb files
    listing = os.listdir(full_path)
    thumbs = [l for l in listing if l.endswith('.thumb')]

    if len(listing) == len(thumbs): # only thumbs
        for p in thumbs:
            os.remove(os.path.join(full_path, p))

    if not listing or len(listing) == len(thumbs):
        logging.debug('removing empty directory %(path)s...' % {'path': full_path})
        os.removedirs(full_path)


def get_current_picture(camera_config, width, height):
    import mjpgclient

    jpg = mjpgclient.get_jpg(camera_config['@id'])
    
    if jpg is None:
        return None
    
    if width is height is None:
        return jpg # no server-side resize needed

    sio = StringIO.StringIO(jpg)
    image = Image.open(sio)
    
    width = width and int(width) or image.size[0]
    height = height and int(height) or image.size[1]
    
    webcam_resolution = camera_config['@webcam_resolution']
    max_width = image.size[0] * webcam_resolution / 100
    max_height = image.size[1] * webcam_resolution / 100
    
    width = min(max_width, width)
    height = min(max_height, height)
    
    if width >= image.size[0] and height >= image.size[1]:
        return jpg # no enlarging of the picture on the server side
    
    image.thumbnail((width, height), Image.CUBIC)

    sio = StringIO.StringIO()
    image.save(sio, format='JPEG')

    return sio.getvalue()


def get_prepared_cache(key):
    return _prepared_files.pop(key, None)


def set_prepared_cache(data):
    key = hashlib.sha1(str(time.time())).hexdigest()

    if key in _prepared_files:
        logging.warn('key "%s" already present in prepared cache' % key)
        
    _prepared_files[key] = data
    
    def clear():
        if _prepared_files.pop(key, None) is not None:
            logging.warn('key "%s" was still present in the prepared cache, removed' % key)

    timeout = 3600 # the user has 1 hour to download the file after creation
    ioloop.IOLoop.instance().add_timeout(datetime.timedelta(seconds=timeout), clear)

    return key
