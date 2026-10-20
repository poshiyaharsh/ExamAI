import secrets
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generate a cryptographically secure random slug for SUPER_ADMIN_PATH.'

    def handle(self, *args, **options):
        # 32 bytes of entropy encoded as hex gives 64 hex characters
        slug = secrets.token_hex(32)

        self.stdout.write(self.style.SUCCESS('\n================================================================='))
        self.stdout.write(self.style.SUCCESS('  EXAMAI SUPER ADMIN - SECURE PATH SLUG GENERATOR'))
        self.stdout.write(self.style.SUCCESS('=================================================================\n'))
        self.stdout.write('Generated random secret path slug:\n')
        self.stdout.write(self.style.WARNING(f'  {slug}\n'))
        self.stdout.write('Add this to your .env file:\n')
        self.stdout.write(self.style.MIGRATE_HEADING(f'  SUPER_ADMIN_PATH={slug}\n'))
        self.stdout.write(self.style.NOTICE(
            'Keep this slug secret. It acts as the cloaked URL mount prefix for the Super Admin portal.\n'
        ))
