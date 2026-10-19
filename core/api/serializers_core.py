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
        read_only_fields = fields


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = "__all__"
        read_only_fields = fields


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
        ]
        read_only_fields = [
            "id",
            "usuario_nome",
            "clinica",
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
        ]
        read_only_fields = [
            "id",
            "usuario_nome",
            "usuario_cpf",
            "clinica",
            "status_cadastro",
        ]


class ServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servico
        fields = "__all__"
        read_only_fields = [
            "id",
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

    class Meta:
        model = Agendamento
        fields = "__all__"
        read_only_fields = [
            "id",
            "clinica",
            "status",
            "resultado",
            "motivo_cancelamento",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        request = self.context.get("request")
        clinica = getattr(request, "clinica", None)

        if clinica is None:
            raise serializers.ValidationError(
                "Não foi possível identificar a clínica ativa."
            )

        cliente = attrs.get(
            "cliente",
            getattr(self.instance, "cliente", None),
        )
        profissional = attrs.get(
            "profissional",
            getattr(self.instance, "profissional", None),
        )
        servico = attrs.get(
            "servico",
            getattr(self.instance, "servico", None),
        )
        pacote = attrs.get(
            "pacote_origem",
            getattr(self.instance, "pacote_origem", None),
        )

        if cliente is not None and cliente.clinica_id != clinica.pk:
            raise serializers.ValidationError({
                "cliente": "O cliente não pertence à clínica ativa."
            })

        if profissional is not None:
            if profissional.clinica_id != clinica.pk:
                raise serializers.ValidationError({
                    "profissional": "O profissional não pertence à clínica ativa."
                })

            if not profissional.ativo:
                raise serializers.ValidationError({
                    "profissional": "Não é possível agendar com um profissional inativo."
                })

            if profissional.role.nome != Role.PROFISSIONAL:
                raise serializers.ValidationError({
                    "profissional": "O colaborador selecionado não é um profissional."
                })

        if servico is not None:
            if servico.clinica_id != clinica.pk:
                raise serializers.ValidationError({
                    "servico": "O serviço não pertence à clínica ativa."
                })

            if not servico.ativo:
                raise serializers.ValidationError({
                    "servico": "Não é possível agendar um serviço inativo."
                })

        if pacote is not None:
            if pacote.clinica_id != clinica.pk:
                raise serializers.ValidationError({
                    "pacote_origem": "O pacote não pertence à clínica ativa."
                })

            if cliente is not None and pacote.cliente_id != cliente.pk:
                raise serializers.ValidationError({
                    "pacote_origem": "O pacote não pertence ao cliente selecionado."
                })

            if servico is not None and pacote.servico_id != servico.pk:
                raise serializers.ValidationError({
                    "pacote_origem": "O pacote não corresponde ao serviço selecionado."
                })

        return attrs


class PacoteSerializer(serializers.ModelSerializer):
    saldo_sessoes = serializers.SerializerMethodField()

    class Meta:
        model = Pacote
        fields = [
            "id",
            "clinica",
            "cliente",
            "servico",
            "quantidade_sessoes",
            "valor_total",
            "data_vencimento",
            "status",
            "observacoes",
            "saldo_sessoes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "clinica",
            "status",
            "saldo_sessoes",
            "created_at",
            "updated_at",
        ]

    def get_saldo_sessoes(self, obj):
        return obj.saldo_sessoes

    def validate_quantidade_sessoes(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "O pacote precisa ter pelo menos uma sessão."
            )
        return value

    def validate_valor_total(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "O valor total do pacote não pode ser negativo."
            )
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        clinica = getattr(request, "clinica", None)

        if clinica is None:
            raise serializers.ValidationError(
                "Não foi possível identificar a clínica ativa."
            )

        cliente = attrs.get(
            "cliente",
            getattr(self.instance, "cliente", None),
        )
        servico = attrs.get(
            "servico",
            getattr(self.instance, "servico", None),
        )

        if cliente is None:
            raise serializers.ValidationError({
                "cliente": "Informe um cliente válido."
            })

        if cliente.clinica_id != clinica.pk:
            raise serializers.ValidationError({
                "cliente": "O cliente não pertence à clínica ativa."
            })

        if cliente.status_cadastro != Cliente.ATIVO:
            raise serializers.ValidationError({
                "cliente": "Não é possível criar um pacote para cliente inativo."
            })

        if servico is None:
            raise serializers.ValidationError({
                "servico": "Informe um serviço válido."
            })

        if servico.clinica_id != clinica.pk:
            raise serializers.ValidationError({
                "servico": "O serviço não pertence à clínica ativa."
            })

        if not servico.ativo:
            raise serializers.ValidationError({
                "servico": "Não é possível contratar um serviço inativo."
            })

        return attrs


class SessaoPacoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessaoPacote
        fields = "__all__"
        read_only_fields = fields
