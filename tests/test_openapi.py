import json
import os
import re
from itertools import product
from unittest import TestCase

from tornado.testing import AsyncHTTPTestCase

from motioneye import VERSION, settings
from motioneye.server import handler_mapping, make_app

# routes that are not part of the API: the web UI itself, and what only
# motion and other motionEye servers call
_NOT_DOCUMENTED = {
    r'^/$',
    r'^/manifest.json$',
    r'^/openapi.json$',
    r'^/_relay_event/?$',
    r'^.*$',
}

_GROUP = re.compile(r'\(\?P<(\w+)>([^()]*)\)(\?)?')


def load_spec() -> dict:
    with open(os.path.join(settings.PROJECT_PATH, 'openapi.json')) as f:
        return json.load(f)


def documented_paths(pattern: str) -> set[str]:
    """Turn a route of the handler mapping into the OpenAPI paths it serves.

    A group listing its values, such as (?P<op>get|set), gives one path per
    value; any other group, such as (?P<camera_id>\\d+), becomes a parameter;
    an optional group gives the path with and without it.
    """

    path = pattern.removeprefix('^').removesuffix('$').removesuffix('/?')
    pieces = _GROUP.split(path)
    literals, groups = pieces[::4], list(zip(pieces[1::4], pieces[2::4], pieces[3::4]))

    choices = []
    for name, body, optional in groups:
        if re.fullmatch(r'\w+(\|\w+)*', body):
            options = body.split('|')
        else:
            options = ['{' + name + '}']
        if optional:
            options.append('')
        choices.append(options)

    paths = set()
    for chosen in product(*choices):
        path = literals[0] + ''.join(c + lit for c, lit in zip(chosen, literals[1:]))
        paths.add(re.sub('/+', '/', path.rstrip('/') + '/'))

    return paths


class OpenApiSpecTest(TestCase):
    def test_every_route_is_documented(self):
        spec_paths = set(load_spec()['paths'])
        routes = set()
        for route in handler_mapping:
            if route[0] not in _NOT_DOCUMENTED:
                routes |= documented_paths(route[0])

        self.assertEqual(set(), routes - spec_paths, 'routes missing from the spec')
        self.assertEqual(set(), spec_paths - routes, 'spec paths with no route')

    def test_route_expansion(self):
        self.assertEqual(
            {'/config/main/get/', '/config/main/set/'},
            documented_paths(r'^/config/main/(?P<op>set|get)/?$'),
        )
        # no route has an optional group today, but one would be expanded so
        self.assertEqual(
            {'/things/', '/things/{key}/'},
            documented_paths(r'^/things/(?P<key>\w+)?/?$'),
        )
        self.assertEqual(
            {'/picture/{camera_id}/delete/{filename}/'},
            documented_paths(
                r'^/picture/(?P<camera_id>\d+)/(?P<op>delete)/(?P<filename>.+?)/?$'
            ),
        )

    def test_operations_have_a_summary_tag_and_success_response(self):
        spec = load_spec()
        tags = {tag['name'] for tag in spec['tags']}
        for path, operations in spec['paths'].items():
            for method, operation in operations.items():
                with self.subTest(path=path, method=method):
                    self.assertIn(method, ('get', 'post'))
                    self.assertTrue(operation['summary'])
                    self.assertTrue(set(operation['tags']) <= tags)
                    self.assertTrue(
                        any(code[0] in '23' for code in operation['responses'])
                    )


class OpenApiHandlerTest(AsyncHTTPTestCase):
    def get_app(self):
        return make_app()

    def test_served_without_signing_in_with_the_running_version(self):
        response = self.fetch('/openapi.json')

        self.assertEqual(200, response.code)
        self.assertEqual('application/json', response.headers['Content-Type'])
        spec = json.loads(response.body)
        self.assertEqual('3.1.0', spec['openapi'])
        self.assertEqual(VERSION, spec['info']['version'])
        self.assertEqual(load_spec()['paths'], spec['paths'])
