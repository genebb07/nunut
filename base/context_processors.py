from datetime import date

def racha_context(request):
    """Context processor para agregar la racha de días a todas las templates"""
    racha_dias = 0
    mensaje_racha = "¡Comienza hoy!"
    
    if request.user.is_authenticated and hasattr(request.user, 'perfil'):
        from .models import LoginStreak
        perfil = request.user.perfil
        
        # Registrar el acceso de hoy si no es invitado
        if perfil.rol != 'GUEST':
            LoginStreak.objects.get_or_create(perfil=perfil, fecha=date.today())
            racha_dias = LoginStreak.calcular_racha(perfil)
            
            # Importar la función de mensajes
            from .views import obtener_mensaje_racha
            mensaje_racha = obtener_mensaje_racha(racha_dias)
    
    return {
        'racha_dias': racha_dias,
        'mensaje_racha': mensaje_racha
    }
