from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0015_procedimento_realizado"),
    ]

    operations = [
        migrations.AddField(
            model_name="procedimentorealizado",
            name="destino_sessao",
            field=models.CharField(
                blank=True,
                choices=[
                    ("DEVOLVIDA", "Sessão devolvida"),
                    ("PERDIDA", "Sessão perdida"),
                    ("NAO_APLICAVEL", "Sem sessão de pacote"),
                ],
                default="",
                max_length=20,
            ),
        ),
    ]