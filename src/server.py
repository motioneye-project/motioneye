
from tornado.web import Application

import handlers
import settings
import template


application = Application(
    [
        (r'^/$', handlers.HomeHandler),
    ],
    debug=settings.DEBUG,
    static_path=settings.STATIC_PATH,
    static_url_prefix=settings.STATIC_URL
)

template.add_context('STATIC_URL', settings.STATIC_URL)
