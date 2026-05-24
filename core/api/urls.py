from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_auth import LoginView
from .views_cliente import ClienteViewSet
from .views_colaborador import ColaboradorViewSet

router = DefaultRouter()
router.register(r"clientes", ClienteViewSet)
router.register(r"colaboradores", ColaboradorViewSet)

urlpatterns = [
    path("login/", LoginView.as_view()),
    path("", include(router.urls)),
]