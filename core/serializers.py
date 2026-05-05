from rest_framework import serializers
from .models import Cliente


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = '__all__'

    def validate_cpf(self, value):
        if len(value) != 11:
            raise serializers.ValidationError("CPF inválido")
        return value

    def create(self, validated_data):
        request = self.context['request']
        validated_data['clinica'] = request.user.colaborador.clinica
        return super().create(validated_data)