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
    if datos.get("nif") and not validar_dni_cif(datos["nif"]):
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
# MÉTRICAS CON GRÁFICOS
# =========================
def mostrar_metricas_usuarios(df_usuarios):
    """Muestra métricas con gráficos como en participantes.py."""
    try:
        # Filtrar solo usuarios del sistema (no alumnos)
        df_sistema = df_usuarios[df_usuarios["rol"].isin(["admin", "gestor", "comercial"])]
        
        if df_sistema.empty:
            metricas = {"total": 0, "admin": 0, "gestor": 0, "comercial": 0, "nuevos_mes": 0}
        else:
            total = len(df_sistema)
            admin = len(df_sistema[df_sistema["rol"] == "admin"])
            gestor = len(df_sistema[df_sistema["rol"] == "gestor"])
            comercial = len(df_sistema[df_sistema["rol"] == "comercial"])
            
            # Usuarios nuevos este mes
            nuevos_mes = 0
            if "created_at" in df_sistema.columns:
                try:
                    df_sistema['created_at_dt'] = pd.to_datetime(df_sistema["created_at"], errors="coerce")
                    mes_actual = datetime.now().month
                    año_actual = datetime.now().year
                    nuevos_mes = len(df_sistema[
                        (df_sistema['created_at_dt'].dt.month == mes_actual) & 
                        (df_sistema['created_at_dt'].dt.year == año_actual)
                    ])
                except:
                    nuevos_mes = 0
            
            metricas = {
                "total": total,
                "admin": admin,
                "gestor": gestor,
                "comercial": comercial,
                "nuevos_mes": nuevos_mes
            }

        # Mostrar métricas
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("👥 Total", metricas["total"], 
                     delta=f"+{metricas['nuevos_mes']}" if metricas['nuevos_mes'] > 0 else None)
        with col2:
            st.metric("🔧 Administradores", metricas["admin"])
        with col3:
            st.metric("👨‍💼 Gestores", metricas["gestor"])
        with col4:
            st.metric("💼 Comerciales", metricas["comercial"])
        with col5:
            st.metric("🆕 Nuevos (mes)", metricas["nuevos_mes"])
        
        # Gráficos de distribución si hay datos
        if metricas["total"] > 0:
            st.markdown("#### 📊 Distribución por Roles")
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                # Gráfico de roles
                import plotly.express as px
                data_roles = {
                    "Rol": ["Admin", "Gestor", "Comercial"],
                    "Cantidad": [metricas["admin"], metricas["gestor"], metricas["comercial"]]
                }
                fig_roles = px.pie(values=data_roles["Cantidad"], names=data_roles["Rol"], 
                                  title="Distribución por roles")
                st.plotly_chart(fig_roles, use_container_width=True)
            
            with col_chart2:
                # Gráfico temporal (simplificado)
                data_temporal = {
                    "Periodo": ["Anteriores", "Este mes"],
                    "Cantidad": [metricas["total"] - metricas["nuevos_mes"], metricas["nuevos_mes"]]
                }
                fig_temporal = px.bar(x=data_temporal["Periodo"], y=data_temporal["Cantidad"],
                                     title="Usuarios por periodo")
                st.plotly_chart(fig_temporal, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Error calculando métricas: {e}")
        # Mostrar métricas vacías
        col1, col2, col3, col4, col5 = st.columns(5)
        for col, label in zip([col1, col2, col3, col4, col5], 
                             ["👥 Total", "🔧 Admin", "👨‍💼 Gestor", "💼 Comercial", "🆕 Nuevos"]):
            with col:
                st.metric(label, 0)

# =========================
# TABLA GENERAL
# =========================
def mostrar_tabla_usuarios(df_usuarios, session_state, titulo_tabla="📋 Lista de Usuarios"):
    """Muestra tabla de usuarios con filtros y selección de fila."""
    if df_usuarios.empty:
        st.info("📋 No hay usuarios para mostrar")
        return None

    st.markdown(f"### {titulo_tabla}")

    # 🔍 Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_nombre = st.text_input("👤 Nombre/Email contiene", key="filtro_tabla_nombre")
    with col2:
        filtro_rol = st.selectbox("Filtrar por rol", ["Todos", "admin", "gestor", "comercial"], key="filtro_tabla_rol")
    with col3:
        filtro_empresa = st.text_input("🏢 Empresa contiene", key="filtro_tabla_empresa")

    # Aplicar filtros
    df_filtered = df_usuarios.copy()
    
    if filtro_nombre:
        df_filtered = df_filtered[
            df_filtered["nombre_completo"].str.contains(filtro_nombre, case=False, na=False) |
            df_filtered["email"].str.contains(filtro_nombre, case=False, na=False)
        ]
    if filtro_rol != "Todos":
        df_filtered = df_filtered[df_filtered["rol"] == filtro_rol]
    if filtro_empresa and "empresa_nombre" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["empresa_nombre"].str.contains(filtro_empresa, case=False, na=False)]

    # Configuración columnas - USAR CAMPOS CORRECTOS
    columnas = ["nombre_completo", "email", "telefono", "rol", "nif", "empresa_nombre", "created_at"]
    columnas_existentes = [col for col in columnas if col in df_filtered.columns]
    df_display = df_filtered[columnas_existentes] if not df_filtered.empty else pd.DataFrame(columns=columnas_existentes)

    # Mostrar tabla
    evento = st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun"
    )

    if evento.selection.rows:
        return df_filtered.iloc[evento.selection.rows[0]], df_filtered
    return None, df_filtered

