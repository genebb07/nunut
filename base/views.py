from django.shortcuts import render, redirect
import requests
from django.core.cache import cache
import random
from datetime import date, datetime, timedelta
from deep_translator import GoogleTranslator
from django.urls import reverse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q, Avg
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .forms import CustomAuthenticationForm, CustomUserCreationForm
from .forms import OnboardingForm
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password
from datetime import date, timedelta, datetime

def get_base_template(request):
    return 'partial.html' if request.headers.get('HX-Request') else 'base.html'

def obtener_mensaje_racha(dias, perfil=None):
    """Retorna un mensaje motivador basado en los días de racha, género, edad y si es recurrente"""
    
    # Valores por defecto
    genero = perfil.genero if perfil else 'O'
    edad = perfil.edad if perfil else 30
    nombre = perfil.usuario.first_name if (perfil and perfil.usuario.first_name) else "Usuario"

    # Términos adaptados
    if genero == 'M':
        terminos = {'campeon': 'Campeona', 'duro': 'dura', 'maestro': 'Maestra', 'rey': 'Reina'}
    else:
        terminos = {'campeon': 'Campeón', 'duro': 'duro', 'maestro': 'Maestro', 'rey': 'Rey'}

    # Detección de Usuario Recurrente (Volvió tras perder racha)
    es_regreso = False
    if perfil and dias <= 1:
        from .models import LoginStreak
        total_logins = LoginStreak.objects.filter(perfil=perfil).count()
        if total_logins > 5: # Si ha entrado muchas veces antes pero su racha es 1
            es_regreso = True

    # Mensajes por Nivel de Formalidad (Edad)
    if edad < 25:
        # Tono: Joven, energético, emojis, "tu"
        if dias == 0:
            return f"¡Vamos {nombre}! Hoy empieza todo. 🔥"
        if dias == 1:
            return "¡Qué bueno verte de nuevo! A recuperar el trono. 👑" if es_regreso else "¡Primer día! Dale con todo. 🚀"
        
        mensajes_cortos = [
            "¡Estás on fire! 🔥",
            "¡Nadie te para! 🚀",
            f"¡Esa es la actitud, {terminos['campeon'].lower()}! ✨",
            "¡Rompiéndola! 💪",
            "¡Sigue así! 💯"
        ]
        
    elif edad > 50:
        # Tono: Maduro, respetuoso, menos emojis, "usted" o muy formal "tu"
        if dias == 0:
            return "Un nuevo comienzo es siempre una oportunidad. Adelante. 🌱"
        if dias == 1:
            return "Bienvenido nuevamente. Su constancia es clave." if es_regreso else "Primer paso completado. Excelente decisión. ✨"
            
        mensajes_cortos = [
            "¡Excelente constancia! ✨",
            "Paso a paso se llega lejos. 🏔️",
            f"Su disciplina es admirable, {terminos['campeon'].lower()}.",
            "Manteniendo el buen ritmo. 👏",
            "La salud es el mejor proyecto. Siga así. 💎"
        ]
        
    else:
        # Tono: Estándar (25-50 años)
        if dias == 0:
            return "¡Hoy es el día! Empieza con fuerza. 💪"
        if dias == 1:
            return "¡Bienvenido de vuelta! A construir esa racha de nuevo. 🔄" if es_regreso else "¡Primer día! El inicio de un gran hábito. 🌱"

        mensajes_cortos = [
            "¡Estás en racha! 🔥",
            "¡No te detengas! 💪",
            "¡Excelente consistencia! ✨",
            "¡Vas por buen camino! 🚀",
            f"¡Sigue así, {terminos['campeon']}! 👑"
        ]

    # Hitos Específicos (Override de mensajes cortos)
    if dias >= 30:
        return f"¡{dias} DÍAS! ¡ERES {terminos['rey'].upper()}! 👑"
    if dias >= 21:
        return f"¡{dias} Días! ¡Hábito de titanio! 💎"
    if dias >= 14:
        return f"¡{dias} Días! ¡Imparable! 🚀"
    if dias >= 7:
        return f"¡Una semana completa! 🎉"
        
    return f"{dias} Días: {random.choice(mensajes_cortos)}"

def obtener_recomendacion_ia(perfil, racha_dias):
    """Genera un mensaje cálido, dinámico y contextual del Coach IA nunut"""
    if not perfil or perfil.rol == 'GUEST':
        return "¡Hola! Soy nunut, tu coach personal. Regístrate para que pueda acompañarte en este viaje hacia tu mejor versión. Juntos haremos de tu salud una prioridad. ✨"
    
    nombre = perfil.usuario.first_name or perfil.usuario.username
    
    # 0. Caching (Clave única por usuario + hora para no saturar API pero actualizarse)
    curr_hour = datetime.now().hour
    cache_key = f"ia_msg_v2_{perfil.id}_{date.today()}_{curr_hour}"
    cached_msg = cache.get(cache_key)
    if cached_msg:
        return cached_msg

    # 1. Obtener Datos de Contexto
    from .models import RegistroAgua, RegistroSueno, ComidaDiaria, LoginStreak
    
    # Hidratación
    agua_hoy, _ = RegistroAgua.objects.get_or_create(perfil=perfil, fecha=date.today())
    
    # Sueño (Último registro)
    sueno_ayer = RegistroSueno.objects.filter(perfil=perfil).order_by('-fecha').first()
    
    # Nutrición (Progreso de hoy)
    comidas_hoy = ComidaDiaria.objects.filter(perfil=perfil, fecha=date.today())
    cal_consumidas = sum(c.calorias for c in comidas_hoy)
    # Evitar llamar "generar_informe" si es pesado, pero lo necesitamos para la meta
    meta_cal = 2000
    try:
        informe = perfil.generar_informe_nutricional()
        meta_cal = informe['plan']['calorias_dia']
    except: pass
    
    nutricion_stats = {
        'cal_pct': min(round((cal_consumidas / meta_cal) * 100), 100) if meta_cal > 0 else 0
    }

    # Estado de Retorno (Usuario antiguo que vuelve)
    es_retorno = False
    if racha_dias <= 1:
        total_logins = LoginStreak.objects.filter(perfil=perfil).count()
        if total_logins > 5: 
            es_retorno = True

    if not perfil.onboarding_completado:
        return f"¡Qué alegría tenerte aquí, {nombre}! 🌱 Soy nunut, tu coach IA. Me encantaría conocerte mejor para sugerirte los mejores alimentos según tu cuerpo. ¿Terminamos tu perfil? ✨"

    # 2. Llamada a Gemini (IA)
    try:
        from .ai_service import generar_recomendacion_premium
        recomendacion_gemini = generar_recomendacion_premium(
            perfil=perfil, 
            racha_dias=racha_dias, 
            agua_hoy=agua_hoy,
            sueno_ayer=sueno_ayer,
            nutricion_hoy=nutricion_stats,
            es_retorno=es_retorno
        )
        
        if recomendacion_gemini:
            # Guardar en cache por 45 minutos
            cache.set(cache_key, recomendacion_gemini, 60 * 45)
            return recomendacion_gemini
            
    except Exception as e:
        print(f"Error cargando Gemini: {e}")

    # Fallback: Lógica Reglas-Base (Cálida y Adaptativa)
    genero = perfil.genero
    edad = perfil.edad
    
    # Ajuste de tono por edad
    formal = edad > 50
    joven = edad < 25
    
    titulo_usuario = nombre
    if genero == 'M':
        titulo_campeon = "campeona" if joven else "guerrera"
    else:
        titulo_campeon = "campeón" if joven else "guerrero"

    # Lógica de Racha
    if racha_dias == 1:
        if perfil.login_streaks.count() > 5: # Volvió
            msg_racha = f"¡Qué gusto verte regresar, {nombre}! 🌱 A veces hay pausas, lo importante es retomar. Estoy aquí para ti."
        else:
            msg_racha = f"Hoy es el comienzo de algo grande, {nombre}. 🌱 Cada paso cuenta, y me hace muy feliz verte dar el primero hoy."
    elif racha_dias >= 7:
        frase = "Tu cuerpo ya está empezando a agradecer este nuevo ritmo." if not formal else "Su organismo está respondiendo positivamente a esta constancia."
        msg_racha = f"Llevas {racha_dias} días imparable. 🔥 {frase}"
    else:
        msg_racha = f"¡{racha_dias} días seguidos! 🔥 Mantener la constancia es la llave que abre todas las puertas de tu bienestar."

    # Lógica basada en objetivo
    objetivo_msg = ""
    if perfil.objetivo == 'PERDER':
        objetivo_msg = "He notado que estás enfocado en sentirte más ligero. Recuerda que no se trata de comer menos, sino de nutrirte mejor. 🥗"
    elif perfil.objetivo == 'GANAR':
        objetivo_msg = "Para esos músculos, la proteína y el descanso son clave hoy. ¡Vamos por esa meta! 💪"
    else:
        objetivo_msg = "Mantener el equilibrio es un arte, y lo estás haciendo genial. ¡Sigue nutriendo tu energía vital! ✨"

    # Lógica de Hidratación
    hidratacion_msg = ""
    if agua_hoy.porcentaje < 40:
        hidratacion_msg = "He notado que has tomado poca agua hoy. Intenta beber un vaso ahora para oxigenar tus células. 💧"
    elif agua_hoy.porcentaje >= 100:
        hidratacion_msg = "¡Excelente nivel de hidratación hoy! Estás cuidando tu metabolismo al máximo. 💧🚀"

    mensajes = [
        f"¡Hola {nombre}! {msg_racha} {objetivo_msg} {hidratacion_msg}",
        f"¿Cómo te sientes hoy, {nombre}? {hidratacion_msg} {msg_racha}",
        f"Tu energía me dice que hoy será un día excelente. ☀️ {objetivo_msg} {hidratacion_msg}",
        f"El agua es combustible vital. {hidratacion_msg} {msg_racha}"
    ]
    
    # Mensaje especial muy joven o muy mayor
    if joven and random.random() > 0.7:
         mensajes.append(f"¡Esa energía está a tope, {titulo_campeon}! ⚡ {msg_racha}")
    if formal and random.random() > 0.7:
         mensajes.append(f"Un placer saludarle, {nombre}. {msg_racha}")

    return random.choice(mensajes)

