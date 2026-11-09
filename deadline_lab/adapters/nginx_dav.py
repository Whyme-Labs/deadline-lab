"""Black-box tests against an unmodified, locally installed nginx DAV server.

Only loopback listeners and disposable files are used. The authored gateway owns
fault injection; nginx is NOT patched or accused of violating HTTP semantics.
Deadline checks apply to gateway dispatch, not the instant of backend persistence.
"""
from __future__ import annotations
import hashlib
import http.client
import http.server
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from ..evidence import digest, seal, verify

POLICIES = ('timeout_only', 'deadline', 'fenced', 'reject_all')
REQUIRED = {'scenario.json', 'history.json', 'target.json', 'completion.json',
            'nginx.conf', 'nginx.access', 'nginx.stderr', 'nginx.version.txt'}


def validate(scenario: dict[str, Any]) -> None:
    if not isinstance(scenario, dict) or scenario.get('schema') != 2 or scenario.get('adapter') != 'nginx-dav':
        raise ValueError('expected schema 2 nginx-dav scenario')
    actions = scenario.get('actions')
    if not isinstance(actions, list) or len(actions) > 24:
        raise ValueError('actions must be a list of at most 24 entries')
    held: set[str] = set()
    keys: set[str] = set()
    values: set[int] = set()
    waited: set[str] = set()
    for a in actions:
        if not isinstance(a, dict):
            raise ValueError('invalid action')
        op = a.get('op')
        if op in {'hold', 'write', 'lost_ack'}:
            if set(a) != {'op', 'key', 'value', 'ttl_ms'}:
                raise ValueError('invalid request fields')
            k, v, ttl = a['key'], a['value'], a['ttl_ms']
            if not isinstance(k, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', k) or k in keys or k == 'healthy_probe':
                raise ValueError('unique simple request keys required')
            if type(v) is not int or not 1 <= v <= 65534 or v in values:
                raise ValueError('unique observable values 1..65534 required')
            if type(ttl) is not int or not 10 <= ttl <= 5000:
                raise ValueError('ttl_ms out of bounds')
            if op == 'lost_ack' and ttl > 250:
                raise ValueError('lost acknowledgement timeout must be at most 250 ms')
            keys.add(k); values.add(v)
            if op == 'hold':
                held.add(k)
        elif op in {'release', 'timeout'}:
            if set(a) != {'op', 'key'} or not isinstance(a.get('key'), str) or a['key'] not in held:
                raise ValueError('release/timeout must refer to a pending held request')
            if op == 'release':
                held.remove(a['key'])
            else:
                if a['key'] in waited:
                    raise ValueError('duplicate timeout wait')
                waited.add(a['key'])
        elif op == 'wait':
            if set(a) != {'op', 'ms'} or type(a['ms']) is not int or not 0 <= a['ms'] <= 100:
                raise ValueError('invalid wait')
        else:
            raise ValueError('unknown action')
    if held:
        raise ValueError('every held request must eventually be released')


def _json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + '\n')


