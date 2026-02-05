from django.shortcuts import render, redirect
import requests
import random
from datetime import date, datetime, timedelta
from deep_translator import GoogleTranslator
from django.urls import reverse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .forms import CustomAuthenticationForm, CustomUserCreationForm
from .forms import OnboardingForm
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password
from datetime import date, timedelta, datetime

def get_base_template(request):
    return 'partial.html' if request.headers.get('HX-Request') else 'base.html'

def obtener_mensaje_racha(dias):
    """Retorna un mensaje motivador basado en los días de racha"""
    if dias == 0:
        return "¡Comienza hoy! 🌱"
    if dias == 1:
        return "¡Primer día! Nuevo comienzo 🌱"
    
    mensajes_cortos = [
        "¡Estás en racha! 🔥",
        "¡No te detengas! 💪",
        "¡Excelente constancia! ✨",
        "¡Vas por buen camino! 🚀",
        "¡Sigue así, campeón! 👑"
    ]
    
    if dias >= 30:
        return f"¡{dias} DÍAS! ¡ERES LEYENDA! 👑"
    if dias >= 21:
        return f"¡{dias} Días! ¡Hábito de acero! 💎"
    if dias >= 14:
        return f"¡{dias} Días! ¡Imparable! 🚀"
    if dias >= 7:
        return f"¡Una semana completa! 🎉"
        
    return f"{dias} Días: {random.choice(mensajes_cortos)}"

def obtener_recomendacion_ia(perfil, racha_dias):
    """Genera un mensaje cálido y motivador del Coach IA nunut"""
    if not perfil or perfil.rol == 'GUEST':
        return "¡Hola! Soy nunut, tu coach personal. Regístrate para que pueda acompañarte en este viaje hacia tu mejor versión. Juntos haremos de tu salud una prioridad. ✨"
    
    nombre = perfil.usuario.first_name or perfil.usuario.username
    
    # Obtener hidratación de hoy
    from .models import RegistroAgua
    agua_hoy, _ = RegistroAgua.objects.get_or_create(perfil=perfil, fecha=date.today())
    
    if not perfil.onboarding_completado:
        return f"¡Qué alegría tenerte aquí, {nombre}! 🌱 Soy nunut, tu coach IA. Me encantaría conocerte mejor para sugerirte los mejores alimentos según tu cuerpo. ¿Terminamos tu perfil? ✨"

    # Intentar obtener recomendación Premium vía Gemini
    try:
        from .ai_service import generar_recomendacion_premium
        recomendacion_gemini = generar_recomendacion_premium(perfil, racha_dias, agua_hoy)
        if recomendacion_gemini:
            return recomendacion_gemini
    except Exception as e:
        print(f"Error cargando Gemini: {e}")

    # Fallback: Lógica Reglas-Base (Cálida)
    # Lógica de Racha
    if racha_dias == 1:
        msg_racha = "Hoy es el comienzo de algo grande. 🌱 Cada paso cuenta, y me hace muy feliz verte dar el primero hoy."
    elif racha_dias >= 7:
        msg_racha = f"Llevas {racha_dias} días con una constancia admirable. 🔥 Tu cuerpo ya está empezando a agradecer este nuevo ritmo."
    else:
        msg_racha = f"¡{racha_dias} días seguidos! 🔥 Mantener la constancia es la llave que abre todas las puertas de tu bienestar."

    # Lógica basada en objetivo
    objetivo_msg = ""
    if perfil.objetivo == 'PERDER':
        objetivo_msg = "He notado que estás enfocado en sentirte más ligero. Recuerda que no se trata de comer menos, sino de nutrirte mejor. 🥗"
    elif perfil.objetivo == 'GANAR':
        objetivo_msg = "Para esos músculos, la proteína y el descanso son tus mejores amigos hoy. ¡Vamos por esa meta! 💪"
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
    
    return random.choice(mensajes)

