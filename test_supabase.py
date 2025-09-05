import streamlit as st
from supabase import create_client

# Cargar claves desde secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

# Crear cliente admin
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

st.title("🔍 Test de conexión con Supabase")

# Verificar conexión básica
try:
    st.write("✅ Conexión establecida con Supabase.")
    st.write("🔐 Probando acceso a Auth Admin...")

    users = supabase_admin.auth.admin.list_users()
    st.success(f"Usuarios en Auth: {len(users.users)} encontrados.")
except Exception as e:
    st.error(f"❌ Error al acceder a Auth Admin: {e}")

# Verificar acceso a tabla protegida
try:
    st.write("📦 Probando acceso a tabla 'usuarios'...")
    res = supabase_admin.table("usuarios").select("*").limit(5).execute()
    st.success(f"✅ Acceso a 'usuarios' correcto. Registros encontrados: {len(res.data)}")
except Exception as e:
    st.error(f"❌ Error al acceder a tabla 'usuarios': {e}")
