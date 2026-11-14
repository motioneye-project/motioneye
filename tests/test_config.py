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
from __future__ import annotations

import os
import tarfile
import unittest
from io import BytesIO
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

from motioneye import config, settings


class TestBackup(unittest.TestCase):
    """Tests for config.backup()."""

    conf_dir: str

    @classmethod
    def setUpClass(cls):
        cls.conf_dir = mkdtemp()
        cls._orig_conf_path = settings.CONF_PATH
        settings.CONF_PATH = cls.conf_dir

    @classmethod
    def tearDownClass(cls):
        settings.CONF_PATH = cls._orig_conf_path
        rmtree(cls.conf_dir)

    def setUp(self):
        # Clean the config dir before each test
        for name in os.listdir(self.conf_dir):
            os.remove(os.path.join(self.conf_dir, name))

    def _create_files(self, *names: str) -> None:
        for name in names:
            open(os.path.join(self.conf_dir, name), 'a').close()

    def _assert_tarball_members(self, data: bytes | None, expected: list[str]) -> None:
        if data is None:
            self.fail('tarball data is None')

        with tarfile.open(fileobj=BytesIO(data)) as tf:
            members = tf.getnames()
        self.assertEqual(sorted(members), sorted(expected))

    def test_backup_includes_motion_conf(self):
        self._create_files('motion.conf')

        data = config.backup()
        self._assert_tarball_members(data, ['motion.conf'])

    def test_backup_includes_camera_confs(self):
        self._create_files('camera-1.conf', 'camera-2.conf')

        data = config.backup()
        self._assert_tarball_members(data, ['camera-1.conf', 'camera-2.conf'])

    def test_backup_includes_mask_files(self):
        self._create_files('mask_1.pgm', 'mask_2.pgm')

        data = config.backup()
        self._assert_tarball_members(data, ['mask_1.pgm', 'mask_2.pgm'])

    def test_backup_excludes_other_files(self):
        self._create_files(
            'motion.conf',
            'uploadservices.json',
            'secrets.json',
            'motioneye.conf',
            'prefs.json',  # left by older versions, the preferences are in the browser now
        )

        data = config.backup()
        self._assert_tarball_members(data, ['motion.conf'])

    def test_backup_empty_dir_returns_empty_tarball(self):
        data = config.backup()
        self._assert_tarball_members(data, [])