def _get_admin_dashboard_data(request):
    seed_db()
    from .models import Receta, Articulo, Perfil, LoginStreak, Sugerencia, LogActividad, RecetaFavorita, ArticuloGuardado
    from django.db.models.functions import TruncDay
    from django.utils import timezone
    from django.db.models import Count, Q, Avg
    
    # 1. Contadores de Usuarios
    total_users_all = User.objects.count()
    total_registrados = User.objects.exclude(username='invitado').count()
    
    # Crecimiento detallado
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    
    this_week_start = today_start - timedelta(days=now.weekday())
    last_week_start = this_week_start - timedelta(days=7)
    
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
    
    this_year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    last_year_start = this_year_start.replace(year=now.year - 1)

    def get_count_growth(this_start, prev_start, end_limit=None):
        if end_limit is None: end_limit = now
        current = User.objects.exclude(username='invitado').filter(date_joined__gte=this_start).count()
        previous = User.objects.exclude(username='invitado').filter(date_joined__gte=prev_start, date_joined__lt=this_start).count()
        growth = ((current - previous) / max(previous, 1)) * 100
        return round(growth, 1)

    crecimiento_data = {
        'dia': get_count_growth(today_start, yesterday_start),
        'semana': get_count_growth(this_week_start, last_week_start),
        'mes': get_count_growth(this_month_start, last_month_start),
        'ano': get_count_growth(this_year_start, last_year_start),
    }

    # Usuarios Activos (7d/30d)
    seven_days_ago = date.today() - timedelta(days=7)
    thirty_days_ago = date.today() - timedelta(days=30)
    active_7d = LoginStreak.objects.filter(fecha__gte=seven_days_ago).values('perfil').distinct().count()
    active_30d = LoginStreak.objects.filter(fecha__gte=thirty_days_ago).values('perfil').distinct().count()
    
    total_staff = User.objects.filter(Q(is_staff=True) | Q(perfil__rol='ADMIN')).distinct().count()
    
    # 2. Distribución y Mapas - Agrupar Venezuela
    from django.db.models import Case, When, Value, CharField
    perfiles_qs = Perfil.objects.exclude(usuario__username='invitado')
    
    # Lista de estados/ciudades de Venezuela para normalización
    vzla_keywords = ['venezuela', 'caracas', 'zulia', 'maracaibo', 'valencia', 'aragua', 'lara', 'bolivar', 'anzoategui', 'tachira', 'miranda']
    
    dist_paises_raw = list(perfiles_qs.values('localidad').annotate(count=Count('id')).order_by('-count'))
    dist_paises_map = {}
    
    for item in dist_paises_raw:
        loc = (item['localidad'] or "").lower()
        is_vzla = any(k in loc for k in vzla_keywords) or not loc
        country = "Venezuela" if is_vzla else item['localidad']
        dist_paises_map[country] = dist_paises_map.get(country, 0) + item['count']
    
    dist_paises = sorted([{'localidad': k, 'count': v} for k, v in dist_paises_map.items()], key=lambda x: x['count'], reverse=True)
    
    dist_genero = list(perfiles_qs.values('genero').annotate(count=Count('id')))
    
    perfiles = Perfil.objects.exclude(usuario__username='invitado').filter(fecha_nacimiento__isnull=False)
    edades = [p.edad for p in perfiles]
    dist_edad = {
        'e18_25': len([e for e in edades if 18 <= e <= 25]),
        'e26_35': len([e for e in edades if 26 <= e <= 35]),
        'e36_50': len([e for e in edades if 36 <= e <= 50]),
        'e50plus': len([e for e in edades if e > 50]),
    }
    
    # 3. Gráficos de Evolución Dinámicos
    periodo_evo = request.GET.get('evo_period', 'mes')
    from django.db.models.functions import TruncDay, TruncMonth
    
    if periodo_evo == 'semana':
        start_evo = now - timedelta(days=7)
        trunc_evo = TruncDay
        label_fmt = '%d %b'
    elif periodo_evo == 'ano':
        start_evo = now - timedelta(days=365)
        trunc_evo = TruncMonth
        label_fmt = '%b %Y'
    else: # mes
        start_evo = now - timedelta(days=30)
        trunc_evo = TruncDay
        label_fmt = '%d %b'

    registros_evolucion = User.objects.exclude(username='invitado')\
        .filter(date_joined__gte=start_evo)\
        .annotate(period=trunc_evo('date_joined'))\
        .values('period')\
        .annotate(count=Count('id'))\
        .order_by('period')
        
    evolucion_data = {
        'labels': [r['period'].strftime(label_fmt) for r in registros_evolucion],
        'values': [r['count'] for r in registros_evolucion],
        'current_period': periodo_evo
    }
    
    dist_objetivos = list(Perfil.objects.exclude(usuario__username='invitado').values('objetivo').annotate(count=Count('id')))
    
    # 4. Gestión de Sugerencias con Filtros
    status_filter = request.GET.get('sug_estado')
    rating_filter = request.GET.get('sug_rating')
    
    sugerencias_all = Sugerencia.objects.all()
    if status_filter:
        sugerencias_all = sugerencias_all.filter(estado=status_filter)
    else:
        # Por defecto ocultamos los archivados en la vista principal
        sugerencias_all = sugerencias_all.exclude(estado='ARCHIVADO')
        
    if rating_filter:
        sugerencias_all = sugerencias_all.filter(calificacion=rating_filter)
    
    sugerencias_recientes = sugerencias_all.order_by('-fecha')[:15]
    
    recetas_pendientes = Receta.objects.filter(esta_aprobada=False)
    
    avg_edad = round(sum(edades) / len(edades), 1) if edades else 0
    retencion = round((active_30d / max(total_registrados, 1)) * 100, 1)

    recent_users_list = []
    # Privacidad: Solo últimos 5 y ocultar username (usar email)
    for u in User.objects.exclude(username='invitado').order_by('-date_joined')[:5]:
        recent_users_list.append({
            'username': "Usuario " + str(u.id),
            'email': u.email,
            'date_joined': u.date_joined,
            'is_active': u.is_active
        })

    return {
        'stats': {
            'total_users': total_registrados,
            'crecimiento': crecimiento_data,
            'active_7d': active_7d,
            'active_30d': active_30d,
            'total_staff': total_staff,
            'avg_edad': avg_edad,
            'retencion': retencion,
        },
        'charts': {
            'dist_paises': dist_paises,
            'dist_genero': list(dist_genero),
            'dist_edad': dist_edad,
            'evolucion': evolucion_data,
            'dist_objetivos': list(dist_objetivos),
        },
        'sugerencias': sugerencias_recientes,
        'recetas_pendientes': recetas_pendientes,
        'recent_users': recent_users_list,
        'recent_users': recent_users_list,
        'filtros_sug': {
            'estado': status_filter,
            'rating': rating_filter
        }
    }

@login_required
def index(request):
    if request.user.is_staff:
        context = _get_admin_dashboard_data(request)
        context['base_template'] = get_base_template(request)
        context['es_admin_view'] = True
        return render(request, 'base/index.html', context)
    es_invitado = False
    if request.user.is_authenticated and hasattr(request.user, 'perfil'):
        es_invitado = request.user.perfil.rol == 'GUEST'

    perfil = getattr(request.user, 'perfil', None)
    perfil_completo = False
    racha_dias = 0
    
    if perfil:
        perfil_completo = all([
            perfil.fecha_nacimiento, 
            perfil.obtener_peso_actual(), 
            perfil.altura, 
            perfil.genero,
            perfil.nivel_actividad,
            perfil.objetivo
        ])
        
        # Registrar el acceso de hoy si no es invitado
        if not es_invitado:
            from .models import LoginStreak
            LoginStreak.objects.get_or_create(perfil=perfil, fecha=date.today())
            racha_dias = LoginStreak.calcular_racha(perfil)
    
    # Obtener Recetas Sugeridas basadas en el perfil y gustos
    from .models import Receta, RecetaFavorita
    recetas_sugeridas = []
    if perfil and perfil.onboarding_completado:
        # 1. Filtrar por tipo de dieta y objetivo (base)
        diet_filter = perfil.tipo_dieta
        base_recetas = list(Receta.objects.filter(tipo_dieta=diet_filter).order_by('?'))
        
        # 2. Refinar por GUSTOS y tendencias del usuario
        user_gustos = list(perfil.gustos.values_list('nombre', flat=True))
        
        # Scoring logic
        scored_recetas = []
        for r in base_recetas:
            score = 0
            # Tendencia por rating
            score += float(r.rating) * 2
            
            # Match con gustos (palabras clave)
            for gusto in user_gustos:
                if gusto.lower() in r.titulo.lower() or gusto.lower() in r.descripcion.lower():
                    score += 15 # Peso alto para gustos explícitos
            
            scored_recetas.append((r, score))
        
        # Ordenar por score y tomar las top 4
        scored_recetas.sort(key=lambda x: x[1], reverse=True)
        recetas_sugeridas = [x[0] for x in scored_recetas[:4]]
        
        # Si no hay suficientes, rellenar con cualquiera
        if len(recetas_sugeridas) < 4:
            ids_excluidos = [r.id for r in recetas_sugeridas]
            recetas_extra = list(Receta.objects.exclude(id__in=ids_excluidos).order_by('?')[:4-len(recetas_sugeridas)])
            recetas_sugeridas.extend(recetas_extra)
    else:
        # Sugerencias por defecto para invitados o nuevos
        recetas_sugeridas = list(Receta.objects.all().order_by('?')[:4])

    # IDs de favoritos para marcar el corazón
    favoritas_ids = []
    if request.user.is_authenticated and hasattr(request.user, 'perfil'):
        favoritas_ids = list(RecetaFavorita.objects.filter(perfil=request.user.perfil).values_list('receta_id', flat=True))

    # Mostrar mensaje si el perfil está incompleto SOLO si no es invitado
    if not perfil_completo and not es_invitado:
        messages.info(request, "📋 Completa tu perfil para obtener recomendaciones nutricionales personalizadas y seguimiento preciso de tus objetivos.")
    
    # Hidratación
    registro_agua = None
    if perfil and not es_invitado:
        from .models import RegistroAgua
        registro_agua, creado = RegistroAgua.objects.get_or_create(perfil=perfil, fecha=date.today())
        # Actualizar meta según peso actual
        registro_agua.actualizar_meta()
    
    # Logic to generate informe
    informe = None
    if es_invitado:
        informe = {
            'plan': {
                'calorias_dia': 2000,
                'proteinas_g': 150,
                'carbohidratos_g': 200,
                'grasas_g': 65
            },
            'porcentajes': {
                'prot_pct': 30,
                'carbs_pct': 40,
                'grasa_pct': 30
            }
        }
    elif perfil and perfil_completo:
        try:
            informe = perfil.generar_informe_nutricional()
        except Exception:
            informe = None

    
    # Análisis Semanal (Promedios)
    analisis_semanal = {'calorias': 0, 'sueno': 0}
    if perfil and not es_invitado:
        from .models import ComidaDiaria, RegistroSueno
        fecha_inicio_semana = date.today() - timedelta(days=7)
        
        # Calorías promedio
        comidas_semana = ComidaDiaria.objects.filter(perfil=perfil, fecha__gte=fecha_inicio_semana)
        if comidas_semana.exists():
            total_cal = sum(c.calorias for c in comidas_semana)
            dias_unicos = comidas_semana.values('fecha').distinct().count()
            analisis_semanal['calorias'] = int(total_cal / max(dias_unicos, 1))
            
        # Sueño promedio
        sueno_semana = RegistroSueno.objects.filter(perfil=perfil, fecha__gte=fecha_inicio_semana)
        if sueno_semana.exists():
            total_horas = sum(s.horas_totales for s in sueno_semana)
            analisis_semanal['sueno'] = round(total_horas / sueno_semana.count(), 1)
    
    # Datos de sueño de hoy para el input
    sueno_hoy = None
    if perfil and not es_invitado:
        from .models import RegistroSueno
        sueno_hoy = RegistroSueno.objects.filter(perfil=perfil, fecha=date.today()).first()

    return render(request, 'base/index.html', {
        'base_template': get_base_template(request),
        'perfil_completo': perfil_completo,
        'es_invitado': es_invitado,
        'informe': informe,
        'racha_dias': racha_dias,
        'mensaje_racha': obtener_mensaje_racha(racha_dias, perfil),
        'recomendacion_ia': obtener_recomendacion_ia(perfil, racha_dias),
        'recetas_sugeridas': recetas_sugeridas,
        'favoritas_ids': favoritas_ids,
        'registro_agua': registro_agua,
        'analisis_semanal': analisis_semanal,
        'sueno_hoy': sueno_hoy,
    })

