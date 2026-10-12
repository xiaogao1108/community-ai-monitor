"""后台启动配置的公网分享，并打开通过健康检查的网址。"""

import json
import subprocess
import time
import urllib.request
import webbrowser

from windows import PORT, PYTHON, ROOT, STATE, configuration, environment, install_tunnel, tunnel_tool_valid
from share_service import ACTIVE


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


def main():
    provider = configuration().get('provider', 'cloudflare')
    if provider == 'cloudflare' and not tunnel_tool_valid(STATE / 'tools/cloudflared.exe'):
        print('首次使用，正在下载 Cloudflare 官方隧道程序……', flush=True)
        install_tunnel()
    url = current_url()
    if not url:
        state = service_state()
        active = state.get('provider') == provider and state.get('status') in ACTIVE and time.time() - state.get('updated_at', 0) < 120
        if not active and state.get('status') in ACTIVE:
            # 仅请求项目自己的 supervisor 退出，不按进程名停止其他服务。
            (STATE / ('stop-' + state['session'])).touch()
            for _ in range(40):
                if service_state().get('status') not in ACTIVE:
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
        for _ in range(180):
            url = current_url()
            if url:
                break
            if process is not None and process.poll() is not None:
                raise RuntimeError('分享启动失败，请查看 .windows/logs/share-launcher-error.log 和隧道日志。')
            time.sleep(0.5)
        else:
            raise RuntimeError('公网连续检查尚未通过，后台会继续检测。请查看 .windows/公网访问地址.txt 与 logs，不要把当前状态视为已稳定上线。')
    webbrowser.open(url)
    print('分享网址：' + url)
    print('网址也保存在 .windows/公网访问地址.txt；可以关闭此窗口，电脑须保持开机联网。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print('打开失败：' + str(error))
        raise SystemExit(1)