class TestRestore(unittest.TestCase):
    """Tests for config.restore()."""

    conf_dir: str

    @classmethod
    def setUpClass(cls):
        cls.conf_dir = mkdtemp()
        cls._orig_conf_path = settings.CONF_PATH
        cls._orig_enable_reboot = settings.ENABLE_REBOOT
        settings.CONF_PATH = cls.conf_dir
        settings.ENABLE_REBOOT = False

    @classmethod
    def tearDownClass(cls):
        settings.CONF_PATH = cls._orig_conf_path
        settings.ENABLE_REBOOT = cls._orig_enable_reboot
        rmtree(cls.conf_dir)

    def setUp(self):
        # Clean the config dir before each test
        for name in os.listdir(self.conf_dir):
            os.remove(os.path.join(self.conf_dir, name))

    def _make_tarball(self, *names: str) -> bytes:
        """Create an in-memory .tar.gz with the given file names as empty members."""
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as tf:
            for name in names:
                member = tarfile.TarInfo(name)
                member.size = 0
                tf.addfile(member)
        return buf.getvalue()

    def _make_tarball_members(self, *members: tarfile.TarInfo) -> bytes:
        """Create an in-memory .tar.gz with the given raw members."""
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as tf:
            for member in members:
                tf.addfile(member)
        return buf.getvalue()

    def _assert_restored_files(self, *expected: str) -> None:
        self.assertEqual(sorted(os.listdir(self.conf_dir)), sorted(expected))

    def test_restore_extracts_motion_conf(self):
        tarball = self._make_tarball('motion.conf')

        config.restore(tarball)
        self._assert_restored_files('motion.conf')

    def test_restore_extracts_camera_confs(self):
        tarball = self._make_tarball('camera-1.conf', 'camera-42.conf')

        config.restore(tarball)
        self._assert_restored_files('camera-1.conf', 'camera-42.conf')

    def test_restore_extracts_mask_files(self):
        tarball = self._make_tarball('mask_1.pgm', 'mask_2.pgm')

        config.restore(tarball)
        self._assert_restored_files('mask_1.pgm', 'mask_2.pgm')

    def test_restore_ignores_non_matching_files(self):
        tarball = self._make_tarball(
            'motion.conf',
            'uploadservices.json',
            'secrets.json',
            'motioneye.conf',
            'prefs.json',  # in backups of older versions
        )

        config.restore(tarball)
        self._assert_restored_files('motion.conf')

    def test_restore_ignores_non_regular_members(self):
        motion_config = tarfile.TarInfo(name='motion.conf')
        motion_config.size = 0

        camera_symlink = tarfile.TarInfo(name='camera-9.conf')
        camera_symlink.type = tarfile.SYMTYPE
        camera_symlink.linkname = 'motion.conf'

        mask_hardlink = tarfile.TarInfo(name='mask_9.pgm')
        mask_hardlink.type = tarfile.LNKTYPE
        mask_hardlink.linkname = 'motion.conf'

        tarball = self._make_tarball_members(
            motion_config, camera_symlink, mask_hardlink
        )

        config.restore(tarball)
        self._assert_restored_files('motion.conf')

    def test_restore_ignores_absolute_paths(self):
        tarball = self._make_tarball(
            '/motion.conf',
            '/camera-1.conf',
            '/mask_1.pgm',
            '/prefs.json',
            'motion.conf',
        )

        config.restore(tarball)
        self._assert_restored_files('motion.conf')

    def test_restore_ignores_pattern_matches_with_path_elements(self):
        tarball = self._make_tarball(
            'camera-1.conf',
            'mask_1.pgm',
            'subdir/camera-2.conf',
            'camera-3.conf/extra',
            './subdir/camera-4.conf',
            '../camera-5.conf',
            'subdir/mask_2.pgm',
            './subdir/mask_3.pgm',
            '../mask_4.pgm',
        )

        config.restore(tarball)
        self._assert_restored_files('camera-1.conf', 'mask_1.pgm')

    def test_restore_accepts_dot_slash_prefix(self):
        """Tarball entries prefixed with ./ (e.g. from GNU tar) should still be accepted."""
        tarball = self._make_tarball('./motion.conf')

        config.restore(tarball)
        self._assert_restored_files('motion.conf')

    def test_restore_returns_reboot_false(self):
        tarball = self._make_tarball('motion.conf')

        result = config.restore(tarball)
        self.assertEqual(result, {'reboot': False})

    def test_restore_invalid_data_returns_none(self):
        result = config.restore(b'not a tarball')
        self.assertIsNone(result)


class TestNetcamParams(unittest.TestCase):
    def test_keeps_other_entries_as_an_extra_option(self):
        data = {
            'netcam_params': 'decoder = drm,keepalive = off, capture_rate = 5,tolerant_check = on'
        }
        config.adapt_config_directives(data, config._MOTION_44_TO_43_OPTIONS_MAPPING)

        self.assertEqual(
            {
                'netcam_keepalive': False,
                'netcam_tolerant_check': True,
                'netcam_params': 'decoder = drm, capture_rate = 5',
            },
            data,
        )

    def test_writes_other_entries_back_with_the_known_ones(self):
        line = 'decoder = drm,keepalive = off,tolerant_check = on,rtsp_transport = tcp'
        data = {'netcam_params': line}
        config.adapt_config_directives(data, config._MOTION_44_TO_43_OPTIONS_MAPPING)
        config.adapt_config_directives(data, config._MOTION_43_TO_44_OPTIONS_MAPPING)

        self.assertEqual({'netcam_params': line}, data)

    def test_adds_no_extra_option_without_other_entries(self):
        data = {
            'netcam_params': 'keepalive = on,tolerant_check = off,rtsp_transport = udp'
        }
        config.adapt_config_directives(data, config._MOTION_44_TO_43_OPTIONS_MAPPING)

        self.assertEqual(
            {
                'netcam_keepalive': True,
                'netcam_tolerant_check': False,
                'netcam_use_tcp': False,
            },
            data,
        )


