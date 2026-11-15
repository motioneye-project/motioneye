import hashlib
from urllib.request import parse_http_list, parse_keqv_list

_HASHES = {
    'MD5': 'md5',
    'MD5-SESS': 'md5',
    'SHA-256': 'sha256',
    'SHA-256-SESS': 'sha256',
}


def digest_params(header: str) -> dict:
    """The parameters of an 'Authorization: Digest ...' header."""
    return parse_keqv_list(parse_http_list(header.removeprefix('Digest ')))


def digest_response(params: dict, method: str, password: str) -> str:
    """The response a server expects for these parameters, with qop=auth."""
    algorithm = params.get('algorithm', 'MD5').upper()

    def h(text):
        return hashlib.new(_HASHES[algorithm], text.encode()).hexdigest()

    ha1 = h(f"{params['username']}:{params['realm']}:{password}")
    if algorithm.endswith('-SESS'):
        ha1 = h(f"{ha1}:{params['nonce']}:{params['cnonce']}")

    ha2 = h(f"{method}:{params['uri']}")
    return h(f"{ha1}:{params['nonce']}:{params['nc']}:{params['cnonce']}:auth:{ha2}")