def panel(request):
    return render(request, 'base/panel.html', {'base_template': get_base_template(request)})

def seed_db():
    from .models import Receta, Articulo
    if not Receta.objects.exists():
        Receta.objects.create(
            titulo="Salmón al Limón",
            descripcion="Filete de salmón fresco con hierbas y cítricos, ideal para cenas ligeras.",
            imagen_url="https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=500&h=300&fit=crop",
            calorias=350, tiempo="25 min", rating=4.8,
            proteinas=34, carbos=5, grasas=22,
            tipo_dieta="KETO", categoria="explorar"
        )
        Receta.objects.create(
            titulo="Bowl de Quinua",
            descripcion="Un bowl energético lleno de fibra y proteínas vegetales.",
            imagen_url="https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=500&h=300&fit=crop",
            calorias=420, tiempo="15 min", rating=4.9,
            proteinas=12, carbos=65, grasas=14,
            tipo_dieta="VEGE", categoria="explorar"
        )
        Receta.objects.create(
            titulo="Tostada de Aguacate",
            descripcion="Clásico desayuno saludable con pan integral y aguacate cremoso.",
            imagen_url="https://images.unsplash.com/photo-1525351484163-7529414344d8?w=500&h=300&fit=crop",
            calorias=280, tiempo="10 min", rating=4.7,
            proteinas=8, carbos=30, grasas=21,
            tipo_dieta="VEGA", categoria="desayuno"
        )
        Receta.objects.create(
            titulo="Pollo al Curry con Coco",
            descripcion="Pechuga de pollo tierna en una salsa cremosa de coco y especias orientales.",
            imagen_url="https://images.unsplash.com/photo-1603894584373-5ac82b2ae398?w=500&h=300&fit=crop",
            calorias=450, tiempo="30 min", rating=4.6,
            proteinas=35, carbos=12, grasas=28,
            tipo_dieta="OMNI", categoria="almuerzo"
        )
        Receta.objects.create(
            titulo="Ensalada Caesar Fit",
            descripcion="Versión saludable con aderezo de yogur griego y pollo a la plancha.",
            imagen_url="https://images.unsplash.com/photo-1550304943-4f24f54ddde9?w=500&h=300&fit=crop",
            calorias=320, tiempo="15 min", rating=4.5,
            proteinas=28, carbos=10, grasas=18,
            tipo_dieta="OMNI", categoria="cena"
        )

    if not Articulo.objects.exists():
        Articulo.objects.create(
            titulo="Beneficios del Ayuno Intermitente",
            descripcion="Descubre cómo el ayuno puede mejorar tu salud metabólica y longevidad.",
            imagen_url="https://images.unsplash.com/photo-1544367563-12123d895951?w=500&h=300&fit=crop",
            categoria="NUTRICIÓN",
            url="https://example.com/ayuno"
        )
        Articulo.objects.create(
            titulo="5 Mitos sobre la Proteína",
            descripcion="Desmentimos las creencias más comunes sobre el consumo de proteínas.",
            imagen_url="https://images.unsplash.com/photo-1532634922-8fe0c757fb13?w=500&h=300&fit=crop",
            categoria="CIENCIA",
            url="https://example.com/proteina"
        )

    from .models import Alimento
    if not Alimento.objects.exists():
        # Basicos
        Alimento.objects.create(nombre="Pollo", calorias_100g=165, proteinas_100g=31, carbos_100g=0, grasas_100g=3.6, fibra_100g=0, vitamina_a_mg=0, vitamina_c_mg=0, hierro_mg=1, magnesio_mg=23, potasio_mg=256, zinc_mg=1)
        Alimento.objects.create(nombre="Arroz", calorias_100g=130, proteinas_100g=2.7, carbos_100g=28, grasas_100g=0.3, fibra_100g=0.4, vitamina_a_mg=0, vitamina_c_mg=0, hierro_mg=0.2, magnesio_mg=12, potasio_mg=35, zinc_mg=0.5)
        Alimento.objects.create(nombre="Huevo", calorias_100g=155, proteinas_100g=13, carbos_100g=1.1, grasas_100g=11, fibra_100g=0, vitamina_a_mg=0.16, vitamina_c_mg=0, hierro_mg=1.2, magnesio_mg=10, potasio_mg=126, zinc_mg=1)
        Alimento.objects.create(nombre="Aguacate", calorias_100g=160, proteinas_100g=2, carbos_100g=8.5, grasas_100g=14.7, fibra_100g=6.7, vitamina_a_mg=0.01, vitamina_c_mg=10, hierro_mg=0.6, magnesio_mg=29, potasio_mg=485, zinc_mg=0.6)
        Alimento.objects.create(nombre="Pasta", calorias_100g=131, proteinas_100g=5, carbos_100g=25, grasas_100g=1.1, fibra_100g=1.2)
        Alimento.objects.create(nombre="Pan", calorias_100g=265, proteinas_100g=9, carbos_100g=49, grasas_100g=3.2, fibra_100g=2.7)
        Alimento.objects.create(nombre="Pescado", calorias_100g=206, proteinas_100g=22, carbos_100g=0, grasas_100g=12, vitamina_a_mg=0.05, vitamina_c_mg=0, hierro_mg=0.5, magnesio_mg=30, potasio_mg=384, zinc_mg=0.5)
        Alimento.objects.create(nombre="Carne", calorias_100g=250, proteinas_100g=26, carbos_100g=0, grasas_100g=15, hierro_mg=2.6, zinc_mg=4.8)
        Alimento.objects.create(nombre="Leche", calorias_100g=42, proteinas_100g=3.4, carbos_100g=5, grasas_100g=1, vitamina_a_mg=0.03, vitamina_c_mg=0)
        Alimento.objects.create(nombre="Papa", calorias_100g=77, proteinas_100g=2, carbos_100g=17, grasas_100g=0.1, fibra_100g=2.2, vitamina_c_mg=19, potasio_mg=421)
        Alimento.objects.create(nombre="Tomate", calorias_100g=18, proteinas_100g=0.9, carbos_100g=3.9, grasas_100g=0.2, fibra_100g=1.2, vitamina_c_mg=13, vitamina_a_mg=0.04)
        Alimento.objects.create(nombre="Lechuga", calorias_100g=15, proteinas_100g=1.4, carbos_100g=2.9, grasas_100g=0.2, fibra_100g=1.3, vitamina_a_mg=0.37)
        Alimento.objects.create(nombre="Manzana", calorias_100g=52, proteinas_100g=0.3, carbos_100g=14, grasas_100g=0.2, fibra_100g=2.4, vitamina_c_mg=4.6)
        Alimento.objects.create(nombre="Platano", calorias_100g=89, proteinas_100g=1.1, carbos_100g=22.8, grasas_100g=0.3, fibra_100g=2.6, potasio_mg=358, vitamina_c_mg=8.7)
        Alimento.objects.create(nombre="Queso", calorias_100g=402, proteinas_100g=25, carbos_100g=1.3, grasas_100g=33)
        Alimento.objects.create(nombre="Yogur", calorias_100g=59, proteinas_100g=10, carbos_100g=3.6, grasas_100g=0.4)
        Alimento.objects.create(nombre="Avena", calorias_100g=389, proteinas_100g=16.9, carbos_100g=66, grasas_100g=6.9, fibra_100g=10.6)

