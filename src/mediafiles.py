
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
import logging
import multiprocessing
import os.path
import stat
import StringIO
import subprocess
import tornado

from PIL import Image

import config
import mjpgclient
import settings
import utils


_PICTURE_EXTS = ['.jpg']
_MOVIE_EXTS = ['.avi', '.mp4']

# a dictionary indexed by camera_id containing
# tuples of (moment, sequence, width, content)
_current_pictures_cache = {}

# a cache list of paths to movies without preview
_previewless_movie_files = []


def _list_media_files(dir, exts, prefix=None):
    media_files = []
    
    if prefix is not None:
        if prefix == 'ungrouped':
            prefix = ''
        
        root = os.path.join(dir, prefix)
        for name in os.listdir(root):
            if name == 'lastsnap.jpg': # ignore the lastsnap.jpg file
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
                if name == 'lastsnap.jpg': # ignore the lastsnap.jpg file
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
            
            os.remove(full_path)
            dir_path = os.path.dirname(full_path)
            if not os.listdir(dir_path):
                logging.debug('removing directory %(path)s...' % {'path': dir_path})
                os.removedirs(dir_path)


def find_ffmpeg():
    try:
        return subprocess.check_output('which ffmpeg', shell=True).strip()
    
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
        if camera_config.get('@proto') != 'v4l2':
            continue
        
        preserve_media = camera_config.get('@preserve_%(media_type)ss' % {'media_type': media_type}, 0)
        if preserve_media == 0:
            return # preserve forever
        
        preserve_moment = datetime.datetime.now() - datetime.timedelta(days=preserve_media)
            
        target_dir = camera_config.get('target_dir')
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
            if camera_config.get('@proto') != 'v4l2':
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
                ioloop.add_timeout(datetime.timedelta(seconds=0.1), poll_process)
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


def get_current_picture(camera_config, width, height):
    jpg = mjpgclient.get_jpg(camera_config['@id'])
    
    if jpg is None:
        return None
    
    if width is height is None:
        return jpg

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


def set_picture_cache(camera_id, sequence, width, content):
    global _current_pictures_cache
    
    if not content:
        return
    
    cache = _current_pictures_cache.setdefault(camera_id, [])
    
    if len(cache) >= settings.PICTURE_CACHE_SIZE:
        cache.pop(0) # drop the first item
    
    cache.append((datetime.datetime.utcnow(), sequence, width, content))


def get_picture_cache(camera_id, sequence, width):
    global _current_pictures_cache
    
    cache = _current_pictures_cache.setdefault(camera_id, [])
    now = datetime.datetime.utcnow()

    for (moment, seq, w, content) in cache:
        delta = now - moment
        if delta.days * 86400 + delta.seconds > settings.PICTURE_CACHE_LIFETIME:
            continue
        
        if (seq >= sequence) and ((width is w is None) or (width >= w)):
            return content
        
    return None
