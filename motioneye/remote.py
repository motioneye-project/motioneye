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

import json
import logging
import re

from typing import Union

from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPResponse

from motioneye import settings
from motioneye import utils

_DOUBLE_SLASH_REGEX = re.compile('//+')


def _make_request(scheme, host, port, username, password, path, method='GET', data=None, query=None,
                  timeout=None, content_type=None):
    path = _DOUBLE_SLASH_REGEX.sub('/', path)
    url = '%(scheme)s://%(host)s%(port)s%(path)s' % {
        'scheme': scheme,
        'host': host,
        'port': ':' + str(port) if port else '',
        'path': path or ''}

    query = dict(query or {})
    query['_username'] = username or ''
    query['_admin'] = 'true'  # always use the admin account

    if url.count('?'):
        url += '&'

    else:
        url += '?'

    url += '&'.join([(n + '=' + v) for (n, v) in list(query.items())])
    url += '&_signature=' + utils.compute_signature(method, url, data, password)

    if timeout is None:
        timeout = settings.REMOTE_REQUEST_TIMEOUT

    headers = {}
    if content_type:
        headers['Content-Type'] = content_type

    return HTTPRequest(url, method, body=data, connect_timeout=timeout, request_timeout=timeout, headers=headers,
                       validate_cert=settings.VALIDATE_CERTS)


async def _send_request(request: HTTPRequest) -> HTTPResponse:
    response = await AsyncHTTPClient().fetch(request)

    try:
        decoded = json.loads(response.body)
        if decoded['error'] == 'unauthorized':
            response.error = 'Authentication Error'

        elif decoded['error']:
            response.error = decoded['error']

    except:
        pass

    return response


def pretty_camera_url(local_config, camera=True):
    scheme = local_config.get('@scheme', local_config.get('scheme')) or 'http'
    host = local_config.get('@host', local_config.get('host'))
    port = local_config.get('@port', local_config.get('port'))
    path = local_config.get('@path', local_config.get('path')) or ''

    url = scheme + '://' + host
    if port and str(port) not in ['80', '443']:
        url += ':' + str(port)

    if path:
        url += path

    if url.endswith('/'):
        url = url[:-1]

    if camera:
        if camera is True:
            url += '/config/' + str(local_config.get('@remote_camera_id', local_config.get('remote_camera_id')))

        else:
            url += '/config/' + str(camera)

    return url


def _remote_params(local_config):
    params = [
        local_config.get('@scheme', local_config.get('scheme')) or 'http',
        local_config.get('@host', local_config.get('host')),
        local_config.get('@port', local_config.get('port')),
        local_config.get('@username', local_config.get('username')),
        local_config.get('@password', local_config.get('password')),
        local_config.get('@path', local_config.get('path')) or '',
        local_config.get('@remote_camera_id', local_config.get('remote_camera_id'))]

    if params[3] is not None:
        params[3] = str(params[3])

    if params[4] is not None:
        params[4] = str(params[4])

    return params


def make_camera_response(c):
    return {
        'id': c['id'],
        'name': c['name']
    }


async def list_cameras(local_config) -> utils.GetCamerasResponse:
    scheme, host, port, username, password, path, _ = _remote_params(local_config)

    logging.debug('listing remote cameras on %(url)s' % {
        'url': pretty_camera_url(local_config, camera=False)})

    request = _make_request(scheme, host, port, username, password,
                            path + '/config/list/')

    response = await _send_request(request)

    if response.error:
        logging.error('failed to list remote cameras on %(url)s: %(msg)s' % {
            'url': pretty_camera_url(local_config, camera=False),
            'msg': utils.pretty_http_error(response)})

        return utils.GetCamerasResponse(None, utils.pretty_http_error(response))

    try:
        response = json.loads(response.body)

    except Exception as e:
        logging.error('failed to decode json answer from %(url)s: %(msg)s' % {
            'url': pretty_camera_url(local_config, camera=False),
            'msg': str(e)})

        return utils.GetCamerasResponse(None, str(e))
    
    else:

        cameras = response['cameras']
    
        # filter out simple mjpeg cameras
        cameras = [make_camera_response(c) for c in cameras if c['proto'] != 'mjpeg' and c.get('enabled')]
    
        return utils.GetCamerasResponse(cameras, None)


