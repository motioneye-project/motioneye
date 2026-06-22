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

from re import sub
from typing import List, Tuple

from motioneye.utils import call_subprocess


def get_os_version() -> Tuple[str, str]:
    try:
        output: str = call_subprocess(['lsb_release', '-sri'])
        lines: List[str] = output.strip().split()
        name, version = lines
        if version.lower() == 'rolling':
            version = ''

        return name, version

    except:
        return _get_os_version_uname()


def _get_os_version_uname() -> Tuple[str, str]:
    try:
        output: str = call_subprocess(['uname', '-rs'])
        lines: List[str] = output.strip().split()
        name, version = lines

        return name, version

    except:
        return 'Linux', ''  # most likely :)


def compare_versions(version1: str, version2: str) -> int:
    version1 = sub('[^0-9.]', '', version1)
    version2 = sub('[^0-9.]', '', version2)

    def int_or_0(n):
        try:
            return int(n)

        except:
            return 0

    version1_list: List[int] = [int_or_0(n) for n in version1.split('.')]
    version2_list: List[int] = [int_or_0(n) for n in version2.split('.')]

    len1: int = len(version1_list)
    len2: int = len(version2_list)
    length: int = min(len1, len2)
    for i in range(length):
        p1: int = version1_list[i]
        p2: int = version2_list[i]

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
