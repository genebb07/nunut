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

def generar_recomendacion_premium(perfil, racha_dias, agua_hoy=None):
    """
    Genera una recomendación ultra-personalizada usando Gemini.
    """
    nombre = perfil.usuario.first_name or perfil.usuario.username
    objetivo = perfil.get_objetivo_display()
    dieta = perfil.get_tipo_dieta_display()
    actividad = perfil.get_nivel_actividad_display()
    
    prompt = f"Genera un mensaje motivador y cálido para {nombre}. "
    prompt += f"Su racha actual es de {racha_dias} días. "
    prompt += f"Su objetivo es {objetivo}, sigue una dieta {dieta} y su nivel de actividad es {actividad}. "
    
    if agua_hoy:
        prompt += f"Hoy ha consumido {agua_hoy.cantidad_vasos} vasos de agua de una meta de {agua_hoy.meta_vasos} ({agua_hoy.litros}L)."
        if agua_hoy.porcentaje < 50:
            prompt += " Por favor, anímale a beber más agua de forma muy amable."
        elif agua_hoy.porcentaje >= 100:
            prompt += " Felicítale por estar perfectamente hidratado."

    prompt += " El mensaje debe ser corto (máximo 3 frases), usar emojis y sonar como un coach experto y amigable."

    system_instruction = "Eres nunut, un coach de salud inteligente, empático y profesional. Tu tono es motivador pero basado en ciencia."
    
    respuesta = obtener_respuesta_gemini(prompt, system_instruction)
    return respuesta
