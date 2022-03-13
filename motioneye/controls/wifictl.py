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

from motioneye import settings
from motioneye.config import additional_config, additional_section

WPA_SUPPLICANT_CONF = settings.WPA_SUPPLICANT_CONF  # @UndefinedVariable


def _get_wifi_settings():
    # will return the first configured network

    logging.debug('reading wifi settings from %s' % WPA_SUPPLICANT_CONF)

    try:
        conf_file = open(WPA_SUPPLICANT_CONF)

    except Exception as e:
        logging.error(f'could open wifi settings file {WPA_SUPPLICANT_CONF}: {str(e)}')

        return {'wifiEnabled': False, 'wifiNetworkName': '', 'wifiNetworkKey': ''}

    lines = conf_file.readlines()
    conf_file.close()

    ssid = psk = ''
    in_section = False
    for line in lines:
        line = line.strip()
        if line.startswith('#'):
            continue

        if line.endswith('{'):
            in_section = True

        elif line.startswith('}'):
            in_section = False
            break

        elif in_section:
            m = re.search(r'ssid\s*=\s*"(.*?)"', line)
            if m:
                ssid = m.group(1)

            m = re.search(r'psk\s*=\s*"?([^"]*)"?', line)
            if m:
                psk = m.group(1)

    if ssid:
        logging.debug('wifi is enabled (ssid = "%s")' % ssid)

        return {'wifiEnabled': True, 'wifiNetworkName': ssid, 'wifiNetworkKey': psk}

    else:
        logging.debug('wifi is disabled')

        return {'wifiEnabled': False, 'wifiNetworkName': ssid, 'wifiNetworkKey': psk}


def _set_wifi_settings(s):
    s.setdefault('wifiEnabled', False)
    s.setdefault('wifiNetworkName', '')
    s.setdefault('wifiNetworkKey', '')

    logging.debug(
        'writing wifi settings to {}: enabled={}, ssid="{}"'.format(
            WPA_SUPPLICANT_CONF, s['wifiEnabled'], s['wifiNetworkName']
        )
    )

    enabled = s['wifiEnabled']
    ssid = s['wifiNetworkName']
    psk = s['wifiNetworkKey']
    psk_is_hex = re.match('^[a-f0-9]{64}$', psk, re.I) is not None
    key_mgmt = None if psk else 'NONE'

    # will update the first configured network
    try:
        conf_file = open(WPA_SUPPLICANT_CONF)

    except Exception as e:
        logging.error(
            'could open wifi settings file {path}: {msg}'.format(
                path=WPA_SUPPLICANT_CONF, msg=str(e)
            )
        )

        return

    lines = conf_file.readlines()
    conf_file.close()

    in_section = False
    found_ssid = False
    found_psk = False
    found_key_mgmt = False
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#'):
            i += 1
            continue

        if line.endswith('{'):
            in_section = True

        elif line.startswith('}'):
            in_section = False
            if enabled and ssid and not found_ssid:
                lines.insert(i, '    ssid="' + ssid + '"\n')
            if enabled and psk and not found_psk:
                if psk_is_hex:
                    lines.insert(i, '    psk=' + psk + '\n')

                else:
                    lines.insert(i, '    psk="' + psk + '"\n')
            if enabled and not found_key_mgmt and key_mgmt:
                lines.insert(i, '    key_mgmt=' + key_mgmt + '\n')

            found_psk = found_ssid = found_key_mgmt = True

            break

        elif in_section:
            if enabled:
                if re.match(r'ssid\s*=\s*".*?"', line):
                    lines[i] = '    ssid="' + ssid + '"\n'
                    found_ssid = True

                elif re.match(r'psk\s*=.*', line):
                    if psk:
                        if psk_is_hex:
                            lines[i] = '    psk=' + psk + '\n'

                        else:
                            lines[i] = '    psk="' + psk + '"\n'

                        found_psk = True

                    else:
                        lines.pop(i)
                        i -= 1

                elif re.match(r'key_mgmt\s*=\s*.*?', line) and key_mgmt:
                    lines[i] = '    key_mgmt=' + key_mgmt + '\n'
                    found_key_mgmt = True

            else:  # wifi disabled
                if re.match(r'ssid\s*=\s*".*?"', line) or re.match(
                    r'psk\s*=\s*".*?"', line
                ):
                    lines.pop(i)
                    i -= 1

        i += 1

    if enabled and not found_ssid:
        lines.append('network={\n')
        lines.append('    scan_ssid=1\n')
        lines.append('    ssid="' + ssid + '"\n')
        if psk_is_hex:
            lines.append('    psk=' + psk + '\n')

        else:
            lines.append('    psk="' + psk + '"\n')
        if key_mgmt:
            lines.append('    key_mgmt=' + key_mgmt + '\n')
        lines.append('}\n\n')

    try:
        conf_file = open(WPA_SUPPLICANT_CONF, 'w')

    except Exception as e:
        logging.error(
            'could open wifi settings file {path}: {msg}'.format(
                path=WPA_SUPPLICANT_CONF, msg=str(e)
            )
        )

        return

    for line in lines:
        conf_file.write(line)

    conf_file.close()


@additional_section
def network():
    return {'label': 'Network', 'description': 'configure the network connection'}


@additional_config
def wifi_enabled():
    if not WPA_SUPPLICANT_CONF:
        return

    return {
        'label': 'Wireless Network',
        'description': 'enable this if you want to connect to a wireless network',
        'type': 'bool',
        'section': 'network',
        'reboot': True,
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_network_name():
    if not WPA_SUPPLICANT_CONF:
        return

    return {
        'label': 'Wireless Network Name',
        'description': 'the name (SSID) of your wireless network',
        'type': 'str',
        'section': 'network',
        'required': True,
        'reboot': True,
        'depends': ['wifiEnabled'],
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_network_key():
    if not WPA_SUPPLICANT_CONF:
        return

    return {
        'label': 'Wireless Network Key',
        'description': 'the key (PSK) required to connect to your wireless network',
        'type': 'pwd',
        'section': 'network',
        'required': False,
        'reboot': True,
        'depends': ['wifiEnabled'],
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }
