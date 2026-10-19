
from rest_framework import serializers

from core.models import (
    Usuario,
    Clinica,
    Role,
    Colaborador,
    Cliente,
    Servico,
    Agendamento,
    Pacote,
    SessaoPacote,
)


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = [
            "id",
            "cpf",
            "nome_completo",
            "data_nascimento",
            "telefone",
        ]
        read_only_fields = fields


class ClinicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinica
        fields = "__all__"
        read_only_fields = [
            "id",
            "cnpj",
            "razao_social",
            "nome_fantasia",
            "telefone",
            "endereco",
            "created_at",
            "updated_at",
        ]


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = "__all__"
        read_only_fields = ["id", "nome"]


class ColaboradorSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(
        source="usuario.nome_completo",
        read_only=True,
    )
    role_nome = serializers.CharField(
        source="role.nome",
        read_only=True,
    )

    class Meta:
        model = Colaborador
        fields = [
            "id",
            "usuario",
            "usuario_nome",
            "clinica",
            "role",
            "role_nome",
            "ativo",
            "pode_editar_agenda",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "usuario",
            "usuario_nome",
            "clinica",
            "ativo",
            "created_at",
            "updated_at",
        ]


class ClienteSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(
        source="usuario.nome_completo",
        read_only=True,
    )
    usuario_cpf = serializers.CharField(
        source="usuario.cpf",
        read_only=True,
    )

    class Meta:
        model = Cliente
        fields = [
            "id",
            "usuario",
            "usuario_nome",
            "usuario_cpf",
            "clinica",
            "telefone",
            "cep",
            "numero_endereco",
            "status_cadastro",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "usuario",
            "usuario_nome",
            "usuario_cpf",
            "clinica",
            "status_cadastro",
            "created_at",
            "updated_at",
        ]


class ServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servico
        fields = "__all__"
        read_only_fields = [
            "clinica",
            "created_at",
            "updated_at",
        ]


class AgendamentoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(
        source="cliente.usuario.nome_completo",
        read_only=True,
    )
    profissional_nome = serializers.CharField(
        source="profissional.usuario.nome_completo",
        read_only=True,
    )
    servico_nome = serializers.CharField(
        source="servico.nome",
        read_only=True,
    )
    pacote_id = serializers.UUIDField(
        source="pacote_origem_id",
        read_only=True,
    )

    class Meta:
        model = Agendamento
        fields = "__all__"
        read_only_fields = [
            "clinica",
            "status",
            "resultado",
            "motivo_cancelamento",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        request = self.context.get("request")
        clinica = getattr(request, "clinica", None) if request else None

        if clinica is None:
            raise serializers.ValidationError(
                "Não foi possível determinar a clínica ativa."
            )

        cliente = attrs.get("cliente")
        profissional = attrs.get("profissional")
        servico = attrs.get("servico")
        pacote = attrs.get("pacote_origem")

        if cliente is not None and cliente.clinica_id != clinica.id:
            raise serializers.ValidationError(
                {"cliente": "O cliente não pertence à clínica ativa."}
            )

        if profissional is not None:
            if profissional.clinica_id != clinica.id or not profissional.ativo:
                raise serializers.ValidationError(
                    {"profissional": "Profissional inválido para a clínica ativa."}
                )
            if profissional.role.nome != Role.PROFISSIONAL:
                raise serializers.ValidationError(
                    {"profissional": "O colaborador selecionado não é profissional."}
                )

        if servico is not None:
            if servico.clinica_id != clinica.id or not servico.ativo:
                raise serializers.ValidationError(
                    {"servico": "Serviço inválido para a clínica ativa."}
                )

        if pacote is not None:
            if pacote.clinica_id != clinica.id:
                raise serializers.ValidationError(
                    {"pacote_origem": "O pacote não pertence à clínica ativa."}
                )
            if pacote.status != Pacote.ATIVO:
                raise serializers.ValidationError(
                    {"pacote_origem": "O pacote não está ativo."}
                )
            if cliente is not None and pacote.cliente_id != cliente.id:
                raise serializers.ValidationError(
                    {"pacote_origem": "O pacote pertence a outro cliente."}
                )
            if servico is not None and pacote.servico_id != servico.id:
                raise serializers.ValidationError(
                    {"pacote_origem": "O pacote pertence a outro serviço."}
                )

        return attrs


class PacoteSerializer(serializers.ModelSerializer):
    saldo_sessoes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Pacote
        fields = "__all__"
        read_only_fields = [
            "clinica",
            "status",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        request = self.context.get("request")
        clinica = getattr(request, "clinica", None) if request else None

        if clinica is None:
            raise serializers.ValidationError(
                "Não foi possível determinar a clínica ativa."
            )

        cliente = attrs.get("cliente")
        servico = attrs.get("servico")

        if cliente is not None:
            if cliente.clinica_id != clinica.id:
                raise serializers.ValidationError(
                    {"cliente": "O cliente não pertence à clínica ativa."}
                )
            if cliente.status_cadastro != Cliente.ATIVO:
                raise serializers.ValidationError(
                    {"cliente": "O cliente está inativo."}
                )

        if servico is not None:
            if servico.clinica_id != clinica.id or not servico.ativo:
                raise serializers.ValidationError(
                    {"servico": "Serviço inválido para a clínica ativa."}
                )

        quantidade = attrs.get("quantidade_sessoes")
        if quantidade is not None and quantidade < 1:
            raise serializers.ValidationError(
                {"quantidade_sessoes": "O pacote precisa ter pelo menos uma sessão."}
            )

        valor = attrs.get("valor_total")
        if valor is not None and valor < 0:
            raise serializers.ValidationError(
                {"valor_total": "O valor total não pode ser negativo."}
            )

        return attrs


class SessaoPacoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessaoPacote
        fields = "__all__"
        read_only_fields = fields
