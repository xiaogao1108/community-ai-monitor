"""双击入口：在后台启动本机网站，再打开浏览器。"""

import json
import socket
import subprocess
import time
import urllib.request
import webbrowser

from windows import PORT, PYTHON, ROOT, STATE, configuration


URL = f'http://127.0.0.1:{PORT}'


def ready():
    try:
        state = json.loads((STATE / 'service.json').read_text(encoding='utf-8'))
        if state.get('status') != 'running' or state.get('public_url') != URL:
            return False
        with urllib.request.urlopen(URL + '/health/', timeout=2) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def main():
    configuration()
    if not ready():
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', PORT))
            except OSError:
                raise RuntimeError('8765 端口已被占用，请先关闭之前的网站窗口，再重试。') from None
        with (STATE / 'logs/launcher.log').open('w', encoding='utf-8') as output, \
                (STATE / 'logs/launcher-error.log').open('w', encoding='utf-8') as errors:
            process = subprocess.Popen(
                [str(PYTHON), str(ROOT / 'deploy/windows.py'), 'local'], cwd=ROOT,
                stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        for _ in range(60):
            if ready():
                break
            if process.poll() is not None:
                raise RuntimeError('网站未能启动，详情见 .windows/logs/launcher-error.log。')
            time.sleep(0.5)
        else:
            raise RuntimeError('网站仍未就绪，请查看 .windows/logs 中的日志。')
    webbrowser.open(URL)
    print('网站已打开，可以关闭此窗口。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError) as error:
        print('打开失败：' + str(error))
        raise SystemExit(1)
