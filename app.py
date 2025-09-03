import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import os
from io import BytesIO
from reportlab.pdfgen import canvas
from lxml import etree

# =======================
# CONFIGURACIÓN SUPABASE
# =======================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    st.error("Error de conexión a Supabase. Revisa URL y KEY.")
    st.stop()

# =======================
# CREAR ADMIN INICIAL SI NO EXISTE
# =======================
admin_email = os.environ.get("ADMIN_EMAIL", "admin@demo.com")
admin_password = os.environ.get("ADMIN_PASSWORD", "demo1234")

res = supabase.table("usuarios").select("*").eq("email", admin_email).execute()
if not res.data:
    # Insertar admin en tabla usuarios
    supabase.table("usuarios").insert([{
        "email": admin_email,
        "nombre": "Administrador",
        "rol": "admin",
        "empresa_id": None
    }]).execute()
    try:
        # Crear en auth
        supabase.auth.sign_up({"email": admin_email, "password": admin_password})
    except Exception as e:
        st.warning(f"No se pudo crear el usuario admin en auth: {e}")

# =======================
# SESIÓN
# =======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None

def logout():
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None
    st.experimental_rerun()

# =======================
# LOGIN
# =======================
if not st.session_state.logged_in:
    st.title("Gestor de Formación - Login")
    with st.form("login_form"):
        email = st.text_input("Usuario (email/CIF)")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Entrar")
    if submitted:
        try:
            user = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if user.user:
                res = supabase.table("usuarios").select("rol,id,nombre,empresa_id").eq("email", email).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.user = res.data[0]
                    st.session_state.role = res.data[0]["rol"]
                    st.experimental_rerun()
        except Exception:
            st.error("Usuario o contraseña incorrectos")