class TestThresholdPixels(unittest.TestCase):
    def test_percent_of_the_frame(self):
        self.assertEqual(4608, config._threshold_pixels('1.5', 640, 480))

    def test_zero_percent_is_one_pixel(self):
        # with threshold 0, Motion does not detect motion at all (#1895)
        self.assertEqual(1, config._threshold_pixels('0', 640, 480))

    def test_less_than_a_pixel_is_one_pixel(self):
        self.assertEqual(1, config._threshold_pixels(0.1, 32, 24))


class TestVideoParams(unittest.TestCase):
    def test_keeps_motion_parameters_as_the_options_before_motion_44(self):
        data = {'video_params': 'palette=15,brightness=10, input = 1,"Gain"=50'}
        config.adapt_config_directives(data, config._MOTION_44_TO_43_OPTIONS_MAPPING)

        self.assertEqual(
            {
                'vid_control_params': 'brightness=10,"Gain"=50',
                'v4l2_palette': '15',
                'input': '1',
            },
            data,
        )

    def test_writes_motion_parameters_back_with_the_controls(self):
        line = 'palette=15,norm=0,brightness=10,"Gain, Automatic"=1'
        data = {'video_params': line}
        config.adapt_config_directives(data, config._MOTION_44_TO_43_OPTIONS_MAPPING)
        config.adapt_config_directives(data, config._MOTION_43_TO_44_OPTIONS_MAPPING)

        self.assertEqual({'video_params': line}, data)

    def test_writes_options_of_motion_43_as_parameters(self):
        # as read from a file of motion < 4.4, in any order
        data = {'frequency': 0, 'vid_control_params': 'brightness=10'}
        data.update(v4l2_palette=15, input=-1, norm=0)
        config.adapt_config_directives(data, config._MOTION_43_TO_44_OPTIONS_MAPPING)

        self.assertEqual(
            {'video_params': 'frequency=0,palette=15,input=-1,norm=0,brightness=10'},
            data,
        )

    def test_a_quoted_control_name_may_hold_a_comma(self):
        data = {'video_params': '"Norm, Auto"=1,norm=0'}
        config.adapt_config_directives(data, config._MOTION_44_TO_43_OPTIONS_MAPPING)

        self.assertEqual({'vid_control_params': '"Norm, Auto"=1', 'norm': '0'}, data)

    def test_adds_no_option_with_controls_only(self):
        data = {'video_params': 'brightness=10,contrast=20'}
        config.adapt_config_directives(data, config._MOTION_44_TO_43_OPTIONS_MAPPING)

        self.assertEqual({'vid_control_params': 'brightness=10,contrast=20'}, data)

    def test_writes_a_palette_without_controls(self):
        data = {'vid_control_params': '', 'v4l2_palette': 8}
        config.adapt_config_directives(data, config._MOTION_43_TO_44_OPTIONS_MAPPING)

        self.assertEqual({'video_params': 'palette=8'}, data)

    def test_matches_motion_parameters_case_sensitively(self):
        data = {'video_params': 'Palette=15,palette=8'}
        config.adapt_config_directives(data, config._MOTION_44_TO_43_OPTIONS_MAPPING)

        self.assertEqual(
            {'vid_control_params': 'Palette=15', 'v4l2_palette': '8'}, data
        )

    def test_a_line_without_controls_keeps_vid_control_params(self):
        data = {'vid_control_params': 'brightness=10', 'video_params': 'palette=8'}
        config.adapt_config_directives(data, config._MOTION_44_TO_43_OPTIONS_MAPPING)

        self.assertEqual(
            {'vid_control_params': 'brightness=10', 'v4l2_palette': '8'}, data
        )

    def test_a_lone_number_is_not_converted(self):
        data = config._conf_to_dict(
            ['video_params 1', 'vid_control_params on'],
            no_convert=['vid_control_params', 'video_params'],
        )

        self.assertEqual({'video_params': '1', 'vid_control_params': 'on'}, data)