def planes(request):
    seed_db()
    from .models import Receta, RecetaFavorita, ComidaDiaria
    from datetime import date, timedelta, datetime
    
    # 1. Búsqueda Local y Ordenamiento
    q = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', '')
    vista_activa = request.GET.get('view', 'recetario')
    
    if q == 'tendencia':
        recetas = Receta.objects.all().order_by('-rating')[:20]
    elif q:
        recetas = Receta.objects.filter(Q(titulo__icontains=q) | Q(descripcion__icontains=q))
    else:
        recetas = Receta.objects.all()
    
    # Aplicar ordenamiento
    from django.db.models import Case, When, Value, IntegerField
    if sort == 'dificultad':
        recetas = recetas.annotate(
            diff_level=Case(
                When(dificultad='Fácil', then=Value(1)),
                When(dificultad='Facil', then=Value(1)),
                When(dificultad='Media', then=Value(2)),
                When(dificultad='Difícil', then=Value(3)),
                When(dificultad='Dificil', then=Value(3)),
                default=Value(2),
                output_field=IntegerField(),
            )
        ).order_by('diff_level')
    elif sort == 'ingredientes':
        recetas = recetas.order_by('ingredientes_count')
    elif sort == 'tiempo':
        recetas = recetas.order_by('tiempo_minutos')
    else:
        recetas = recetas.order_by('-id')

    recetas = list(recetas)

    # 2. Lógica de Cache para la API
    cache_key = f"api_fetched_{q if q else 'default'}"
    from django.core.cache import cache
    ya_buscado = cache.get(cache_key)

    # Aumentado el umbral a 40 recetas mínimo
    should_fetch_api = not ya_buscado and (q or len(recetas) < 40)

    if should_fetch_api:
        try:
            api_key = "40fcdd780cb940a5a6c55c79f3bf4857"
            query_term = q if q else "mediterranean"
            num_api = 30 if not q else 15
            
            # Spoonacular
            url = f"https://api.spoonacular.com/recipes/complexSearch?apiKey={api_key}&query={query_term}&addRecipeInformation=true&number={num_api}&addRecipeNutrition=true"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('results', [])
                
                # Traducción simple de términos comunes si detectamos que vienen de API externa
                def traducir_fast(txt):
                    dic = {
                        'Chicken': 'Pollo', 'Rice': 'Arroz', 'Salad': 'Ensalada', 'Beef': 'Carne', 'Fish': 'Pescado',
                        'Pasta': 'Pasta', 'Egg': 'Huevo', 'Healthy': 'Saludable', 'Breakfast': 'Desayuno',
                        'Lunch': 'Almuerzo', 'Dinner': 'Cena', 'Bowl': 'Bowl', 'Soup': 'Sopa', 'Roast': 'Asado',
                        'Grilled': 'A la plancha', 'Fresh': 'Fresco', 'Quick': 'Rápido', 'Easy': 'Fácil',
                        'Low Carb': 'Bajo en carbos', 'Keto': 'Keto', 'Vegan': 'Vegano', 'Vegetarian': 'Vegetariano'
                    }
                    for k, v in dic.items():
                        txt = txt.replace(k, v).replace(k.lower(), v.lower())
                    return txt

                for item in items:
                    titulo_esp = traducir_fast(item['title'])
                    if not Receta.objects.filter(titulo__iexact=titulo_esp).exists():
                        # Extraer Macros
                        nuts = {n['name']: n for n in item.get('nutrition', {}).get('nutrients', [])}
                        cal = int(nuts.get('Calories', {}).get('amount', 400))
                        prot = int(nuts.get('Protein', {}).get('amount', 20))
                        
                        # Determinar categoría y dieta
                        cat = 'explorar'
                        if 'breakfast' in item.get('dishTypes', []): cat = 'desayuno'
                        
                        tipo_dieta = 'OMNI'
                        if item.get('ketogenic'): tipo_dieta = 'KETO'
                        elif item.get('vegan'): tipo_dieta = 'VEGA'
                        elif item.get('vegetarian'): tipo_dieta = 'VEGE'

                        # Extraer tiempo numérico
                        try:
                            t_min = int(item.get('readyInMinutes', 30))
                        except: t_min = 30

                        # PERSISTENCIA: Guardamos en la base de datos
                        nueva_receta = Receta.objects.create(
                            titulo=titulo_esp,
                            descripcion=f"Deliciosa receta de {titulo_esp} adaptada para tu plan nutricional.",
                            imagen_url=item['image'],
                            calorias=cal,
                            tiempo=f"{t_min} min",
                            tiempo_minutos=t_min,
                            rating=round(4.0 + (item.get('aggregateLikes', 0) / 1000), 1),
                            proteinas=prot,
                            carbos=random.randint(20, 50),
                            grasas=random.randint(10, 30),
                            tipo_dieta=tipo_dieta,
                            categoria=cat,
                            ingredientes_count=len(item.get('nutrition', {}).get('ingredients', [])) or random.randint(5, 12)
                        )
                        recetas.append(nueva_receta)
            # --- FALLBACK THEMEALDB (Solo si seguimos con muy pocas) ---
            if len(recetas) < 8:
                url_db = f"https://www.themealdb.com/api/json/v1/1/search.php?s={query_term}"
                try:
                    resp = requests.get(url_db, timeout=3)
                    if resp.status_code == 200:
                        meals = resp.json().get('meals', [])
                        for m in (meals[:5] if meals else []):
                            if not Receta.objects.filter(titulo__iexact=m['strMeal']).exists():
                                nueva_receta = Receta.objects.create(
                                    titulo=traducir_fast(m['strMeal']),
                                    descripcion=f"Receta internacional de {traducir_fast(m['strMeal'])} lista para disfrutar.",
                                    imagen_url=m['strMealThumb'],
                                    calorias=random.randint(400, 600),
                                    tiempo="30 min", rating=4.6,
                                    proteinas=30, carbos=20, grasas=10,
                                    tipo_dieta='OMNI', categoria='explorar'
                                )
                                recetas.append(nueva_receta)
                except: pass
            
            # Marcar como ya buscado en cache por 1 hora para evitar re-hits constantes
            cache.set(cache_key, True, 3600)

        except Exception as e:
            print(f"Error API: {e}")

    # Favoritos
    favoritas_ids = []
    if request.user.is_authenticated and hasattr(request.user, 'perfil'):
        favoritas_ids = list(RecetaFavorita.objects.filter(perfil=request.user.perfil).values_list('receta_id', flat=True))

    es_invitado = False
    if request.user.is_authenticated and hasattr(request.user, 'perfil'):
        es_invitado = request.user.perfil.rol == 'GUEST'

    # Opciones dinámicas para filtros
    from .models import Perfil
    opciones_dieta = {k: v for k, v in Perfil.OPCIONES_DIETA if k != 'OTRO'}
    
    # Categorías únicas presentes en la BD + bases
    cats_db = list(Receta.objects.values_list('categoria', flat=True).distinct())
    cats_base = ['desayuno', 'almuerzo', 'cena', 'snack', 'postre']
    categorias = sorted(list(set(cats_db + cats_base)))

    # --- Lógica de Calendario Semanal ---
    semana = []
    selected_date_str = request.GET.get('date')
    selected_date = None
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except: pass

    if request.user.is_authenticated and not es_invitado:
        # Usamos la misma lógica que en diario()
        current_date = date.today()
        start_of_week = current_date # Empezamos hoy
        dias_nombres = ['DOM', 'LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB']
        
        for i in range(7):
            d = start_of_week + timedelta(days=i)
            # Comidas para este día
            comidas_dia = ComidaDiaria.objects.filter(perfil=request.user.perfil, fecha=d)
            
            # El día está activo si es el seleccionado por URL, o si no hay selección y es hoy
            is_active = (selected_date == d) if selected_date else (d == date.today())
            
            semana.append({
                'fecha': d,
                'dia_num': d.day,
                'nombre': dias_nombres[(d.weekday() + 1) % 7],
                'is_active': is_active,
                'comidas': comidas_dia
            })

    return render(request, 'base/planes.html', {
        'base_template': get_base_template(request),
        'recetas': recetas,
        'favoritas_ids': favoritas_ids,
        'es_invitado': es_invitado,
        'opciones_dieta': opciones_dieta,
        'categorias_receta': categorias,
        'vista_activa': vista_activa,
        'semana_calendario': semana,
        'fecha_seleccionada': selected_date_str
    })

@login_required
def analizador(request):
    perfil = request.user.perfil
    
    # 1. Manejo de Fecha
    date_str = request.GET.get('date')
    if date_str:
        try:
            current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            current_date = date.today()
    else:
        current_date = date.today()

    # 2. Obtener Comidas
    comidas = perfil.comidas_diarias.filter(fecha=current_date).order_by('hora')
    
    # 3. Resumen de Macros Reales (Consumidos)
    consumo = {
        'calorias': sum(c.calorias for c in comidas),
        'proteinas': sum(c.proteinas for c in comidas),
        'carbos': sum(c.carbos for c in comidas),
        'grasas': sum(c.grasas for c in comidas),
    }

    # 4. Objetivos del Perfil
    informe = perfil.generar_informe_nutricional()
    plan = informe['plan']
    
    # 5. Porcentajes de Cumplimiento
    progress = {
        'calorias': min(round((consumo['calorias'] / plan['calorias_dia']) * 100), 100) if plan['calorias_dia'] > 0 else 0,
        'proteinas': min(round((consumo['proteinas'] / plan['proteinas_g']) * 100), 100) if plan['proteinas_g'] > 0 else 0,
        'carbos': min(round((consumo['carbos'] / plan['carbohidratos_g']) * 100), 100) if plan['carbohidratos_g'] > 0 else 0,
        'grasas': min(round((consumo['grasas'] / plan['grasas_g']) * 100), 100) if plan['grasas_g'] > 0 else 0,
        'faltan_kcal': max(plan['calorias_dia'] - consumo['calorias'], 0)
    }

    # 6. Generar Calendario Semanal (la semana del current_date)
    start_of_week = current_date - timedelta(days=current_date.weekday() + 1 if current_date.weekday() != 6 else 0) # Domingo
    semana = []
    dias_nombres = ['DOM', 'LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB']
    for i in range(7):
        d = start_of_week + timedelta(days=i)
        semana.append({
            'fecha': d,
            'dia_num': d.day,
            'nombre': dias_nombres[i],
            'is_today': d == date.today(),
            'is_active': d == current_date,
            'fecha_iso': d.isoformat()
        })

    context = {
        'base_template': get_base_template(request),
        'current_date': current_date,
        'prev_week': (current_date - timedelta(days=7)).isoformat(),
        'next_week': (current_date + timedelta(days=7)).isoformat(),
        'comidas': comidas,
        'consumo': consumo,
        'plan': plan,
        'progress': progress,
        'semana': semana,
        'mes_nombre': current_date.strftime('%B %Y')
    }

    if request.headers.get('HX-Request'):
        return render(request, 'base/analizador.html', context)
    
    return render(request, 'base/analizador.html', context)

@login_required
def progreso(request):
    if request.user.is_staff:
        # VISTA DE ADMIN PARA PROGRESO: Estadísticas Globales de la App
        from .models import Perfil, ComidaDiaria, RegistroAgua, RegistroSueno, Receta
        from django.db.models import Count, Avg, Sum
        
        total_perfiles = Perfil.objects.exclude(usuario__username='invitado').count()
        promedio_imc = Perfil.objects.exclude(usuario__username='invitado').aggregate(avg_grasa=Avg('porcentaje_grasa'))
        
        # Estadísticas de uso de la app
        today = date.today()
        comidas_hoy = ComidaDiaria.objects.filter(fecha=today).count()
        total_vasos_hoy = RegistroAgua.objects.filter(fecha=today).aggregate(total=Sum('cantidad_vasos'))['total'] or 0
        agua_hoy = round(total_vasos_hoy * 0.25, 1)
        suenos_7d = RegistroSueno.objects.filter(fecha__gte=today - timedelta(days=7))
        sueno_avg = sum(s.horas_totales for s in suenos_7d) / max(suenos_7d.count(), 1)
        
        dist_objetivos = list(Perfil.objects.exclude(usuario__username='invitado').values('objetivo').annotate(count=Count('id')))
        
        return render(request, 'base/progreso.html', {
            'base_template': get_base_template(request),
            'es_admin_view': True,
            'app_stats': {
                'total_users': total_perfiles,
                'comidas_registradas_hoy': comidas_hoy,
                'litros_agua_hoy': round(agua_hoy, 1),
                'promedio_sueno_7d': round(sueno_avg, 1),
                'recetas_totales': Receta.objects.count(),
                'objetivos': dist_objetivos
            }
        })

    perfil = request.user.perfil
    peso = float(perfil.obtener_peso_actual())
    altura_m = float(perfil.altura) / 100 if perfil.altura else 0
    
    # 1. Biometría Base
    imc = 0
    imc_estado = "SIN DATOS"
    if peso > 0 and altura_m > 0:
        imc = round(peso / (altura_m ** 2), 1)
        if imc < 18.5: imc_estado = "BAJO PESO"
        elif imc < 25: imc_estado = "ÓPTIMO"
        elif imc < 30: imc_estado = "SOBREPESO"
        else: imc_estado = "OBESIDAD"
    
    # 2. Composición Avanzada (Ciencia)
    grasa_pct = float(perfil.porcentaje_grasa) if perfil.porcentaje_grasa else 20.0
    grasa_kg = round(peso * (grasa_pct / 100), 1)
    masa_magra = round(peso - grasa_kg, 1)
    musculo_est = round(masa_magra * 0.45, 1) # Estimación fitness estándar
    agua_lt = round(masa_magra * 0.73, 1) # La masa magra es ~73% agua
    hueso_kg = round(peso * 0.15, 1) # El esqueleto humano es ~15% del peso total
    
    # 3. Metabolismo & Energía
    try:
        info_nutri = perfil.generar_informe_nutricional()
        tmb = info_nutri['datos_base']['tmb_pura']
        tdee = info_nutri['datos_base']['mantenimiento']
        calorias_obj = info_nutri['plan']['calorias_dia']
    except:
        tmb = tdee = calorias_obj = 0
    
    # 4. Proyecciones IA (Matemáticas Futuras)
    deficit_superavit = calorias_obj - tdee
    cambio_mensual_kg = (deficit_superavit * 30) / 7700 # 7700 kcal ~= 1kg de grasa
    
    proyecciones = {
        '30_dias': round(peso + cambio_mensual_kg, 1),
        '60_dias': round(peso + (cambio_mensual_kg * 2), 1),
        '90_dias': round(peso + (cambio_mensual_kg * 3), 1),
        'tendencia': "DESCENSO" if cambio_mensual_kg < 0 else "ASCENSO" if cambio_mensual_kg > 0 else "NEUTRO"
    }

    # 5. Edad Nutricional (Fun AI Logic)
    # Factor basando en IMC óptimo (22) y actividad
    consistencia = 0.85 # Placeholder hasta tener logs reales
    edad_real = perfil.edad if perfil.fecha_nacimiento else 30
    desviacion_imc = abs(imc - 22) if imc > 0 else 5
    edad_nutri = round(edad_real + (desviacion_imc * 0.5) - (consistencia * 3))

    from .models import LoginStreak, RegistroPeso
    import json
    racha = LoginStreak.calcular_racha(perfil)

    # Obtener historial de pesos (más reciente primero)
    historial_pesos = list(RegistroPeso.objects.filter(perfil=perfil).order_by('-fecha')[:30])

    # Preparar datos para la gráfica (mostramos en el mismo orden: último -> primero)
    pesos_data = {
        'fechas': [p.fecha.strftime('%d/%m') for p in historial_pesos],
        'valores': [float(p.peso) for p in historial_pesos]
    }
    pesos_data_json = json.dumps(pesos_data)

    context = {
        'base_template': get_base_template(request),
        'peso_actual': peso,
        'imc': imc,
        'imc_estado': imc_estado,
        'avatar': perfil.get_avatar_state(),
        'racha': racha,
        'historial_pesos': historial_pesos,
        'pesos_data': pesos_data_json,
        'composicion': {
            'grasa_kg': grasa_kg,
            'grasa_pct': grasa_pct,
            'masa_magra': masa_magra,
            'musculo_kg': musculo_est,
            'agua_lt': agua_lt,
            'hueso_kg': hueso_kg,
        },
        'metabolismo': {
            'tmb': tmb,
            'tdee': tdee,
            'objetivo_calorico': calorias_obj,
        },
        'proyecciones': proyecciones,
        'edad_nutri': edad_nutri,
        'edad_real': edad_real,
    }
    
    return render(request, 'base/progreso.html', context)

