"""
Configuración de URLs para el proyecto core.

La lista `urlpatterns` enruta las URLs a las vistas. Para más información, ver:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Ejemplos:
Vistas de funciones
    1. Añadir una importación:  from my_app import views
    2. Añadir una URL a urlpatterns:  path('', views.home, name='home')
Vistas basadas en clases
    1. Añadir una importación:  from other_app.views import Home
    2. Añadir una URL a urlpatterns:  path('', Home.as_view(), name='home')
Incluir otro URLconf
    1. Importar la función include(): from django.urls import include, path
    2. Añadir una URL a urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('base.urls')),
    path('accounts/', include('allauth.urls')),
]
