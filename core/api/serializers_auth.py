from rest_framework import serializers
from django.contrib.auth import authenticate


class LoginSerializer(serializers.Serializer):
    cpf = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(username=data["cpf"], password=data["password"])

        if not user:
            raise serializers.ValidationError("Credenciais inválidas")

        data["user"] = user
        return data