def biblio(request):
    seed_db()
    from .models import Articulo, ArticuloGuardado
    articulos = Articulo.objects.all()
    
    guardados_ids = []
    if request.user.is_authenticated and hasattr(request.user, 'perfil'):
        guardados_ids = list(ArticuloGuardado.objects.filter(perfil=request.user.perfil).values_list('articulo_id', flat=True))

    return render(request, 'base/biblio.html', {
        'base_template': get_base_template(request),
        'articulos': articulos,
        'guardados_ids': guardados_ids
    })

@login_required
def toggle_favorito(request, receta_id):
    from .models import Receta, RecetaFavorita
    perfil = request.user.perfil
    receta = Receta.objects.get(id=receta_id)
    
    obj, created = RecetaFavorita.objects.get_or_create(perfil=perfil, receta=receta)
    if not created:
        obj.delete()
        is_fav = False
    else:
        is_fav = True
        
    return JsonResponse({'status': 'success', 'is_favorite': is_fav})

@login_required
def toggle_guardado(request, articulo_id):
    from .models import Articulo, ArticuloGuardado
    perfil = request.user.perfil
    articulo = Articulo.objects.get(id=articulo_id)
    
    obj, created = ArticuloGuardado.objects.get_or_create(perfil=perfil, articulo=articulo)
    if not created:
        obj.delete()
        is_saved = False
    else:
        is_saved = True
        
    return JsonResponse({'status': 'success', 'is_saved': is_saved})

def iniciar_sesion(request):
    # Si el usuario ya está autenticado y NO es el usuario 'invitado', redirigirle fuera
    if request.user.is_authenticated and getattr(request.user, 'username', None) != 'invitado':
        return redirect('base:index')
    if request.method == 'POST':
        # Intentar procesar inicio de sesión
        if 'login_submit' in request.POST:
            login_form = CustomAuthenticationForm(request, data=request.POST)
            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)
                # Mantener la sesión abierta por 14 días
                try:
                    request.session.set_expiry(1209600)
                except Exception:
                    pass
                messages.success(request, f'¡Bienvenido de nuevo, {user.first_name or user.username}!')
                return redirect('base:index')
            else:
                messages.error(request, 'Usuario o contraseña incorrectos. Por favor, verifica tus datos.')
                # Mantener el formulario de registro vacío pero válido para renderizar
                register_form = CustomUserCreationForm()
        
        # Si por alguna razón llega un POST de registro a esta URL (recuperación de errores)
        elif 'register_submit' in request.POST:
             return registro(request)
    else:
        login_form = CustomAuthenticationForm()
        register_form = CustomUserCreationForm()

    return render(request, 'auth/autenticacion.html', {
        'base_template': get_base_template(request),
        'initial_mode': 'login',
        'login_form': login_form,
        'register_form': register_form
    })

def registro(request):
    # Si el usuario ya está autenticado y NO es 'invitado', no permitir registro
    if request.user.is_authenticated and getattr(request.user, 'username', None) != 'invitado':
        return redirect('base:index')
    if request.method == 'POST':
        if 'register_submit' in request.POST:
            register_form = CustomUserCreationForm(request.POST)
            if register_form.is_valid():
                user = register_form.save()
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                try:
                    request.session.set_expiry(1209600)
                except Exception:
                    pass
                messages.success(request, f'¡Cuenta creada exitosamente! Bienvenido a nunut, {user.first_name or user.username}!')
                return redirect('base:index')
            else:
                # Mostrar errores de forma amigable
                if register_form.errors.get('username'):
                    messages.error(request, 'Este nombre de usuario ya está en uso. Elige otro.')
                if register_form.errors.get('email'):
                    messages.error(request, 'Este email ya está registrado.')
                if register_form.errors.get('password2'):
                    messages.error(request, 'Las contraseñas no coinciden.')
                if register_form.errors.get('password1'):
                    for error in register_form.errors.get('password1'):
                        messages.error(request, error)
                
                login_form = CustomAuthenticationForm()
        
        elif 'login_submit' in request.POST:
            return iniciar_sesion(request)
    else:
        register_form = CustomUserCreationForm()
        login_form = CustomAuthenticationForm()

    return render(request, 'auth/autenticacion.html', {
        'base_template': get_base_template(request),
        'initial_mode': 'register',
        'login_form': login_form,
        'register_form': register_form
    })

def bienvenida(request):
    # Si el usuario ya está autenticado y NO es 'invitado', redirigir al `index`
    if request.user.is_authenticated and getattr(request.user, 'username', None) != 'invitado':
        return redirect('base:index')
    return render(request, 'auth/bienvenida.html', {'base_template': get_base_template(request)})

def recuperar_contrasena(request):
    # --- LÓGICA PARA REINICIAR EL PROCESO ---
    if request.GET.get('restart'):
        request.session['reset_step'] = 1
        request.session.pop('reset_email', None)
        request.session.pop('reset_code', None)
        return redirect('base:recuperar_contrasena') # Cambia por el nombre de tu URL

    # Obtener el paso actual (por defecto 1)
    step = request.session.get('reset_step', 1)

    if request.method == 'POST':
        # PASO 1: ENVIAR CÓDIGO
        if step == 1:
            email = request.POST.get('email').lower().strip()
            try:
                user = User.objects.get(email=email)
                # Generar código de 6 dígitos
                code = str(random.randint(100000, 999999))
                
                # Guardar en sesión
                request.session['reset_email'] = email
                request.session['reset_code'] = code
                
                # Enviar Email
                asunto = 'Código de recuperación - Nunut'
                mensaje = f'Hola, tu código de verificación para restablecer tu contraseña es: {code}'
                email_desde = 'Nunut <noreply@nunut.com>' # Configurado en settings.py
                
                send_mail(asunto, mensaje, email_desde, [email], fail_silently=False)
                
                request.session['reset_step'] = 2
                messages.success(request, f"Código enviado a {email}")
                
            except User.DoesNotExist:
                messages.error(request, "No existe una cuenta con ese correo electrónico.")
            except Exception as e:
                messages.error(request, f"Error al enviar el correo. Revisa tu conexión. Detalle: {e}")

        # PASO 2: VERIFICAR CÓDIGO
        elif step == 2:
            input_code = request.POST.get('code')
            session_code = request.session.get('reset_code')

            if input_code == session_code:
                request.session['reset_step'] = 3
                messages.success(request, "Código correcto. Ingresa tu nueva contraseña.")
            else:
                messages.error(request, "El código ingresado es incorrecto.")

        # PASO 3: CAMBIAR CONTRASEÑA
        elif step == 3:
            password = request.POST.get('new_password')
            confirm = request.POST.get('confirm_password')

            if password == confirm:
                if len(password) < 8:
                    messages.error(request, "La contraseña debe tener al menos 8 caracteres.")
                else:
                    email = request.session.get('reset_email')
                    user = User.objects.get(email=email)
                    user.password = make_password(password)
                    user.save()

                    # Limpiar la sesión por completo
                    request.session.pop('reset_step', None)
                    request.session.pop('reset_email', None)
                    request.session.pop('reset_code', None)

                    messages.success(request, "Contraseña actualizada correctamente. Ya puedes entrar.")
                    return redirect('base:iniciar_sesion')
            else:
                messages.error(request, "Las contraseñas no coinciden.")

        return redirect(request.path)

    return render(request, 'auth/recuperar_contrasena.html', {'step': step})


@login_required
def guardar_paso(request, paso_id):
    # Asegurar que el usuario tenga un `Perfil` asociado (puede faltar por señales no disparadas)
    from .models import Perfil
    perfil = getattr(request.user, 'perfil', None)
    if perfil is None:
        perfil = Perfil.objects.create(usuario=request.user)
    
    if request.method == 'POST':
        form = OnboardingForm(request.POST, request.FILES, instance=perfil, step=paso_id)
        
        if form.is_valid():
            perfil_guardado = form.save(commit=False)
            
            if 'foto_perfil_upload' in request.FILES:
                image_file = request.FILES['foto_perfil_upload']
                perfil_guardado.foto_perfil = image_file.read()
            
            perfil_guardado.save()
            form.save_extra_data(perfil_guardado) 
            
            if paso_id >= 4:
                perfil_guardado.onboarding_completado = True
                perfil_guardado.save()
                if request.headers.get('HX-Request'):
                    response = HttpResponse()
                    response['HX-Redirect'] = reverse('base:index')
                    return response
                return redirect('base:index')
            
            # Si el guardado fue bien y no es el final, avanzamos al siguiente paso
            target_step = paso_id + 1
            # Reinstanciamos para el NUEVO paso
            form = OnboardingForm(instance=perfil, step=target_step)
        else:
            # Formulario inválido, nos quedamos en el mismo paso con el form actual (que tiene los errores)
            target_step = paso_id
            from django.contrib import messages
            messages.error(request, "Error al guardar el paso. Por favor revisa los datos ingresados.")
    else:
        # Es un GET, mostramos el paso solicitado
        target_step = paso_id
        form = OnboardingForm(instance=perfil, step=target_step)

    # --- RENDERIZADO ---
    template_name = f'encuesta/paso{target_step}.html'
    
    context = {
        'paso_actual': target_step,
        'form': form,
    }
    
    if target_step == 2:
        context.update({
            'niveles_actividad': [('SEDE', 'Sedentario', 'chair'), ('LIGE', 'Activo', 'directions_walk'), ('MODE', 'Muy Activo', 'fitness_center'), ('ATLE', 'Atleta', 'bolt')],
            'objetivos': [('PERDER', 'Bajar de peso', '...', 'nutrition', '...'), ('GANAR', 'Ganar músculo', '...', 'fitness_center', '...'), ('MANTENER', 'Mantener Salud', '...', 'spa', '...')]
        })

    return render(request, template_name, context)

