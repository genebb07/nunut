import os
import sys
import django

# setup django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from base.models import Receta

def add_advanced_recipes():
    print("🍳 Añadiendo Recetas Avanzadas y Variadas...")

    # Lista de nuevas recetas con datos completos
    new_recipes = [
        # --- FÁCIL ---
        {
            "titulo": "Batido Verde Detox",
            "desc": "Energía instantánea con espinacas, manzana y jengibre. Ideal para comenzar el día ligero.",
            "calorias": 180,
            "tiempo": "5 min",
            "dificultad": "Fácil",
            "tipo_dieta": "VEGA", # Vegano
            "categoria": "desayuno",
            "macros": {"p": 4, "c": 35, "f": 2},
            "img": "https://images.unsplash.com/photo-1610970881699-44a5587cabec?q=80&w=600&auto=format&fit=crop",
            "ingredientes": ["1 Manzana verde", "Puñado de espinacas", "Pepino", "Jugo de limón", "Jengibre", "Agua de coco"],
            "pasos": ["Lavar y cortar frutas.", "Licuar todo hasta obtener mezcla homogénea.", "Servir frío."]
        },
        {
            "titulo": "Huevos Revueltos con Champiñones",
            "desc": "Desayuno proteico clásico, bajo en carbohidratos.",
            "calorias": 320,
            "tiempo": "10 min",
            "dificultad": "Fácil",
            "tipo_dieta": "VEGE", # Vegetariano
            "categoria": "desayuno",
            "macros": {"p": 22, "c": 5, "f": 24},
            "img": "https://images.unsplash.com/photo-1510693206972-df098062cb71?q=80&w=600&auto=format&fit=crop",
            "ingredientes": ["3 Huevos grandes", "100g Champiñones laminados", "Cebollín picado", "Mantequilla o Ghee", "Sal y pimienta"],
            "pasos": ["Saltear champiñones en mantequilla.", "Batir huevos y añadirlos a la sartén.", "Revolver hasta el punto deseado.", "Servir con cebollín."]
        },
        {
            "titulo": "Ensalada Caprese Keto",
            "desc": "Fresca, simple y alta en grasas saludables. Perfecta para dietas cetogénicas.",
            "calorias": 450,
            "tiempo": "5 min",
            "dificultad": "Fácil",
            "tipo_dieta": "KETO", # Keto/Paleo (usaré PALEO o OTRO según modelo)
            "categoria": "almuerzo", # Aunque es ensalada, puede ser almuerzo ligero
            "macros": {"p": 18, "c": 8, "f": 38},
            "img": "https://images.unsplash.com/photo-1529312266912-b33cf6227e2f?q=80&w=600&auto=format&fit=crop",
            "ingredientes": ["Mozzarella fresca (bocconcini)", "Tomates Cherry", "Albahaca fresca", "Aceite de Oliva virgen extra", "Vinagre balsámico (poco)"],
            "pasos": ["Cortar tomates y queso.", "Mezclar en un bowl.", "Añadir albahaca y aderezo."]
        },

        # --- DIFÍCIL ---
        {
            "titulo": "Risotto de Setas Trufado",
            "desc": "Un plato elegante que requiere paciencia y técnica para lograr la cremosidad perfecta.",
            "calorias": 650,
            "tiempo": "50 min",
            "dificultad": "Difícil",
            "tipo_dieta": "VEGE",
            "categoria": "cena", # Cena pesada o Almuerzo domingo
            "macros": {"p": 18, "c": 85, "f": 25},
            "img": "https://images.unsplash.com/photo-1626804475297-411db1420718?q=80&w=600&auto=format&fit=crop",
            "ingredientes": ["Arroz Arborio", "Caldo de verduras caliente", "Setas Porcini secas", "Vino blanco seco", "Parmesano Reggiano", "Aceite de trufa"],
            "pasos": ["Sofreír cebolla y arroz.", "Desglasar con vino blanco.", "Añadir caldo cucharón a cucharón removiendo constantemente (20 min).", "Mantecar con mantequilla y parmesano fuera del fuego.", "Terminar con aceite de trufa."]
        },
        {
            "titulo": "Salmón Wellington",
            "desc": "Salmón envuelto en hojaldre con espinacas y queso crema. Una receta impresionante.",
            "calorias": 780,
            "tiempo": "60 min",
            "dificultad": "Difícil",
            "tipo_dieta": "OMNI",
            "categoria": "almuerzo",
            "macros": {"p": 45, "c": 40, "f": 48},
            "img": "https://images.unsplash.com/photo-1632778149955-e80f8ceca2e8?q=80&w=600&auto=format&fit=crop",
            "ingredientes": ["Lomo de Salmón sin piel", "Masa de hojaldre", "Espinacas salteadas", "Queso crema con hierbas", "Huevo para pintar"],
            "pasos": ["Extender hojaldre.", "Colocar cama de espinacas y queso.", "Poner salmón encima y cerrar el paquete.", "Pintar con huevo y hornear a 200°C por 25-30 min."]
        },
        {
            "titulo": "Curry Thai Verde de Vegetales",
            "desc": "Explosión de sabores exóticos. Requiere hacer la pasta de curry desde cero para el mejor sabor.",
            "calorias": 420,
            "tiempo": "45 min",
            "dificultad": "Difícil", # Media-Dificil por ingredientes
            "tipo_dieta": "VEGA",
            "categoria": "cena",
            "macros": {"p": 15, "c": 35, "f": 28},
            "img": "https://images.unsplash.com/photo-1622396636181-42661578e9db?q=80&w=600&auto=format&fit=crop",
            "ingredientes": ["Leche de coco", "Berenjena thai", "Bambú", "Pasta de curry verde (casera)", "Tofu firme", "Albahaca thai", "Lima Kaffir"],
            "pasos": ["Hacer pasta machacando chiles verdes, galangal, lemongrass, ajo y chalotas.", "Freír pasta en aceite.", "Añadir leche de coco y reducir.", "Cocinar vegetales y tofu en la salsa."]
        },
        
        # --- MEDIA ---
        {
             "titulo": "Buddha Bowl Mediterráneo",
             "desc": "Equilibrio perfecto de macros colores mediterráneos.",
             "calorias": 550,
             "tiempo": "25 min",
             "dificultad": "Media",
             "tipo_dieta": "VEGE",
             "categoria": "almuerzo",
             "macros": {"p": 20, "c": 65, "f": 22},
             "img": "https://images.unsplash.com/photo-1543339308-43e59d6b73a6?q=80&w=600&auto=format&fit=crop",
             "ingredientes": ["Falafel horneado", "Hummus", "Tabouleh (perejil, tomate, burgol)", "Aceitunas negras", "Pan pita integral"],
             "pasos": ["Hornear falafels.", "Preparar tabouleh picando todo fino.", "Montar bowl con hummus en el centro y acompañamientos alrededor."]
        }

    ]

    count = 0
    for r in new_recipes:
        # Mapeo de dieta a choices del modelo si es necesario, o usar valores directos
        dieta_map = {'KETO': 'OTRO'} # Mapear KETO a OTRO si no existe en modelo
        tipo_dieta = dieta_map.get(r['tipo_dieta'], r['tipo_dieta'])

        # Crear descripción completa
        ingredientes_txt = "\n".join([f"- {ing}" for ing in r["ingredientes"]])
        pasos_txt = "\n".join([f"{i+1}. {paso}" for i, paso in enumerate(r["pasos"])])
        full_desc = f"{r['desc']}\n\n### Ingredientes:\n{ingredientes_txt}\n\n### Preparación:\n{pasos_txt}"

        receta, created = Receta.objects.get_or_create(
            titulo=r['titulo'],
            defaults={
                'descripcion': full_desc,
                'calorias': r['calorias'],
                'tiempo': r['tiempo'],
                'tiempo_minutos': int(r['tiempo'].split()[0]),
                'dificultad': r['dificultad'],
                'tipo_dieta': tipo_dieta,
                'categoria': r['categoria'],
                'imagen_url': r['img'],
                'proteinas': r['macros']['p'],
                'carbos': r['macros']['c'],
                'grasas': r['macros']['f'],
                'ingredientes_count': len(r['ingredientes']),
                'esta_aprobada': True
            }
        )
        if created:
            print(f"   ✅ Añadida: {r['titulo']} ({r['dificultad']} - {r['tipo_dieta']})")
            count += 1
        else:
            print(f"   ℹ️ Ya existe: {r['titulo']}")

    print(f"\n🎉 ¡{count} recetas nuevas añadidas!")

if __name__ == '__main__':
    add_advanced_recipes()
