import unittest
from unittest.mock import patch

from motioneye import settings
from motioneye.controls import smbctl


class TestMountPassword(unittest.TestCase):
    """The password goes to mount.cifs through PASSWD, as a comma in it ended
    the password option and the mount failed with "Invalid argument"."""

    def _mount(self, username, password):
        with (
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


if __name__ == '__main__':
    unittest.main()
