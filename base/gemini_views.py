import os
import json
import google.generativeai as genai
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def generar_receta_ia(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return JsonResponse({'success': False, 'error': 'API Key de Gemini no configurada.'}, status=500)

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
    """Genera 3 recetas (Desayuno, Almuerzo, Cena) y las guarda automáticamente."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return JsonResponse({'success': False, 'error': 'API Key no configurada.'}, status=500)

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
        
        print(f"Using model for plan: {model_name}")
        model = genai.GenerativeModel(model_name)
        
        perfil = request.user.perfil
        dieta = perfil.get_tipo_dieta_display()
        objetivo = perfil.get_objetivo_display()
        
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
        Crea un plan diario de 3 comidas adaptadas al país del usuario (Desayuno, Almuerzo, Cena) adaptado a:
        
        PERFIL DEL USUARIO:
        - Ubicación: {localidad}
        - Edad: {edad} años
        - Peso: {peso} kg
        - Dieta: {dieta}
        - Objetivo: {objetivo}
        
        REQUERIMIENTOS NUTRICIONALES DIARIOS:
        - Calorías totales: {calorias_objetivo} kcal/día
        - Proteínas: {proteinas_objetivo}g/día
        - Carbohidratos: {carbos_objetivo}g/día
        - Grasas: {grasas_objetivo}g/día
        
        INSTRUCCIONES CRÍTICAS:
        1. Usa SOLO ingredientes comunes en el país del usuario
        2. Los platos deben ser TÍPICOS del país o adaptaciones saludables
        3. Evita ingredientes exóticos o difíciles de conseguir
        4. Distribuye calorías: Desayuno 30% ({int(calorias_objetivo*0.3)} kcal), Almuerzo 40% ({int(calorias_objetivo*0.4)} kcal), Cena 30% ({int(calorias_objetivo*0.3)} kcal)
        5. CADA receta DEBE tener al menos 5 ingredientes con cantidades exactas
        6. CADA receta DEBE tener pasos numerados y detallados
        
        Responde EXCLUSIVAMENTE con un JSON Array de 3 objetos con esta estructura EXACTA:
        [
            {{
                "titulo": "Nombre del plato",
                "tipo": "DESAYUNO",
                "tiempo": "15 min",
                "descripcion": "Descripción breve del plato",
                "calorias": {int(calorias_objetivo*0.3)},
                "proteinas": {int(proteinas_objetivo*0.3)},
                "carbos": {int(carbos_objetivo*0.3)},
                "grasas": {int(grasas_objetivo*0.3)},
                "pasos": "1. Paso detallado.\\n2. Otro paso.\\n3. Servir.",
                "ingredientes": ["Ingrediente 1 - 100g", "Ingrediente 2 - 50g", "Ingrediente 3 - 2 unidades", "Ingrediente 4 - al gusto", "Ingrediente 5 - 1 taza"]
            }},
            {{
                "titulo": "Plato para almuerzo",
                "tipo": "ALMUERZO",
                "tiempo": "30 min",
                "descripcion": "Descripción",
                "calorias": {int(calorias_objetivo*0.4)},
                "proteinas": {int(proteinas_objetivo*0.4)},
                "carbos": {int(carbos_objetivo*0.4)},
                "grasas": {int(grasas_objetivo*0.4)},
                "pasos": "1. Paso.\\n2. Paso.\\n3. Paso.",
                "ingredientes": ["Ingrediente 1", "Ingrediente 2", "Ingrediente 3", "Ingrediente 4", "Ingrediente 5"]
            }},
            {{
                "titulo": "Cena ligera",
                "tipo": "CENA",
                "tiempo": "20 min",
                "descripcion": "Descripción",
                "calorias": {int(calorias_objetivo*0.3)},
                "proteinas": {int(proteinas_objetivo*0.3)},
                "carbos": {int(carbos_objetivo*0.3)},
                "grasas": {int(grasas_objetivo*0.3)},
                "pasos": "1. Paso.\\n2. Paso.\\n3. Paso.",
                "ingredientes": ["Ingrediente 1", "Ingrediente 2", "Ingrediente 3", "Ingrediente 4", "Ingrediente 5"]
            }}
        ]
        
        IMPORTANTE: Cada objeto DEBE tener exactamente estos campos. Los ingredientes deben ser una lista de strings.
        """
        
        response = model.generate_content(prompt)
        text_resp = response.text.replace('```json', '').replace('```', '').strip()
        
        data_list = json.loads(text_resp)
        if not isinstance(data_list, list):
            raise ValueError("La respuesta no es una lista")

        from .models import Receta
        
        # Placeholder images mapped by type
        images = {
            "DESAYUNO": "https://images.unsplash.com/photo-1533089862017-5614a9570541?w=500&h=300&fit=crop",
            "ALMUERZO": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500&h=300&fit=crop",
            "CENA": "https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=500&h=300&fit=crop"
        }
        
        created_count = 0
        for item in data_list:
            tipo = item.get('tipo', 'ALMUERZO').upper()
            
            # Formatear descripción e ingredientes
            desc = item.get('descripcion', '')
            if 'ingredientes' in item:
                desc += "\n\nINGREDIENTES:\n" + "\n".join([f"- {ing}" for ing in item['ingredientes']])
            if 'pasos' in item:
                desc += "\n\nPREPARACIÓN:\n" + item['pasos']

            Receta.objects.create(
                titulo=item.get('titulo', 'Receta IA'),
                descripcion=desc,
                tiempo=item.get('tiempo', '30 min'),
                calorias=item.get('calorias', 500),
                proteinas=item.get('proteinas', 20),
                carbos=item.get('carbos', 50),
                grasas=item.get('grasas', 20),
                tipo_dieta=perfil.tipo_dieta,
                categoria=tipo.lower(),
                imagen_url=images.get(tipo, images["ALMUERZO"]),
                perfil_creador=perfil
            )
            created_count += 1
            
        return JsonResponse({'success': True, 'count': created_count})
        
    except Exception as e:
        print("Error Plan IA:", e)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