def _port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class NginxTarget:
    """Own one foreground process, never use nginx -s or global configuration."""
    def __init__(self, out: Path, binary: Path | None = None):
        found = str(binary) if binary else shutil.which('nginx')
        if not found:
            raise RuntimeError('nginx not installed; external-target gate is NOT RUN')
        self.binary = Path(found).resolve()
        version = subprocess.run([str(self.binary), '-V'], capture_output=True, text=True,
                                 timeout=3, check=True)
        text = version.stdout + version.stderr
        if '--with-http_dav_module' not in text:
            raise RuntimeError('installed nginx does not include the DAV module')
        self.out = out.resolve()
        # Nginx path interpolation is intentionally not a general config templater.
        if any(c in str(self.out) for c in '\n\r";{}$\\'):
            raise ValueError('unsupported characters in output path')
        self.root = self.out / 'state-files'
        self.root.mkdir()
        (self.out / 'body-temp').mkdir()
        (self.root / 'state').write_text('0\n')
        self.token = secrets.token_hex(16)
        self.port = _port()
        config = f'''daemon off;
master_process off;
pid "{self.out}/nginx.pid";
error_log "{self.out}/nginx.stderr" notice;
events {{ worker_connections 32; }}
http {{
    access_log "{self.out}/nginx.access";
    client_body_temp_path "{self.out}/body-temp";
    client_max_body_size 1k;
    server {{
        listen 127.0.0.1:{self.port};
        root "{self.root}";
        location = /health {{ return 200 "{self.token}"; }}
        location = /state {{ dav_methods PUT; create_full_put_path off; }}
        location = /healthy {{ dav_methods PUT; create_full_put_path off; }}
        location / {{ deny all; }}
    }}
}}
'''
        (self.out / 'nginx.conf').write_text(config)
        (self.out / 'nginx.version.txt').write_text(text)
        self.stderr = (self.out / 'nginx.launch.stderr').open('wb')
        self.stdout = (self.out / 'nginx.stdout').open('wb')
        self.process = subprocess.Popen([str(self.binary), '-p', str(self.out) + '/',
            '-c', str(self.out / 'nginx.conf')], stdout=self.stdout, stderr=self.stderr)
        try:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError(f'nginx exited during startup: {self.process.returncode}')
                try:
                    c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=.1)
                    try:
                        c.request('GET', '/health')
                        r = c.getresponse()
                        if r.status == 200 and r.read().decode() == self.token:
                            break
                    finally:
                        c.close()
                except (OSError, http.client.HTTPException):
                    time.sleep(.005)
            else:
                raise RuntimeError('nginx startup token not observed; no mutation sent')
        except BaseException:
            self.close()
            raise

    def snapshot(self, healthy: bool = False) -> dict[str, Any]:
        path = self.root / ('healthy' if healthy else 'state')
        raw = path.read_bytes() if path.exists() else b''
        return {'monotonic_ns': time.monotonic_ns(), 'bytes_hex': raw.hex(),
                'sha256': hashlib.sha256(raw).hexdigest(),
                'value': int(raw.strip()) if raw else None}

    def put(self, value: int, healthy: bool = False) -> int:
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=2)
        try:
            c.request('PUT', '/healthy' if healthy else '/state', body=f'{value}\n'.encode(),
                      headers={'Content-Type': 'application/octet-stream', 'Connection': 'close'})
            r = c.getresponse(); r.read()
            return r.status
        finally:
            c.close()

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(timeout=2)
        self.stderr.close(); self.stdout.close()


