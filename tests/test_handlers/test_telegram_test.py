from json import dumps, loads
from unittest.mock import patch
from urllib.parse import parse_qs

from motioneye.handlers.config import ConfigHandler
from tests.test_handlers import HandlerTestCase


class TestTelegramTest(HandlerTestCase):
    handler_cls = ConfigHandler

    def test_button_sends_to_the_requested_topic_or_default_chat(self):
        for fields in ({'thread_id': '73'}, {}, {'thread_id': ''}):
            with (
                self.subTest(fields=fields),
                patch('motioneye.sendtelegram._post', return_value={}) as post,
            ):
                response = self.fetch(
                    '/config/1/test/',
                    method='POST',
                    body=dumps(
                        dict(what='telegram', api='fake', chatid='-42', **fields)
                    ),
                    headers={
                        'Cookie': self.make_session_cookie('admin'),
                        'Content-Type': 'application/json',
                    },
                )
                self.assertEqual(200, response.code)
                self.assertEqual({}, loads(response.body))
                route, body, _, retry = post.call_args.args
                self.assertEqual('/botfake/sendMessage', route)
                self.assertFalse(retry)
                sent = parse_qs(body.decode())
                self.assertEqual(['-42'], sent['chat_id'])
                expected_topic = (
                    [fields['thread_id']] if fields.get('thread_id') else None
                )
                self.assertEqual(expected_topic, sent.get('message_thread_id'))
