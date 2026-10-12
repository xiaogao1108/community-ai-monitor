from community_project.settings import *


SECRET_KEY = 'isolated-test-settings-only'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.PBKDF2PasswordHasher']
