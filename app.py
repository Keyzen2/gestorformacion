# app.py
import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import os
from io import BytesIO
from reportlab.pdfgen import canvas
from lxml import etree
from utils import (
    importar_participantes_excel,
    generar_pdf_grupo,
    generar_xml_accion_formativa,
    generar_xml_inicio_grupo,
    generar_xml_finalizacion_grupo
)

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
                res = supabase.table("usuarios").select("*").eq("email", email).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.user = res.data[0]
                    st.session_state.role = res.data[0]["rol"]
                    st.experimental_rerun()
        except Exception:
            st.error("Usuario o contraseña incorrectos")

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
# APP PRINCIPAL
# =======================
if st.session_state.get("logged_in"):
    user_data = st.session_state.get("user", {})
    nombre_usuario = user_data.get("nombre") or user_data.get("email") or "Usuario"
    st.sidebar.title(f"Bienvenido {nombre_usuario}")
    st.sidebar.button("Cerrar sesión", on_click=logout)
    
    # =======================
    # MENÚ LATERAL
    # =======================
    opciones = ["Usuarios y Empresas", "Acciones Formativas", "Grupos", "Participantes", "Documentos"]
    menu = st.sidebar.radio("Menú", opciones)

    # =======================
    # PANEL ADMIN
    # =======================
    if st.session_state.role == "admin":

        if menu == "Usuarios y Empresas":
            st.subheader("Usuarios y Empresas")
            if st.button("Ver Usuarios"):
                usuarios = supabase.table("usuarios").select("*").execute().data
                st.dataframe(pd.DataFrame(usuarios))

            if st.button("Ver Empresas"):
                empresas = supabase.table("empresas").select("*").execute().data
                st.dataframe(pd.DataFrame(empresas))

            st.markdown("### Crear Usuario")
            with st.form("crear_usuario"):
                email_new = st.text_input("Email")
                nombre_new = st.text_input("Nombre")
                rol_new = st.selectbox("Rol", ["admin", "empresa"])
                submitted_user = st.form_submit_button("Crear Usuario")
                if submitted_user:
                    try:
                        # Insertar usuario en tabla usuarios (suponiendo que auth_id ya existe en auth)
                        supabase.table("usuarios").insert({
                            "auth_id": "placeholder_uuid",  # reemplazar con auth_id real
                            "email": email_new,
                            "nombre": nombre_new,
                            "rol": rol_new
                        }).execute()
                        st.success("Usuario creado")
                    except Exception as e:
                        st.error(f"Error: {e}")

        elif menu == "Acciones Formativas":
            st.subheader("Acciones Formativas")
            acciones = supabase.table("acciones_formativas").select("*").execute().data
            df_acciones = pd.DataFrame(acciones)
            anio_filter = st.selectbox("Filtrar por Año", options=[None]+sorted(df_acciones["fecha_inicio"].dt.year.dropna().unique().tolist()) if not df_acciones.empty else [])
            df_filtered = df_acciones.copy()
            if anio_filter:
                df_filtered = df_filtered[df_acciones["fecha_inicio"].dt.year == anio_filter]
            st.dataframe(df_filtered)

            st.markdown("### Crear Acción Formativa")
            with st.form("crear_accion"):
                nombre_accion = st.text_input("Nombre")
                descripcion_accion = st.text_area("Descripción")
                fecha_inicio = st.date_input("Fecha Inicio")
                fecha_fin = st.date_input("Fecha Fin")
                empresa_id_sel = st.text_input("Empresa ID")
                submitted_accion = st.form_submit_button("Crear Acción")
                if submitted_accion:
                    supabase.table("acciones_formativas").insert({
                        "nombre": nombre_accion,
                        "descripcion": descripcion_accion,
                        "fecha_inicio": fecha_inicio,
                        "fecha_fin": fecha_fin,
                        "empresa_id": empresa_id_sel
                    }).execute()
                    st.success("Acción formativa creada")

        elif menu == "Grupos":
            st.subheader("Grupos")
            grupos = supabase.table("grupos").select("*").execute().data
            st.dataframe(pd.DataFrame(grupos))

            st.markdown("### Crear Grupo")
            with st.form("crear_grupo"):
                codigo_grupo = st.text_input("Código Grupo")
                fecha_inicio = st.date_input("Fecha Inicio")
                fecha_fin = st.date_input("Fecha Fin")
                accion_formativa_id = st.text_input("ID Acción Formativa")
                empresa_id_sel = st.text_input("Empresa ID")
                submitted_grupo = st.form_submit_button("Crear Grupo")
                if submitted_grupo:
                    supabase.table("grupos").insert({
                        "codigo_grupo": codigo_grupo,
                        "fecha_inicio": fecha_inicio,
                        "fecha_fin": fecha_fin,
                        "accion_formativa_id": accion_formativa_id,
                        "empresa_id": empresa_id_sel
                    }).execute()
                    st.success("Grupo creado")

        elif menu == "Participantes":
            st.subheader("Importar Participantes")
            uploaded_file = st.file_uploader("Selecciona archivo .xlsx", type=["xlsx"])
            if uploaded_file:
                df_part = pd.read_excel(uploaded_file)
                batch_size = 50
                for i in range(0, len(df_part), batch_size):
                    batch = df_part.iloc[i:i+batch_size].to_dict(orient="records")
                    supabase.table("participantes").insert(batch).execute()
                st.success(f"Importados {len(df_part)} participantes en batches de {batch_size}")

        elif menu == "Documentos":
            st.subheader("Generar Documentos")
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
        st.dataframe(df_acciones)
