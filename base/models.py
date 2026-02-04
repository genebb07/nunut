from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import date, datetime, timedelta

class Alergia(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.nombre

class Intolerancia(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.nombre

class CondicionMedica(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    def __str__(self): return self.nombre

class Medicamento(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.nombre

class Gustos(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    categoria = models.CharField(max_length=100, blank=True)
    def __str__(self):
        return self.nombre

# Modelo de Perfil de Usuario para extender la información predeterminada de Django
class Perfil(models.Model):
    # Opciones de selección
    OPCIONES_GENERO = [
        ('H', 'Hombre'),
        ('M', 'Mujer'),
    ]

    OPCIONES_SOMATOTIPO = [
        ('ECTO', 'Ectomorfo'),
        ('MESO', 'Mesomorfo'),
        ('ENDO', 'Endomorfo'),
    ]

    OPCIONES_DIETA = [
        ('OMNI', 'Omnívora (Todo)'),
        ('VEGE', 'Vegetariana'),
        ('VEGA', 'Vegana'),
        ('KETO', 'Keto / Cetogénica'),
        ('PALEO', 'Paleo'),
        ('OTRO', 'Otro / Personalizado'),
    ]

    OPCIONES_COMIDAS = [
        ('3G', '3 Comidas Grandes'),
        ('5P', '5 Comidas Pequeñas'),
        ('6+', 'Más de 6 snacks/comidas'),
        ('OMAD', 'Una comida al día'),
    ]

    OPCIONES_ACTIVIDAD = [
        ('SEDE', 'Sedentario (Poco o nada)'),
        ('LIGE', 'Ligero (1-3 días/sem)'),
        ('MODE', 'Moderado (3-5 días/sem)'),
        ('INTE', 'Intenso (6-7 días/sem)'),
        ('ATLE', 'Atleta / Muy intenso'),
    ]

    OBJETIVO_CHOICES = [
        ('GANAR', 'Ganar masa muscular'),
        ('PERDER', 'Perder peso'),
        ('MANTENER', 'Mantenimiento/Salud'),
    ]
    
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    localidad = models.CharField(max_length=100, default="Venezuela", blank=True)
    genero = models.CharField(max_length=1, choices=OPCIONES_GENERO, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    
    # Datos físicos
    altura = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Altura en cm")
    porcentaje_grasa = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="% de grasa")  
    somatotipo = models.CharField(max_length=4, choices=OPCIONES_SOMATOTIPO, blank=True)
    
    # Salud y medicina
    alergias = models.ManyToManyField(Alergia, blank=True)
    intolerancias = models.ManyToManyField(Intolerancia, blank=True)
    condiciones_medicas = models.ManyToManyField(CondicionMedica, blank=True)
    medicamentos = models.ManyToManyField(Medicamento, blank=True)
    
    # Nutrición y hábitos
    tipo_dieta = models.CharField(max_length=5, choices=OPCIONES_DIETA, default='OMNI')
    gustos = models.ManyToManyField(Gustos, blank=True, related_name='gustos_perfiles')
    frecuencia_comidas = models.CharField(max_length=4, choices=OPCIONES_COMIDAS, default='3G')
    
    # Metas y Estilo de Vida
    objetivo = models.CharField(max_length=10, choices=OBJETIVO_CHOICES, blank=True)
    nivel_actividad = models.CharField(max_length=4, choices=OPCIONES_ACTIVIDAD, default='SEDE')
    horario_sueno = models.CharField(max_length=100, blank=True)

    # Foto de perfil guardada como datos binarios en la BD
    foto_perfil = models.BinaryField(null=True, blank=True, editable=True)
    # Llave de sesión para control de sesión única
    last_session_key = models.CharField(max_length=40, null=True, blank=True)
    # Preferencia de modo oscuro
    modo_oscuro = models.BooleanField(default=False)
    onboarding_completado = models.BooleanField(default=False)
    
    @property
    def edad(self):
        """Calcula la edad automáticamente basada en la fecha actual"""
        today = date.today()
        return today.year - self.fecha_nacimiento.year - (
            (today.month, today.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )

    def get_foto_base64(self):
        """Convierte la foto binaria a base64 para mostrarla en HTML"""
        if self.foto_perfil:
            import base64
            try:
                # Asegurarse de que sean bytes (por si llega memoryview o str residual)
                if isinstance(self.foto_perfil, str):
                    return None # Datos antiguos incompatibles
                
                # Si es memoryview (común en algunos DB backends), obtener bytes
                bytes_data = self.foto_perfil
                if isinstance(bytes_data, memoryview):
                    bytes_data = bytes_data.tobytes()
                
                return base64.b64encode(bytes_data).decode('utf-8')
            except Exception:
                return None
        return None

    def obtener_peso_actual(self):
        ultimo_registro = self.historial_peso.first()
        return ultimo_registro.peso if ultimo_registro else 0

    def calcular_tmb(self):
        peso = self.obtener_peso_actual()
        if not (peso and self.altura and self.fecha_nacimiento):
            return 0

        # Si el usuario ingresó grasa corporal, usamos Katch-McArdle (Más pro)
        if self.porcentaje_grasa:
            masa_magra = float(peso) * (1 - (float(self.porcentaje_grasa) / 100))
            tmb = 370 + (21.6 * masa_magra)
        else:
            # Si NO la ingresó, usamos Mifflin-St Jeor (Estándar de oro actual)
            if self.genero == 'H':
                tmb = (10 * float(peso)) + (6.25 * float(self.altura)) - (5 * self.edad) + 5
            else:
                tmb = (10 * float(peso)) + (6.25 * float(self.altura)) - (5 * self.edad) - 161

        # Factor de actividad (Esto es clave para la precisión)
            factores = {'SEDE': 1.2, 'LIGE': 1.375, 'MODE': 1.55, 'INTE': 1.725, 'ATLE': 1.9}
        return tmb * factores.get(self.nivel_actividad, 1.2)

    def generar_informe_nutricional(self):
        peso = float(self.obtener_peso_actual())
        tmb_base = self.calcular_tmb()
        
        # 1. Gasto Energético Total
        factores = {'SEDE': 1.2, 'LIGE': 1.375, 'MODE': 1.55, 'INTE': 1.725, 'ATLE': 1.9}
        factor = factores.get(self.nivel_actividad, 1.2)
        mantenimiento = max(tmb_base * factor, 1)
        
        # 2. Ajuste por Objetivo (Déficit más conservador para evitar rebote)
        # Reducimos el déficit de -500 a -400 si es sedentario para dar margen a los macros
        ajustes = {'PERDER': -400, 'GANAR': 300, 'MANTENER': 0}
        calorias_objetivo = max(mantenimiento + ajustes.get(self.objetivo, 0), 1)
        
        # 3. Valla de Seguridad (TMB Pura)
        tmb_pura = max(tmb_base, 1)
        es_limite_seguridad = False
        if calorias_objetivo < tmb_pura:
            calorias_objetivo = tmb_pura
            es_limite_seguridad = True

        # 4. Cálculo de Macronutrientes DINÁMICO
        if self.objetivo == 'PERDER':
            prot_g = peso * 1.6  # Suficiente para preservar músculo sin saturar
            grasa_g = peso * 0.7 # Mínimo saludable para hormonas
        elif self.objetivo == 'GANAR':
            prot_g = peso * 2.0
            grasa_g = peso * 1.0
        else:
            prot_g = peso * 1.8
            grasa_g = peso * 0.9

        # 5. Carbohidratos: Ahora tendrán un suelo mínimo de seguridad
        calorias_restantes = calorias_objetivo - (prot_g * 4) - (grasa_g * 9)
        carbs_g = max(calorias_restantes / 4, 0)

        # Ajuste final: Si los carbs bajan de 100g en alguien sedentario, 
        # reequilibramos bajando un poco la grasa para no entrar en keto forzada
        if carbs_g < 100 and not self.objetivo == 'GANAR':
            # Quitamos un poco de grasa para dárselo a los carbs (1g grasa = 2.25g carbs)
            ajuste_grasa = min(15, grasa_g - 20) # No bajar de 20g de grasa
            if ajuste_grasa > 0:
                grasa_g -= ajuste_grasa
                carbs_g += (ajuste_grasa * 9) / 4

        # Evitar divisiones por cero en porcentajes
        total_cal = max(calorias_objetivo, 1)

        return {
            'datos_base': {
                'peso': peso,
                'tmb_pura': round(tmb_pura),
                'mantenimiento': round(mantenimiento),
                'factor_actividad': factor,
            },
            'plan': {
                'calorias_dia': round(calorias_objetivo),
                'proteinas_g': round(prot_g),
                'carbohidratos_g': round(carbs_g),
                'grasas_g': round(grasa_g),
            },
            'porcentajes': {
                'prot_pct': round((prot_g * 4 / total_cal) * 100),
                'carbs_pct': round((carbs_g * 4 / total_cal) * 100),
                'grasa_pct': round((grasa_g * 9 / total_cal) * 100),
            },
            'seguridad': es_limite_seguridad
        }


    def __str__(self):
        return f'Perfil de {self.usuario.username}'

# Señal para crear automáticamente un Perfil cuando se crea un Usuario
@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)

# Señal para guardar automáticamente el Perfil cuando se guarda el Usuario
@receiver(post_save, sender=User)
def guardar_perfil(sender, instance, **kwargs):
    # En casos raros el perfil podría no existir si se borró manualmente
    if hasattr(instance, 'perfil'):
        instance.perfil.save()

class RegistroPeso(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='historial_peso')
    peso = models.DecimalField(max_digits=5, decimal_places=2)
    fecha = models.DateField(auto_now_add=True) # Se graba solo al crearse

    class Meta:
        ordering = ['-fecha'] # El más reciente siempre arriba

    def __str__(self):
        return f"{self.perfil.usuario.username} - {self.peso}kg - {self.fecha}"

class RegistroSueno(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='historial_sueno')
    fecha = models.DateField(auto_now_add=True)
    hora_acostarse = models.TimeField()
    hora_levantarse = models.TimeField()
    calidad = models.IntegerField(choices=[(i, i) for i in range(1, 6)], help_text="Del 1 al 5")

    @property
    def horas_totales(self):
        # 1. Creamos una fecha ficticia (hoy) para poder operar con horas
        fecha_dummy = date.today()
        
        # 2. Combinamos la fecha con las horas de acostarse y levantarse
        inicio = datetime.combine(fecha_dummy, self.hora_acostarse)
        fin = datetime.combine(fecha_dummy, self.hora_levantarse)

        # 3. EL TRUCO: Si la hora de levantarse es menor que la de acostarse,
        # significa que el usuario se despertó al día siguiente.
        if fin <= inicio:
            fin += timedelta(days=1)

        # 4. Calculamos la diferencia
        diferencia = fin - inicio
        
        # 5. Retornamos el total en horas (con máximo 2 decimales)
        # 3600 segundos = 1 hora
        return round(diferencia.total_seconds() / 3600, 2)
class Receta(models.Model):
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    imagen_url = models.URLField(max_length=500)
    calorias = models.IntegerField()
    tiempo = models.CharField(max_length=50) # '25 min'
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=4.5)
    
    # Macros
    proteinas = models.CharField(max_length=50)
    carbos = models.CharField(max_length=50)
    grasas = models.CharField(max_length=50)
    
    tipo_dieta = models.CharField(max_length=10, choices=Perfil.OPCIONES_DIETA, default='OMNI')
    categoria = models.CharField(max_length=50, default='explorar') # explorar, desayuno...

    def __str__(self): return self.titulo

class RecetaFavorita(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='recetas_favoritas')
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)
    
    class Meta:
        unique_together = ('perfil', 'receta')

class Articulo(models.Model):
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    imagen_url = models.URLField(max_length=500)
    categoria = models.CharField(max_length=50)
    url = models.URLField(blank=True, max_length=500)
    
    def __str__(self): return self.titulo
    
class ArticuloGuardado(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='articulos_guardados')
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ('perfil', 'articulo')


class ComidaDiaria(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='comidas_diarias')
    receta = models.ForeignKey(Receta, on_delete=models.SET_NULL, null=True, blank=True)
    nombre = models.CharField(max_length=200)
    calorias = models.IntegerField()
    proteinas = models.IntegerField(default=0)
    carbos = models.IntegerField(default=0)
    grasas = models.IntegerField(default=0)
    fecha = models.DateField()
    hora = models.TimeField(null=True, blank=True)
    completada = models.BooleanField(default=False)
    imagen_url = models.URLField(max_length=500, blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} - {self.fecha} ({self.perfil.usuario.username})"
