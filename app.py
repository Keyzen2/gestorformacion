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
import random, string
from datetime import datetime

# ----------------- CONFIG -----------------
SUPABASE_URL = st.secrets["SUPABASE"]["url"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE"]["anon_key"]
SUPABASE_SERVICE_KEY = st.secrets["SUPABASE"].get("service_role_key")
BUCKET_DOC = "documentos"

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ----------------- HELPERS -----------------
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

def generar_password(longitud=10):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(longitud))

# ----------------- UI -----------------
st.title("Soy tu gestor de formación")
usuario_uid = get_current_user_auth_id()

# ----------------- DETECTAR ROL -----------------
rol = "empresa"
empresa_id = None
try:
    user_db = supabase.table("usuarios").select("*").eq("auth_id", usuario_uid).execute().data
    if user_db and len(user_db) > 0:
        rol = user_db[0]["rol"]
        empresa_id = user_db[0].get("empresa_id")
except Exception:
    st.warning("No se pudo determinar el rol, por defecto: empresa")

# ----------------- PANEL ADMIN -----------------
if rol == "admin":
    st.subheader("Panel Admin")

    # ----- GESTIÓN USUARIOS -----
    st.markdown("### Usuarios existentes")
    usuarios = supabase.table("usuarios").select("*").execute().data or []
    for u in usuarios:
        st.write(f"{u.get('nombre')} - {u.get('email')} - rol: {u.get('rol')}")

    with st.form("cambiar_rol"):
        email_cambiar = st.text_input("Email a cambiar")
        nuevo_rol = st.selectbox("Nuevo rol", ["empresa", "admin"])
        if st.form_submit_button("Actualizar rol"):
            supabase.table("usuarios").update({"rol": nuevo_rol}).eq("email", email_cambiar).execute()
            st.success("Rol actualizado")

    # ----- CREAR EMPRESA -----
    st.markdown("### Dar de alta nueva empresa")
    with st.form("crear_empresa"):
        cif = st.text_input("CIF/NIF")
        razon_social = st.text_input("Razón Social")
        direccion = st.text_input("Dirección")
        poblacion = st.text_input("Población")
        cp = st.text_input("Código Postal")
        email = st.text_input("Email de contacto")
        if st.form_submit_button("Crear empresa"):
            empresa_res = supabase.table("empresas").insert({
                "cif": cif,
                "razon_social": razon_social,
                "direccion": direccion,
                "poblacion": poblacion,
                "codigo_postal": cp,
                "email": email
            }).execute()
            if empresa_res.data and len(empresa_res.data) > 0:
                nueva_empresa_id = empresa_res.data[0]["id"]
                password = generar_password()
                auth_res = supabase.auth.admin.create_user({
                    "email": email,
                    "password": password,
                    "user_metadata": {"empresa_id": str(nueva_empresa_id)}
                })
                auth_id = auth_res.user.id if hasattr(auth_res, "user") else auth_res["id"]
                supabase.table("usuarios").insert({
                    "auth_id": auth_id,
                    "rol": "empresa",
                    "empresa_id": nueva_empresa_id,
                    "email": email,
                    "nombre": razon_social
                }).execute()
                st.success(f"Empresa creada y usuario generado. Contraseña: {password}")
            else:
                st.error("Error al crear la empresa")

# ----------------- PANEL EMPRESA -----------------
if rol == "empresa":
    st.subheader("Mis acciones formativas")
    acciones = supabase.table("acciones_formativas").select("*").eq("empresa_id", empresa_id).execute().data or []
    if not acciones:
        st.info("No tienes acciones formativas.")
    else:
        anios = sorted(list({datetime.fromisoformat(a["created_at"]).year for a in acciones}))
        anio_seleccionado = st.selectbox("Filtrar por año", anios)
        acciones_filtradas = [a for a in acciones if datetime.fromisoformat(a["created_at"]).year == anio_seleccionado]

        accion_map = {a["id"]: a for a in acciones_filtradas}
        accion_id = st.selectbox("Acción formativa", list(accion_map.keys()), format_func=lambda x: accion_map[x]["nombre"])

        grupos = supabase.table("grupos").select("*").eq("accion_formativa_id", accion_id).execute().data or []
        if grupos:
            grupo_map = {g["id"]: g for g in grupos}
            grupo_id = st.selectbox("Grupo", list(grupo_map.keys()), format_func=lambda x: grupo_map[x]["codigo_grupo"])
        else:
            st.info("No hay grupos para esta acción.")
            grupo_id = None

        participantes = supabase.table("participantes").select("*").eq("grupo_id", grupo_id).execute().data or []
        st.markdown("#### Participantes")
        for p in participantes:
            st.write(f"{p.get('nombre')} — {p.get('nif')}")

        st.subheader("Documentos generados para mi empresa")
        docs = supabase.table("documentos").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).execute().data or []
        for d in docs:
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

# ----------------- PANEL ADMIN: ACCIONES, GRUPOS, PARTICIPANTES, DOCUMENTOS -----------------
if rol == "admin":
    st.subheader("Gestión completa de acciones formativas y documentos")

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

        excel = st.file_uploader("Importar participantes (.xlsx)", type=["xlsx"])
        if excel and grupo_id:
            participantes = importar_participantes_excel(excel)
            BATCH = 200
            for i in range(0, len(participantes), BATCH):
                batch = participantes[i:i+BATCH]
                for p in batch:
                    p["grupo_id"] = grupo_id
                supabase.table("participantes").insert(batch).execute()
            st.success(f"{len(participantes)} participantes importados.")

        pagina = st.session_state.get("pagina_participantes", 0)
        page_size = 50
        filtro = st.text_input("Buscar por nombre o NIF")
        query = supabase.table("participantes").select("*").eq("grupo_id", grupo_id)
        if filtro:
            query = query.ilike("nombre", f"%{filtro}%")
        participantes_page = query.range(pagina*page_size, (pagina+1)*page_size-1).execute().data or []
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

        # Generación XML/PDF
        if st.button("Generar y guardar XML Acción Formativa"):
            accion = supabase.table("acciones_formativas").select("*").eq("id", accion_id).execute().data[0]
            xmlb = generar_xml_accion_formativa(accion)
            if validar_xml(xmlb, st.secrets["FUNDAE"]["xsd_accion_formativa"]):
                signed_url, path = guardar_documento_en_storage(supabase, BUCKET_DOC, xmlb, f"accion_{accion_id}.xml",
                                                                 "AccionFormativa", None, accion_id, usuario_uid)
                st.success("XML validado y guardado.")
                st.write("URL temporal (1h):", signed_url)
            else:
                st.error("XML inválido según XSD.")

        if st.button("Generar y guardar XML Inicio Grupo"):
            if not grupo_id:
                st.error("Selecciona un grupo.")
            else:
                grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute().data[0]
                participantes_full = supabase.table("participantes").select("*").eq("grupo_id", grupo_id).execute().data or []
                xmlb = generar_xml_inicio_grupo(grupo, participantes_full)
                if validar_xml(xmlb, st.secrets["FUNDAE"]["xsd_inicio_grupo"]):
                    signed_url, path = guardar_documento_en_storage(supabase, BUCKET_DOC, xmlb, f"inicio_grupo_{grupo_id}.xml",
                                                                     "InicioGrupo", grupo_id, accion_id, usuario_uid)
                    st.success("XML inicio grupo guardado.")
                    st.write("URL temporal (1h):", signed_url)
                else:
                    st.error
