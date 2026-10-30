"""Hub/remote check between two motionEye installations, e.g. a release and HEAD.

Starts a remote motionEye server with one network camera, fed by a local picture
server, and a hub that shows that camera as a remote motionEye camera. Then talks to
the hub's HTTP API as its web UI does: list the cameras, get the camera's config,
fetch a current picture, list the media, and save the camera twice. Each save posts
exactly the keys the hub's own UI sends, read from cameraUi2Dict() in the hub's
main.js. The second save must leave the remote's camera file unchanged apart from the
camera name (and the text overlay that shows it). A third save does what the Home
Assistant integration does: post the whole fetched config back with web hooks set.

Tracebacks in the server logs are reported separately from these API checks, and fail
the run too unless --ignore-tracebacks is given.

Usage: python3 tests/hub_remote_compat.py --hub VENV --remote VENV [--ignore-tracebacks]
Each VENV is a virtual environment with motionEye installed; motion must be in PATH.
"""

from __future__ import annotations

import argparse
import difflib
import http.client
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

HUB_PORT = 18765
REMOTE_PORT = 18766
HUB_MOTION_PORT = 17999
REMOTE_MOTION_PORT = 17998
STREAM_PORT = 18082
PICTURE_PORT = 18090
REMOTE_SECRET = 'hub-remote-compat-0123456789'
ADMIN_PASSWORD = 'hub-remote-compat'
# shaped like the web hooks the Home Assistant integration sets; never called here
HA_WEBHOOK = 'http://127.0.0.1:8123/api/webhook/hub-remote-compat?camera_id=%t&src=hass-motioneye'

FROZEN_0_44 = Path(__file__).with_name('test_config_older_clients.py')


class CheckFailed(Exception):
    pass


# -I and a neutral working directory: a motioneye folder in the current directory (this
# script runs from a checkout) must not shadow the version installed in the venv
NEUTRAL_DIR = tempfile.gettempdir()


def python_command(venv: Path) -> list[str]:
    return [str(venv / 'bin' / 'python'), '-I']


def run_python(venv: Path, code: str) -> str:
    return subprocess.run(
        python_command(venv) + ['-c', code],
        check=True,
        capture_output=True,
        text=True,
        cwd=NEUTRAL_DIR,
    ).stdout.strip()


def package_dir(venv: Path) -> Path:
    return Path(
        run_python(
            venv, 'import motioneye, os; print(os.path.dirname(motioneye.__file__))'
        )
    )


def version_of(venv: Path) -> str:
    return run_python(venv, 'import motioneye; print(motioneye.VERSION)')


def ui_keys(main_js: str) -> set[str]:
    """Top-level keys of the dict that cameraUi2Dict() returns in this main.js."""
    lines = main_js.replace('\r', '').split('\n')
    start = next(
        i for i, line in enumerate(lines) if line.startswith('function cameraUi2Dict(')
    )
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith('}'))
    body = '\n'.join(lines[start : end + 1])

    keys: set[str] = set()
    j = body.index('var dict = {') + len('var dict = ')
    depth = 0
    buf = ''
    in_str = ''
    escaped = False
    while j < len(body):
        c = body[j]
        j += 1
        if in_str:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == in_str:
                in_str = ''
            buf += c
            continue

        if c in '\'"':
            in_str = c
        elif c in '{[(':
            depth += 1
        elif c in '}])':
            depth -= 1
            if depth == 0:
                break
        elif c == ':' and depth == 1:
            match = re.search(r"'([a-z0-9_]+)'\s*$", buf)
            if match:
                keys.add(match.group(1))

        buf = '' if c in ',{' and depth == 1 else buf + c

    keys.update(re.findall(r'\bdict\.([a-z0-9_]+)\s*=', body))
    keys.update(re.findall(r"\bdict\[['\"]([a-z0-9_]+)['\"]\]\s*=", body))
    if len(keys) < 100 or not {'name', 'enabled'} <= keys:
        raise CheckFailed(
            f'cameraUi2Dict() parsed to {len(keys)} keys, main.js changed shape?'
        )

    return keys


def frozen_0_44_keys() -> set[str]:
    text = FROZEN_0_44.read_text(encoding='utf-8')
    block = text[text.index('_SENT_BY_0_44 = frozenset(') :]
    block = block[: block.index('\n)\n')]
    return set(re.findall(r"'([a-z0-9_]+)'", block))


