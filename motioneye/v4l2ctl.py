
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

import fcntl
import logging
import os.path
import pipes
import re
import stat
import subprocess
import time
import utils


_resolutions_cache = {}
_ctrls_cache = {}
_ctrl_values_cache = {}

_DEV_V4L_BY_ID = '/dev/v4l/by-id/'
_V4L2_TIMEOUT = 10


def find_v4l2_ctl():
    try:
        return subprocess.check_output(['which', 'v4l2-ctl'], stderr=utils.DEV_NULL).strip()
    
    except subprocess.CalledProcessError:  # not found
        return None


def list_devices():
    global _resolutions_cache, _ctrls_cache, _ctrl_values_cache
    
    logging.debug('listing V4L2 devices')
    
    try:
        output = ''
        started = time.time()
        p = subprocess.Popen(['v4l2-ctl', '--list-devices'], stdout=subprocess.PIPE, bufsize=1)

        fd = p.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        while True:
            try:
                data = p.stdout.read(1024)
                if not data:
                    break
            
            except IOError:
                data = ''
                time.sleep(0.01)

            output += data

            if len(output) > 10240:
                logging.warn('v4l2-ctl command returned more than 10k of output')
                break
            
            if time.time() - started > _V4L2_TIMEOUT:
                logging.warn('v4l2-ctl command ran for more than %s seconds' % _V4L2_TIMEOUT)
                break

    except subprocess.CalledProcessError:
        logging.debug('failed to list devices (probably no devices installed)')
        return []

    try:
        # try to kill the v4l2-ctl subprocess
        p.kill()

    except:
        pass  # nevermind

    name = None
    devices = []
    for line in output.split('\n'):
        if line.startswith('\t'):
            device = line.strip()
            persistent_device = find_persistent_device(device)
            devices.append((device, persistent_device, name))
        
            logging.debug('found device %(name)s: %(device)s, %(persistent_device)s' % {
                          'name': name, 'device': device, 'persistent_device': persistent_device})

        else:
            name = line.split('(')[0].strip()
    
    # clear the cache
    _resolutions_cache = {}
    _ctrls_cache = {}
    _ctrl_values_cache = {}

    return devices


def list_resolutions(device):
    import motionctl
    
    global _resolutions_cache
    
    device = utils.make_str(device)
    
    if device in _resolutions_cache:
        return _resolutions_cache[device]
    
    logging.debug('listing resolutions of device %(device)s...' % {'device': device})
    
    resolutions = set()
    output = ''
    started = time.time()
    cmd = 'v4l2-ctl -d %(device)s --list-formats-ext | grep -vi stepwise | grep -oE "[0-9]+x[0-9]+" || true' % {
            'device': pipes.quote(device)}

    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, bufsize=1)

    fd = p.stdout.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    while True:
        try:
            data = p.stdout.read(1024)
            if not data:
                break

        except IOError:
            data = ''
            time.sleep(0.01)

        output += data

        if len(output) > 10240:
            logging.warn('v4l2-ctl command returned more than 10k of output')
            break
        
        if time.time() - started > _V4L2_TIMEOUT:
            logging.warn('v4l2-ctl command ran for more than %s seconds' % _V4L2_TIMEOUT)
            break
    
    try:
        # try to kill the v4l2-ctl subprocess
        p.kill()
    
    except:
        pass  # nevermind

    for pair in output.split('\n'):
        pair = pair.strip()
        if not pair:
            continue
        
        width, height = pair.split('x')
        width = int(width)
        height = int(height)

        if (width, height) in resolutions:
            continue  # duplicate resolution

        if width < 96 or height < 96:  # some reasonable minimal values
            continue
        
        if not motionctl.resolution_is_valid(width, height):
            continue

        resolutions.add((width, height))
        
        logging.debug('found resolution %(width)sx%(height)s for device %(device)s' % {
                'device': device, 'width': width, 'height': height})
    
    if not resolutions:
        logging.debug('no resolutions found for device %(device)s, using common values' % {'device': device})

        # no resolution returned by v4l2-ctl call, add common default resolutions
        resolutions = utils.COMMON_RESOLUTIONS
        resolutions = [r for r in resolutions if motionctl.resolution_is_valid(*r)]

    resolutions = list(sorted(resolutions, key=lambda r: (r[0], r[1])))
    _resolutions_cache[device] = resolutions
    
    return resolutions


def device_present(device):
    device = utils.make_str(device)
    
    try:
        st = os.stat(device)
        return stat.S_ISCHR(st.st_mode)

    except:
        return False
    

def find_persistent_device(device):
    device = utils.make_str(device)
    
    try:
        devs_by_id = os.listdir(_DEV_V4L_BY_ID)

    except OSError:
        return device
    
    for p in devs_by_id:
        p = os.path.join(_DEV_V4L_BY_ID, p)
        if os.path.realpath(p) == device:
            return p
    
    return device