class Gateway:
    """A cooperative delay hook around real HTTP requests to the external target."""
    def __init__(self, target: NginxTarget, policy: str):
        self.target, self.policy = target, policy
        self.requests: dict[str, dict[str, Any]] = {}
        self.dispatch_lock = threading.Lock()
        self.highest = 0
        self.stopping = threading.Event()
        gateway = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *_: Any) -> None:
                pass
            def do_PUT(self) -> None:
                key = self.path.removeprefix('/')
                request = gateway.requests.get(key)
                if request is None or request['received'].is_set():
                    self.send_error(400); return
                size = int(self.headers.get('Content-Length', '0'))
                if size > 64 or size < 1:
                    self.send_error(400); return
                payload = self.rfile.read(size)
                if payload != f"{request['value']}\n".encode():
                    self.send_error(400); return
                request['received_ns'] = time.monotonic_ns()
                request['received'].set()
                if not request['release'].wait(7):
                    request['error'] = 'hold hook timed out'
                    request['done'].set(); return
                try:
                    with gateway.dispatch_lock:
                        now = time.monotonic_ns()
                        if gateway.policy == 'reject_all':
                            status, reason = 503, 'reject_all'
                        elif gateway.policy in {'deadline', 'fenced'} and now >= request['expires_ns']:
                            status, reason = 408, 'expired_before_dispatch'
                        elif gateway.policy == 'fenced' and request['seq'] < gateway.highest:
                            status, reason = 409, 'superseded_before_dispatch'
                        else:
                            request['dispatch_ns'] = time.monotonic_ns()
                            status = gateway.target.put(request['value'], request['healthy'])
                            reason = 'forwarded'
                            if status not in {201, 204}:
                                raise RuntimeError(f'upstream write returned HTTP {status}')
                            gateway.highest = max(gateway.highest, request['seq'])
                        request.update(upstream_status=status, decision=reason)
                    if request['lose_ack']:
                        # Do not reply, but allow the client socket to really time out.
                        request['done'].set()
                        request['client_done'].wait(2)
                        self.close_connection = True
                        return
                    self.send_response(status)
                    self.send_header('Content-Length', '0')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                except (BrokenPipeError, ConnectionResetError):
                    # Expected when a delayed request outlives its downstream client.
                    request['reply_lost_after_client_disconnect'] = True
                except Exception as exc:
                    request['error'] = f'{type(exc).__name__}: {exc}'
                finally:
                    request['done'].set()
                    self.close_connection = True

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': .005}, daemon=True)
        self.thread.start()

    def issue(self, key: str, value: int, ttl_ms: int, hold: bool = False,
              lose_ack: bool = False, healthy: bool = False) -> dict[str, Any]:
        start = time.monotonic_ns()
        r: dict[str, Any] = {'key': key, 'seq': len(self.requests) + 1, 'value': value,
            'issued_ns': start, 'expires_ns': start + ttl_ms * 1_000_000, 'healthy': healthy,
            'hold': hold, 'lose_ack': lose_ack,
            **{x: threading.Event() for x in ('release', 'received', 'done', 'client_done')}}
        if not hold:
            r['release'].set()
        self.requests[key] = r
        def client() -> None:
            c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=ttl_ms/1000)
            try:
                c.request('PUT', '/' + key, body=f'{value}\n'.encode(), headers={'Connection': 'close'})
                response = c.getresponse(); response.read()
                r['client_status'] = 'http'
                r['client_http_status'] = response.status
            except (TimeoutError, socket.timeout):
                r['client_status'] = 'timeout'
            except (OSError, http.client.HTTPException) as exc:
                r['client_status'] = 'error'
                r['client_error'] = str(exc)
            finally:
                r['client_completed_ns'] = time.monotonic_ns()
                c.close(); r['client_done'].set()
        r['thread'] = threading.Thread(target=client, daemon=True)
        r['thread'].start()
        if not r['received'].wait(2):
            raise RuntimeError('gateway did not receive request')
        return r

    @staticmethod
    def finish(r: dict[str, Any]) -> None:
        if not r['done'].wait(3) or not r['client_done'].wait(6):
            raise RuntimeError('request completion budget exceeded')
        r['thread'].join(timeout=1)
        if r.get('error') or r.get('client_status') == 'error':
            raise RuntimeError(r.get('error', r.get('client_error')))

    @staticmethod
    def record(r: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in r.items() if isinstance(v, (str, int, bool))}

    def close(self) -> None:
        for r in self.requests.values():
            r['release'].set(); r['client_done'].set()
        for r in self.requests.values():
            r['done'].wait(3); r['thread'].join(timeout=1)
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)


