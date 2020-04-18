from dataclasses import dataclass
from typing import TypedDict, Union


__all__ = ('URLDataDict', 'RtmpUrl', 'RtspUrl', 'MjpegUrl')


class URLDataDict(TypedDict):
    scheme: str
    host: str
    port: str
    path: str
    username: str
    password: str


@dataclass
class StreamUrl:
    scheme: str
    port: str
    host: str = '127.0.0.1'
    path: str = ''
    username: Union[None, str] = None
    password: Union[None, str] = None

    _tpl = '%(scheme)s://%(host)s%(port)s%(path)s'

    def __str__(self):
        return self._tpl % dict(scheme=self.scheme, host=self.host, port=(':' + self.port) if self.port else '',
                                path=self.path, username=self.username, password=self.password)


@dataclass
class RtmpUrl(StreamUrl):
    scheme: str = 'rtmp'
    port: str = '1935'


@dataclass
class RtspUrl(StreamUrl):
    scheme: str = 'rtsp'
    port: str = '554'


@dataclass
class MjpegUrl(StreamUrl):
    scheme: str = 'http'
    port: str = '80'
