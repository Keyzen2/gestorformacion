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
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import pandas as pd

# -------------------
# CONFIG
# -------------------
SUPABASE_URL = st.secrets["SUPABASE"]["url"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE"]["anon_key"]
SUPABASE_SERVICE_KEY = st.secrets["SUPABASE"].get("service_role_key")
BUCKET_DOC = "documentos"

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -------------------
# FUNCIONES AUXILIARES
# -------------------
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

def get_user_role(usuario_uid):
    try:
        r = supabase.rpc("get_user_role", {"uid": usuario_uid}).execute()
        if r and getattr(r, "data", None):
            return r.data[0].get("rol"), r.data[0].get("empresa_id")
    except Exception:
        pass
    return "empresa", None  # fallback

# -------------------
# AUTENTICACIÓN
# -------------------
st.title("Soy tu gestor de formación")
usuario_uid = get_current_user_auth_id()
rol, empresa_id = get_user_role(usuario_uid)

# -------------------
# MENÚ LATERAL
# -------------------
if rol == "admin":
    menu = st.sidebar.selectbox("Menú", ["Panel Admin", "Acciones Formativas", "Grupos", "Participantes", "Documentos", "Empresas", "Usuarios"])
else:
    menu = st.sidebar.selectbox("Menú", ["Mis Acciones", "Mis Grupos", "Mis Participantes", "Mis Documentos"])

# -------------------
# PANEL ADMIN
# -------------------
if rol == "admin" and menu == "Panel Admin":
    st.subheader("Usuarios Registrados")
    usuarios = supabase.table("usuarios").select("*").execute().data or []
    for u in usuarios:
        st.write(f"{u.get('nombre')} - {u.get('email')} - rol: {u.get('rol')} - empresa_id: {u.get('empresa_id')}")

    with st.form("crear_usuario"):
        st.markdown("### Crear usuario / empresa")
        nombre = st.text_input("Nombre")
        email = st.text_input("Email")
        rol_nuevo = st.selectbox("Rol", ["admin", "empresa"])
        cif = st.text_input("CIF/NIF empresa (solo si rol empresa)")
        if st.form_submit_button("Crear usuario"):
            supabase.table("usuarios").insert([{
                "nombre": nombre,
                "email": email,
                "rol": rol_nuevo,
                "empresa_id": None if rol_nuevo=="admin" else cif
            }]).execute()
            st.success("Usuario creado")

# -------------------
# ACCIONES FORMATIVAS (Admin)
# -------------------
if rol == "admin" and menu == "Acciones Formativas":
    st.subheader("Acciones Formativas")
    with st.form("crear_accion"):
        tipo_accion = st.selectbox("Tipo de acción formativa", ["Propia", "Certificado Profesionalidad"])
        codigo = st.text_input("Código de acción")
        denominacion = st.text_input("Denominación")
        area = st.selectbox("Área profesional", ["ADGD - ADMINISTRACIÓN Y AUDITORÍA", "SIST - SISTEMAS", "HOTE - HOSTELERÍA"])  # ejemplo
        modalidad = st.selectbox("Modalidad", ["Presencial", "Teleformación"])
        horas_pres = st.number_input("Horas presenciales", 0)
        horas_tele = st.number_input("Horas teleformación", 0)
        objetivos = st.text_area("Objetivos")
        contenidos = st.text_area("Contenidos")
        if st.form_submit_button("Crear acción"):
            supabase.table("acciones_formativas").insert([{
                "tipo": tipo_accion,
                "codigo": codigo,
                "denominacion": denominacion,
                "area": area,
                "modalidad": modalidad,
                "horas_presenciales": horas_pres,
                "horas_teleformacion": horas_tele,
                "objetivos": objetivos,
                "contenidos": contenidos
            }]).execute()
            st.success("Acción formativa creada")

    acciones = supabase.table("acciones_formativas").select("*").execute().data or []
    if acciones:
        df = pd.DataFrame(acciones)
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_pagination()
        gb.configure_side_bar()
        gridOptions = gb.build()
        AgGrid(df, gridOptions=gridOptions, enable_enterprise_modules=True)

# -------------------
# GRUPOS (Admin)
# -------------------
if rol == "admin" and menu == "Grupos":
    st.subheader("Grupos")
    acciones = supabase.table("acciones_formativas").select("*").execute().data or []
    accion_map = {a["id"]: a for a in acciones}
    accion_id = st.selectbox("Selecciona acción", list(accion_map.keys()), format_func=lambda x: accion_map[x]["denominacion"])
    with st.form("crear_grupo"):
        codigo_grupo = st.text_input("Código grupo")
        fecha_inicio = st.date_input("Fecha inicio")
        fecha_fin = st.date_input("Fecha fin")
        if st.form_submit_button("Crear grupo"):
            supabase.table("grupos").insert([{
                "codigo_grupo": codigo_grupo,
                "accion_formativa_id": accion_id,
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin": fecha_fin.isoformat()
            }]).execute()
            st.success("Grupo creado")

# -------------------
# PARTICIPANTES (Admin)
# -------------------
if rol == "admin" and menu == "Participantes":
    st.subheader("Participantes")
    grupos = supabase.table("grupos").select("*").execute().data or []
    grupo_map = {g["id"]: g for g in grupos}
    grupo_id = st.selectbox("Selecciona grupo", list(grupo_map.keys()), format_func=lambda x: grupo_map[x]["codigo_grupo"])
    excel = st.file_uploader("Importar participantes (.xlsx)", type=["xlsx"])
    if excel and grupo_id:
        participantes = importar_participantes_excel(excel)
        for p in participantes:
            p["grupo_id"] = grupo_id
        supabase.table("participantes").insert(participantes).execute()
        st.success(f"{len(participantes)} participantes importados")

# -------------------
# DOCUMENTOS (Admin / Empresa)
# -------------------
if menu in ["Documentos", "Mis Documentos"]:
    st.subheader("Histórico de Documentos")
    if rol == "admin":
        documentos = supabase.table("documentos").select("*").order("created_at", desc=True).execute().data or []
    else:
        documentos = supabase.table("documentos").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).execute().data or []

    for d in documentos:
        st.write(f"{d.get('created_at')} — {d.get('tipo')} — {d.get('archivo_path')}")
        try:
            signed = supabase.storage.from_(BUCKET_DOC).create_signed_url(d.get("archivo_path"), 3600)
            url = signed.get("signedURL") or signed.get("data", {}).get("signedUrl")
            if url:
                st.markdown(f"[Descargar (1h)]({url})")
        except Exception:
            st.write("No se pudo crear URL temporal para este documento.")

# -------------------
# CERRAR SESIÓN
# -------------------
if st.sidebar.button("Cerrar sesión"):
    supabase.auth.sign_out()
    st.session_state.clear()
    st.experimental_rerun()

