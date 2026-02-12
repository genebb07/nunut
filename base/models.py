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

class Perfil(models.Model):
    OPCIONES_GENERO = [('H', 'Hombre'), ('M', 'Mujer')]
    OPCIONES_SOMATOTIPO = [('ECTO', 'Ectomorfo'), ('MESO', 'Mesomorfo'), ('ENDO', 'Endomorfo')]
    OPCIONES_DIETA = [('OMNI', 'Omnívora'), ('VEGE', 'Vegetariana'), ('VEGA', 'Vegana'), ('PALEO', 'Paleo'), ('OTRO', 'Personalizada')]
    OPCIONES_COMIDAS = [('3G', '3 Comidas Grandes'), ('5P', '5 Comidas Pequeñas'), ('6+', 'Más de 6 snacks/comidas'), ('OMAD', 'Una comida al día')]
    OPCIONES_ACTIVIDAD = [('SEDE', 'Sedentario'), ('LIGE', 'Ligero'), ('MODE', 'Moderado'), ('INTE', 'Intenso'), ('ATLE', 'Atleta')]
    OBJETIVO_CHOICES = [('GANAR', 'Ganar masa muscular'), ('PERDER', 'Perder peso'), ('MANTENER', 'Mantenimiento/Salud')]
    
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    localidad = models.CharField(max_length=100, default="Venezuela", blank=True)
    genero = models.CharField(max_length=1, choices=OPCIONES_GENERO, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    altura = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    porcentaje_grasa = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    medida_cintura = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    medida_cuello = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    medida_cadera = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    somatotipo = models.CharField(max_length=4, choices=OPCIONES_SOMATOTIPO, blank=True)
    alergias = models.ManyToManyField(Alergia, blank=True)
    intolerancias = models.ManyToManyField(Intolerancia, blank=True)
    condiciones_medicas = models.ManyToManyField(CondicionMedica, blank=True)
    notas_medicas = models.TextField(blank=True)
    medicamentos = models.ManyToManyField(Medicamento, blank=True)
    tipo_dieta = models.CharField(max_length=5, choices=OPCIONES_DIETA, default='OMNI')
    gustos = models.ManyToManyField(Gustos, blank=True, related_name='gustos_perfiles')
    disgustos = models.ManyToManyField(Gustos, blank=True, related_name='disgustos_perfiles')
    frecuencia_comidas = models.CharField(max_length=4, choices=OPCIONES_COMIDAS, default='3G')
    objetivo = models.CharField(max_length=10, choices=OBJETIVO_CHOICES, blank=True)
    nivel_actividad = models.CharField(max_length=4, choices=OPCIONES_ACTIVIDAD, default='SEDE')
    horario_sueno = models.CharField(max_length=100, blank=True)
    foto_perfil = models.BinaryField(null=True, blank=True, editable=True)
    last_session_key = models.CharField(max_length=40, null=True, blank=True)
    modo_oscuro = models.BooleanField(default=False)
    OPCIONES_ROL = [('ADMIN', 'Administrador'), ('USER', 'Usuario'), ('GUEST', 'Invitado')]
    onboarding_completado = models.BooleanField(default=False)
    rol = models.CharField(max_length=5, choices=OPCIONES_ROL, default='USER')
    ultimo_cambio_nombre = models.DateTimeField(null=True, blank=True)
    
    @property
    def edad(self):
        if not self.fecha_nacimiento: return 30
        today = date.today()
        return today.year - self.fecha_nacimiento.year - ((today.month, today.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day))

    def get_foto_base64(self):
        if self.foto_perfil:
            import base64
            try:
                bytes_data = self.foto_perfil
                if isinstance(bytes_data, memoryview): bytes_data = bytes_data.tobytes()
                return base64.b64encode(bytes_data).decode('utf-8')
            except: return None
        return None

    def obtener_peso_actual(self):
        ultimo = self.historial_peso.first()
        return ultimo.peso if ultimo else 0

    def calcular_tmb(self):
        peso = self.obtener_peso_actual()
        if not (peso and self.altura and self.fecha_nacimiento): return 0
        if self.genero == 'H':
            return (10 * float(peso)) + (6.25 * float(self.altura)) - (5 * self.edad) + 5
        return (10 * float(peso)) + (6.25 * float(self.altura)) - (5 * self.edad) - 161
    
    def calcular_tdee(self):
        factores = {'SEDE': 1.2, 'LIGE': 1.375, 'MODE': 1.55, 'INTE': 1.725, 'ATLE': 1.9}
        return self.calcular_tmb() * factores.get(self.nivel_actividad, 1.2)

    def generar_informe_nutricional(self):
        peso = float(self.obtener_peso_actual() or 0)
        tmb_pura = float(self.calcular_tmb() or 0)
        mantenimiento = float(self.calcular_tdee() or 0)

        ajustes = {'PERDER': 0.85, 'GANAR': 1.10, 'MANTENER': 1.0}
        objetivo_key = self.objetivo if self.objetivo else 'MANTENER'
        calorias = mantenimiento * ajustes.get(objetivo_key, 1.0)

        prot = round(peso * 1.8) if peso > 0 else 0
        grasa = round(peso * 0.9) if peso > 0 else 0

        # Evitar operaciones inválidas si no hay datos
        try:
            carbs = round((calorias - (prot * 4) - (grasa * 9)) / 4) if calorias and (prot or grasa) else 0
        except Exception:
            carbs = 0

        return {
            'plan': {
                'calorias_dia': int(round(calorias)),
                'proteinas_g': int(round(prot)),
                'carbohidratos_g': int(round(carbs)),
                'grasas_g': int(round(grasa))
            },
            'datos_base': {
                'tmb_pura': int(round(tmb_pura)),
                'mantenimiento': int(round(mantenimiento)),
                'peso_actual': peso,
                'objetivo': objetivo_key
            }
        }

    def get_avatar_state(self):
        """Calcula el estado visual del avatar según métricas reales"""
        peso = float(self.obtener_peso_actual())
        altura_m = float(self.altura) / 100 if self.altura else 1.7
        imc = peso / (altura_m ** 2) if peso > 0 else 22
        
        # 1. Cuerpo (Basado en IMC y Somatotipo)
        cuerpo = "normal"
        if imc < 18.5: cuerpo = "flaco"
        elif imc > 27: cuerpo = "ancho"
        elif self.somatotipo == 'ECTO' and imc < 20: cuerpo = "flaco"
        elif self.somatotipo == 'ENDO' and imc > 25: cuerpo = "ancho"

        # 2. Ánimo (Basado en Sueño y Racha)
        # Obtenemos último registro de sueño
        ultimo_sueno = self.historial_sueno.first()
        racha = LoginStreak.calcular_racha(self)
        
        animo = "normal"
        if (ultimo_sueno and ultimo_sueno.calidad <= 2) or racha < 2:
            animo = "cansado"
        elif racha >= 3 and (ultimo_sueno and ultimo_sueno.calidad >= 4):
            animo = "energico"
        
        # 3. Hidratación (Hoy)
        registro_agua = self.registros_agua.filter(fecha=date.today()).first()
        hidratacion = "hidratado"
        if registro_agua and registro_agua.porcentaje < 50:
            hidratacion = "deshidratado"
        elif not registro_agua:
            hidratacion = "deshidratado" # Asumimos falta de registro como falta de agua

        # 4. Peso Tendencia (Comparando con el primer registro disponible)
        peso_inicial = self.historial_peso.last()
        tendencia = "estable"
        if peso_inicial and peso > 0:
            dif = peso - float(peso_inicial.peso)
            if dif > 0.5: tendencia = "subiendo"
            elif dif < -0.5: tendencia = "bajando"

        return {
            'cuerpo': cuerpo,
            'animo': animo,
            'hidratacion': hidratacion,
            'tendencia': tendencia,
            'imc': round(imc, 1)
        }


    def __str__(self):
        return f'Perfil de {self.usuario.username}'


    def calcular_porcentaje_grasa_marina(self):
        import math
        if not self.altura or not self.medida_cintura or not self.medida_cuello: return None
        a, ci, cu = float(self.altura), float(self.medida_cintura), float(self.medida_cuello)
        try:
            if self.genero == 'H':
                res = 495 / (1.0324 - 0.19077 * math.log10(ci - cu) + 0.15456 * math.log10(a)) - 450
            elif self.genero == 'M':
                if not self.medida_cadera: return None
                ca = float(self.medida_cadera)
                res = 495 / (1.29579 - 0.35004 * math.log10(ci + ca - cu) + 0.22100 * math.log10(a)) - 450
            else: return None
            return round(res, 1)
        except: return None

    def __str__(self): return f'Perfil de {self.usuario.username}'

@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created: Perfil.objects.create(usuario=instance)

@receiver(post_save, sender=User)
def guardar_perfil(sender, instance, **kwargs):
    if hasattr(instance, 'perfil'): instance.perfil.save()

class RegistroPeso(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='historial_peso')
    peso = models.DecimalField(max_digits=5, decimal_places=2)
    fecha = models.DateField(auto_now_add=True)
    class Meta: ordering = ['-fecha']

class RegistroSueno(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='historial_sueno')
    fecha = models.DateField(auto_now_add=True)
    hora_acostarse = models.TimeField()
    hora_levantarse = models.TimeField()
    calidad = models.IntegerField(choices=[(i, i) for i in range(1, 6)])

    @property
    def horas_totales(self):
        d = date.today()
        i = datetime.combine(d, self.hora_acostarse)
        f = datetime.combine(d, self.hora_levantarse)
        if f <= i: f += timedelta(days=1)
        return round((f - i).total_seconds() / 3600, 2)

class Alimento(models.Model):
    nombre = models.CharField(max_length=200, unique=True)
    calorias_100g = models.IntegerField(default=0)
    proteinas_100g = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    carbos_100g = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    grasas_100g = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    fibra_100g = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    
    # Micronutrientes (mg o mcg según estándar per 100g)
    vitamina_a_mg = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    vitamina_c_mg = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    hierro_mg = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    magnesio_mg = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    potasio_mg = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    zinc_mg = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    def __str__(self): return self.nombre

class Receta(models.Model):
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    imagen = models.ImageField(upload_to='recetas/', null=True, blank=True)
    imagen_url = models.URLField(max_length=500, blank=True, null=True)
    calorias = models.IntegerField()
    tiempo = models.CharField(max_length=50)
    tiempo_minutos = models.IntegerField(default=30)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=4.5)
    proteinas = models.IntegerField(default=0)
    carbos = models.IntegerField(default=0)
    grasas = models.IntegerField(default=0)
    tipo_dieta = models.CharField(max_length=10, choices=Perfil.OPCIONES_DIETA, default='OMNI')
    categoria = models.CharField(max_length=50, default='explorar')
    perfil_creador = models.ForeignKey(Perfil, on_delete=models.SET_NULL, null=True, blank=True, related_name='recetas_propias')
    presupuesto = models.CharField(max_length=20, default='Medio') # Económico, Medio, Caro
    dificultad = models.CharField(max_length=20, default='Media') # Fácil, Media, Difícil
    ingredientes_count = models.IntegerField(default=0)
    esta_aprobada = models.BooleanField(default=True)
    def __str__(self): return self.titulo

