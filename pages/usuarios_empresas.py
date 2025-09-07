import streamlit as st
import pandas as pd
from datetime import datetime
from services.alumnos import alta_alumno

def main(supabase, session_state):
    st.title("👥 Gestión de Usuarios")
    st.caption("Consulta, creación, edición y eliminación de usuarios registrados en la plataforma.")

    # =========================
    # Cargar usuarios
    # =========================
    usuarios_res = supabase.table("usuarios").select("*").execute()
    usuarios = pd.DataFrame(usuarios_res.data) if usuarios_res.data else pd.DataFrame()

    if usuarios.empty:
        st.info("ℹ️ No hay usuarios registrados.")
        return

    # =========================
    # Filtro y resumen
    # =========================
    search_query = st.text_input("🔍 Buscar por nombre o email")
    usuarios_filtrados = usuarios.copy()
    if search_query:
        usuarios_filtrados = usuarios_filtrados[
            usuarios_filtrados["nombre"].str.contains(search_query, case=False, na=False) |
            usuarios_filtrados["email"].str.contains(search_query, case=False, na=False)
        ]

    st.download_button(
        "⬇️ Descargar CSV",
        usuarios_filtrados.to_csv(index=False).encode("utf-8"),
        file_name="usuarios.csv",
        mime="text/csv"
    )

    st.markdown("### 📋 Usuarios registrados")
    for _, row in usuarios_filtrados.iterrows():
        rol_icon = {"admin": "🛠️", "gestor": "📋", "alumno": "🎓"}
        icon = rol_icon.get(row["rol"], "👤")

        with st.expander(f"{icon} {row['nombre']} ({row['email']})", expanded=False):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"**🆔 ID:** {row['id']}")
                st.markdown(f"**📧 Email:** {row['email']}")
                st.markdown(f"**🎓 Rol:** {row['rol'].capitalize()}")
                if row.get("empresa_id"):
                    st.markdown(f"**🏢 Empresa ID:** {row['empresa_id']}")
                if row.get("grupo_id"):
                    st.markdown(f"**👥 Grupo ID:** {row['grupo_id']}")
                st.markdown(f"**📅 Alta:** {row.get('created_at', '—')}")

            with col2:
                tab1, tab2 = st.tabs(["✏️ Editar", "🗑️ Eliminar"])
                with tab1:
                    with st.form(f"edit_user_{row['id']}", clear_on_submit=False):
                        nombre_new = st.text_input("Nombre", value=row.get("nombre", ""))
                        email_new = st.text_input("Email", value=row.get("email", ""))
                        rol_new = st.selectbox("Rol", ["admin", "gestor", "alumno"], index=["admin", "gestor", "alumno"].index(row.get("rol", "usuario")))

                        empresa_id_new = row.get("empresa_id")
                        grupo_id_new = row.get("grupo_id")

                        if rol_new == "gestor":
                            empresa_id_new = st.text_input("Empresa ID asignada", value=str(empresa_id_new or ""), help="Solo el ID. La gestión de empresas se realiza en empresas.py")

                        if rol_new == "alumno":
                            grupo_id_new = st.text_input("Grupo ID asignado", value=str(grupo_id_new or ""), help="Solo el ID. La gestión de grupos se realiza en grupos.py")

                        guardar = st.form_submit_button("💾 Guardar cambios")
                        if guardar:
                            try:
                                supabase.table("usuarios").update({
                                    "nombre": nombre_new,
                                    "email": email_new,
                                    "rol": rol_new,
                                    "empresa_id": empresa_id_new if empresa_id_new else None,
                                    "grupo_id": grupo_id_new if grupo_id_new else None
                                }).eq("id", row["id"]).execute()
                                st.success("✅ Usuario actualizado correctamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al actualizar: {str(e)}")

                with tab2:
                    relaciones = []
                    if row["rol"] == "gestor" and row.get("empresa_id"):
                        relaciones.append("empresa asignada")
                    if row["rol"] == "alumno" and row.get("grupo_id"):
                        relaciones.append("grupo asignado")

                    if relaciones:
                        st.warning(f"⚠️ No se puede eliminar este usuario. Está vinculado a: {', '.join(relaciones)}")
                    else:
                        if st.button(f"🗑️ Eliminar usuario {row['nombre']}", key=f"del_{row['id']}"):
                            try:
                                supabase.table("usuarios").delete().eq("id", row["id"]).execute()
                                st.success("✅ Usuario eliminado correctamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al eliminar usuario: {str(e)}")

    # =========================
    # Crear nuevo usuario
    # =========================
    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden crear usuarios.")
        return

    st.markdown("### ➕ Crear nuevo usuario")
    with st.expander("Formulario de alta", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            email_new = st.text_input("📧 Email *")
            nombre_new = st.text_input("👤 Nombre *")
            password_new = st.text_input("🔒 Contraseña *", type="password")
        with col2:
            rol_new = st.selectbox("🎓 Rol", ["admin", "gestor", "alumno"])
            empresa_id_new = None
            grupo_id_new = None

            if rol_new == "gestor":
                empresa_id_new = st.text_input("🏢 Empresa ID asignada *", help="Solo el ID. La gestión de empresas se realiza en empresas.py")

            if rol_new == "alumno":
                grupo_id_new = st.text_input("👥 Grupo ID asignado (opcional)", help="Solo el ID. La gestión de grupos se realiza en grupos.py")

        submitted_user = st.form_submit_button("✅ Crear usuario")
        if submitted_user:
            if not email_new or not nombre_new or not password_new:
                st.error("⚠️ Todos los campos son obligatorios.")
            elif rol_new == "gestor" and not empresa_id_new:
                st.error("⚠️ Debes asignar una empresa al gestor.")
            else:
                try:
                    if rol_new == "alumno":
                        creado = alta_alumno(supabase, email=email_new, password=password_new, nombre=nombre_new, grupo_id=grupo_id_new)
                        if creado:
                            st.success(f"✅ Usuario '{nombre_new}' creado correctamente.")
                            st.rerun()
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
                            if empresa_id_new:
                                insert_data["empresa_id"] = empresa_id_new
                            if grupo_id_new:
                                insert_data["grupo_id"] = grupo_id_new

                            supabase.table("usuarios").insert(insert_data).execute()
                            st.success(f"✅ Usuario '{nombre_new}' creado correctamente.")
                            st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al crear el usuario: {e}")
                    
