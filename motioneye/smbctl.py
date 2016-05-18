
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
import os
import re
import subprocess
import time
import utils

from tornado.ioloop import IOLoop

import config
import settings


def start():
    io_loop = IOLoop.instance()
    io_loop.add_timeout(datetime.timedelta(seconds=settings.MOUNT_CHECK_INTERVAL), _check_mounts)


def stop():
    _umount_all()


def find_mount_cifs():
    try:
        return subprocess.check_output(['which', 'mount.cifs'], stderr=utils.DEV_NULL).strip()
    
    except subprocess.CalledProcessError: # not found
        return None


def make_mount_point(server, share, username):
    server = re.sub('[^a-zA-Z0-9]', '_', server).lower()
    share = re.sub('[^a-zA-Z0-9]', '_', share).lower()
    
    if username:
        username = re.sub('[^a-zA-Z0-9]', '_', username).lower()
        mount_point = os.path.join(settings.SMB_MOUNT_ROOT, 'motioneye_%s_%s_%s' % (server, share, username))
    
    else:
        mount_point = os.path.join(settings.SMB_MOUNT_ROOT, 'motioneye_%s_%s' % (server, share))

    return mount_point


def list_mounts():
    logging.debug('listing smb mounts...')
    
    mounts = []
    with open('/proc/mounts', 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            
            target = parts[0]
            mount_point = parts[1]
            fstype = parts[2]
            opts = ' '.join(parts[3:])
            
            if fstype != 'cifs':
                continue
            
            if not _is_motioneye_mount(mount_point):
                continue
            
            match = re.match('//([^/]+)/(.+)', target)
            if not match:
                continue
            
            if len(match.groups()) != 2:
                continue
            
            server, share = match.groups()
            share = share.replace('\\040', ' ') # spaces are reported oddly by /proc/mounts
            
            match = re.search('username=([\w\s]+)', opts)
            if match:
                username = match.group(1)
            
            else:
                username = None
                
            logging.debug('found smb mount "//%s/%s" at "%s"' % (server, share, mount_point))
            
            mounts.append({
                'server': server,
                'share': share,
                'username': username,
                'mount_point': mount_point
            })

    return mounts


def update_mounts():
    network_shares = config.get_network_shares()
    
    mounts = list_mounts()
    mounts = dict(((m['server'], m['share'], m['username'] or ''), False) for m in mounts)
    
    should_stop = False # indicates that motion should be stopped immediately
    should_start = True # indicates that motion can be started afterwards
    for network_share in network_shares:
        key = (network_share['server'], network_share['share'], network_share['username'] or '')
        if key in mounts: # found
            mounts[key] = True
        
        else: # needs to be mounted
            should_stop = True
            if not _mount(network_share['server'], network_share['share'], network_share['username'], network_share['password']):
                should_start = False
    
    # unmount the no longer necessary mounts
    for (server, share, username), required in mounts.items():
        if not required:
            _umount(server, share, username)
            should_stop = True
    
    return (should_stop, should_start)


def _mount(server, share, username, password):
    mount_point = make_mount_point(server, share, username)
    
    logging.debug('making sure mount point "%s" exists' % mount_point)
    
    if not os.path.exists(mount_point):    
        os.makedirs(mount_point)
        
    if username:
        opts = 'username=%s,password=%s' % (username, password)
        sec_types = [None, 'ntlm', 'ntlmv2', 'ntlmv2i', 'ntlmsspi', 'none']

    else:
        opts = 'guest'
        sec_types = [None, 'none', 'ntlm', 'ntlmv2', 'ntlmv2i', 'ntlmsspi']

    for sec in sec_types:
        if sec:
            actual_opts = opts + ',sec=' + sec
        
        else:
            actual_opts = opts

        try:
            logging.debug('mounting "//%s/%s" at "%s" (sec=%s)' % (server, share, mount_point, sec))
            subprocess.check_call(['mount.cifs', '//%s/%s' % (server, share), mount_point, '-o', actual_opts])
            break

        except subprocess.CalledProcessError:
            pass
            
    else:
        logging.error('failed to mount smb share "//%s/%s" at "%s"' % (server, share, mount_point))
        return None
    
    # test to see if mount point is writable
    try:
        path = os.path.join(mount_point, '.motioneye_' + str(int(time.time())))
        os.mkdir(path)
        os.rmdir(path)
        logging.debug('directory at "%s" is writable' % mount_point)
    
    except:
        logging.error('directory at "%s" is not writable' % mount_point)
        
        return None
    
    return mount_point


def _umount(server, share, username):
    mount_point = make_mount_point(server, share, username)
    logging.debug('unmounting "//%s/%s" from "%s"' % (server, share, mount_point))
    
    try:
        subprocess.check_call(['umount', mount_point])

    except subprocess.CalledProcessError:
        logging.error('failed to unmount smb share "//%s/%s" from "%s"' % (server, share, mount_point))
        
        return False
    
    try:
        os.rmdir(mount_point)
    
    except Exception as e:
        logging.error('failed to remove smb mount point "%s": %s' % (mount_point, e))
        
        return False
        
    return True


def _is_motioneye_mount(mount_point):
    mount_point_root = os.path.join(settings.SMB_MOUNT_ROOT, 'motioneye_')
    return bool(re.match('^' + mount_point_root + '\w+$', mount_point))


def _umount_all():
    for mount in list_mounts():
        _umount(mount['server'], mount['share'], mount['username'])


def _check_mounts():
    import motionctl
    
    logging.debug('checking SMB mounts...')
    
    stop, start = update_mounts()
    if stop:
        motionctl.stop()

    if start:
        motionctl.start()
        
    io_loop = IOLoop.instance()
    io_loop.add_timeout(datetime.timedelta(seconds=settings.MOUNT_CHECK_INTERVAL), _check_mounts)

