import os
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


if __name__ == '__main__':
    unittest.main()