def invitado(request):
    # Usamos nombre en minúsculas como se solicitó
    user, created = User.objects.get_or_create(username='invitado', defaults={
        'email': 'invitado@nunut.com',
        'first_name': 'Invitado',
        'is_active': True
    })
    
    if created:
        user.set_unusable_password()
        user.save()

    # Asegurar que el perfil tenga el onboarding completado
    from .models import Perfil
    perfil, p_created = Perfil.objects.get_or_create(usuario=user)
    perfil.onboarding_completado = True
    perfil.rol = 'GUEST'
    perfil.save()

    # Iniciar sesión especificando el backend explícitamente para evitar ambigüedades
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    
    try:
        request.session.set_expiry(1209600) # 14 días
    except Exception:
        pass
        
    messages.info(request, "🎯 Estás navegando como invitado. Regístrate para acceder a funciones personalizadas como planes nutricionales y seguimiento de progreso.")
    return redirect('base:index')

def cerrar_sesion(request):
    """Cierra la sesión del usuario y redirige a la bienvenida."""
    logout(request)
    return redirect('base:bienvenida')

from django.contrib.auth.decorators import login_required
from .forms import EditarPerfilForm

@login_required
def perfil(request):
    if request.method == 'POST':
        form = EditarPerfilForm(request.POST, request.FILES, instance=request.user.perfil, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Perfil actualizado exitosamente!')
            return redirect('base:perfil')
        else:
            for error in form.errors.values():
                for e in error:
                    messages.error(request, e)
    else:
        form = EditarPerfilForm(instance=request.user.perfil, user=request.user)
    
    # Preparar datos dinámicos para la plantilla
    perfil = getattr(request.user, 'perfil', None)
    if perfil is None:
        from .models import Perfil
        perfil = Perfil.objects.create(usuario=request.user)

    # Peso actual: tomar el último registro si existe
    peso_actual = None
    try:
        ultimo = perfil.historial_peso.first()
        if ultimo:
            peso_actual = float(ultimo.peso)
    except Exception:
        peso_actual = None

    altura_cm = float(perfil.altura) if perfil.altura else None
    imc = None
    if peso_actual and altura_cm:
        try:
            altura_m = altura_cm / 100.0
            imc = round(peso_actual / (altura_m * altura_m), 1)
        except Exception:
            imc = None

    objetivo_display = perfil.get_objetivo_display() if perfil and perfil.objetivo else None
    nivel_actividad_display = perfil.get_nivel_actividad_display() if perfil and perfil.nivel_actividad else None

    # Lógica de Logros y Racha
    from .models import Logro, LoginStreak
    
    # 1. Verificar Logros Dinámicos
    Logro.verificar_y_otorgar(perfil)
    
    # 2. Obtener datos para la vista
    racha_actual = LoginStreak.calcular_racha(perfil)
    logros_recientes = perfil.logros.all().order_by('-fecha_obtenido')[:4]

    return render(request, 'base/perfil.html', {
        'base_template': get_base_template(request),
        'form': form,
        'perfil': perfil,
        'altura_cm': altura_cm,
        'peso_actual': peso_actual,
        'imc': imc,
        'objetivo_display': objetivo_display,
        'nivel_actividad_display': nivel_actividad_display,
        # Nuevos datos
        'racha_dias': racha_actual,
        'logros': logros_recientes,
        'total_logros': perfil.logros.count()
    })

@login_required
def toggle_dark_mode(request):
    if request.user.is_authenticated:
        perfil = request.user.perfil
        perfil.modo_oscuro = not perfil.modo_oscuro
        perfil.save()
        return JsonResponse({'status': 'success', 'modo_oscuro': perfil.modo_oscuro})
    return JsonResponse({'status': 'error'}, status=403)


@login_required
def perfil_api(request):
    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return JsonResponse({'error': 'Perfil no encontrado'}, status=404)

    data = {
        'usuario': request.user.username,
        'email': request.user.email,
        'localidad': perfil.localidad,
        'genero': perfil.get_genero_display() if perfil.genero else None,
        'fecha_nacimiento': perfil.fecha_nacimiento.isoformat() if perfil.fecha_nacimiento else None,
        'altura': str(perfil.altura) if perfil.altura else None,
        'nivel_actividad': perfil.nivel_actividad,
        'objetivo': perfil.objetivo,
        'gustos': list(perfil.gustos.values_list('nombre', flat=True)),
        'alergias': list(perfil.alergias.values_list('nombre', flat=True)),
        'foto_perfil_base64': perfil.get_foto_base64(),
        'onboarding_completado': perfil.onboarding_completado,
    }
    return JsonResponse(data)


# NOTE: `perfil` URL already existe y muestra el perfil del usuario.
# Eliminada la vista `perfil_detalle` para evitar duplicados.


@login_required
def perfiles_api(request):
    """Listado de todos los perfiles — solo para staff/admin — con paginación simple.

    Query params:
    - page: número de página (default 1)
    - per_page: items por página (default 20)
    """
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Permiso denegado'}, status=403)

    from .models import Perfil
    qs = Perfil.objects.select_related('usuario').prefetch_related('gustos', 'alergias').all()

    # Parámetros de paginación
    try:
        per_page = int(request.GET.get('per_page', 20))
    except (TypeError, ValueError):
        per_page = 20

    try:
        page = int(request.GET.get('page', 1))
    except (TypeError, ValueError):
        page = 1

    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.page(1)

    results = []
    for perfil in page_obj.object_list:
        results.append({
            'usuario': perfil.usuario.username,
            'email': perfil.usuario.email if request.user.is_superuser else f"ID: {perfil.id}",
            'localidad': perfil.localidad,
            'altura': str(perfil.altura) if perfil.altura else None,
            'nivel_actividad': perfil.nivel_actividad,
            'objetivo': perfil.objetivo,
        })

    payload = {
        'total': paginator.count,
        'per_page': per_page,
        'page': page_obj.number,
        'total_pages': paginator.num_pages,
        'results': results,
    }
    return JsonResponse(payload)

def calcular_macros_api(request):
    # Requerir usuario autenticado
    from django.contrib.auth.decorators import login_required
    # Decorator aplicado manualmente para evitar reordenar imports
    @login_required
    def _inner(request):
        # 1. Caso Invitado: Mostrar invitación a unirse
        if request.user.username == 'invitado':
            return render(request, 'encuesta/parciales/invitacion_registro.html')

        try:
            perfil = request.user.perfil
        except Exception:
            # Si por algún motivo no hay perfil
            return render(request, 'encuesta/parciales/invitacion_registro.html')

        # 2. Caso Usuario Registrado con Perfil Incompleto
        # Verificamos campos críticos para el cálculo de TDEE/Macros
        campos_completos = all([
            perfil.fecha_nacimiento,
            perfil.obtener_peso_actual(),
            perfil.altura,
            perfil.genero,
            perfil.nivel_actividad,
            perfil.objetivo
        ])

        if not campos_completos:
            return render(request, 'encuesta/parciales/fin_encuesta.html')

        # 3. Caso Normal: Generar informe
        informe = perfil.generar_informe_nutricional()

        if request.headers.get('HX-Request'):
            return render(request, 'encuesta/parciales/macros_card.html', {'informe': informe})

        return JsonResponse(informe)

    return _inner(request)

# --- ADMIN PANEL LOGIC ---

@user_passes_test(lambda u: u.is_staff, login_url='base:index')
def admin_dashboard(request):
    context = _get_admin_dashboard_data(request)
    context['base_template'] = get_base_template(request)
    context['es_admin_view'] = True
    return render(request, 'base/index.html', context)

@login_required
def enviar_sugerencia(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            from .models import Sugerencia
            Sugerencia.objects.create(
                perfil=request.user.perfil,
                asunto=data.get('asunto', 'Sugerencia General'),
                mensaje=data.get('mensaje', ''),
                calificacion=data.get('calificacion', 5)
            )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)

@user_passes_test(lambda u: u.is_staff)
def responder_sugerencia(request, sugerencia_id):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            from .models import Sugerencia, LogActividad
            sug = Sugerencia.objects.get(id=sugerencia_id)
            sug.respuesta_admin = data.get('respuesta')
            sug.estado = data.get('estado', 'REVISION')
            sug.save()
            
            # Intento de envío de email
            try:
                send_mail(
                    f"nunt AI: Respuesta a tu sugerencia",
                    f"Hola {sug.perfil.usuario.first_name or sug.perfil.usuario.username},\n\nHemos revisado tu mensaje: '{sug.mensaje}'\n\nRespuesta de nuestro equipo:\n{sug.respuesta_admin}\n\nGracias por ayudarnos a mejorar.",
                    'soporte@nunut.ai',
                    [sug.perfil.usuario.email],
                    fail_silently=True
                )
            except: pass

            LogActividad.objects.create(
                usuario=request.user,
                accion=f"Respondió a sugerencia #{sug.id}",
                detalles=f"Estado: {sug.estado}"
            )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)

@user_passes_test(lambda u: u.is_staff)
def marcar_leido_sugerencia(request, sugerencia_id):
    from .models import Sugerencia
    try:
        sug = Sugerencia.objects.get(id=sugerencia_id)
        sug.estado = 'LEIDO'
        sug.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@user_passes_test(lambda u: u.is_staff)
def archivar_sugerencia(request, sugerencia_id):
    from .models import Sugerencia
    try:
        sug = Sugerencia.objects.get(id=sugerencia_id)
        sug.estado = 'ARCHIVADO'
        sug.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@user_passes_test(lambda u: u.is_staff)
def curar_receta(request, receta_id):
    if request.method == 'POST':
        from .models import Receta, LogActividad
        try:
            receta = Receta.objects.get(id=receta_id)
            accion = request.POST.get('accion') # 'aprobar' o 'rechazar'
            
            if accion == 'aprobar':
                receta.esta_aprobada = True
                receta.save()
                LogActividad.objects.create(
                    usuario=request.user,
                    accion=f"Aprobó receta: {receta.titulo}"
                )
            elif accion == 'rechazar':
                LogActividad.objects.create(
                    usuario=request.user,
                    accion=f"Rechazó receta: {receta.titulo}"
                )
                receta.delete()
                
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)

