
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


# versions

def get_version():
    import motioneye
    
    return motioneye.VERSION


def get_all_versions():
    return []


def compare_versions(version1, version2):
    version1 = re.sub('[^0-9.]', '', version1)
    version2 = re.sub('[^0-9.]', '', version2)
    
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


def perform_update(version):
    logging.error('updating is not implemented')
    
    return False
