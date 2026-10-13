"""Windows 本机部署：独立数据库、Waitress 与临时 HTTPS 隧道。"""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from urllib.parse import urlsplit
import venv


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.windows'
WEB = ROOT / 't7/Python/community_system'
AI = ROOT / 't7/Python/aiWatchdog-main'
PYTHON = STATE / 'venv/Scripts/python.exe'
PORT = 8765
CLOUDFLARED_URL = 'https://github.com/cloudflare/cloudflared/releases/download/2026.9.3/cloudflared-windows-amd64.exe'
CLOUDFLARED_SHA256 = 'f096265ec2fcbe9bb6e2d64268db167ced3fcbb83d894bdb9e2fcdb26f2ea7e2'


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def configuration():
    STATE.mkdir(exist_ok=True)
    for directory in ('secrets', 'logs', 'tools', 'data/media', 'data/static', 'data/ai'):
        (STATE / directory).mkdir(parents=True, exist_ok=True)
    for name in ('django_secret_key', 'ai_ingest_token'):
        target = STATE / 'secrets' / (name + '.txt')
        if not target.exists():
            with target.open('x', encoding='utf-8') as handle:
                handle.write(secrets.token_urlsafe(48))
    path = STATE / 'config.json'
    if not path.exists():
        write_json(path, {'public_url': 'https://localhost', 'provider': 'cloudflare'})
    return json.loads(path.read_text(encoding='utf-8'))