async def get_config(local_config) -> utils.GetConfigResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    logging.debug('getting config for remote camera %(id)s on %(url)s' % {
        'id': camera_id,
        'url': pretty_camera_url(local_config)})

    request = _make_request(scheme, host, port, username, password,
                            path + '/config/%(id)s/get/' % {'id': camera_id})
    response = await _send_request(request)

    if response.error:
        logging.error('failed to get config for remote camera %(id)s on %(url)s: %(msg)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config),
            'msg': utils.pretty_http_error(response)})

        return utils.GetConfigResponse(None, error=utils.pretty_http_error(response))

    try:
        response = json.loads(response.body)

    except Exception as e:
        logging.error('failed to decode json answer from %(url)s: %(msg)s' % {
            'url': pretty_camera_url(local_config),
            'msg': str(e)})

        return utils.GetConfigResponse(None, error=str(e))
    
    else:
        response['host'] = host
        response['port'] = port

        return utils.GetConfigResponse(remote_ui_config=response, error=None)


async def set_config(local_config, ui_config) -> Union[str, None]:
    scheme = local_config.get('@scheme', local_config.get('scheme'))
    host = local_config.get('@host', local_config.get('host'))
    port = local_config.get('@port', local_config.get('port'))
    username = local_config.get('@username', local_config.get('username'))
    password = local_config.get('@password', local_config.get('password'))
    path = local_config.get('@path', local_config.get('path')) or ''
    camera_id = local_config.get('@remote_camera_id', local_config.get('remote_camera_id'))

    logging.debug('setting config for remote camera %(id)s on %(url)s' % {
        'id': camera_id,
        'url': pretty_camera_url(local_config)})

    ui_config = json.dumps(ui_config)

    p = path + '/config/%(id)s/set/' % {'id': camera_id}
    request = _make_request(scheme, host, port, username, password, p,
                            method='POST', data=ui_config, content_type='application/json')
    response = await _send_request(request)

    result = None

    if response.error:
        logging.error('failed to set config for remote camera %(id)s on %(url)s: %(msg)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config),
            'msg': utils.pretty_http_error(response)})

        result = utils.pretty_http_error(response)

    return result


async def test(local_config, data) -> utils.CommonExternalResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)
    what = data['what']
    logging.debug('testing %(what)s on remote camera %(id)s, on %(url)s' % {
        'what': what,
        'id': camera_id,
        'url': pretty_camera_url(local_config)})

    data = json.dumps(data)

    p = path + '/config/%(id)s/test/' % {'id': camera_id}
    request = _make_request(scheme, host, port, username, password, p,
                            method='POST', data=data, content_type='application/json')
    response = await _send_request(request)
    if response.error:
        logging.error('failed to test %(what)s on remote camera %(id)s, on %(url)s: %(msg)s' % {
            'what': what,
            'id': camera_id,
            'url': pretty_camera_url(local_config),
            'msg': utils.pretty_http_error(response)})

        return utils.CommonExternalResponse(None, error=utils.pretty_http_error(response))

    return utils.CommonExternalResponse(None, None)  # it will never return result = True, what the point?


async def get_current_picture(local_config, width, height) -> utils.GetCurrentPictureResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    logging.debug('getting current picture for remote camera %(id)s on %(url)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config)})

    query = {}

    if width:
        query['width'] = str(width)

    if height:
        query['height'] = str(height)

    p = path + '/picture/%(id)s/current/' % {'id': camera_id}
    
    request = _make_request(scheme, host, port, username, password, p, query=query)
    response = await _send_request(request)
    
    cookies = utils.parse_cookies(response.headers.get_list('Set-Cookie'))
    motion_detected = cookies.get('motion_detected_' + str(camera_id)) == 'true'
    capture_fps = cookies.get('capture_fps_' + str(camera_id))
    capture_fps = float(capture_fps) if capture_fps else 0
    monitor_info = cookies.get('monitor_info_' + str(camera_id))

    if response.error:
        logging.error('failed to get current picture for remote camera %(id)s on %(url)s: %(msg)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config),
            'msg': utils.pretty_http_error(response)})

        return utils.GetCurrentPictureResponse(error=utils.pretty_http_error(response))

    return utils.GetCurrentPictureResponse(motion_detected=motion_detected, capture_fps=capture_fps,
                                           monitor_info=monitor_info, picture=response.body)


