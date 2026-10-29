from __future__ import annotations

import unittest

from motioneye import config
from tests.test_notification_settings import _UI, _ConfigCase

# the keys cameraUi2Dict() in 0.44.0's main.js can return, i.e. what that UI posts when a camera
# is saved (an Apply right after an upload service test leaves out upload_authorization_key).
# Frozen, so do not add new settings here.
_SENT_BY_0_44 = frozenset(
    {
        'admin_only',
        'auto_brightness',
        'auto_noise_detect',
        'auto_threshold_tuning',
        'capture_mode',
        'clean_cloud_enabled',
        'command_end_notifications_enabled',
        'command_end_notifications_exec',
        'command_notifications_enabled',
        'command_notifications_exec',
        'command_storage_enabled',
        'command_storage_exec',
        'create_debug_media',
        'custom_left_text',
        'custom_right_text',
        'despeckle_filter',
        'email_notifications_addresses',
        'email_notifications_enabled',
        'email_notifications_from',
        'email_notifications_picture_time_span',
        'email_notifications_smtp_account',
        'email_notifications_smtp_password',
        'email_notifications_smtp_port',
        'email_notifications_smtp_server',
        'email_notifications_smtp_tls',
        'enabled',
        'event_gap',
        'extra_options',
        'frame_change_threshold',
        'framerate',
        'friday_from',
        'friday_to',
        'image_file_name',
        'image_quality',
        'left_text',
        'light_switch_detect',
        'manual_snapshots',
        'max_frame_change_threshold',
        'max_movie_length',
        'minimum_motion_frames',
        'monday_from',
        'monday_to',
        'motion_detection',
        'motion_mask',
        'motion_mask_lines',
        'motion_mask_type',
        'movie_file_name',
        'movie_format',
        'movie_passthrough',
        'movie_quality',
        'movies',
        'name',
        'network_password',
        'network_server',
        'network_share_name',
        'network_smb_ver',
        'network_username',
        'noise_level',
        'post_capture',
        'pre_capture',
        'preserve_movies',
        'preserve_pictures',
        'privacy_mask',
        'privacy_mask_lines',
        'proto',
        'recording_mode',
        'resolution',
        'right_text',
        'root_directory',
        'rotation',
        'saturday_from',
        'saturday_to',
        'show_frame_changes',
        'smart_mask_sluggishness',
        'snapshot_interval',
        'still_images',
        'storage_device',
        'streaming_auth_mode',
        'streaming_framerate',
        'streaming_motion',
        'streaming_password',
        'streaming_port',
        'streaming_quality',
        'streaming_resolution',
        'streaming_server_resize',
        'streaming_username',
        'sunday_from',
        'sunday_to',
        'telegram_notifications_api',
        'telegram_notifications_chat_id',
        'telegram_notifications_enabled',
        'telegram_notifications_picture_time_span',
        'text_overlay',
        'text_scale',
        'thursday_from',
        'thursday_to',
        'tuesday_from',
        'tuesday_to',
        'upload_access_key',
        'upload_authorization_key',
        'upload_bucket',
        'upload_enabled',
        'upload_endpoint_url',
        'upload_location',
        'upload_method',
        'upload_movie',
        'upload_password',
        'upload_picture',
        'upload_port',
        'upload_secret_key',
        'upload_server',
        'upload_service',
        'upload_sse_c_key',
        'upload_subfolders',
        'upload_username',
        'video_controls',
        'video_streaming',
        'web_hook_end_notifications_enabled',
        'web_hook_end_notifications_http_method',
        'web_hook_end_notifications_url',
        'web_hook_notifications_enabled',
        'web_hook_notifications_http_method',
        'web_hook_notifications_url',
        'web_hook_storage_enabled',
        'web_hook_storage_http_method',
        'web_hook_storage_url',
        'wednesday_from',
        'wednesday_to',
        'working_schedule',
        'working_schedule_type',
    }
)
# a hub forwards that to a remote camera without admin_only, which stays local
_FORWARDED_BY_0_44 = _SENT_BY_0_44 - {'admin_only'}

# every camera setting such a hub does not forward, each away from its default; a setting
# added later belongs here too, so that the tests below check it is kept
_NOT_FORWARDED = {
    'admin_only': True,
    'upload_tls': True,
    'upload_verify': False,
    'clean_uploaded': True,
    'email_notifications_smtp_verify': False,
    'web_hook_notifications_verify': False,
    'web_hook_end_notifications_verify': False,
    'web_hook_storage_verify': False,
}
# what the camera answer carries besides settings
_NOT_SETTINGS = {
    'actions',
    'available_disks',
    'available_resolutions',
    'device_url',
    'disk_total',
    'disk_used',
    'id',
    'smb_shares',
}
_NOT_DEFAULT = {'@upload_tls': True, '@upload_verify': False, '@clean_uploaded': True}


def _as_older_hub_posts(ui):
    return {name: value for name, value in ui.items() if name in _FORWARDED_BY_0_44}


class OlderClientTest(_ConfigCase):
    """A camera config posted without the settings added after 0.44.0, as a hub running
    0.44 forwards it for a remote camera, is saved, and keeps what the camera has."""

    def test_a_post_without_the_new_settings_keeps_the_stored_values(self):
        changed = dict(self.camera, **_NOT_DEFAULT)
        defaults = {name: self.camera[name] for name in _NOT_DEFAULT}

        for stored, expected in ((self.camera, defaults), (changed, _NOT_DEFAULT)):
            with self.subTest(stored=expected):
                ui = _as_older_hub_posts(config.motion_camera_dict_to_ui(stored))
                data = config.motion_camera_ui_to_dict(ui, stored)

                self.assertEqual(expected, {name: data[name] for name in expected})

    def test_the_camera_file_is_unchanged_by_such_a_post(self):
        self._write(1, dict(self.camera, **_NOT_DEFAULT))
        self._post(self._get())  # the file as the server writes it
        text = self._read(1)
        for line in (
            '# @upload_tls on',
            '# @upload_verify off',
            '# @clean_uploaded on',
        ):
            self.assertIn(f'\n{line}\n', text)

        self._post(_as_older_hub_posts(self._get()))

        self.assertEqual(text, self._read(1))

    def test_a_post_with_the_new_settings_still_sets_them(self):
        ui = config.motion_camera_dict_to_ui(self.camera)
        ui.update(upload_tls=True, upload_verify=False, clean_uploaded=True)

        data = config.motion_camera_ui_to_dict(ui, self.camera)

        self.assertEqual(_NOT_DEFAULT, {name: data[name] for name in _NOT_DEFAULT})

    def test_a_save_from_a_0_44_hub_keeps_every_setting_it_does_not_forward(self):
        self._write(1, self.camera)
        self._post({**self._get(), **_UI, **_NOT_FORWARDED})  # notifications, webhooks
        text = self._read(1)
        got = self._get()
        self.assertEqual(_NOT_FORWARDED, {name: got[name] for name in _NOT_FORWARDED})

        self._post(_as_older_hub_posts(got))

        self.assertEqual(text, self._read(1))

    def test_every_setting_a_0_44_hub_does_not_forward_is_listed(self):
        self._write(1, self.camera)
        self._post({**self._get(), **_UI})  # notification settings show only while on
        ui = self._get()

        not_forwarded = set(ui) - _FORWARDED_BY_0_44 - _NOT_SETTINGS

        self.assertEqual(set(_NOT_FORWARDED), not_forwarded)


if __name__ == '__main__':
    unittest.main()
