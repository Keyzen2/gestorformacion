# app.py
import streamlit as st
from supabase import create_client
from io import BytesIO
from utils import (
    generar_xml_accion_formativa,
    generar_xml_inicio_grupo,
    generar_xml_finalizacion_grupo,
    generar_pdf_grupo,
    importar_participantes_excel,
    validar_xml,
    guardar_documento_en_storage
)

# Config
SUPABASE_URL = st.secrets["SUPABASE"]["url"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE"]["anon_key"]
SUPABASE_SERVICE_KEY = st.secrets["SUPABASE"].get("service_role_key")
BUCKET_DOC = "documentos"

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -----------------------------
# Helpers de autenticación
# -----------------------------
def get_current_user_auth_id():
    try:
        resp = supabase.auth.get_user()
        if resp and hasattr(resp, "data") and resp.data and resp.data.get("user"):
            return resp.data["user"]["id"]
        if isinstance(resp, dict) and resp.get("data") and resp["data"].get("user"):
            return resp["data"]["user"]["id"]
    except Exception:
        pass
    return st.session_state.get("user_id")

def login_screen():
    st.title("Soy tu gestor de formación")
    st.subheader("Iniciar sesión")

    email = st.text_input("Email")
    password = st.text_input("Contraseña", type="password")

    if st.button("Entrar"):
        try:
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            if auth_response.user:
                st.session_state["user_id"] = auth_response.user.id
                st.session_state["user_email"] = auth_response.user.email
                st.experimental_rerun()
            else:
                st.error("Credenciales incorrectas")
        except Exception as e:
            st.error(f"Error al iniciar sesión: {e}")

def logout_button():
    if st.sidebar.button("Cerrar sesión"):
        st.session_state.clear()
        st.experimental_rerun()

# -----------------------------
# Formulario de alta de empresa + usuario
# -----------------------------
def crear_empresa_usuario():
    st.subheader("Crear Empresa y Usuario Empresa")
    nombre_empresa = st.text_input("Nombre de la empresa")
    cif_empresa = st.text_input("CIF")
    email_usuario = st.text_input("Email del usuario")
    if st.button("Crear"):
        if not (nombre_empresa and cif_empresa and email_usuario):
            st.warning("Rellena todos los campos")
            return
        # Insert empresa
        empresa_resp = supabase.table("empresas").insert({
            "nombre": nombre_empresa,
            "cif": cif_empresa
        }).execute()
        if empresa_resp.data:
            empresa_id = empresa_resp.data[0]["id"]
            # Insert usuario
            supabase.table("usuarios").insert({
                "email": email_usuario,
                "rol": "empresa",
                "empresa_id": empresa_id
            }).execute()
            st.success(f"Empresa '{nombre_empresa}' y usuario '{email_usuario}' creados correctamente.")
        else:
            st.error("Error al crear la empresa.")

# -----------------------------
# Panel principal (lo que ya tenías)
# -----------------------------
def main_panel(usuario_uid, rol):
    st.title("Soy tu gestor de formación")

    # Panel administración
    if rol == "admin":
        st.subheader("Panel admin - Usuarios")
        usuarios = supabase.table("usuarios").select("*").execute().data or []
        for u in usuarios:
            st.write(f"{u.get('nombre')} - {u.get('email')} - rol: {u.get('rol')}")

        with st.form("cambiar_rol"):
            email_cambiar = st.text_input("Email a cambiar")
            nuevo_rol = st.selectbox("Nuevo rol", ["empresa", "admin"])
            if st.form_submit_button("Actualizar rol"):
                supabase.table("usuarios").update({"rol": nuevo_rol}).eq("email", email_cambiar).execute()
                st.success("Rol actualizado")

        # Formulario de creación de empresas + usuarios
        crear_empresa_usuario()

    # ---------------------------
    # Selección acción formativa y grupo
    # ---------------------------
    acciones = supabase.table("acciones_formativas").select("*").execute().data or []
    if not acciones:
        st.info("No hay acciones formativas. Crea una en la base de datos.")
        return

    accion_map = {a["id"]: a for a in acciones}
    accion_id = st.selectbox("Acción formativa", list(accion_map.keys()), format_func=lambda x: accion_map[x]["nombre"])

    grupos = supabase.table("grupos").select("*").eq("accion_formativa_id", accion_id).execute().data or []
    grupo_map = {g["id"]: g for g in grupos}
    if grupos:
        grupo_id = st.selectbox("Grupo", list(grupo_map.keys()), format_func=lambda x: grupo_map[x]["codigo_grupo"])
    else:
        st.info("No hay grupos para esta acción.")
        grupo_id = None

    # --- Importación de participantes, paginación, generación XML/PDF, histórico ---
    # 🔽 🔽 🔽 Aquí va exactamente tu código original de 203 líneas
    # Mantener tal cual lo tenías: importación de Excel, generación XML/PDF, histórico
    # No se toca nada de la lógica existente
    # ------------------------------------------------------------------------------

# -----------------------------
# MAIN FLOW
# -----------------------------
def main():
    usuario_uid = get_current_user_auth_id()
    if not usuario_uid:
        login_screen()
        return

    # Sidebar
    st.sidebar.write(f"Usuario: {st.session_state.get('user_email')}")
    logout_button()

    # Obtener rol desde tabla usuarios
    rol = "empresa"
    try:
        r = supabase.table("usuarios").select("rol").eq("auth_id", usuario_uid).single().execute()
        if r and getattr(r, "data", None):
            rol = r.data["rol"]
    except Exception:
        st.warning("No se pudo determinar el rol, por defecto: empresa")

    main_panel(usuario_uid, rol)

if __name__ == "__main__":
    main()
