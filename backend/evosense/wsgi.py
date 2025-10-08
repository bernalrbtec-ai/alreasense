"""
WSGI config for alrea_sense project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')

application = get_wsgi_application()
