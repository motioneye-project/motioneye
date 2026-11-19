from json import dumps, loads
from unittest.mock import patch
from urllib.parse import parse_qs

from motioneye import sendtelegram
from motioneye.handlers.config import ConfigHandler
from tests.test_handlers import HandlerTestCase


class TestTelegramTest(HandlerTestCase):
    handler_cls = ConfigHandler

    def _test_button(self, **fields):
        response = self.fetch(
            '/config/1/test/',
            method='POST',
            body=dumps(dict(what='telegram', api='fake', chatid='-42', **fields)),
            headers={
                'Cookie': self.make_session_cookie('admin'),
                'Content-Type': 'application/json',
            },
        )
        self.assertEqual(200, response.code)
        return loads(response.body)

    def test_button_sends_to_the_requested_topic_or_default_chat(self):
        for fields in ({'thread_id': '73'}, {}, {'thread_id': ''}):
            with (
                self.subTest(fields=fields),
                patch('motioneye.sendtelegram._post', return_value={}) as post,
            ):
                self.assertEqual({}, self._test_button(**fields))
                route, body, _, retry = post.call_args.args
                self.assertEqual('/botfake/sendMessage', route)
                self.assertFalse(retry)
                sent = parse_qs(body.decode())
                self.assertEqual(['-42'], sent['chat_id'])
                expected_topic = (
                    [fields['thread_id']] if fields.get('thread_id') else None
                )
                self.assertEqual(expected_topic, sent.get('message_thread_id'))

    def test_missing_topic_explains_how_to_choose_a_destination_without_resending(self):
        missing = 'Bad Request: message thread not found'
        for topic, description, expect_hint in (
            ('73', missing, True),
            ('73', 'Bad Request: chat not found', False),
            ('', missing, False),
        ):
            error = sendtelegram.TelegramError(400, description, None)
            with (
                self.subTest(topic=topic, description=description),
                patch('motioneye.sendtelegram._post_once', side_effect=error) as post,
            ):
                reply = self._test_button(thread_id=topic)['error']
                if expect_hint:
                    self.assertIn(str(error), reply)
                    self.assertIn('leave the ID blank', reply)
                    self.assertIn('General', reply)
                else:
                    self.assertEqual(str(error), reply)
                post.assert_called_once()
                fields = parse_qs(post.call_args.args[1])
                self.assertEqual([b'-42'], fields[b'chat_id'])
                self.assertEqual(
                    [b'73'] if topic else None, fields.get(b'message_thread_id')
                )
