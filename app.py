# app.py
import streamlit as st
import os
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
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
        email = st.text_input("Usuario (email)")
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
        except Exception as e:
            st.error(f"Usuario o contraseña incorrectos: {e}")

# =======================
# MAIN APP
# =======================
if st.session_state.logged_in:
    st.sidebar.button("Cerrar sesión", on_click=logout)
    st.title(f"Bienvenido {st.session_state.user['nombre']} ({st.session_state.role})")

    # =======================
    # PANEL ADMIN
    # =======================
    if st.session_state.role == "admin":
        st.subheader("Panel Admin")

        # --- Usuarios ---
        st.markdown("### Usuarios")
        if st.button("Ver Usuarios"):
            usuarios = supabase.table("usuarios").select("*").execute().data
            st.dataframe(pd.DataFrame(usuarios))

        with st.expander("Crear Nuevo Usuario"):
            new_email = st.text_input("Email")
            new_name = st.text_input("Nombre")
            new_rol = st.selectbox("Rol", ["admin", "empresa"])
            new_password = st.text_input("Contraseña", type="password")
            if st.button("Crear Usuario"):
                try:
                    supabase.auth.admin.create_user({"email": new_email, "password": new_password})
                    # Insertar en tabla usuarios
                    supabase.table("usuarios").insert([{
                        "auth_id": supabase.auth.api.get_user_by_email(new_email).id,
                        "email": new_email,
                        "nombre": new_name,
                        "rol": new_rol
                    }]).execute()
                    st.success("Usuario creado correctamente")
                except Exception as e:
                    st.error(f"No se pudo crear el usuario: {e}")

        # --- Empresas ---
        st.markdown("### Empresas")
        if st.button("Ver Empresas"):
            empresas = supabase.table("empresas").select("*").execute().data
            st.dataframe(pd.DataFrame(empresas))

        with st.expander("Crear Nueva Empresa"):
            emp_name = st.text_input("Nombre Empresa")
            if st.button("Crear Empresa"):
                try:
                    supabase.table("empresas").insert([{"nombre": emp_name}]).execute()
                    st.success("Empresa creada correctamente")
                except Exception as e:
                    st.error(f"No se pudo crear la empresa: {e}")

        # --- Acciones Formativas ---
        st.markdown("### Acciones Formativas")
        acciones = supabase.table("acciones_formativas").select("*").execute().data
        df_acciones = pd.DataFrame(acciones)
        if st.button("Ver Acciones Formativas"):
            st.dataframe(df_acciones)

        with st.expander("Crear Acción Formativa"):
            nombre_accion = st.text_input("Nombre")
            desc_accion = st.text_area("Descripción")
            if st.button("Crear Acción"):
                try:
                    supabase.table("acciones_formativas").insert([{
                        "nombre": nombre_accion,
                        "descripcion": desc_accion
                    }]).execute()
                    st.success("Acción formativa creada correctamente")
                except Exception as e:
                    st.error(f"No se pudo crear la acción: {e}")

        # --- Grupos ---
        st.markdown("### Grupos")
        grupos = supabase.table("grupos").select("*").execute().data
        df_grupos = pd.DataFrame(grupos)
        if st.button("Ver Grupos"):
            st.dataframe(df_grupos)

        with st.expander("Crear Grupo"):
            codigo_grupo = st.text_input("Código Grupo")
            accion_id = st.selectbox("Acción Formativa", df_acciones["id"].tolist() if not df_acciones.empty else [])
            if st.button("Crear Grupo"):
                try:
                    supabase.table("grupos").insert([{
                        "codigo_grupo": codigo_grupo,
                        "accion_formativa_id": accion_id
                    }]).execute()
                    st.success("Grupo creado correctamente")
                except Exception as e:
                    st.error(f"No se pudo crear el grupo: {e}")

        # --- Participantes ---
        st.markdown("### Importar Participantes")
        uploaded_file = st.file_uploader("Selecciona archivo .xlsx", type=["xlsx"])
        if uploaded_file:
            try:
                participantes = importar_participantes_excel(uploaded_file)
                supabase.table("participantes").insert(participantes).execute()
                st.success(f"Importados {len(participantes)} participantes")
            except Exception as e:
                st.error(f"Error al importar participantes: {e}")

        # --- Documentos PDF/XML ---
        st.markdown("### Generar Documentos")
        accion_sel = st.selectbox("Selecciona acción formativa", df_acciones["id"].tolist() if not df_acciones.empty else [])
        if accion_sel:
            if st.button("Generar PDF de Acción"):
                pdf_buffer = generar_pdf_grupo("accion_formativa.pdf")
                st.download_button("Descargar PDF", pdf_buffer, file_name="accion_formativa.pdf")

            if st.button("Generar XML Inicio Grupo"):
                participantes = supabase.table("participantes").select("*").eq("grupo_id", accion_sel).execute().data
                xml_buffer = generar_xml_inicio_grupo({"id": accion_sel}, participantes)
                st.download_button("Descargar XML Inicio", xml_buffer, file_name="inicio_grupo.xml")

            if st.button("Generar XML Finalización Grupo"):
                participantes = supabase.table("participantes").select("*").eq("grupo_id", accion_sel).execute().data
                xml_buffer = generar_xml_finalizacion_grupo({"id": accion_sel}, participantes)
                st.download_button("Descargar XML Finalización", xml_buffer, file_name="finalizacion_grupo.xml")

    # =======================
    # PANEL EMPRESA
    # =======================
    elif st.session_state.role == "empresa":
        st.subheader("Panel Empresa")
        acciones = supabase.table("acciones_formativas").select("*").eq("empresa_id", st.session_state.user["empresa_id"]).execute().data
        df_acciones = pd.DataFrame(acciones)
        st.dataframe(df_acciones)