async def list_media(local_config, media_type, prefix) -> utils.ListMediaResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    logging.debug('getting media list for remote camera %(id)s on %(url)s' % {
        'id': camera_id,
        'url': pretty_camera_url(local_config)})

    query = {}
    if prefix is not None:
        query['prefix'] = prefix

    # timeout here is 10 times larger than usual - we expect a big delay when fetching the media list
    p = path + '/%(media_type)s/%(id)s/list/' % {'id': camera_id, 'media_type': media_type}
    request = _make_request(scheme, host, port, username, password, p, query=query,
                            timeout=10 * settings.REMOTE_REQUEST_TIMEOUT)
    response = await _send_request(request)
    if response.error:
        logging.error('failed to get media list for remote camera %(id)s on %(url)s: %(msg)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config),
            'msg': utils.pretty_http_error(response)})

        return utils.ListMediaResponse(error=utils.pretty_http_error(response))

    try:
        response = json.loads(response.body)

    except Exception as e:
        logging.error('failed to decode json answer from %(url)s: %(msg)s' % {
            'url': pretty_camera_url(local_config),
            'msg': str(e)})

        return utils.ListMediaResponse(error=str(e))

    return utils.ListMediaResponse(media_list=response)


async def get_media_content(local_config, filename, media_type) -> utils.CommonExternalResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    logging.debug('downloading file %(filename)s of remote camera %(id)s on %(url)s' % {
        'filename': filename,
        'id': camera_id,
        'url': pretty_camera_url(local_config)})

    path += '/%(media_type)s/%(id)s/download/%(filename)s' % {
        'media_type': media_type,
        'id': camera_id,
        'filename': filename}

    # timeout here is 10 times larger than usual - we expect a big delay when fetching the media list
    request = _make_request(scheme, host, port, username, password,
                            path, timeout=10 * settings.REMOTE_REQUEST_TIMEOUT)
    response = await _send_request(request)
    if response.error:
        logging.error('failed to download file %(filename)s of remote camera %(id)s on %(url)s: %(msg)s' % {
            'filename': filename,
            'id': camera_id,
            'url': pretty_camera_url(local_config),
            'msg': utils.pretty_http_error(response)})

        return utils.CommonExternalResponse(error=utils.pretty_http_error(response))

    return utils.CommonExternalResponse(result=response.body)


async def make_zipped_content(local_config, media_type, group) -> utils.CommonExternalResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    logging.debug('preparing zip file for group "%(group)s" of remote camera %(id)s on %(url)s' % {
        'group': group or 'ungrouped',
        'id': camera_id,
        'url': pretty_camera_url(local_config)})

    prepare_path = path + '/%(media_type)s/%(id)s/zipped/%(group)s/' % {
        'media_type': media_type,
        'id': camera_id,
        'group': group}

    # timeout here is 100 times larger than usual - we expect a big delay
    request = _make_request(scheme, host, port, username, password,
                            prepare_path, timeout=100 * settings.REMOTE_REQUEST_TIMEOUT)
    response = await _send_request(request)
    if response.error:
        msg = 'failed to prepare zip file for group "%(group)s" ' \
              'of remote camera %(id)s on %(url)s: %(msg)s' % {
                  'group': group or 'ungrouped',
                  'id': camera_id,
                  'url': pretty_camera_url(local_config),
                  'msg': utils.pretty_http_error(response)}

        logging.error(msg)

        return utils.CommonExternalResponse(error=utils.pretty_http_error(response))

    try:
        key = json.loads(response.body)['key']

    except Exception as e:
        logging.error('failed to decode json answer from %(url)s: %(msg)s' % {
            'url': pretty_camera_url(local_config),
            'msg': str(e)})

        return utils.CommonExternalResponse(error=str(e))
    else:
        return utils.CommonExternalResponse(result={'key': key})


