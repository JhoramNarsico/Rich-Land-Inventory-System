from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

class Command(BaseCommand):
    help = 'Ensures permissions are set correctly for groups'

    def handle(self, *args, **options):
        # Ensure Salesman has refund access
        try:
            salesman, _ = Group.objects.get_or_create(name='Salesman')
            perm = Permission.objects.get(codename='can_adjust_stock')
            salesman.permissions.add(perm)
            self.stdout.write(self.style.SUCCESS('Successfully ensured Salesman group has can_adjust_stock permission'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error setting permissions: {e}'))