def run(scenario: dict[str, Any], policy: str, out: Path,
        binary: Path | None = None) -> dict[str, Any]:
    validate(scenario)
    if policy not in POLICIES:
        raise ValueError('unknown gateway policy')
    out.mkdir(parents=True, exist_ok=False)
    _json(out / 'scenario.json', scenario)
    target = gateway = None
    history: list[dict[str, Any]] = []
    error = None
    metadata: dict[str, Any] = {'adapter': 'nginx-dav', 'policy': policy,
        'qnx_executed': False, 'physical_hardware': False, 'independent_target': 'nginx',
        'upstream_modified': False, 'observed_object': 'local file written by nginx DAV',
        'scope': 'gateway dispatch deadlines and command ordering, not physical actuation'}
    try:
        target = NginxTarget(out, binary)
        metadata.update(binary_sha256=digest(target.binary), binary_name=target.binary.name,
                        pid=target.process.pid, backend='linux-installed-binary',
                        version=(out / 'nginx.version.txt').read_text().splitlines()[0])
        gateway = Gateway(target, policy)
        budget_deadline = time.monotonic() + 20
        for index, action in enumerate(scenario['actions']):
            if time.monotonic() > budget_deadline:
                raise RuntimeError('external scenario execution budget exceeded')
            op = action['op']
            before = target.snapshot()
            request = None
            if op in {'hold', 'write', 'lost_ack'}:
                request = gateway.issue(action['key'], action['value'], action['ttl_ms'],
                                        hold=op == 'hold', lose_ack=op == 'lost_ack')
                if op != 'hold':
                    gateway.finish(request)
                if op == 'lost_ack' and request.get('client_status') != 'timeout':
                    raise RuntimeError('lost-ack fault did not activate')
            elif op in {'release', 'timeout'}:
                request = gateway.requests[action['key']]
                if op == 'timeout':
                    if not request['client_done'].wait(6) or request.get('client_status') != 'timeout':
                        raise RuntimeError('client-timeout fault did not activate')
                else:
                    request['release'].set(); gateway.finish(request)
            elif op == 'wait':
                time.sleep(action['ms'] / 1000)
            history.append({'seq': index, 'action': action, 'before': before, 'after': target.snapshot(),
                            'request': Gateway.record(request) if request is not None else None})
        before = target.snapshot(healthy=True)
        probe = gateway.issue('healthy_probe', 65535, 2000, healthy=True)
        gateway.finish(probe)
        history.append({'seq': len(history), 'action': {'op': 'healthy_probe'}, 'before': before,
                        'after': target.snapshot(healthy=True), 'request': Gateway.record(probe)})
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        if gateway:
            gateway.close()
        if target:
            target.close()
            metadata['target_exit'] = target.process.returncode
    _json(out / 'target.json', metadata)
    _json(out / 'history.json', history)
    _json(out / 'completion.json', {'complete': error is None, 'error': error, 'records': len(history)})
    for name in REQUIRED:
        if not (out / name).exists():
            (out / name).write_text('')
    seal(out, sorted(REQUIRED))
    result = evaluate(out)
    result.update(policy=policy, adapter='nginx-dav', qnx_executed=False,
                  name=scenario.get('name', 'unnamed'), action_count=len(scenario['actions']),
                  evidence_level='linux-unmodified-nginx/real-http-and-files',
                  upstream_bug_claimed=False)
    _json(out / 'result.json', result)
    return result


