"""后台启动配置的公网分享，并打开通过健康检查的网址。"""

import json
import socket
import subprocess
import time
import urllib.request
import webbrowser

from windows import PORT, PYTHON, ROOT, STATE, configuration, environment, install_tunnel, tunnel_tool_valid
from share_service import ACTIVE, exclusive_share


def service_state():
    try:
        return json.loads((STATE / 'service.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def current_url():
    state = service_state()
    if state.get('status') != 'running' or state.get('provider') != configuration().get('provider', 'cloudflare'):
        return None
    check = state.get('public_check') or {}
    if not check.get('ok') or time.time() - check.get('checked_at', 0) > 60:
        return None
    if time.time() - state.get('updated_at', 0) > 120:
        return None
    url = state.get('public_url', '')
    if not url.startswith('https://'):
        return None
    try:
        request = urllib.request.Request(f'http://127.0.0.1:{PORT}/health/',
                                         headers={'X-Forwarded-Proto': 'https'})
        with urllib.request.urlopen(request, timeout=2) as response:
            return url if response.status == 200 else None
    except OSError:
        return None


def share_is_stopped():
    """状态文件可能跨重启残留，以进程锁和端口确认旧服务已经退出。"""
    try:
        with exclusive_share():
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', PORT))
        return True
    except (OSError, RuntimeError):
        return False


def main():
    provider = configuration().get('provider', 'cloudflare')
    if provider == 'cloudflare' and not tunnel_tool_valid(STATE / 'tools/cloudflared.exe'):
        print('首次使用，正在下载 Cloudflare 官方隧道程序……', flush=True)
        install_tunnel()
    url = current_url()
    if not url:
        state = service_state()
        active = (state.get('provider') == provider and state.get('status') in ACTIVE
                  and time.time() - state.get('updated_at', 0) < 120 and not share_is_stopped())
        if not active and state.get('status') in ACTIVE:
            # 仅请求项目自己的 supervisor 退出，不按进程名停止其他服务。
            (STATE / ('stop-' + state['session'])).touch()
            for _ in range(40):
                if service_state().get('status') not in ACTIVE or share_is_stopped():
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError('之前的网站未退出，请先双击“关闭网站.cmd”后重试。')
        print('正在连接 ' + provider + '，请稍等……', flush=True)
        process = None
        if not active:
            with (STATE / 'logs/share-launcher.log').open('a', encoding='utf-8') as output, \
                    (STATE / 'logs/share-launcher-error.log').open('a', encoding='utf-8') as errors:
                process = subprocess.Popen(
                    [str(PYTHON), str(ROOT / 'deploy/windows.py'), 'share'], cwd=ROOT,
                    env=environment(), stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                )
        last_status = None
        for _ in range(360):
            url = current_url()
            if url:
                break
            state = service_state()
            status = state.get('status')
            if status != last_status:
                messages = {'reconnecting': '公网连接正在恢复，将自动获取新网址……',
                            'checking': '已获取网址，正在检查公网访问……',
                            'degraded': '公网暂未连通，后台正在重试……'}
                if status in messages:
                    print(messages[status], flush=True)
                last_status = status
            if process is not None and process.poll() is not None:
                raise RuntimeError('分享启动失败，请查看 .windows/logs/share-launcher-error.log 和隧道日志。')
            time.sleep(0.5)
        else:
            state = service_state()
            check = state.get('public_check') or {}
            detail = state.get('message') or check.get('error') or str(check.get('http_status') or '连接超时')
            raise RuntimeError('公网连接仍未恢复（' + detail + '）。后台会继续重试，请在网络恢复后再次双击；最新网址见 .windows/公网访问地址.txt。')
    webbrowser.open(url)
    print('分享网址：' + url)
    print('网址也保存在 .windows/公网访问地址.txt；可以关闭此窗口，电脑须保持开机联网。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print('打开失败：' + str(error))
        raise SystemExit(1)
