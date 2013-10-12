
import datetime
import logging
import os

import config


def _remove_older_files(dir, moment, exts):
    for root, dirs, files in os.walk(dir):  # @UnusedVariable
        for name in files:
            full_path = os.path.join(root, name)
            if not os.path.isfile(full_path):
                continue
            
            full_path_lower = full_path.lower()
            if not [e for e in exts if full_path_lower.endswith(e)]:
                continue
            
            file_moment = datetime.datetime.fromtimestamp(os.path.getmtime(full_path))
            if file_moment < moment:
                logging.debug('removing file %(path)s...' % {
                        'path': full_path})
                
                os.remove(full_path)


def cleanup_images():
    logging.debug('cleaning up images...')
    
    for camera_id in config.get_camera_ids():
        camera_config = config.get_camera(camera_id)
        if camera_config.get('@proto') != 'v4l2':
            continue
        
        preserve_images = camera_config.get('@preserve_images')
        if preserve_images == 0:
            return # preserve forever
        
        preserve_moment = datetime.datetime.now() - datetime.timedelta(days=preserve_images)
            
        target_dir = camera_config.get('target_dir')
        _remove_older_files(target_dir, preserve_moment, exts=['.jpg', '.png'])


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
        _remove_older_files(target_dir, preserve_moment, exts=['.avi'])
