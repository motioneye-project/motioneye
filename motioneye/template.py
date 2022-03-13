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

import gettext

from babel.support import Translations
from jinja2 import Environment, FileSystemLoader, select_autoescape

from motioneye import settings
from motioneye.utils.dtconv import (
    pretty_date,
    pretty_date_time,
    pretty_duration,
    pretty_time,
)

from .meyectl import traduction

_jinja_env = None


def _init_jinja():
    global _jinja_env

    #            loader=FileSystemLoader(searchpath="templates" ),
    _jinja_env = Environment(
        loader=FileSystemLoader(settings.TEMPLATE_PATH),
        trim_blocks=False,
        extensions=['jinja2.ext.i18n'],
        autoescape=select_autoescape(['html', 'xml']),
    )
    _jinja_env.install_gettext_translations(traduction, newstyle=True)

    # globals
    _jinja_env.globals['settings'] = settings

    # filters
    _jinja_env.filters['pretty_date_time'] = pretty_date_time
    _jinja_env.filters['pretty_date'] = pretty_date
    _jinja_env.filters['pretty_time'] = pretty_time
    _jinja_env.filters['pretty_duration'] = pretty_duration


def add_template_path(path):
    global _jinja_env
    if _jinja_env is None:
        _init_jinja()

    _jinja_env.loader.searchpath.append(path)


def add_context(name, value):
    global _jinja_env
    if _jinja_env is None:
        _init_jinja()

    _jinja_env.globals[name] = value


def render(template_name, **context):
    global _jinja_env
    if _jinja_env is None:
        _init_jinja()

    template = _jinja_env.get_template(template_name)
    return template.render(**context)
