#!/usr/bin/env python3

# Copyright (c) 2022 Jean Michault
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

import sys
from subprocess import run

import motioneye


def main():
    run(
        [f'{motioneye.__path__[0]}/extra/linux_init', *sys.argv[1:]],
        cwd=motioneye.__path__[0],
        check=False,
    )


if __name__ == '__main__':
    main()