def admin_registro(request):
    # Only allow if already admin or via secret checking logic (here implemented via form code)
    if request.method == 'POST':
        code = request.POST.get('security_code')
        if code != 'NUNUT-ADMIN-2026': # Simple hardcoded secret
            messages.error(request, 'Código de seguridad inválido.')
            return redirect('base:admin_registro')
            
        # Manually process basic user creation for brevity or reuse form
        form = CustomUserCreationForm(request.POST) # Reusing the form but will patch is_staff
        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            messages.success(request, f'Administrador {user.username} creado correctamente.')
            return redirect('base:admin_dashboard')
        else:
             for error in form.errors.values():
                messages.error(request, error)
    else:
        form = CustomUserCreationForm()
        
    return render(request, 'admin/registro.html', {
        'base_template': get_base_template(request),
        'form': form
    })
@login_required
def crear_receta(request):
    if request.method == 'POST':
        try:
            from .models import Receta
            
            # Extract basic data
            titulo = request.POST.get('titulo')
            dieta = request.POST.get('dieta')
            tiempo = request.POST.get('tiempo')
            img_url = request.POST.get('imagen_url')
            desc = request.POST.get('descripcion')
            
            # Extract macros (default to 0 if empty)
            calorias = int(request.POST.get('calorias') or 0)
            proteinas = int(request.POST.get('proteinas') or 0)
            carbos = int(request.POST.get('carbos') or 0)
            grasas = int(request.POST.get('grasas') or 0)

            # Process Ingredients
            nombres = request.POST.getlist('ingredientes_nombres')
            cantidades = request.POST.getlist('ingredientes_cantidades')
            
            ingredientes_txt = ""
            if nombres and len(nombres) > 0:
                ingredientes_txt = "\n\nINGREDIENTES:\n"
                for n, c in zip(nombres, cantidades):
                     if n.strip():
                        ingredientes_txt += f"- {n.strip()} ({c.strip()})\n"
            
            final_desc = desc + ingredientes_txt

            # Extract numeric time
            try:
                t_str = str(tiempo)
                t_val = int(''.join(filter(str.isdigit, t_str)) or 30)
            except: t_val = 30

            Receta.objects.create(
                perfil_creador=request.user.perfil,
                titulo=titulo,
                tipo_dieta=dieta,
                tiempo=tiempo,
                tiempo_minutos=t_val,
                imagen_url=img_url if img_url else None,
                descripcion=final_desc,
                calorias=calorias,
                proteinas=proteinas,
                carbos=carbos,
                grasas=grasas,
                ingredientes_count=len([n for n in nombres if n.strip()]),
                categoria=request.POST.get('categoria', 'explorar'),
                dificultad=request.POST.get('dificultad', 'Media'),
                presupuesto=request.POST.get('presupuesto', 'Medio')
            )
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

@login_required
def borrar_receta(request, receta_id):
    if request.method == 'POST':
        from .models import Receta
        try:
            receta = Receta.objects.get(id=receta_id)
            if receta.perfil_creador == request.user.perfil:
                receta.delete()
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'No tienes permiso para borrar esta receta.'}, status=403)
        except Receta.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Receta no encontrada.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

@login_required
def editar_receta(request, receta_id):
    from .models import Receta
    try:
        receta = Receta.objects.get(id=receta_id)
    except Receta.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Receta no encontrada'}, status=404)
    
    # Verificar permisos
    if receta.perfil_creador != request.user.perfil:
         return JsonResponse({'success': False, 'error': 'No tienes permiso.'}, status=403)

    if request.method == 'POST':
        try:
            # Extract basic data
            receta.titulo = request.POST.get('titulo')
            # Check for diet type validity if needed, or trust form
            receta.tipo_dieta = request.POST.get('dieta')
            receta.tiempo = request.POST.get('tiempo')
            img_url = request.POST.get('imagen_url')
            
            # Preserve original description part if we want, or just overwrite.
            # Here we assume the form sends the "description" part separate from ingredients again
            desc_text = request.POST.get('descripcion', '')
            
            # Extract macros
            receta.calorias = int(request.POST.get('calorias') or 0)
            receta.proteinas = int(request.POST.get('proteinas') or 0)
            receta.carbos = int(request.POST.get('carbos') or 0)
            receta.grasas = int(request.POST.get('grasas') or 0)

            # New fields
            receta.dificultad = request.POST.get('dificultad', receta.dificultad)
            receta.presupuesto = request.POST.get('presupuesto', receta.presupuesto)
            receta.categoria = request.POST.get('categoria', receta.categoria)
            
            # Extract numeric time
            try:
                t_str = str(receta.tiempo)
                receta.tiempo_minutos = int(''.join(filter(str.isdigit, t_str)) or 30)
            except: receta.tiempo_minutos = 30

            if img_url:
                receta.imagen_url = img_url

            # Process Ingredients
            nombres = request.POST.getlist('ingredientes_nombres')
            cantidades = request.POST.getlist('ingredientes_cantidades')
            
            receta.ingredientes_count = len([n for n in nombres if n.strip()])

            ingredientes_txt = ""
            if nombres and len(nombres) > 0:
                ingredientes_txt = "\n\nINGREDIENTES:\n"
                for n, c in zip(nombres, cantidades):
                     if n.strip():
                        ingredientes_txt += f"- {n.strip()} ({c.strip()})\n"
            
            receta.descripcion = desc_text + ingredientes_txt
            receta.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    # GET: Return JSON for population
    ingredientes_pre = []
    desc_clean = receta.descripcion
    
    if "INGREDIENTES:" in receta.descripcion:
        parts = receta.descripcion.split("INGREDIENTES:")
        desc_clean = parts[0].strip()
        ing_part = parts[1].strip()
        for line in ing_part.split('\n'):
            line = line.strip()
            if line.startswith('-'):
                try:
                    content = line[1:].strip() 
                    # Last parenthesis is quantity
                    if '(' in content and content.endswith(')'):
                        name_part = content.rpartition('(')[0].strip()
                        cant_part = content.rpartition('(')[2].replace(')', '').strip()
                        if name_part:
                            ingredientes_pre.append({'nombre': name_part, 'cantidad': cant_part})
                    else:
                        # Fallback if format is weird
                        ingredientes_pre.append({'nombre': content, 'cantidad': ''})
                except: pass

    data = {
        'id': receta.id,
        'titulo': receta.titulo,
        'tipo_dieta': receta.tipo_dieta,
        'tiempo': receta.tiempo,
        'imagen_url': receta.imagen_url,
        'descripcion': desc_clean,
        'calorias': receta.calorias,
        'proteinas': receta.proteinas,
        'carbos': receta.carbos,
        'grasas': receta.grasas,
        'ingredientes': ingredientes_pre
    }
    
    return JsonResponse({'success': True, 'receta': data})

@login_required
def actualizar_agua(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            cambio = int(data.get('cambio', 0))
            
            from .models import RegistroAgua
            registro, _ = RegistroAgua.objects.get_or_create(perfil=request.user.perfil, fecha=date.today())
            
            registro.actualizar_meta() # Asegurar meta fresca
            registro.cantidad_vasos = max(0, registro.cantidad_vasos + cambio)
            registro.save()
            
            return JsonResponse({
                'status': 'success',
                'cantidad_vasos': registro.cantidad_vasos,
                'litros': float(registro.litros),
                'porcentaje': registro.porcentaje,
                'meta_vasos': registro.meta_vasos
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)

# API para obtener consumo de comidas del día
@login_required
def comidas_hoy_api(request):
    from .models import ComidaDiaria
    from datetime import date
    
    try:
        comidas = ComidaDiaria.objects.filter(
            perfil=request.user.perfil,
            fecha=date.today()
        )
        
        total_calorias = sum(c.calorias for c in comidas)
        total_proteinas = sum(c.proteinas for c in comidas)
        total_carbos = sum(c.carbos for c in comidas)
        total_grasas = sum(c.grasas for c in comidas)
        
        return JsonResponse({
            'status': 'success',
            'consumo': {
                'calorias': total_calorias,
                'proteinas': total_proteinas,
                'carbos': total_carbos,
                'grasas': total_grasas
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def guardar_comida_api(request):
    if request.method == 'POST':
        import json
        from .models import ComidaDiaria
        from datetime import datetime, date
        try:
            data = json.loads(request.body)
            perfil = request.user.perfil
            
            # Hora actual (o la enviada)
            hora_str = data.get('hora')
            if hora_str:
                hora = datetime.strptime(hora_str, '%H:%M').time()
            else:
                hora = datetime.now().time()
            
            fecha_str = data.get('fecha')
            if fecha_str:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            else:
                fecha = date.today()

            ComidaDiaria.objects.create(
                perfil=perfil,
                nombre=data.get('nombre', 'Comida sin nombre'),
                calorias=int(data.get('calorias', 0)),
                proteinas=int(float(data.get('proteinas', 0))),
                carbos=int(float(data.get('carbos', 0))),
                grasas=int(float(data.get('grasas', 0))),
                hora=hora,
                fecha=fecha,
                categoria=data.get('categoria', 'almuerzo')
            )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

# API para guardar registro de sueño
@login_required
def guardar_sueno_api(request):
    if request.method == 'POST':
        import json
        from .models import RegistroSueno
        from datetime import date, datetime, timedelta
        
        try:
            data = json.loads(request.body)
            horas = float(data.get('horas', 0))
            calidad = int(data.get('calidad', 3))
            
            if horas <= 0 or horas > 24:
                return JsonResponse({'status': 'error', 'message': 'Horas inválidas'}, status=400)
            
            # Calcular hora de acostarse y levantarse (aproximado)
            # Asumimos que se levantó hoy a las 7 AM
            hora_levantarse = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
            hora_acostarse = hora_levantarse - timedelta(hours=horas)
            
            # Verificar si ya existe registro de hoy
            registro_existente = RegistroSueno.objects.filter(
                perfil=request.user.perfil,
                fecha=date.today()
            ).first()
            
            if registro_existente:
                # Actualizar existente
                registro_existente.hora_acostarse = hora_acostarse.time()
                registro_existente.hora_levantarse = hora_levantarse.time()
                registro_existente.calidad = calidad
                registro_existente.save()
            else:
                # Crear nuevo
                RegistroSueno.objects.create(
                    perfil=request.user.perfil,
                    hora_acostarse=hora_acostarse.time(),
                    hora_levantarse=hora_levantarse.time(),
                    calidad=calidad
                )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Sueño registrado correctamente'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def guardar_peso_api(request):
    if request.method == 'POST':
        import json
        from .models import RegistroPeso
        from datetime import date
        
        try:
            data = json.loads(request.body)
            peso = float(data.get('peso', 0))
            
            if peso <= 0 or peso > 500:
                return JsonResponse({'status': 'error', 'message': 'Peso inválido'}, status=400)
            
            # Crear nuevo registro de peso
            RegistroPeso.objects.create(
                perfil=request.user.perfil,
                peso=peso
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Peso registrado correctamente',
                'peso': float(peso)
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def borrar_peso(request, peso_id):
    from .models import RegistroPeso
    if request.method in ('DELETE', 'POST'):
        try:
            registro = RegistroPeso.objects.get(id=peso_id, perfil=request.user.perfil)
            registro.delete()
            return JsonResponse({'status': 'success', 'message': 'Registro eliminado correctamente'})
        except RegistroPeso.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Registro no encontrado'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

# API para generar y descargar informe PDF
@login_required
def generar_informe_pdf(request):
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    from datetime import date, timedelta
    from .models import ComidaDiaria, RegistroAgua, RegistroSueno, RegistroPeso
    
    try:
        # Crear el PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="informe_nunut_{date.today()}.pdf"'
        
        # Crear el canvas
        p = canvas.Canvas(response, pagesize=letter)
        width, height = letter
        
        # Título
        p.setFont("Helvetica-Bold", 24)
        p.drawString(1*inch, height - 1*inch, "Informe Nutricional nunut")
        
        # Información del usuario
        p.setFont("Helvetica", 12)
        y = height - 1.5*inch
        p.drawString(1*inch, y, f"Usuario: {request.user.first_name or request.user.username}")
        y -= 0.3*inch
        p.drawString(1*inch, y, f"Fecha: {date.today().strftime('%d/%m/%Y')}")
        
        # Obtener datos de la última semana
        fecha_inicio = date.today() - timedelta(days=7)
        
        # Resumen de calorías
        y -= 0.6*inch
        p.setFont("Helvetica-Bold", 14)
        p.drawString(1*inch, y, "Resumen Semanal")
        
        comidas_semana = ComidaDiaria.objects.filter(
            perfil=request.user.perfil,
            fecha__gte=fecha_inicio
        )
        
        total_cal = sum(c.calorias for c in comidas_semana)
        promedio_cal = total_cal / 7 if comidas_semana.exists() else 0
        
        y -= 0.4*inch
        p.setFont("Helvetica", 11)
        p.drawString(1.2*inch, y, f"Consumo promedio diario: {int(promedio_cal)} kcal")
        
        # Hidratación
        agua_semana = RegistroAgua.objects.filter(
            perfil=request.user.perfil,
            fecha__gte=fecha_inicio
        )
        promedio_agua = sum(r.cantidad_vasos for r in agua_semana) / 7 if agua_semana.exists() else 0
        
        y -= 0.3*inch
        p.drawString(1.2*inch, y, f"Hidratación promedio: {promedio_agua:.1f} vasos/día")
        
        # Sueño
        sueno_semana = RegistroSueno.objects.filter(
            perfil=request.user.perfil,
            fecha__gte=fecha_inicio
        )
        promedio_sueno = sum(r.horas_totales for r in sueno_semana) / 7 if sueno_semana.exists() else 0
        
        y -= 0.3*inch
        p.drawString(1.2*inch, y, f"Sueño promedio: {promedio_sueno:.1f} horas/noche")
        
        # Peso
        peso_actual = request.user.perfil.obtener_peso_actual()
        if peso_actual:
            y -= 0.3*inch
            p.drawString(1.2*inch, y, f"Peso actual: {peso_actual} kg")
        
        # Plan nutricional
        if hasattr(request.user, 'perfil'):
            try:
                informe = request.user.perfil.generar_informe_nutricional()
                y -= 0.6*inch
                p.setFont("Helvetica-Bold", 14)
                p.drawString(1*inch, y, "Plan Nutricional Recomendado")
                
                y -= 0.4*inch
                p.setFont("Helvetica", 11)
                p.drawString(1.2*inch, y, f"Calorías diarias: {informe['plan']['calorias_dia']} kcal")
                y -= 0.3*inch
                p.drawString(1.2*inch, y, f"Proteínas: {informe['plan']['proteinas_g']}g ({informe['porcentajes']['prot_pct']}%)")
                y -= 0.3*inch
                p.drawString(1.2*inch, y, f"Carbohidratos: {informe['plan']['carbohidratos_g']}g ({informe['porcentajes']['carbs_pct']}%)")
                y -= 0.3*inch
                p.drawString(1.2*inch, y, f"Grasas: {informe['plan']['grasas_g']}g ({informe['porcentajes']['grasa_pct']}%)")
            except:
                pass
        
        # Footer
        p.setFont("Helvetica-Oblique", 9)
        p.drawString(1*inch, 0.5*inch, "Generado por nunut - Tu compañero de vida saludable")
        
        # Finalizar PDF
        p.showPage()
        p.save()
        
        return response
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
def calificar_receta(request, receta_id):
    if request.method == 'POST' and request.user.is_authenticated:
        try:
            import json
            data = json.loads(request.body)
            puntuacion = int(data.get('puntuacion', 0))
            
            if 1 <= puntuacion <= 5:
                from .models import CalificacionReceta, Receta
                calif, created = CalificacionReceta.objects.update_or_create(
                    perfil=request.user.perfil,
                    receta_id=receta_id,
                    defaults={'puntuacion': puntuacion}
                )
                
                # Recalcular rating promedio
                receta = calif.receta
                from django.db.models import Avg
                stats = CalificacionReceta.objects.filter(receta=receta).aggregate(Avg('puntuacion'))
                nuevo_promedio = stats['puntuacion__avg']
                
                if nuevo_promedio:
                    receta.rating = round(nuevo_promedio, 1)
                    receta.save()
                
                return JsonResponse({
                    'status': 'success', 
                    'new_rating': float(receta.rating),
                    'message': '¡Gracias por calificar!'
                })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def gestionar_cuenta(request):
    from .forms import ChangeUsernameForm, ChangeEmailForm
    from django.contrib.auth.forms import PasswordChangeForm
    
    return render(request, 'base/gestionar_cuenta.html', {
        'base_template': get_base_template(request),
        'user': request.user,
        'username_form': ChangeUsernameForm(user=request.user),
        'email_form': ChangeEmailForm(user=request.user),
        'password_form': PasswordChangeForm(user=request.user),
    })

@login_required
def cambiar_username(request):
    from .forms import ChangeUsernameForm
    if request.method == 'POST':
        form = ChangeUsernameForm(request.POST, user=request.user)
        if form.is_valid():
            request.user.username = form.cleaned_data['new_username']
            request.user.save()
            messages.success(request, '¡Nombre de usuario actualizado con éxito!')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    return redirect('base:gestionar_cuenta')

@login_required
def cambiar_email(request):
    from .forms import ChangeEmailForm
    if request.method == 'POST':
        form = ChangeEmailForm(request.POST, user=request.user)
        if form.is_valid():
            request.user.email = form.cleaned_data['new_email']
            request.user.save()
            messages.success(request, '¡Correo electrónico actualizado con éxito!')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    return redirect('base:gestionar_cuenta')

@login_required
def cambiar_contrasena(request):
    if request.method == 'POST':
        from django.contrib.auth import update_session_auth_hash
        from django.contrib.auth.forms import PasswordChangeForm
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Tu contraseña ha sido actualizada exitosamente.')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    return redirect('base:gestionar_cuenta')

@login_required
def agregar_al_calendario(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            receta_ids = data.get('receta_ids', [])
            fecha_str = data.get('fecha', str(date.today()))
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            force = data.get('force', False)
            
            from .models import Receta, ComidaDiaria
            
            perfil = request.user.perfil
            
            # Obtener meta de calorías (por defecto 2000)
            meta_calorias = 2000 
            try:
                informe = perfil.generar_informe_nutricional()
                if informe and 'plan' in informe:
                    meta_calorias = informe['plan'].get('calorias_dia', 2000)
            except: pass
            
            # Calcular calorías ya consumidas en ese día
            comidas_dia = ComidaDiaria.objects.filter(perfil=perfil, fecha=fecha)
            calorias_actuales = sum(c.calorias for c in comidas_dia)
            
            warnings = []
            recetas_objs = []
            calorias_a_agregar = 0
            
            # Primero cargamos las recetas para validar duplicados
            duplicates = []
            for rid in receta_ids:
                try:
                    r = Receta.objects.get(id=rid)
                    recetas_objs.append(r)
                    
                    # Check duplicado
                    if ComidaDiaria.objects.filter(perfil=perfil, fecha=fecha, nombre__iexact=r.titulo).exists():
                         duplicates.append(f"'{r.titulo}' ya está en tu plan del {fecha.strftime('%d/%m')}")
                    
                    calorias_a_agregar += r.calorias
                except Receta.DoesNotExist:
                    continue
            
            # Si hay duplicados y no forzamos, pedimos confirmación
            if duplicates and not force:
                return JsonResponse({
                    'success': False,
                    'requires_confirmation': True,
                    'message': "Detección de duplicados:\n" + "\n".join(duplicates) + "\n\n¿Deseas añadirla de todos modos?"
                })

            # Check límite de calorías (esto siempre alerta, no bloquea)
            if calorias_actuales + calorias_a_agregar > meta_calorias:
                exceso = (calorias_actuales + calorias_a_agregar) - meta_calorias
                warnings.append(f"¡Cuidado! Con esto superarás tu meta diaria por {exceso} kcal.")

            # Crear registros
            for receta in recetas_objs:
                ComidaDiaria.objects.create(
                    perfil=request.user.perfil,
                    nombre=receta.titulo,
                    calorias=receta.calorias,
                    proteinas=receta.proteinas,
                    carbos=receta.carbos,
                    grasas=receta.grasas,
                    hora=datetime.now().time(),
                    fecha=fecha,
                    categoria=receta.categoria if receta.categoria in ['desayuno', 'almuerzo', 'cena', 'snack', 'postre'] else 'almuerzo',
                    imagen_url=receta.imagen_url
                )
            
            # Mensaje motivacional aleatorio
            frases = [
                "¡Excelente elección! Tu cuerpo te lo agradecerá 🌱",
                "¡Sigue así! Cada comida saludable cuenta 💪",
                "¡Delicioso y nutritivo! Vas por buen camino 🚀",
                "¡Bien hecho! Cuidar de ti es lo más importante ❤️",
                "¡Añadido! Disfruta de tu comida sana 🥗"
            ]
            import random
            motivational_msg = random.choice(frases)
            
            return JsonResponse({
                'success': True,
                'warnings': warnings,
                'message': motivational_msg
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

@login_required
def quitar_del_calendario(request, comida_id):
    if request.method == 'POST':
        from .models import ComidaDiaria
        try:
            comida = ComidaDiaria.objects.get(id=comida_id, perfil=request.user.perfil)
            comida.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

@login_required
def obtener_calorias_dias(request):
    """API endpoint to get calorie data for the next 7 days"""
    try:
        from .models import ComidaDiaria
        perfil = request.user.perfil
        
        # Get user's calorie goal
        meta_cal = 2000
        try:
            informe = perfil.generar_informe_nutricional()
            meta_cal = informe['plan']['calorias_dia']
        except:
            pass
        
        # Calculate calories for next 7 days
        today = date.today()
        dias_data = []
        
        for i in range(7):
            fecha = today + timedelta(days=i)
            comidas_dia = ComidaDiaria.objects.filter(perfil=perfil, fecha=fecha)
            calorias_acumuladas = sum(c.calorias for c in comidas_dia)
            
            dias_data.append({
                'fecha': fecha.isoformat(),
                'calorias': calorias_acumuladas,
                'meta': meta_cal
            })
        
        return JsonResponse({
            'success': True,
            'dias': dias_data,
            'meta_calorias': meta_cal
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

