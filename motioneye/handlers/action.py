
# Copyright (c) 2020 Vlsarro
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

import datetime
import logging
import os
import subprocess

from tornado.ioloop import IOLoop
from tornado.web import HTTPError

from motioneye import config
from motioneye import motionctl
from motioneye import remote
from motioneye import utils
from motioneye.handlers.base import BaseHandler


__all__ = ('ActionHandler',)


class ActionHandler(BaseHandler):

    async def post(self, camera_id, action):
        camera_id = int(camera_id)
        if camera_id not in config.get_camera_ids():
            raise HTTPError(404, 'no such camera')

        local_config = config.get_camera(camera_id)
        if utils.is_remote_camera(local_config):
            resp = await remote.exec_action(local_config, action)
            if resp.error:
                msg = 'Failed to execute action on remote camera at %(url)s: %(msg)s.' % {
                    'url': remote.pretty_camera_url(local_config), 'msg': resp.error}

                return self.finish_json({'error': msg})

            return self.finish_json()

        if action == 'snapshot':
            logging.debug('executing snapshot action for camera with id %s' % camera_id)
            await self.snapshot(camera_id)
            return

        elif action == 'record_start':
            logging.debug('executing record_start action for camera with id %s' % camera_id)
            return self.record_start(camera_id)

        elif action == 'record_stop':
            logging.debug('executing record_stop action for camera with id %s' % camera_id)
            return self.record_stop(camera_id)

        action_commands = config.get_action_commands(local_config)
        command = action_commands.get(action)
        if not command:
            raise HTTPError(400, 'unknown action')

        logging.debug('executing %s action for camera with id %s: "%s"' % (action, camera_id, command))
        self.run_command_bg(command)

    def run_command_bg(self, command):
        self.p = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        self.command = command

        self.io_loop = IOLoop.instance()
        self.io_loop.add_timeout(datetime.timedelta(milliseconds=100), self.check_command)

    def check_command(self):
        exit_status = self.p.poll()
        if exit_status is not None:
            output = self.p.stdout.read()
            lines = output.decode('utf-8').split('\n')
            if not lines[-1]:
                lines = lines[:-1]
            command = os.path.basename(self.command)
            if exit_status:
                logging.warning('%s: command has finished with non-zero exit status: %s' % (command, exit_status))
                for line in lines:
                    logging.warning('%s: %s' % (command, line))

            else:
                logging.debug('%s: command has finished' % command)
                for line in lines:
                    logging.debug('%s: %s' % (command, line))

            return self.finish_json({'status': exit_status})

        else:
            self.io_loop.add_timeout(datetime.timedelta(milliseconds=100), self.check_command)

    async def snapshot(self, camera_id):
        await motionctl.take_snapshot(camera_id)
        return self.finish_json({})

    def record_start(self, camera_id):
        return self.finish_json({})

    def record_stop(self, camera_id):
        return self.finish_json({})
