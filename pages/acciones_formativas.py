import streamlit as st
import pandas as pd
import traceback
from services.alumnos import alta_alumno

def main(supabase, session_state):
    try:
        st.subheader("👥 Usuarios y Empresas")

        # -----------------------
        # Ver usuarios y empresas
        # -----------------------
        col1, col2 = st.columns(2)

        with col1:
            if st.button("📋 Ver Usuarios"):
                usuarios = supabase.table("usuarios").select("*").execute().data
                if usuarios:
                    st.dataframe(pd.DataFrame(usuarios))
                else:
                    st.info("No hay usuarios registrados")

        with col2:
            if st.button("🏢 Ver Empresas"):
                empresas = supabase.table("empresas").select("*").execute().data
                if empresas:
                    st.dataframe(pd.DataFrame(empresas))
                else:
                    st.info("No hay empresas registradas")

        # -----------------------
        # Crear Usuario
        # -----------------------
        if session_state.role != "admin":
            st.warning("🔒 Solo los administradores pueden crear usuarios.")
            return

        st.markdown("### ➕ Crear Usuario")

        if "usuario_creado" not in session_state:
            session_state.usuario_creado = False

        with st.form("crear_usuario", clear_on_submit=True):
            email_new = st.text_input("Email *")
            nombre_new = st.text_input("Nombre *")
            password_new = st.text_input("Contraseña *", type="password")
            rol_new = st.selectbox("Rol", ["admin", "gestor", "alumno"])

            empresa_id = None
            grupo_id = None

            if rol_new == "gestor":
                empresas_res = supabase.table("empresas").select("id, nombre").execute()
                empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}
                if empresas_dict:
                    empresa_nombre = st.selectbox("Empresa asignada *", options=list(empresas_dict.keys()))
                    empresa_id = empresas_dict.get(empresa_nombre)
                else:
                    st.warning("⚠️ No hay empresas creadas. Debes crear una antes de dar de alta un gestor.")
                    st.stop()

            if rol_new == "alumno":
                grupos_res = supabase.table("grupos").select("id, codigo_grupo").execute()
                grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_res.data} if grupos_res.data else {}
                if grupos_dict:
                    grupo_nombre = st.selectbox("Grupo asignado (opcional)", options=["-- Ninguno --"] + list(grupos_dict.keys()))
                    if grupo_nombre != "-- Ninguno --":
                        grupo_id = grupos_dict.get(grupo_nombre)

            submitted_user = st.form_submit_button("Crear Usuario")

            if submitted_user and not session_state.usuario_creado:
                if not email_new or not nombre_new or not password_new:
                    st.error("⚠️ Todos los campos son obligatorios")
                elif rol_new == "gestor" and not empresa_id:
                    st.error("⚠️ Debes asignar una empresa al gestor")
                else:
                    try:
                        if rol_new == "alumno":
                            creado = alta_alumno(
                                supabase,
                                email=email_new,
                                password=password_new,
                                nombre=nombre_new,
                                grupo_id=grupo_id
                            )
                            if creado:
                                session_state.usuario_creado = True
                        else:
                            existe = supabase.table("usuarios").select("id").eq("email", email_new).execute()
                            if existe.data:
                                st.error(f"⚠️ Ya existe un usuario con el email '{email_new}'.")
                            else:
                                auth_res = supabase.auth.sign_up({
                                    "email": email_new,
                                    "password": password_new
                                })
                                if not auth_res.user:
                                    st.error("❌ Error al crear el usuario en Auth.")
                                    return

                                insert_data = {
                                    "auth_id": auth_res.user.id,
                                    "email": email_new,
                                    "nombre": nombre_new,
                                    "rol": rol_new
                                }
                                if empresa_id:
                                    insert_data["empresa_id"] = empresa_id

                                supabase.table("usuarios").insert(insert_data).execute()
                                session_state.usuario_creado = True
                                st.success(f"✅ Usuario '{nombre_new}' creado correctamente")

                        if session_state.usuario_creado:
                            usuarios = supabase.table("usuarios").select("*").execute().data
                            if usuarios:
                                st.dataframe(pd.DataFrame(usuarios))

                    except Exception as e:
                        st.error(f"❌ Error al crear el usuario: {e}")

    except Exception as e:
        st.error(f"💥 Error en usuarios_empresas.main: {e}")
        st.code(traceback.format_exc())

# -----------------------
# Función auxiliar para gestores
# -----------------------
def empresas_only(supabase, session_state):
    try:
        st.subheader("🏢 Mi Empresa")
        empresa_id = session_state.user.get("empresa_id")
        if not empresa_id:
            st.info("No tienes empresa asignada")
            return

        empresa_res = supabase.table("empresas").select("*").eq("id", empresa_id).execute()
        if empresa_res.data:
            st.dataframe(pd.DataFrame(empresa_res.data))
        else:
            st.info("No hay datos de empresa")
    except Exception as e:
        st.error(f"💥 Error en empresas_only: {e}")
        st.code(traceback.format_exc())