class RecetaFavorita(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='recetas_favoritas')
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE)
    fecha = models.DateField(auto_now_add=True)
    class Meta: unique_together = ('perfil', 'receta')

class CalificacionReceta(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='calificaciones_recetas')
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, related_name='calificaciones')
    puntuacion = models.PositiveSmallIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    fecha = models.DateTimeField(auto_now_add=True)
    class Meta: unique_together = ('perfil', 'receta')

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
    class Meta: unique_together = ('perfil', 'articulo')

class ComidaDiaria(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='comidas_diarias')
    nombre = models.CharField(max_length=200)
    calorias = models.IntegerField()
    proteinas = models.IntegerField()
    carbos = models.IntegerField()
    grasas = models.IntegerField()
    hora = models.TimeField()
    fecha = models.DateField(default=date.today)
    completada = models.BooleanField(default=True)
    categoria = models.CharField(max_length=50, choices=[('desayuno', 'Desayuno'), ('almuerzo', 'Almuerzo'), ('cena', 'Cena'), ('snack', 'Snack'), ('postre', 'Postre')], default='almuerzo')
    imagen_url = models.URLField(blank=True, null=True)
    def __str__(self): return f"{self.nombre} ({self.calorias} kcal)"

class LoginStreak(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='login_streaks')
    fecha = models.DateField(auto_now_add=True)
    class Meta: ordering = ['-fecha']; unique_together = ('perfil', 'fecha')

    @staticmethod
    def calcular_racha(perfil):
        from datetime import date, timedelta
        registros = LoginStreak.objects.filter(perfil=perfil).order_by('-fecha')
        if not registros.exists(): return 0
        racha = 0
        fecha_esperada = date.today()
        for registro in registros:
            if registro.fecha == fecha_esperada:
                racha += 1
                fecha_esperada -= timedelta(days=1)
            elif registro.fecha == fecha_esperada + timedelta(days=1):
                continue
            else: break
        return racha

