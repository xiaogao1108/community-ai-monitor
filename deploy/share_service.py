"""维护本项目的公网隧道、动态域名和可验证的健康状态。"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
import queue
import secrets
import socket
import subprocess
import time

import requests

from windows import ROOT, STATE, PORT, PYTHON, configuration, environment, open_localhost_tunnel, open_tunnel, tunnel_tool_valid, write_json


ACTIVE = {'starting', 'checking', 'running', 'reconnecting', 'degraded'}


def health_check(url):
    try:
        response = requests.get(url + '/health/', params={'check': time.time_ns()},
                                timeout=8, allow_redirects=False)
        ok = response.status_code == 200 and response.json().get('status') == 'ok'
        return {'ok': ok, 'http_status': response.status_code, 'checked_at': time.time()}
    except requests.RequestException as error:
        return {'ok': False, 'error': type(error).__name__, 'checked_at': time.time()}
    except (ValueError, AttributeError):
        return {'ok': False, 'error': 'InvalidHealthResponse', 'checked_at': time.time()}


def stop_process(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@contextmanager
def exclusive_share():
    import msvcrt
    with (STATE / 'share.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError('本项目的公网分享已在运行，请勿重复启动。') from None
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


class ShareService:
    def __init__(self, provider='localhost.run'):
        if provider not in ('localhost.run', 'cloudflare'):
            raise ValueError('不支持的公网隧道服务')
        self.provider = provider
        self.session = secrets.token_hex(12)
        self.stop_file = STATE / ('stop-' + self.session)
        self.children = []
        self.updates = queue.Queue()
        self.web = None
        self.web_log = None
        self.tunnel = None
        self.url = None
        self.state = 'starting'
        self.check = None
        self.successes = 0
        self.retry_at = 0
        self.retry_delay = 2
        self.web_retry_at = 0
        self.web_retry_delay = 2
        self.flags = subprocess.CREATE_NO_WINDOW

    def publish(self, message=''):
        data = {'status': self.state, 'session': self.session, 'provider': self.provider,
                'public_url': self.url, 'updated_at': time.time(), 'supervisor_pid': os.getpid(),
                'web_pid': self.web.pid if self.web else None,
                'tunnel_pid': self.tunnel.pid if self.tunnel else None,
                'public_check': self.check, 'message': message}
        write_json(STATE / 'service.json', data)
        if self.state == 'running':
            text = self.url + '\n公网健康检查通过。电脑须保持开机联网，免费网址可能自动变化。\n'
        elif self.state in ('checking', 'degraded') and self.url:
            text = self.url + '\n当前公网检查尚未通过，请勿视为已稳定上线。\n'
        else:
            text = '公网分享暂不可用：' + self.state + '。\n' + message + '\n'
        (STATE / '公网访问地址.txt').write_text(text, encoding='utf-8')

    def start_web(self, url):
        stop_process(self.web)
        if self.web in self.children:
            self.children.remove(self.web)
        if self.web_log:
            self.web_log.close()
        config = configuration()
        config['public_url'] = url
        write_json(STATE / 'config.json', config)
        self.url = url
        self.state = 'checking'
        self.check = None
        self.successes = 0
        self.publish('域名已更新，正在校验公网访问')
        self.web_log = (STATE / 'logs/web.log').open('a', encoding='utf-8')
        self.web = subprocess.Popen([str(PYTHON), str(ROOT / 'deploy/windows.py'), 'serve'],
                                    cwd=ROOT, env=environment(url), stdin=subprocess.DEVNULL,
                                    stdout=self.web_log, stderr=subprocess.STDOUT,
                                    creationflags=self.flags)
        self.children.append(self.web)
        print('当前网址：' + url, flush=True)

    def connect(self):
        self.state = 'reconnecting'
        self.url = None
        self.check = None
        self.successes = 0
        self.publish('正在连接 ' + self.provider)
        self.updates = queue.Queue()
        before = len(self.children)
        try:
            if self.provider == 'cloudflare':
                url = open_tunnel(STATE / 'tools/cloudflared.exe', self.children, self.flags,
                                  self.updates, self.stop_file.exists)
            else:
                url = open_localhost_tunnel(self.children, self.flags, self.updates, self.stop_file.exists)
            self.tunnel = self.children[-1]
            self.start_web(url)
            self.retry_delay = 2
        except (OSError, RuntimeError):
            for child in self.children[before:]:
                stop_process(child)
            del self.children[before:]
            self.tunnel = None
            self.state = 'reconnecting'
            self.url = None
            self.retry_at = time.monotonic() + self.retry_delay
            self.retry_delay = min(self.retry_delay * 2, 30)
            self.publish('隧道连接失败，将自动重试；详见 .windows/logs')

    def apply_updates(self):
        latest = None
        while True:
            try:
                event = self.updates.get_nowait()
            except queue.Empty:
                break
            if isinstance(event, dict) and event.get('error') == 'tunnel_not_found':
                stop_process(self.tunnel)
                if self.tunnel in self.children:
                    self.children.remove(self.tunnel)
                self.tunnel = None
                self.updates = queue.Queue()
                self.url = None
                self.check = None
                self.successes = 0
                self.state = 'reconnecting'
                self.retry_at = time.monotonic() + self.retry_delay
                self.retry_delay = min(self.retry_delay * 2, 30)
                self.publish('Cloudflare 临时隧道已失效，正在自动申请新网址')
                return True
            if isinstance(event, str):
                latest = event
        if latest and latest != self.url:
            self.start_web(latest)
            return True
        return False

    def record_check(self, url, result):
        if url != self.url or self.tunnel is None or self.tunnel.poll() is not None:
            return
        self.check = result
        self.successes = self.successes + 1 if result['ok'] else 0
        self.state = 'running' if self.successes >= 3 else ('checking' if result['ok'] else 'degraded')
        if self.state == 'running':
            self.web_retry_delay = 2
        self.publish()

    def run(self):
        self.publish()
        pending = None
        checked_url = None
        next_check = next_heartbeat = 0
        with ThreadPoolExecutor(max_workers=1) as executor:
            try:
                while not self.stop_file.exists():
                    now = time.monotonic()
                    if self.tunnel is None or self.tunnel.poll() is not None:
                        if self.tunnel is not None:
                            self.children.remove(self.tunnel)
                            self.tunnel = None
                            self.state = 'reconnecting'
                            self.url = None
                            self.check = None
                            self.publish('隧道已断开，正在恢复')
                        if now >= self.retry_at:
                            self.connect()
                            next_check = 0
                    if self.tunnel is not None:
                        if self.apply_updates():
                            next_check = 0
                        if self.tunnel is None:
                            continue
                        if self.web is None or self.web.poll() is not None:
                            self.state = 'degraded'
                            self.check = None
                            self.successes = 0
                            if now >= self.web_retry_at:
                                self.start_web(self.url)
                                self.web_retry_at = now + self.web_retry_delay
                                self.web_retry_delay = min(self.web_retry_delay * 2, 30)
                                next_check = 0
                        if pending is not None and pending.done():
                            self.record_check(checked_url, pending.result())
                            pending = None
                        if pending is None and now >= next_check:
                            checked_url = self.url
                            pending = executor.submit(health_check, checked_url)
                            next_check = now + (30 if self.state == 'running' else 3)
                    if now >= next_heartbeat:
                        self.publish()
                        next_heartbeat = now + 5
                    time.sleep(0.25)
            finally:
                for child in reversed(self.children):
                    stop_process(child)
                if self.web_log:
                    self.web_log.close()
                self.url = None
                self.state = 'stopped'
                self.publish()
                self.stop_file.unlink(missing_ok=True)


def run():
    provider = configuration().get('provider', 'cloudflare')
    if provider == 'cloudflare' and not tunnel_tool_valid(STATE / 'tools/cloudflared.exe'):
        raise RuntimeError('Cloudflare 程序缺失或损坏，请先运行 install-tunnel')
    with exclusive_share():
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', PORT))
        ShareService(provider).run()
