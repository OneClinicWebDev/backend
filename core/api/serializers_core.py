from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.models import (
    Usuario,
    Clinica,
    Role,
    Colaborador,
    Cliente,
    Especialidade,
    Servico,
    ModeloPacote,
    Agendamento,
    Pacote,
    SessaoPacote,
)

from core.validators import (
    validar_cnpj,
    validar_telefone,
    validar_cep,
)


MAX_INTEGER = 2147483647


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


class ClinicaAtualizacaoSerializer(serializers.ModelSerializer):
    cnpj = serializers.CharField(max_length=18, trim_whitespace=True)
    telefone = serializers.CharField(max_length=20, trim_whitespace=True)

    class Meta:
        model = Clinica
        fields = [
            "id",
            "cnpj",
            "razao_social",
            "nome_fantasia",
            "telefone",
            "endereco",
            "profissionais_podem_editar_agenda",
        ]
        read_only_fields = ["id", "profissionais_podem_editar_agenda"]

    def validate_cnpj(self, value):
        try:
            cnpj = validar_cnpj(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

        existentes = Clinica.objects.filter(cnpj=cnpj)

        if self.instance is not None:
            existentes = existentes.exclude(pk=self.instance.pk)

        if existentes.exists():
            raise serializers.ValidationError(
                "Já existe uma clínica cadastrada com este CNPJ."
            )

        return cnpj

    def validate_telefone(self, value):
        try:
            return validar_telefone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_razao_social(self, value):
        value = value.strip()

        if len(value) < 3:
            raise serializers.ValidationError(
                "Informe uma razão social com pelo menos 3 caracteres."
            )

        return value

    def validate_nome_fantasia(self, value):
        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError(
                "Informe um nome fantasia válido."
            )

        return value

    def validate_endereco(self, value):
        return value.strip()


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
    cpf = serializers.CharField(write_only=True, required=False, max_length=14)
    nome_completo = serializers.CharField(write_only=True, required=False, max_length=255)
    especialidades = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        allow_empty=True,
        allow_null=True,
        write_only=True 
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
            "cpf",
            "nome_completo",
            "especialidades",
        ]
        read_only_fields = [
            "id",
            "usuario",
            "usuario_nome",
            "clinica",
            "role_nome",
        ]

    def _processar_especialidades(self, colaborador, nomes_especialidades):
        role_obj = colaborador.role
        is_profissional = role_obj and str(role_obj.nome).strip().upper() == "PROFISSIONAL"

        if not is_profissional:
            colaborador.especialidades.clear()
        elif nomes_especialidades is not None:
            clinica = colaborador.clinica
            objs = []
            for nome in nomes_especialidades:
                nome_formatado = str(nome).strip().title()
                if nome_formatado:
                    esp, _ = Especialidade.objects.get_or_create(
                        clinica=clinica, 
                        nome=nome_formatado
                    )
                    objs.append(esp)
            colaborador.especialidades.set(objs)
        Especialidade.objects.filter(
            clinica=colaborador.clinica, 
            profissionais__isnull=True
        ).delete()

    def create(self, validated_data):
        especialidades = validated_data.pop("especialidades", [])
        colaborador = super().create(validated_data)
        self._processar_especialidades(colaborador, especialidades)
        return colaborador

    def update(self, instance, validated_data):
        especialidades = validated_data.pop("especialidades", None)
        colaborador = super().update(instance, validated_data)
        if especialidades is not None:
            self._processar_especialidades(colaborador, especialidades)
        return colaborador

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["especialidades"] = [esp.nome for esp in instance.especialidades.all()]
        return representation
class ClienteSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(
        source="usuario.nome_completo",
        read_only=True,
    )
    usuario_cpf = serializers.SerializerMethodField()
    cpf = serializers.CharField(write_only=True, required=False, max_length=14)
    nome_completo = serializers.CharField(write_only=True, required=False, max_length=255)

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
            "cpf",
            "nome_completo"
        ]
        read_only_fields = [
            "id",
            "usuario",
            "usuario_nome",
            "usuario_cpf",
            "clinica",
        ]

    def get_usuario_cpf(self, obj):
        cpf = getattr(obj.usuario, 'cpf', None)
        if cpf and len(cpf) == 11:
            return f"***.{cpf[3:6]}.{cpf[6:9]}-**"
        return cpf

    def validate_telefone(self, value):
        try:
            return validar_telefone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_cep(self, value):
        if not value or not value.strip():
            return ""

        try:
            return validar_cep(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_numero_endereco(self, value):
        return value.strip()

class ServicoSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(
        max_length=255,
        trim_whitespace=True,
    )
    duracao_padrao_minutos = serializers.IntegerField(
        min_value=1,
        max_value=MAX_INTEGER,
    )
    preco = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
    )

    class Meta:
        model = Servico
        fields = "__all__"
        read_only_fields = [
            "id",
            "clinica",
            "created_at",
            "updated_at",
        ]

    def validate_nome(self, value):
        if not value:
            raise serializers.ValidationError(
                "O nome do serviço é obrigatório."
            )
        return value

    def validate_duracao_padrao_minutos(self, value):
        if not 1 <= value <= MAX_INTEGER:
            raise serializers.ValidationError(
                "A duração deve ser um número inteiro positivo válido."
            )
        return value

    def validate_categoria(self, value):
        return value.strip()

    def validate_descricao(self, value):
        return value.strip()

class ModeloPacoteSerializer(serializers.ModelSerializer):
    servico_nome = serializers.CharField(
        source="servico.nome",
        read_only=True,
    )

    class Meta:
        model = ModeloPacote
        fields = [
            "id",
            "clinica",
            "nome",
            "servico",
            "servico_nome",
            "quantidade_sessoes",
            "valor_total",
            "categoria",
            "descricao",
            "ativo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "clinica",
            "created_at",
            "updated_at",
        ]

    def validate_nome(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                "O nome do pacote é obrigatório."
            )
        return value

    def validate_quantidade_sessoes(self, value):
        if not 1 <= value <= MAX_INTEGER:
            raise serializers.ValidationError(
                "A quantidade de sessões deve ser um inteiro positivo válido."
            )
        return value

    def validate_valor_total(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "O valor total do pacote não pode ser negativo."
            )
        return value

    def validate_categoria(self, value):
        return value.strip()

    def validate_descricao(self, value):
        return value.strip()

    def validate(self, attrs):
        request = self.context.get("request")
        clinica = getattr(request, "clinica", None) if request else None

        if clinica is None:
            raise serializers.ValidationError(
                "Não foi possível identificar a clínica ativa."
            )

        servico = attrs.get(
            "servico",
            getattr(self.instance, "servico", None),
        )

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
                "servico": "Não é possível usar um serviço inativo."
            })

        return attrs
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
    cliente_telefone = serializers.CharField(
        source="cliente.telefone",
        read_only=True,
    )
    servico_preco = serializers.DecimalField(
        source="servico.preco",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    servico_duracao_minutos = serializers.IntegerField(
        source="servico.duracao_padrao_minutos",
        read_only=True,
    )
    preco_acordado = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        allow_null=True,
    )
    pacote_nome = serializers.SerializerMethodField()
    sessao_pacote_status = serializers.SerializerMethodField()

    def get_pacote_nome(self, obj):
        pacote = obj.pacote_origem

        if pacote is None:
            return None

        if pacote.modelo_id:
            return pacote.modelo.nome

        return obj.servico.nome

    def get_sessao_pacote_status(self, obj):
        if obj.pacote_origem_id is None:
            return None

        sessao = getattr(obj, "sessao_pacote", None)

        if sessao is None:
            return None

        return sessao.status

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
                    "profissional": (
                        "O profissional não pertence à clínica ativa."
                    )
                })

            if not profissional.ativo:
                raise serializers.ValidationError({
                    "profissional": (
                        "Não é possível agendar com um profissional inativo."
                    )
                })

            if profissional.role.nome not in (Role.PROFISSIONAL, Role.ADMIN):
                 raise serializers.ValidationError({
                "profissional": (
                "O colaborador selecionado não pode realizar atendimentos."
             )
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
                    "pacote_origem": (
                        "O pacote não pertence à clínica ativa."
                    )
                })

            if cliente is not None and pacote.cliente_id != cliente.pk:
                raise serializers.ValidationError({
                    "pacote_origem": (
                        "O pacote não pertence ao cliente selecionado."
                    )
                })

            if pacote.status != Pacote.ATIVO:
                raise serializers.ValidationError({
                "pacote_origem": "O pacote não está ativo."
                })

            if servico is not None and pacote.servico_id != servico.pk:
                raise serializers.ValidationError({
                    "pacote_origem": (
                        "O pacote não corresponde ao serviço selecionado."
                    )
                })

        return attrs