def get_brightness(device):
    return _get_ctrl(device, 'brightness')


def set_brightness(device, value):
    _set_ctrl(device, 'brightness', value)


def get_contrast(device):
    return _get_ctrl(device, 'contrast')


def set_contrast(device, value):
    _set_ctrl(device, 'contrast', value)


def get_saturation(device):
    return _get_ctrl(device, 'saturation')


def set_saturation(device, value):
    _set_ctrl(device, 'saturation', value)


def get_hue(device):
    return _get_ctrl(device, 'hue')


def set_hue(device, value):
    _set_ctrl(device, 'hue', value)


def _get_ctrl(device, control):
    global _ctrl_values_cache
    
    device = utils.make_str(device)
    
    if not device_present(device):
        return None
    
    if device in _ctrl_values_cache and control in _ctrl_values_cache[device]:
        return _ctrl_values_cache[device][control]
    
    controls = _list_ctrls(device)
    properties = controls.get(control)
    if properties is None:
        logging.debug('control %(control)s not found for device %(device)s' % {
                'control': control, 'device': device})
        
        return None
    
    value = int(properties['value'])
    
    # adjust the value range
    if 'min' in properties and 'max' in properties:
        min_value = int(properties['min'])
        max_value = int(properties['max'])
        
        value = int(round((value - min_value) * 100.0 / (max_value - min_value)))
    
    else:
        logging.warn('min and max values not found for control %(control)s of device %(device)s' % {
                'control': control, 'device': device})
    
    logging.debug('control %(control)s of device %(device)s is %(value)s%%' % {
            'control': control, 'device': device, 'value': value})
    
    return value


def _set_ctrl(device, control, value):
    global _ctrl_values_cache
    
    device = utils.make_str(device)
    
    if not device_present(device):
        return

    controls = _list_ctrls(device)
    properties = controls.get(control)
    if properties is None:
        logging.debug('control %(control)s not found for device %(device)s' % {
                'control': control, 'device': device})
        
        return
    
    _ctrl_values_cache.setdefault(device, {})[control] = value

    # adjust the value range
    if 'min' in properties and 'max' in properties:
        min_value = int(properties['min'])
        max_value = int(properties['max'])
        
        value = int(round(min_value + value * (max_value - min_value) / 100.0))
    
    else:
        logging.warn('min and max values not found for control %(control)s of device %(device)s' % {
                'control': control, 'device': device})
    
    logging.debug('setting control %(control)s of device %(device)s to %(value)s' % {
            'control': control, 'device': device, 'value': value})

    output = ''
    started = time.time()
    cmd = 'v4l2-ctl -d %(device)s --set-ctrl %(control)s=%(value)s' % {
            'device': pipes.quote(device), 'control': pipes.quote(control), 'value': pipes.quote(str(value))}
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, bufsize=1)

    fd = p.stdout.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    while True:
        try:
            data = p.stdout.read(1024)
            if not data:
                break
        
        except IOError:
            data = ''
            time.sleep(0.01)

        output += data

        if len(output) > 10240:
            logging.warn('v4l2-ctl command returned more than 10k of output')
            break

        if time.time() - started > 3:
            logging.warn('v4l2-ctl command ran for more than 3 seconds')
            break

    try:
        # try to kill the v4l2-ctl subprocess
        p.kill()

    except:
        pass  # nevermind


def _list_ctrls(device):
    global _ctrls_cache
    
    device = utils.make_str(device)

    if device in _ctrls_cache:
        return _ctrls_cache[device]
    
    output = ''
    started = time.time()
    p = subprocess.Popen('v4l2-ctl -d %(device)s --list-ctrls' % {
            'device': pipes.quote(device)}, shell=True, stdout=subprocess.PIPE, bufsize=1)

    fd = p.stdout.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    while True:
        try:
            data = p.stdout.read(1024)
            if not data:
                break
        
        except IOError:
            data = ''
            time.sleep(0.01)

        output += data

        if len(output) > 10240:
            logging.warn('v4l2-ctl command returned more than 10k of output')
            break

        if time.time() - started > 3:
            logging.warn('v4l2-ctl command ran for more than 3 seconds')
            break

    try:
        # try to kill the v4l2-ctl subprocess
        p.kill()

    except:
        pass  # nevermind

    controls = {}
    for line in output.split('\n'):
        if not line:
            continue
        
        match = re.match('^\s*(\w+)\s+\(\w+\)\s*:\s*(.+)\s*', line)
        if not match:
            continue
        
        (control, properties) = match.groups()
        properties = dict([v.split('=', 1) for v in properties.split(' ') if v.count('=')])
        controls[control] = properties
    
    _ctrls_cache[device] = controls
    
    return controls