# =======================
# MAIN APP
# =======================
if st.session_state.logged_in:
    st.sidebar.button("Cerrar sesión", on_click=logout)
    st.title(f"Bienvenido {st.session_state.user['nombre']} ({st.session_state.role})")

    # =======================
    # FUNCIONES AUXILIARES
    # =======================
    def generar_pdf(nombre_archivo, contenido="PDF de prueba"):
        buffer = BytesIO()
        c = canvas.Canvas(buffer)
        c.drawString(100, 750, contenido)
        c.save()
        buffer.seek(0)
        return buffer

    def validar_xml(xml_string, xsd_string):
        xml_doc = etree.fromstring(xml_string.encode())
        xsd_doc = etree.fromstring(xsd_string.encode())
        schema = etree.XMLSchema(xsd_doc)
        return schema.validate(xml_doc)

    # =======================
    # PANEL ADMIN
    # =======================
    if st.session_state.role == "admin":
        st.subheader("Panel Admin")

        # Usuarios y Empresas
        st.markdown("### Usuarios y Empresas")
        if st.button("Ver Usuarios"):
            usuarios = supabase.table("usuarios").select("*").execute().data
            st.dataframe(pd.DataFrame(usuarios))
        if st.button("Ver Empresas"):
            empresas = supabase.table("empresas").select("*").execute().data
            st.dataframe(pd.DataFrame(empresas))

        # Acciones Formativas
        st.markdown("### Acciones Formativas")
        acciones = supabase.table("acciones_formativas").select("*").execute().data
        df_acciones = pd.DataFrame(acciones) if acciones else pd.DataFrame()
        anio_filter = st.selectbox("Filtrar por Año", options=[None]+sorted(df_acciones["año"].dropna().unique().tolist()) if not df_acciones.empty else [None])
        estado_filter = st.selectbox("Filtrar por Estado", options=[None]+sorted(df_acciones["estado"].dropna().unique().tolist()) if not df_acciones.empty else [None])
        df_filtered = df_acciones.copy()
        if anio_filter:
            df_filtered = df_filtered[df_acciones["año"] == anio_filter]
        if estado_filter:
            df_filtered = df_filtered[df_acciones["estado"] == estado_filter]
        st.dataframe(df_filtered)

        # Importación Masiva de Participantes
        st.markdown("### Importar Participantes")
        uploaded_file = st.file_uploader("Selecciona archivo .xlsx", type=["xlsx"])
        if uploaded_file:
            df_part = pd.read_excel(uploaded_file)
            batch_size = 50
            for i in range(0, len(df_part), batch_size):
                batch = df_part.iloc[i:i+batch_size].to_dict(orient="records")
                supabase.table("participantes").insert(batch).execute()
            st.success(f"Importados {len(df_part)} participantes en batches de {batch_size}")

        # Generación de Documentos
        st.markdown("### Generar PDF/XML")
        accion_sel = st.selectbox("Selecciona acción formativa", options=df_acciones["id"].tolist() if not df_acciones.empty else [])
        if accion_sel:
            if st.button("Generar PDF"):
                pdf_buffer = generar_pdf("documento.pdf")
                st.download_button("Descargar PDF", pdf_buffer, file_name="documento.pdf")
            if st.button("Generar XML de prueba"):
                xml_string = "<root><accion id='{}'/></root>".format(accion_sel)
                st.code(xml_string)

        # Crear Usuario desde Panel Admin
        st.markdown("### Crear Usuario Nuevo")
        with st.form("crear_usuario_form"):
            nuevo_email = st.text_input("Email")
            nuevo_nombre = st.text_input("Nombre")
            nuevo_rol = st.selectbox("Rol", ["empresa", "admin"])
            password_default = "Demo1234!"
            submit_usuario = st.form_submit_button("Crear Usuario")
        if submit_usuario:
            try:
                # Crear en auth
                supabase.auth.sign_up({"email": nuevo_email, "password": password_default})
                # Insertar en tabla usuarios
                supabase.table("usuarios").insert([{
                    "email": nuevo_email,
                    "nombre": nuevo_nombre,
                    "rol": nuevo_rol,
                    "empresa_id": None
                }]).execute()
                st.success(f"Usuario {nuevo_email} creado con contraseña por defecto: {password_default}")
            except Exception as e:
                st.error(f"No se pudo crear el usuario: {e}")

    # =======================
    # PANEL EMPRESA
    # =======================
    elif st.session_state.role == "empresa":
        st.subheader("Panel Empresa")
        
        # Obtener acciones formativas de la empresa
        acciones = supabase.table("acciones_formativas").select("*") \
            .eq("empresa_id", st.session_state.user["empresa_id"]).execute().data
        df_acciones = pd.DataFrame(acciones) if acciones else pd.DataFrame()
        
        # Filtros por año y estado
        anio_filter = st.selectbox("Filtrar por Año", options=[None]+sorted(df_acciones["año"].dropna().unique().tolist()) if not df_acciones.empty else [None])
        estado_filter = st.selectbox("Filtrar por Estado", options=[None]+sorted(df_acciones["estado"].dropna().unique().tolist()) if not df_acciones.empty else [None])
        
        df_filtered = df_acciones.copy()
        if anio_filter:
            df_filtered = df_filtered[df_acciones["año"] == anio_filter]
        if estado_filter:
            df_filtered = df_filtered[df_acciones["estado"] == estado_filter]
        
        st.markdown("### Mis Acciones Formativas")
        st.dataframe(df_filtered)

        # Listado de participantes de las acciones de la empresa
        st.markdown("### Mis Participantes")
        grupo_ids = [g["id"] for g in acciones] if acciones else []
        if grupo_ids:
            participantes = supabase.table("participantes").select("*").in_("grupo_id", grupo_ids).execute().data
            st.dataframe(pd.DataFrame(participantes))
        else:
            st.info("No hay acciones formativas para mostrar participantes.")

        # Descarga de documentos asociados al usuario
        st.markdown("### Descarga de Documentos")
        documentos = supabase.table("documentos").select("*") \
            .eq("usuario_auth_id", st.session_state.user["id"]).execute().data
        if documentos:
            for doc in documentos:
                file_name = doc["archivo_path"].split("/")[-1]
                signed_url = supabase.storage.from_("documentos").create_signed_url(doc["archivo_path"], 3600)
                url = signed_url.get("signedURL") or (signed_url.get("data") and signed_url["data"].get("signedUrl"))
                if url:
                    st.markdown(f"[{file_name}]({url})", unsafe_allow_html=True)
                else:
                    st.write(doc["archivo_path"])
        else:
            st.info("No hay documentos disponibles para descargar.")
