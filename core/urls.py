from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClienteViewSet, ColaboradorViewSet, ServicoViewSet, AgendamentoViewSet

router = DefaultRouter()
router.register(r'clientes', ClienteViewSet, basename='cliente')
router.register(r'colaboradores', ColaboradorViewSet, basename='colaborador')
router.register(r'servicos', ServicoViewSet, basename='servico')
router.register(r'agendamentos', AgendamentoViewSet, basename='agendamento')

urlpatterns = [
    path('', include(router.urls)),
]