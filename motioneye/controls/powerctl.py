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
from collections import OrderedDict
from typing import Dict

from motioneye import utils

__all__ = ('PowerControl',)


class PowerControl:

    _shut_down_cmd_sequence = OrderedDict(
        [
            ('poweroff', ''),
            ('shutdown', ' -h now'),
            ('systemctl', ' poweroff'),
            ('init', ' 0'),
        ]
    )

    _reboot_cmd_sequence = OrderedDict(
        [
            ('reboot', ''),
            ('shutdown', ' -r now'),
            ('systemctl', ' reboot'),
            ('init', ' 6'),
        ]
    )

    @staticmethod
    def _find_prog(prog: str) -> str:
        return utils.call_subprocess(['which', prog])

    @classmethod
    def _exec_prog(cls, prog: str, args: str = '') -> bool:
        p = cls._find_prog(prog)
        logging.info('executing "%s"' % p)
        return os.system(p + args) == 0

    @classmethod
    def _run_procedure(cls, prog_sequence: Dict[str, str], log_msg: str) -> bool:
        logging.info(log_msg)

        for prog, args in prog_sequence.items():
            try:
                return cls._exec_prog(prog, args)
            except subprocess.CalledProcessError:  # program not found
                continue
        else:
            return False

    @classmethod
    def shut_down(cls) -> bool:
        return cls._run_procedure(cls._shut_down_cmd_sequence, 'shutting down')

    @classmethod
    def reboot(cls) -> bool:
        return cls._run_procedure(cls._reboot_cmd_sequence, 'rebooting')
