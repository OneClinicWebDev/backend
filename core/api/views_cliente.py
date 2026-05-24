from rest_framework import viewsets
from core.models import Cliente
from .base import ClinicaMixin
from .serializers_core import ClienteSerializer


class ClienteViewSet(ClinicaMixin, viewsets.ModelViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer