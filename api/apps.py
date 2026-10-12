from django.apps import AppConfig
from django.db.backends.signals import connection_created


def configure_sqlite_connection(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        try:
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA journal_mode=WAL;')
                cursor.execute('PRAGMA synchronous=NORMAL;')
                cursor.execute('PRAGMA busy_timeout=20000;')
        except Exception:
            pass


class ApiConfig(AppConfig):
    name = 'api'

    def ready(self):
        connection_created.connect(configure_sqlite_connection)
