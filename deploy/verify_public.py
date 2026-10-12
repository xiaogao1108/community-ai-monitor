"""连续检查当前公网网址，不读取或提交用户凭据。"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import time

import requests

from windows import STATE, write_json


ROUTES = [('GET', '/health/', 200), ('GET', '/login/', 200),
          ('GET', '/static/css/style.css', 200),
          ('GET', '/static/css/vendor/bootstrap.min.css', 200),
          ('GET', '/static/js/vendor/jquery.min.js', 200),
          ('GET', '/static/css/vendor/fontawesome/webfonts/fa-solid-900.woff2', 200),
          ('GET', '/static/video/abnormal/test.mp4', 401), ('POST', '/login/', 403)]


def check(url, route, cycle, system_proxy=False):
    method, path, expected = route
    started = time.monotonic()
    result = {'cycle': cycle, 'url': url, 'method': method, 'path': path, 'expected': expected}
    headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1'} if cycle % 2 else {}
    try:
        with requests.Session() as session:
            session.trust_env = system_proxy
            response = session.request(method, url + path, headers=headers,
                                       params={'verify': time.time_ns()}, timeout=10, allow_redirects=False)
        result.update(status=response.status_code, ok=response.status_code == expected)
        if path == '/health/' and result['ok']:
            result['ok'] = response.json().get('status') == 'ok'
        if path == '/login/' and method == 'GET' and result['ok']:
            result['ok'] = 'csrfmiddlewaretoken' in response.text
        if response.is_redirect:
            result['redirect'] = response.headers.get('Location')
    except (requests.RequestException, ValueError) as error:
        result.update(ok=False, error=type(error).__name__)
    result['seconds'] = round(time.monotonic() - started, 2)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rounds', type=int, default=30)
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--system-proxy', action='store_true', help='额外比较本机代理线路；默认直接访问公网')
    args = parser.parse_args()
    if args.rounds < 1 or args.interval < 0:
        parser.error('rounds 必须为正数，interval 不能为负数')
    started = time.monotonic()
    report = {'started_at': time.time(), 'network': 'system-proxy' if args.system_proxy else 'direct', 'results': []}
    destination = STATE / 'logs' / ('public-verification-' + str(time.time_ns()) + '.json')
    with ThreadPoolExecutor(max_workers=4) as executor:
        for cycle in range(args.rounds):
            state = json.loads((STATE / 'service.json').read_text(encoding='utf-8'))
            url = state.get('public_url')
            if not url or not url.startswith('https://'):
                results = [{'cycle': cycle, 'ok': False, 'error': 'NoPublicUrl'}]
            else:
                results = list(executor.map(lambda route: check(url, route, cycle, args.system_proxy), ROUTES))
            report['results'].extend(results)
            report.update(elapsed_seconds=round(time.monotonic() - started, 1),
                          passed=sum(item['ok'] for item in report['results']), total=len(report['results']))
            write_json(destination, report)
            print(f"Round {cycle + 1}/{args.rounds}: {sum(item['ok'] for item in results)}/{len(results)}; total {report['passed']}/{report['total']}", flush=True)
            if cycle + 1 < args.rounds:
                time.sleep(args.interval)
    print('Report: ' + str(destination))
    return 0 if report['passed'] == report['total'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
