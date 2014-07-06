
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
import json
import logging
import os.path
import shutil
import signal
import subprocess
import tempfile
import time
import urllib2

from tornado.ioloop import IOLoop

import settings


_BITBUCKET_ROOT_URL = 'https://bitbucket.org'
_BITBUCKET_DOWNLOAD_URL = '%(root)s/%(owner)s/%(repo)s/get/%(version)s.tar.gz'
_BITBUCKET_LIST_TAGS_URL = '%(root)s/api/1.0/repositories/%(owner)s/%(repo)s/tags'

_UPDATE_PATHS = ['src', 'static', 'templates', 'motioneye.py']


# versions

def get_version():
    import motioneye
    
    return motioneye.VERSION


def get_all_versions():
    url = _BITBUCKET_LIST_TAGS_URL % {
            'root': _BITBUCKET_ROOT_URL,
            'owner': settings.REPO[0],
            'repo': settings.REPO[1]}
    
    url += '?_=' + str(int(time.time())) # prevents caching
    
    try:
        logging.debug('fetching %(url)s...' % {'url': url})
        
        response = urllib2.urlopen(url, timeout=settings.REMOTE_REQUEST_TIMEOUT)
        response = json.load(response)
        versions = response.keys()
        
        logging.debug('available versions: %(versions)s' % {
                'versions': ', '.join(versions)})
        
        return sorted(versions, cmp=compare_versions)

    except Exception as e:
        logging.error('could not get versions: %(msg)s' % {'msg': unicode(e)}, exc_info=True)
        
    return []


def compare_versions(version1, version2):
    version1 = [int(n) for n in version1.split('.')]
    version2 = [int(n) for n in version2.split('.')]
    
    len1 = len(version1)
    len2 = len(version2)
    length = min(len1, len2)
    for i in xrange(length):
        p1 = version1[i]
        p2 = version2[i]
        
        if p1 < p2:
            return -1
        
        elif p1 > p2:
            return 1
    
    if len1 < len2:
        return -1
    
    elif len1 > len2:
        return 1
    
    else:
        return 0


# updating

def download(version):
    url = _BITBUCKET_DOWNLOAD_URL % {
            'root': _BITBUCKET_ROOT_URL,
            'owner': settings.REPO[0],
            'repo': settings.REPO[1],
            'version': version}
    
    url += '?_=' + str(int(time.time())) # prevents caching
    
    try:
        logging.debug('downloading %(url)s...' % {'url': url})
        
        response = urllib2.urlopen(url, timeout=settings.REMOTE_REQUEST_TIMEOUT)
        data = response.read()

    except Exception as e:
        logging.error('could download update: %(msg)s' % {'msg': unicode(e)})
        
        raise
    
    path = tempfile.mkdtemp()
    path = os.path.join(path, version + '.tar.gz')
    
    logging.debug('writing archive to %(path)s...' % {'path': path})
    
    try:
        with open(path, 'w') as f:
            f.write(data)
        
    except Exception as e:
        logging.error('could download update: %(msg)s' % {'msg': unicode(e)})
        
        raise
    
    return path


def cleanup(path):
    try:
        shutil.rmtree(path)
    
    except Exception as e:
        logging.error('could cleanup update directory: %(msg)s' % {'msg': unicode(e)})


def perform_update(version):
    logging.info('updating to version %(version)s...' % {'version': version})
    
    try:
        # make sure the partition where motionEye resides is writable
        path = os.path.abspath(settings.PROJECT_PATH)
        if settings.ENABLE_REBOOT:
            try:
                df_lines = subprocess.check_output('df %s' % path, shell=True).split('\n')
                last_line = [l for l in df_lines if l.strip()][-1]
                mount_point = last_line.split()[-1]
                
                os.system('mount -o remount,rw %s' % mount_point)
            
            except Exception as e:
                logging.error('failed to remount root partition rw: %s' % e, exc_info=True)
        
        if not os.access(path, os.W_OK):
            raise Exception('path "%s" is not writable' % path)
        
        # download the archive
        archive = download(version)
        temp_path = os.path.dirname(archive)
        
        # extract the archive
        logging.debug('extracting archive %(archive)s...' % {'archive': archive})
        os.system('tar zxf %(archive)s -C %(path)s' % {
                'archive': archive, 'path': temp_path})
        
        # kill all the subprocesses
        try:
            children_pids = [int(p) for p in subprocess.check_output('ps -o pid --no-headers --ppid %s' % os.getpid(), shell=True).split() if p]
            for pid in children_pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                    logging.debug('killed process %d' % pid)
                
                except Exception as e:
                    if getattr(e, 'errno', None) == 3: # no such process
                        continue
                    
                    else:
                        logging.error('failed to kill process %d: %s' % (pid, e))

        except Exception as e:
            logging.error('failed to kill children processes: %s' % e)
        
        # determine the root path of the extracted archive
        root_name = [f for f in os.listdir(temp_path) if os.path.isdir(os.path.join(temp_path, f))][0]
        root_path = os.path.join(temp_path, root_name)
        
        for p in _UPDATE_PATHS:
            src = os.path.join(root_path, p)
            dst = os.path.join(settings.PROJECT_PATH, p)
            
            logging.debug('copying %(src)s over %(dst)s...' % {'src': src, 'dst':  dst})
            
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            
            else:
                shutil.copy(src, dst)

        # remove the temporary update directory
        logging.debug('removing %(path)s...' % {'path': temp_path})
        cleanup(temp_path)
        
        logging.info('updating done')
        
        if settings.ENABLE_REBOOT:
            def call_reboot():
                logging.info('rebooting')
                os.system('reboot')
                
            IOLoop.instance().add_timeout(datetime.timedelta(seconds=2), call_reboot)
        
        return True
    
    except Exception as e:
        logging.error('could not perform update: %(msg)s' % {'msg': unicode(e)}, exc_info=True)
        
        return False