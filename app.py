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
        # --- Usuarios y Empresas ---
        st.markdown("### Usuarios y Empresas")
        if st.button("Ver Usuarios"):
            usuarios = supabase.table("usuarios").select("*").execute().data
            st.dataframe(pd.DataFrame(usuarios))
        if st.button("Ver Empresas"):
            empresas = supabase.table("empresas").select("*").execute().data
            st.dataframe(pd.DataFrame(empresas))

        # --- Acciones Formativas ---
        st.markdown("### Acciones Formativas")
        acciones = supabase.table("acciones_formativas").select("*").execute().data
        df_acciones = pd.DataFrame(acciones)
        # Filtros
        anio_filter = st.selectbox("Filtrar por Año", options=[None]+sorted(df_acciones["año"].dropna().unique().tolist()))
        estado_filter = st.selectbox("Filtrar por Estado", options=[None]+sorted(df_acciones["estado"].dropna().unique().tolist()))
        df_filtered = df_acciones.copy()
        if anio_filter:
            df_filtered = df_filtered[df_acciones["año"] == anio_filter]
        if estado_filter:
            df_filtered = df_filtered[df_acciones["estado"] == estado_filter]
        st.dataframe(df_filtered)

        # --- Importación Masiva de Participantes ---
        st.markdown("### Importar Participantes")
        uploaded_file = st.file_uploader("Selecciona archivo .xlsx", type=["xlsx"])
        if uploaded_file:
            df_part = pd.read_excel(uploaded_file)
            batch_size = 50
            for i in range(0, len(df_part), batch_size):
                batch = df_part.iloc[i:i+batch_size].to_dict(orient="records")
                supabase.table("participantes").insert(batch).execute()
            st.success(f"Importados {len(df_part)} participantes en batches de {batch_size}")

        # --- Generación de Documentos ---
        st.markdown("### Generar PDF/XML")
        accion_sel = st.selectbox("Selecciona acción formativa", options=df_acciones["id"].tolist() if not df_acciones.empty else [])
        if accion_sel:
            if st.button("Generar PDF"):
                pdf_buffer = generar_pdf("documento.pdf")
                st.download_button("Descargar PDF", pdf_buffer, file_name="documento.pdf")
            if st.button("Generar XML de prueba"):
                xml_string = "<root><accion id='{}'/></root>".format(accion_sel)
                st.code(xml_string)

    # =======================
    # PANEL EMPRESA
    # =======================
    elif st.session_state.role == "empresa":
        st.subheader("Panel Empresa")
        acciones = supabase.table("acciones_formativas").select("*").eq("empresa_id", st.session_state.user["empresa_id"]).execute().data
        df_acciones = pd.DataFrame(acciones)
        # Filtros
        anio_filter = st.selectbox("Filtrar por Año", options=[None]+sorted(df_acciones["año"].dropna().unique().tolist()))
        estado_filter = st.selectbox("Filtrar por Estado", options=[None]+sorted(df_acciones["estado"].dropna().unique().tolist()))
        df_filtered = df_acciones.copy()
        if anio_filter:
            df_filtered = df_filtered[df_acciones["año"] == anio_filter]
        if estado_filter:
            df_filtered = df_filtered[df_acciones["estado"] == estado_filter]
        st.dataframe(df_filtered)

        st.markdown("### Mis Participantes")
        participantes = supabase.table("participantes").select("*").in_("grupo_id", [g["id"] for g in acciones]).execute().data
        st.dataframe(pd.DataFrame(participantes))

        st.markdown("### Descarga Documentos")
        documentos = supabase.table("documentos").select("*").eq("usuario_auth_id", st.session_state.user["id"]).execute().data
        for doc in documentos:
            st.write(doc["archivo_path"])