class TestVideoParamsSave(unittest.TestCase):
    # a V4L2 camera with a palette set through Extra Options, saved through its file
    motion_post43 = True

    def setUp(self):
        self.conf_dir = mkdtemp()
        self.addCleanup(rmtree, self.conf_dir)
        config.invalidate()
        self.addCleanup(config.invalidate)
        main_config = {}
        config._set_default_motion(main_config)
        controls = {
            'brightness': {
                'min': 0,
                'max': 255,
                'value': 128,
                'control_id': 'ID09963776',
            }
        }
        for target, kwargs in (
            ('builtins._', {'new': str, 'create': True}),
            ('motioneye.config.get_main', {'return_value': main_config}),
            ('motioneye.config.set_main', {}),
            ('motioneye.settings.CONF_PATH', {'new': self.conf_dir}),
            ('motioneye.meyectl.find_command', {'return_value': 'meyectl'}),
            ('motioneye.mediafiles.find_ffmpeg', {'return_value': (None, None, None)}),
            ('motioneye.motionctl.is_motion_pre42', {'return_value': False}),
            (
                'motioneye.motionctl.is_motion_post43',
                {'return_value': self.motion_post43},
            ),
            ('motioneye.utils.get_disk_usage', {'return_value': None}),
            ('motioneye.controls.diskctl.list_mounted_disks', {'return_value': []}),
            ('motioneye.controls.v4l2ctl.list_ctrls', {'return_value': controls}),
            (
                'motioneye.controls.v4l2ctl.list_resolutions',
                {'return_value': [(640, 480)]},
            ),
        ):
            patcher = patch(target, **kwargs)
            self.addCleanup(patcher.stop)
            patcher.start()

        camera = {'@id': 1, '@enabled': True, 'videodevice': '/dev/video0'}
        camera.update(width=640, height=480)
        config._set_default_motion_camera(1, camera)
        camera['target_dir'] = self.conf_dir
        camera['video_params'] = 'palette=15,ID09963776=10'
        config.adapt_config_directives(camera, config._MOTION_44_TO_43_OPTIONS_MAPPING)
        config.set_camera(1, camera)

    def _get(self):
        config._camera_config_cache.pop(1, None)
        return config.motion_camera_dict_to_ui(config.get_camera(1))

    def _video_params(self):
        with open(os.path.join(self.conf_dir, 'camera-1.conf')) as f:
            return [
                line
                for line in f.read().splitlines()
                if line.startswith(('video_params', 'vid_control_params', 'v4l2_'))
            ]

    def _save(self, ui):
        config.set_camera(1, config.motion_camera_ui_to_dict(ui, config.get_camera(1)))

    def test_the_palette_shows_in_extra_options(self):
        ui = self._get()

        self.assertIn(('video_params', 'palette=15'), ui['extra_options'])
        self.assertNotIn('v4l2_palette', dict(ui['extra_options']))
        self.assertEqual(10, ui['video_controls']['brightness']['value'])

    def test_a_save_keeps_the_palette(self):
        ui = self._get()
        ui['video_controls']['brightness']['value'] = 20
        self._save(ui)

        self.assertEqual(
            ['video_params palette=15,ID09963776=20'], self._video_params()
        )

    def test_an_entered_palette_is_saved_and_shows_the_same(self):
        ui = self._get()
        ui['extra_options'] = [('video_params', 'palette=8, input = 1')]
        self._save(ui)

        self.assertEqual(
            ['video_params palette=8,input=1,ID09963776=10'], self._video_params()
        )
        self.assertEqual(
            [('video_params', 'palette=8,input=1')], self._get()['extra_options']
        )

    def test_removing_the_extra_option_removes_the_palette(self):
        ui = self._get()
        ui['extra_options'] = []
        self._save(ui)

        self.assertEqual(['video_params ID09963776=10'], self._video_params())

    def test_an_option_of_motion_43_shows_as_it_is_saved(self):
        # e.g. from a file last saved for motion < 4.4
        ui = self._get()
        ui['extra_options'] = [('v4l2_palette', '8')]
        self._save(ui)

        self.assertEqual(['video_params palette=8,ID09963776=10'], self._video_params())
        self.assertEqual([('video_params', 'palette=8')], self._get()['extra_options'])

    def test_failing_to_list_the_shown_controls_is_a_warning(self):
        ui = self._get()
        ui['video_controls']['brightness']['value'] = 20
        with (
            patch('motioneye.controls.v4l2ctl.list_ctrls', return_value={}),
            self.assertLogs(level='WARNING') as logs,
        ):
            self._save(ui)

        self.assertEqual(
            ['WARNING:root:camera 1 control listing failed, controls not updated'],
            logs.output,
        )
        # the stored value is kept
        self.assertEqual(10, self._get()['video_controls']['brightness']['value'])

    def test_a_camera_without_controls_is_no_warning(self):
        # as seen through libcamera's V4L2 layer, where the page shows no controls
        with patch('motioneye.controls.v4l2ctl.list_ctrls', return_value={}):
            ui = self._get()
            with patch('motioneye.config.logging.warning') as warning:
                self._save(ui)

        self.assertEqual({}, ui['video_controls'])
        warning.assert_not_called()


