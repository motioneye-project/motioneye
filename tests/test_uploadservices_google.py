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

import json
import tempfile
import unittest
from base64 import urlsafe_b64encode
from hashlib import sha256
from io import BytesIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from motioneye import uploadservices
from motioneye.uploadservices import GoogleDrive, GooglePhoto

_CODE = '4/0Ab32j93'
_CREDENTIALS = {'access_token': 'a', 'refresh_token': 'r'}


class TestGoogleAuthorization(unittest.TestCase):
    """Google blocked the out-of-band redirect (urn:ietf:wg:oauth:2.0:oob), so
    the key could no longer be obtained (#2516)."""

    def setUp(self):
        uploadservices._code_verifiers.clear()

    def _authorize(self, service=GoogleDrive):
        return parse_qs(urlparse(service.get_authorize_url()).query)

    def test_authorize_url_redirects_to_the_loopback_address(self):
        for service in (GoogleDrive, GooglePhoto):
            with self.subTest(service=service.NAME):
                query = self._authorize(service)
                self.assertEqual(['http://127.0.0.1'], query['redirect_uri'])

    def test_authorize_url_has_the_challenge_of_a_verifier_kept_per_service(self):
        for service in (GoogleDrive, GooglePhoto):
            with self.subTest(service=service.NAME):
                query = self._authorize(service)
                verifier = uploadservices._code_verifiers[service.NAME]
                challenge = urlsafe_b64encode(sha256(verifier.encode()).digest())

                self.assertEqual(['S256'], query['code_challenge_method'])
                self.assertEqual(
                    [challenge.rstrip(b'=').decode()], query['code_challenge']
                )

        self.assertEqual(2, len(set(uploadservices._code_verifiers.values())))

    @patch('motioneye.uploadservices.utils.urlopen')
    def test_key_is_the_code_or_the_address_it_came_in(self, urlopen):
        for key in (
            _CODE,
            f' {_CODE} ',
            (
                f'http://127.0.0.1/?iss=https://accounts.google.com&code={_CODE}'
                '&scope=https://www.googleapis.com/auth/drive.file'
            ),
        ):
            with self.subTest(key=key):
                self._authorize()
                verifier = uploadservices._code_verifiers['gdrive']
                urlopen.return_value = BytesIO(
                    json.dumps({'access_token': 'a', 'refresh_token': 'r'}).encode()
                )

                GoogleDrive(camera_id=1)._request_credentials(key)

                body = parse_qs(urlopen.call_args[0][0].data.decode())
                self.assertEqual([_CODE], body['code'])
                self.assertEqual([verifier], body['code_verifier'])
                # the token request must name the redirect of the authorization
                self.assertEqual(['http://127.0.0.1'], body['redirect_uri'])
                # a verifier is good for one key only
                self.assertNotIn('gdrive', uploadservices._code_verifiers)

    @patch('motioneye.uploadservices.utils.urlopen')
    def test_key_without_a_link_from_this_run_is_refused(self, urlopen):
        # e.g. after a restart, the verifier of the link is gone
        with self.assertRaisesRegex(RuntimeError, 'obtain a new key'):
            GoogleDrive(camera_id=1)._request_credentials(_CODE)

        urlopen.assert_not_called()


class TestCredentialsFromTheTest(unittest.TestCase):
    """The test obtains the credentials with a service of its own; uploads and
    Apply use the one kept in memory, which has to get them too (#3512)."""

    def setUp(self):
        conf = tempfile.TemporaryDirectory()
        self.addCleanup(conf.cleanup)
        for target, value in (
            (uploadservices.settings, ('CONF_PATH', conf.name)),
            (uploadservices, ('_services', None)),
        ):
            p = patch.object(target, *value)
            p.start()
            self.addCleanup(p.stop)

        for method, kwargs in (
            ('_request_credentials', {'return_value': dict(_CREDENTIALS)}),
            ('_get_folder_id', {'side_effect': self._get_folder_id}),
        ):
            p = patch.object(GoogleDrive, method, autospec=True, **kwargs)
            p.start()
            self.addCleanup(p.stop)

    @staticmethod
    def _get_folder_id(service, path=''):
        # what the folder lookup does first: obtain the credentials, and save them
        if not service._credentials:
            service._credentials = service._request_credentials(
                service._authorization_key
            )
            service.save()

        return 'folder'

    def test_uploads_and_apply_keep_the_credentials_of_the_test(self):
        # the service was in use before the key was obtained, e.g. applied once
        uploadservices.update(1, 'gdrive', {'location': '/cams'})

        result = uploadservices.test_access(
            1, 'gdrive', {'location': '/cams', 'authorization_key': _CODE}
        )
        self.assertIs(True, result)

        # the key field is cleared after the test, so Apply sends no key
        uploadservices.update(1, 'gdrive', {'location': '/cams'})

        service = uploadservices._get_service(1, 'gdrive')
        self.assertEqual(_CREDENTIALS, service.dump()['credentials'])
        uploadservices._services = None  # as after a restart
        stored = uploadservices._get_service(1, 'gdrive').dump()
        self.assertEqual(_CREDENTIALS, stored['credentials'])
        # the key is spent once the credentials were obtained, so it is not kept
        self.assertIsNone(stored['authorization_key'])

    def test_unsaved_settings_of_the_test_are_not_applied(self):
        uploadservices.update(1, 'gdrive', {'location': '/cams'})

        uploadservices.test_access(
            1, 'gdrive', {'location': '/other', 'authorization_key': _CODE}
        )

        service = uploadservices._get_service(1, 'gdrive')
        self.assertEqual('/cams', service.dump()['location'])
        self.assertEqual(_CREDENTIALS, service.dump()['credentials'])
        # also in the state file, which the test's own service had written
        uploadservices._services = None  # as after a restart
        stored = uploadservices._get_service(1, 'gdrive').dump()
        self.assertEqual('/cams', stored['location'])
        self.assertEqual(_CREDENTIALS, stored['credentials'])

    def test_a_failed_test_changes_nothing(self):
        uploadservices.update(1, 'gdrive', {'location': '/cams'})
        GoogleDrive._request_credentials.side_effect = RuntimeError('invalid_grant')

        result = uploadservices.test_access(
            1, 'gdrive', {'location': '/other', 'authorization_key': _CODE}
        )

        self.assertEqual('invalid_grant', result)
        stored = uploadservices._get_service(1, 'gdrive').dump()
        self.assertEqual(('/cams', None), (stored['location'], stored['credentials']))


if __name__ == '__main__':
    unittest.main()
