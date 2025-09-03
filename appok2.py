# app.py - Gestor Formación v4.0
import streamlit as st
import pandas as pd
from supabase import create_client, Client

# =======================
# CONFIGURACIÓN SUPABASE
# =======================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Gestor Formación", layout="wide")

# =======================
# LOGIN
# =======================
st.title("Gestor de Formación")

email = st.text_input("Email")
password = st.text_input("Contraseña", type="password")
login_btn = st.button("Iniciar sesión")

rol = None
usuario = None

if login_btn:
    try:
        user = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        if user and user.user:
            res = supabase.table("usuarios").select("*").eq("email", email).execute()
            if res.data:
                usuario = res.data[0]
                rol = usuario["rol"]
                st.session_state["usuario"] = usuario
                st.session_state["rol"] = rol
                st.success(f"Bienvenido {usuario['nombre']} ({rol})")
            else:
                st.error("Usuario no encontrado en la tabla.")
        else:
            st.error("Credenciales inválidas.")
    except Exception as e:
        st.error(f"Error al iniciar sesión: {e}")

if "usuario" in st.session_state:
    usuario = st.session_state["usuario"]
    rol = st.session_state["rol"]

# =======================
# PANEL ADMIN
# =======================
if rol == "admin":
    st.subheader("Panel de Administración")

    # Mostrar todos los usuarios
    res = supabase.table("usuarios").select("*").execute()
    if res.data:
        df_users = pd.DataFrame(res.data)
        st.dataframe(df_users)

    st.divider()

    # Crear usuario nuevo
    st.markdown("### Crear nuevo usuario")
    with st.form("crear_usuario"):
        nuevo_email = st.text_input("Email")
        nuevo_nombre = st.text_input("Nombre")
        nuevo_rol = st.selectbox("Rol", ["admin", "empresa", "usuario"])
        nuevo_password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Crear usuario")

        if submitted:
            try:
                # 1) Crear en Supabase Auth
                user = supabase.auth.sign_up({
                    "email": nuevo_email,
                    "password": nuevo_password
                })
                auth_id = user.user.id

                # 2) Insertar en tabla usuarios
                supabase.table("usuarios").insert([{
                    "auth_id": auth_id,
                    "email": nuevo_email,
                    "nombre": nuevo_nombre,
                    "rol": nuevo_rol
                }]).execute()

                st.success(f"Usuario {nuevo_email} creado con éxito.")
                st.experimental_rerun()

            except Exception as e:
                st.error(f"Error al crear usuario: {e}")

    st.divider()

    # Editar / borrar usuarios existentes
    st.markdown("### Editar / Eliminar usuarios")
    if res.data:
        user_to_edit = st.selectbox("Seleccionar usuario", [u["email"] for u in res.data])
        selected_user = next((u for u in res.data if u["email"] == user_to_edit), None)

        if selected_user:
            with st.form("editar_usuario"):
                edit_nombre = st.text_input("Nombre", value=selected_user.get("nombre", ""))
                edit_rol = st.selectbox(
                    "Rol",
                    ["admin", "empresa", "usuario"],
                    index=["admin", "empresa", "usuario"].index(selected_user.get("rol", "usuario"))
                )
                submitted_edit = st.form_submit_button("Guardar cambios")
                delete_btn = st.form_submit_button("Eliminar usuario")

                if submitted_edit:
                    supabase.table("usuarios").update({
                        "nombre": edit_nombre,
                        "rol": edit_rol
                    }).eq("auth_id", selected_user["auth_id"]).execute()
                    st.success("Usuario actualizado.")
                    st.experimental_rerun()

                if delete_btn:
                    supabase.table("usuarios").delete().eq("auth_id", selected_user["auth_id"]).execute()
                    st.success("Usuario eliminado.")
                    st.experimental_rerun()

# =======================
# PANEL EMPRESA
# =======================
elif rol == "empresa":
    st.subheader("Panel Empresa")
    st.info("Aquí irá la gestión de acciones formativas, grupos, participantes y documentos.")

# =======================
# PANEL USUARIO
# =======================
elif rol == "usuario":
    st.subheader("Panel Usuario")
    st.info("Aquí irá la vista de un participante con sus documentos y cursos.")