class Client:
    """HTTP client for one server, keeping its session cookie."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.cookies: dict[str, str] = {}

    def request(
        self, method: str, path: str, body: bytes | None = None, content_type: str = ''
    ) -> tuple[int, str, bytes]:
        headers: dict[str, str] = {}
        if content_type:
            headers['Content-Type'] = content_type
        if self.cookies:
            headers['Cookie'] = '; '.join(f'{k}={v}' for k, v in self.cookies.items())

        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=60)
        try:
            conn.request(method, path, body=body, headers=headers)
            response = conn.getresponse()
            data = response.read()
            for name, value in response.getheaders():
                if name.lower() == 'set-cookie':
                    cookie = value.split(';', 1)[0]
                    if '=' in cookie:
                        key, val = cookie.split('=', 1)
                        self.cookies[key.strip()] = val.strip()

            return response.status, response.getheader('Content-Type') or '', data
        finally:
            conn.close()

    def get_json(self, path: str) -> dict:
        status, _, data = self.request('GET', path)
        if status != 200:
            raise CheckFailed(f'GET {path}: HTTP {status}: {data[:300]!r}')

        answer = json.loads(data)
        if isinstance(answer, dict) and answer.get('error'):
            raise CheckFailed(f'GET {path}: {answer["error"]}')

        return answer

    def post_json(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload).encode()
        status, _, data = self.request('POST', path, body, 'application/json')
        if status != 200:
            raise CheckFailed(f'POST {path}: HTTP {status}: {data[:300]!r}')

        return json.loads(data) if data else {}

    def login(self) -> None:
        form = urllib.parse.urlencode({'username': 'admin', 'password': ADMIN_PASSWORD})
        status, _, data = self.request(
            'POST', '/login/', form.encode(), 'application/x-www-form-urlencoded'
        )
        if status != 200:
            raise CheckFailed(f'login: HTTP {status}: {data[:300]!r}')


def write(path: Path, *lines: str) -> None:
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    path.chmod(0o600)


def set_up(root: Path, hub: Path, remote: Path) -> None:
    hub_dir, remote_dir = root / 'hub', root / 'remote'
    for directory in (
        hub_dir / 'run',
        hub_dir / 'log',
        hub_dir / 'tmp',
        remote_dir / 'run',
        remote_dir / 'log',
        remote_dir / 'tmp',
    ):
        directory.mkdir(parents=True)
    for directory in (
        root / 'media' / 'hub',
        root / 'media' / 'remote',
        root / 'pictures',
    ):
        directory.mkdir(parents=True)

    run_python(
        remote,
        'from PIL import Image; '
        f"Image.new('RGB', (640, 480), (40, 90, 140)).save('{root / 'pictures' / 'cam.jpg'}', 'JPEG')",
    )
    password_hash = run_python(
        hub,
        f"from argon2 import PasswordHasher; print(PasswordHasher().hash('{ADMIN_PASSWORD}'))",
    )

    for name, directory, port, motion_port in (
        ('remote', remote_dir, REMOTE_PORT, REMOTE_MOTION_PORT),
        ('hub', hub_dir, HUB_PORT, HUB_MOTION_PORT),
    ):
        write(
            directory / 'motioneye.conf',
            f'conf_path {directory}',
            f'run_path {directory / "run"}',
            f'log_path {directory / "log"}',
            f'media_path {root / "media" / name}',
            f'port {port}',
            'listen 127.0.0.1',
            f'motion_control_port {motion_port}',
            'log_level info',
        )

    write(
        remote_dir / 'motion.conf',
        'setup_mode off',
        f'webcontrol_port {REMOTE_MOTION_PORT}',
        'webcontrol_interface 1',
        'webcontrol_localhost on',
        'webcontrol_parms 2',
        f'# @client_secret {REMOTE_SECRET}',
        'camera camera-1.conf',
    )
    write(
        remote_dir / 'camera-1.conf',
        '# @id 1',
        '# @enabled on',
        '# @proto netcam',
        'camera_name Remote',
        f'netcam_url http://127.0.0.1:{PICTURE_PORT}/cam.jpg',
        f'target_dir {root / "media" / "remote"}',
        f'stream_port {STREAM_PORT}',
        'stream_localhost on',
        'framerate 2',
        'stream_maxrate 2',
        'picture_output off',
        'movie_output off',
        'snapshot_interval 0',
    )
    write(
        hub_dir / 'motion.conf',
        'setup_mode off',
        f'# @admin_password {password_hash}',
        f'# @normal_password {password_hash}',
    )
    write(
        hub_dir / 'camera-1.conf',
        '# @id 1',
        '# @enabled on',
        '# @proto motioneye',
        '# @scheme http',
        '# @host 127.0.0.1',
        f'# @port {REMOTE_PORT}',
        '# @path /',
        '# @remote_camera_id 1',
        f'# @remote_secret {REMOTE_SECRET}',
    )


def start(root: Path, hub: Path, remote: Path) -> list[subprocess.Popen]:
    processes = []
    picture_log = (root / 'pictures.log').open('w')
    processes.append(
        subprocess.Popen(
            [
                sys.executable,
                '-m',
                'http.server',
                str(PICTURE_PORT),
                '--bind',
                '127.0.0.1',
            ],
            cwd=root / 'pictures',
            stdout=picture_log,
            stderr=subprocess.STDOUT,
        )
    )
    for name, venv in (('remote', remote), ('hub', hub)):
        log = (root / f'{name}.log').open('w')
        processes.append(
            subprocess.Popen(
                python_command(venv)
                + [
                    '-m',
                    'motioneye.meyectl',
                    'startserver',
                    '-c',
                    str(root / name / 'motioneye.conf'),
                ],
                cwd=root / name,
                # both servers create <tmp>/MotionEye on import and race for it
                env={**os.environ, 'TMPDIR': str(root / name / 'tmp')},
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        )

    for port in (REMOTE_PORT, HUB_PORT):
        deadline = time.monotonic() + 60
        while True:
            try:
                Client(port).request('GET', '/')
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise CheckFailed(
                        f'nothing answers on port {port} after 60 s'
                    ) from None
                time.sleep(0.5)

    return processes


def as_ui_posts(answer: dict, keys: set[str]) -> tuple[dict, list[str]]:
    """What the hub's UI posts for a camera whose settings dialog was filled from answer."""
    payload = {key: answer[key] for key in keys if key in answer}
    missing = sorted(keys - set(answer))
    for key in missing:  # an empty field, or no video controls for a network camera
        payload[key] = {} if key == 'video_controls' else ''

    return payload, missing


