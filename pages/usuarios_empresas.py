import streamlit as st
import pandas as pd
from utils import (
    importar_participantes_excel,
    generar_pdf,
    validar_xml,
    generar_xml_accion_formativa,
    generar_xml_inicio_grupo,
    generar_xml_finalizacion_grupo
)

def main(supabase, session_state):
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
                supabase.table("usuarios").insert({
                    "auth_id": "placeholder_uuid",
                    "email": email_new,
                    "nombre": nombre_new,
                    "rol": rol_new
                }).execute()
                st.success("Usuario creado")
            except Exception as e:
                st.error(f"Error: {e}")
