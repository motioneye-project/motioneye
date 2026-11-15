import subprocess
import unittest
from unittest.mock import patch

from motioneye import settings
from motioneye.controls import smbctl

_MOUNT_POINT = '/media/motioneye_nas_cams_me'


class TestMountWithoutRoot(unittest.TestCase):
    """Without root, the shares are mounted through the sudo helper that
    motioneye_init installs (#2710)."""

    def setUp(self):
        for target, args in (
            (settings, ('SMB_MOUNT_ROOT', '/media')),
            (smbctl, ('_mount_cifs_path_cache', '/usr/sbin/mount.cifs')),
            (smbctl, ('_umount_path_cache', '/usr/bin/umount')),
            (smbctl.os, ('geteuid', lambda: 999)),
            (smbctl.os, ('mkdir', lambda path: None)),
            (smbctl.os, ('rmdir', lambda path: None)),
            (smbctl.shutil, ('which', lambda name: f'/usr/bin/{name}')),
        ):
            p = patch.object(target, *args)
            p.start()
            self.addCleanup(p.stop)

        p = patch.object(smbctl.subprocess, 'run')
        self.run_ = p.start()
        self.addCleanup(p.stop)

    def _calls(self):
        return [(c.args[0], c.kwargs.get('input')) for c in self.run_.call_args_list]

    def test_mount_passes_the_password_on_stdin(self):
        with patch.object(smbctl.os.path, 'exists') as exists:
            mount_point = smbctl._mount('nas', 'cams', '3.0', 'me', 'se,cret')

        self.assertEqual(_MOUNT_POINT, mount_point)
        # the helper creates the mount point, which needs root in /media
        exists.assert_not_called()
        self.assertEqual(
            [
                (
                    [
                        '/usr/bin/sudo',
                        '-n',
                        smbctl.SMB_HELPER,
                        'mount',
                        '//nas/cams',
                        _MOUNT_POINT,
                        'username=me,vers=3.0',
                    ],
                    b'se,cret',
                )
            ],
            self._calls(),
        )

    def test_guest_mount_sends_no_password(self):
        smbctl._mount('nas', 'cams', '3.0', '', '')

        self.assertEqual(
            (
                [
                    '/usr/bin/sudo',
                    '-n',
                    smbctl.SMB_HELPER,
                    'mount',
                    '//nas/cams',
                    '/media/motioneye_nas_cams',
                    'guest,vers=3.0',
                ],
                b'',
            ),
            self._calls()[0],
        )

    def test_next_security_mode_after_a_failed_mount(self):
        self.run_.side_effect = [subprocess.CalledProcessError(32, 'sudo'), None]

        self.assertEqual(_MOUNT_POINT, smbctl._mount('nas', 'cams', '3.0', 'me', 'pw'))

        self.assertEqual(
            ['username=me,vers=3.0', 'username=me,vers=3.0,sec=ntlmsspi'],
            [c[0][-1] for c in self._calls()],
        )

    def test_umount_through_the_helper(self):
        with patch.object(smbctl.os, 'rmdir') as rmdir:
            self.assertTrue(smbctl._umount('nas', 'cams', 'me'))

        self.assertEqual(
            [(['/usr/bin/sudo', '-n', smbctl.SMB_HELPER, 'umount', _MOUNT_POINT], b'')],
            self._calls(),
        )
        # the helper removes the mount point, as it is root's
        rmdir.assert_not_called()

    def test_helper_works(self):
        self.assertTrue(smbctl.helper_works())

        self.run_.side_effect = subprocess.CalledProcessError(1, 'sudo')
        self.assertFalse(smbctl.helper_works())

        self.run_.side_effect = FileNotFoundError('sudo')
        self.assertFalse(smbctl.helper_works())

        with patch.object(smbctl.shutil, 'which', lambda name: None):
            self.assertFalse(smbctl.helper_works())


class TestMountPassword(unittest.TestCase):
    """As root, the password goes to mount.cifs through PASSWD, as a comma in it
    ended the password option and the mount failed with "Invalid argument"."""

    def _mount(self, username, password):
        with (
            patch.object(smbctl.os, 'geteuid', lambda: 0),
            patch.object(settings, 'SMB_MOUNT_ROOT', '/media'),
            patch.object(smbctl, '_mount_cifs_path_cache', '/usr/sbin/mount.cifs'),
            patch.object(smbctl.os.path, 'exists', return_value=True),
            patch.object(smbctl.os, 'mkdir'),
            patch.object(smbctl.os, 'rmdir'),
            patch.object(smbctl.subprocess, 'run') as run,
        ):
            smbctl._mount('nas', 'cams', '3.0', username, password)

        command = run.call_args.args[0]
        env = run.call_args.kwargs['env']
        return command[-1], env and env.get('PASSWD')

    def test_password_with_a_comma(self):
        opts, passwd = self._mount('me', 'pa,ss w')

        self.assertEqual(('username=me,vers=3.0', 'pa,ss w'), (opts, passwd))

    def test_empty_password_is_given_as_an_option(self):
        # without it, mount.cifs would ask for one
        opts, passwd = self._mount('me', '')

        self.assertEqual(('username=me,password=,vers=3.0', None), (opts, passwd))

    def test_guest_has_no_password(self):
        opts, passwd = self._mount('', '')

        self.assertEqual(('guest,vers=3.0', None), (opts, passwd))


class TestMediaFoldersAtStart(unittest.TestCase):
    def test_no_folder_below_a_share_that_is_not_mounted_yet(self):
        from motioneye import config, server

        cameras = {
            1: {'@storage_device': 'network-share', 'target_dir': _MOUNT_POINT + '/c'},
            2: {'@storage_device': 'custom-path', 'target_dir': '/var/lib/c2'},
        }
        with (
            patch.object(settings, 'SMB_SHARES', True),
            patch.object(config, 'get_main'),
            patch.object(config, 'get_camera_ids', return_value=[1, 2]),
            patch.object(config, 'get_camera', side_effect=cameras.get),
            patch.object(server.os.path, 'exists', return_value=False),
            patch.object(server.os, 'makedirs') as makedirs,
        ):
            server.make_media_folders()

        makedirs.assert_called_once_with('/var/lib/c2')


if __name__ == '__main__':
    unittest.main()
