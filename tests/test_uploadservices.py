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

import os
import ssl
import subprocess
import sys
import unittest
from importlib.util import find_spec
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from motioneye import uploadservices


def _needs(module):
    # optional modules; CI installs them, so it fails instead of skipping
    return unittest.skipUnless(
        find_spec(module) or os.environ.get('CI'), f'{module} is not installed'
    )


class TestUploadMediaFileCleanup(unittest.TestCase):
    """Tests for the optional "remove after successful upload" behaviour of
    uploadservices.upload_media_file (the @clean_uploaded option, see #3089).

    The caller (relay handler) passes clean_uploaded, so the cleanup branch -
    including the camera config lookup and the mediafiles import - must be
    skipped entirely when it is False."""

    def setUp(self):
        self.target_dir = os.path.join(os.sep + 'data', 'cam1')
        self.filename = os.path.join(self.target_dir, '2024-01-01', 'movie.mp4')
        self.expected_rel = os.path.join('2024-01-01', 'movie.mp4')

    @patch('motioneye.mediafiles.del_media_content')
    @patch('motioneye.config.get_camera')
    @patch('motioneye.uploadservices._get_service')
    def test_removes_local_file_on_success_when_enabled(
        self, mock_get, mock_get_camera, mock_del
    ):
        mock_get.return_value = MagicMock()  # upload_file() succeeds
        camera_config = {'target_dir': self.target_dir}
        mock_get_camera.return_value = camera_config

        uploadservices.upload_media_file(
            1,
            'cam',
            self.target_dir,
            'ftp',
            self.filename,
            clean_uploaded=True,
        )

        mock_del.assert_called_once_with(camera_config, self.expected_rel)

    @patch('motioneye.mediafiles.del_media_content')
    @patch('motioneye.config.get_camera')
    @patch('motioneye.uploadservices._get_service')
    def test_keeps_local_file_when_disabled(self, mock_get, mock_get_camera, mock_del):
        mock_get.return_value = MagicMock()

        uploadservices.upload_media_file(
            1,
            'cam',
            self.target_dir,
            'ftp',
            self.filename,
            clean_uploaded=False,
        )

        # the common path must not even look up the camera config
        mock_get_camera.assert_not_called()
        mock_del.assert_not_called()

    @patch('motioneye.mediafiles.del_media_content')
    @patch('motioneye.config.get_camera')
    @patch('motioneye.uploadservices._get_service')
    def test_keeps_local_file_when_upload_fails(
        self, mock_get, mock_get_camera, mock_del
    ):
        service = MagicMock()
        service.upload_file.side_effect = Exception('upload boom')
        mock_get.return_value = service

        # a failed upload must not raise and must not delete the local file
        uploadservices.upload_media_file(
            1,
            'cam',
            self.target_dir,
            'ftp',
            self.filename,
            clean_uploaded=True,
        )

        mock_get_camera.assert_not_called()
        mock_del.assert_not_called()

    @patch('motioneye.mediafiles.del_media_content')
    @patch('motioneye.uploadservices._get_service')
    def test_no_cleanup_when_service_missing(self, mock_get, mock_del):
        mock_get.return_value = None

        uploadservices.upload_media_file(
            1,
            'cam',
            self.target_dir,
            'ftp',
            self.filename,
            clean_uploaded=True,
        )

        mock_del.assert_not_called()

    @patch('motioneye.mediafiles.del_media_content')
    @patch('motioneye.config.get_camera')
    @patch('motioneye.uploadservices._get_service')
    def test_cleanup_error_does_not_propagate(
        self, mock_get, mock_get_camera, mock_del
    ):
        mock_get.return_value = MagicMock()
        mock_get_camera.return_value = {'target_dir': self.target_dir}
        mock_del.side_effect = Exception('disk error')

        # a cleanup error must never affect the (already successful) upload
        uploadservices.upload_media_file(
            1,
            'cam',
            self.target_dir,
            'ftp',
            self.filename,
            clean_uploaded=True,
        )

        mock_del.assert_called_once()


