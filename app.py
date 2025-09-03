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
SUPABASE_SERVICE_KEY = st.secrets["SUPABASE"].get("service_role_key")  # opcional, para operaciones server-side
BUCKET_DOC = "documentos"

# Cliente supabase (usar anon key para operaciones de usuario normal)
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Helper para obtener uid del usuario autenticado
def get_current_user_auth_id():
    try:
        resp = supabase.auth.get_user()
        # estructura: {'data': {'user': {...}}} en versiones recientes
        if resp and hasattr(resp, "data") and resp.data and resp.data.get("user"):
            return resp.data["user"]["id"]
        if isinstance(resp, dict) and resp.get("data") and resp["data"].get("user"):
            return resp["data"]["user"]["id"]
    except Exception:
        pass
    # fallback (por si gestionas sesión manualmente)
    return st.session_state.get("user_id")

# UI
st.title("Soy tu gestor de formación")

# --- Autenticación mínima (recomiendo integrar páginas de login con Supabase Auth)
# en este ejemplo, asumimos usuario autenticado y que supabase.auth.get_user() funciona.
usuario_uid = get_current_user_auth_id()

# Mostrar admin panel si es admin (comprobación por la función is_admin en BD)
is_admin_resp = False
try:
    # llamamos a la función SQL is_admin
    r = supabase.rpc("is_admin", {"uid": usuario_uid}).execute()
    if r and getattr(r, "data", None):
        is_admin_resp = bool(r.data)
except Exception:
    pass

# Panel administración
if is_admin_resp:
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

# Selección acción formativa y grupo
acciones = supabase.table("acciones_formativas").select("*").execute().data or []
if not acciones:
    st.info("No hay acciones formativas. Crea una en la base de datos.")
else:
    accion_map = {a["id"]: a for a in acciones}
    accion_id = st.selectbox("Acción formativa", list(accion_map.keys()), format_func=lambda x: accion_map[x]["nombre"])

    grupos = supabase.table("grupos").select("*").eq("accion_formativa_id", accion_id).execute().data or []
    grupo_map = {g["id"]: g for g in grupos}
    if grupos:
        grupo_id = st.selectbox("Grupo", list(grupo_map.keys()), format_func=lambda x: grupo_map[x]["codigo_grupo"])
    else:
        st.info("No hay grupos para esta acción.")
        grupo_id = None

    # Importación masiva de participantes
    excel = st.file_uploader("Importar participantes (.xlsx)", type=["xlsx"])
    if excel and grupo_id:
        participantes = importar_participantes_excel(excel)
        # bulk insert con batching
        BATCH = 200
        for i in range(0, len(participantes), BATCH):
            batch = participantes[i:i+BATCH]
            for p in batch:
                p["grupo_id"] = grupo_id
            supabase.table("participantes").insert(batch).execute()
        st.success(f"{len(participantes)} participantes importados.")

    # Paginación + filtro
    pagina = st.session_state.get("pagina_participantes", 0)
    page_size = 50
    filtro = st.text_input("Buscar por nombre o NIF")

    query = supabase.table("participantes").select("*").eq("grupo_id", grupo_id)
    if filtro:
        # filtro simple por nombre (ajusta si quieres por nif)
        query = query.ilike("nombre", f"%{filtro}%")

    participantes_page = query.range(pagina*page_size, (pagina+1)*page_size - 1).execute().data or []
    st.write(f"Mostrando {len(participantes_page)} participantes (página {pagina+1})")
    for p in participantes_page:
        st.write(f"{p.get('nombre')} — {p.get('nif')}")

    c1, c2 = st.columns(2)
    if c1.button("Anterior") and pagina > 0:
        st.session_state["pagina_participantes"] = pagina - 1
        st.experimental_rerun()
    if c2.button("Siguiente") and len(participantes_page) == page_size:
        st.session_state["pagina_participantes"] = pagina + 1
        st.experimental_rerun()

    # -- Generar / Guardar documentos --
    if st.button("Generar y guardar XML Acción Formativa"):
        accion = supabase.table("acciones_formativas").select("*").eq("id", accion_id).execute().data[0]
        xmlb = generar_xml_accion_formativa(accion)
        # validar con XSD (ruta en secrets)
        if validar_xml(xmlb, st.secrets["FUNDAE"]["xsd_accion_formativa"]):
            # guardar en storage y registrar en documentos
            signed_url, path = guardar_documento_en_storage(
                supabase, BUCKET_DOC, xmlb, f"accion_{accion_id}.xml",
                "AccionFormativa", None, accion_id, usuario_uid
            )
            st.success("XML validado y guardado.")
            st.write("URL temporal (1h):", signed_url)
        else:
            st.error("XML inválido según XSD.")

    if st.button("Generar y guardar XML Inicio Grupo"):
        if not grupo_id:
            st.error("Selecciona un grupo.")
        else:
            grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute().data[0]
            # coger participantes del grupo (sin paginar para generar todo)
            participantes_full = supabase.table("participantes").select("*").eq("grupo_id", grupo_id).execute().data or []
            xmlb = generar_xml_inicio_grupo(grupo, participantes_full)
            if validar_xml(xmlb, st.secrets["FUNDAE"]["xsd_inicio_grupo"]):
                signed_url, path = guardar_documento_en_storage(
                    supabase, BUCKET_DOC, xmlb, f"inicio_grupo_{grupo_id}.xml",
                    "InicioGrupo", grupo_id, accion_id, usuario_uid
                )
                st.success("XML inicio grupo guardado.")
                st.write("URL temporal (1h):", signed_url)
            else:
                st.error("XML inválido según XSD.")

    if st.button("Generar y guardar XML Finalización Grupo"):
        if not grupo_id:
            st.error("Selecciona un grupo.")
        else:
            grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute().data[0]
            participantes_full = supabase.table("participantes").select("*").eq("grupo_id", grupo_id).execute().data or []
            xmlb = generar_xml_finalizacion_grupo(grupo, participantes_full)
            if validar_xml(xmlb, st.secrets["FUNDAE"]["xsd_finalizacion_grupo"]):
                signed_url, path = guardar_documento_en_storage(
                    supabase, BUCKET_DOC, xmlb, f"finalizacion_grupo_{grupo_id}.xml",
                    "FinalizacionGrupo", grupo_id, accion_id, usuario_uid
                )
                st.success("XML finalización guardado.")
                st.write("URL temporal (1h):", signed_url)
            else:
                st.error("XML inválido según XSD.")

    if st.button("Generar y guardar PDF del Grupo"):
        if not grupo_id:
            st.error("Selecciona un grupo.")
        else:
            grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute().data[0]
            participantes_full = supabase.table("participantes").select("*").eq("grupo_id", grupo_id).execute().data or []
            pdfb = generar_pdf_grupo(grupo, participantes_full)
            signed_url, path = guardar_documento_en_storage(
                supabase, BUCKET_DOC, pdfb, f"grupo_{grupo_id}.pdf",
                "PDFGrupo", grupo_id, accion_id, usuario_uid
            )
            st.success("PDF generado y guardado.")
            st.write("URL temporal (1h):", signed_url)

    # -- Histórico de documentos del usuario --
    st.subheader("Histórico de Documentos")
    docs = supabase.table("documentos").select("*").eq("usuario_auth_id", usuario_uid).order("created_at", desc=True).execute().data or []
    for d in docs:
        st.write(f"{d.get('created_at')} — {d.get('tipo')} — {d.get('archivo_path')}")
        # generamos signed url para cada archivo (petición al storage)
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
