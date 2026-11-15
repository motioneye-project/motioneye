import os
import subprocess
import unittest
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

from motioneye import settings, utils
from motioneye.controls import v4l2ctl


class LibcameraV4l2EnvTest(unittest.TestCase):
    """motion and v4l2-ctl get libcamera's V4L2 layer preloaded, as with libcamerify."""

    def setUp(self):
        self.tmp = mkdtemp()
        self.addCleanup(rmtree, self.tmp)
        self.v4l2_compat = os.path.join(self.tmp, 'v4l2-compat.so')
        open(self.v4l2_compat, 'w').close()

        for patcher in (
            patch.dict(os.environ, clear=False),
            patch.object(utils, '_libcamera_v4l2_missing_reported', False),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

        os.environ.pop('LD_PRELOAD', None)

    def _env(self, path):
        with patch.object(settings, 'LIBCAMERA_V4L2', path):
            return utils.libcamera_v4l2_env()

    def test_not_set_inherits_motioneyes_environment(self):
        self.assertIsNone(self._env(None))

    def test_set_preloads_it_and_keeps_the_rest(self):
        os.environ['SOME_VARIABLE'] = 'kept'

        env = self._env(self.v4l2_compat)

        self.assertEqual(self.v4l2_compat, env['LD_PRELOAD'])
        self.assertEqual('kept', env['SOME_VARIABLE'])
        self.assertNotIn('LD_PRELOAD', os.environ)

    def test_added_to_other_preloaded_libraries(self):
        os.environ['LD_PRELOAD'] = '/usr/lib/a.so:/usr/lib/b.so'

        env = self._env(self.v4l2_compat)

        self.assertEqual(
            f'/usr/lib/a.so /usr/lib/b.so {self.v4l2_compat}', env['LD_PRELOAD']
        )

    def test_not_twice_when_motioneye_runs_under_libcamerify(self):
        preloaded = '/usr/libexec/aarch64-linux-gnu/libcamera/v4l2-compat.so'
        os.environ['LD_PRELOAD'] = preloaded

        self.assertEqual(preloaded, self._env(self.v4l2_compat)['LD_PRELOAD'])

    def test_a_missing_file_is_reported_once(self):
        missing = os.path.join(self.tmp, 'missing.so')
        with self.assertLogs(level='ERROR') as logs:
            self.assertIsNone(self._env(missing))
            self.assertIsNone(self._env(missing))

        self.assertEqual(
            [f'ERROR:root:libcamera_v4l2: {missing} not found, starting without it'],
            logs.output,
        )


class V4l2CtlEnvTest(unittest.TestCase):
    """The camera detection sees the cameras the way motion does."""

    def test_every_v4l2_ctl_call_gets_the_environment(self):
        env = {'LD_PRELOAD': '/v4l2-compat.so'}
        with (
            patch.object(utils, 'libcamera_v4l2_env', return_value=env),
            patch.object(utils, 'call_subprocess', return_value='') as call,
        ):
            v4l2ctl.list_devices()
            v4l2ctl._resolutions_cache.clear()
            v4l2ctl.list_resolutions('/dev/video0')
            v4l2ctl._ctrls_cache.clear()
            v4l2ctl.list_ctrls('/dev/video0')

        commands = [c.args[0] for c in call.call_args_list]
        self.assertEqual(3, len(commands))
        for c in call.call_args_list:
            with self.subTest(command=c.args[0]):
                self.assertIs(env, c.kwargs['env'])
                # libcamera logs to stderr, which must not end up in the parsed output
                self.assertEqual(subprocess.PIPE, c.kwargs['stderr'])


class V4l2CtlErrorTest(unittest.TestCase):
    """A failing v4l2-ctl call logs why and keeps what it printed before."""

    def setUp(self):
        v4l2ctl._ctrls_cache.clear()

    def test_list_devices_keeps_the_output_of_a_failed_call(self):
        error = subprocess.CalledProcessError(
            1,
            ['v4l2-ctl', '--list-devices'],
            output='USB Camera (usb-1):\n\t/dev/video0\n',
            stderr='Cannot open device /dev/video1\n',
        )
        with (
            patch.object(utils, 'call_subprocess', side_effect=error),
            patch.object(v4l2ctl, 'find_persistent_device', side_effect=lambda d: d),
            self.assertLogs(level='DEBUG') as logs,
        ):
            devices = v4l2ctl.list_devices()

        self.assertEqual([('/dev/video0', '/dev/video0', 'USB Camera')], devices)
        self.assertIn(
            'DEBUG:root:v4l2-ctl error: Cannot open device /dev/video1', logs.output
        )

    def test_list_devices_logs_a_missing_v4l2_ctl(self):
        error = FileNotFoundError(2, 'No such file or directory', 'v4l2-ctl')
        with (
            patch.object(utils, 'call_subprocess', side_effect=error),
            self.assertLogs(level='DEBUG') as logs,
        ):
            self.assertEqual([], v4l2ctl.list_devices())

        self.assertIn(f'DEBUG:root:v4l2-ctl error: {error}', logs.output)

    def test_list_ctrls_keeps_the_output_of_a_failed_call(self):
        error = subprocess.CalledProcessError(
            1,
            ['v4l2-ctl', '-d', '/dev/video0', '--list-ctrls'],
            output='                     brightness 0x00980900 (int)    : '
            'min=0 max=255 step=1 default=128 value=128\n',
            stderr='VIDIOC_QUERYCTRL: failed: Input/output error\n',
        )
        with (
            patch.object(utils, 'call_subprocess', side_effect=error),
            self.assertLogs(level='ERROR') as logs,
        ):
            controls = v4l2ctl.list_ctrls('/dev/video0')

        self.assertIn('brightness', controls)
        self.assertEqual(
            [
                (
                    'ERROR:root:failed to list controls of device "/dev/video0": '
                    'VIDIOC_QUERYCTRL: failed: Input/output error'
                )
            ],
            logs.output,
        )

    def test_list_resolutions_logs_why_it_failed(self):
        v4l2ctl._resolutions_cache.clear()
        error = OSError('cannot start the shell')
        with (
            patch.object(utils, 'call_subprocess', side_effect=error),
            self.assertLogs(level='ERROR') as logs,
        ):
            v4l2ctl.list_resolutions('/dev/video0')

        self.assertEqual(
            [
                (
                    'ERROR:root:failed to list resolutions of device "/dev/video0": '
                    'cannot start the shell'
                )
            ],
            logs.output,
        )


if __name__ == '__main__':
    unittest.main()