# =========================
# FORMULARIO INTEGRADO CORREGIDO
# =========================
def mostrar_formulario_usuario(usuario_data, data_service, auth_service, empresas_dict, es_creacion=False):
    """Formulario completamente integrado con reset correcto."""
    
    if es_creacion:
        st.subheader("➕ Crear Usuario del Sistema")
        datos = {}
        # CLAVE: Generar ID único para resetear formulario
        form_key = f"crear_usuario_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    else:
        st.subheader(f"✏️ Editar Usuario: {usuario_data['nombre_completo']}")
        datos = usuario_data.copy()
        form_key = f"editar_usuario_{datos['id']}"

    with st.form(form_key, clear_on_submit=True):  # IMPORTANTE: clear_on_submit=True
        
        # =========================
        # INFORMACIÓN PERSONAL
        # =========================
        st.markdown("### 👤 Información Personal")
        col1, col2 = st.columns(2)
        
        with col1:
            email = st.text_input("Email", value=datos.get("email", ""))
            nombre_completo = st.text_input("Nombre completo", value=datos.get("nombre_completo", ""))
            telefono = st.text_input("Teléfono", value=datos.get("telefono", ""))
        
        with col2:
            nif = st.text_input("Documento (DNI/NIE/CIF)", value=datos.get("nif", ""))
            rol = st.selectbox("Rol", ["", "admin", "gestor", "comercial"], 
                              index=["", "admin", "gestor", "comercial"].index(datos.get("rol", "")) if datos.get("rol") in ["", "admin", "gestor", "comercial"] else 0,
                              help="Admin: acceso total, Gestor: empresa específica, Comercial: CRM")

        # =========================
        # EMPRESA (INTEGRADA)
        # =========================
        st.markdown("### 🏢 Asignación de Empresa")
        col1, col2 = st.columns(2)
        
        with col1:
            # CORREGIDO: Reset de empresa en formulario de creación
            if es_creacion and st.session_state.get("usuario_creado_exitosamente"):
                # Resetear después de creación exitosa
                empresa_sel = st.selectbox("🏢 Empresa", options=[""] + sorted(empresas_dict.keys()), 
                                         index=0, help="Solo obligatorio para gestores y comerciales")
                # Limpiar flag
                del st.session_state["usuario_creado_exitosamente"]
            else:
                empresa_actual_nombre = datos.get("empresa_nombre", "")
                empresa_opciones = [""] + sorted(empresas_dict.keys())
                empresa_sel = st.selectbox(
                    "🏢 Empresa",
                    options=empresa_opciones,
                    index=empresa_opciones.index(empresa_actual_nombre) if empresa_actual_nombre in empresa_opciones else 0,
                    help="Solo obligatorio para gestores y comerciales"
                )
            
            empresa_id = empresas_dict.get(empresa_sel) if empresa_sel else None
        
        with col2:
            # Estado de la asignación
            if empresa_sel:
                st.success(f"✅ **Empresa asignada:** {empresa_sel}")
            else:
                if rol in ["gestor", "comercial"]:
                    st.warning("⚠️ **Empresa requerida** para este rol")
                else:
                    st.info("ℹ️ **Empresa no requerida** para administradores")

        # Credenciales (solo en creación)
        if es_creacion:
            st.markdown("### 🔐 Credenciales de acceso")
            password = st.text_input(
                "Contraseña (opcional - se genera automáticamente si se deja vacío)", 
                type="password",
                help="Deja vacío para generar una contraseña automática segura"
            )
        else:
            password = None
            # Mostrar opción para resetear contraseña
            st.markdown("### 🔐 Gestión de contraseña")
            if st.checkbox("Generar nueva contraseña", help="Marca para generar nueva contraseña automática"):
                st.info("Se generará una nueva contraseña al guardar los cambios")
                password = "NUEVA_PASSWORD_AUTO"

        # =========================
        # VALIDACIONES
        # =========================
        datos_validar = {
            "email": email,
            "nombre_completo": nombre_completo,
            "telefono": telefono,
            "nif": nif,
            "rol": rol,
            "empresa_sel": empresa_sel
        }
        
        errores = []
        error_validacion = validar_datos_usuario(datos_validar, empresas_dict, es_creacion=es_creacion)
        if error_validacion:
            errores.append(error_validacion)
        
        if errores:
            st.warning(f"⚠️ Campos pendientes: {', '.join(errores)}")
            st.info("💡 Puedes intentar guardar - se validarán al procesar")

        # =========================
        # BOTONES
        # =========================
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button(
                "➕ Crear Usuario" if es_creacion else "💾 Guardar Cambios",
                type="primary",
                use_container_width=True
            )
        with col2:
            if not es_creacion:
                eliminar = st.form_submit_button(
                    "🗑️ Eliminar",
                    type="secondary",
                    use_container_width=True
                )
            else:
                eliminar = False

        # =========================
        # PROCESAMIENTO CORREGIDO
        # =========================
        if submitted:
            if errores:
                st.error(f"❌ Corrige estos errores: {', '.join(errores)}")
            else:
                try:
                    # DATOS COMPLETOS CORREGIDOS SEGÚN EL SCHEMA
                    datos_usuario = {
                        "email": email.strip(),
                        "nombre_completo": nombre_completo.strip(),
                        "nombre": nombre_completo.strip(),  # Campo requerido
                        "telefono": telefono.strip() if telefono else None,
                        "nif": nif.strip() if nif else None,
                        "rol": rol,
                        # CORREGIDO: Solo asignar empresa_id para roles que lo necesitan
                        "empresa_id": empresa_id if rol in ["gestor", "comercial"] else None,
                        # IMPORTANTE: Los usuarios admin/gestor/comercial NO tienen grupo_id
                        # El campo grupo_id es solo para rol "alumno" (que se crea en participantes.py)
                    }
                    
                    if es_creacion:
                        # CREAR CON AUTHSERVICE - DEBUG MEJORADO
                        password_final = password.strip() if password and password.strip() != "" else None
                        
                        # DEBUG: Mostrar datos que se van a enviar
                        st.write("🔍 **Debug - Datos a insertar:**")
                        st.json(datos_usuario)
                        
                        with st.spinner("Creando usuario..."):
                            ok, usuario_id = auth_service.crear_usuario_con_auth(
                                datos_usuario, 
                                tabla="usuarios", 
                                password=password_final
                            )
                        
                        if ok:
                            st.success("✅ Usuario creado correctamente con acceso al sistema")
                            # MARCAR PARA RESET
                            st.session_state["usuario_creado_exitosamente"] = True
                            # LIMPIAR CACHE
                            if hasattr(data_service, 'get_usuarios') and hasattr(data_service.get_usuarios, 'clear'):
                                data_service.get_usuarios.clear()
                            st.rerun()
                        else:
                            st.error("❌ AuthService devolvió False. Revisa los logs del servicio.")
                    else:
                        # ACTUALIZAR CON AUTHSERVICE
                        if password == "NUEVA_PASSWORD_AUTO":
                            # Generar nueva contraseña
                            import secrets
                            import string
                            caracteres = string.ascii_letters + string.digits + "!@#$%^&*"
                            nueva_password = ''.join(secrets.choice(caracteres) for _ in range(12))
                            
                            # Actualizar contraseña en Auth
                            try:
                                auth_id = datos.get("auth_id")
                                if auth_id:
                                    auth_service.supabase.auth.admin.update_user_by_id(auth_id, {"password": nueva_password})
                                    st.success(f"🔑 Nueva contraseña generada: {nueva_password}")
                            except Exception as e:
                                st.warning(f"⚠️ Error actualizando contraseña: {e}")
                        
                        with st.spinner("Actualizando usuario..."):
                            ok = auth_service.actualizar_usuario_con_auth(
                                tabla="usuarios",
                                registro_id=datos["id"],
                                datos_editados=datos_usuario
                            )
                        
                        if ok:
                            st.success("✅ Usuario actualizado correctamente")
                            # LIMPIAR CACHE
                            if hasattr(data_service, 'get_usuarios') and hasattr(data_service.get_usuarios, 'clear'):
                                data_service.get_usuarios.clear()
                            st.rerun()
                        else:
                            st.error("❌ No se pudo actualizar el usuario.")
                            
                except Exception as e:
                    st.error(f"❌ Error procesando usuario: {str(e)}")
                    # DEBUG: Mostrar detalles del error
                    if "column" in str(e).lower():
                        st.error("💡 Error de campo de base de datos. Verifica que todos los campos existan en la tabla 'usuarios'.")

        if eliminar:
            if st.session_state.get("confirmar_eliminar_usuario"):
                try:
                    with st.spinner("Eliminando usuario..."):
                        ok = auth_service.eliminar_usuario_con_auth(
                            tabla="usuarios",
                            registro_id=datos["id"]
                        )
                    
                    if ok:
                        st.success("✅ Usuario eliminado correctamente")
                        del st.session_state["confirmar_eliminar_usuario"]
                        # LIMPIAR CACHE
                        if hasattr(data_service, 'get_usuarios') and hasattr(data_service.get_usuarios, 'clear'):
                            data_service.get_usuarios.clear()
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error eliminando usuario: {e}")
            else:
                st.session_state["confirmar_eliminar_usuario"] = True
                st.warning("⚠️ Pulsa nuevamente para confirmar eliminación")

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

    if df_usuarios.empty:
        st.info("ℹ️ No hay usuarios registrados.")
        return

    # Tabs principales (títulos simplificados como participantes)
    tabs = st.tabs(["Listado", "Crear", "Métricas"])

    # =========================
    # TAB LISTADO
    # =========================
    with tabs[0]:
        try:
            # Filtrar solo usuarios del sistema (no alumnos)
            df_filtered = df_usuarios[df_usuarios["rol"].isin(["admin", "gestor", "comercial"])].copy()
            
            # Mostrar tabla
            seleccionado, df_paged = mostrar_tabla_usuarios(df_filtered, session_state)

            # Exportación en expander (como participantes)
            st.divider()
            
            with st.expander("📥 Exportar Usuarios"):
                exportar_usuarios(df_filtered)

            with st.expander("ℹ️ Ayuda sobre Usuarios"):
                st.markdown("""
                **Funcionalidades principales:**
                - 🔍 **Filtros**: Usa los campos de búsqueda para encontrar usuarios rápidamente
                - ✏️ **Edición**: Haz clic en una fila para editar un usuario
                - 📊 **Exportar**: Gestión de datos en el expander superior
                - 🏢 **Empresa integrada**: Selección dentro del formulario

                **Roles disponibles:**
                - 👑 **Admin**: Acceso total al sistema, puede gestionar todas las empresas
                - 👨‍💼 **Gestor**: Administra una empresa específica (requiere empresa asignada)
                - 💼 **Comercial**: Gestión de CRM y clientes (requiere empresa asignada)

                **Importante:**
                - 🎓 **Los alumnos NO se crean aquí** - se crean desde "Participantes"
                - Los gestores y comerciales deben tener empresa asignada obligatoriamente
                - Las contraseñas se generan automáticamente de forma segura
                """)

            if seleccionado is not None:
                with st.container(border=True):
                    mostrar_formulario_usuario(seleccionado, data_service, auth_service, empresas_dict, es_creacion=False)

        except Exception as e:
            st.error(f"❌ Error cargando usuarios: {e}")

    # =========================
    # TAB CREAR
    # =========================
    with tabs[1]:
        with st.container(border=True):
            mostrar_formulario_usuario({}, data_service, auth_service, empresas_dict, es_creacion=True)

    # =========================
    # TAB MÉTRICAS
    # =========================
    with tabs[2]:
        mostrar_metricas_usuarios(df_usuarios)

    st.divider()
    st.caption("💡 Gestiona usuarios administrativos del sistema desde esta interfaz centralizada.")
