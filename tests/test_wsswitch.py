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

"""Tests verifying that the working schedule keeps a manual detection change."""

import unittest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from motioneye import config, motionctl, utils, wsswitch

DURING = datetime(2026, 10, 31, 12, 0)
OUTSIDE = datetime(2026, 10, 31, 20, 0)


class WorkingScheduleTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.camera = {
            '@working_schedule': '|'.join(['08:00-17:00'] * 7),
            '@working_schedule_type': 'during',
            '@motion_detection': True,
        }
        # the state of motion detection in motion
        self.enabled = True
        self.get_error = None

        async def get_motion_detection(camera_id):
            return utils.GetMotionDetectionResult(self.enabled, self.get_error)

        async def set_motion_detection(camera_id, state):
            self.enabled = state == 'start'

        self.set = AsyncMock(side_effect=set_motion_detection)
        self.datetime = Mock()
        for patcher in (
            patch.object(wsswitch, '_ws_state', {}),
            patch.object(wsswitch, 'IOLoop'),
            patch.object(wsswitch, 'datetime', self.datetime),
            patch.object(config, 'get_camera_ids', return_value=[1]),
            patch.object(config, 'get_camera', side_effect=lambda _: self.camera),
            patch.object(utils, 'is_local_motion_camera', return_value=True),
            patch.object(motionctl, 'running', return_value=True),
            patch.object(
                motionctl, 'get_motion_detection', side_effect=get_motion_detection
            ),
            patch.object(motionctl, 'set_motion_detection', self.set),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    async def _check(self, now):
        self.datetime.now.return_value = now
        await wsswitch._check_ws()

    async def test_a_manual_pause_lasts_until_the_schedule_changes(self):
        await self._check(DURING)
        self.set.assert_not_called()

        self.enabled = False  # paused with the button
        await self._check(DURING)
        self.set.assert_not_called()

        await self._check(OUTSIDE)
        self.assertFalse(self.enabled)
        await self._check(DURING)
        self.set.assert_called_once_with(1, 'start')
        self.assertTrue(self.enabled)

    async def test_a_manual_start_lasts_until_the_schedule_changes(self):
        await self._check(OUTSIDE)
        self.set.assert_called_once_with(1, 'pause')

        self.enabled = True  # started with the button
        await self._check(OUTSIDE)
        self.assertTrue(self.enabled)

        await self._check(DURING)
        await self._check(OUTSIDE)
        self.assertEqual(2, self.set.call_count)
        self.assertFalse(self.enabled)

    async def test_the_state_is_checked_again_after_a_motion_restart(self):
        await self._check(DURING)
        self.enabled = False  # e.g. paused, then motion started again

        wsswitch.clear_cache()
        await self._check(DURING)
        self.set.assert_called_once_with(1, 'start')

    async def test_the_state_is_checked_again_after_an_error(self):
        self.enabled = False
        self.get_error = 'connection refused'
        await self._check(DURING)
        self.set.assert_not_called()

        self.get_error = None
        await self._check(DURING)
        self.set.assert_called_once_with(1, 'start')

    async def test_a_failed_switch_is_tried_again(self):
        self.enabled = False
        self.set.side_effect = None
        self.set.return_value = 'failed to start motion detection'
        await self._check(DURING)
        await self._check(DURING)
        self.assertEqual(2, self.set.call_count)


if __name__ == '__main__':
    unittest.main()
