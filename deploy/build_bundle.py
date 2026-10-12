"""只打包部署所需源文件，排除本地密钥、用户文件和数据库。"""
import argparse
import hashlib
from pathlib import Path
import re
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB = 't7/Python/community_system'
AI = 't7/Python/aiWatchdog-main'
AI_FILES = (
    'config.py', 'django_integration.py', 'multi_modal_analyzer.py', 'prompt.py',
    'utility.py', 'video_recording.py', 'video_server.py',
    'requirements.production.txt', 'test_deepseek.py', 'test_deployment.py',
)
PRIVATE_NAMES = {'settings.local.json', 'api_keys.local.json', '.env'}
EXCLUDED_PARTS = {'.git', '__pycache__', 'venv', '.venv', 'node_modules', 'secrets', 'input'}


def deployment_files(root):
    selected = [root / '.dockerignore']
    selected.extend(root / name for name in ('打开网站.cmd', '关闭网站.cmd'))
    for path in (root / 'deploy').rglob('*'):
        relative = path.relative_to(root / 'deploy')
        if path.is_file() and not (set(relative.parts) & EXCLUDED_PARTS) and path.name not in PRIVATE_NAMES:
            if path.suffix in {'.py', '.sh', '.cmd', '.yaml', '.md'} or path.name in {
                'Caddyfile', 'Dockerfile.web', 'Dockerfile.ai', '.env.example'
            } or path.name == 'requirements.validation.txt':
                selected.append(path)
    for folder in ('community_project', 'core'):
        for path in (root / WEB / folder).rglob('*'):
            if path.is_file() and not (set(path.parts) & EXCLUDED_PARTS) and path.name not in PRIVATE_NAMES:
                if path.suffix in {'.py', '.html'}:
                    selected.append(path)
    for folder in ('css', 'js', 'images'):
        for path in (root / WEB / 'static' / folder).rglob('*'):
            if path.is_file() and (path.suffix.lower() in {'.css', '.js', '.svg', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.woff', '.woff2', '.ttf'} or path.name.startswith('LICENSE.')):
                selected.append(path)
    selected.extend(root / WEB / name for name in ('manage.py', 'requirements.production.txt', 'requirements.windows.txt'))
    selected.extend(root / AI / name for name in AI_FILES)
    return sorted(set(selected))


def checked_content(path):
    data = path.read_bytes()
    if path.suffix in {'.py', '.html', '.md', '.yaml', '.sh', '.txt', '.js', '.css'} or path.name.startswith('Dockerfile'):
        # 已知 API key 与私钥格式直接阻止打包；不打印命中的内容。
        if re.search(rb'sk-[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----', data):
            raise ValueError(f'检测到疑似密钥，请先移除：{path.relative_to(PROJECT_ROOT)}')
        data = data.replace(b'\r\n', b'\n')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=PROJECT_ROOT / 'dist' / 'community-deploy.zip')
    args = parser.parse_args()
    files = deployment_files(PROJECT_ROOT)
    contents = [(path.relative_to(PROJECT_ROOT).as_posix(), checked_content(path)) for path in files]
    manifest = '\n'.join(f'{hashlib.sha256(data).hexdigest()}  {name}' for name, data in contents) + '\n'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, data in contents:
            info = zipfile.ZipInfo('community-deploy/' + name, date_time=(2026, 10, 12, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            bundle.writestr(info, data)
        bundle.writestr('community-deploy/SHA256SUMS', manifest)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix('.zip.sha256').write_text(digest + '  ' + args.output.name + '\n', encoding='utf-8')
    print(f'打包完成：{args.output}；{len(files)} 个源文件；{args.output.stat().st_size} 字节')


if __name__ == '__main__':
    main()
