# app.py
import streamlit as st
from supabase import create_client
from io import BytesIO
from datetime import datetime
from utils import (
    generar_xml_accion_formativa,
    generar_xml_inicio_grupo,
    generar_xml_finalizacion_grupo,
    generar_pdf_grupo,
    importar_participantes_excel,
    validar_xml,
    guardar_documento_en_storage
)

# ------------------------
# CONFIGURACIÓN
# ------------------------
SUPABASE_URL = st.secrets["SUPABASE"]["url"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE"]["anon_key"]
SUPABASE_SERVICE_KEY = st.secrets["SUPABASE"].get("service_role_key")
BUCKET_DOC = "documentos"

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ------------------------
# HELPER: USUARIO ACTUAL
# ------------------------
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

usuario_uid = get_current_user_auth_id()
rol_usuario = "empresa"  # default
empresa_id = None

# Intentar determinar rol desde tabla usuarios
try:
    user = supabase.table("usuarios").select("*").eq("usuario_auth_id", usuario_uid).execute().data
    if user:
        user = user[0]
        rol_usuario = user.get("rol", "empresa")
        empresa_id = user.get("empresa_id")
except Exception:
    st.warning("No se pudo determinar el rol, por defecto: empresa")

st.title("Soy tu gestor de formación")

# ------------------------
# MENU LATERAL
# ------------------------
if rol_usuario == "admin":
    opcion = st.sidebar.selectbox("Menú Admin", [
        "Acciones Formativas", "Grupos", "Participantes", "Usuarios / Empresas",
        "Generar Documentos", "Histórico Documentos", "Cerrar sesión"
    ])
else:
    opcion = st.sidebar.selectbox("Menú Empresa", [
        "Mis Acciones Formativas", "Mis Grupos", "Mis Participantes",
        "Mis Documentos", "Cerrar sesión"
    ])

# ------------------------
# CERRAR SESIÓN
# ------------------------
if opcion == "Cerrar sesión":
    supabase.auth.sign_out()
    st.session_state.clear()
    st.experimental_rerun()

# ------------------------
# ADMIN - ACCIONES FORMATIVAS
# ------------------------
if rol_usuario == "admin" and opcion == "Acciones Formativas":
    st.subheader("Alta de Acción Formativa")
    with st.form("form_accion"):
        tipo = st.selectbox("Tipo de acción formativa", ["Propia", "Certificado de Profesionalidad"])
        codigo = st.text_input("Código de acción")
        denominacion = st.text_input("Denominación")
        area = st.selectbox("Área profesional", [
            "ADGD - ADMINISTRACIÓN Y AUDITORÍA",
            "INDA - INFORMÁTICA Y DESARROLLO",
            "ELEC - ELECTRICIDAD Y ELECTRÓNICA"
        ])
        modalidad = st.selectbox("Modalidad", ["Presencial", "Teleformación"])
        horas_presenciales = st.number_input("Horas presenciales", min_value=0)
        horas_teleformacion = st.number_input("Horas teleformación", min_value=0)
        objetivos = st.text_area("Objetivos")
        contenidos = st.text_area("Contenidos")
        if st.form_submit_button("Crear Acción Formativa"):
            supabase.table("acciones_formativas").insert([{
                "tipo": tipo,
                "codigo": codigo,
                "denominacion": denominacion,
                "area": area,
                "modalidad": modalidad,
                "horas_presenciales": horas_presenciales,
                "horas_teleformacion": horas_teleformacion,
                "objetivos": objetivos,
                "contenidos": contenidos,
                "empresa_id": None
            }]).execute()
            st.success("Acción formativa creada")

    # Mostrar tabla con st.dataframe
    acciones = supabase.table("acciones_formativas").select("*").execute().data or []
    if acciones:
        st.dataframe(acciones)

# ------------------------
# ADMIN - GRUPOS
# ------------------------
if rol_usuario == "admin" and opcion == "Grupos":
    st.subheader("Grupos")
    acciones = supabase.table("acciones_formativas").select("*").execute().data or []
    accion_map = {a["id"]: a for a in acciones}
    accion_id = st.selectbox("Acción Formativa", list(accion_map.keys()),
                             format_func=lambda x: accion_map[x]["denominacion"])
    grupos = supabase.table("grupos").select("*").eq("accion_formativa_id", accion_id).execute().data or []
    if grupos:
        st.dataframe(grupos)

# ------------------------
# ADMIN - PARTICIPANTES
# ------------------------
if rol_usuario == "admin" and opcion == "Participantes":
    st.subheader("Participantes")
    grupos = supabase.table("grupos").select("*").execute().data or []
    grupo_map = {g["id"]: g for g in grupos}
    grupo_id = st.selectbox("Selecciona grupo", list(grupo_map.keys()),
                            format_func=lambda x: grupo_map[x]["codigo_grupo"])
    participantes = supabase.table("participantes").select("*").eq("grupo_id", grupo_id).execute().data or []
    if participantes:
        st.dataframe(participantes)

# ------------------------
# ADMIN - USUARIOS / EMPRESAS
# ------------------------
if rol_usuario == "admin" and opcion == "Usuarios / Empresas":
    st.subheader("Usuarios y Empresas")
    usuarios = supabase.table("usuarios").select("*").execute().data or []
    st.dataframe(usuarios)
    with st.form("form_usuario"):
        nombre = st.text_input("Nombre")
        email = st.text_input("Email")
        rol_nuevo = st.selectbox("Rol", ["admin", "empresa"])
        empresa_id_nueva = st.text_input("CIF/NIF empresa (si es empresa)")
        if st.form_submit_button("Crear Usuario"):
            supabase.table("usuarios").insert([{
                "nombre": nombre,
                "email": email,
                "rol": rol_nuevo,
                "empresa_id": empresa_id_nueva,
                "usuario_auth_id": None
            }]).execute()
            st.success("Usuario creado")

# ------------------------
# ADMIN - GENERAR DOCUMENTOS
# ------------------------
if rol_usuario == "admin" and opcion == "Generar Documentos":
    st.subheader("Generar XML / PDF")
    st.info("Aquí se generará y guardará XML/PDF de Fundae según acción/grupo seleccionados")

# ------------------------
# ADMIN - HISTÓRICO DOCUMENTOS
# ------------------------
if rol_usuario == "admin" and opcion == "Histórico Documentos":
    st.subheader("Histórico de Documentos")
    docs = supabase.table("documentos").select("*").order("created_at", desc=True).execute().data or []
    st.dataframe(docs)

# ------------------------
# EMPRESA - MIS ACCIONES / GRUPOS / PARTICIPANTES / DOCUMENTOS
# ------------------------
if rol_usuario == "empresa":
    st.subheader(f"Bienvenido, empresa {empresa_id}")
    menu_empresa = st.sidebar.selectbox("Menú Empresa", [
        "Mis Acciones Formativas", "Mis Grupos", "Mis Participantes", "Mis Documentos"
    ])

    if menu_empresa == "Mis Acciones Formativas":
        acciones = supabase.table("acciones_formativas").select("*").eq("empresa_id", empresa_id).execute().data or []
        if acciones:
            st.dataframe(acciones)
        else:
            st.info("No tienes acciones formativas registradas.")

    elif menu_empresa == "Mis Grupos":
        grupos = supabase.table("grupos").select("*").eq("empresa_id", empresa_id).execute().data or []
        if grupos:
            st.dataframe(grupos)
        else:
            st.info("No tienes grupos registrados.")

    elif menu_empresa == "Mis Participantes":
        grupos = supabase.table("grupos").select("*").eq("empresa_id", empresa_id).execute().data or []
        grupo_map = {g["id"]: g for g in grupos}
        if grupos:
            grupo_id = st.selectbox("Selecciona grupo", list(grupo_map.keys()), format_func=lambda x: grupo_map[x]["codigo_grupo"])
            participantes = supabase.table("participantes").select("*").eq("grupo_id", grupo_id).execute().data or []
            if participantes:
                st.dataframe(participantes)
            else:
                st.info("No hay participantes en este grupo.")
        else:
            st.info("No tienes grupos registrados.")

    elif menu_empresa == "Mis Documentos":
        documentos = supabase.table("documentos").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).execute().data or []
        if documentos:
            st.dataframe(documentos)
        else:
            st.info("No tienes documentos generados.")
