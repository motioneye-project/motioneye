
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

from tornado.web import Application

import handlers
import logging
import settings
import template


def log_request(handler):
    if handler.get_status() < 400:
        log_method = logging.debug
    
    elif handler.get_status() < 500:
        log_method = logging.warning
    
    else:
        log_method = logging.error
    
    request_time = 1000.0 * handler.request.request_time()
    log_method("%d %s %.2fms", handler.get_status(),
               handler._request_summary(), request_time)


application = Application(
    [
        (r'^/$', handlers.MainHandler),
        (r'^/config/main/(?P<op>set|get)/?$', handlers.ConfigHandler),
        (r'^/config/(?P<camera_id>\d+)/(?P<op>get|set|rem|set_preview|_relay_event)/?$', handlers.ConfigHandler),
        (r'^/config/(?P<op>add|list|list_devices)/?$', handlers.ConfigHandler),
        (r'^/picture/(?P<camera_id>\d+)/(?P<op>current|list|frame)/?$', handlers.PictureHandler),
        (r'^/picture/(?P<camera_id>\d+)/(?P<op>download|preview|delete)/(?P<filename>.+?)/?$', handlers.PictureHandler),
        (r'^/picture/(?P<camera_id>\d+)/(?P<op>zipped|timelapse)/(?P<group>.+?)/?$', handlers.PictureHandler),
        (r'^/movie/(?P<camera_id>\d+)/(?P<op>list)/?$', handlers.MovieHandler),
        (r'^/movie/(?P<camera_id>\d+)/(?P<op>download|preview|delete)/(?P<filename>.+?)/?$', handlers.MovieHandler),
        (r'^/update/?$', handlers.UpdateHandler),
        (r'^/power/(?P<op>shutdown)/?$', handlers.PowerHandler),
        (r'^/version/?$', handlers.VersionHandler),
        (r'^.*$', handlers.NotFoundHandler),
    ],
    debug=False,
    log_function=log_request,
    static_path=settings.STATIC_PATH,
    static_url_prefix=settings.STATIC_URL
)

template.add_context('STATIC_URL', settings.STATIC_URL)
