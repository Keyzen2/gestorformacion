import streamlit as st
from supabase import create_client

# Cargar claves desde secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

# Crear cliente admin
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

st.title("🔍 Diagnóstico de conexión con Supabase")
st.caption("Verifica que el cliente admin tiene acceso a Auth y a las tablas protegidas.")

# Test 1: Conexión básica
try:
    st.success("✅ Conexión establecida con Supabase.")
except Exception as e:
    st.error(f"❌ Error de conexión: {e}")

# Test 2: Acceso a Auth Admin
with st.expander("🔐 Verificar acceso a Auth Admin"):
    try:
        users_list = supabase_admin.auth.admin.list_users()
        if isinstance(users_list, list):
            st.success(f"✅ Acceso a Auth Admin correcto. Usuarios encontrados: {len(users_list)}")
            st.write(users_list[:5])  # Mostrar los primeros 5 usuarios
        else:
            st.warning("⚠️ La respuesta no es una lista. Resultado:")
            st.write(users_list)
    except Exception as e:
        st.error(f"❌ Error al acceder a Auth Admin: {e}")

# Test 3: Acceso a tabla 'usuarios'
with st.expander("📦 Verificar acceso a tabla 'usuarios'"):
    try:
        res = supabase_admin.table("usuarios").select("*").limit(5).execute()
        st.success(f"✅ Acceso a 'usuarios' correcto. Registros encontrados: {len(res.data)}")
        st.dataframe(res.data)
    except Exception as e:
        st.error(f"❌ Error al acceder a tabla 'usuarios': {e}")

# Test 4: Acceso a tabla 'participantes'
with st.expander("🧑‍🎓 Verificar acceso a tabla 'participantes'"):
    try:
        res = supabase_admin.table("participantes").select("*").limit(5).execute()
        st.success(f"✅ Acceso a 'participantes' correcto. Registros encontrados: {len(res.data)}")
        st.dataframe(res.data)
    except Exception as e:
        st.error(f"❌ Error al acceder a tabla 'participantes': {e}")
