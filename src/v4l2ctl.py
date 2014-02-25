
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
import re
import subprocess


_resolutions_cache = {}
_ctrls_cache = {}
_ctrl_values_cache = {}


def find_v4l2_ctl():
    try:
        return subprocess.check_output('which v4l2-ctl', shell=True).strip()
    
    except subprocess.CalledProcessError: # not found
        return None


def list_devices():
    global _resolutions_cache
    
    logging.debug('listing v4l devices...')
    
    devices = []
    
    output = subprocess.check_output('v4l2-ctl --list-devices', shell=True)
    
    name = None
    for line in output.split('\n'):
        if line.startswith('\t'):
            device = line.strip()
            devices.append((device, name))
        
            logging.debug('found device %(name)s: %(device)s' % {
                    'name': name, 'device': device})
            
        else:
            name = line.split('(')[0].strip()
    
    # clear the cache
    _resolutions_cache = {}
    _ctrls_cache = {}
    _ctrl_values_cache = {}

    return devices


def list_resolutions(device):
    global _resolutions_cache
    
    if device in _resolutions_cache:
        return _resolutions_cache[device]
    
    logging.debug('listing resolutions of device %(device)s...' % {'device': device})
    
    resolutions = set()
    output = subprocess.check_output('v4l2-ctl -d %(device)s --list-formats-ext | grep -oE "[0-9]+x[0-9]+" || true' % {
            'device': device}, shell=True)

    for pair in output.split('\n'):
        pair = pair.strip()
        if not pair:
            continue
        
        width, height = pair.split('x')
        width = int(width)
        height = int(height)
        
        resolutions.add((width, height))
        
        logging.debug('found resolution %(width)sx%(height)s for device %(device)s' % {
                'device': device, 'width': width, 'height': height})
    
    if not resolutions:
        logging.debug('no resolutions found for device %(device)s, adding the defaults' % {'device': device})
        
        # no resolution returned by v4l2-ctl call, add common default resolutions
        resolutions.add((320, 240))
        resolutions.add((640, 480))
        resolutions.add((800, 480))
        resolutions.add((1024, 576))
        resolutions.add((1024, 768))
        resolutions.add((1280, 720))
        resolutions.add((1280, 800))
        resolutions.add((1280, 960))
        resolutions.add((1280, 1024))
        resolutions.add((1440, 960))
        resolutions.add((1440, 1024))
        resolutions.add((1600, 1200))

    resolutions = list(sorted(resolutions, key=lambda r: (r[0], r[1])))
    _resolutions_cache[device] = resolutions
    
    return resolutions


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
    
    if device in _ctrl_values_cache and control in _ctrl_values_cache[device]:
        return _ctrl_values_cache[device][control]
    
    controls = _list_ctrls(device)
    properties = controls.get(control)
    if properties is None:
        logging.warn('control %(control)s not found for device %(device)s' % {
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
    
    controls = _list_ctrls(device)
    properties = controls.get(control)
    if properties is None:
        logging.warn('control %(control)s not found for device %(device)s' % {
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
        
    subprocess.call('v4l2-ctl -d %(device)s --set-ctrl %(control)s=%(value)s' % {
            'device': device, 'control': control, 'value': value}, shell=True)


def _list_ctrls(device):
    global _ctrls_cache
    
    if device in _ctrls_cache:
        return _ctrls_cache[device]
    
    output = subprocess.check_output('v4l2-ctl -d %(device)s --list-ctrls' % {
            'device': device}, shell=True)

    controls = {}
    for line in output.split('\n'):
        if not line:
            continue
        
        match = re.match('^\s*(\w+)\s+\(\w+\)\s+\:\s*(.+)', line)
        if not match:
            continue
        
        (control, properties) = match.groups()
        properties = dict([v.split('=', 1) for v in properties.split(' ') if v.count('=')])
        controls[control] = properties
    
    _ctrls_cache[device] = controls
    
    return controls