async def get_zipped_content(local_config, media_type, key, group) -> utils.CommonExternalResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    logging.debug('downloading zip file for remote camera %(id)s on %(url)s' % {
        'id': camera_id,
        'url': pretty_camera_url(local_config)})

    p = path + '/%(media_type)s/%(id)s/zipped/%(group)s/?key=%(key)s' % {
        'media_type': media_type,
        'group': group,
        'id': camera_id,
        'key': key}

    request = _make_request(scheme, host, port, username, password, p,
                            timeout=10 * settings.REMOTE_REQUEST_TIMEOUT)
    response = await _send_request(request)
    if response.error:
        logging.error('failed to download zip file for remote camera %(id)s on %(url)s: %(msg)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config),
            'msg': utils.pretty_http_error(response)})

        return utils.CommonExternalResponse(error=utils.pretty_http_error(response))

    return utils.CommonExternalResponse(result={
        'data': response.body,
        'content_type': response.headers.get('Content-Type'),
        'content_disposition': response.headers.get('Content-Disposition')
    })


async def make_timelapse_movie(local_config, framerate, interval, group) -> utils.CommonExternalResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    msg = 'making timelapse movie for group "%(group)s" of remote camera %(id)s ' \
          'with rate %(framerate)s/%(int)s on %(url)s' % {
              'group': group or 'ungrouped',
              'id': camera_id,
              'framerate': framerate,
              'int': interval,
              'url': pretty_camera_url(local_config)}

    logging.debug(msg)

    path += '/picture/%(id)s/timelapse/%(group)s/?interval=%(int)s&framerate=%(framerate)s' % {
        'id': camera_id,
        'int': interval,
        'framerate': framerate,
        'group': group}

    request = _make_request(scheme, host, port, username, password,
                            path, timeout=100 * settings.REMOTE_REQUEST_TIMEOUT)
    response = await _send_request(request)
    if response.error:
        msg = 'failed to make timelapse movie for group "%(group)s" of remote camera %(id)s ' \
              'with rate %(framerate)s/%(int)s on %(url)s: %(msg)s' % {
                  'group': group or 'ungrouped',
                  'id': camera_id,
                  'url': pretty_camera_url(local_config),
                  'int': interval,
                  'framerate': framerate,
                  'msg': utils.pretty_http_error(response)}

        logging.error(msg)

        return utils.CommonExternalResponse(error=utils.pretty_http_error(response))

    try:
        response = json.loads(response.body)

    except Exception as e:
        logging.error('failed to decode json answer from %(url)s: %(msg)s' % {
            'url': pretty_camera_url(local_config),
            'msg': str(e)})

        return utils.CommonExternalResponse(error=str(e))

    else:
        return utils.CommonExternalResponse(result=response)


async def check_timelapse_movie(local_config, group) -> utils.CommonExternalResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    logging.debug('checking timelapse movie status for remote camera %(id)s on %(url)s' % {
        'id': camera_id,
        'url': pretty_camera_url(local_config)})

    p = path + '/picture/%(id)s/timelapse/%(group)s/?check=true' % {
        'id': camera_id,
        'group': group}
    request = _make_request(scheme, host, port, username, password, p)
    response = await _send_request(request)
    
    if response.error:
        logging.error('failed to check timelapse movie status for remote camera %(id)s on %(url)s: %(msg)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config),
            'msg': utils.pretty_http_error(response)})

        return utils.CommonExternalResponse(error=utils.pretty_http_error(response))

    try:
        response = json.loads(response.body)

    except Exception as e:
        logging.error('failed to decode json answer from %(url)s: %(msg)s' % {
            'url': pretty_camera_url(local_config),
            'msg': str(e)})

        return utils.CommonExternalResponse(error=str(e))

    else:
        return utils.CommonExternalResponse(result=response)


async def get_timelapse_movie(local_config, key, group) -> utils.CommonExternalResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    logging.debug('downloading timelapse movie for remote camera %(id)s on %(url)s' % {
        'id': camera_id,
        'url': pretty_camera_url(local_config)})

    p = path + '/picture/%(id)s/timelapse/%(group)s/?key=%(key)s' % {
        'id': camera_id,
        'group': group,
        'key': key}

    request = _make_request(scheme, host, port, username, password, p,
                            timeout=10 * settings.REMOTE_REQUEST_TIMEOUT)
    response = await _send_request(request)
    if response.error:
        logging.error('failed to download timelapse movie for remote camera %(id)s on %(url)s: %(msg)s' % {
            'id': camera_id,
            'url': pretty_camera_url(local_config),
            'msg': utils.pretty_http_error(response)})

        return utils.CommonExternalResponse(error=utils.pretty_http_error(response))

    return utils.CommonExternalResponse(result={
        'data': response.body,
        'content_type': response.headers.get('Content-Type'),
        'content_disposition': response.headers.get('Content-Disposition')
    })


