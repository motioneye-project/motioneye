
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
import subprocess


def _find_prog(prog):
    try:
        return subprocess.check_output('which %s' % prog, shell=True).strip()
    
    except subprocess.CalledProcessError: # not found
        return None


def _exec_prog(prog):
    logging.info('executing "%s"' % prog)
    
    return os.system(prog) == 0


def shut_down():
    logging.info('shutting down')
    
    prog = _find_prog('poweroff')
    if prog:
        return _exec_prog(prog)
    
    prog = _find_prog('shutdown')
    if prog:
        return _exec_prog(prog + ' -h now')
    
    prog = _find_prog('systemctl')
    if prog:
        return _exec_prog(prog + ' poweroff')
    
    prog = _find_prog('init')
    if prog:
        return _exec_prog(prog + ' 0')
    
    return False


def reboot():
    logging.info('rebooting')
    
    prog = _find_prog('reboot')
    if prog:
        return _exec_prog(prog)
    
    prog = _find_prog('shutdown')
    if prog:
        return _exec_prog(prog + ' -r now')
    
    prog = _find_prog('systemctl')
    if prog:
        return _exec_prog(prog + ' reboot')
    
    prog = _find_prog('init')
    if prog:
        return _exec_prog(prog + ' 6')
    
    return False
