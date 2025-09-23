import streamlit as st
import pandas as pd
import re
from datetime import datetime, date
from io import BytesIO
from utils import validar_dni_cif, validar_email
from services.data_service import get_data_service
from services.auth_service import get_auth_service

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
    """Exporta usuarios a CSV o Excel en expander."""
    with st.expander("📥 Exportar Usuarios"):
        col1, col2 = st.columns(2)

        with col1:
            csv_data = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📄 Descargar CSV",
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
                "📊 Descargar Excel",
                data=buffer,
                file_name=f"usuarios_{datetime.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

def validar_datos_usuario(datos: dict, empresas_dict: dict, es_creacion: bool = False):
    """Valida los campos obligatorios de un usuario (SIN rol alumno)."""
    if not datos.get("email"):
        return "El email es obligatorio."
    if not re.match(EMAIL_REGEX, datos["email"]):
        return "Email no válido."
    if not datos.get("nombre_completo"):
        return "El nombre completo es obligatorio."
    if datos.get("documento") and not validar_dni_cif(datos["documento"]):
        return "Documento no válido."
    
    # Validar que gestor tiene empresa
    if datos.get("rol") == "gestor":
        empresa_sel = datos.get("empresa_sel", "")
        if not empresa_sel or empresa_sel not in empresas_dict:
            return "Los gestores deben tener una empresa asignada."
    
    # Validar rol permitido
    roles_permitidos = ["admin", "gestor", "comercial"]
    if datos.get("rol") not in roles_permitidos:
        return f"Rol no válido. Permitidos: {', '.join(roles_permitidos)}"
    
    return None

# =========================
# CAMPOS CONECTADOS EMPRESA
# =========================
def mostrar_campos_empresa_usuario(empresas_dict, datos, key_suffix=""):
    """Campos de empresa conectados al rol (solo para gestor/comercial)."""
    
    # Empresa seleccionada
    empresa_key = f"empresa_usuario_{key_suffix}"
    if empresa_key not in st.session_state:
        empresa_actual = datos.get("empresa_nombre", "")
        st.session_state[empresa_key] = empresa_actual
    
    empresa_opciones = [""] + sorted(empresas_dict.keys())
    empresa_sel = st.selectbox(
        "🏢 Empresa asignada",
        options=empresa_opciones,
        index=empresa_opciones.index(st.session_state[empresa_key]) if st.session_state[empresa_key] in empresa_opciones else 0,
        key=f"empresa_select_{key_suffix}",
        help="Solo obligatorio para gestores y comerciales"
    )
    
    # Actualizar session_state si cambió
    if empresa_sel != st.session_state[empresa_key]:
        st.session_state[empresa_key] = empresa_sel
        st.rerun()
    
    empresa_id = empresas_dict.get(empresa_sel) if empresa_sel else None
    
    return empresa_sel, empresa_id

