
from tornado.web import RequestHandler

import template


class BaseHandler(RequestHandler):
    def render(self, template_name, content_type='text/html', **context):
        self.set_header('Content-Type', content_type)
        
        content = template.render(template_name, **context)
        self.finish(content)


class HomeHandler(BaseHandler):
    def get(self):
        self.render('home.html')