class RegistroAgua(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='registros_agua')
    fecha = models.DateField(default=date.today)
    cantidad_vasos = models.IntegerField(default=0)
    meta_vasos = models.IntegerField(default=8)
    class Meta: unique_together = ('perfil', 'fecha'); ordering = ['-fecha']

    @property
    def litros(self): return round(self.cantidad_vasos * 0.25, 2)
    @property
    def meta_litros(self): return round(self.meta_vasos * 0.25, 2)
    @property
    def porcentaje(self):
        if self.meta_vasos <= 0: return 0
        return min(round((self.cantidad_vasos / self.meta_vasos) * 100), 100)
    def actualizar_meta(self):
        peso = self.perfil.obtener_peso_actual()
        if peso and peso > 0:
            self.meta_vasos = max(8, round(float(peso) * 0.14))
            self.save()

class Sugerencia(models.Model):
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('LEIDO', 'Leído'),
        ('REVISION', 'En Revisión'),
        ('IMPLEMENTADO', 'Implementado'),
        ('DESCARTADO', 'Descartado'),
        ('ARCHIVADO', 'Archivado'),
    ]
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='sugerencias')
    asunto = models.CharField(max_length=200, blank=True)
    mensaje = models.TextField()
    calificacion = models.PositiveSmallIntegerField(default=5, choices=[(i, str(i)) for i in range(1, 6)])
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=15, choices=ESTADOS, default='PENDIENTE')
    respuesta_admin = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Sugerencia de {self.perfil.usuario.username} - {self.estado}"