class TestFTPWithTLS(unittest.TestCase):
    """The FTP upload service's TLS switch: plain FTP by default, FTP over TLS
    with the server's certificate checked when the switch is on, and a setting
    to turn that check off."""

    def _service(self, **settings):
        service = uploadservices.FTP('1')
        service.load(
            {
                'server': 'ftp.example',
                'port': 21,
                'username': 'cam',
                'password': 'pw',
                'location': '/motioneye',
                **settings,
            }
        )

        return service

    @patch('motioneye.uploadservices._FTPTLSSessionReuse')
    @patch('motioneye.uploadservices.FTPc')
    def test_connects_in_plain_ftp_by_default(self, ftp, ftp_tls):
        conn = self._service()._get_conn(create=True)

        ftp.assert_called_once_with(timeout=uploadservices.FTP.SOCKET_TIMEOUT)
        ftp_tls.assert_not_called()
        conn.connect.assert_called_once_with('ftp.example', port=21)
        conn.login.assert_called_once_with('cam', 'pw')
        conn.prot_p.assert_not_called()

    @patch('motioneye.uploadservices.FTPc')
    @patch('motioneye.uploadservices._FTPTLSSessionReuse')
    def test_with_tls_on_it_checks_the_certificate_and_protects_the_data(
        self, ftp_tls, ftp
    ):
        conn = self._service(tls=True)._get_conn(create=True)

        ftp.assert_not_called()
        context = ftp_tls.call_args.kwargs['context']
        self.assertTrue(context.check_hostname)
        self.assertEqual(ssl.CERT_REQUIRED, context.verify_mode)
        self.assertEqual(
            uploadservices.FTP.SOCKET_TIMEOUT, ftp_tls.call_args.kwargs['timeout']
        )
        self.assertGreater(uploadservices.FTP.SOCKET_TIMEOUT, 0)
        conn.connect.assert_called_once_with('ftp.example', port=21)
        conn.login.assert_called_once_with('cam', 'pw')
        conn.prot_p.assert_called_once_with()

    @patch('motioneye.uploadservices._FTPTLSSessionReuse')
    def test_the_certificate_check_can_be_turned_off(self, ftp_tls):
        self._service(tls=True, verify=False)._get_conn(create=True)

        context = ftp_tls.call_args.kwargs['context']
        self.assertFalse(context.check_hostname)
        self.assertEqual(ssl.CERT_NONE, context.verify_mode)

    def test_tls_is_off_and_the_check_on_by_default_and_both_survive_a_round_trip(
        self,
    ):
        defaults = uploadservices.FTP('1').dump()
        self.assertFalse(defaults['tls'])
        self.assertTrue(defaults['verify'])

        other = uploadservices.FTP('1')
        other.load(self._service(tls=True, verify=False).dump())

        self.assertTrue(other.dump()['tls'])
        self.assertFalse(other.dump()['verify'])

    def test_a_text_off_value_turns_the_check_off(self):
        self.assertIs(False, self._service(verify='off').dump()['verify'])

    @patch('motioneye.uploadservices._FTPTLSSessionReuse')
    @patch('motioneye.uploadservices.FTPc')
    def test_new_settings_drop_the_cached_connection(self, ftp, ftp_tls):
        service = self._service()
        plain = service._get_conn()

        service.load({'tls': True})
        conn = service._get_conn()

        self.assertIs(ftp.return_value, plain)
        self.assertIs(ftp_tls.return_value, conn)
        conn.prot_p.assert_called_once_with()

    @patch('motioneye.uploadservices.FTPc')
    def test_a_failed_upload_drops_the_cached_connection(self, ftp):
        service = self._service()
        broken = ftp.return_value
        broken.storbinary.side_effect = OSError('timed out')

        with self.assertRaises(OSError):
            service.upload_data('2026-10-24/a.jpg', 'image/jpeg', b'x', 0, 'cam')

        ftp.return_value = MagicMock()
        self.assertIs(ftp.return_value, service._get_conn())
        self.assertEqual(2, ftp.call_count)
        broken.close.assert_called_once_with()

    def test_data_connections_resume_the_control_connection_tls_session(self):
        client = uploadservices._FTPTLSSessionReuse(
            context=ssl.create_default_context()
        )
        client.host = 'ftp.example'
        client.sock = MagicMock(session='control session')
        client.context = MagicMock()
        client._prot_p = True
        data_socket = object()

        with patch.object(
            uploadservices.FTPc, 'ntransfercmd', return_value=(data_socket, 42)
        ):
            conn, size = client.ntransfercmd('STOR picture.jpg')

        client.context.wrap_socket.assert_called_once_with(
            data_socket, server_hostname='ftp.example', session='control session'
        )
        self.assertIs(client.context.wrap_socket.return_value, conn)
        self.assertEqual(42, size)

    def test_data_connections_are_left_alone_without_prot_p(self):
        client = uploadservices._FTPTLSSessionReuse(
            context=ssl.create_default_context()
        )
        client.context = MagicMock()
        data_socket = object()

        with patch.object(
            uploadservices.FTPc, 'ntransfercmd', return_value=(data_socket, None)
        ):
            conn, _ = client.ntransfercmd('NLST')

        self.assertIs(data_socket, conn)
        client.context.wrap_socket.assert_not_called()