def evaluate(out: Path) -> dict[str, Any]:
    """Offline oracle: trusts recorded file observations, not an HTTP success alone."""
    errors: list[str] = []
    violations: list[dict[str, Any]] = []
    effects = healthy = unknowns = 0
    try:
        verify(out, REQUIRED)
        scenario = json.loads((out / 'scenario.json').read_text()); validate(scenario)
        metadata = json.loads((out / 'target.json').read_text())
        if metadata.get('target_exit') != 0 or metadata.get('upstream_modified') is not False:
            raise ValueError('unclean external target or unsupported modified target')
        if not re.fullmatch(r'[0-9a-f]{64}', metadata.get('binary_sha256', '')):
            raise ValueError('missing target executable identity')
        completion = json.loads((out / 'completion.json').read_text())
        history = json.loads((out / 'history.json').read_text())
        if not completion.get('complete'):
            raise ValueError('incomplete run: ' + str(completion.get('error')))
        if len(history) != len(scenario['actions']) + 1 or completion.get('records') != len(history):
            raise ValueError('missing observation or healthy probe')
        latest_effect_seq = 0
        state = 0
        seen_keys: set[str] = set()
        issued: dict[str, dict[str, Any]] = {}
        for i, h in enumerate(history):
            if h['seq'] != i:
                raise ValueError('observation order mismatch')
            action = h['action']
            if i < len(scenario['actions']) and action != scenario['actions'][i]:
                raise ValueError('action provenance mismatch')
            is_probe = i == len(history) - 1
            if is_probe and action != {'op': 'healthy_probe'}:
                raise ValueError('healthy probe missing')
            for snap in (h['before'], h['after']):
                raw = bytes.fromhex(snap['bytes_hex'])
                if hashlib.sha256(raw).hexdigest() != snap['sha256']:
                    raise ValueError('file observation digest mismatch')
                if (int(raw.strip()) if raw else None) != snap['value']:
                    raise ValueError('file observation value mismatch')
            if h['after']['monotonic_ns'] < h['before']['monotonic_ns']:
                raise ValueError('observation clock ordering')
            r = h['request']
            if action['op'] in {'hold', 'write', 'lost_ack'} or is_probe:
                if not isinstance(r, dict):
                    raise ValueError('issued request metadata missing')
                key = 'healthy_probe' if is_probe else action['key']
                value = 65535 if is_probe else action['value']
                ttl = 2000 if is_probe else action['ttl_ms']
                if (r.get('key') != key or r.get('value') != value or
                    r.get('seq') != len(issued) + 1 or key in issued or
                    r['expires_ns'] - r['issued_ns'] != ttl * 1_000_000 or
                    r.get('healthy') is not is_probe):
                    raise ValueError('issued request does not match scenario')
                issued[key] = {k: r[k] for k in ('key', 'seq', 'value', 'issued_ns', 'expires_ns', 'healthy')}
            elif action['op'] in {'release', 'timeout'}:
                original = issued.get(action['key'])
                if original is None or not isinstance(r, dict) or any(r.get(k) != v for k, v in original.items()):
                    raise ValueError('held request identity changed')
            elif r is not None:
                raise ValueError('unexpected request metadata')
            if not is_probe and h['before']['value'] != state:
                raise ValueError('unobserved file change between actions')
            change = h['after']['value'] != h['before']['value']
            if change:
                if r is None or h['after']['value'] != r['value'] or 'dispatch_ns' not in r:
                    raise ValueError('file change cannot be associated with dispatched request')
                if not (r['issued_ns'] <= r['received_ns'] <= r['dispatch_ns'] <= h['after']['monotonic_ns']):
                    raise ValueError('dispatch provenance ordering')
                if r['key'] in seen_keys:
                    raise ValueError('duplicate ambiguous observation')
                seen_keys.add(r['key'])
                if is_probe:
                    healthy += 1
                else:
                    effects += 1
                    if r['dispatch_ns'] >= r['expires_ns']:
                        violations.append({'property': 'expired_dispatch_effect', 'key': r['key'], 'observation': i})
                    if r['seq'] < latest_effect_seq:
                        violations.append({'property': 'superseded_effect', 'key': r['key'], 'observation': i})
                    latest_effect_seq = max(latest_effect_seq, r['seq'])
                    state = h['after']['value']
                    if r.get('client_status') == 'timeout':
                        unknowns += 1
            elif r and action['op'] in {'release', 'write', 'lost_ack'} and r.get('decision') == 'forwarded':
                raise ValueError('forwarded successful request has no independent file effect')
        if healthy != 1:
            violations.append({'property': 'healthy_progress', 'observed': healthy})
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        errors.append(str(exc))
    return {'verdict': 'INCONCLUSIVE' if errors else 'FAIL' if violations else 'PASS',
        'properties': sorted({v['property'] for v in violations}), 'violations': violations,
        'evidence_errors': errors, 'observed_file_effects': effects, 'healthy_effects': healthy,
        'timeout_but_effect_observed': unknowns,
        'limits': 'Unmodified nginx is an independent HTTP/file target; gateway policies and hooks are ours. '
                  'Timeout is not cancellation. Dispatch expiry is not a backend commit-time guarantee.'}
