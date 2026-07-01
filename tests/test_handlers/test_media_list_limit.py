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

"""Tests verifying the optional 'limit' query parameter parsing in the media list endpoints."""

import json
from unittest.mock import AsyncMock, patch

from motioneye.handlers.movie import MovieHandler
from motioneye.handlers.picture import PictureHandler
from tests.test_handlers import HandlerTestCase


class _MediaListLimitTests:
    media_type: str

    def _fetch_list(self, qs=''):
        cookie = self.make_session_cookie('admin')
        with patch(
            'motioneye.mediafiles.list_media', new=AsyncMock(return_value=[])
        ) as list_media:
            response = self.fetch(
                f'/{self.media_type}/1/list/{qs}', headers={'Cookie': cookie}
            )

        self.assertEqual(200, response.code)
        self.assertEqual([], json.loads(response.body)['mediaList'])
        return list_media.call_args.kwargs

    def test_no_limit_defaults_to_none(self):
        kwargs = self._fetch_list()
        self.assertIsNone(kwargs['limit'])
        self.assertTrue(kwargs['with_stat'])

    def test_positive_limit_is_passed_through(self):
        kwargs = self._fetch_list('?with_stat=false&limit=1')
        self.assertEqual(kwargs['limit'], 1)
        self.assertFalse(kwargs['with_stat'])

    def test_invalid_limit_values_are_ignored(self):
        for qs in ('?limit=abc', '?limit=0', '?limit=-5', '?limit='):
            with self.subTest(qs=qs):
                kwargs = self._fetch_list(qs)
                self.assertIsNone(kwargs['limit'])


class PictureListLimitTest(_MediaListLimitTests, HandlerTestCase):
    handler_cls = PictureHandler
    media_type = 'picture'


class MovieListLimitTest(_MediaListLimitTests, HandlerTestCase):
    handler_cls = MovieHandler
    media_type = 'movie'
