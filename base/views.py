from django.shortcuts import render, redirect
import requests
import random
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

def get_base_template(request):
    return 'partial.html' if request.headers.get('HX-Request') else 'base.html'

@login_required
def index(request):
    perfil = getattr(request.user, 'perfil', None)
    perfil_completo = False
    if perfil:
        perfil_completo = all([
            perfil.fecha_nacimiento, 
            perfil.obtener_peso_actual(), 
            perfil.altura, 
            perfil.genero,
            perfil.nivel_actividad,
            perfil.objetivo
        ])
    
    # Mostrar mensaje si el perfil está incompleto y no es invitado
    if not perfil_completo and request.user.username != 'invitado':
        messages.info(request, "📋 Completa tu perfil para obtener recomendaciones nutricionales personalizadas y seguimiento preciso de tus objetivos.")
    
    return render(request, 'base/index.html', {
        'base_template': get_base_template(request),
        'perfil_completo': perfil_completo,
        'es_invitado': request.user.username == 'invitado'
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
            proteinas="34g", carbos="5g", grasas="22g",
            tipo_dieta="KETO", categoria="explorar"
        )
        Receta.objects.create(
            titulo="Bowl de Quinua",
            descripcion="Un bowl energético lleno de fibra y proteínas vegetales.",
            imagen_url="https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=500&h=300&fit=crop",
            calorias=420, tiempo="15 min", rating=4.9,
            proteinas="12g", carbos="65g", grasas="14g",
            tipo_dieta="VEGE", categoria="explorar"
        )
        Receta.objects.create(
            titulo="Tostada de Aguacate",
            descripcion="Clásico desayuno saludable con pan integral y aguacate cremoso.",
            imagen_url="https://images.unsplash.com/photo-1525351484163-7529414344d8?w=500&h=300&fit=crop",
            calorias=280, tiempo="10 min", rating=4.7,
            proteinas="8g", carbos="30g", grasas="21g",
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
    url_spoon = "https://api.spoonacular.com/recipes/complexSearch"
    params_spoon = {
        'apiKey': api_key,
        'query': query_term,
        'number': 8,  # Reduced from 15 for faster loading
        'addRecipeInformation': 'true',
        'addRecipeNutrition': 'true'
    }

    # 3. API 2: TheMealDB (Respaldo gratuito, sin macros precisos)
    url_mealdb = f"https://www.themealdb.com/api/json/v1/1/search.php?s={query_term}"

    # Only make API calls if searching or if local DB is empty
    should_fetch_api = q or len(recetas) < 3
    
    if should_fetch_api:
        try:
            # --- FETCH SPOONACULAR ---
            response = requests.get(url_spoon, params=params_spoon, timeout=2)  # Reduced timeout
            if response.status_code == 200:
                data = response.json()
                for item in data.get('results', []):
                    # Extraer macros reales
                    nutrients = {n['name']: n for n in item.get('nutrition', {}).get('nutrients', [])}
                    cal = int(nutrients.get('Calories', {}).get('amount', 0))
                    
                    if not any(r.titulo.lower() == item['title'].lower() for r in recetas):
                        # Traducir título
                        titulo_es = item['title']
                        try:
                            titulo_es = translator.translate(item['title'])
                        except: pass

                        # Mapeo Categorías para Filtros
                        cat_smart = 'tendencia' # Default
                        # Prioridad de mapeo para filtros frontend
                        if item.get('vegan'): cat_smart = 'vegana'
                        elif item.get('ketogenic'): cat_smart = 'keto'
                        elif item.get('vegetarian'): cat_smart = 'vegana' # Simplificación para filtro

                        recetas.append(Receta(
                            id=item['id'] + 100000,
                            titulo=titulo_es,
                            descripcion=f"Sugerencia inteligente basada en tus gustos.",
                            imagen_url=item['image'],
                            calorias=cal,
                            tiempo=f"{item.get('readyInMinutes')} min",
                            rating=4.5,
                            proteinas=f"{int(nutrients.get('Protein', {}).get('amount', 0))}g",
                            carbos=f"{int(nutrients.get('Carbohydrates', {}).get('amount', 0))}g",
                            grasas=f"{int(nutrients.get('Fat', {}).get('amount', 0))}g",
                            tipo_dieta='KETO' if item.get('ketogenic') else 'VEGA' if item.get('vegan') else 'OMNI',
                            categoria=cat_smart
                        ))

            # --- FETCH THEMEALDB ---
            if len(recetas) < 6:  # Only if we need more recipes
                resp_db = requests.get(url_mealdb, timeout=2)  # Reduced timeout
                if resp_db.status_code == 200:
                    data_db = resp_db.json()
                    if data_db.get('meals'):
                        import random
                        for meal in data_db['meals'][:5]:  # Reduced from 10
                             if not any(r.titulo.lower() == meal['strMeal'].lower() for r in recetas):
                                es_carne = any(x in meal['strMeal'].lower() for x in ['beef', 'chicken', 'pork', 'lamb'])
                                prot = random.randint(25, 45) if es_carne else random.randint(5, 15)
                                cal_est = random.randint(300, 700)
                                
                                # Traducir título
                                titulo_es = meal['strMeal']
                                try:
                                    titulo_es = translator.translate(meal['strMeal'])
                                except: pass

                                # Mapeo de Categoría
                                str_cat = meal.get('strCategory', '').lower()
                                cat_meal = 'tendencia'
                                if str_cat in ['vegan', 'vegetarian']: cat_meal = 'vegana'
                                if 'keto' in str_cat or 'beef' in str_cat: cat_meal = 'keto' 
                                
                                recetas.append(Receta(
                                    id=int(meal['idMeal']) + 500000,
                                    titulo=titulo_es,
                                    descripcion=f"Clásico internacional de la categoría {meal.get('strCategory')}.",
                                    imagen_url=meal['strMealThumb'],
                                    calorias=cal_est,
                                    tiempo=f"{random.randint(15, 45)} min", 
                                    rating=round(random.uniform(4.0, 5.0), 1),
                                    proteinas=f"{prot}g",
                                    carbos=f"{random.randint(20, 60)}g",
                                    grasas=f"{random.randint(10, 30)}g",
                                    tipo_dieta='OMNI', 
                                    categoria=cat_meal
                                ))

        except Exception as e:
            print(f"Error APIs: {e}")
            pass

    # Favoritos
    favoritas_ids = []
    if request.user.is_authenticated and hasattr(request.user, 'perfil'):
        favoritas_ids = list(RecetaFavorita.objects.filter(perfil=request.user.perfil).values_list('receta_id', flat=True))

    return render(request, 'base/planes.html', {
        'base_template': get_base_template(request),
        'recetas': recetas,
        'favoritas_ids': favoritas_ids
    })

def diario(request):
    return render(request, 'base/diario.html', {'base_template': get_base_template(request)})

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
        form = EditarPerfilForm(request.POST, instance=request.user.perfil, user=request.user)
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
