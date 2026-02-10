import os
import json
import google.generativeai as genai
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings

@login_required
def generar_receta_ia(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key:
        return JsonResponse({'success': False, 'error': 'API Key de Gemini no configurada en settings.py.'}, status=500)

    try:
        genai.configure(api_key=api_key)
        
        # Auto-detect available model
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except Exception as list_err:
            print(f"Could not list models: {list_err}")
        
        # Try models in order of preference
        model_name = None
        preferred_models = ['models/gemini-1.5-flash', 'models/gemini-pro', 'models/gemini-1.0-pro']
        
        for pref in preferred_models:
            if pref in available_models:
                model_name = pref
                break
        
        if not model_name and available_models:
            model_name = available_models[0]
        
        if not model_name:
            return JsonResponse({'success': False, 'error': 'No hay modelos disponibles para tu API key.'}, status=500)
        
        print(f"Using model: {model_name}")
        model = genai.GenerativeModel(model_name)
        
        perfil = request.user.perfil
        dieta = perfil.get_tipo_dieta_display()
        objetivo = perfil.get_objetivo_display()
        alergias = ", ".join([a.nombre for a in perfil.alergias.all()])
        gustos = ", ".join([g.nombre for g in perfil.gustos.all()])
        
        # Get nutritional info
        informe = None
        try:
            informe = perfil.generar_informe_nutricional()
        except:
            pass
        
        calorias_objetivo = informe['plan']['calorias_dia'] if informe else 2000
        proteinas_objetivo = informe['plan']['proteinas_g'] if informe else 150
        carbos_objetivo = informe['plan']['carbohidratos_g'] if informe else 200
        grasas_objetivo = informe['plan']['grasas_g'] if informe else 65
        
        edad = perfil.edad if perfil.fecha_nacimiento else "adulto"
        peso = perfil.obtener_peso_actual() or "peso promedio"
        localidad = perfil.localidad or "internacional"
        
        prompt = f"""
        Actúa como un chef nutricionista adaptado al país del usuario experto. Crea una receta única y detallada adaptada a este perfil:
        
        PERFIL DEL USUARIO:
        - Ubicación: {localidad}
        - Edad: {edad} años
        - Peso actual: {peso} kg
        - Dieta: {dieta}
        - Objetivo: {objetivo}
        - Alergias a evitar: {alergias if alergias else 'Ninguna'}
        - Gustos preferidos: {gustos if gustos else 'Variado'}
        
        REQUERIMIENTOS NUTRICIONALES DIARIOS:
        - Calorías totales: {calorias_objetivo} kcal/día
        - Proteínas: {proteinas_objetivo}g/día
        - Carbohidratos: {carbos_objetivo}g/día
        - Grasas: {grasas_objetivo}g/día
        
        INSTRUCCIONES CRÍTICAS:
        1. Usa SOLO ingredientes comunes y accesibles en el país del usuario
        2. La receta debe ser un plato TÍPICO o COMÚN del país del usuario o cosas accesibles para la localidad del usuario
        3. Evita ingredientes exóticos, caros o difíciles de conseguir
        4. La receta debe representar UNA COMIDA completa, ya sea desayuno, almuerzo o cena, adaptada al perfil del usuario
        5. Ajusta las calorías para ~{int(calorias_objetivo/3)} kcal (1/3 del total diario)
        6. DEBES incluir una lista DETALLADA de ingredientes con cantidades exactas
        7. DEBES incluir pasos de preparación COMPLETOS y numerados
        
        Responde EXCLUSIVAMENTE con un objeto JSON válido (sin texto extra, sin markdown) con esta estructura EXACTA:
        {{
            "titulo": "Nombre del plato",
            "descripcion": "Descripción breve de 2 líneas explicando por qué es ideal para este perfil.",
            "tiempo": "ej. 25 min",
            "calorias": {int(calorias_objetivo/3)},
            "proteinas": {int(proteinas_objetivo/3)},
            "carbos": {int(carbos_objetivo/3)},
            "grasas": {int(grasas_objetivo/3)},
            "ingredientes": [
                {{"nombre": "Harina de maíz precocida", "cantidad": "200g"}},
                {{"nombre": "Pollo desmenuzado", "cantidad": "150g"}},
                {{"nombre": "Aguacate", "cantidad": "1 unidad"}}
            ],
            "pasos": "1. Preparar la masa de arepa con harina y agua.\\n2. Formar las arepas y cocinar en budare.\\n3. Rellenar con pollo y aguacate.\\n4. Servir caliente."
        }}
        
        IMPORTANTE: La lista de ingredientes DEBE tener todos los ingredientes con cantidades específicas.
        Los pasos DEBEN estar numerados y ser claros y detallados.
        """
        
        response = model.generate_content(prompt)
        text_resp = response.text.replace('```json', '').replace('```', '').strip()
        
        try:
            data = json.loads(text_resp)
            
            # Build complete description with ingredients and steps
            full_desc = data.get('descripcion', '')
            
            # Add ingredients section
            if 'ingredientes' in data and data['ingredientes']:
                full_desc += "\n\nINGREDIENTES:\n"
                for ing in data['ingredientes']:
                    nombre = ing.get('nombre', '') if isinstance(ing, dict) else str(ing)
                    cantidad = ing.get('cantidad', '') if isinstance(ing, dict) else ''
                    if cantidad:
                        full_desc += f"- {nombre} ({cantidad})\n"
                    else:
                        full_desc += f"- {nombre}\n"
            
            # Add preparation steps
            if 'pasos' in data:
                full_desc += "\nPREPARACIÓN:\n" + data['pasos']
            
            # Asegurar que los datos del JSON coincidan con lo que espera el frontend
            final_data = {
                'titulo': data.get('titulo'),
                'descripcion': full_desc,
                'tiempo': data.get('tiempo'),
                'calorias': data.get('calorias'),
                'proteinas': data.get('proteinas'),
                'carbos': data.get('carbos'),
                'grasas': data.get('grasas'),
                'ingredientes': data.get('ingredientes', []),
                'imagen_url': 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500&h=300&fit=crop'
            }
            
            return JsonResponse({'success': True, 'receta': final_data})
        except json.JSONDecodeError:
            print("Error decoding JSON:", text_resp)
            return JsonResponse({'success': False, 'error': 'La IA no devolvió un formato válido. Intenta de nuevo.'}, status=500)

    except Exception as e:
        print("Gemini Error:", e)
        return JsonResponse({'success': False, 'error': f'Error de Gemini: {str(e)}'}, status=500)

@login_required
def generar_plan_ia(request):
    """Genera un plan diario de comidas adaptado al perfil completo del usuario."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key:
        return JsonResponse({'success': False, 'error': 'API Key no configurada en settings.py.'}, status=500)

    try:
        genai.configure(api_key=api_key)
        
        # Auto-detect available model
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except Exception as list_err:
            print(f"Could not list models: {list_err}")
        
        # Prefer flash for speed
        model_name = next((m for m in ['models/gemini-1.5-flash', 'models/gemini-pro'] if m in available_models), available_models[0] if available_models else None)
        
        if not model_name:
            return JsonResponse({'success': False, 'error': 'No hay modelos disponibles.'}, status=500)
        
        model = genai.GenerativeModel(model_name)
        
        perfil = request.user.perfil
        informe = perfil.generar_informe_nutricional()
        
        # Nutritional data
        plan_cal = informe['plan']['calorias_dia']
        plan_prot = informe['plan']['proteinas_g']
        plan_carb = informe['plan']['carbohidratos_g']
        plan_gras = informe['plan']['grasas_g']
        tdee = informe['datos_base']['mantenimiento']
        imc = round(float(perfil.obtener_peso_actual()) / ((float(perfil.altura)/100)**2), 1) if perfil.altura and perfil.obtener_peso_actual() else 0
        
        # Preferences and restrictions
        dieta = perfil.get_tipo_dieta_display() or "Omnívora"
        objetivo = perfil.get_objetivo_display() or "Mantener"
        localidad = perfil.localidad or "Chile/Venezuela"
        alergias = ", ".join([a.nombre for a in perfil.alergias.all()])
        gustos = ", ".join([g.nombre for g in perfil.gustos.all()])
        disgustos = ", ".join([d.nombre for d in perfil.disgustos.all()])
        medico = ", ".join([c.nombre for c in perfil.condiciones_medicas.all()])
        if perfil.notas_medicas:
            medico += f". Notas: {perfil.notas_medicas}"
        
        # Meal Frequency
        freq_map = {'3G': 3, '5P': 5, '6+': 6, 'OMAD': 1}
        n_comidas = freq_map.get(perfil.frecuencia_comidas, 3)
        
        prompt = f"""
        Actúa como un Nutricionista Jefe experto en comida de {localidad}. Crea un plan diario de exactamente {n_comidas} comidas para este usuario:
        
        DATOS DEL USUARIO:
        - Ubicación: {localidad}
        - IMC: {imc} (Estado: {objetivo})
        - Dieta: {dieta}
        - Alergias/Restricciones: {alergias if alergias else 'Ninguna'}
        - Condiciones Médicas: {medico if medico else 'Ninguna'}
        - Gustos: {gustos if gustos else 'Variado'}
        - Disgustos (EVITAR COMPLETAMENTE): {disgustos if disgustos else 'Ninguno'}
        
        REQUERIMIENTOS DIARIOS (TOTAL):
        - Calorías: {plan_cal} kcal (TDEE: {tdee})
        - Proteína: {plan_prot}g | Carbos: {plan_carb}g | Grasas: {plan_gras}g
        
        INSTRUCCIONES:
        1. Genera EXACTAMENTE {n_comidas} comidas que sumen aproximadamentne los totales anteriores.
        2. Para cada receta, asigna un "presupuesto" (Económico, Medio, Caro) y una "dificultad" (Fácil, Media, Difícil).
        3. Usa ingredientes locales y reales de {localidad}.
        4. No hables, responde exclusivamente con el JSON.
        
        Responde EXCLUSIVAMENTE con un JSON Array de objetos con esta estructura:
        [
            {{
                "titulo": "Nombre del plato",
                "tipo": "DESAYUNO/ALMUERZO/CENA/SNACK",
                "descripcion": "Descripción breve",
                "tiempo": "20 min",
                "calorias": 0,
                "proteinas": 0,
                "carbos": 0,
                "grasas": 0,
                "presupuesto": "Economico/Medio/Caro",
                "dificultad": "Facil/Media/Dificil",
                "ingredientes": ["ingrediente 1", "ingrediente 2"],
                "pasos": "1. Paso 1.\\n2. Paso 2."
            }}
        ]
        """
        
        safety = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = model.generate_content(prompt, safety_settings=safety)
        text_resp = response.text.strip()
        print(f"DEBUG Plan IA Raw Resp: {text_resp[:200]}...") # Log first 200 chars

        # Robust JSON extraction
        try:
            # Look for the first '[' and last ']'
            start_index = text_resp.find('[')
            end_index = text_resp.rfind(']') + 1
            if start_index == -1 or end_index == 0:
                raise ValueError("No se encontró un JSON válido en la respuesta de la IA")
            
            json_str = text_resp[start_index:end_index]
            data_list = json.loads(json_str)
        except Exception as parse_err:
            print(f"Error parseando JSON IA: {parse_err}")
            print(f"Respuesta completa fallida: {text_resp}")
            return JsonResponse({'success': False, 'error': f"Error en formato de IA: {str(parse_err)}"}, status=500)

        from .models import Receta
        
        images = {
            "DESAYUNO": "https://images.unsplash.com/photo-1533089862017-5614a9570541?w=500",
            "ALMUERZO": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500",
            "CENA": "https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=500",
            "SNACK": "https://images.unsplash.com/photo-1590080875515-8a3a8dc339c?w=500"
        }
        
        result_plan = []
        for item in data_list:
            tipo = item.get('tipo', 'ALMUERZO').upper()
            
            # Persistir en BD
            desc_full = item.get('descripcion', '')
            if 'ingredientes' in item:
                desc_full += "\n\nINGREDIENTES:\n" + "\n".join([f"- {ing}" for ing in item['ingredientes']])
            if 'pasos' in item:
                desc_full += "\n\nPREPARACIÓN:\n" + item['pasos']

            receta = Receta.objects.create(
                titulo=item.get('titulo', 'Receta IA'),
                descripcion=desc_full,
                tiempo=item.get('tiempo', '30 min'),
                calorias=item.get('calorias', 0),
                proteinas=item.get('proteinas', 0),
                carbos=item.get('carbos', 0),
                grasas=item.get('grasas', 0),
                presupuesto=item.get('presupuesto', 'Medio'),
                dificultad=item.get('dificultad', 'Media'),
                tipo_dieta=perfil.tipo_dieta,
                categoria=tipo.lower(),
                imagen_url=images.get(tipo, images["ALMUERZO"]),
                perfil_creador=perfil
            )
            # Data for frontend
            item['id'] = receta.id
            item['imagen_url'] = receta.imagen_url
            result_plan.append(item)
            
        return JsonResponse({
            'success': True, 
            'plan': result_plan,
            'metas': {
                'calorias_dia': plan_cal,
                'proteinas_g': plan_prot,
                'carbohidratos_g': plan_carb,
                'grasas_g': plan_gras
            }
        })
        
    except Exception as e:
        print("Error Plan IA:", e)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def analizar_comida_ia(request):
    """Analiza una comida usando NLP local + Base de Datos, con fallback a Gemini."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        descripcion_comida = data.get('descripcion', '').strip()
        
        if not descripcion_comida:
            return JsonResponse({'success': False, 'error': 'Descripción vacía'}, status=400)

        # --- 1. INTENTO DE ANÁLISIS NLP LOCAL ---
        from .models import Alimento
        import re

        # Regex para identificar cantidades y alimentos
        # Patrones: "100g de pollo", "200 gr arroz", "1 taza de leche", "pollo 100g"
        # Simplificación: Buscar Numero + Unidad (opcional) + Texto Restante
        
        # Separadores de "complementos"
        separadores = r'(?: y | con | \+ | , | más | tras | acompando de )'
        partes = re.split(separadores, descripcion_comida, flags=re.IGNORECASE)
        
        ingredientes_detectados = []
        macros_totales = {'calorias': 0, 'proteinas': 0, 'carbos': 0, 'grasas': 0, 'fibra': 0}
        micro_totales = {'vitamina_a': 0, 'vitamina_c': 0, 'hierro': 0, 'magnesio': 0, 'potasio': 0, 'zinc': 0}
        
        found_any = False
        
        for parte in partes:
            parte = parte.strip()
            if not parte: continue
            
            # Extraer cantidad
            cantidad = 100 # Default 100g
            match_cant = re.search(r'(\d+(?:[.,]\d+)?)', parte)
            if match_cant:
                try:
                    cantidad = float(match_cant.group(1).replace(',', '.'))
                except: pass
            
            # Limpiar nombre (quitar numeros, unidades comunes, stopwords)
            nombre_limpio = re.sub(r'\d+(?:[.,]\d+)?', '', parte) # Quitar numeros
            nombre_limpio = re.sub(r'\b(g|gr|gramos|ml|litros|kg|kilo|kilos|taza|tazas|cuchara|cucharadas|unidad|unidades|pieza|piezas)\b', '', nombre_limpio, flags=re.IGNORECASE)
            nombre_limpio = re.sub(r'\b(de|del|un|una|el|la|los|las)\b', '', nombre_limpio, flags=re.IGNORECASE)
            nombre_limpio = nombre_limpio.strip()
            
            # Buscar en BD (Fuzzy search simple: buscando keywords)
            # Primero intento exacto, luego contains
            alimento = Alimento.objects.filter(nombre__iexact=nombre_limpio).first()
            if not alimento:
                alimento = Alimento.objects.filter(nombre__icontains=nombre_limpio).first()
                # Fallback: si string es "pechuga de pollo", y tenemos "Pollo", intentamos buscar palabras clave
                if not alimento and len(nombre_limpio) > 3:
                    for palabra in nombre_limpio.split():
                        if len(palabra) > 3:
                            alimento = Alimento.objects.filter(nombre__icontains=palabra).first()
                            if alimento: break
            
            if alimento:
                found_any = True
                factor = cantidad / 100.0
                
                # Calcular macros
                cal = int(alimento.calorias_100g * factor)
                prot = round(float(alimento.proteinas_100g) * factor, 1)
                carbs = round(float(alimento.carbos_100g) * factor, 1)
                grasas = round(float(alimento.grasas_100g) * factor, 1)
                fibra = round(float(alimento.fibra_100g) * factor, 1)
                
                macros_totales['calorias'] += cal
                macros_totales['proteinas'] += prot
                macros_totales['carbos'] += carbs
                macros_totales['grasas'] += grasas
                macros_totales['fibra'] += fibra
                
                # Micronutrientes
                micro_totales['vitamina_a'] += float(alimento.vitamina_a_mg) * factor
                micro_totales['vitamina_c'] += float(alimento.vitamina_c_mg) * factor
                micro_totales['hierro'] += float(alimento.hierro_mg) * factor
                micro_totales['magnesio'] += float(alimento.magnesio_mg) * factor
                micro_totales['potasio'] += float(alimento.potasio_mg) * factor
                micro_totales['zinc'] += float(alimento.zinc_mg) * factor
                
                ingredientes_detectados.append({
                    "nombre": alimento.nombre,
                    "cantidad": f"{int(cantidad) if cantidad.is_integer() else cantidad}g"
                })

        # Si encontramos ALGO en la BD local, devolvemos eso (Prioridad Local)
        # Ojo: Si el usuario pone "100g pollo y 100g vibranium", solo detectará pollo.
        # Para ser robustos, si detectamos CERO ingredientes, usamos Gemini.
        # Si detectamos al menos uno, asumimos éxito parcial y devolvemos eso (o podríamos mezclar, pero complicado).
        
        if found_any and len(ingredientes_detectados) > 0:
            return JsonResponse({
                'success': True,
                'analisis': {
                    "titulo": descripcion_comida.capitalize(),
                    "descripcion": f"Análisis basado en base de datos local para: {', '.join([i['nombre'] for i in ingredientes_detectados])}",
                    "calorias": int(macros_totales['calorias']),
                    "proteinas": int(macros_totales['proteinas']),
                    "carbohidratos": int(macros_totales['carbos']),
                    "grasas": int(macros_totales['grasas']),
                    "fibra": int(macros_totales['fibra']),
                    "ingredientes": ingredientes_detectados,
                    "micronutrientes": {k: int(v) for k, v in micro_totales.items()}
                }
            })

        # --- 2. FALLBACK A GEMINI SI NO HAY MATCH LOCAL ---
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
             return JsonResponse({'success': False, 'error': 'No se encontraron alimentos en la BD y no hay API Key.'}, status=404)

        genai.configure(api_key=api_key)
        
        # Auto-detect available model
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except: pass
        
        model_name = next((m for m in ['models/gemini-1.5-flash', 'models/gemini-pro'] if m in available_models), available_models[0] if available_models else None)
        
        if not model_name:
            return JsonResponse({'success': False, 'error': 'No hay modelos disponibles.'}, status=500)
        
        model = genai.GenerativeModel(model_name)
        
        prompt = f"""
        Eres un nutricionista experto. Analiza la siguiente descripción de comida y proporciona un análisis nutricional detallado.
        
        DESCRIPCIÓN DE LA COMIDA:
        "{descripcion_comida}"
        
        INSTRUCCIONES:
        1. Identifica todos los ingredientes principales
        2. Estima las cantidades aproximadas
        3. Calcula los valores nutricionales totales
        4. Proporciona un desglose de macronutrientes
        5. Incluye micronutrientes relevantes (vitaminas y minerales)
        
        Responde EXCLUSIVAMENTE con un objeto JSON válido (sin texto extra, sin markdown) con esta estructura EXACTA:
        {{
            "titulo": "Nombre descriptivo del plato",
            "descripcion": "Descripción breve del análisis",
            "calorias": 0,
            "proteinas": 0,
            "carbohidratos": 0,
            "grasas": 0,
            "fibra": 0,
            "ingredientes": [
                {{"nombre": "Ingrediente 1", "cantidad": "100g"}},
                {{"nombre": "Ingrediente 2", "cantidad": "50g"}}
            ],
            "micronutrientes": {{
                "vitamina_a": 120,
                "vitamina_c": 88,
                "hierro": 24,
                "magnesio": 45,
                "potasio": 32,
                "zinc": 15
            }}
        }}
        """
        
        response = model.generate_content(prompt)
        text_resp = response.text.replace('```json', '').replace('```', '').strip()
        analysis_data = json.loads(text_resp)
        
        return JsonResponse({
            'success': True,
            'analisis': analysis_data
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    except Exception as e:
        print("Error Analizar Comida:", e)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def transcribir_audio(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    if not request.FILES.get('audio_file'):
        return JsonResponse({'success': False, 'error': 'No se recibió archivo de audio'}, status=400)
    
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    import os
    import time
    import traceback
    
    audio_file = request.FILES['audio_file']
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    
    if not api_key:
        return JsonResponse({'success': False, 'error': 'API Key no configurada'}, status=500)

    # 1. Guardar temporalmente usando el storage de Django (más robusto)
    # Generar un nombre único para evitar colisiones
    temp_filename = f"audio_{int(time.time())}_{audio_file.name}"
    path = default_storage.save(f'tmp/{temp_filename}', ContentFile(audio_file.read()))
    full_path = default_storage.path(path)
    
    try:
        genai.configure(api_key=api_key)
        
        # 2. Subir a Gemini
        uploaded_file = genai.upload_file(full_path)
        
        # 3. Esperar procesamiento (max 20s)
        attempts = 0
        while uploaded_file.state.name == "PROCESSING" and attempts < 20:
            time.sleep(1)
            uploaded_file = genai.get_file(uploaded_file.name)
            attempts += 1
            
        if uploaded_file.state.name == "FAILED":
            raise Exception("El procesamiento del audio falló en los servidores de Google.")
            
        # 4. Transcribir
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        prompt = "Actúa como un transcriptor experto. Transcribe este audio exactamente palabra por palabra en español. Si solo hay silencio o ruido, responde 'SILENCIO'. No añadas introducciones."
        
        response = model.generate_content([prompt, uploaded_file])
        transcription = response.text.strip()
        
        if "SILENCIO" in transcription.upper():
            transcription = ""
            
        return JsonResponse({'success': True, 'text': transcription})

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': f"Error en la IA: {str(e)}"}, status=500)
        
    finally:
        # 5. Limpiar siempre
        try:
            if default_storage.exists(path):
                default_storage.delete(path)
        except: pass
        try:
            if 'uploaded_file' in locals():
                genai.delete_file(uploaded_file.name)
        except: pass
