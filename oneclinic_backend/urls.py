from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

def home_view(request):
    return HttpResponse(
        """
        <h1>OneClinic Backend</h1>
        <p>API disponível em /api/</p>
        <p>Admin disponível em /admin/</p>
        """
    )

urlpatterns = [
    path("", home_view),
    path("admin/", admin.site.urls),
    path("api/", include("core.api.urls")),
]