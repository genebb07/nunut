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