def changed_lines(before: str, after: str) -> list[str]:
    diff = difflib.unified_diff(before.split('\n'), after.split('\n'), lineterm='', n=0)
    return [
        line
        for line in diff
        if line[:1] in '+-' and not line.startswith(('+++', '---')) and line[1:].strip()
    ]


def check(root: Path, hub: Path, remote: Path, report: list[str]) -> None:
    hub_keys = ui_keys(
        (package_dir(hub) / 'static' / 'js' / 'main.js').read_text(encoding='utf-8')
    )
    report.append(
        f"hub UI posts {len(hub_keys)} camera keys (cameraUi2Dict() in the hub's main.js)"
    )
    for venv in (hub, remote):
        if version_of(venv) == '0.44.0':
            keys_0_44 = ui_keys(
                (package_dir(venv) / 'static' / 'js' / 'main.js').read_text(
                    encoding='utf-8'
                )
            )
            if keys_0_44 != frozen_0_44_keys():
                raise CheckFailed(
                    'parsed 0.44.0 keys differ from _SENT_BY_0_44 in the tests'
                )
            report.append('parsed 0.44.0 keys match _SENT_BY_0_44 in the tests')

    client = Client(HUB_PORT)
    client.login()

    cameras = client.get_json('/config/list/')['cameras']
    camera = next((c for c in cameras if c.get('id') == 1), None)
    if not camera or camera.get('connection_failed'):
        raise CheckFailed(f'camera list: {camera}')
    report.append(f"camera list: remote camera listed as {camera.get('name')!r}")

    answer = client.get_json('/config/1/get/')
    report.append(f"camera config: {len(answer)} keys, name {answer.get('name')!r}")

    deadline = time.monotonic() + 120
    while True:
        status, content_type, data = client.request('GET', '/picture/1/current/')
        if status == 200 and content_type.startswith('image/jpeg') and data:
            report.append(f'current picture: {len(data)} bytes of JPEG')
            break
        if time.monotonic() > deadline:
            raise CheckFailed(
                f'no current picture after 120 s: HTTP {status} {content_type!r}'
            )
        time.sleep(2)

    for kind in ('picture', 'movie'):
        media = client.get_json(f'/{kind}/1/list/')
        report.append(f"{kind} list: {len(media.get('mediaList', []))} entries")

    camera_file = root / 'remote' / 'camera-1.conf'
    before = ''
    for number in (1, 2):
        name = f'Saved through the hub {number}'
        payload, missing = as_ui_posts(client.get_json('/config/1/get/'), hub_keys)
        payload['name'] = name
        result = client.post_json('/config/0/set/', {'1': payload})
        if result.get('error'):
            raise CheckFailed(f'save {number}: {result["error"]}')
        if missing and number == 1:
            report.append(
                f"keys the UI sends but the answer lacks, sent empty: {', '.join(missing)}"
            )

        saved = client.get_json('/config/1/get/').get('name')
        if saved != name:
            raise CheckFailed(
                f'save {number}: the camera is called {saved!r}, not {name!r}'
            )
        report.append(f'save {number}: name arrived')

        after = camera_file.read_text(encoding='utf-8')
        if number == 2:
            changed = changed_lines(before, after)
            unexpected = [
                line
                for line in changed
                if not line[1:].startswith(('camera_name ', 'text_left '))
            ]
            if unexpected:
                raise CheckFailed(
                    'save 2 changed more than the name:\n' + '\n'.join(unexpected)
                )
            report.append(
                f"save 2: the remote's camera file changed only in {len(changed)} name lines"
            )
        before = after

    # the Home Assistant integration (motioneye-client) saves differently: it posts the
    # whole config it fetched back to the single camera endpoint, with its web hooks set
    answer = client.get_json('/config/1/get/')
    hooks = {
        'web_hook_notifications_enabled': True,
        'web_hook_notifications_http_method': 'POSTj',
        'web_hook_notifications_url': f'{HA_WEBHOOK}&event_type=motion_detected',
        'web_hook_storage_enabled': True,
        'web_hook_storage_http_method': 'POSTj',
        'web_hook_storage_url': f'{HA_WEBHOOK}&file_path=%f&event_type=file_stored',
    }
    result = client.post_json('/config/1/set/', {**answer, **hooks})
    if result.get('error'):
        raise CheckFailed(f'Home Assistant style save: {result["error"]}')

    saved_config = client.get_json('/config/1/get/')
    wrong = {
        k: saved_config.get(k) for k, v in hooks.items() if saved_config.get(k) != v
    }
    if wrong or saved_config.get('name') != answer.get('name'):
        raise CheckFailed(
            f"Home Assistant style save: {wrong or saved_config.get('name')!r} after the save"
        )
    report.append(
        'Home Assistant style save: the whole config posted back with its web hooks set, '
        'and the web hooks arrived'
    )


