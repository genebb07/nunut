import os
import google.generativeai as genai
from django.conf import settings

# Gemini API Key from settings


def obtener_respuesta_gemini(prompt, system_instruction=None):
    """
    Función utilitaria para obtener respuestas de Google Gemini.
    """
    GEMINI_API_KEY = getattr(settings, 'GEMINI_API_KEY', None)
    if not GEMINI_API_KEY:
        print("Error: No se encontró GEMINI_API_KEY en settings.py")
        return "¡Sigue esforzándote! Tu coach estará listo en un momento."
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        
        # Opciones de configuración del modelo
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 1024,
        }

        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=generation_config,
            system_instruction=system_instruction
        )

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error en Gemini API: {e}")
        return None

import random

def generar_recomendacion_premium(perfil, racha_dias, agua_hoy=None, sueno_ayer=None, nutricion_hoy=None, es_retorno=False):
    """
    Genera un mensaje ultra-personalizado y dinámico usando Gemini, considerando 
    contexto completo de salud, género, edad y estado de ánimo.
    """
    nombre = perfil.usuario.first_name or perfil.usuario.username
    objetivo = perfil.get_objetivo_display()
    
    # 1. Contexto Demográfico
    genero = "Mujer" if perfil.genero == 'M' else "Hombre" if perfil.genero == 'H' else "Neutro"
    edad = perfil.edad
    rango_edad = "Joven (<25)" if edad < 25 else "Adulto Mayor (>50)" if edad > 50 else "Adulto (25-50)"

    # 2. Selección de Tono Aleatorio (para variedad)
    tonos = [
        "Juguetón y divertido (usa humor)",
        "Amigable y cercano (como un mejor amigo)",
        "Motivador y energético (como un coach deportivo)",
        "Respetuoso y sereno (zen)",
        "Científico pero accesible (datos curiosos)",
        "Desafiante (reto directo)"
    ]
    tono_elegido = random.choice(tonos)
    
    # 3. Construcción del Prompt
    prompt = f"""
    Actúa como 'nunut', un coach de salud IA avanzado. Genera un mensaje MUY BREVE (máximo 2 oraciones) para el usuario.
    
    PERFIL DEL USUARIO:
    - Nombre: {nombre}
    - Género: {genero}
    - Rango de Edad: {rango_edad} (Adapta el lenguaje: más emojis/slang si es joven, más formal/respetuoso si es mayor).
    - Objetivo: {objetivo}
    - Estado de Racha: {racha_dias} días consecutivos.
    - Es usuario que vuelve tras abandono: {"SÍ" if es_retorno else "NO"} (Si es SÍ, sé acogedor, "qué bueno verte de nuevo").

    ESTADO ACTUAL (Dales feedback sobre esto si es relevante/crítico):
    """

    if agua_hoy:
        prompt += f"\n- Hidratación Hoy: {agua_hoy.cantidad_vasos}/{agua_hoy.meta_vasos} vasos ({agua_hoy.porcentaje}%). "
        if agua_hoy.porcentaje < 30: prompt += "(CRÍTICO: Muy bajo, recuérdale beber agua ya)."
    
    if sueno_ayer:
        prompt += f"\n- Sueño Anoche: {sueno_ayer.horas_totales} horas (Calidad: {sueno_ayer.calidad}/5). "
        if sueno_ayer.horas_totales < 6: prompt += "(Dormir poco afecta el metabolismo, menciónalo con cuidado)."
    
    if nutricion_hoy:
        cal_pct = nutricion_hoy.get('cal_pct', 0)
        prompt += f"\n- Calorías Hoy: {cal_pct}% del objetivo cumplido. "

    prompt += f"\n\nINSTRUCCIONES CLAVE:"
    prompt += f"\n1. TONO A USAR HOY: {tono_elegido} (¡Varía el estilo!)."
    prompt += "\n2. NO saludes siempre con 'Hola'. Sé creativo."
    prompt += "\n3. Si hay una 'marca personal' o hito (ej. 100% agua, 7 días racha), celébralo."
    prompt += "\n4. Si todo está bajo (agua, racha), sé empático, no regañes."
    prompt += "\n5. NO repitas frases genéricas. ¡Sorprende al usuario!"
    
    system_instruction = "Eres nunut, un compañero de vida saludable que se adapta camaleónicamente al usuario."

    # Intentar obtener respuesta (con fallback silencioso si falla API)
    try:
        respuesta = obtener_respuesta_gemini(prompt, system_instruction)
        return respuesta if respuesta else None
    except Exception:
        return None
