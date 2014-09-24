
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
import settings


def get_wifi_settings():
    # will return the first configured network
    
    logging.debug('reading wifi settings from %s' % settings.WPA_SUPPLICANT_CONF)
    
    try:
        conf_file = open(settings.WPA_SUPPLICANT_CONF, 'r')
    
    except Exception as e:
        logging.error('could open wifi settings file %(path)s: %(msg)s' % {
                'path': settings.WPA_SUPPLICANT_CONF, 'msg': unicode(e)})
        
        return {
            'ssid': None,
            'psk': None
        }
    
    lines = conf_file.readlines()
    conf_file.close()
    
    ssid = psk = ''
    in_section = False
    for line in lines:
        line = line.strip()
        if line.startswith('#'):
            continue
        
        if '{' in line:
            in_section = True
            
        elif '}' in line:
            in_section = False
            break
            
        elif in_section:
            m = re.search('ssid\s*=\s*"(.*?)"', line)
            if m:
                ssid = m.group(1)
    
            m = re.search('psk\s*=\s*"(.*?)"', line)
            if m:
                psk = m.group(1)

    if ssid:
        logging.debug('wifi is enabled (ssid = "%s")' % ssid)
    
    else:
        logging.debug('wifi is disabled')

    return {
        'ssid': ssid,
        'psk': psk
    }


def set_wifi_settings(s):
    # will update the first configured network
    
    logging.debug('writing wifi settings to %s' % settings.WPA_SUPPLICANT_CONF)
    
    enabled = bool(s['ssid'])
    ssid = s['ssid']
    psk = s['psk']
    
    try:
        conf_file = open(settings.WPA_SUPPLICANT_CONF, 'r')
    
    except Exception as e:
        logging.error('could open wifi settings file %(path)s: %(msg)s' % {
                'path': settings.WPA_SUPPLICANT_CONF, 'msg': unicode(e)})

        return
    
    lines = conf_file.readlines()
    conf_file.close()
    
    in_section = False
    found_ssid = False
    found_psk = False
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#'):
            i += 1
            continue
        
        if '{' in line:
            in_section = True
            
        elif '}' in line:
            in_section = False
            if enabled and ssid and not found_ssid:
                lines.insert(i, '    ssid="' + ssid + '"\n')
            if enabled and psk and not found_psk:
                lines.insert(i, '    psk="' + psk + '"\n')
            
            found_psk = found_ssid = True
            
            break
            
        elif in_section:
            if enabled:
                if re.match('ssid\s*=\s*".*?"', line):
                    lines[i] = '    ssid="' + ssid + '"\n'
                    found_ssid = True
                
                elif re.match('psk\s*=\s*".*?"', line):
                    if psk:
                        lines[i] = '    psk="' + psk + '"\n'
                        found_psk = True
                
                    else:
                        lines.pop(i)
                        i -= 1
        
            else: # wifi disabled
                if re.match('ssid\s*=\s*".*?"', line) or re.match('psk\s*=\s*".*?"', line):
                    lines.pop(i)
                    i -= 1
        
        i += 1

    if enabled and not found_ssid:
        lines.append('network={\n')
        lines.append('    scan_ssid=1\n')
        lines.append('    ssid="' + ssid + '"\n')
        lines.append('    psk="' + psk + '"\n')
        lines.append('}\n\n')

    try:
        conf_file = open(settings.WPA_SUPPLICANT_CONF, 'w')
    
    except Exception as e:
        logging.error('could open wifi settings file %(path)s: %(msg)s' % {
                'path': settings.WPA_SUPPLICANT_CONF, 'msg': unicode(e)})

        return
    
    for line in lines:
        conf_file.write(line)

    conf_file.close()
