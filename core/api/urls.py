from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views_auth import LoginView, LogoutView, MeView
from .views_cadastro import CadastroClinicaView
from .views_cliente import ClienteViewSet
from .views_colaborador import ColaboradorViewSet
from .views_servico import ServicoViewSet
from .views_agendamento import AgendamentoViewSet
from .views_pacote import PacoteViewSet
from .views_clinica import ClinicaViewSet
from .views_modelo_pacote import ModeloPacoteViewSet

router = DefaultRouter()
router.register(r"clinica", ClinicaViewSet, basename="clinica")
router.register(r"clientes", ClienteViewSet, basename="cliente")
router.register(r"colaboradores", ColaboradorViewSet, basename="colaborador")
router.register(r"servicos", ServicoViewSet, basename="servico")
router.register(r"modelos-pacote", ModeloPacoteViewSet, basename="modelo-pacote")
router.register(r"agendamentos", AgendamentoViewSet, basename="agendamento")
router.register(r"pacotes", PacoteViewSet, basename="pacote")

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='login'),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path('auth/criar-clinica/', CadastroClinicaView.as_view(), name='criar_clinica'),
    path('', include(router.urls)),
]