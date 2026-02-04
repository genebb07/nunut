from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from .models import Perfil, Alergia, Gustos
from datetime import date

# Formulario personalizado de Autenticación (Login)
class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Añadir clases CSS y placeholders a los campos
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-input',
                'placeholder': field.label
            })
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            # Permitir login con correo electrónico
            if '@' in username:
                try:
                    user = User.objects.get(email=username)
                    username = user.username
                    self.cleaned_data['username'] = username
                except User.DoesNotExist:
                    # Dejar que la autenticación falle normalmente
                    pass
        
        return super().clean()

# Formulario personalizado de Creación de Usuario (Registro)
class CustomUserCreationForm(UserCreationForm):
    # Campos adicionales requeridos
    first_name = forms.CharField(label="Nombre", max_length=30)
    last_name = forms.CharField(label="Apellido", max_length=30)
    email = forms.EmailField(label="Correo Electrónico", required=True)
    fecha_nacimiento = forms.DateField(label="Fecha de Nacimiento", widget=forms.DateInput(attrs={'type': 'date'}))
    genero = forms.ChoiceField(label="Género", choices=Perfil.OPCIONES_GENERO)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'fecha_nacimiento', 'genero', 'email', 'username')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Estilizar campos con clases CSS
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-input',
                'placeholder': field.label
            })

    # Validación personalizada de correo único
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo ya está registrado.")
        return email

    # Validación de Nombres (Solo letras)
    def clean_first_name(self):
        name = self.cleaned_data.get('first_name')
        if not name.replace(' ', '').isalpha():
            raise forms.ValidationError("El nombre no puede contener números ni símbolos.")
        return name

    def clean_last_name(self):
        name = self.cleaned_data.get('last_name')
        if not name.replace(' ', '').isalpha():
            raise forms.ValidationError("El apellido no puede contener números ni símbolos.")
        return name

    # Validación de mayoría de edad (18 años)
    def clean_fecha_nacimiento(self):
        dob = self.cleaned_data.get('fecha_nacimiento')
        today = date.today()
        if dob:
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 18:
                raise forms.ValidationError("Debes tener al menos 18 años para registrarte.")
        return dob

    # Validación extra de contraseña
    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if len(password) < 8:
            raise forms.ValidationError("La contraseña debe tener al menos 8 caracteres.")
        return password

    # Guardar usuario y campos relacionados
    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            # El perfil es creado por la señal 'post_save', ahora lo actualizamos con datos extra
            if hasattr(user, 'perfil'):
                user.perfil.fecha_nacimiento = self.cleaned_data['fecha_nacimiento']
                user.perfil.genero = self.cleaned_data['genero']
                user.perfil.save()
        return user

