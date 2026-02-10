"""
Script para resetear el perfil de un usuario (borrar datos de la encuesta)
Ejecutar con: python reset_perfil.py <username>
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from base.models import Perfil, RegistroPeso

def reset_perfil(username):
    """Resetea todos los datos del perfil de un usuario"""
    print("=" * 70)
    print(f"RESETEO DE PERFIL - Usuario: {username}")
    print("=" * 70)
    
    try:
        user = User.objects.get(username=username)
        perfil = user.perfil
    except User.DoesNotExist:
        print(f"❌ ERROR: Usuario '{username}' no encontrado")
        return
    except Perfil.DoesNotExist:
        print(f"❌ ERROR: El usuario '{username}' no tiene perfil asociado")
        return
    
    print(f"\n✓ Usuario encontrado: {user.first_name} {user.last_name}")
    print(f"  Email: {user.email}")
    print(f"\n⚠️  Se borrarán los siguientes datos:")
    
    # Mostrar qué se va a borrar
    print(f"  - Localidad: {perfil.localidad or 'N/A'}")
    print(f"  - Altura: {perfil.altura or 'N/A'} cm")
    print(f"  - Nivel de actividad: {perfil.nivel_actividad or 'N/A'}")
    print(f"  - Objetivo: {perfil.objetivo or 'N/A'}")
    print(f"  - Alergias: {perfil.alergias.count()} registradas")
    print(f"  - Gustos: {perfil.gustos.count()} registrados")
    print(f"  - Historial de peso: {perfil.historial_peso.count()} registros")
    print(f"  - Foto de perfil: {'Sí' if perfil.foto_perfil else 'No'}")
    
    # Confirmar
    confirmacion = input("\n¿Estás seguro de que quieres resetear este perfil? (escribe 'SI' para confirmar): ")
    
    if confirmacion.strip().upper() != 'SI':
        print("\n❌ Operación cancelada")
        return
    
    print("\n🔄 Reseteando perfil...")
    
    user.onboarding_completado = False
    # Borrar historial de peso
    peso_count = perfil.historial_peso.count()
    perfil.historial_peso.all().delete()
    print(f"  ✓ Eliminados {peso_count} registros de peso")
    
    # Limpiar relaciones ManyToMany
    alergias_count = perfil.alergias.count()
    perfil.alergias.clear()
    print(f"  ✓ Eliminadas {alergias_count} alergias")
    
    gustos_count = perfil.gustos.count()
    perfil.gustos.clear()
    print(f"  ✓ Eliminados {gustos_count} gustos")
    
    # Resetear campos del perfil
    perfil.localidad = "Venezuela"
    perfil.altura = None
    perfil.nivel_actividad = 'SEDE'
    perfil.objetivo = ''
    perfil.foto_perfil = None
    perfil.onboarding_completado = False
    perfil.save()
    
    print(f"  ✓ Campos del perfil reseteados")
    
    print("\n" + "=" * 70)
    print("✅ PERFIL RESETEADO EXITOSAMENTE")
    print("=" * 70)
    print(f"\nEl usuario '{username}' puede volver a completar la encuesta desde cero.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python reset_perfil.py <username>")
        print("\nEjemplo: python reset_perfil.py mela")
        sys.exit(1)
    
    username = sys.argv[1]
    reset_perfil(username)
