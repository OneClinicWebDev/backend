from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import Role


@receiver(post_migrate)
def create_roles(sender, **kwargs):
    if sender.name == "core":
        Role.objects.get_or_create(nome="ADMIN")
        Role.objects.get_or_create(nome="SECRETARIO")
        Role.objects.get_or_create(nome="PROFISSIONAL")