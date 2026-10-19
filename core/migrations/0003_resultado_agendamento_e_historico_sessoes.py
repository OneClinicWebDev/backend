
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrar_estados_antigos(apps, schema_editor):
    Agendamento = apps.get_model("core", "Agendamento")
    SessaoPacote = apps.get_model("core", "SessaoPacote")

    Agendamento.objects.filter(status="FALTA").update(
        status="CONCLUIDO",
        resultado="FALTA",
    )

    SessaoPacote.objects.filter(status="REALIZADA").update(
        status="UTILIZADA",
    )

    SessaoPacote.objects.filter(status="FALTA").update(
        status="PERDIDA",
    )


def reverter_estados_antigos(apps, schema_editor):
    Agendamento = apps.get_model("core", "Agendamento")
    SessaoPacote = apps.get_model("core", "SessaoPacote")

    SessaoPacote.objects.filter(status="UTILIZADA").update(
        status="REALIZADA",
    )

    SessaoPacote.objects.filter(status="PERDIDA").update(
        status="FALTA",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_usuario_is_staff_usuario_is_superuser"),
    ]

    operations = [
        migrations.AddField(
            model_name="agendamento",
            name="resultado",
            field=models.CharField(
                choices=[
                    ("AGUARDANDO_RESULTADO", "Aguardando resultado"),
                    ("REALIZADO", "Realizado"),
                    ("FALTA", "Falta"),
                ],
                default="AGUARDANDO_RESULTADO",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="agendamento",
            name="motivo_cancelamento",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="historicosessao",
            name="usuario_executor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="historicos_sessao_executados",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="historicosessao",
            name="agendamento_relacionado",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="historicos_sessao",
                to="core.agendamento",
            ),
        ),
        migrations.AddField(
            model_name="historicosessao",
            name="motivo",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="historicosessao",
            name="justificativa",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="historicosessao",
            name="estado_anterior",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AlterField(
            model_name="historicosessao",
            name="sessao",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="historico",
                to="core.sessaopacote",
            ),
        ),
        migrations.RunPython(
            migrar_estados_antigos,
            reverter_estados_antigos,
        ),
        migrations.AlterField(
            model_name="agendamento",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDENTE", "Pendente"),
                    ("CONFIRMADO", "Confirmado"),
                    ("CONCLUIDO", "Concluído"),
                    ("CANCELADO", "Cancelado"),
                ],
                default="PENDENTE",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="sessaopacote",
            name="status",
            field=models.CharField(
                choices=[
                    ("DISPONIVEL", "Disponível"),
                    ("AGENDADA", "Agendada"),
                    ("UTILIZADA", "Utilizada"),
                    ("PERDIDA", "Perdida"),
                    ("CANCELADA", "Cancelada"),
                ],
                default="DISPONIVEL",
                max_length=20,
            ),
        ),
    ]
