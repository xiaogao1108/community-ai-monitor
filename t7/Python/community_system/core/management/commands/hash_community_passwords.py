from django.contrib.auth.hashers import identify_hasher, make_password
from django.core.management.base import BaseCommand

from core.models import User


class Command(BaseCommand):
    help = '检查历史明文密码；传入 --apply 才会转换为哈希。请先备份数据库。'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        count = 0
        for user in User.objects.only('user_id', 'password').iterator():
            if user.password.startswith('!'):
                continue
            try:
                identify_hasher(user.password)
            except ValueError:
                count += 1
                if options['apply']:
                    User.objects.filter(user_id=user.user_id, password=user.password).update(
                        password=make_password(user.password),
                    )
        action = '已转换' if options['apply'] else '待转换（未修改数据库）'
        self.stdout.write(f'{action}: {count}')
