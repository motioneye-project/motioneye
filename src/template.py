
from jinja2 import Environment, FileSystemLoader

import settings
import utils


_jinja_env = None


def _init_jinja():
    global _jinja_env
    
    _jinja_env = Environment(
            loader=FileSystemLoader(settings.TEMPLATE_PATH),
            trim_blocks=False)

    # globals
    _jinja_env.globals['settings'] = settings
    
    # filters
    _jinja_env.filters['pretty_date_time'] = utils.pretty_date_time
    _jinja_env.filters['pretty_date'] = utils.pretty_date
    _jinja_env.filters['pretty_time'] = utils.pretty_time
    _jinja_env.filters['pretty_duration'] = utils.pretty_duration


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