@login_required
def index(request):
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

    return render(request, 'base/index.html', {
        'base_template': get_base_template(request),
        'perfil_completo': perfil_completo,
        'es_invitado': es_invitado,
        'informe': informe,
        'racha_dias': racha_dias,
        'mensaje_racha': obtener_mensaje_racha(racha_dias),
        'recomendacion_ia': obtener_recomendacion_ia(perfil, racha_dias),
        'recetas_sugeridas': recetas_sugeridas,
        'favoritas_ids': favoritas_ids,
        'registro_agua': registro_agua,
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

def planes(request):
    seed_db()
    from .models import Receta, RecetaFavorita
    
    # 1. Búsqueda Local
    recetas = list(Receta.objects.all())
    q = request.GET.get('q')
    
    # query default para que siempre haya contenido (popular/saludable)
    query_term = q if q else "healthy"

    # Translator instance (cache to avoid repeatedly init)
    translator = GoogleTranslator(source='auto', target='es')

    # 2. API 1: Spoonacular (Data rica en macros)
    api_key = "40fcdd780cb940a5a6c55c79f3bf4857"
    
    # Siempre buscar recetas si hay menos de 20
    should_fetch_api = q or len(recetas) < 20
    
    if should_fetch_api:
        try:
            # Solo buscar lo necesario
            search_list = [query_term]
            if not q and len(recetas) < 10:
                search_list.append("healthy")

            for search_query in search_list:
                if len(recetas) >= 15: break
                
                url = f"https://api.spoonacular.com/recipes/complexSearch?apiKey={api_key}&query={search_query}&addRecipeInformation=true&number=10&addRecipeNutrition=true"
                try:
                    response = requests.get(url, timeout=3)
                    if response.status_code == 200:
                        data = response.json()
                        for item in data.get('results', []):
                            if not any(r.titulo.lower() == item['title'].lower() for r in recetas):
                                # Macros
                                nuts = {n['name']: n for n in item.get('nutrition', {}).get('nutrients', [])}
                                cal = int(nuts.get('Calories', {}).get('amount', 400))
                                prot = int(nuts.get('Protein', {}).get('amount', 20))
                                
                                # Simplified logic
                                cat = 'explorar'
                                if 'breakfast' in item.get('dishTypes', []): cat = 'desayuno'
                                
                                tipo_dieta = 'OMNI'
                                if item.get('ketogenic'): tipo_dieta = 'KETO'
                                elif item.get('vegan'): tipo_dieta = 'VEGA'
                                elif item.get('vegetarian'): tipo_dieta = 'VEGE'

                                recetas.append(Receta(
                                    id=item['id'] + 100000,
                                    titulo=item['title'],
                                    descripcion=f"Receta de {search_query} para tu plan saludable.",
                                    imagen_url=item['image'],
                                    calorias=cal,
                                    tiempo=f"{item.get('readyInMinutes', 30)} min",
                                    rating=round(4.0 + (item.get('aggregateLikes', 0) / 1000), 1),
                                    proteinas=prot,
                                    carbos=random.randint(20, 50),
                                    grasas=random.randint(10, 30),
                                    tipo_dieta=tipo_dieta,
                                    categoria=cat
                                ))
                except: continue

            # --- FALLBACK THEMEALDB SI SIGUE VACÍO ---
            if len(recetas) < 8:
                url_db = "https://www.themealdb.com/api/json/v1/1/search.php?s=chicken"
                try:
                    resp = requests.get(url_db, timeout=2)
                    if resp.status_code == 200:
                        meals = resp.json().get('meals', [])
                        for m in (meals[:8] if meals else []):
                            if not any(r.titulo.lower() == m['strMeal'].lower() for r in recetas):
                                recetas.append(Receta(
                                    id=int(m['idMeal']) + 500000,
                                    titulo=m['strMeal'],
                                    descripcion="Deliciosa opción internacional.",
                                    imagen_url=m['strMealThumb'],
                                    calorias=random.randint(400, 600),
                                    tiempo="30 min", rating=4.6,
                                    proteinas=30, carbos=20, grasas=10,
                                    tipo_dieta='OMNI', categoria='explorar'
                                 ))
                except: pass
        except Exception as e:
            print(f"Error General API: {e}")

    # Favoritos
    favoritas_ids = []
    if request.user.is_authenticated and hasattr(request.user, 'perfil'):
        favoritas_ids = list(RecetaFavorita.objects.filter(perfil=request.user.perfil).values_list('receta_id', flat=True))

    # Inyección de Receta Especial IA
    if not q or "ai" in q.lower() or "ia" in q.lower():
        recetas.insert(0, Receta(
            id=999999,
            titulo="Bowl Metabólico 'nunut AI'",
            descripcion="Optimizado por IA para mejorar tu metabolismo basal y control de glucosa.",
            imagen_url="https://images.unsplash.com/photo-1546069901-ba9599a7e63c?q=80&w=500",
            calorias=485,
            tiempo="15 min",
            rating=5.0,
            proteinas=32,
            carbos=14,
            grasas=22,
            tipo_dieta='KETO',
            categoria='tendencia'
        ))

    es_invitado = False
    if request.user.is_authenticated and hasattr(request.user, 'perfil'):
        es_invitado = request.user.perfil.rol == 'GUEST'

    return render(request, 'base/planes.html', {
        'base_template': get_base_template(request),
        'recetas': recetas,
        'favoritas_ids': favoritas_ids,
        'es_invitado': es_invitado
    })

@login_required
def diario(request):
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
        return render(request, 'base/diario.html', context)
    
    return render(request, 'base/diario.html', context)

def progreso(request):
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
    info_nutri = perfil.generar_informe_nutricional()
    tmb = info_nutri['datos_base']['tmb_pura']
    tdee = info_nutri['datos_base']['mantenimiento']
    calorias_obj = info_nutri['plan']['calorias_dia']
    
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

    context = {
        'base_template': get_base_template(request),
        'peso_actual': peso,
        'imc': imc,
        'imc_estado': imc_estado,
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

    return render(request, 'base/perfil.html', {
        'base_template': get_base_template(request),
        'form': form,
        'perfil': perfil,
        'altura_cm': altura_cm,
        'peso_actual': peso_actual,
        'imc': imc,
        'objetivo_display': objetivo_display,
        'nivel_actividad_display': nivel_actividad_display,
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
            'email': perfil.usuario.email,
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
    seed_db()
    from .models import Receta, Articulo
    
    # Stats
    total_users = User.objects.count()
    total_recipes = Receta.objects.count()
    total_articles = Articulo.objects.count()
    
    # Recent users
    recent_users = User.objects.order_by('-date_joined')[:5]
    
    # Recent content (Basic combination)
    recent_recipes = [{'titulo': r.titulo, 'type': 'recipe'} for r in Receta.objects.all().order_by('-id')[:3]]
    recent_articles = [{'titulo': a.titulo, 'type': 'article'} for a in Articulo.objects.all().order_by('-id')[:2]]
    recent_content = recent_recipes + recent_articles
    
    return render(request, 'admin/dashboard.html', {
        'base_template': get_base_template(request),
        'total_users': total_users,
        'total_recipes': total_recipes,
        'total_articles': total_articles,
        'recent_users': recent_users,
        'recent_content': recent_content
    })

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

            Receta.objects.create(
                perfil_creador=request.user.perfil,
                titulo=titulo,
                tipo_dieta=dieta,
                tiempo=tiempo,
                imagen_url=img_url if img_url else None,
                descripcion=final_desc,
                calorias=calorias,
                proteinas=proteinas,
                carbos=carbos,
                grasas=grasas,
                categoria="personalizada"
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

            if img_url:
                receta.imagen_url = img_url

            # Process Ingredients
            nombres = request.POST.getlist('ingredientes_nombres')
            cantidades = request.POST.getlist('ingredientes_cantidades')
            
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