class TestWebdavVerify(unittest.TestCase):
    """The WebDAV upload service checks the server's certificate on every
    request by default and has a setting to turn that check off."""

    _ENDPOINT = 'https://dav.example/remote.php/dav/files/me/'

    def _service(self, **settings):
        service = uploadservices.Webdav('1')
        service.load(
            {
                'endpoint_url': self._ENDPOINT,
                'username': 'cam',
                'password': 'pw',
                'location': '/motioneye',
                **settings,
            }
        )

        return service

    @patch('motioneye.utils.urlopen')
    def test_the_certificate_is_checked_by_default(self, urlopen):
        self._service()._request(self._ENDPOINT + 'motioneye/', 'MKCOL')

        request = urlopen.call_args.args[0]
        self.assertIs(True, urlopen.call_args.kwargs['verify'])
        self.assertEqual(self._ENDPOINT + 'motioneye/', request.full_url)
        self.assertEqual('MKCOL', request.get_method())
        self.assertEqual('Basic Y2FtOnB3', request.get_header('Authorization'))

    @patch('motioneye.utils.urlopen')
    def test_the_check_can_be_turned_off(self, urlopen):
        self._service(verify=False)._request(self._ENDPOINT + 'motioneye/', 'MKCOL')

        self.assertIs(False, urlopen.call_args.kwargs['verify'])

    def test_the_check_is_on_by_default_and_survives_a_round_trip(self):
        self.assertIs(True, uploadservices.Webdav('1').dump()['verify'])

        other = uploadservices.Webdav('1')
        other.load(self._service(verify=False).dump())

        self.assertIs(False, other.dump()['verify'])

    def test_a_state_without_the_key_keeps_the_check_on(self):
        service = uploadservices.Webdav('1')
        service.load({'endpoint_url': self._ENDPOINT})
        self.assertIs(True, service.dump()['verify'])

        service.load({'verify': 'off'})  # only an explicit off value turns it off
        self.assertIs(False, service.dump()['verify'])

        service.load({'endpoint_url': self._ENDPOINT})  # an update without the key
        self.assertIs(False, service.dump()['verify'])

    @patch('motioneye.utils.urlopen')
    def test_test_access_reports_a_certificate_error(self, urlopen):
        reason = ssl.SSLCertVerificationError(
            1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed'
        )
        urlopen.side_effect = URLError(reason)

        with self.assertLogs(level='ERROR') as logs:
            result = self._service().test_access()

        self.assertIsInstance(result, str)
        self.assertIn('CERTIFICATE_VERIFY_FAILED', result)
        self.assertIn('webdav: <urlopen error', '\n'.join(logs.output))


@_needs('boto3')
class TestS3Verify(unittest.TestCase):
    """The S3 upload service's certificate check can be turned off for a custom
    endpoint only; AWS itself is always verified."""

    _ENDPOINT = 'https://minio.example:9000'

    def _service(self, **settings):
        service = uploadservices.S3('1')
        service.load(
            {
                'access_key': 'AKIAFAKEKEY',
                'secret_key': 'FAKE-secret',
                'bucket': 'cam',
                **settings,
            }
        )

        return service

    def _clients(self, service):
        # the keyword arguments of the boto3 client that each call site builds
        with patch('boto3.client') as client:
            service.test_access()
            service.upload_file(None, '/data/x.jpg', 'cam')

        calls = client.call_args_list
        self.assertEqual([('s3',), ('s3',)], [call.args for call in calls])
        return {'test_access': calls[0].kwargs, 'upload_file': calls[1].kwargs}

    def test_aws_is_always_verified(self):
        for site, kwargs in self._clients(self._service(verify=False)).items():
            with self.subTest(site):
                self.assertIsNone(kwargs['endpoint_url'])
                self.assertIsNone(kwargs['verify'])

    def test_a_custom_endpoint_is_verified_by_default(self):
        service = self._service(endpoint_url=self._ENDPOINT)
        for site, kwargs in self._clients(service).items():
            with self.subTest(site):
                self.assertEqual(self._ENDPOINT, kwargs['endpoint_url'])
                self.assertIsNone(kwargs['verify'])

    def test_the_check_can_be_turned_off_for_a_custom_endpoint(self):
        service = self._service(endpoint_url=self._ENDPOINT, verify=False)
        for site, kwargs in self._clients(service).items():
            with self.subTest(site):
                self.assertEqual(self._ENDPOINT, kwargs['endpoint_url'])
                self.assertEqual('AKIAFAKEKEY', kwargs['aws_access_key_id'])
                self.assertEqual('FAKE-secret', kwargs['aws_secret_access_key'])
                self.assertIs(False, kwargs['verify'])

    def test_the_check_is_on_by_default_and_survives_a_round_trip(self):
        self.assertIs(True, uploadservices.S3('1').dump()['verify'])

        other = uploadservices.S3('1')
        other.load(self._service(endpoint_url=self._ENDPOINT, verify=False).dump())

        self.assertIs(False, other.dump()['verify'])
        self.assertEqual(self._ENDPOINT, other.dump()['endpoint_url'])

    def test_a_state_without_the_key_keeps_the_check_on(self):
        service = self._service()
        self.assertIs(True, service.dump()['verify'])

        service.load({'verify': 'off'})
        self.assertIs(False, service.dump()['verify'])

        service.load({'bucket': 'other'})  # an update without the key
        self.assertIs(False, service.dump()['verify'])

    def test_an_emptied_endpoint_means_aws_again(self):
        service = self._service(endpoint_url=self._ENDPOINT, verify=False)

        service.load({'endpoint_url': ''})

        self.assertIsNone(service.dump()['endpoint_url'])
        for site, kwargs in self._clients(service).items():
            with self.subTest(site=site):
                self.assertIsNone(kwargs['endpoint_url'])
                self.assertIsNone(kwargs['verify'])


