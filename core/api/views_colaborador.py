from rest_framework import viewsets
from core.models import Colaborador
from .base import ClinicaMixin
from .serializers_core import ColaboradorSerializer


class ColaboradorViewSet(ClinicaMixin, viewsets.ModelViewSet):
    queryset = Colaborador.objects.all()
    serializer_class = ColaboradorSerializer