def exception_lines(lines: list[str]) -> list[str]:
    """The exception each traceback in a log ends with."""
    found = []
    for i, line in enumerate(lines):
        if line.startswith('Traceback (most recent call last)'):
            rest = (text for text in lines[i + 1 :] if text and not text[0].isspace())
            found.append(next(rest, '(no exception line after the traceback)'))

    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    parser.add_argument(
        '--hub', type=Path, required=True, help='virtual environment of the hub'
    )
    parser.add_argument(
        '--remote', type=Path, required=True, help='virtual environment of the remote'
    )
    parser.add_argument(
        '--ignore-tracebacks',
        action='store_true',
        help='report tracebacks in the server logs without failing, e.g. for local runs '
        'where a tool the servers call is missing',
    )
    args = parser.parse_args()

    hub, remote = args.hub.resolve(), args.remote.resolve()
    report = [
        f'hub motionEye {version_of(hub)} from {package_dir(hub)}',
        f'remote motionEye {version_of(remote)} from {package_dir(remote)}',
    ]
    root = Path(tempfile.mkdtemp(prefix='hub-remote-'))
    processes: list[subprocess.Popen] = []
    failure = ''
    try:
        set_up(root, hub, remote)
        processes = start(root, hub, remote)
        check(root, hub, remote, report)
    except CheckFailed as e:
        failure = str(e)
    except Exception as e:  # anything else still gets the server logs printed below
        failure = f'unexpected {type(e).__name__}: {e}'
    finally:
        for process in reversed(processes):
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()

    logs: dict[str, list[str]] = {}
    tracebacks: list[str] = []
    for name in ('remote', 'hub'):
        log = root / f'{name}.log'
        text = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
        logs[name] = text.split('\n')
        raised = exception_lines(logs[name])
        tracebacks.extend(f'{name}: {line}' for line in raised)
        errors = [line for line in logs[name] if ' ERROR: ' in line]
        report.append(
            f'{name} log: {len(errors)} error lines, {len(raised)} tracebacks'
        )

    report.append(f'API checks: FAILED: {failure}' if failure else 'API checks: OK')
    if tracebacks:
        report.append('tracebacks in the server logs (separate from the API checks):')
        for line in dict.fromkeys(tracebacks):  # each once, in order, with a count
            report.append(f'  {tracebacks.count(line)} x {line}')
        if not args.ignore_tracebacks:
            failure = failure or (
                f'{len(tracebacks)} tracebacks in the server logs '
                '(--ignore-tracebacks reports them without failing)'
            )

    if failure:
        for name in ('remote', 'hub'):
            report.append(f'--- {name} log, last 40 lines ---')
            report.extend(logs[name][-40:])

    report.append(f'FAILED: {failure}' if failure else 'OK')
    print('\n'.join(report))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as f:
            f.write('```\n' + '\n'.join(report) + '\n```\n')

    return 1 if failure else 0


if __name__ == '__main__':
    sys.exit(main())
