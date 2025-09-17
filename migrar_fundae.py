import os
from supabase import create_client
from utils.fundae_helpers import actualizar_tipo_documento_tutores, migrar_horarios_existentes

# Configurar Supabase
SUPABASE_URL = "tu_url_de_supabase"
SUPABASE_KEY = "tu_key_de_supabase" 
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Iniciando migración FUNDAE...")

# 1. Migrar tipos de documento
print("1. Actualizando tipos de documento en tutores...")
if actualizar_tipo_documento_tutores(supabase):
    print("✅ Tipos de documento actualizados")
else:
    print("❌ Error al actualizar tipos de documento")

# 2. Migrar horarios
print("2. Migrando horarios a formato estructurado...")
migrados, errores = migrar_horarios_existentes(supabase)
print(f"✅ Horarios migrados: {migrados}")
if errores > 0:
    print(f"⚠️ Errores: {errores}")

print("Migración completada!")
