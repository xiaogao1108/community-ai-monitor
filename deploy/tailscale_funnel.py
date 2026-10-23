"""用本机 Tailscale 设备的固定域名发布当前网站。"""
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time

from windows import PORT, STATE


def executable():
    installed = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Tailscale/tailscale.exe'
    found = str(installed) if installed.is_file() else shutil.which('tailscale')
    if not found:
        raise RuntimeError('尚未安装 Tailscale，请先安装官方 Windows 客户端并登录。')
    return found


def read_status(*arguments):
    try:
        result = subprocess.run([executable(), *arguments, '--json'], capture_output=True,
                                text=True, encoding='utf-8', timeout=15,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError('无法读取 Tailscale 状态，请确认客户端服务已启动并登录。')
        value = json.loads(result.stdout)
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError('invalid status')
        return value
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('Tailscale 状态读取失败，请检查本机客户端。') from exc


def public_url(status=None):
    status = read_status('status') if status is None else status
    if status.get('BackendState') != 'Running':
        raise RuntimeError('请先打开 Tailscale 客户端，完成账号登录并连接。')
    name = (status.get('Self') or {}).get('DNSName', '').rstrip('.').lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+\.ts\.net', name):
        raise RuntimeError('尚未取得有效的 Tailscale 固定域名，请检查 MagicDNS 和设备注册。')
    return 'https://' + name


def check_available():
    url = public_url()
    config = read_status('funnel', 'status')
    # 不覆盖同一设备上已有的 Serve/Funnel 网站，包括前台会话。
    def occupied(value):
        if not isinstance(value, dict):
            return False
        if '443' in (value.get('TCP') or {}):
            return True
        if any(str(key).endswith(':443') for key in (value.get('Web') or {})):
            return True
        return any(occupied(item) for item in (value.get('Foreground') or {}).values())
    if occupied(config):
        raise RuntimeError('Tailscale 的 HTTPS 443 已有分享配置，为避免覆盖其他服务，请先确认并关闭旧配置。')
    return url


def open_tunnel(children, flags, updates=None, stopped=None):
    url = check_available()
    process = subprocess.Popen(
        [executable(), 'funnel', '--yes', '--https=443', f'http://127.0.0.1:{PORT}'],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='replace', creationflags=flags,
    )
    children.append(process)
    ready = queue.Queue()

    def read_output():
        with (STATE / 'logs/tailscale-funnel.log').open('a', encoding='utf-8') as log:
            for line in process.stdout:
                log.write(re.sub(r'https://login\.tailscale\.com/\S+', '[请在 Tailscale 客户端完成授权]', line))
                log.flush()
                if re.search(re.escape(url) + r'(?=[\s/:]|$)', line):
                    ready.put(url)
            process.stdout.close()

    threading.Thread(target=read_output, daemon=True).start()
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if stopped and stopped():
            raise RuntimeError('已请求停止连接。')
        if process.poll() is not None:
            raise RuntimeError('Funnel 启动失败，请查看 .windows/logs/tailscale-funnel.log。')
        try:
            return ready.get(timeout=0.25)
        except queue.Empty:
            pass
    raise RuntimeError('Funnel 尚未就绪；首次使用需要在 Tailscale 页面启用 HTTPS 和 Funnel。')