# =========================
# MAIN
# =========================
def main(supabase, session_state):
    st.title("👥 Gestión de Usuarios del Sistema")
    st.caption("Administradores, gestores y comerciales. Los alumnos se crean desde Participantes.")

    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        return

    data_service = get_data_service(supabase, session_state)
    auth_service = get_auth_service(supabase, session_state)

    try:
        df_usuarios = data_service.get_usuarios(include_empresa=True)

        empresas_res = supabase.table("empresas").select("id,nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data or []}

    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # =========================
    # Métricas rápidas
    # =========================
    if not df_usuarios.empty:
        # Filtrar solo usuarios del sistema (no alumnos)
        df_sistema = df_usuarios[df_usuarios["rol"].isin(["admin", "gestor", "comercial"])]
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Total", len(df_sistema))
        with col2:
            st.metric("🔧 Administradores", len(df_sistema[df_sistema["rol"] == "admin"]))
        with col3:
            st.metric("👨‍💼 Gestores", len(df_sistema[df_sistema["rol"] == "gestor"]))
        with col4:
            st.metric("💼 Comerciales", len(df_sistema[df_sistema["rol"] == "comercial"]))

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
        rol_filter = st.selectbox("Filtrar por rol", ["Todos", "admin", "gestor", "comercial"])

    # Filtrar solo usuarios del sistema (no alumnos)
    df_filtered = df_usuarios[df_usuarios["rol"].isin(["admin", "gestor", "comercial"])].copy()
    
    if query:
        q_lower = query.lower()
        search_cols = []
        for col in ["nombre_completo", "email", "telefono", "documento"]:
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
    st.markdown("### 📋 Usuarios del Sistema")

    columnas = ["nombre_completo", "email", "telefono", "rol", "documento", "empresa_nombre", "created_at"]
    columnas_existentes = [col for col in columnas if col in df_filtered.columns]
    df_display = df_filtered[columnas_existentes] if not df_filtered.empty else pd.DataFrame(columns=columnas_existentes)

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
    # Tabs para Formularios
    # =========================
    st.divider()
    tabs = st.tabs(["Crear Usuario", "Editar Usuario"])

    # =========================
    # TAB CREAR
    # =========================
    with tabs[0]:
        st.markdown("### ➕ Crear Usuario del Sistema")
        
        # Campos empresa fuera del formulario para roles que lo necesiten
        st.markdown("#### 🏢 Asignación de Empresa")
        empresa_sel_crear, empresa_id_crear = mostrar_campos_empresa_usuario(empresas_dict, {}, "crear")
        st.divider()
        
        with st.form("crear_usuario", clear_on_submit=False):
            
            st.markdown("#### 👤 Información Personal")
            col1, col2 = st.columns(2)
            
            with col1:
                email = st.text_input("Email", key="crear_email")
                nombre_completo = st.text_input("Nombre completo", key="crear_nombre_completo")
                telefono = st.text_input("Teléfono", key="crear_telefono")
            
            with col2:
                documento = st.text_input("Documento (DNI/NIE/CIF)", key="crear_documento")
                rol = st.selectbox("Rol", ["", "admin", "gestor", "comercial"], key="crear_rol", 
                                 help="Admin: acceso total, Gestor: empresa específica, Comercial: CRM")
                password = st.text_input("Contraseña (opcional - se genera automática)", type="password", key="crear_pass")
            
            # Mostrar empresa seleccionada
            st.markdown("#### 📊 Asignación actual")
            if empresa_sel_crear:
                st.success(f"🏢 **Empresa:** {empresa_sel_crear}")
            else:
                if rol in ["gestor", "comercial"]:
                    st.warning("⚠️ **Empresa:** Requerida para gestores y comerciales")
                else:
                    st.info("ℹ️ **Empresa:** No requerida para administradores")
            
            # Validaciones
            datos_nuevo = {
                "email": email,
                "nombre_completo": nombre_completo,
                "telefono": telefono,
                "documento": documento,
                "rol": rol,
                "empresa_sel": empresa_sel_crear,
                "password": password
            }
            
            errores = []
            error_validacion = validar_datos_usuario(datos_nuevo, empresas_dict, es_creacion=True)
            if error_validacion:
                errores.append(error_validacion)
            
            if errores:
                st.warning(f"⚠️ Campos pendientes: {', '.join(errores)}")
                st.info("💡 Puedes intentar crear - se validarán al procesar")
            
            submitted = st.form_submit_button("➕ Crear Usuario", type="primary")

            if submitted:
                if errores:
                    st.error(f"❌ Corrige estos errores: {', '.join(errores)}")
                else:
                    try:
                        datos_usuario = {
                            "email": email,
                            "nombre_completo": nombre_completo,
                            "telefono": telefono,
                            "documento": documento,
                            "rol": rol,
                            "empresa_id": empresa_id_crear if rol in ["gestor", "comercial"] else None,
                        }
                        
                        # USAR AUTHSERVICE CENTRALIZADO
                        ok, usuario_id = auth_service.crear_usuario_con_auth(
                            datos_usuario, 
                            tabla="usuarios", 
                            password=password if password else None
                        )
                        
                        if ok:
                            st.success("✅ Usuario creado correctamente con acceso al sistema")
                            data_service.get_usuarios.clear()
                            # Limpiar session state
                            st.session_state.pop("empresa_usuario_crear", None)
                            st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error al crear usuario: {e}")

    # =========================
    # TAB EDITAR
    # =========================
    with tabs[1]:
        if seleccionado is not None:
            st.markdown(f"### ✏️ Editar Usuario: {seleccionado['nombre_completo']}")
            
            # Campos empresa fuera del formulario
            st.markdown("#### 🏢 Asignación de Empresa")
            empresa_sel_editar, empresa_id_editar = mostrar_campos_empresa_usuario(empresas_dict, seleccionado, f"editar_{seleccionado['id']}")
            st.divider()
            
            with st.form(f"editar_usuario_{seleccionado['id']}", clear_on_submit=False):
                
                st.markdown("#### 👤 Información Personal")
                col1, col2 = st.columns(2)
                
                with col1:
                    email_edit = st.text_input("Email", value=seleccionado["email"])
                    nombre_completo_edit = st.text_input("Nombre completo", value=seleccionado["nombre_completo"])
                    telefono_edit = st.text_input("Teléfono", value=seleccionado.get("telefono", ""))
                
                with col2:
                    documento_edit = st.text_input("Documento", value=seleccionado.get("documento", ""))
                    roles_disponibles = ["admin", "gestor", "comercial"]
                    rol_edit = st.selectbox("Rol", roles_disponibles, 
                                          index=roles_disponibles.index(seleccionado["rol"]) if seleccionado["rol"] in roles_disponibles else 0)
                
                # Gestión de contraseña
                st.markdown("#### 🔐 Gestión de contraseña")
                if st.checkbox("Generar nueva contraseña", help="Marca para generar nueva contraseña automática"):
                    st.info("Se generará una nueva contraseña al guardar los cambios")
                    reset_password = True
                else:
                    reset_password = False
                
                # Mostrar empresa seleccionada
                st.markdown("#### 📊 Asignación actual")
                if empresa_sel_editar:
                    st.success(f"🏢 **Empresa:** {empresa_sel_editar}")
                else:
                    if rol_edit in ["gestor", "comercial"]:
                        st.warning("⚠️ **Empresa:** Requerida para gestores y comerciales")
                    else:
                        st.info("ℹ️ **Empresa:** No requerida para administradores")
                
                # Validaciones
                datos_editados = {
                    "email": email_edit,
                    "nombre_completo": nombre_completo_edit,
                    "telefono": telefono_edit,
                    "documento": documento_edit,
                    "rol": rol_edit,
                    "empresa_sel": empresa_sel_editar
                }
                
                errores_edit = []
                error_validacion_edit = validar_datos_usuario(datos_editados, empresas_dict, es_creacion=False)
                if error_validacion_edit:
                    errores_edit.append(error_validacion_edit)
                
                if errores_edit:
                    st.warning(f"⚠️ Campos pendientes: {', '.join(errores_edit)}")
                
                submitted_edit = st.form_submit_button("💾 Guardar cambios", type="primary")

                if submitted_edit:
                    if errores_edit:
                        st.error(f"❌ Corrige estos errores: {', '.join(errores_edit)}")
                    else:
                        try:
                            datos_finales = {
                                "email": email_edit,
                                "nombre_completo": nombre_completo_edit,
                                "telefono": telefono_edit,
                                "documento": documento_edit,
                                "rol": rol_edit,
                                "empresa_id": empresa_id_editar if rol_edit in ["gestor", "comercial"] else None,
                            }
                            
                            # Manejar reset de contraseña
                            if reset_password:
                                import secrets
                                import string
                                caracteres = string.ascii_letters + string.digits + "!@#$%^&*"
                                nueva_password = ''.join(secrets.choice(caracteres) for _ in range(12))
                                
                                # Actualizar contraseña en Auth
                                try:
                                    auth_id = seleccionado.get("auth_id")
                                    if auth_id:
                                        supabase.auth.admin.update_user_by_id(auth_id, {"password": nueva_password})
                                        st.success(f"🔑 Nueva contraseña generada: {nueva_password}")
                                except Exception as e:
                                    st.warning(f"⚠️ Error actualizando contraseña: {e}")
                            
                            # USAR AUTHSERVICE CENTRALIZADO
                            ok = auth_service.actualizar_usuario_con_auth(
                                tabla="usuarios",
                                registro_id=seleccionado["id"],
                                datos_editados=datos_finales
                            )
                            
                            if ok:
                                st.success("✅ Usuario actualizado correctamente")
                                data_service.get_usuarios.clear()
                                st.rerun()
                                
                        except Exception as e:
                            st.error(f"❌ Error al actualizar usuario: {e}")
        else:
            st.info("👆 Selecciona un usuario de la tabla para editarlo")

    # =========================
    # Información adicional
    # =========================
    st.divider()
    with st.expander("ℹ️ Información sobre Roles y Usuarios"):
        st.markdown("""
        **Roles disponibles en este módulo:**
        
        - **👑 Admin**: Acceso total al sistema, puede gestionar todas las empresas y usuarios
        - **👨‍💼 Gestor**: Administra una empresa específica y sus datos (requiere empresa asignada)
        - **💼 Comercial**: Gestión de CRM y clientes de la empresa (requiere empresa asignada)
        
        **Importante:**
        - 🎓 **Los alumnos NO se crean aquí** - se crean desde la sección "Participantes"
        - Los alumnos creados en Participantes automáticamente tienen acceso a "Mis Grupos"
        - Los gestores y comerciales deben tener una empresa asignada obligatoriamente
        - Las contraseñas se generan automáticamente de forma segura si no se especifican
        """)
    
    st.caption("💡 Gestiona usuarios administrativos del sistema desde esta interfaz centralizada.")
