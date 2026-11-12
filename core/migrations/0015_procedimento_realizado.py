import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def popular_procedimentos(apps, schema_editor):
    Agendamento = apps.get_model("core", "Agendamento")
    Procedimento = apps.get_model("core", "ProcedimentoRealizado")
    Sessao = apps.get_model("core", "SessaoPacote")
    Pacote = apps.get_model("core", "Pacote")

    existentes = set(Procedimento.objects.values_list("agendamento_id", flat=True))

    concluidos = (
        Agendamento.objects.filter(status="CONCLUIDO", resultado="REALIZADO")
        .select_related("cliente__usuario", "profissional__usuario", "servico")
        .order_by("pk")
    )

    for ag in concluidos.iterator():
        if ag.pk in existentes:
            continue

        sessao = Sessao.objects.filter(agendamento_id=ag.pk).first()
        pacote = sessao.pacote if sessao else ag.pacote_origem
        valor = ag.preco_acordado
        if valor is None:
            valor = 0 if pacote else (ag.servico.preco or 0)

        minutos = int((ag.data_hora_fim - ag.data_hora_inicio).total_seconds() // 60)
        if minutos <= 0:
            minutos = ag.servico.duracao_padrao_minutos

        Procedimento.objects.create(
            clinica_id=ag.clinica_id,
            cliente_id=ag.cliente_id,
            profissional_id=ag.profissional_id,
            servico_id=ag.servico_id,
            agendamento_id=ag.pk,
            pacote_id=pacote.pk if pacote else None,
            sessao_id=sessao.pk if sessao and sessao.status == "UTILIZADA" else None,
            cliente_nome=ag.cliente.usuario.nome_completo,
            profissional_nome=ag.profissional.usuario.nome_completo,
            servico_nome=ag.servico.nome,
            pacote_nome=(
                (pacote.modelo.nome if pacote.modelo_id else f"Pacote {pacote.pk}")
                if pacote
                else ""
            ),
            valor=valor,
            duracao_minutos=minutos,
            realizado_em=ag.data_hora_fim,
            origem="MIGRACAO",
            status="REALIZADO",
        )

    for pacote in Pacote.objects.filter(status="ATIVO"):
        if not Sessao.objects.filter(
            pacote_id=pacote.pk, status__in=["DISPONIVEL", "AGENDADA"]
        ).exists() and Sessao.objects.filter(pacote_id=pacote.pk).exists():
            pacote.status = "CONCLUIDO"
            pacote.save(update_fields=["status"])


def reverter(apps, schema_editor):
    apps.get_model("core", "ProcedimentoRealizado").objects.filter(origem="MIGRACAO").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_roles_especialidades_datas"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcedimentoRealizado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cliente_nome", models.CharField(max_length=255)),
                ("profissional_nome", models.CharField(max_length=255)),
                ("servico_nome", models.CharField(max_length=255)),
                ("pacote_nome", models.CharField(blank=True, default="", max_length=255)),
                ("valor", models.DecimalField(decimal_places=2, max_digits=10)),
                ("duracao_minutos", models.PositiveIntegerField()),
                ("realizado_em", models.DateTimeField()),
                ("origem", models.CharField(choices=[("AUTOMATICA", "Conclusão automática"), ("MANUAL", "Conclusão manual"), ("MIGRACAO", "Migração de histórico")], max_length=20)),
                ("status", models.CharField(choices=[("REALIZADO", "Realizado"), ("ESTORNADO", "Estornado")], default="REALIZADO", max_length=20)),
                ("estornado_em", models.DateTimeField(blank=True, null=True)),
                ("motivo_estorno", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("agendamento", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="procedimento_realizado", to="core.agendamento")),
                ("cliente", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="procedimentos_realizados", to="core.cliente")),
                ("clinica", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="procedimentos_realizados", to="core.clinica")),
                ("estornado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="procedimentos_estornados", to=settings.AUTH_USER_MODEL)),
                ("pacote", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="procedimentos_realizados", to="core.pacote")),
                ("profissional", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="procedimentos_realizados", to="core.colaborador")),
                ("registrado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="procedimentos_registrados", to=settings.AUTH_USER_MODEL)),
                ("servico", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="procedimentos_realizados", to="core.servico")),
                ("sessao", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="procedimentos_realizados", to="core.sessaopacote")),
            ],
            options={
                "db_table": "procedimentos_realizados",
                "ordering": ["-realizado_em", "-pk"],
            },
        ),
        migrations.AddIndex(
            model_name="procedimentorealizado",
            index=models.Index(fields=["cliente", "realizado_em"], name="idx_proc_cliente_data"),
        ),
        migrations.AddIndex(
            model_name="procedimentorealizado",
            index=models.Index(fields=["clinica", "realizado_em"], name="idx_proc_clinica_data"),
        ),
        migrations.AddConstraint(
            model_name="procedimentorealizado",
            constraint=models.CheckConstraint(condition=models.Q(("valor__gte", 0)), name="chk_proc_realizado_valor_nao_negativo"),
        ),
        migrations.RunPython(popular_procedimentos, reverter),
    ]