async def get_media_preview(local_config, filename, media_type, width, height) -> utils.CommonExternalResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    logging.debug('getting file preview for %(filename)s of remote camera %(id)s on %(url)s' % {
        'filename': filename,
        'id': camera_id,
        'url': pretty_camera_url(local_config)})

    path += '/%(media_type)s/%(id)s/preview/%(filename)s' % {
        'media_type': media_type,
        'id': camera_id,
        'filename': filename}

    query = {}

    if width:
        query['width'] = str(width)

    if height:
        query['height'] = str(height)

    request = _make_request(scheme, host, port, username, password, path, query=query)
    response = await _send_request(request)
    if response.error:
        logging.error('failed to get file preview for %(filename)s of remote camera %(id)s on %(url)s: %(msg)s' % {
            'filename': filename,
            'id': camera_id,
            'url': pretty_camera_url(local_config),
            'msg': utils.pretty_http_error(response)})

        return utils.CommonExternalResponse(error=utils.pretty_http_error(response))

    return utils.CommonExternalResponse(result=response.body)


async def del_media_content(local_config, filename, media_type) -> utils.CommonExternalResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    logging.debug('deleting file %(filename)s of remote camera %(id)s on %(url)s' % {
        'filename': filename,
        'id': camera_id,
        'url': pretty_camera_url(local_config)})

    path += '/%(media_type)s/%(id)s/delete/%(filename)s' % {
        'media_type': media_type,
        'id': camera_id,
        'filename': filename}

    request = _make_request(scheme, host, port, username, password, path, method='POST', data='{}',
                            timeout=settings.REMOTE_REQUEST_TIMEOUT, content_type='application/json')
    response = await _send_request(request)
    if response.error:
        logging.error('failed to delete file %(filename)s of remote camera %(id)s on %(url)s: %(msg)s' % {
            'filename': filename,
            'id': camera_id,
            'url': pretty_camera_url(local_config),
            'msg': utils.pretty_http_error(response)})

        return utils.CommonExternalResponse(error=utils.pretty_http_error(response))

    return utils.CommonExternalResponse()


async def del_media_group(local_config, group, media_type) -> utils.CommonExternalResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    logging.debug('deleting group "%(group)s" of remote camera %(id)s on %(url)s' % {
        'group': group or 'ungrouped',
        'id': camera_id,
        'url': pretty_camera_url(local_config)})

    path += '/%(media_type)s/%(id)s/delete_all/%(group)s/' % {
        'media_type': media_type,
        'id': camera_id,
        'group': group}

    request = _make_request(scheme, host, port, username, password, path, method='POST', data='{}',
                            timeout=settings.REMOTE_REQUEST_TIMEOUT, content_type='application/json')
    response = await _send_request(request)
    if response.error:
        logging.error('failed to delete group "%(group)s" of remote camera %(id)s on %(url)s: %(msg)s' % {
            'group': group or 'ungrouped',
            'id': camera_id,
            'url': pretty_camera_url(local_config),
            'msg': utils.pretty_http_error(response)})

        return utils.CommonExternalResponse(error=utils.pretty_http_error(response))

    return utils.CommonExternalResponse()


async def exec_action(local_config, action) -> utils.CommonExternalResponse:
    scheme, host, port, username, password, path, camera_id = _remote_params(local_config)

    logging.debug('executing action "%(action)s" of remote camera %(id)s on %(url)s' % {
        'action': action,
        'id': camera_id,
        'url': pretty_camera_url(local_config)})

    path += '/action/%(id)s/%(action)s/' % {
        'action': action,
        'id': camera_id}

    request = _make_request(scheme, host, port, username, password, path, method='POST', data='{}',
                            timeout=settings.REMOTE_REQUEST_TIMEOUT, content_type='application/json')
    response = await _send_request(request)
    if response.error:
        logging.error('failed to execute action "%(action)s" of remote camera %(id)s on %(url)s: %(msg)s' % {
            'action': action,
            'id': camera_id,
            'url': pretty_camera_url(local_config),
            'msg': utils.pretty_http_error(response)})

        return utils.CommonExternalResponse(error=utils.pretty_http_error(response))

    return utils.CommonExternalResponse()
