from __future__ import annotations

import unittest
from io import BytesIO
from json import loads
from unittest.mock import AsyncMock, MagicMock, patch

import tornado.testing
from tornado.httpclient import HTTPClientError, HTTPRequest, HTTPResponse

from motioneye import config, motionctl, settings
from motioneye.handlers.action import ActionHandler
from motioneye.utils import CommonExternalResponse, GetMotionDetectionResult
from tests.test_handlers import (
    _FAKE_CAMERA_CONFIG,
    _FAKE_CAMERA_ID,
    _FAKE_REMOTE_CAMERA_CONFIG,
    HandlerTestCase,
    RemoteCameraTestCase,
)

# the id motion knows camera 1 by
_MOTION_CAMERA_ID = 7

# action => path of the request to motion's control interface it ends up in
_MOTION_PATHS = {
    'snapshot': f'{_MOTION_CAMERA_ID}/action/snapshot',
    'eventstart': f'{_MOTION_CAMERA_ID}/action/eventstart',
    'eventend': f'{_MOTION_CAMERA_ID}/action/eventend',
    'detectionstart': f'{_MOTION_CAMERA_ID}/detection/start',
    'detectionpause': f'{_MOTION_CAMERA_ID}/detection/pause',
}

# action => how the error message starts when motion could not be told to do it
_FAILED = {
    'snapshot': f"failed to trigger 'snapshot' action for camera {_FAKE_CAMERA_ID}",
    'eventstart': f"failed to trigger 'eventstart' action for camera {_FAKE_CAMERA_ID}",
    'eventend': f"failed to trigger 'eventend' action for camera {_FAKE_CAMERA_ID}",
    'detectionstart': f'failed to start motion detection for camera {_FAKE_CAMERA_ID}',
    'detectionpause': f'failed to pause motion detection for camera {_FAKE_CAMERA_ID}',
}


def _motion_answer(code=200, body=b''):
    return HTTPResponse(HTTPRequest('http://127.0.0.1/'), code, buffer=BytesIO(body))


class _PostsActions:
    def post(self, action, user='admin'):
        return self.fetch(
            f'/action/{_FAKE_CAMERA_ID}/{action}',
            method='POST',
            body='',
            headers={'Cookie': self.make_session_cookie(user)},
        )


