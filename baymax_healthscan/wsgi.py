import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baymax_healthscan.settings')

wsgi = get_wsgi_application()
