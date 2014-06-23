
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

import logging
import os
import re
import subprocess


def find_mount_cifs():
    try:
        return subprocess.check_output('which mount.cifs', shell=True).strip()
    
    except subprocess.CalledProcessError: # not found
        return None


def _make_mount_point(server, share, username):
    server = re.sub('[^a-zA-Z0-9]', '_', server).lower()
    share = re.sub('[^a-zA-Z0-9]', '_', share).lower()
    
    if username:
        mount_point = '/media/motioneye_%s_%s_%s' % (server, share, username) 
    
    else:
        mount_point = '/media/motioneye_%s_%s' % (server, share)

    logging.debug('making sure mount point "%s" exists' % mount_point)    
    os.makedirs(mount_point)
    
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
            opts = parts[3]
            
            if fstype != 'cifs':
                continue
            
            match = re.match('//([^/]+)/(.+)', target)
            if not match:
                continue
            
            if len(match.groups()) != 2:
                continue
            
            server, share = match.groups()
            
            match = re.search('username=(\w+)', opts)
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


def is_motioneye_mount(mount_point):
    return bool(re.match('^/media/motioneye_\w+$', mount_point))


def mount(server, share, username, password):
    mount_point = _make_mount_point(server, share, username)
    logging.debug('mounting "//%s/%s" at "%s"' % (server, share, mount_point))
    
    if username:
        opts = 'username=%s,password=%s' % (username, password)
        
    else:
        opts = 'guest'

    try:
        subprocess.check_call('mount.cifs //%s/%s %s -o %s' % (server, share, mount_point, opts), shell=True)
        
        return mount_point

    except subprocess.CalledProcessError:
        logging.error('failed to mount smb share "//%s/%s" at "%s"' % (server, share, mount_point))
        
        return False


def umount(server, share, username):
    mount_point = _make_mount_point(server, share, username)
    logging.debug('unmounting "//%s/%s" from "%s"' % (server, share, mount_point))
    
    try:
        subprocess.check_call('umount %s' % mount_point, shell=True)
        
        return True

    except subprocess.CalledProcessError:
        logging.error('failed to unmount smb share "//%s/%s" from "%s"' % (server, share, mount_point))
        
        return False