@_needs('pycurl')
class TestSFTPTestAccess(unittest.TestCase):
    """The SFTP test removes its file and folder afterwards with lower case
    commands, as libcurl 8 refuses upper case ones ("Unknown SFTP command")."""

    @patch('motioneye.uploadservices.time', return_value=1700000000.5)
    @patch('pycurl.Curl')
    def test_removes_the_test_file_and_folder(self, curl, _):
        service = uploadservices.SFTP('1')
        service.load(
            {
                'server': 'sftp.example',
                'port': 22,
                'username': 'cam',
                'password': 'x',
                'location': '/up',
            }
        )

        self.assertIs(True, service.test_access())

        conn = curl.return_value
        options = {call.args[0]: call.args[1] for call in conn.setopt.call_args_list}
        self.assertEqual(
            'sftp://sftp.example:22//up//motioneye_test/1700000000.5',
            options[conn.URL],
        )
        self.assertEqual(
            ['rm /up//motioneye_test/1700000000.5', 'rmdir /up/motioneye_test'],
            options[conn.POSTQUOTE],
        )


class TestOptionalModules(unittest.TestCase):
    """boto3 and pycurl are needed by the S3 and SFTP uploads only: they are
    imported on use, and without them only that service fails, saying what to
    install."""

    def _s3(self):
        service = uploadservices.S3('1')
        service.load({'access_key': 'AKIAFAKEKEY', 'secret_key': 'x', 'bucket': 'cam'})
        return service

    def _sftp(self):
        service = uploadservices.SFTP('1')
        service.load(
            {
                'server': 'sftp.example',
                'port': 22,
                'username': 'cam',
                'password': 'x',
                'location': '/up',
            }
        )
        return service

    def test_importing_the_module_does_not_import_them(self):
        code = (
            'import sys, motioneye.uploadservices; '
            'print(sorted(m for m in ("boto3", "pycurl") if m in sys.modules))'
        )
        out = subprocess.run(
            [sys.executable, '-c', code], capture_output=True, text=True, check=True
        ).stdout

        self.assertEqual('[]', out.strip())

    def test_test_access_says_what_to_install(self):
        for module, service in (('boto3', self._s3()), ('pycurl', self._sftp())):
            with self.subTest(module), patch.dict(sys.modules, {module: None}):
                with self.assertLogs(level='ERROR'):
                    result = service.test_access()

                self.assertIsInstance(result, str)
                self.assertIn(f'Python module {module}', result)
                self.assertIn(f'sudo {sys.executable} -m pip install {module}', result)

    def test_an_upload_fails_and_keeps_the_file(self):
        for module, service in (('boto3', self._s3()), ('pycurl', self._sftp())):
            with self.subTest(module), patch.dict(sys.modules, {module: None}):
                with self.assertRaisesRegex(RuntimeError, f'Python module {module}'):
                    service.upload_file(None, __file__, 'cam')

                get = patch.object(uploadservices, '_get_service', return_value=service)
                deleting = patch('motioneye.mediafiles.del_media_content')
                with get, deleting as delete, self.assertLogs(level='ERROR') as logs:
                    uploadservices.upload_media_file(
                        1, 'cam', '/data', service.NAME, __file__, True
                    )

                delete.assert_not_called()
                self.assertIn(f'Python module {module}', '\n'.join(logs.output))

    def test_the_services_are_still_offered(self):
        with patch.dict(sys.modules, {'boto3': None, 'pycurl': None}):
            names = uploadservices._get_service_classes()

        self.assertIn('s3', names)
        self.assertIn('sftp', names)

    @_needs('pycurl')
    def test_sftp_sets_its_options_on_a_real_curl_object(self):
        # the options are read from the Curl object, which has them all
        import pycurl

        conn = pycurl.Curl()
        for name in ('URL', 'CONNECTTIMEOUT', 'READFUNCTION', 'POSTQUOTE', 'UPLOAD'):
            with self.subTest(name):
                self.assertEqual(getattr(pycurl, name), getattr(conn, name))

        conn.close()


if __name__ == '__main__':
    unittest.main()