class TestVideoParamsSavePre44(TestVideoParamsSave):
    # the same camera, with its file brought to a motion which has no video_params
    motion_post43 = False

    def test_the_palette_shows_in_extra_options(self):
        ui = self._get()

        self.assertEqual([('v4l2_palette', 15)], ui['extra_options'])
        self.assertEqual(10, ui['video_controls']['brightness']['value'])

    def test_a_save_keeps_the_palette(self):
        for value in (20, 30):  # the second save starts from the rewritten file
            ui = self._get()
            ui['video_controls']['brightness']['value'] = value
            self._save(ui)

            self.assertEqual(
                ['v4l2_palette 15', f'vid_control_params ID09963776={value}'],
                sorted(self._video_params()),
            )
            self.assertEqual(
                value, self._get()['video_controls']['brightness']['value']
            )

    def test_an_entered_palette_is_saved_and_shows_the_same(self):
        ui = self._get()
        ui['extra_options'] = [('video_params', 'palette=8')]
        self._save(ui)

        self.assertEqual(
            ['v4l2_palette 8', 'vid_control_params ID09963776=10'],
            sorted(self._video_params()),
        )
        self.assertEqual([('v4l2_palette', 8)], self._get()['extra_options'])

    def test_removing_the_extra_option_removes_the_palette(self):
        ui = self._get()
        ui['extra_options'] = []
        self._save(ui)

        self.assertEqual(['vid_control_params ID09963776=10'], self._video_params())

    def test_an_option_of_motion_43_shows_as_it_is_saved(self):
        ui = self._get()
        ui['extra_options'] = [('v4l2_palette', '8')]
        self._save(ui)

        self.assertEqual(
            ['v4l2_palette 8', 'vid_control_params ID09963776=10'],
            sorted(self._video_params()),
        )
        self.assertEqual([('v4l2_palette', 8)], self._get()['extra_options'])


class TestDefaultMotion(unittest.TestCase):
    def test_control_interface_cannot_change_parameters_by_default(self):
        data = {}
        config._set_default_motion(data)

        self.assertEqual(0, data['webcontrol_parms'])

    def test_keeps_stored_control_interface_parameters(self):
        # existing installations keep what is stored in motion.conf
        data = {'webcontrol_parms': 2}
        config._set_default_motion(data)

        self.assertEqual(2, data['webcontrol_parms'])


class TestDefaultMovieCodec(unittest.TestCase):
    def _default(self):
        data = {}
        config._set_default_motion_camera(1, data)
        return data['movie_codec']

    def test_new_cameras_record_h264_in_software(self):
        # ffmpeg lists these encoders without the hardware behind them (#2504)
        for encoder in ('has_h264_omx_support', 'has_h264_v4l2m2m_support'):
            with (
                self.subTest(encoder),
                patch(f'motioneye.motionctl.{encoder}', return_value=True),
            ):
                self.assertEqual('mp4', self._default())

    def test_keeps_a_stored_codec(self):
        data = {'movie_codec': 'mp4:h264_v4l2m2m'}
        config._set_default_motion_camera(1, data)

        self.assertEqual('mp4:h264_v4l2m2m', data['movie_codec'])
