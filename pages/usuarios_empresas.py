import streamlit as st
import pandas as pd
from datetime import datetime
from services.alumnos import alta_alumno

def main(supabase, session_state):
    st.subheader("👥 Gestión de Usuarios")
    st.caption("Consulta, creación, edición y eliminación de usuarios.")

    # =========================
    # Cargar usuarios
    # =========================
    usuarios_res = supabase.table("usuarios").select("*").execute()
    usuarios = pd.DataFrame(usuarios_res.data) if usuarios_res.data else pd.DataFrame()

    if usuarios.empty:
        st.info("ℹ️ No hay usuarios registrados.")
    else:
        # =========================
        # Filtrado y descarga CSV
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

        # =========================
        # Tabla de usuarios
        # =========================
        for idx, row in usuarios_filtrados.iterrows():
            rol_color = {"admin": "background-color:#FFD700;", "gestor": "background-color:#90EE90;", "alumno": "background-color:#ADD8E6;"}
            style = rol_color.get(row["rol"], "")
            with st.container():
                st.markdown(f"<div style='{style};padding:10px;border-radius:5px;'>"
                            f"<b>{row['nombre']}</b> ({row['email']}) — <i>{row['rol']}</i></div>", unsafe_allow_html=True)

                with st.expander("Editar usuario"):
                    with st.form(f"edit_user_{row['id']}", clear_on_submit=False):
                        nombre_new = st.text_input("Nombre", value=row.get("nombre",""))
                        email_new = st.text_input("Email", value=row.get("email",""))
                        rol_new = st.selectbox("Rol", ["admin","gestor","alumno"], index=["admin","gestor","alumno"].index(row.get("rol","usuario")))

                        empresa_id_new = row.get("empresa_id")
                        grupo_id_new = row.get("grupo_id")

                        # --- Desplegable dinámico de empresa si rol = gestor ---
                        if rol_new == "gestor":
                            empresas_res = supabase.table("empresas").select("id,nombre").execute()
                            empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}
                            if empresas_dict:
                                empresa_nombre = st.selectbox("Empresa asignada *",
                                                              options=list(empresas_dict.keys()),
                                                              index=list(empresas_dict.values()).index(empresa_id_new) if empresa_id_new in empresas_dict.values() else 0)
                                empresa_id_new = empresas_dict.get(empresa_nombre)
                            else:
                                st.warning("⚠️ No hay empresas creadas.")

                        # --- Desplegable de grupo si rol = alumno ---
                        if rol_new == "alumno":
                            grupos_res = supabase.table("grupos").select("id,codigo_grupo").execute()
                            grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_res.data} if grupos_res.data else {}
                            if grupos_dict:
                                grupo_nombre = st.selectbox("Grupo asignado (opcional)",
                                                            options=["-- Ninguno --"] + list(grupos_dict.keys()),
                                                            index=list(grupos_dict.values()).index(grupo_id_new) if grupo_id_new in grupos_dict.values() else 0)
                                if grupo_nombre != "-- Ninguno --":
                                    grupo_id_new = grupos_dict.get(grupo_nombre)
                                else:
                                    grupo_id_new = None

                        guardar = st.form_submit_button("💾 Guardar cambios")
                        if guardar:
                            try:
                                supabase.table("usuarios").update({
                                    "nombre": nombre_new,
                                    "email": email_new,
                                    "rol": rol_new,
                                    "empresa_id": empresa_id_new,
                                    "grupo_id": grupo_id_new
                                }).eq("id", row["id"]).execute()
                                st.success("✅ Usuario actualizado correctamente.")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"❌ Error al actualizar: {str(e)}")

                    # --- Eliminación segura ---
                    relaciones = []
                    if row["rol"]=="gestor" and row.get("empresa_id"):
                        relaciones.append("empresa asignada")
                    if row["rol"]=="alumno" and row.get("grupo_id"):
                        relaciones.append("grupo asignado")

                    if relaciones:
                        st.warning(f"⚠️ No se puede eliminar este usuario. Está vinculado a: {', '.join(relaciones)}")
                    else:
                        if st.button(f"🗑️ Eliminar usuario {row['nombre']}"):
                            try:
                                supabase.table("usuarios").delete().eq("id", row["id"]).execute()
                                st.success("✅ Usuario eliminado correctamente.")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"❌ Error al eliminar usuario: {str(e)}")

    # =========================
    # Crear nuevo usuario
    # =========================
    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden crear usuarios.")
        return

    st.markdown("### ➕ Crear Usuario")
    with st.form("crear_usuario", clear_on_submit=True):
        email_new = st.text_input("Email *")
        nombre_new = st.text_input("Nombre *")
        password_new = st.text_input("Contraseña *", type="password")
        rol_new = st.selectbox("Rol", ["admin","gestor","alumno"])

        empresa_id_new = None
        grupo_id_new = None

        # Desplegable empresa solo si rol gestor
        if rol_new=="gestor":
            empresas_res = supabase.table("empresas").select("id,nombre").execute()
            empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}
            if empresas_dict:
                empresa_nombre = st.selectbox("Empresa asignada *", options=list(empresas_dict.keys()))
                empresa_id_new = empresas_dict.get(empresa_nombre)
            else:
                st.warning("⚠️ No hay empresas creadas. Debes crear una antes de dar de alta un gestor.")
                st.stop()

        # Desplegable grupo solo si rol alumno
        if rol_new=="alumno":
            grupos_res = supabase.table("grupos").select("id,codigo_grupo").execute()
            grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_res.data} if grupos_res.data else {}
            if grupos_dict:
                grupo_nombre = st.selectbox("Grupo asignado (opcional)", options=["-- Ninguno --"]+list(grupos_dict.keys()))
                if grupo_nombre != "-- Ninguno --":
                    grupo_id_new = grupos_dict.get(grupo_nombre)

        submitted_user = st.form_submit_button("Crear Usuario")
        if submitted_user:
            if not email_new or not nombre_new or not password_new:
                st.error("⚠️ Todos los campos son obligatorios.")
            elif rol_new=="gestor" and not empresa_id_new:
                st.error("⚠️ Debes asignar una empresa al gestor.")
            else:
                try:
                    if rol_new=="alumno":
                        creado = alta_alumno(supabase, email=email_new, password=password_new, nombre=nombre_new, grupo_id=grupo_id_new)
                        if creado:
                            st.success(f"✅ Usuario '{nombre_new}' creado correctamente.")
                            st.experimental_rerun()
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

                            insert_data = {"auth_id": auth_res.user.id, "email": email_new, "nombre": nombre_new, "rol": rol_new}
                            if empresa_id_new: insert_data["empresa_id"] = empresa_id_new
                            if grupo_id_new: insert_data["grupo_id"] = grupo_id_new

                            supabase.table("usuarios").insert(insert_data).execute()
                            st.success(f"✅ Usuario '{nombre_new}' creado correctamente.")
                            st.experimental_rerun()

                except Exception as e:
                    st.error(f"❌ Error al crear el usuario: {e}")
