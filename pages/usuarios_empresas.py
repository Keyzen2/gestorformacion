import streamlit as st
import pandas as pd

def main(supabase, session_state):
    # ADMIN FULL
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
        rol_new = st.selectbox("Rol", ["admin", "gestor"])
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

# Solo gestión de empresas para gestores
def empresas_only(supabase, session_state):
    st.subheader("Gestión de Empresas")
    st.markdown("### Crear / Editar Empresa")
    with st.form("crear_empresa"):
        nombre = st.text_input("Nombre Empresa *")
        cif = st.text_input("CIF *")
        direccion = st.text_area("Dirección")
        telefono = st.text_input("Teléfono")
        email = st.text_input("Email")
        representante_nombre = st.text_input("Nombre Representante Legal")
        representante_dni = st.text_input("DNI Representante Legal")
        submitted_empresa = st.form_submit_button("Guardar Empresa")

        if submitted_empresa:
            if not nombre or not cif:
                st.error("⚠️ Nombre y CIF son obligatorios.")
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
                    st.success(f"✅ Empresa '{nombre}' guardada correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al guardar la empresa: {str(e)}")