def environment(public_url=None, local=False):
    config = configuration()
    public_url = public_url or config['public_url']
    parsed = urlsplit(public_url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.port or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('公网地址必须是无端口、无路径的 HTTPS 地址')
    env = os.environ.copy()
    # 运行目录中的专用密钥优先，避免继承旧项目凭据。
    for name in ('DJANGO_SECRET_KEY', 'AI_INGEST_TOKEN', 'DB_PASSWORD', 'DB_PASSWORD_FILE'):
        env.pop(name, None)
    env.update({
        'DJANGO_SETTINGS_MODULE': 'community_project.settings_windows',
        'DJANGO_SECRET_KEY_FILE': str(STATE / 'secrets/django_secret_key.txt'),
        'AI_INGEST_TOKEN_FILE': str(STATE / 'secrets/ai_ingest_token.txt'),
        'DJANGO_ALLOWED_HOSTS': parsed.hostname + ',localhost,127.0.0.1',
        'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://' + parsed.hostname,
        'DB_ENGINE': 'sqlite', 'DB_PATH': str(STATE / 'data/db.sqlite3'),
        'MEDIA_ROOT': str(STATE / 'data/media'), 'STATIC_ROOT': str(STATE / 'data/static'),
        'AI_STATE_DIR': str(STATE / 'data/ai'),
        'DJANGO_BASE_URL': f'http://127.0.0.1:{PORT}',
        'AI_HOST': '127.0.0.1', 'AI_PORT': '16532',
        'PYTHONUTF8': '1',
    })
    if local:
        env['DJANGO_SETTINGS_MODULE'] = 'community_project.settings_windows_local'
    key_file = STATE / 'secrets/deepseek_api_key.txt'
    if key_file.exists():
        env.pop('DEEPSEEK_API_KEY', None)
        env['DEEPSEEK_API_KEY_FILE'] = str(key_file)
    return env


def setup():
    configuration()
    if not PYTHON.exists():
        venv.create(STATE / 'venv', with_pip=True)
    subprocess.run([str(PYTHON), '-m', 'pip', 'install', '-r', str(WEB / 'requirements.windows.txt')], check=True)
    subprocess.run([str(PYTHON), str(Path(__file__)), 'init'], check=True)
    print('本机部署已就绪，可运行 python deploy/windows.py local。')


def tunnel_tool_valid(tool):
    if not tool.is_file():
        return False
    try:
        result = subprocess.run([str(tool), '--version'], capture_output=True, timeout=15,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return result.returncode == 0 and b'cloudflared version' in result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def install_tunnel():
    configuration()
    tool = STATE / 'tools/cloudflared.exe'
    if not tunnel_tool_valid(tool):
        partial = tool.with_name('cloudflared.download.exe')
        with urllib.request.urlopen(CLOUDFLARED_URL, timeout=60) as response, partial.open('wb') as output:
            shutil.copyfileobj(response, output)
            expected = response.headers.get('Content-Length')
        if expected and partial.stat().st_size != int(expected):
            raise RuntimeError('隧道程序下载不完整，请重新运行 install-tunnel')
        if hashlib.sha256(partial.read_bytes()).hexdigest() != CLOUDFLARED_SHA256:
            raise RuntimeError('隧道程序 SHA256 与官方发布不一致，请重新下载')
        if not tunnel_tool_valid(partial):
            raise RuntimeError('下载的隧道程序无法运行，请从 Cloudflare 官方下载 Windows AMD64 版本')
        partial.replace(tool)
    print('公网隧道程序已就绪。')


def configure_django(local=False):
    os.environ.update(environment(local=local))
    sys.path.insert(0, str(WEB))
    import django
    django.setup()


def initialize():
    configure_django()
    from django.core.management import call_command
    from django.contrib.auth import get_user_model
    from django.contrib.auth.hashers import make_password
    from django.db import transaction
    from core.models import User
    call_command('migrate', interactive=False)
    call_command('collectstatic', interactive=False)
    call_command('check', deploy=True, fail_level='WARNING')
    admin_model = get_user_model()
    if not admin_model.objects.exists() and not User.objects.exists():
        password = secrets.token_urlsafe(24)
        login_file = STATE / 'admin-login.txt'
        with transaction.atomic():
            admin_model.objects.create_superuser('admin001', '', password)
            User.objects.create(username='本机管理员', account='admin001', password=make_password(password), type='admin')
            with login_file.open('x', encoding='utf-8') as handle:
                handle.write('后台 /admin/ 与社区 /login/\n账号：admin001\n密码：' + password + '\n仅保存在本机，请勿分享此文件。\n')
    print('初始化完成。登录信息保存在 .windows/admin-login.txt，未显示密码。')


def serve(local=False):
    configure_django(local=local)
    from django.core.wsgi import get_wsgi_application
    from waitress import serve as run_server
    run_server(get_wsgi_application(), host='127.0.0.1', port=PORT, threads=2,
               trusted_proxy=None if local else '127.0.0.1',
               trusted_proxy_headers=set() if local else {'x-forwarded-proto'},
               clear_untrusted_proxy_headers=True, max_request_body_size=105 * 1024 * 1024)


def start(local=False):
    configuration()
    with socket.socket() as check:
        check.bind(('127.0.0.1', PORT))
    tool = STATE / 'tools/cloudflared.exe'
    if not PYTHON.exists() or not (STATE / 'data/db.sqlite3').exists():
        raise RuntimeError('请先运行 python deploy/windows.py setup')
    if not local and not tunnel_tool_valid(tool):
        raise RuntimeError('隧道程序缺失或不完整，请运行 python deploy/windows.py install-tunnel；仅本机使用可运行 local')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    session = secrets.token_hex(12)
    stop_file = STATE / ('stop-' + session)
    service_file = STATE / 'service.json'
    children = []
    handles = []
    try:
        if local:
            public_url = f'http://127.0.0.1:{PORT}'
        else:
            public_url = open_tunnel(tool, children, flags)
        if not local:
            config = configuration()
            config['public_url'] = public_url
            write_json(STATE / 'config.json', config)
        log = (STATE / 'logs/web.log').open('w', encoding='utf-8')
        handles.append(log)
        command = 'serve-local' if local else 'serve'
        web = subprocess.Popen([str(PYTHON), str(Path(__file__)), command], cwd=ROOT,
                               env=environment(local=local), stdout=log, stderr=subprocess.STDOUT,
                               creationflags=flags)
        children.append(web)
        for _ in range(60):
            if web.poll() is not None:
                raise RuntimeError('网站启动失败，详情见 .windows/logs/web.log')
            try:
                request = urllib.request.Request(f'http://127.0.0.1:{PORT}/health/', headers={'X-Forwarded-Proto': 'https'})
                with urllib.request.urlopen(request, timeout=2) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.5)
        else:
            raise RuntimeError('网站健康检查超时')
        write_json(service_file, {'status': 'running', 'session': session, 'public_url': public_url,
                                  'provider': 'local' if local else 'cloudflare'})
        if not local:
            (STATE / '公网访问地址.txt').write_text(public_url + '\n保持电脑开机联网；重新启动后请以新地址为准。\n', encoding='utf-8')
        print('网站地址：' + public_url, flush=True)
        print('保持此窗口运行；Ctrl+C 或 python deploy/windows.py stop 关闭。', flush=True)
        while not stop_file.exists():
            if any(process.poll() is not None for process in children):
                raise RuntimeError('网站或隧道已退出，请检查 .windows/logs')
            time.sleep(0.5)
    finally:
        for process in reversed(children):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for handle in handles:
            handle.close()
        write_json(service_file, {'status': 'stopped', 'session': session})
        if not local:
            (STATE / '公网访问地址.txt').write_text('公网分享已停止。双击项目根目录的“打开网站.cmd”重新开启。\n', encoding='utf-8')
        stop_file.unlink(missing_ok=True)


def cloudflare_event(line):
    if 'Unauthorized: Tunnel not found' in line:
        return {'error': 'tunnel_not_found'}
    match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com(?=[\s/|]|$)', line)
    return match.group() if match else None


def open_tunnel(tool, children, flags, updates=None, stopped=None):
    tunnel = subprocess.Popen([str(tool), 'tunnel', '--no-autoupdate', '--url', f'http://127.0.0.1:{PORT}',
                               '--protocol', 'http2'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding='utf-8', errors='replace', creationflags=flags)
    children.append(tunnel)
    found = updates if updates is not None else queue.Queue()
    def read_tunnel():
        with (STATE / 'logs/tunnel.log').open('a', encoding='utf-8') as log:
            for line in tunnel.stdout:
                log.write(line)
                log.flush()
                event = cloudflare_event(line)
                if event:
                    found.put(event)
    threading.Thread(target=read_tunnel, daemon=True).start()
    public_url = None
    for _ in range(90):
        if stopped and stopped():
            raise InterruptedError('用户已请求停止分享')
        if tunnel.poll() is not None:
            raise RuntimeError('公网隧道未能建立，详情见 .windows/logs/tunnel.log')
        try:
            public_url = found.get(timeout=1)
            if isinstance(public_url, dict):
                raise RuntimeError('Cloudflare 临时隧道已失效，需要重新建立连接')
            break
        except queue.Empty:
            pass
    if not public_url:
        raise RuntimeError('获取公网地址超时，详情见 .windows/logs/tunnel.log')
    return public_url


def localhost_url(line):
    try:
        event = json.loads(line)
    except ValueError:
        return None
    if not isinstance(event, dict) or event.get('type') != 'v1.tcpip_forward.register.accepted':
        return None
    data = event.get('data', '')
    if not isinstance(data, str):
        return None
    match = re.search(r'https://([a-z0-9-]+\.(?:lhr\.life|localhost\.run))(?=[\s/]|$)', data)
    return 'https://' + match.group(1) if match else None


def localhost_command():
    ssh = shutil.which('ssh')
    if not ssh:
        raise RuntimeError('Windows OpenSSH 客户端未安装，请在系统可选功能中启用它。')
    return [ssh, '-F', os.devnull, '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
            '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
            '-o', 'StrictHostKeyChecking=accept-new',
            '-o', 'UserKnownHostsFile="' + (STATE / 'secrets/localhost-run-known-hosts').as_posix() + '"',
            '-o', 'IdentityAgent=none', '-o', 'PubkeyAuthentication=no',
            '-o', 'PasswordAuthentication=no', '-o', 'KbdInteractiveAuthentication=no',
            '-o', 'ExitOnForwardFailure=yes', '-R', f'80:127.0.0.1:{PORT}',
            'nokey@localhost.run', '--', '--output', 'json', '--inject-http-proxy-headers']


def open_localhost_tunnel(children, flags, updates=None, stopped=None):
    tunnel = subprocess.Popen(localhost_command(), cwd=ROOT, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding='utf-8', errors='replace', creationflags=flags)
    children.append(tunnel)
    found = updates if updates is not None else queue.Queue()

    def read_output():
        with (STATE / 'logs/localhost-run.log').open('a', encoding='utf-8') as log:
            for line in tunnel.stdout:
                url = localhost_url(line)
                # 注册响应附带大段二维码；仅记录实际网址。
                log.write(('已分配网址：' + url + '\n') if url else line)
                log.flush()
                if url:
                    found.put(url)

    threading.Thread(target=read_output, daemon=True).start()
    for _ in range(60):
        if stopped and stopped():
            raise InterruptedError('用户已请求停止分享')
        if tunnel.poll() is not None:
            raise RuntimeError('localhost.run 连接失败，详情见 .windows/logs/localhost-run.log')
        try:
            return found.get(timeout=1)
        except queue.Empty:
            pass
    raise RuntimeError('localhost.run 分配网址超时，详情见 .windows/logs/localhost-run.log')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'install-tunnel', 'set-key', 'init', 'start', 'share', 'local', 'serve', 'serve-local', 'stop', 'status', 'manage', 'ai'])
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == 'setup':
        setup()
        return
    if args.command == 'install-tunnel':
        install_tunnel()
        return
    if args.command == 'set-key':
        configuration()
        key = getpass.getpass('请输入 DeepSeek API Key（不回显）：').strip()
        if not key:
            raise ValueError('密钥不能为空')
        (STATE / 'secrets/deepseek_api_key.txt').write_text(key, encoding='utf-8')
        print('已保存在本机 secrets 目录；重新启动 AI 后生效。')
        return
    if args.command in ('init', 'serve', 'serve-local') and Path(sys.executable).resolve() != PYTHON.resolve():
        if not PYTHON.exists():
            raise RuntimeError('请先运行 setup')
        raise SystemExit(subprocess.call([str(PYTHON), str(Path(__file__)), args.command]))
    if args.command == 'init':
        initialize()
    elif args.command in ('serve', 'serve-local'):
        serve(local=args.command == 'serve-local')
    elif args.command in ('start', 'local'):
        start(local=args.command == 'local')
    elif args.command == 'share':
        from share_service import run
        run()
    elif args.command in ('stop', 'status'):
        path = STATE / 'service.json'
        data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'status': 'stopped'}
        if args.command == 'stop' and data['status'] in ('starting', 'checking', 'running', 'reconnecting', 'degraded'):
            (STATE / ('stop-' + data['session'])).touch()
            print('已请求停止本次网站和隧道。')
        else:
            print(json.dumps(data, ensure_ascii=False))
    elif args.command == 'manage':
        raise SystemExit(subprocess.call([str(PYTHON), str(WEB / 'manage.py'), *args.arguments], env=environment(), cwd=WEB))
    elif args.command == 'ai':
        if len(args.arguments) > 1:
            parser.error('用法：python deploy/windows.py ai "视频路径或RTSP地址或摄像头编号"')
        env = environment()
        source = args.arguments[0] if args.arguments else getpass.getpass('输入视频绝对路径、RTSP 地址或摄像头编号（不回显）：').strip()
        if not source:
            raise ValueError('视频源不能为空')
        env['VIDEO_SOURCE'] = source
        raise SystemExit(subprocess.call([str(PYTHON), str(AI / 'video_server.py')], env=env, cwd=AI))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('服务已停止。')
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print('操作失败：' + str(error), file=sys.stderr)
        raise SystemExit(1)
