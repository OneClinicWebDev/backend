from django.db import migrations


def criar_roles(apps, schema_editor):
    Role = apps.get_model("core", "Role")

    roles = [
        ("ADMIN", "Admin"),
        ("SECRETARIO", "Secretário"),
        ("PROFISSIONAL", "Profissional"),
    ]

    for nome, _ in roles:
        Role.objects.get_or_create(nome=nome)


def remover_roles(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    Role.objects.filter(
        nome__in=["ADMIN", "SECRETARIO", "PROFISSIONAL"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(criar_roles, remover_roles),
    ]