"""
Script de verificación del guardado de datos de la encuesta
Ejecutar con: python verificar_guardado.py <username>
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from base.models import Perfil, RegistroPeso

def verificar_usuario(username):
    """Verifica todos los datos guardados de un usuario"""
    print("=" * 70)
    print(f"VERIFICACIÓN DE DATOS GUARDADOS - Usuario: {username}")
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
    
    print(f"\n✓ Usuario encontrado: {user.first_name} {user.last_name} ({user.email})")
    print(f"  Onboarding completado: {'✓ SÍ' if perfil.onboarding_completado else '✗ NO'}\n")
    
    # PASO 1: Localidad
    print("━" * 70)
    print("📍 PASO 1 - LOCALIDAD")
    print("━" * 70)
    print(f"  Localidad: {perfil.localidad or '❌ NO GUARDADO'}")
    
    # PASO 2: Datos Físicos
    print("\n" + "━" * 70)
    print("📊 PASO 2 - DATOS FÍSICOS Y OBJETIVOS")
    print("━" * 70)
    print(f"  Altura: {perfil.altura or '❌ NO GUARDADO'} cm")
    
    # Peso (desde historial)
    ultimo_peso = perfil.historial_peso.first()
    if ultimo_peso:
        print(f"  Peso: ✓ {ultimo_peso.peso} kg (registrado el {ultimo_peso.fecha})")
    else:
        print(f"  Peso: ❌ NO GUARDADO")
    
    # Nivel de actividad
    actividad_display = dict(perfil.OPCIONES_ACTIVIDAD).get(perfil.nivel_actividad, 'NO GUARDADO')
    print(f"  Nivel de Actividad: {perfil.nivel_actividad or '❌'} ({actividad_display})")
    
    # Objetivo
    objetivo_display = dict(perfil.OBJETIVO_CHOICES).get(perfil.objetivo, 'NO GUARDADO')
    print(f"  Objetivo: {perfil.objetivo or '❌'} ({objetivo_display})")
    
    # PASO 3: Alergias
    print("\n" + "━" * 70)
    print("🚫 PASO 3 - ALERGIAS")
    print("━" * 70)
    alergias = perfil.alergias.all()
    if alergias.exists():
        print(f"  Total: {alergias.count()} alergia(s) guardada(s)")
        for alergia in alergias:
            print(f"    ✓ {alergia.nombre}")
    else:
        print("  ❌ NO HAY ALERGIAS GUARDADAS")
    
    # PASO 4: Gustos
    print("\n" + "━" * 70)
    print("❤️  PASO 4 - GUSTOS")
    print("━" * 70)
    gustos = perfil.gustos.all()
    if gustos.exists():
        print(f"  Total: {gustos.count()} gusto(s) guardado(s)")
        for gusto in gustos:
            print(f"    ✓ {gusto.nombre}")
    else:
        print("  ❌ NO HAY GUSTOS GUARDADOS")
    
    # Resumen final
    print("\n" + "=" * 70)
    print("📋 RESUMEN DE COMPLETITUD")
    print("=" * 70)
    
    checks = {
        "Localidad": bool(perfil.localidad),
        "Altura": bool(perfil.altura),
        "Peso": bool(ultimo_peso),
        "Nivel de Actividad": bool(perfil.nivel_actividad),
        "Objetivo": bool(perfil.objetivo),
        "Alergias": alergias.exists(),
        "Gustos": gustos.exists()
    }
    
    completados = sum(checks.values())
    total = len(checks)
    porcentaje = (completados / total) * 100
    
    for campo, guardado in checks.items():
        status = "✓" if guardado else "✗"
        print(f"  {status} {campo}")
    
    print(f"\n  Progreso: {completados}/{total} campos ({porcentaje:.0f}%)")
    
    if completados == total:
        print("\n  🎉 ¡TODOS LOS DATOS SE GUARDARON CORRECTAMENTE!")
    else:
        print(f"\n  ⚠️  FALTAN {total - completados} CAMPOS POR GUARDAR")
    
    print("=" * 70)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python verificar_guardado.py <username>")
        print("\nEjemplo: python verificar_guardado.py patri")
        sys.exit(1)
    
    username = sys.argv[1]
    verificar_usuario(username)
