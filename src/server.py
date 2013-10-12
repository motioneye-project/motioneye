
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
        (r'^/config/(?P<camera_id>\d+)/(?P<op>get|set|rem|set_preview)/?$', handlers.ConfigHandler),
        (r'^/config/(?P<op>add|list|list_devices)/?$', handlers.ConfigHandler),
        (r'^/snapshot/(?P<camera_id>\d+)/(?P<op>current|list)/?$', handlers.SnapshotHandler),
        (r'^/snapshot/(?P<camera_id>\d+)/(?P<op>download)/(?P<filename>.+)/?$', handlers.SnapshotHandler),
        (r'^/movie/(?P<camera_id>\d+)/(?P<op>list)/?$', handlers.MovieHandler),
        (r'^/movie/(?P<camera_id>\d+)/(?P<op>download)/(?P<filename>.+)/?$', handlers.MovieHandler),
    ],
    debug=settings.DEBUG,
    log_function=log_request,
    static_path=settings.STATIC_PATH,
    static_url_prefix=settings.STATIC_URL
)

template.add_context('STATIC_URL', settings.STATIC_URL)
