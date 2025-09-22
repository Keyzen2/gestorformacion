import streamlit as st
import pandas as pd
import re
from datetime import datetime, date
from io import BytesIO
from utils import validar_dni_cif, validar_email
from services.data_service import get_data_service

EMAIL_REGEX = r"^[^@]+@[^@]+\.[^@]+$"

# =========================
# CONFIG STREAMLIT
# =========================
st.set_page_config(
    page_title="👥 Gestión de Usuarios",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# HELPERS
# =========================
def exportar_usuarios(df: pd.DataFrame):
    """Exporta usuarios a CSV o Excel."""
    col1, col2 = st.columns(2)

    with col1:
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar CSV",
            data=csv_data,
            file_name=f"usuarios_{datetime.today().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col2:
        buffer = BytesIO()
        df.to_excel(buffer, index=False, engine="openpyxl")
        buffer.seek(0)
        st.download_button(
            "📥 Descargar Excel",
            data=buffer,
            file_name=f"usuarios_{datetime.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

def validar_datos_usuario(datos: dict, empresas_dict: dict, grupos_dict: dict, es_creacion: bool = False):
    """Valida los campos obligatorios de un usuario."""
    if not datos.get("email"):
        return "⚠️ El email es obligatorio."
    if not re.match(EMAIL_REGEX, datos["email"]):
        return "⚠️ Email no válido."
    if not datos.get("nombre_completo"):
        return "⚠️ El nombre completo es obligatorio."
    if datos.get("nif") and not validar_dni_cif(datos["nif"]):
        return "⚠️ NIF/CIF no válido."
    if datos.get("rol") in ["gestor", "alumno"]:
        empresa_sel = datos.get("empresa_sel", "")
        if not empresa_sel or empresa_sel not in empresas_dict:
            return f"⚠️ Los usuarios con rol '{datos['rol']}' deben tener una empresa asignada."
    return None

# =========================
# MAIN
# =========================
def main(supabase, session_state):
    st.title("👥 Gestión de Usuarios")
    st.caption("Consulta, creación y edición de usuarios registrados en la plataforma.")

    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        return

    data_service = get_data_service(supabase, session_state)

    try:
        df_usuarios = data_service.get_usuarios(include_empresa=True)

        empresas_res = supabase.table("empresas").select("id,nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data or []}
        empresas_opciones = [""] + sorted(empresas_dict.keys())

        grupos_res = supabase.table("grupos").select("id,codigo_grupo").execute()
        grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_res.data or []}
        grupos_opciones = [""] + sorted(grupos_dict.keys())

    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # =========================
    # Métricas rápidas
    # =========================
    if not df_usuarios.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Total Usuarios", len(df_usuarios))
        with col2:
            st.metric("🔧 Administradores", len(df_usuarios[df_usuarios["rol"] == "admin"]))
        with col3:
            st.metric("👨‍💼 Gestores", len(df_usuarios[df_usuarios["rol"] == "gestor"]))
        with col4:
            st.metric("🎓 Alumnos", len(df_usuarios[df_usuarios["rol"] == "alumno"]))

    if df_usuarios.empty:
        st.info("ℹ️ No hay usuarios registrados.")
        return

    # =========================
    # Filtros
    # =========================
    st.divider()
    st.markdown("### 🔍 Buscar y filtrar")

    col1, col2 = st.columns(2)
    with col1:
        query = st.text_input("🔍 Buscar por nombre, email o teléfono")
    with col2:
        rol_filter = st.selectbox("Filtrar por rol", ["Todos", "admin", "gestor", "alumno"])

    df_filtered = df_usuarios.copy()
    if query:
        q_lower = query.lower()
        search_cols = []
        for col in ["nombre_completo", "email", "telefono", "nif"]:
            if col in df_filtered.columns:
                search_cols.append(df_filtered[col].fillna("").str.lower().str.contains(q_lower, na=False))
        if search_cols:
            mask = search_cols[0]
            for m in search_cols[1:]:
                mask = mask | m
            df_filtered = df_filtered[mask]

    if rol_filter != "Todos":
        df_filtered = df_filtered[df_filtered["rol"] == rol_filter]

    # =========================
    # Tabla con selección
    # =========================
    st.divider()
    st.markdown("### 📋 Usuarios")

    columnas = ["nombre_completo", "email", "telefono", "rol", "nif", "empresa_nombre", "created_at"]
    df_display = df_filtered[columnas] if not df_filtered.empty else pd.DataFrame(columns=columnas)

    evento = st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun"
    )

    seleccionado = None
    if evento.selection.rows:
        seleccionado = df_filtered.iloc[evento.selection.rows[0]]

    # Exportación
    if not df_filtered.empty:
        exportar_usuarios(df_filtered)

    # =========================
    # Formularios
    # =========================
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("➕ Crear Usuario")
        with st.form("crear_usuario"):
            nuevo = {
                "email": st.text_input("Email", key="crear_email"),
                "nombre_completo": st.text_input("Nombre completo", key="crear_nombre_completo"),
                "nombre": st.text_input("Nombre corto", key="crear_nombre"),
                "telefono": st.text_input("Teléfono", key="crear_telefono"),
                "nif": st.text_input("NIF/NIE/CIF", key="crear_nif"),
                "rol": st.selectbox("Rol", ["", "admin", "gestor", "alumno"], key="crear_rol"),
                "empresa_sel": st.selectbox("Empresa", empresas_opciones, key="crear_empresa"),
                "grupo_sel": st.selectbox("Grupo", grupos_opciones, key="crear_grupo"),
                "password": st.text_input("Contraseña (opcional)", type="password", key="crear_pass")
            }
            submitted = st.form_submit_button("➕ Crear", type="primary")

            if submitted:
                error = validar_datos_usuario(nuevo, empresas_dict, grupos_dict, es_creacion=True)
                if error:
                    st.error(error)
                else:
                    try:
                        empresa_id = empresas_dict.get(nuevo.pop("empresa_sel")) if nuevo.get("empresa_sel") else None
                        grupo_id = grupos_dict.get(nuevo.pop("grupo_sel")) if nuevo.get("grupo_sel") else None
                        password = nuevo.get("password") or "TempPass123!"

                        auth_res = supabase.auth.admin.create_user({
                            "email": nuevo["email"],
                            "password": password,
                            "email_confirm": True
                        })
                        if not getattr(auth_res, "user", None):
                            st.error("❌ Error al crear usuario en Auth.")
                        else:
                            auth_id = auth_res.user.id
                            db_datos = {
                                "auth_id": auth_id,
                                "email": nuevo["email"],
                                "nombre_completo": nuevo["nombre_completo"],
                                "nombre": nuevo["nombre"],
                                "telefono": nuevo["telefono"],
                                "nif": nuevo["nif"],
                                "rol": nuevo["rol"],
                                "empresa_id": empresa_id,
                                "grupo_id": grupo_id,
                                "created_at": datetime.utcnow().isoformat()
                            }
                            result = supabase.table("usuarios").insert(db_datos).execute()
                            if result.data:
                                data_service.get_usuarios.clear()
                                st.success(f"✅ Usuario creado. Contraseña temporal: {password}")
                                st.rerun()
                            else:
                                supabase.auth.admin.delete_user(auth_id)
                                st.error("❌ Error al crear usuario en BD.")
                    except Exception as e:
                        st.error(f"❌ Error al crear usuario: {e}")

    with col2:
        if seleccionado is not None:
            st.subheader(f"✏️ Editar Usuario: {seleccionado['nombre_completo']}")
            with st.form("editar_usuario"):
                edit = {
                    "email": st.text_input("Email", value=seleccionado["email"]),
                    "nombre_completo": st.text_input("Nombre completo", value=seleccionado["nombre_completo"]),
                    "nombre": st.text_input("Nombre corto", value=seleccionado.get("nombre", "")),
                    "telefono": st.text_input("Teléfono", value=seleccionado.get("telefono", "")),
                    "nif": st.text_input("NIF/NIE/CIF", value=seleccionado.get("nif", "")),
                    "rol": st.selectbox("Rol", ["", "admin", "gestor", "alumno"], index=["","admin","gestor","alumno"].index(seleccionado["rol"])),
                    "empresa_sel": st.selectbox("Empresa", empresas_opciones, index=empresas_opciones.index(seleccionado.get("empresa_nombre", "")) if seleccionado.get("empresa_nombre") else 0),
                    "grupo_sel": st.selectbox("Grupo", grupos_opciones, index=grupos_opciones.index(seleccionado.get("grupo_codigo", "")) if seleccionado.get("grupo_codigo") else 0),
                }
                submitted_edit = st.form_submit_button("💾 Guardar cambios", type="primary")

                if submitted_edit:
                    error = validar_datos_usuario(edit, empresas_dict, grupos_dict)
                    if error:
                        st.error(error)
                    else:
                        try:
                            empresa_id = empresas_dict.get(edit.pop("empresa_sel")) if edit.get("empresa_sel") else None
                            grupo_id = grupos_dict.get(edit.pop("grupo_sel")) if edit.get("grupo_sel") else None
                            cambios = {
                                **edit,
                                "empresa_id": empresa_id,
                                "grupo_id": grupo_id,
                                "updated_at": datetime.utcnow().isoformat()
                            }
                            supabase.table("usuarios").update(cambios).eq("id", seleccionado["id"]).execute()
                            data_service.get_usuarios.clear()
                            st.success("✅ Usuario actualizado correctamente")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al actualizar usuario: {e}")

    st.divider()
    st.caption("💡 Gestiona usuarios del sistema desde esta interfaz centralizada.")
