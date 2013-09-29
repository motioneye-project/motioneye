
import logging
import re
import subprocess


def list_devices():
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

    return devices


def list_resolutions(device):
    logging.debug('listing resolutions of device %(device)s...' % {'device': device})
    
    resolutions = set()
    output = subprocess.check_output('v4l2-ctl -d %(device)s --list-formats-ext | grep -oE "[0-9]+x[0-9]+"' % {
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
    
    return list(sorted(resolutions, key=lambda r: (r[0], r[1])))


def set_brightness(device, value):
    _set_ctrl(device, 'brightness', value)


def set_contrast(device, value):
    _set_ctrl(device, 'contrast', value)


def set_saturation(device, value):
    _set_ctrl(device, 'saturation', value)


def set_hue(device, value):
    _set_ctrl(device, 'hue', value)


def _set_ctrl(device, control, value):
    controls = _list_ctrls(device)
    properties = controls.get(control)
    if properties is None:
        logging.warn('control %(control)s not found for device %(device)s' % {
                'control': control, 'device': device})
        
        return
    
    # adjust the value range
    if 'min' in properties and 'max' in properties:
        min_value = int(properties['min'])
        max_value = int(properties['max'])
        
        value = min_value + value * float(max_value - min_value) / 100
    
    else:
        logging.warn('min and max values not found for control %(control)s of device %(device)s' % {
                'control': control, 'device': device})
    
    logging.debug('setting control %(control)s of device %(device)s to %(value)s' % {
            'control': control, 'device': device, 'value': value})
        
    subprocess.call('v4l2-ctl -d %(device)s --set-ctrl %(control)s=%(value)s' % {
            'device': device, 'control': control, 'value': value}, shell=True)


def _list_ctrls(device):
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
        properties = dict([v.split('=') for v in properties.split(' ')])
        controls[control] = properties
    
    return controls
