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

import unittest
from unittest.mock import patch
from urllib.error import URLError

from motioneye import meyectl, settings, webhook

_URL = 'https://hooks.example/notify?a=1'


class WebhookTest(unittest.TestCase):
    """meyectl webhook, as motion runs it: the server's certificate is checked
    unless the hook's line carries --no-verify."""

    def setUp(self):
        self._patch('motioneye.meyectl.configure_logging')
        self._patch('motioneye.meyectl.configure_tornado')
        self.urlopen = self._patch('motioneye.utils.urlopen')

    def _patch(self, target, *args, **kwargs):
        patcher = patch(target, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def _call(self, *args):
        # the one urlopen() call that these command line arguments lead to
        webhook.main(meyectl.make_arg_parser('webhook'), list(args))
        self.urlopen.assert_called_once()
        return self.urlopen.call_args

    def test_the_certificate_is_checked_by_default(self):
        call = self._call('GET', _URL)

        request = call.args[0]
        self.assertEqual(_URL, request.full_url)
        self.assertEqual('GET', request.get_method())
        self.assertIsNone(request.data)
        self.assertIs(True, call.kwargs['verify'])
        self.assertEqual(settings.REMOTE_REQUEST_TIMEOUT, call.kwargs['timeout'])

    def test_no_verify_turns_the_check_off_for_this_hook(self):
        call = self._call('-c', '/x.conf', '--no-verify', 'POSTj', _URL)

        request = call.args[0]
        self.assertIs(False, call.kwargs['verify'])
        self.assertEqual(settings.REMOTE_REQUEST_TIMEOUT, call.kwargs['timeout'])
        self.assertEqual('https://hooks.example/notify', request.full_url)
        self.assertEqual('POST', request.get_method())
        self.assertEqual(b'{"a": "1"}', request.data)
        self.assertEqual('application/json', request.get_header('Content-type'))

    def test_a_certificate_error_is_logged_and_swallowed(self):
        reason = '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed'
        self.urlopen.side_effect = URLError(reason)

        with self.assertLogs(level='ERROR') as logs:
            self._call('GET', _URL)

        error = f'ERROR:root:failed to call webhook: <urlopen error {reason}>'
        self.assertEqual([error], logs.output)


if __name__ == '__main__':
    unittest.main()
