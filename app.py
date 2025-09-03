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

# -------------------
# Configuración
# -------------------
SUPABASE_URL = st.secrets["SUPABASE"]["url"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE"]["anon_key"]
BUCKET_DOC = "documentos"

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -------------------
# Helper para usuario autenticado
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

usuario_uid = get_current_user_auth_id()

# -------------------
# Determinar rol
# -------------------
rol = "empresa"
empresa_id = None
try:
    user = supabase.table("usuarios").select("*").eq("auth_uid", usuario_uid).execute().data
    if user and len(user) > 0:
        user = user[0]
        rol = user.get("rol", "empresa")
        empresa_id = user.get("empresa_id")
except Exception:
    st.warning("No se pudo determinar el rol, por defecto: empresa")

# -------------------
# Título
# -------------------
st.title("Soy tu gestor de formación")

# -------------------
# Menú lateral
# -------------------
if rol == "admin":
    menu = st.sidebar.selectbox("Menú Admin", [
        "Inicio", "Acciones Formativas", "Grupos", "Participantes", 
        "Usuarios / Empresas", "Documentos"
    ])
else:
    menu = st.sidebar.selectbox("Menú Empresa", [
        "Inicio", "Mis Acciones", "Mis Grupos", "Mis Participantes", "Mis Documentos"
    ])

# -------------------
# ADMIN - Inicio
# -------------------
if menu == "Inicio":
    st.subheader("Bienvenido Admin" if rol=="admin" else "Bienvenido Empresa")
    st.write("Usa el menú lateral para navegar.")

# -------------------
# ADMIN - Usuarios / Empresas
# -------------------
if rol == "admin" and menu == "Usuarios / Empresas":
    st.subheader("Gestión de Empresas y Usuarios")
    
    # Formulario alta empresa
    with st.expander("Crear nueva empresa"):
        cif = st.text_input("CIF/NIF")
        razon_social = st.text_input("Razón Social")
        direccion = st.text_input("Dirección")
        poblacion = st.text_input("Población")
        cp = st.text_input("Código Postal")
        email = st.text_input("Email de contacto")
        clave = st.text_input("Clave de acceso para empresa")
        if st.button("Crear Empresa"):
            # Insert en empresas
            supabase.table("empresas").insert([{
                "cif": cif,
                "razon_social": razon_social,
                "direccion": direccion,
                "poblacion": poblacion,
                "cp": cp,
                "email": email,
                "password": clave
            }]).execute()
            st.success("Empresa creada correctamente.")
    
    # Listado de empresas
    empresas = supabase.table("empresas").select("*").execute().data or []
    st.write("Empresas existentes:")
    st.dataframe(empresas)

# -------------------
# ADMIN - Acciones Formativas
# -------------------
if rol=="admin" and menu=="Acciones Formativas":
    st.subheader("Acciones Formativas")
    
    # Formulario creación acción formativa
    with st.expander("Crear acción formativa"):
        tipo_accion = st.selectbox("Tipo acción", ["Propia", "Certificado Profesionalidad"])
        codigo = st.text_input("Código acción")
        nombre = st.text_input("Denominación")
        area = st.selectbox("Área Profesional", ["ADGD - Administración y Auditoría", "Otro"])
        modalidad = st.selectbox("Modalidad", ["Presencial", "Teleformación"])
        horas_presenciales = st.number_input("Horas presenciales", 0)
        horas_teleformacion = st.number_input("Horas teleformación", 0)
        objetivos = st.text_area("Objetivos")
        contenidos = st.text_area("Contenidos")
        if st.button("Crear Acción Formativa"):
            supabase.table("acciones_formativas").insert([{
                "tipo_accion": tipo_accion,
                "codigo": codigo,
                "nombre": nombre,
                "area_profesional": area,
                "modalidad": modalidad,
                "horas_presenciales": horas_presenciales,
                "horas_teleformacion": horas_teleformacion,
                "objetivos": objetivos,
                "contenidos": contenidos
            }]).execute()
            st.success("Acción formativa creada.")

    # Mostrar tabla interactiva de acciones
    acciones = supabase.table("acciones_formativas").select("*").execute().data or []
    st.dataframe(acciones)

# -------------------
# ADMIN - Grupos
# -------------------
if rol=="admin" and menu=="Grupos":
    st.subheader("Grupos")
    acciones = supabase.table("acciones_formativas").select("*").execute().data or []
    accion_map = {a["id"]: a for a in acciones}
    if acciones:
        accion_sel = st.selectbox("Seleccionar Acción", list(accion_map.keys()), format_func=lambda x: accion_map[x]["nombre"])
        codigo_grupo = st.text_input("Código Grupo")
        fecha_inicio = st.date_input("Fecha inicio")
        fecha_fin = st.date_input("Fecha fin")
        if st.button("Crear Grupo"):
            supabase.table("grupos").insert([{
                "codigo_grupo": codigo_grupo,
                "accion_formativa_id": accion_sel,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin
            }]).execute()
            st.success("Grupo creado.")
    grupos = supabase.table("grupos").select("*").execute().data or []
    st.dataframe(grupos)

# -------------------
# ADMIN - Participantes
# -------------------
if rol=="admin" and menu=="Participantes":
    st.subheader("Participantes")
    grupos = supabase.table("grupos").select("*").execute().data or []
    grupo_map = {g["id"]: g for g in grupos}
    if grupos:
        grupo_sel = st.selectbox("Seleccionar Grupo", list(grupo_map.keys()), format_func=lambda x: grupo_map[x]["codigo_grupo"])
        excel = st.file_uploader("Importar participantes (.xlsx)", type=["xlsx"])
        if excel:
            participantes = importar_participantes_excel(excel)
            for p in participantes:
                p["grupo_id"] = grupo_sel
            supabase.table("participantes").insert(participantes).execute()
            st.success(f"{len(participantes)} participantes importados")
    participantes = supabase.table("participantes").select("*").execute().data or []
    st.dataframe(participantes)

# -------------------
# ADMIN - Documentos
# -------------------
if rol=="admin" and menu=="Documentos":
    st.subheader("Documentos")
    documentos = supabase.table("documentos").select("*").order("created_at", desc=True).execute().data or []
    st.dataframe(documentos)

# -------------------
# EMPRESA - Mis Acciones / Grupos / Participantes / Documentos
# -------------------
if rol=="empresa":
    if menu=="Mis Acciones":
        acciones = supabase.table("acciones_formativas").select("*").eq("empresa_id", empresa_id).execute().data or []
        st.dataframe(acciones)
    if menu=="Mis Grupos":
        grupos = supabase.table("grupos").select("*").execute().data or []
        grupos = [g for g in grupos if g.get("accion_formativa_id") in [a["id"] for a in supabase.table("acciones_formativas").select("*").eq("empresa_id", empresa_id).execute().data]]
        st.dataframe(grupos)
    if menu=="Mis Participantes":
        participantes = supabase.table("participantes").select("*").execute().data or []
        participantes = [p for p in participantes if p.get("grupo_id") in [g["id"] for g in supabase.table("grupos").select("*").execute().data]]
        st.dataframe(participantes)
    if menu=="Mis Documentos":
        documentos = supabase.table("documentos").select("*").eq("empresa_id", empresa_id).execute().data or []
        st.dataframe(documentos)
