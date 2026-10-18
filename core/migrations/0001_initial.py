import core.models
import django.contrib.postgres.constraints
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models
from django.contrib.postgres.operations import BtreeGistExtension 


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        BtreeGistExtension(), 
        migrations.CreateModel(
            name='Usuario',
            fields=[
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('cpf', models.CharField(max_length=11, unique=True, validators=[core.models.validate_cpf])),
                ('nome_completo', models.CharField(max_length=255)),
                ('data_nascimento', models.DateField()),
                ('telefone', models.CharField(blank=True, max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'usuarios',
            },
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(choices=[('ADMIN', 'Administrador'), ('SECRETARIO', 'Secretário'), ('PROFISSIONAL', 'Profissional')], max_length=20, unique=True)),
            ],
            options={
                'db_table': 'roles',
            },
        ),
        migrations.CreateModel(
            name='Clinica',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('cnpj', models.CharField(max_length=14, unique=True, validators=[core.models.validate_cnpj])),
                ('razao_social', models.CharField(max_length=255)),
                ('nome_fantasia', models.CharField(max_length=255)),
                ('telefone', models.CharField(max_length=20)),
                ('endereco', models.CharField(blank=True, max_length=255)),
                ('profissionais_podem_editar_agenda', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'clinicas',
                'constraints': [models.CheckConstraint(condition=models.Q(('cnpj__regex', '^[0-9]{14}$')), name='chk_cnpj_format'), models.CheckConstraint(condition=models.Q(('telefone__regex', '^[0-9]+$')), name='chk_clinica_telefone_format')],
            },
        ),
        migrations.CreateModel(
            name='Cliente',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('telefone', models.CharField(max_length=20)),
                ('cep', models.CharField(blank=True, max_length=8)),
                ('numero_endereco', models.CharField(blank=True, max_length=20)),
                ('status_cadastro', models.CharField(choices=[('ATIVO', 'Ativo'), ('INATIVO', 'Inativo')], default='ATIVO', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vinculos_cliente', to=settings.AUTH_USER_MODEL)),
                ('clinica', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clientes', to='core.clinica')),
            ],
            options={
                'db_table': 'clientes',
                'unique_together': {('usuario', 'clinica')},
            },
        ),
        migrations.CreateModel(
            name='Auditoria',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('acao', models.CharField(choices=[('CREATE', 'Criação'), ('UPDATE', 'Atualização'), ('DELETE', 'Exclusão'), ('DEACTIVATE', 'Desativação')], max_length=20)),
                ('entidade', models.CharField(max_length=50)),
                ('objeto_id', models.CharField(max_length=255)),
                ('dados_anteriores', models.JSONField(blank=True, null=True)),
                ('dados_novos', models.JSONField(blank=True, null=True)),
                ('origem', models.CharField(choices=[('USUARIO', 'Usuário via API'), ('SISTEMA', 'Rotina Automática / Sistema')], default='USUARIO', max_length=20)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('data_hora', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='auditorias', to=settings.AUTH_USER_MODEL)),
                ('clinica', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='auditorias', to='core.clinica')),
            ],
            options={
                'db_table': 'auditoria',
                'ordering': ['-data_hora'],
            },
        ),
        migrations.CreateModel(
            name='Colaborador',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('ativo', models.BooleanField(default=True)),
                ('pode_editar_agenda', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('clinica', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='colaboradores', to='core.clinica')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vinculos_colaborador', to=settings.AUTH_USER_MODEL)),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.role')),
            ],
            options={
                'db_table': 'colaboradores',
                'unique_together': {('usuario', 'clinica')},
            },
        ),
        migrations.CreateModel(
            name='Servico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=255)),
                ('duracao_padrao_minutos', models.PositiveIntegerField()),
                ('ativo', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('clinica', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='servicos', to='core.clinica')),
            ],
            options={
                'db_table': 'servicos',
            },
        ),
        migrations.CreateModel(
            name='Pacote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantidade_sessoes', models.PositiveIntegerField()),
                ('valor_total', models.DecimalField(decimal_places=2, max_digits=10)),
                ('data_vencimento', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('ATIVO', 'Ativo'), ('CONCLUIDO', 'Concluído'), ('CANCELADO', 'Cancelado')], default='ATIVO', max_length=20)),
                ('observacoes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pacotes', to='core.cliente')),
                ('clinica', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pacotes', to='core.clinica')),
                ('servico', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pacotes', to='core.servico')),
            ],
            options={
                'db_table': 'pacotes',
            },
        ),
        migrations.CreateModel(
            name='Agendamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_hora_inicio', models.DateTimeField()),
                ('data_hora_fim', models.DateTimeField()),
                ('status', models.CharField(choices=[('PENDENTE', 'Pendente'), ('CONFIRMADO', 'Confirmado'), ('CONCLUIDO', 'Concluído'), ('CANCELADO', 'Cancelado'), ('FALTA', 'Falta')], default='PENDENTE', max_length=20)),
                ('observacoes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='agendamentos', to='core.cliente')),
                ('clinica', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='agendamentos', to='core.clinica')),
                ('profissional', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='agendamentos_profissional', to='core.colaborador')),
                ('pacote_origem', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='agendamentos', to='core.pacote')),
                ('servico', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='agendamentos', to='core.servico')),
            ],
            options={
                'db_table': 'agendamentos',
            },
        ),
        migrations.CreateModel(
            name='SessaoPacote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('AGENDADA', 'Agendada'), ('REALIZADA', 'Realizada'), ('CANCELADA', 'Cancelada'), ('FALTA', 'Falta')], default='AGENDADA', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('agendamento', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sessao_pacote', to='core.agendamento')),
                ('pacote', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessoes', to='core.pacote')),
            ],
            options={
                'db_table': 'sessoes_pacote',
            },
        ),
        migrations.CreateModel(
            name='HistoricoSessao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado_anterior', models.CharField(max_length=20)),
                ('estado_novo', models.CharField(max_length=20)),
                ('data_alteracao', models.DateTimeField(auto_now_add=True)),
                ('sessao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='historico', to='core.sessaopacote')),
            ],
            options={
                'db_table': 'historico_sessoes',
            },
        ),
        migrations.AddConstraint(
            model_name='agendamento',
            constraint=models.CheckConstraint(condition=models.Q(('data_hora_fim__gt', models.F('data_hora_inicio'))), name='chk_data_fim_maior_inicio'),
        ),
        migrations.AddConstraint(
            model_name='agendamento',
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(condition=models.Q(('status', 'CONFIRMADO')), expressions=[('profissional', '='), (models.Func(models.F('data_hora_inicio'), models.F('data_hora_fim'), function='tstzrange'), '&&')], name='chk_sobreposicao_profissional'),
        ),
        migrations.AddConstraint(
            model_name='agendamento',
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(condition=models.Q(('status', 'CONFIRMADO')), expressions=[('cliente', '='), (models.Func(models.F('data_hora_inicio'), models.F('data_hora_fim'), function='tstzrange'), '&&')], name='chk_sobreposicao_cliente'),
        ),
    ]