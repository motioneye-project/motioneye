import unittest

from motioneye.utils import build_digest_header, parse_digest_challenge
from tests.test_utils import digest_params, digest_response

_CHALLENGE = 'Digest realm="cam", qop="auth,auth-int", nonce="n0nce", opaque="0paque"'


class ExpectedResponseTest(unittest.TestCase):
    """The helper the tests check against gives the RFC examples' responses."""

    def test_rfc_2617(self):
        params = {
            'username': 'Mufasa',
            'realm': 'testrealm@host.com',
            'nonce': 'dcd98b7102dd2f0e8b11d0f600bfb0c093',
            'uri': '/dir/index.html',
            'nc': '00000001',
            'cnonce': '0a4f113b',
        }
        self.assertEqual(
            '6629fae49393a05397450978507c4ef1',
            digest_response(params, 'GET', 'Circle Of Life'),
        )

    def test_rfc_7616(self):
        params = {
            'username': 'Mufasa',
            'realm': 'http-auth@example.org',
            'nonce': '7ypf/xlj9XXwfDPEoM4URrv/xwf94BcCAzFZH4GiTo0v',
            'uri': '/dir/index.html',
            'nc': '00000001',
            'cnonce': 'f2/wE4q74E6zIJEtWaHKaf5wv/H5QzzpXusqGemxURZJ',
        }
        for algorithm, response in (
            ('MD5', '8ca523f5e9506fed4657c9700eebdbec'),
            (
                'SHA-256',
                '753927fa0e85d155564e2e272a28d1802ca10daf4496794697cf8db5856cb6c1',
            ),
        ):
            with self.subTest(algorithm):
                self.assertEqual(
                    response,
                    digest_response(
                        {**params, 'algorithm': algorithm}, 'GET', 'Circle of Life'
                    ),
                )


class ParseDigestChallengeTest(unittest.TestCase):
    def test_quoted_values_may_hold_commas(self):
        self.assertEqual(
            {
                'realm': 'cam',
                'qop': 'auth,auth-int',
                'nonce': 'n0nce',
                'opaque': '0paque',
            },
            parse_digest_challenge([_CHALLENGE]),
        )

    def test_the_first_digest_challenge_is_taken(self):
        challenges = ['Basic realm="cam"', _CHALLENGE, 'Digest realm="b", nonce="b"']

        self.assertEqual('n0nce', parse_digest_challenge(challenges)['nonce'])

    def test_several_challenges_in_one_header_value(self):
        header = f'Basic realm="cam", {_CHALLENGE}, Bearer'
        self.assertEqual('n0nce', parse_digest_challenge([header])['nonce'])

        header = f'{_CHALLENGE}, Basic realm="other"'
        self.assertEqual('cam', parse_digest_challenge([header])['realm'])

        self.assertIsNone(parse_digest_challenge(['Basic realm="cam", Bearer']))

    def test_spaces_around_parameters_are_allowed(self):
        challenge = parse_digest_challenge(
            ['Digest realm = "cam" , nonce= "n" ,qop = auth']
        )

        self.assertEqual({'realm': 'cam', 'nonce': 'n', 'qop': 'auth'}, challenge)

    def test_an_empty_value_is_kept(self):
        challenge = parse_digest_challenge(['Digest realm="cam", nonce="n", opaque='])

        self.assertEqual('', challenge['opaque'])

    def test_none_without_a_usable_digest_challenge(self):
        for challenges in (
            [],
            ['Basic realm="cam"'],
            ['Digest realm="cam"'],  # no nonce
            ['Digest realm="cam", nonce'],  # not key=value
            ['Digest nonce="n"'],  # no realm
        ):
            with self.subTest(challenges):
                self.assertIsNone(parse_digest_challenge(challenges))


class BuildDigestHeaderTest(unittest.TestCase):
    def check(self, url, uri, algorithm=None):
        state = parse_digest_challenge([_CHALLENGE])
        if algorithm:
            state['algorithm'] = algorithm

        header = build_digest_header('GET', url, 'user', 'pw', state)
        params = digest_params(header)

        self.assertEqual(uri, params['uri'])
        self.assertEqual('auth', params['qop'])
        self.assertEqual('0paque', params['opaque'])
        self.assertEqual(digest_response(params, 'GET', 'pw'), params['response'])
        if algorithm:
            # algorithm, qop and nc are sent unquoted (RFC 7616, section 3.4)
            self.assertIn(f', algorithm={algorithm},', header)

    def test_the_uri_is_the_path_and_query(self):
        self.check('http://cam:8080/video.cgi?res=hi', '/video.cgi?res=hi')
        self.check(
            'http://cam:8080/video;jsessionid=1?res=hi', '/video;jsessionid=1?res=hi'
        )

    def test_an_empty_path_is_sent_as_a_slash(self):
        self.check('http://cam:8080', '/')

    def test_the_algorithms(self):
        for algorithm in ('MD5', 'MD5-sess', 'SHA-256', 'SHA-256-sess'):
            with self.subTest(algorithm):
                self.check('http://cam/', '/', algorithm)

    def test_qop_may_list_auth_with_spaces(self):
        state = {'realm': 'cam', 'nonce': 'n', 'qop': 'auth-int, auth'}

        params = digest_params(build_digest_header('GET', '/', 'user', 'pw', state))

        self.assertEqual(digest_response(params, 'GET', 'pw'), params['response'])

    def test_none_for_an_unknown_algorithm_or_without_qop_auth(self):
        for state in (
            {'realm': 'cam', 'nonce': 'n', 'algorithm': 'SHA-512-256'},
            {'realm': 'cam', 'nonce': 'n', 'qop': 'auth-int'},
        ):
            with self.subTest(state):
                self.assertIsNone(build_digest_header('GET', '/', 'u', 'p', state))


if __name__ == '__main__':
    unittest.main()
