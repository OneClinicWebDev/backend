from django.contrib import admin
from django.urls import path, include

def home_view(request):
    return HttpResponse("<h1>OneClinic API está rodando!</h1><p>Acesse <a href='/admin/'>/admin/</a> para o painel ou <a href='/api/login/'>/api/login/</a> para a API.</p>")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.api.urls")),
]