class LogActividad(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    accion = models.CharField(max_length=255)
    detalles = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.usuario.username if self.usuario else 'Sistema'} - {self.accion} ({self.fecha})"


class Logro(models.Model):
    TIPO_LOGRO = [
        ('RACHA', 'Racha de Sesión'),
        ('REGISTRO', 'Nutrición'),
        ('AGUA', 'Hidratación'),
        ('OTRO', 'Bienestar'),
    ]
    perfil = models.ForeignKey('Perfil', on_delete=models.CASCADE, related_name='logros')
    tipo = models.CharField(max_length=20, choices=TIPO_LOGRO)
    titulo = models.CharField(max_length=50) 
    descripcion = models.CharField(max_length=150)
    
    # Visuales para badges
    icono = models.CharField(max_length=50, default='stars')
    color_class = models.CharField(max_length=20, default='text-warning') # e.g. text-warning
    bg_class = models.CharField(max_length=20, default='bg-warning') # e.g. bg-warning
    
    fecha_obtenido = models.DateField(auto_now_add=True)
    
    class Meta:
        unique_together = ('perfil', 'titulo')

    def __str__(self): return f"{self.perfil} - {self.titulo}"

    @classmethod
    def verificar_y_otorgar(cls, perfil):
        """
        Lógica centralizada para desbloquear logros dinámicamente.
        """
        # 1. RACHA: 3 Días Seguidos
        racha = LoginStreak.calcular_racha(perfil)
        if racha >= 3:
            cls.objects.get_or_create(
                perfil=perfil, titulo='On Fire',
                defaults={
                    'tipo': 'RACHA',
                    'descripcion': '¡3 días seguidos entrando!',
                    'icono': 'local_fire_department',
                    'color_class': 'text-danger',
                    'bg_class': 'bg-danger'
                }
            )

        # 2. RACHA: 7 Días (Semana Perfecta)
        if racha >= 7:
            cls.objects.get_or_create(
                perfil=perfil, titulo='Semana Perfecta',
                defaults={
                    'tipo': 'RACHA',
                    'descripcion': '7 días de constancia pura.',
                    'icono': 'stars',
                    'color_class': 'text-warning',
                    'bg_class': 'bg-warning'
                }
            )

        # 3. AGUA: Meta del día cumplida
        hoy = date.today()
        agua_hoy = perfil.registros_agua.filter(fecha=hoy).first()
        if agua_hoy and agua_hoy.porcentaje >= 100:
            cls.objects.get_or_create(
                perfil=perfil, titulo='Hidratado',
                defaults={
                    'tipo': 'AGUA',
                    'descripcion': 'Cumpliste tu meta de agua hoy.',
                    'icono': 'water_full',
                    'color_class': 'text-primary',
                    'bg_class': 'bg-primary'
                }
            )
        
        # 4. DIETA: Vegano (Solo si aplica)
        if perfil.tipo_dieta == 'VEGA':
             cls.objects.get_or_create(
                perfil=perfil, titulo='Vegan Power',
                defaults={
                    'tipo': 'REGISTRO',
                    'descripcion': 'Comprometido con el estilo de vida vegano.',
                    'icono': 'eco',
                    'color_class': 'text-success',
                    'bg_class': 'bg-success'
                }
            )
        
        # 5. REGISTRO: Primera comida analizada
        if ComidaDiaria.objects.filter(perfil=perfil).exists():
             cls.objects.get_or_create(
                perfil=perfil, titulo='Primer Bocado',
                defaults={
                    'tipo': 'REGISTRO',
                    'descripcion': 'Registraste tu primera comida.',
                    'icono': 'restaurant',
                    'color_class': 'text-info',
                    'bg_class': 'bg-info'
                }
            )
