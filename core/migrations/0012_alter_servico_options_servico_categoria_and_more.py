
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "core",
            "0011_remove_colaborador_especialidades_especialidade_and_more",
        ),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="servico",
            options={"ordering": ["nome"]},
        ),
        migrations.AlterModelTable(
            name="servico",
            table="core_servico",
        ),
        migrations.AddField(
            model_name="servico",
            name="categoria",
            field=models.CharField(
                blank=True,
                default="",
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name="servico",
            name="descricao",
            field=models.TextField(
                blank=True,
                default="",
            ),
        ),
        migrations.AddField(
            model_name="servico",
            name="preco",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=10,
            ),
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE public.core_servico
                ADD COLUMN IF NOT EXISTS duracao_padrao_minutos integer NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name="ModeloPacote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nome", models.CharField(max_length=255)),
                ("quantidade_sessoes", models.PositiveIntegerField()),
                (
                    "valor_total",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                    ),
                ),
                (
                    "categoria",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=100,
                    ),
                ),
                (
                    "descricao",
                    models.TextField(
                        blank=True,
                        default="",
                    ),
                ),
                ("ativo", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "clinica",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="modelos_pacote",
                        to="core.clinica",
                    ),
                ),
                (
                    "servico",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="modelos_pacote",
                        to="core.servico",
                    ),
                ),
            ],
            options={
                "db_table": "modelos_pacote",
                "ordering": ["nome"],
            },
        ),
        migrations.AddField(
            model_name="pacote",
            name="modelo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="aquisicoes",
                to="core.modelopacote",
            ),
        ),
        migrations.AddConstraint(
            model_name="modelopacote",
            constraint=models.CheckConstraint(
                condition=models.Q(quantidade_sessoes__gte=1),
                name="chk_modelo_pacote_sessoes_positivas",
            ),
        ),
        migrations.AddConstraint(
            model_name="modelopacote",
            constraint=models.CheckConstraint(
                condition=models.Q(valor_total__gte=0),
                name="chk_modelo_pacote_valor_nao_negativo",
            ),
        ),
    ]
