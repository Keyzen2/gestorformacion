# usuarios_empresas.py
import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("Usuarios y Empresas")

    # ========================
    # Mostrar Usuarios
    # ========================
    if st.button("Ver Usuarios"):
        usuarios = supabase.table("usuarios").select("*").execute().data
        if usuarios:
            st.dataframe(pd.DataFrame(usuarios))
        else:
            st.info("No hay usuarios registrados.")

    # ========================
    # Mostrar Empresas
    # ========================
    if st.button("Ver Empresas"):
        empresas = supabase.table("empresas").select("*").execute().data
        if empresas:
            st.dataframe(pd.DataFrame(empresas))
        else:
            st.info("No hay empresas registradas.")

    # ========================
    # Crear Empresa
    # ========================
    st.markdown("### Crear Empresa")
    with st.form("crear_empresa"):
        nombre = st.text_input("Nombre *")
        cif = st.text_input("CIF")
        direccion = st.text_input("Dirección")
        ciudad = st.text_input("Ciudad")
        provincia = st.text_input("Provincia")
        codigo_postal = st.text_input("Código Postal")
        telefono = st.text_input("Teléfono")
        email = st.text_input("Email")
        representante_nombre = st.text_input("Nombre Representante Legal")
        representante_dni = st.text_input("DNI Representante Legal")
        submitted_empresa = st.form_submit_button("Crear Empresa")

        if submitted_empresa:
            if not nombre:
                st.error("⚠️ El nombre de la empresa es obligatorio.")
            else:
                try:
                    supabase.table("empresas").insert({
                        "nombre": nombre,
                        "cif": cif,
                        "direccion": direccion,
                        "ciudad": ciudad,
                        "provincia": provincia,
                        "codigo_postal": codigo_postal,
                        "telefono": telefono,
                        "email": email,
                        "representante_nombre": representante_nombre,
                        "representante_dni": representante_dni
                    }).execute()
                    st.success(f"✅ Empresa '{nombre}' creada correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear la empresa: {str(e)}")

    # ========================
    # Crear Usuario
    # ========================
    st.markdown("### Crear Usuario")
    with st.form("crear_usuario"):
        email_new = st.text_input("Email")
        nombre_new = st.text_input("Nombre")
        rol_new = st.selectbox("Rol", ["admin", "gestor"])
        
        # Si es gestor, seleccionar empresa
        empresa_id = None
        if rol_new == "gestor":
            empresas_res = supabase.table("empresas").select("id, nombre").execute()
            empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}
            empresa_nombre = st.selectbox("Asignar a Empresa", options=list(empresas_dict.keys()) if empresas_dict else ["No hay empresas"])
            empresa_id = empresas_dict.get(empresa_nombre) if empresas_dict else None

        submitted_user = st.form_submit_button("Crear Usuario")
        if submitted_user:
            if not email_new or not nombre_new:
                st.error("⚠️ Email y nombre son obligatorios.")
            elif rol_new == "gestor" and not empresa_id:
                st.error("⚠️ Debes asignar una empresa al gestor.")
            else:
                try:
                    supabase.table("usuarios").insert({
                        "auth_id": "placeholder_uuid",  # Reemplazar con auth_id real desde Supabase Auth
                        "email": email_new,
                        "nombre": nombre_new,
                        "rol": rol_new,
                        "empresa_id": empresa_id
                    }).execute()
                    st.success(f"✅ Usuario '{nombre_new}' creado correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al crear el usuario: {str(e)}")
