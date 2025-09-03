# usuarios_empresas.py
import streamlit as st
import pandas as pd
from utils import importar_participantes_excel

def main(supabase, session_state):
    st.subheader("Usuarios y Empresas")

    # =======================
    # VISUALIZAR DATOS
    # =======================
    if st.button("Ver Usuarios"):
        usuarios = supabase.table("usuarios").select("*").execute().data
        if usuarios:
            st.dataframe(pd.DataFrame(usuarios))
        else:
            st.info("No hay usuarios registrados.")

    if st.button("Ver Empresas"):
        empresas = supabase.table("empresas").select("*").execute().data
        if empresas:
            st.dataframe(pd.DataFrame(empresas))
        else:
            st.info("No hay empresas registradas.")

    # =======================
    # CREAR USUARIO
    # =======================
    st.markdown("### Crear Usuario")
    with st.form("crear_usuario"):
        email_new = st.text_input("Email")
        nombre_new = st.text_input("Nombre completo")
        rol_new = st.selectbox("Rol", ["admin", "gestor", "empresa"])
        empresa_id_new = st.text_input("Empresa ID (opcional, solo para gestores/empresa)")
        submitted_user = st.form_submit_button("Crear Usuario")

        if submitted_user:
            if not email_new or not nombre_new or not rol_new:
                st.error("⚠️ Email, nombre y rol son obligatorios.")
            else:
                try:
                    supabase.table("usuarios").insert({
                        "auth_id": "placeholder_uuid",  # sustituir con auth_id real si se crea en auth
                        "email": email_new,
                        "nombre": nombre_new,
                        "rol": rol_new,
                        "empresa_id": empresa_id_new or None
                    }).execute()
                    st.success("Usuario creado correctamente.")
                except Exception as e:
                    st.error(f"Error al crear usuario: {e}")

    # =======================
    # CREAR EMPRESA
    # =======================
    st.markdown("### Crear Empresa")
    with st.form("crear_empresa"):
        nombre = st.text_input("Nombre empresa")
        cif = st.text_input("CIF")
        direccion = st.text_input("Dirección")
        telefono = st.text_input("Teléfono (opcional)")
        email = st.text_input("Email (opcional)")
        representante_nombre = st.text_input("Nombre representante legal")
        representante_dni = st.text_input("DNI representante legal")
        submitted_empresa = st.form_submit_button("Crear Empresa")

        if submitted_empresa:
            if not nombre or not cif or not direccion or not representante_nombre or not representante_dni:
                st.error("⚠️ Todos los campos obligatorios deben completarse.")
            else:
                try:
                    supabase.table("empresas").insert({
                        "nombre": nombre,
                        "cif": cif,
                        "direccion": direccion,
                        "telefono": telefono,
                        "email": email,
                        "representante_nombre": representante_nombre,
                        "representante_dni": representante_dni
                    }).execute()
                    st.success(f"✅ Empresa '{nombre}' creada correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear empresa: {e}")
