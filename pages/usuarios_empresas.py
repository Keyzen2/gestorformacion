import streamlit as st
import pandas as pd
from services.alumnos import alta_alumno

def main(supabase, session_state):
    st.subheader("👥 Gestión de Usuarios y Empresas")
    st.caption("Consulta y creación de usuarios vinculados a empresas y grupos.")

    # =========================
    # Visualización de datos
    # =========================
    with st.expander("📋 Ver Usuarios"):
        usuarios = supabase.table("usuarios").select("*").execute().data
        if usuarios:
            st.dataframe(pd.DataFrame(usuarios))
        else:
            st.info("ℹ️ No hay usuarios registrados.")

    st.divider()

    with st.expander("🏢 Ver Empresas"):
        empresas = supabase.table("empresas").select("*").execute().data
        if empresas:
            st.dataframe(pd.DataFrame(empresas))
        else:
            st.info("ℹ️ No hay empresas registradas.")

    st.divider()

    # =========================
    # Alta de usuarios
    # =========================
    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden crear usuarios.")
        return

    st.markdown("### ➕ Crear Usuario")

    if "usuario_creado" not in st.session_state:
        st.session_state.usuario_creado = False

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

        if submitted_user and not st.session_state.usuario_creado:
            if not email_new or not nombre_new or not password_new:
                st.error("⚠️ Todos los campos son obligatorios.")
            elif rol_new == "gestor" and not empresa_id:
                st.error("⚠️ Debes asignar una empresa al gestor.")
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
                            st.session_state.usuario_creado = True
                    else:
                        existe = supabase.table("usuarios").select("id").eq("email", email_new).execute()
                        if existe.data:
                            st.error(f"⚠️ Ya existe un usuario con el email '{email_new}'.")
                        else:
                            auth_res = supabase.auth.admin.create_user({
                                "email": email_new,
                                "password": password_new,
                                "email_confirm": True
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
                            st.session_state.usuario_creado = True
                            st.success(f"✅ Usuario '{nombre_new}' creado correctamente.")

                    if st.session_state.usuario_creado:
                        st.markdown("### 👤 Usuarios actualizados")
                        usuarios = supabase.table("usuarios").select("*").execute().data
                        if usuarios:
                            st.dataframe(pd.DataFrame(usuarios))

                except Exception as e:
                    st.error(f"❌ Error al crear el usuario: {e}")

def empresas_only(supabase, session_state):
    st.subheader("🏢 Mi Empresa")
    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.info("ℹ️ No tienes empresa asignada.")
        return

    empresa_res = supabase.table("empresas").select("*").eq("id", empresa_id).execute()
    if empresa_res.data:
        st.dataframe(pd.DataFrame(empresa_res.data))
    else:
        st.info("ℹ️ No hay datos de empresa.")
        
