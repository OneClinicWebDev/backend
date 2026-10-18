from rest_framework import serializers
from core.models import (
    Clinica, Colaborador, Cliente, Especialidade, Role, 
    Servico, Agendamento, Pacote, SessaoPacote
)

class ClinicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinica
        fields = [
            "id", "cnpj", "razao_social", "nome_fantasia",
            "telefone", "email", "cep", "logradouro", "numero",
            "complemento", "bairro", "cidade", "estado",
            "profissionais_podem_editar_agenda", "ativo",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

class ColaboradorSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(source="usuario.nome_completo", read_only=True)
    usuario_cpf = serializers.CharField(source="usuario.cpf", read_only=True)
    role_nome = serializers.CharField(source="role.nome", read_only=True)

    class Meta:
        model = Colaborador
        fields = [
            "id", "usuario", "usuario_nome", "usuario_cpf",
            "clinica", "role", "role_nome", "pode_editar_agenda",
            "ativo", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

class ClienteSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(source="usuario.nome_completo", read_only=True)
    usuario_cpf = serializers.CharField(source="usuario.cpf", read_only=True)

    class Meta:
        model = Cliente
        fields = [
            "id", "usuario", "usuario_nome", "usuario_cpf",
            "clinica", "telefone", "email", "cep", "logradouro",
            "numero", "complemento", "bairro", "cidade", "estado",
            "status_cadastro", "status_financeiro",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

class EspecialidadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Especialidade
        fields = [
            "id", "clinica", "nome", "descricao",
            "ativo", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

class ServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servico
        fields = [
            "id", "clinica", "nome", "descricao", 
            "duracao_padrao_minutos", "preco", "ativo", 
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

class AgendamentoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.usuario.nome_completo", read_only=True)
    profissional_nome = serializers.CharField(source="profissional.usuario.nome_completo", read_only=True)
    servico_nome = serializers.CharField(source="servico.nome", read_only=True)

    class Meta:
        model = Agendamento
        fields = [
            "id", "clinica", "cliente", "cliente_nome", 
            "profissional", "profissional_nome", 
            "servico", "servico_nome", "agendamento_anterior",
            "data_hora_inicio", "data_hora_fim", "status", 
            "resultado", "motivo_cancelamento", "observacoes",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

class SessaoPacoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessaoPacote
        fields = ['id', 'pacote', 'agendamento', 'estado', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class PacoteSerializer(serializers.ModelSerializer):
    sessoes = SessaoPacoteSerializer(many=True, read_only=True)
    cliente_nome = serializers.CharField(source="cliente.usuario.nome_completo", read_only=True)
    servico_nome = serializers.CharField(source="servico.nome", read_only=True)

    class Meta:
        model = Pacote
        fields = [
            'id', 'clinica', 'cliente', 'cliente_nome', 'servico', 'servico_nome',
            'quantidade_contratada', 'ativo', 'sessoes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'ativo']