from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

def home_view(request):
    return HttpResponse("""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <title>OneClinic API</title>

        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: Arial, sans-serif;
                background: #F6F8F9;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }

            .card {
                background: white;
                padding: 40px;
                width: 420px;
                border-radius: 20px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0,0,0,.08);
                border: 1px solid #DCE5E7;
            }

            h1 {
                color: #062B4A;
                margin-bottom: 15px;
                font-size: 32px;
            }

            .clinic {
                color: #25A7AE;
            }

            p {
                color: #5B6B7B;
                margin-bottom: 30px;
                line-height: 1.6;
            }

            .button {
                display: block;
                text-decoration: none;
                background: #25A7AE;
                color: white;
                padding: 14px;
                border-radius: 12px;
                margin-bottom: 15px;
                font-weight: bold;
                transition: .2s;
            }

            .button:hover {
                background: #1E8F95;
            }

            .button.secondary {
                background: transparent;
                color: #062B4A;
                border: 2px solid #062B4A;
            }

            .button.secondary:hover {
                background: #062B4A;
                color: white;
            }

            .status {
                margin-top: 20px;
                color: #25A7AE;
                font-size: 14px;
                font-weight: bold;
            }
        </style>
    </head>

    <body>
        <div class="card">
            <h1>One<span class="clinic">Clinic</span> API</h1>

            <p>
                Servidor online e funcionando corretamente.
            </p>

            <a class="button" href="/admin/">
                Painel Administrativo
            </a>

            <a class="button secondary" href="/api/login/">
                API Login
            </a>

            <div class="status">
                ● ONLINE
            </div>
        </div>
    </body>
    </html>
    """)

urlpatterns = [
    path("", home_view),
    path("admin/", admin.site.urls),
    path("api/", include("core.api.urls")),
]