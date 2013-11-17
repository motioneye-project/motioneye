
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
import os.path
import StringIO
import subprocess

from PIL import Image

import config
import utils


_PICTURE_EXTS = ['.jpg']
_MOVIE_EXTS = ['.avi', '.mp4']


def _list_media_files(dir, exts, prefix=None):
    full_paths = []
    
    if prefix is not None:
        if prefix == 'ungrouped':
            prefix = ''
        
        root = os.path.join(dir, prefix)
        for name in os.listdir(root):
            if name == 'lastsnap.jpg': # ignore the lastsnap.jpg file
                continue
                
            full_path = os.path.join(root, name)
            if not os.path.isfile(full_path):
                continue
             
            full_path_lower = full_path.lower()
            if not [e for e in exts if full_path_lower.endswith(e)]:
                continue
            
            full_paths.append(full_path)
    
    else:    
        for root, dirs, files in os.walk(dir):  # @UnusedVariable
            for name in files:
                if name == 'lastsnap.jpg': # ignore the lastsnap.jpg file
                    continue
                
                full_path = os.path.join(root, name)
                if not os.path.isfile(full_path):
                    continue
                 
                full_path_lower = full_path.lower()
                if not [e for e in exts if full_path_lower.endswith(e)]:
                    continue
                
                full_paths.append(full_path)
    
    return full_paths


def _remove_older_files(dir, moment, exts):
    for full_path in _list_media_files(dir, exts):
        # TODO files listed here may not belong to the given camera
        
        file_moment = datetime.datetime.fromtimestamp(os.path.getmtime(full_path))
        if file_moment < moment:
            logging.debug('removing file %(path)s...' % {
                    'path': full_path})
            
            os.remove(full_path)


def cleanup_media(media_type):
    logging.debug('cleaning up %(media_type)ss...' % {'media_type': media_type})
    
    if media_type == 'picture':
        exts = _PICTURE_EXTS
        
    elif media_type == 'movie':
        exts = _MOVIE_EXTS
        
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
    
    logging.debug('creating movie preview for %(path)s with an offset of %(offs)s seconds ...' % {
            'path': full_path, 'offs': offs})

    cmd = 'ffmpeg -i "%(path)s" -f mjpeg -vframes 1 -ss %(offs)s -y %(path)s.thumb' % {
            'path': full_path, 'offs': offs}
    
    try:
        subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
    
    except subprocess.CalledProcessError as e:
        logging.error('failed to create movie preview for %(path)s: %(msg)s' % {
                'path': full_path, 'msg': unicode(e)})
        
        return None
    
    return full_path + '.thumb'


def make_next_movie_preview():
    logging.debug('making preview for the next movie...')
    
    for camera_id in config.get_camera_ids():
        camera_config = config.get_camera(camera_id)
        if camera_config.get('@proto') != 'v4l2':
            continue
        
        target_dir = camera_config['target_dir']
        
        for full_path in _list_media_files(target_dir, _MOVIE_EXTS):
            # TODO files listed here may not belong to the given camera
        
            if os.path.exists(full_path + '.thumb'):
                continue
            
            logging.debug('found a movie without preview: %(path)s' % {
                    'path': full_path})
                
            make_movie_preview(camera_config, full_path)
            
            break
        
        else:
            logging.debug('all movies have preview')
            

def list_media(camera_config, media_type, prefix=None, stat=False):
    target_dir = camera_config.get('target_dir')

    if media_type == 'picture':
        exts = _PICTURE_EXTS
        
    elif media_type == 'movie':
        exts = _MOVIE_EXTS
        
    full_paths = _list_media_files(target_dir, exts=exts, prefix=prefix)
    media_files = []
    
    for p in full_paths:
        path = p[len(target_dir):]
        if not path.startswith('/'):
            path = '/' + path

        timestamp = None
        size = None
        
        if stat:
            try:
                stat = os.stat(p)
             
            except Exception as e:
                logging.error('stat call failed for file %(path)s: %(msg)s' % {
                        'path': path, 'msg': unicode(e)})
                 
                continue
 
            timestamp = stat.st_mtime
            size = stat.st_size
        
        media_files.append({
            'path': path,
            'momentStr': timestamp and utils.pretty_date_time(datetime.datetime.fromtimestamp(timestamp)),
            'sizeStr': size and utils.pretty_size(size),
            'timestamp': timestamp
        })
    
    # TODO files listed here may not belong to the given camera
    
    return media_files


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
