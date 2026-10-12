"""在部署服务器生成本地配置和随机密钥，不覆盖已有配置。"""
import argparse
import getpass
import os
from pathlib import Path
import re
import secrets


def write_new(path, content):
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(content)
    if os.name != 'nt':
        path.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', help='网站域名，不含协议或路径')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    env_file = root / '.env'
    if not env_file.exists():
        domain = args.domain or input('请输入已解析到服务器的域名：').strip()
        if not re.fullmatch(r'(?=.{1,253}$)[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?', domain) or '.' not in domain:
            parser.error('域名格式不正确，请填写例如 community.example.com')
        template = (root / '.env.example').read_text(encoding='utf-8')
        write_new(env_file, template.replace('community.example.com', domain))
    secret_dir = root / 'secrets'
    secret_dir.mkdir(exist_ok=True)
    if os.name != 'nt':
        secret_dir.chmod(0o700)
    for name in ('django_secret_key', 'db_password', 'db_root_password', 'ai_ingest_token'):
        target = secret_dir / (name + '.txt')
        if not target.exists():
            write_new(target, secrets.token_urlsafe(48) + '\n')
    target = secret_dir / 'deepseek_api_key.txt'
    if not target.exists():
        key = getpass.getpass('请输入 DeepSeek API Key（输入不显示）：').strip()
        if not key:
            parser.error('DeepSeek API Key 不能为空；已生成的配置保留，重新运行可继续')
        write_new(target, key + '\n')
    (root / 'input').mkdir(exist_ok=True)
    print('配置已就绪。已有文件未覆盖，密钥未显示。')


if __name__ == '__main__':
    main()
