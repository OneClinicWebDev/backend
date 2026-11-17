from django.db import migrations, models
from django.db.models import Count, Q


def verificar_duplicidades(apps, schema_editor):
    Pacote = apps.get_model("core", "Pacote")

    duplicados = (
        Pacote.objects.filter(status="ATIVO", modelo__isnull=False)
        .values("cliente_id", "modelo_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )

    if duplicados.exists():
        detalhes = ", ".join(
            f"cliente={d['cliente_id']} modelo={d['modelo_id']} ({d['total']} ativos)"
            for d in duplicados[:20]
        )
        raise RuntimeError(
            "Existem clientes com mais de um pacote ATIVO do mesmo modelo. "
            "Conclua ou cancele os excedentes antes de migrar: " + detalhes
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_primeiroacessocodigo"),
    ]

    operations = [
        migrations.RunPython(verificar_duplicidades, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="pacote",
            constraint=models.UniqueConstraint(
                condition=Q(status="ATIVO"),
                fields=("cliente", "modelo"),
                name="uniq_pacote_ativo_por_cliente_modelo",
            ),
        ),
    ]