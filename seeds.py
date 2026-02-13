import os
import django
import random
from datetime import date, timedelta, datetime
import sys

# 1. Configurar Entorno Django
# Asumimos que el script está en la raíz del proyecto (al mismo nivel que manage.py)
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from base.models import Perfil, LoginStreak, Receta, RegistroPeso, ComidaDiaria, RegistroAgua

def run_seed():
    print("🌱 Iniciando Seeding de Base de Datos NUNUT...")

    # --- 1. CREACIÓN DE USUARIOS ---
    print("👤 Generando usuarios...")
    nombres = ['Ana', 'Carlos', 'Sofia', 'Miguel', 'Elena', 'David']
    apellidos = ['Garcia', 'Lopez', 'Rodriguez', 'Martinez', 'Fernandez', 'Perez']
    
    users_created = []

    for i in range(5):
        nombre = nombres[i]
        apellido = apellidos[i]
        username = f"{nombre.lower()}{random.randint(10,99)}"
        email = f"{username}@example.com"
        
        if not User.objects.filter(username=username).exists():
            user = User.objects.create_user(username=username, email=email, password='password123')
            user.first_name = nombre
            user.last_name = apellido
            # Fecha registro aleatoria ultimos 3 meses
            dias_atras = random.randint(1, 90)
            fecha_registro = datetime.now() - timedelta(days=dias_atras)
            user.date_joined = fecha_registro
            user.save()
            print(f"   - Usuario creado: {username}")
            users_created.append(user)
        else:
            print(f"   - Usuario {username} ya existe, saltando.")

    # --- 2. USUARIO 'VALU' Y RACHA ---
    print("\n👑 Configurando usuario 'valu'...")
    valu, created = User.objects.get_or_create(username='valu')
    if created:
        valu.set_password('valu123')
        valu.email = 'valu@nunut.app'
        valu.first_name = 'Valeria'
        valu.save()
        print("   - Usuario 'valu' creado.")
    else:
        print("   - Usuario 'valu' ya existía.")

    # Perfil de Valu
    perfil_valu, _ = Perfil.objects.get_or_create(usuario=valu)
    perfil_valu.altura = 165
    perfil_valu.genero = 'M'
    perfil_valu.fecha_nacimiento = date(1995, 5, 20)
    perfil_valu.rol = 'USER' # Asegurar rol
    perfil_valu.save()

    # Racha de 10 días para Valu
    print("   - Generando racha de 10 días...")
    # Limpiar racha previa para evitar duplicados en unique_together
    LoginStreak.objects.filter(perfil=perfil_valu).delete()
    
    hoy = date.today()
    for i in range(10):
        fecha = hoy - timedelta(days=i)
        LoginStreak.objects.get_or_create(perfil=perfil_valu, fecha=fecha)
    print("   - Racha generada exitosamente.")

    # --- 3. RECETAS COMPLETAS ---
    print("\n🍳 Creando Recetas Gourmet...")
    
    recetas_data = [
        {
            "titulo": "Bowl de Salmón y Quinoa",
            "calorias": 480,
            "tiempo": "25 min",
            "img": "https://images.unsplash.com/photo-1467003909585-2f8a7270028d?q=80&w=600&auto=format&fit=crop",
            "desc": "Un bowl nutritivo lleno de ácidos grasos omega-3 y proteínas de alta calidad.",
            "ingredientes": ["150g Salmón fresco", "100g Quinoa cocida", "1/2 Aguacate", "50g Pepino", "Semillas de sésamo", "Salsa de soja baja en sodio"],
            "pasos": ["Cocinar la quinoa según instrucciones.", "Sellar el salmón en sartén 3 min por lado.", "Cortar vegetales en cubos.", "Armar el bowl y decorar con sésamo."]
        },
        {
            "titulo": "Tostadas de Aguacate y Huevo",
            "calorias": 350,
            "tiempo": "10 min",
            "img": "https://images.unsplash.com/photo-1525351484163-7529414395d8?q=80&w=600&auto=format&fit=crop",
            "desc": "El desayuno perfecto para energía sostenida durante la mañana.",
            "ingredientes": ["2 Rebanadas pan integral", "1 Aguacate maduro", "2 Huevos pochados", "Chiles secos", "Sal y pimienta", "Aceite de oliva"],
            "pasos": ["Tostar el pan.", "Machacar el aguacate con sal y limón.", "Pocharlos huevos en agua hirviendo 3 min.", "Montar tostada con aguacate y huevo encima."]
        },
        {
            "titulo": "Pasta al Pesto con Tomates Cherry",
            "calorias": 520,
            "tiempo": "20 min",
            "img": "https://images.unsplash.com/photo-1473093295043-cdd812d0e601?q=80&w=600&auto=format&fit=crop",
            "desc": "Un clásico italiano lleno de sabor y antioxidantes.",
            "ingredientes": ["100g Pasta integral", "30g Albahaca fresca", "30g Queso Parmesano", "1 diente de Ajo", "Aceite de oliva virgen", "100g Tomates Cherry"],
            "pasos": ["Hervir pasta al dente.", "Procesar albahaca, nueces, ajo, queso y aceite.", "Mezclar pasta con pesto.", "Añadir tomates cherry cortados."]
        },
        {
            "titulo": "Smoothie Bowl Tropical",
            "calorias": 300,
            "tiempo": "5 min",
            "img": "https://images.unsplash.com/photo-1494597564530-871f2b93ac55?q=80&w=600&auto=format&fit=crop",
            "desc": "Refrescante y lleno de vitaminas para empezar el día.",
            "ingredientes": ["1 Plátano congelado", "100g Mango", "200ml Leche de almendra", "Granola", "Coco rallado", "Semillas de chía"],
            "pasos": ["Licuar plátano, mango y leche hasta obtener textura cremosa.", "Servir en bowl.", "Decorar con granola, coco y chía."]
        },
        {
            "titulo": "Ensalada César con Pollo Grillado",
            "calorias": 410,
            "tiempo": "15 min",
            "img": "https://images.unsplash.com/photo-1550304943-4f24f54ddde9?q=80&w=600&auto=format&fit=crop",
            "desc": "Versión ligera de la famosa ensalada, alta en proteínas.",
            "ingredientes": ["1 Pechuga de pollo", "Lechuga Romana", "Crutones integrales", "Queso Parmesano", "Yogur griego (para aderezo)", "Mostaza Dijon"],
            "pasos": ["Grillar pollo con sal y pimienta.", "Lavar y cortar lechuga.", "Hacer aderezo con yogur, mostaza y limón.", "Mezclar todo en un bowl grande."]
        },
        {
            "titulo": "Wrap de Hummus y Vegetales",
            "calorias": 380,
            "tiempo": "10 min",
            "img": "https://images.unsplash.com/photo-1626700051175-6818013e1d4f?q=80&w=600&auto=format&fit=crop",
            "desc": "Opción vegana rápida y deliciosa para el almuerzo.",
            "ingredientes": ["1 Tortilla integral grande", "4 cdas Hummus", "Espinacas baby", "Pimiento rojo asado", "Zanahoria rallada", "Pepino"],
            "pasos": ["Calentar ligeramente la tortilla.", "Untar hummus en la base.", "Colocar vegetales en capas.", "Enrollar apretado y cortar a la mitad."]
        },
        {
            "titulo": "Pechuga de Pollo al Limón y Hierbas",
            "calorias": 450,
            "tiempo": "30 min",
            "img": "https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?q=80&w=600&auto=format&fit=crop",
            "desc": "Cena baja en carbohidratos y alta en sabor.",
            "ingredientes": ["2 Pechugas de pollo", "Jugo de 1 limón", "Romero fresco", "Tomillo", "Ajo en polvo", "Espárragos"],
            "pasos": ["Marinar pollo con limón y hierbas 15 min.", "Hornear a 200°C por 20 min.", "Saltear espárragos en sartén.", "Servir caliente."]
        },
        {
            "titulo": "Avena Nocturna (Overnight Oats)",
            "calorias": 320,
            "tiempo": "5 min",
            "img": "https://images.unsplash.com/photo-1517673132405-a56a62b18caf?q=80&w=600&auto=format&fit=crop",
            "desc": "Desayuno listo para llevar, preparado la noche anterior.",
            "ingredientes": ["1/2 taza Avena", "1/2 taza Leche vegetal", "1 cda semillas chía", "1 cdita miel", "Manzana picada", "Canela"],
            "pasos": ["Mezclar avena, leche, chía y miel en un frasco.", "Refrigerar toda la noche.", "Añadir manzana y canela antes de comer."]
        },
        {
            "titulo": "Poke Bowl de Atún",
            "calorias": 500,
            "tiempo": "20 min",
            "img": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?q=80&w=600&auto=format&fit=crop",
            "desc": "Fresco, crudo y delicioso. Un plato hawaiano lleno de color.",
            "ingredientes": ["150g Atún fresco (sashimi)", "Arroz de sushi o integral", "Edamame", "Rábano", "Algas Wakame", "Salsa Ponzu"],
            "pasos": ["Cortar atún en cubos.", "Disponer arroz en la base.", "Colocar ingredientes ordenadamente encima.", "Rociar con salsa Ponzu."]
        },
        {
            "titulo": "Pancakes de Avena y Plátano",
            "calorias": 400,
            "tiempo": "15 min",
            "img": "https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445?q=80&w=600&auto=format&fit=crop",
            "desc": "Sin harinas refinadas, perfectos para un fin de semana fit.",
            "ingredientes": ["1 taza Avena molida", "1 Plátano maduro", "1 Huevo", "1/2 taza Leche", "Polvo de hornear", "Miel para servir"],
            "pasos": ["Licuar avena, plátano, huevo y leche.", "Cocinar en sartén antiadherente vuelta y vuelta.", "Servir con fruta fresca y un toque de miel."]
        }
    ]

    for data in recetas_data:
        # Formatear descripción rica
        ingredientes_txt = "\n".join([f"- {ing}" for ing in data["ingredientes"]])
        pasos_txt = "\n".join([f"{i+1}. {paso}" for i, paso in enumerate(data["pasos"])])
        
        full_desc = f"{data['desc']}\n\n### Ingredientes:\n{ingredientes_txt}\n\n### Preparación:\n{pasos_txt}"

        receta, created = Receta.objects.get_or_create(
            titulo=data["titulo"],
            defaults={
                "calorias": data["calorias"],
                "tiempo": data["tiempo"],
                "tiempo_minutos": int(data["tiempo"].split()[0]),
                "imagen_url": data["img"],
                "descripcion": full_desc,
                "ingredientes_count": len(data["ingredientes"]),
                "esta_aprobada": True,
                "categoria": "almuerzo" if data["calorias"] > 400 else "desayuno"
            }
        )
        if created:
            print(f"   - Receta creada: {data['titulo']}")

    # --- 4. HISTORIAL DE PESO 'VALU' ---
    print("\n⚖️ Generando historial de peso para 'valu'...")
    # Limpiar historial previo para evitar superposiciones raras en pruebas
    RegistroPeso.objects.filter(perfil=perfil_valu).delete()
    
    peso_actual = 68.5
    fecha_cursor = hoy - timedelta(days=60) # Hace 2 meses
    
    while fecha_cursor <= hoy:
        # Variación aleatoria pequeña (-0.3 a +0.2 kg) para simular fluctuaciones reales pero tendencia a la baja
        variacion = random.uniform(-0.4, 0.2)
        peso_actual += variacion
        
        RegistroPeso.objects.create(
            perfil=perfil_valu,
            peso=round(peso_actual, 1),
            fecha=fecha_cursor
        )
        
        # Avanzar dÃas aleatorios (registro cada 2-4 días)
        fecha_cursor += timedelta(days=random.randint(2, 4))

    print(f"   - Historial de peso generado. Peso final: {round(peso_actual, 1)}kg")

    print("\n✨ ¡Seeding Completado exitosamente!")
    print("   Ahora puedes iniciar sesión con:")
    print("   Usuario: valu")
    print("   Contraseña: valu123")

if __name__ == '__main__':
    run_seed()
