from django.urls import path

from core.views.auth_views import LoginView

urlpatterns = [
    path(
        'auth/login/',
        LoginView.as_view(),
        name='login'
    ),
]