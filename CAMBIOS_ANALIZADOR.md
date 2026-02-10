# Analizador Nutricional - Cambios Implementados

## Resumen
Se ha transformado completamente el módulo "Diario" en un "Analizador Nutricional" avanzado con capacidades de IA para analizar comidas mediante voz o texto en tiempo real.

## Cambios Realizados

### 1. URLs y Rutas
- **Archivo**: `base/urls.py`
- Renombrado: `diario/` → `analizador/`
- Agregado nuevo endpoint: `/api/analizar_comida_ia/` para el análisis de comidas con IA

### 2. Vistas (Backend)
- **Archivo**: `base/views.py`
- Renombrada función: `diario()` → `analizador()`
- Actualizado template: `diario.html` → `analizador.html`

### 3. Funciones de IA
- **Archivo**: `base/gemini_views.py`
- **Nueva función**: `analizar_comida_ia()`
  - Analiza descripciones de comidas (voz o texto)
  - Identifica ingredientes y cantidades
  - Calcula valores nutricionales completos
  - Proporciona desglose de macronutrientes
  - Incluye análisis de micronutrientes (vitaminas y minerales)

### 4. Navegación
- **Archivo**: `templates/base.html`
- Actualizado enlace de navegación: "Diario" → "Analizador"
- Actualizada ruta: `base:diario` → `base:analizador`

### 5. Template Principal
- **Archivo**: `templates/base/analizador.html` (NUEVO)

#### Características Principales:

**A. Interfaz de Entrada Dual**
- **Tab de Voz**:
  - Reconocimiento de voz en tiempo real (Web Speech API)
  - Transcripción en vivo
  - Indicador visual de escucha
  - Soporte para español (es-ES)
  
- **Tab de Texto**:
  - Área de texto grande para descripciones detalladas
  - Placeholder con ejemplo
  - Validación de entrada

**B. Análisis en Tiempo Real**
- Panel lateral con métricas actualizadas:
  - Calorías totales (card destacado con gradiente verde)
  - Proteínas con barra de progreso
  - Carbohidratos con barra de progreso
  - Grasas
  - Fibra
- Estado del análisis (ESPERANDO/ANALIZANDO/COMPLETADO/ERROR)

**C. Resultados Detallados**
1. **Distribución de Macronutrientes**:
   - Gráfico circular visual
   - Desglose porcentual de P/C/G
   
2. **Micronutrientes**:
   - 6 tarjetas con vitaminas y minerales
   - Porcentajes del valor diario recomendado
   - Iconos y colores distintivos
   - Barras de progreso individuales

3. **Ingredientes Detectados**:
   - Lista de ingredientes con cantidades
   - Iconos visuales
   - Diseño tipo tarjeta

**D. Integración con Calendario**
- Modal de selección de fecha
- Mini calendario de 7 días
- Indicadores visuales (Hoy, días de la semana)
- Confirmación antes de guardar
- Guardado en base de datos mediante API

## Funcionalidades Técnicas

### Frontend
- **Bootstrap 5** para layout responsive
- **Material Symbols** para iconografía
- **Web Speech API** para reconocimiento de voz
- **Fetch API** para comunicación con backend
- **Animaciones CSS** para transiciones suaves
- **Dark Mode** completamente soportado

### Backend
- **Google Gemini AI** para análisis nutricional
- **JSON responses** para comunicación asíncrona
- **CSRF protection** en todas las peticiones
- **Login required** para protección de rutas
- **Error handling** robusto

### Base de Datos
- Integración con modelo `ComidaDiaria` existente
- Guardado de análisis en calendario
- Asociación con perfil de usuario

## Flujo de Uso

1. **Usuario accede al Analizador**
   - Desde navegación principal → "Analizador"

2. **Describe su comida**
   - Opción A: Habla usando el micrófono
   - Opción B: Escribe en el área de texto

3. **Presiona "ANALIZAR COMIDA"**
   - Se envía petición a `/api/analizar_comida_ia/`
   - IA procesa la descripción
   - Retorna análisis completo en JSON

4. **Ve resultados en tiempo real**
   - Tarjetas de macronutrientes se actualizan
   - Aparece sección de análisis detallado
   - Scroll automático a resultados

5. **Añade al calendario**
   - Presiona "Añadir al Calendario"
   - Selecciona fecha en modal
   - Confirma y guarda en base de datos

## Mejoras de UX

- **Feedback visual inmediato**: Indicadores de estado en cada paso
- **Animaciones suaves**: Transiciones y efectos de aparición
- **Responsive design**: Funciona en móvil, tablet y desktop
- **Accesibilidad**: Textos descriptivos y estructura semántica
- **Toast notifications**: Mensajes de éxito/error elegantes
- **Loading states**: Spinners y estados de carga

## Compatibilidad

- **Navegadores con Web Speech API**:
  - Chrome/Edge (recomendado)
  - Safari (limitado)
  - Firefox (experimental)
  
- **Fallback**: Si no hay soporte de voz, tab de texto siempre disponible

## Notas Técnicas

- El paquete `google-generativeai` está deprecado pero funcional
- Se recomienda migrar a `google-genai` en el futuro
- La API de Gemini requiere key válida en `settings.py`
- El reconocimiento de voz requiere HTTPS en producción

## Archivos Modificados

1. `base/urls.py` - Rutas actualizadas
2. `base/views.py` - Vista renombrada
3. `base/gemini_views.py` - Nueva función de análisis
4. `templates/base.html` - Navegación actualizada
5. `templates/base/analizador.html` - Template completamente nuevo

## Testing Recomendado

1. Probar reconocimiento de voz en diferentes navegadores
2. Verificar análisis con descripciones variadas
3. Confirmar guardado en calendario
4. Validar responsive en móvil
5. Probar dark mode
6. Verificar manejo de errores (sin API key, sin conexión, etc.)
