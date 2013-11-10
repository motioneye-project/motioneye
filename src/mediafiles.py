
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

import config
import utils


_PICTURE_EXTS = ['.jpg']
_MOVIE_EXTS = ['.avi', '.mp4']


def _list_media_files(dir, exts):
    full_paths = []
    for root, dirs, files in os.walk(dir):  # @UnusedVariable
        for name in files:
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


def cleanup_pictures():
    logging.debug('cleaning up pictures...')
    
    for camera_id in config.get_camera_ids():
        camera_config = config.get_camera(camera_id)
        if camera_config.get('@proto') != 'v4l2':
            continue
        
        preserve_pictures = camera_config.get('@preserve_pictures')
        if preserve_pictures == 0:
            return # preserve forever
        
        preserve_moment = datetime.datetime.now() - datetime.timedelta(days=preserve_pictures)
            
        target_dir = camera_config.get('target_dir')
        _remove_older_files(target_dir, preserve_moment, exts=_PICTURE_EXTS)


def cleanup_movies():
    logging.debug('cleaning up movies...')
    
    for camera_id in config.get_camera_ids():
        camera_config = config.get_camera(camera_id)
        if camera_config.get('@proto') != 'v4l2':
            continue
        
        preserve_movies = camera_config.get('@preserve_movies')
        if preserve_movies == 0:
            return # preserve forever
        
        preserve_moment = datetime.datetime.now() - datetime.timedelta(days=preserve_movies)
            
        target_dir = camera_config.get('target_dir')
        _remove_older_files(target_dir, preserve_moment, exts=_MOVIE_EXTS)


def list_pictures(camera_config):
    target_dir = camera_config.get('target_dir')
#     output_all = camera_config.get('output_all')
#     output_normal = camera_config.get('output_normal')
#     jpeg_filename = camera_config.get('jpeg_filename')
#     snapshot_interval = camera_config.get('snapshot_interval')
#     snapshot_filename = camera_config.get('snapshot_filename')
#     
#     if (output_all or output_normal) and jpeg_filename:
#         filename = jpeg_filename
#     
#     elif snapshot_interval and snapshot_filename:
#         filename = snapshot_filename
#     
#     else:
#         return []

    full_paths = _list_media_files(target_dir, exts=_PICTURE_EXTS)
    picture_files = []
    
    for p in full_paths:
        path = p[len(target_dir):]
        if not path.startswith('/'):
            path = '/' + path
        
        picture_files.append({
            'path': path,
            'momentStr': utils.pretty_date_time(datetime.datetime.fromtimestamp(os.path.getmtime(p))),
            'timestamp': os.path.getmtime(p)
        })
    
    # TODO files listed here may not belong to the given camera
    
    return picture_files


def list_movies(camera_config):
    target_dir = camera_config.get('target_dir')

    full_paths = _list_media_files(target_dir, exts=_MOVIE_EXTS)
    movie_files = [{
        'path': p[len(target_dir):],
        'momentStr': utils.pretty_date_time(datetime.datetime.fromtimestamp(os.path.getmtime(p))),
        'timestamp': os.path.getmtime(p)
    } for p in full_paths]
    
    # TODO files listed here may not belong to the given camera
    
    return movie_files


def get_media_content(camera_config, path):
    target_dir = camera_config.get('target_dir')

    full_path = os.path.join(target_dir, path)
    
    try:
        with open(full_path) as f:
            return f.read()
    
    except Exception as e:
        logging.error('failed to read file %(path)s: %(msg)s' % {
                'path': full_path, 'msg': unicode(e)})
        
        return None
