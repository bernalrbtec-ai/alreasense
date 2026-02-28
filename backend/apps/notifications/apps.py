from django.apps import AppConfig


def _normalize_bytea_for_decrypt(value):
    """Converte bytea em formato hex (ex.: b'\\x80...' do PostgreSQL) para bytes reais."""
    if value is None:
        return value
    if isinstance(value, bytes) and value.startswith(b'\\x'):
        try:
            return bytes.fromhex(value[2:].decode('ascii'))
        except (ValueError, UnicodeDecodeError):
            pass
    if isinstance(value, str) and value.startswith('\\x'):
        try:
            return bytes.fromhex(value[2:])
        except ValueError:
            pass
    return value


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'
    verbose_name = 'Notifications'

    def ready(self):
        import apps.notifications.signals
        # Patch: quando bytea vem em hex no deferred load, django-cryptography recebe b'\\x80...'
        # e o primeiro byte vira 0x5c -> "Signature version not supported". Normalizar para bytes reais.
        from django.utils.encoding import force_bytes
        from django_cryptography.fields import EncryptedMixin
        _original_from_db_value = EncryptedMixin.from_db_value

        def _patched_from_db_value(self, value, *args, **kwargs):
            value = _normalize_bytea_for_decrypt(value)
            if value is not None:
                value = force_bytes(value)
            return _original_from_db_value(self, value, *args, **kwargs)

        EncryptedMixin.from_db_value = _patched_from_db_value

