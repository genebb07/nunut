from django.urls import path
from . import views

app_name = 'base'

urlpatterns = [
    path('', views.bienvenida, name='bienvenida'),
    path('dashboard/', views.index, name='index'),
    path('panel/', views.panel, name='panel'),
    path('planes/', views.planes, name='planes'),
    path('diario/', views.diario, name='diario'),
    path('progreso/', views.progreso, name='progreso'),
    path('biblioteca/', views.biblio, name='biblio'),
    path('iniciar_sesion/', views.iniciar_sesion, name='iniciar_sesion'),
    path('registro/', views.registro, name='registro'),
    path('recuperar_contrasena/', views.recuperar_contrasena, name='recuperar_contrasena'),
    path('guardar_paso/<int:paso_id>/', views.guardar_paso, name='guardar_paso'),
    path('api/perfil/', views.perfil_api, name='perfil_api'),
    path('api/calcular_macros/', views.calcular_macros_api, name='calcular_macros'),
    path('api/perfiles/', views.perfiles_api, name='perfiles_api'),
    path('invitado/', views.invitado, name='invitado'),
    path('perfil/', views.perfil, name='perfil'),
    path('toggle_dark_mode/', views.toggle_dark_mode, name='toggle_dark_mode'),
    path('api/toggle_favorito/<int:receta_id>/', views.toggle_favorito, name='toggle_favorito'),
    path('api/toggle_guardado/<int:articulo_id>/', views.toggle_guardado, name='toggle_guardado'),
    path('api/crear_receta/', views.crear_receta, name='crear_receta'),
    path('cerrar_sesion/', views.cerrar_sesion, name='cerrar_sesion'),
    path('gestion-nunut/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('gestion-nunut/registro/', views.admin_registro, name='admin_registro'),
]