class OnboardingForm(forms.ModelForm):
    # Campo extra para la foto (no está en el modelo directamente si usas ImageField)
    foto_perfil_upload = forms.ImageField(required=False)

    class Meta:
        model = Perfil
        fields = ['localidad', 'objetivo', 'nivel_actividad', 'altura']
    
    # Campos extra gestionados manualmente
    peso = forms.DecimalField(max_digits=5, decimal_places=2, required=False)
    # Definimos estos campos aquí para que la validación estándar de ModelForm no interfiera
    # y podamos aceptar strings arbitrarios que luego convertiremos en objetos.
    alergias = forms.CharField(required=False) 
    gustos = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        # Recibimos el "paso" actual
        self.step = kwargs.pop('step', None)
        super().__init__(*args, **kwargs)
        
        # Definir qué campos corresponden a cada paso
        fields_per_step = {
            1: ['localidad'],
            2: ['altura', 'peso', 'objetivo', 'nivel_actividad'],
            3: ['alergias'],
            4: ['gustos']
        }
        
        # Obtener los campos permitidos para este paso
        allowed_fields = fields_per_step.get(self.step, [])
        
        # Eliminar los campos que no son de este paso para evitar sobreescribir con blancos
        # convertimos keys a lista para poder mutar el diccionario
        for field_name in list(self.fields.keys()):
            if field_name not in allowed_fields:
                del self.fields[field_name]
        
        # Hacer obligatorios los campos del paso actual (excepto opcionales naturales)
        # Nota: peso, alergias y gustos tienen su propia lógica
        if self.step == 1:
            if 'localidad' in self.fields: self.fields['localidad'].required = True
        
        if self.step == 2:
            if 'altura' in self.fields: self.fields['altura'].required = True
            if 'peso' in self.fields: self.fields['peso'].required = True
             # nivel_actividad y objetivo suelen tener defaults, pero mejor forzar selección si es radio
            if 'objetivo' in self.fields: self.fields['objetivo'].required = True
            if 'nivel_actividad' in self.fields: self.fields['nivel_actividad'].required = True

    def save_extra_data(self, perfil):
        """
        Método auxiliar para guardar datos que no son campos directos del modelo
        o que requieren lógica M2M manual. Se debe llamar DESPUÉS de perfil.save().
        """
        # --- MANEJO DE PESO ---
        if self.cleaned_data.get('peso'):
            from .models import RegistroPeso
            RegistroPeso.objects.create(perfil=perfil, peso=self.cleaned_data['peso'])

        # --- MANEJO DE ALERGIAS (Paso 3) ---
        # Esperamos una cadena separada por comas desde el input hidden
        raw_alergias = self.data.get('alergias')
        # Si no hay data directa, revisamos cleaned_data por si acaso
        if not raw_alergias and 'alergias' in self.cleaned_data:
            raw_alergias = self.cleaned_data['alergias']
            
        if raw_alergias:
            # Puede venir como lista si es cleaned_data de un CharField o string
            if isinstance(raw_alergias, list):
                items = raw_alergias
            else:
                items = raw_alergias.split(',')
                
            pks_alergias = []
            for item in items:
                nombre = item.strip()
                if nombre:
                    obj, _ = Alergia.objects.get_or_create(nombre__iexact=nombre, defaults={'nombre': nombre})
                    pks_alergias.append(obj.pk)
            
            # Usamos set() para reemplazar
            if pks_alergias:
                perfil.alergias.set(pks_alergias)

        # --- MANEJO DE GUSTOS (Paso 4) ---
        # Gustos viene como checkboxes (lista de valores)
        raw_gustos = self.data.getlist('gustos')
        if raw_gustos:
            pks_gustos = []
            for item in raw_gustos:
                nombre = item.strip()
                if nombre:
                    obj, _ = Gustos.objects.get_or_create(nombre__iexact=nombre, defaults={'nombre': nombre})
                    pks_gustos.append(obj.pk)
            
            if pks_gustos:
                try:
                    perfil.gustos.set(pks_gustos)
                except Exception:
                    pass



class EditarPerfilForm(forms.ModelForm):
    first_name = forms.CharField(label="Nombre", max_length=30, required=True)
    last_name = forms.CharField(label="Apellido", max_length=30, required=True)
    email = forms.EmailField(label="Email", required=True)
    
    class Meta:
        model = Perfil
        fields = [
            'localidad', 'fecha_nacimiento', 'genero', 
            'altura', 'porcentaje_grasa', 'somatotipo',
            'tipo_dieta', 'objetivo', 'nivel_actividad',
            'frecuencia_comidas', 'horario_sueno',
            'alergias', 'intolerancias', 'condiciones_medicas', 'gustos'
        ]
        labels = {
            'localidad': 'Ubicación',
            'fecha_nacimiento': 'Fecha de Nacimiento',
            'genero': 'Género',
            'altura': 'Altura (cm)',
            'porcentaje_grasa': '% Grasa Corporal',
            'somatotipo': 'Somatotipo',
            'tipo_dieta': 'Tipo de Dieta',
            'objetivo': 'Objetivo Principal',
            'nivel_actividad': 'Nivel de Actividad',
            'frecuencia_comidas': 'Frecuencia de Comidas',
            'horario_sueno': 'Horario de Sueño',
            'alergias': 'Alergias',
            'intolerancias': 'Intolerancias',
            'condiciones_medicas': 'Condiciones Médicas',
            'gustos': 'Mis Gustos'
        }
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'localidad': forms.TextInput(attrs={'placeholder': 'Ciudad, País'}),
            'altura': forms.NumberInput(attrs={'step': '0.01'}),
            'porcentaje_grasa': forms.NumberInput(attrs={'step': '0.1'}),
            'horario_sueno': forms.TextInput(attrs={'placeholder': 'Ej: 11pm - 7am'}),
            'alergias': forms.CheckboxSelectMultiple(),
            'intolerancias': forms.CheckboxSelectMultiple(),
            'condiciones_medicas': forms.CheckboxSelectMultiple(),
            'gustos': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email
        
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs.update({'class': 'form-control custom-input'})
            else:
                field.widget.attrs.update({'class': 'form-check-input'})
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if self.user and User.objects.filter(email=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("Este email ya está en uso por otro usuario.")
        return email
    
    def save(self, commit=True):
        perfil = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            if commit:
                self.user.save()
                perfil.save()
                self.save_m2m() # Importante para campos ManyToMany
        return perfil
