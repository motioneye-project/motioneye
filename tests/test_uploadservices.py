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
import unittest
from unittest.mock import MagicMock, patch

from motioneye import uploadservices


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

    def test_settings_from_a_config_file_arrive_as_strings(self):
        service = self._service(tls='on', verify='off')

        self.assertTrue(service.dump()['tls'])
        self.assertFalse(service.dump()['verify'])

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


if __name__ == '__main__':
    unittest.main()