class PacoteSerializer(serializers.ModelSerializer):
    quantidade_sessoes = serializers.IntegerField(
        min_value=1,
        max_value=MAX_INTEGER,
    )
    valor_total = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
    )
    saldo_sessoes = serializers.SerializerMethodField()
    sessoes_disponiveis = serializers.SerializerMethodField()
    modelo_nome = serializers.CharField(
        source="modelo.nome",
        read_only=True,
    )
    cliente_nome = serializers.CharField(
        source="cliente.usuario.nome_completo",
        read_only=True,
    )
    servico_nome = serializers.CharField(
        source="servico.nome",
        read_only=True,
    )

    class Meta:
        model = Pacote
        fields = [
            "id",
            "clinica",
            "modelo",
            "modelo_nome",
            "cliente",
            "cliente_nome",
            "servico",
            "servico_nome",
            "quantidade_sessoes",
            "valor_total",
            "status",
            "observacoes",
            "saldo_sessoes",
            "sessoes_disponiveis",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "clinica",
            "status",
            "saldo_sessoes",
            "sessoes_disponiveis",
            "created_at",
            "updated_at",
        ]

    def get_saldo_sessoes(self, obj):
        return obj.saldo_sessoes

    def get_sessoes_disponiveis(self, obj):
        return sum(
            1
            for sessao in obj.sessoes.all()
            if sessao.status == SessaoPacote.DISPONIVEL
        )

    def validate_quantidade_sessoes(self, value):
        if not 1 <= value <= MAX_INTEGER:
            raise serializers.ValidationError(
                "A quantidade de sessões deve ser um inteiro positivo válido."
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
        clinica = getattr(request, "clinica", None) if request else None

        if clinica is None:
            raise serializers.ValidationError(
                "Não foi possível identificar a clínica ativa."
            )

        cliente = attrs.get(
            "cliente",
            getattr(self.instance, "cliente", None),
        )
        modelo = attrs.get(
            "modelo",
            getattr(self.instance, "modelo", None),
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

        if self.instance is None and modelo is None:
            raise serializers.ValidationError({
                "modelo": "Selecione um modelo do catálogo para criar a aquisição."
            })

        if modelo is not None:
            if modelo.clinica_id != clinica.pk:
                raise serializers.ValidationError({
                    "modelo": "O modelo não pertence à clínica ativa."
                })

            if not modelo.ativo:
                raise serializers.ValidationError({
                    "modelo": "Não é possível vender um modelo de pacote inativo."
                })

            if self.instance is not None and modelo.pk != self.instance.modelo_id:
                raise serializers.ValidationError({
                    "modelo": "O modelo de uma aquisição existente não pode ser alterado."
                })

        return attrs

class SessaoPacoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessaoPacote
        fields = "__all__"
        read_only_fields = fields