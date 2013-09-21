
from tornado.web import Application

import handlers
import settings
import template


application = Application(
    [
        (r'^/$', handlers.MainHandler),
        (r'^/config/(?P<camera_id>\w+)/(?P<op>get|set|rem)/?$', handlers.ConfigHandler),
        (r'^/config/(?P<op>add)/?$', handlers.ConfigHandler),
        (r'^/snapshot/(?P<camera_id>\w+)/(?P<op>current|list)/?$', handlers.SnapshotHandler),
        (r'^/snapshot/(?P<camera_id>\w+)/(?P<op>download)/(?P<filename>.+)/?$', handlers.SnapshotHandler),
        (r'^/movie/(?P<camera_id>\w+)/(?P<op>list)/?$', handlers.MovieHandler),
        (r'^/movie/(?P<camera_id>\w+)/(?P<op>download)/(?P<filename>.+)/?$', handlers.MovieHandler),
    ],
    debug=settings.DEBUG,
    static_path=settings.STATIC_PATH,
    static_url_prefix=settings.STATIC_URL
)

template.add_context('STATIC_URL', settings.STATIC_URL)
