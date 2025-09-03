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

# -------------------
# CONFIG
# -------------------
SUPABASE_URL = st.secrets["SUPABASE"]["url"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE"]["anon_key"]
SUPABASE_SERVICE_KEY = st.secrets["SUPABASE"].get("service_role_key")
BUCKET_DOC = "documentos"

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -------------------
# AUTENTICACIÓN Y ROLES
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

def get_usuario_data(uid):
    usuarios = supabase.table("usuarios").select("*").eq("auth_id", uid).execute().data or []
    return usuarios[0] if usuarios else None

usuario_uid = get_current_user_auth_id()

# FORZAR ADMIN (si quieres sobreescribir, puedes poner aquí el UID)
FORZAR_ADMIN_UID = None  # ejemplo: "xxxx-xxxx-xxxx"
if FORZAR_ADMIN_UID:
    usuario_uid = FORZAR_ADMIN_UID

usuario_data = get_usuario_data(usuario_uid)
rol = usuario_data.get("rol") if usuario_data else "empresa"
empresa_id = usuario_data.get("empresa_id") if usuario_data else None

st.title("Soy tu gestor de formación")

# -------------------
# BOTÓN CERRAR SESIÓN
# -------------------
if st.sidebar.button("Cerrar sesión"):
    supabase.auth.sign_out()
    st.session_state.clear()
    st.experimental_rerun()

# -------------------
# MENÚ LATERAL
# -------------------
if rol == "admin":
    menu = st.sidebar.selectbox("Menú", [
        "Panel Admin",
        "Acciones Formativas",
        "Grupos",
        "Participantes",
        "Usuarios y Empresas",
        "Documentos"
    ])
else:
    menu = st.sidebar.selectbox("Menú", [
        "Mis Acciones",
        "Mis Grupos",
        "Mis Participantes",
        "Mis Documentos"
    ])

# -------------------
# PANEL ADMIN
# -------------------
if rol == "admin" and menu == "Panel Admin":
    st.subheader("Panel Admin - Usuarios y Empresas")
    usuarios = supabase.table("usuarios").select("*").execute().data or []
    for u in usuarios:
        st.write(f"{u.get('nombre')} - {u.get('email')} - rol: {u.get('rol')} - empresa_id: {u.get('empresa_id')}")
    
    with st.form("crear_empresa"):
        st.write("Dar de alta empresa")
        cif = st.text_input("CIF / NIF")
        razon_social = st.text_input("Razón Social")
        direccion = st.text_input("Dirección")
        poblacion = st.text_input("Población")
        cp = st.text_input("Código Postal")
        email = st.text_input("Email")
        password = st.text_input("Clave inicial", type="password")
        if st.form_submit_button("Crear Empresa"):
            # Crear usuario Auth en Supabase
            user_auth = supabase.auth.sign_up({"email": email, "password": password})
            auth_id = user_auth.user.id if user_auth and hasattr(user_auth, "user") else None
            # Insertar en tabla usuarios
            supabase.table("usuarios").insert([{
                "nombre": razon_social,
                "email": email,
                "rol": "empresa",
                "empresa_id": None,
                "auth_id": auth_id
            }]).execute()
            st.success("Empresa creada")

# -------------------
# ACCIONES FORMATIVAS
# -------------------
if (rol == "admin" and menu == "Acciones Formativas") or (rol == "empresa" and menu == "Mis Acciones"):
    st.subheader("Acciones Formativas")
    query = supabase.table("acciones_formativas").select("*").order("created_at", desc=True)
    if rol == "empresa" and empresa_id:
        query = query.eq("empresa_id", empresa_id)
    acciones = query.execute().data or []

    if acciones:
        gb = GridOptionsBuilder.from_dataframe(acciones)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(editable=False, groupable=True)
        AgGrid(acciones, gridOptions=gb.build(), update_mode=GridUpdateMode.NO_UPDATE)
    else:
        st.info("No hay acciones formativas.")

    if rol == "admin":
        with st.form("crear_accion"):
            st.write("Crear nueva acción formativa")
            tipo = st.selectbox("Tipo de acción", ["Propia", "Certificado profesionalidad"])
            codigo = st.text_input("Código acción")
            denominacion = st.text_input("Denominación")
            area_profesional = st.selectbox("Área profesional", ["ADGD - ADMINISTRACIÓN Y AUDITORÍA", "Otra"])
            modalidad = st.selectbox("Modalidad", ["Presencial", "Teleformación"])
            horas_presenciales = st.number_input("Horas presenciales", min_value=0)
            horas_teleformacion = st.number_input("Horas teleformación", min_value=0)
            objetivos = st.text_area("Objetivos")
            contenidos = st.text_area("Contenidos")
            if st.form_submit_button("Crear acción"):
                supabase.table("acciones_formativas").insert([{
                    "tipo": tipo,
                    "codigo": codigo,
                    "denominacion": denominacion,
                    "area_profesional": area_profesional,
                    "modalidad": modalidad,
                    "horas_presenciales": horas_presenciales,
                    "horas_teleformacion": horas_teleformacion,
                    "objetivos": objetivos,
                    "contenidos": contenidos,
                    "empresa_id": None
                }]).execute()
                st.success("Acción formativa creada.")

# -------------------
# GRUPOS + PARTICIPANTES + XML/PDF
# -------------------
if (rol == "admin" and menu in ["Grupos","Participantes","Documentos"]) or (rol == "empresa" and menu in ["Mis Grupos","Mis Participantes","Mis Documentos"]):
    # Selección acción y grupo
    acciones_list = supabase.table("acciones_formativas").select("*").execute().data or []
    accion_map = {a["id"]: a for a in acciones_list}
    if not acciones_list:
        st.info("No hay acciones formativas.")
    else:
        accion_id = st.selectbox("Acción Formativa", list(accion_map.keys()), format_func=lambda x: accion_map[x]["denominacion"])
        grupos_list = supabase.table("grupos").select("*").eq("accion_formativa_id", accion_id).execute().data or []
        grupo_map = {g["id"]: g for g in grupos_list}
        if grupos_list:
            grupo_id = st.selectbox("Grupo", list(grupo_map.keys()), format_func=lambda x: grupo_map[x]["codigo_grupo"])
        else:
            st.info("No hay grupos")
            grupo_id = None

        # IMPORTACIÓN PARTICIPANTES (solo admin)
        if rol == "admin" and grupo_id:
            excel = st.file_uploader("Importar participantes (.xlsx)", type=["xlsx"])
            if excel:
                participantes = importar_participantes_excel(excel)
                BATCH = 200
                for i in range(0, len(participantes), BATCH):
                    batch = participantes[i:i+BATCH]
                    for p in batch:
                        p["grupo_id"] = grupo_id
                    supabase.table("participantes").insert(batch).execute()
                st.success(f"{len(participantes)} participantes importados.")

        # GENERAR DOCUMENTOS (solo admin)
if rol == "admin" and grupo_id:
    grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute().data[0]
    participantes_full = supabase.table("participantes").select("*").eq("grupo_id", grupo_id).execute().data or []

    if st.button("Generar XML Acción Formativa"):
        xmlb = generar_xml_accion_formativa(accion_map[accion_id])
        if validar_xml(xmlb, st.secrets["FUNDAE"]["xsd_accion_formativa"]):
            signed_url, path = guardar_documento_en_storage(
                supabase, BUCKET_DOC, xmlb, f"accion_{accion_id}.xml",
                "AccionFormativa", None, accion_id, usuario_uid
            )
            st.success("XML Acción Formativa guardado")
            st.write("URL temporal (1h):", signed_url)

    if st.button("Generar XML Inicio Grupo"):
        xmlb = generar_xml_inicio_grupo(grupo, participantes_full)
        if validar_xml(xmlb, st.secrets["FUNDAE"]["xsd_inicio_grupo"]):
            signed_url, path = guardar_documento_en_storage(
                supabase, BUCKET_DOC, xmlb, f"inicio_grupo_{grupo_id}.xml",
                "InicioGrupo", grupo_id, accion_id, usuario_uid
            )
            st.success("XML Inicio Grupo guardado")
            st.write("URL temporal (1h):", signed_url)

    if st.button("Generar XML Finalización Grupo"):
        xmlb = generar_xml_finalizacion_grupo(grupo, participantes_full)
        if validar_xml(xmlb, st.secrets["FUNDAE"]["xsd_finalizacion_grupo"]):
            signed_url, path = guardar_documento_en_storage(
                supabase, BUCKET_DOC, xmlb, f"finalizacion_grupo_{grupo_id}.xml",
                "FinalizacionGrupo", grupo_id, accion_id, usuario_uid
            )
            st.success("XML Finalización Grupo guardado")
            st.write("URL temporal (1h):", signed_url)

    if st.button("Generar PDF Grupo"):
        pdfb = generar_pdf_grupo(grupo, participantes_full)
        signed_url, path = guardar_documento_en_storage(
            supabase, BUCKET_DOC, pdfb, f"grupo_{grupo_id}.pdf",
            "PDFGrupo", grupo_id, accion_id, usuario_uid
        )
        st.success("PDF Grupo generado")
        st.write("URL temporal (1h):", signed_url)

# -------------------
# HISTÓRICO DOCUMENTOS
# -------------------
st.subheader("Histórico de Documentos")
if rol == "admin":
    documentos = supabase.table("documentos").select("*").order("created_at", desc=True).execute().data or []
else:
    documentos = supabase.table("documentos").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).execute().data or []

for d in documentos:
    st.write(f"{d.get('created_at')} — {d.get('tipo')} — {d.get('archivo_path')}")
    try:
        signed = supabase.storage.from_(BUCKET_DOC).create_signed_url(d.get("archivo_path"), 3600)
        url = None
        if signed and isinstance(signed, dict):
            if "signedURL" in signed:
                url = signed["signedURL"]
            elif "data" in signed and isinstance(signed["data"], dict):
                url = signed["data"].get("signedUrl") or signed["data"].get("signedURL")
        if url:
            st.markdown(f"[Descargar (1h)]({url})")
    except Exception:
        st.write("No se pudo crear URL temporal para este documento.")


