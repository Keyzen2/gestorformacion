# pages/usuarios_empresas.py

import streamlit as st
import pandas as pd
from datetime import datetime
from services.users import create_user, update_user, delete_user
from utils import ROLES

def main(supabase, session_state):
    st.title("👥 Gestión de Usuarios")
    st.caption("Alta, edición y eliminación de usuarios en la plataforma.")

    # Solo administradores
    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        st.stop()

    # Cargar datos maestros
    usuarios_res = supabase.table("usuarios").select("*").execute()
    usuarios = pd.DataFrame(usuarios_res.data or [])

    empresas_res = supabase.table("empresas").select("id,nombre").execute()
    empresas = empresas_res.data or []
    empresas_dict = {e["nombre"]: e["id"] for e in empresas}

    grupos_res = supabase.table("grupos").select("id,codigo_grupo").execute()
    grupos = grupos_res.data or []
    grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos}

    # Búsqueda y exportación CSV
    search = st.text_input("🔍 Buscar por nombre o email")
    usuarios_filtrados = usuarios.copy()
    if search:
        mask = (
            usuarios_filtrados["nombre"].str.contains(search, case=False, na=False)
            | usuarios_filtrados["email"].str.contains(search, case=False, na=False)
        )
        usuarios_filtrados = usuarios_filtrados[mask]

    if not usuarios_filtrados.empty:
        csv = usuarios_filtrados.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar CSV",
            data=csv,
            file_name="usuarios.csv",
            mime="text/csv"
        )
    else:
        st.info("ℹ️ No hay usuarios para mostrar.")

    st.divider()
    st.markdown("### 📋 Usuarios registrados")

    for _, row in usuarios_filtrados.iterrows():
        icon = {"admin":"🛠️","gestor":"📋","alumno":"🎓"}.get(row["rol"], "👤")
        with st.expander(f"{icon}  {row['nombre']}  ({row['email']})"):
            # Detalles
            st.markdown(f"**🆔 ID:** {row['id']}")
            st.markdown(f"**📧 Email:** {row['email']}")
            st.markdown(f"**🎓 Rol:** {row['rol'].capitalize()}")
            if row.get("empresa_id"):
                emp_name = next((n for n,i in empresas_dict.items() if i==row["empresa_id"]), row["empresa_id"])
                st.markdown(f"**🏢 Empresa:** {emp_name}")
            if row.get("grupo_id"):
                grp_name = next((n for n,i in grupos_dict.items() if i==row["grupo_id"]), row["grupo_id"])
                st.markdown(f"**👥 Grupo:** {grp_name}")
            st.markdown(f"**📅 Alta:** {row.get('created_at','—')}")

            # Pestañas Editar / Eliminar
            tab_edit, tab_delete = st.tabs(["✏️ Editar", "🗑️ Eliminar"])

            # ----- EDITAR -----
            with tab_edit:
                with st.form(f"form_edit_{row['id']}", clear_on_submit=True):
                    nombre_new = st.text_input("Nombre *", value=row.get("nombre",""))
                    email_new  = st.text_input("Email *",  value=row.get("email",""))
                    rol_new    = st.selectbox("Rol *", sorted(ROLES), index=list(sorted(ROLES)).index(row["rol"]))
                    emp_id_new = row.get("empresa_id")
                    grp_id_new = row.get("grupo_id")

                    if rol_new == "gestor":
                        sel = st.selectbox(
                            "Empresa asignada *",
                            sorted(empresas_dict.keys()),
                            index=list(empresas_dict.keys()).index(
                                next((n for n,i in empresas_dict.items() if i==emp_id_new), "")
                            ) if emp_id_new else 0
                        )
                        emp_id_new = empresas_dict[sel]
                        grp_id_new = None

                    elif rol_new == "alumno":
                        sel = st.selectbox(
                            "Grupo asignado *",
                            sorted(grupos_dict.keys()),
                            index=list(grupos_dict.keys()).index(
                                next((n for n,i in grupos_dict.items() if i==grp_id_new), "")
                            ) if grp_id_new else 0
                        )
                        grp_id_new = grupos_dict[sel]
                        emp_id_new = None

                    else:  # admin
                        emp_id_new = None
                        grp_id_new = None

                    guardar = st.form_submit_button("💾 Guardar cambios")
                    if guardar:
                        if not nombre_new or not email_new:
                            st.error("⚠️ Nombre y email son obligatorios.")
                        else:
                            try:
                                update_user(
                                    supabase,
                                    auth_id=row["auth_id"],
                                    email=email_new,
                                    nombre=nombre_new,
                                    rol=rol_new,
                                    empresa_id=emp_id_new,
                                    grupo_id=grp_id_new
                                )
                                st.success("✅ Usuario actualizado correctamente.")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"❌ Error al actualizar usuario: {e}")

            # ----- ELIMINAR -----
            with tab_delete:
                depends = []
                if row["rol"] == "gestor" and row.get("empresa_id"):
                    depends.append("empresa asignada")
                if row["rol"] == "alumno" and row.get("grupo_id"):
                    depends.append("grupo asignado")
                if depends:
                    st.warning(f"⚠️ No se puede eliminar. Vinculado a: {', '.join(depends)}")
                else:
                    if st.button("🗑️ Eliminar usuario", key=f"del_{row['id']}"):
                        try:
                            delete_user(supabase, auth_id=row["auth_id"])
                            st.success("✅ Usuario eliminado correctamente.")
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"❌ Error al eliminar usuario: {e}")

    # ----- CREAR NUEVO USUARIO -----
    st.divider()
    st.markdown("### ➕ Crear nuevo usuario")
    with st.form("form_new_user", clear_on_submit=True):
        email_new    = st.text_input("📧 Email *")
        nombre_new   = st.text_input("👤 Nombre *")
        password_new = st.text_input("🔒 Contraseña *", type="password")
        rol_new      = st.selectbox("🎓 Rol *", sorted(ROLES))
        emp_id_new   = None
        grp_id_new   = None

        if rol_new == "gestor":
            sel = st.selectbox("🏢 Empresa asignada *", sorted(empresas_dict.keys()))
            emp_id_new = empresas_dict[sel]
        elif rol_new == "alumno":
            sel = st.selectbox("👥 Grupo asignado *", sorted(grupos_dict.keys()))
            grp_id_new = grupos_dict[sel]

        crear = st.form_submit_button("✅ Crear usuario")

    if crear:
        if not email_new or not nombre_new or not password_new:
            st.error("⚠️ Todos los campos con * son obligatorios.")
        elif rol_new == "gestor" and not emp_id_new:
            st.error("⚠️ Debes seleccionar una empresa para el gestor.")
        elif rol_new == "alumno" and not grp_id_new:
            st.error("⚠️ Debes seleccionar un grupo para el alumno.")
        else:
            try:
                create_user(
                    supabase,
                    email=email_new,
                    password=password_new,
                    nombre=nombre_new,
                    rol=rol_new,
                    empresa_id=emp_id_new,
                    grupo_id=grp_id_new
                )
                st.success(f"✅ Usuario '{nombre_new}' creado correctamente.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ Error al crear usuario: {e}")
