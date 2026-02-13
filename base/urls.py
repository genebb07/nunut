from django.urls import path
from . import views
from . import gemini_views

app_name = 'base'

urlpatterns = [
    # --- Vistas Públicas y Autenticación ---
    path('', views.bienvenida, name='bienvenida'),
    path('iniciar_sesion/', views.iniciar_sesion, name='iniciar_sesion'),
    path('registro/', views.registro, name='registro'),
    path('recuperar_contrasena/', views.recuperar_contrasena, name='recuperar_contrasena'),
    path('invitado/', views.invitado, name='invitado'),
    path('cerrar_sesion/', views.cerrar_sesion, name='cerrar_sesion'),

    # --- Dashboard y Vistas Principales ---
    path('dashboard/', views.index, name='index'),
    path('planes/', views.planes, name='planes'),
    path('analizador/', views.analizador, name='analizador'),
    path('progreso/', views.progreso, name='progreso'),
    path('biblioteca/', views.biblio, name='biblio'),
    path('perfil/', views.perfil, name='perfil'),
    path('gestionar_cuenta/', views.gestionar_cuenta, name='gestionar_cuenta'),

    # --- APIs de Perfil y Configuración ---
    path('toggle_dark_mode/', views.toggle_dark_mode, name='toggle_dark_mode'),
    path('cambiar_username/', views.cambiar_username, name='cambiar_username'),
    path('cambiar_email/', views.cambiar_email, name='cambiar_email'),
    path('cambiar_contrasena/', views.cambiar_contrasena, name='cambiar_contrasena'),
    path('guardar_paso/<int:paso_id>/', views.guardar_paso, name='guardar_paso'),
    path('api/perfil/', views.perfil_api, name='perfil_api'),

    # --- APIs de Nutrición y Recetas ---
    path('api/calcular_macros/', views.calcular_macros_api, name='calcular_macros'),
    path('api/crear_receta/', views.crear_receta, name='crear_receta'),
    path('editar_receta/<int:receta_id>/', views.editar_receta, name='editar_receta'),
    path('api/borrar_receta/<int:receta_id>/', views.borrar_receta, name='borrar_receta'),
    path('api/calificar_receta/<int:receta_id>/', views.calificar_receta, name='calificar_receta'),
    path('api/toggle_favorito/<int:receta_id>/', views.toggle_favorito, name='toggle_favorito'),
    path('api/toggle_guardado/<int:articulo_id>/', views.toggle_guardado, name='toggle_guardado'),
    path('api/buscar_alimentos/', views.buscar_alimentos_api, name='buscar_alimentos'),
    path('api/calcular_nutricion/', views.calcular_nutricion_api, name='calcular_nutricion'),

    # --- APIs de Registro Diario ---
    path('api/actualizar_agua/', views.actualizar_agua, name='actualizar_agua'),
    path('api/comidas_hoy/', views.comidas_hoy_api, name='comidas_hoy_api'),
    path('api/guardar_comida/', views.guardar_comida_api, name='guardar_comida_api'),
    path('api/guardar_sueno/', views.guardar_sueno_api, name='guardar_sueno_api'),
    path('api/guardar_peso/', views.guardar_peso_api, name='guardar_peso_api'),
    path('api/borrar_peso/<int:peso_id>/', views.borrar_peso, name='borrar_peso'),
    path('api/agregar_al_calendario/', views.agregar_al_calendario, name='agregar_al_calendario'),
    path('api/quitar_del_calendario/<int:comida_id>/', views.quitar_del_calendario, name='quitar_del_calendario'),
    path('api/obtener_calorias_dias/', views.obtener_calorias_dias, name='obtener_calorias_dias'),
    path('api/generar_informe_pdf/', views.generar_informe_pdf, name='generar_informe_pdf'),

    # --- Funcionalidades IA (Gemini) ---
    path('api/generar_receta_ia/', gemini_views.generar_receta_ia, name='generar_receta_ia'),
    path('api/generar_plan_ia/', gemini_views.generar_plan_ia, name='generar_plan_ia'),
    path('api/analizar_comida_ia/', gemini_views.analizar_comida_ia, name='analizar_comida_ia'),
    path('api/transcribir_audio/', gemini_views.transcribir_audio, name='transcribir_audio'),

    # --- Panel de Administración y Gestión ---
    path('gestion-nunut/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('gestion-nunut/registro/', views.admin_registro, name='admin_registro'),
    path('panel/', views.panel, name='panel'),
    path('api/perfiles/', views.perfiles_api, name='perfiles_api'),
    path('api/enviar_sugerencia/', views.enviar_sugerencia, name='enviar_sugerencia'),
    path('api/responder_sugerencia/<int:sugerencia_id>/', views.responder_sugerencia, name='responder_sugerencia'),
    path('api/marcar_leido_sugerencia/<int:sugerencia_id>/', views.marcar_leido_sugerencia, name='marcar_leido_sugerencia'),
    path('api/archivar_sugerencia/<int:sugerencia_id>/', views.archivar_sugerencia, name='archivar_sugerencia'),
    path('api/curar_receta/<int:receta_id>/', views.curar_receta, name='curar_receta'),
]