class _LocalActionCase(_PostsActions, HandlerTestCase):
    """Camera 1 is run by the local motion, which answers what the test sets."""

    handler_cls = ActionHandler

    def setUp(self):
        super().setUp()
        self.client = MagicMock()
        self.motion_answers(return_value=_motion_answer())
        for p in (
            patch('motioneye.motionctl.AsyncHTTPClient', return_value=self.client),
            patch(
                'motioneye.motionctl.camera_id_to_motion_camera_id',
                return_value=_MOTION_CAMERA_ID,
            ),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(motionctl._motion_detection.clear)
        self.addCleanup(motionctl._motion_detected.clear)

    def motion_answers(self, **kwargs):
        self.client.fetch = AsyncMock(**kwargs)

    @staticmethod
    def motion_url(path):
        return f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{path}'

    def requested_url(self):
        return self.client.fetch.call_args.args[0].url


class LocalActionTest(_LocalActionCase):
    """The actions for a camera of the local motion are passed on to motion."""

    def test_every_action_is_passed_on_to_the_motion_control_interface(self):
        for action, path in _MOTION_PATHS.items():
            with self.subTest(action):
                self.motion_answers(return_value=_motion_answer())

                response = self.post(action)

                self.assertEqual(200, response.code)
                self.assertEqual({'error': None}, loads(response.body))
                self.client.fetch.assert_awaited_once()
                self.assertEqual(self.motion_url(path), self.requested_url())

    def test_pausing_the_detection_ends_the_motion_detected_state(self):
        motionctl.set_motion_detected(_FAKE_CAMERA_ID, True)

        self.post('detectionstart')

        self.assertTrue(motionctl.is_motion_detected(_FAKE_CAMERA_ID))

        self.post('detectionpause')

        self.assertFalse(motionctl.is_motion_detected(_FAKE_CAMERA_ID))

    def test_the_detection_status_follows_the_actions_without_asking_motion(self):
        for action, enabled in (('detectionpause', False), ('detectionstart', True)):
            with self.subTest(action):
                self.post(action)
                self.motion_answers(return_value=_motion_answer())

                status = self.io_loop.run_sync(
                    lambda: motionctl.get_motion_detection(_FAKE_CAMERA_ID)
                )

                self.assertEqual(GetMotionDetectionResult(enabled, None), status)
                self.client.fetch.assert_not_called()

    def test_a_failed_action_reports_why(self):
        failures = {
            'motion is not reachable': (
                {'side_effect': HTTPClientError(599, 'Connection refused')},
                'Connection refused',
            ),
            'motion answers with an error': (
                {'return_value': _motion_answer(500)},
                'Internal Server Error',
            ),
            'motion does not know the action': (
                {'return_value': _motion_answer(200, b'Bad Request: unknown action')},
                'Bad Request',
            ),
        }
        for action in _MOTION_PATHS:
            for failure, (answer, reason) in failures.items():
                with self.subTest(action=action, failure=failure):
                    self.motion_answers(**answer)

                    with self.assertLogs(level='ERROR'):
                        response = self.post(action)

                    self.assertEqual(200, response.code)
                    error = loads(response.body)['error']
                    self.assertTrue(error.startswith(_FAILED[action]), error)
                    self.assertIn(reason, error)

    def test_an_unknown_motion_camera_is_reported_without_asking_motion(self):
        unknown = patch(
            'motioneye.motionctl.camera_id_to_motion_camera_id', return_value=None
        )
        for action in _MOTION_PATHS:
            with self.subTest(action), unknown, self.assertLogs(level='ERROR'):
                response = self.post(action)

                self.assertEqual(200, response.code)
                self.assertEqual(
                    {
                        'error': 'could not find motion camera id for camera '
                        f'{_FAKE_CAMERA_ID}'
                    },
                    loads(response.body),
                )
                self.client.fetch.assert_not_called()

    def test_a_failed_detection_action_leaves_the_status_to_be_asked_again(self):
        self.motion_answers(side_effect=HTTPClientError(599, 'Connection refused'))
        with self.assertLogs(level='ERROR'):
            self.post('detectionpause')
        self.motion_answers(
            return_value=_motion_answer(200, b'Camera 7 Detection status ACTIVE')
        )

        status = self.io_loop.run_sync(
            lambda: motionctl.get_motion_detection(_FAKE_CAMERA_ID)
        )

        self.assertEqual(GetMotionDetectionResult(True, None), status)

    def test_other_actions_are_not_passed_on(self):
        # the removed recording actions, the keys the UI lists its buttons by,
        # and near misses of the actions above
        for action in (
            'bogus',
            'record_start',
            'record_stop',
            'detection',
            'detectionstop',
            'motion_event',
            'motion_detection',
        ):
            with self.subTest(action):
                response = self.post(action)

                self.assertEqual(400, response.code)
                self.client.fetch.assert_not_called()

    def test_a_trailing_slash_after_the_action_is_accepted(self):
        # hubs of older versions address the actions of a remote camera this way
        response = self.post('detectionstart/')

        self.assertEqual(200, response.code)
        self.assertEqual(
            self.motion_url(_MOTION_PATHS['detectionstart']), self.requested_url()
        )

    def test_the_keys_the_ui_lists_its_buttons_by_are_not_runnable_actions(self):
        # they only tell the UI to show the buttons, which post the actions above
        _FAKE_CAMERA_CONFIG.update(
            {'@motion_event_button': True, '@motion_detection_button': True}
        )
        self.addCleanup(_FAKE_CAMERA_CONFIG.pop, '@motion_event_button')
        self.addCleanup(_FAKE_CAMERA_CONFIG.pop, '@motion_detection_button')

        for action in ('motion_event', 'motion_detection'):
            with self.subTest(action):
                response = self.post(action)

                self.assertEqual(400, response.code)
                self.client.fetch.assert_not_called()


class AdminOnlyActionTest(_LocalActionCase):
    """Every action of an admin-only camera is refused to a normal user."""

    def tearDown(self):
        _FAKE_CAMERA_CONFIG['@admin_only'] = False
        super().tearDown()

    def test_a_normal_user_is_denied_every_action(self):
        _FAKE_CAMERA_CONFIG['@admin_only'] = True
        for action in _MOTION_PATHS:
            with self.subTest(action):
                response = self.post(action, user='normal')

                self.assertEqual(403, response.code)
                self.assertIn('admin-only', loads(response.body)['error'])
                self.client.fetch.assert_not_called()

    def test_an_admin_is_allowed_every_action(self):
        _FAKE_CAMERA_CONFIG['@admin_only'] = True
        for action, path in _MOTION_PATHS.items():
            with self.subTest(action):
                response = self.post(action, user='admin')

                self.assertEqual(200, response.code)
                self.assertEqual(self.motion_url(path), self.requested_url())

    def test_a_normal_user_may_use_the_actions_of_any_other_camera(self):
        for action, path in _MOTION_PATHS.items():
            with self.subTest(action):
                response = self.post(action, user='normal')

                self.assertEqual(200, response.code)
                self.assertEqual(self.motion_url(path), self.requested_url())


class RemoteActionTest(_PostsActions, RemoteCameraTestCase):
    """The actions for a remote camera go to the remote motionEye, by the same name."""

    handler_cls = ActionHandler

    def setUp(self):
        super().setUp()
        self.exec_action = AsyncMock(return_value=CommonExternalResponse())
        self.motion_client = MagicMock()
        for p in (
            patch('motioneye.remote.exec_action', self.exec_action),
            patch('motioneye.motionctl.AsyncHTTPClient', self.motion_client),
        ):
            p.start()
            self.addCleanup(p.stop)

    def test_every_action_is_passed_on_to_the_remote_unchanged(self):
        for action in _MOTION_PATHS:
            with self.subTest(action):
                self.exec_action.reset_mock()

                response = self.post(action)

                self.assertEqual(200, response.code)
                self.assertEqual({}, loads(response.body))
                self.exec_action.assert_awaited_once_with(
                    _FAKE_REMOTE_CAMERA_CONFIG, action
                )
                self.motion_client.assert_not_called()

    def test_a_failed_remote_action_reports_why(self):
        self.exec_action.return_value = CommonExternalResponse(
            error='request timed out'
        )
        for action in _MOTION_PATHS:
            with self.subTest(action):
                response = self.post(action)

                self.assertEqual(200, response.code)
                error = loads(response.body)['error']
                self.assertTrue(
                    error.startswith('Failed to execute action on remote camera at '),
                    error,
                )
                self.assertTrue(error.endswith(': request timed out.'), error)


class ActionButtonsTest(unittest.TestCase):
    """The camera config lists the buttons the UI shows, by the keys main.js knows."""

    def test_the_buttons_are_listed_when_enabled(self):
        actions = config.get_action_commands(
            {'@id': 1, '@motion_event_button': True, '@motion_detection_button': True}
        )

        self.assertIn('motion_event', actions)
        self.assertIn('motion_detection', actions)

    def test_the_buttons_are_not_listed_by_default(self):
        actions = config.get_action_commands({'@id': 1})

        self.assertNotIn('motion_event', actions)
        self.assertNotIn('motion_detection', actions)

    def test_each_button_is_enabled_on_its_own(self):
        event_only = config.get_action_commands(
            {'@id': 1, '@motion_event_button': True}
        )
        detection_only = config.get_action_commands(
            {'@id': 1, '@motion_detection_button': True}
        )

        self.assertEqual(
            (True, False),
            ('motion_event' in event_only, 'motion_detection' in event_only),
        )
        self.assertEqual(
            (False, True),
            ('motion_event' in detection_only, 'motion_detection' in detection_only),
        )


if __name__ == '__main__':
    tornado.testing.main()
