import streamlit as st
import pandas as pd
import re
from datetime import datetime, date
from io import BytesIO
from utils import validar_dni_cif, validar_email, get_ajustes_app
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
def mostrar_tabla_usuarios(df_usuarios, session_state, columnas_mostrar, titulo_tabla="📋 Lista de Usuarios"):
    """Muestra tabla de usuarios con filtros y selección de fila."""

    if df_usuarios.empty:
        st.info("📋 No hay usuarios para mostrar")
        return None, df_usuarios  # <- devolvemos también df vacío para consistencia

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

    # ✅ Usar columnas dinámicas desde ajustes_app
    columnas_existentes = [col for col in columnas_mostrar if col in df_filtered.columns]
    df_display = (
        df_filtered[columnas_existentes] if not df_filtered.empty
        else pd.DataFrame(columns=columnas_existentes)
    )

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
    """Formulario simplificado: crear sin empresa, editar con empresa."""
    
    if es_creacion:
        st.subheader("➕ Crear Usuario del Sistema")
        datos = {}
    else:
        st.subheader(f"✏️ Editar Usuario: {usuario_data['nombre_completo']}")
        datos = usuario_data.copy()

    form_key = f"usuario_form_{es_creacion}_{datos.get('id', 'nuevo')}"

    with st.form(form_key, clear_on_submit=es_creacion):
        
        # =========================
        # INFORMACIÓN PERSONAL (SIEMPRE)
        # =========================
        st.markdown("### 👤 Información Personal")
        col1, col2 = st.columns(2)
        
        with col1:
            email = st.text_input("Email", value=datos.get("email", ""))
            nombre_completo = st.text_input("Nombre completo", value=datos.get("nombre_completo", ""))
            telefono = st.text_input("Teléfono", value=datos.get("telefono", ""))
        
        with col2:
            nif = st.text_input("Documento (DNI/NIE/CIF)", value=datos.get("nif", ""))
            
            # Rol siempre disponible
            roles = ["", "admin", "gestor", "comercial"]
            rol_index = roles.index(datos.get("rol", "")) if datos.get("rol") in roles else 0
            rol = st.selectbox("Rol", roles, index=rol_index, 
                              help="Admin: acceso total, Gestor: empresa específica, Comercial: CRM")

        # =========================
        # EMPRESA (SOLO EN EDICIÓN)
        # =========================
        empresa_id = None
        if not es_creacion:
            st.markdown("### 🏢 Asignación de Empresa")
            
            # Mostrar empresa actual si existe
            empresa_actual = datos.get("empresa_nombre", "")
            if empresa_actual:
                st.info(f"Empresa actual: {empresa_actual}")
            
            # Campo para cambiar empresa
            empresa_opciones = [""] + sorted(empresas_dict.keys())
            empresa_index = empresa_opciones.index(empresa_actual) if empresa_actual in empresa_opciones else 0
            empresa_sel = st.selectbox(
                "Nueva empresa" if empresa_actual else "Asignar empresa", 
                empresa_opciones, 
                index=empresa_index,
                help="Selecciona empresa para gestores y comerciales"
            )
            empresa_id = empresas_dict.get(empresa_sel) if empresa_sel else None
            
            # Mostrar validación visual
            if rol in ["gestor", "comercial"]:
                if empresa_sel:
                    st.success(f"✅ Empresa asignada: {empresa_sel}")
                else:
                    st.warning("⚠️ Este rol requiere empresa asignada")
            elif empresa_sel:
                st.info("ℹ️ Los administradores no requieren empresa específica")

        # =========================
        # CREDENCIALES
        # =========================
        password = None
        if es_creacion:
            st.markdown("### 🔐 Credenciales")
            st.info("💡 Se generará contraseña automática segura al crear el usuario")
            password = st.text_input("Contraseña personalizada (opcional)", 
                                   type="password",
                                   help="Deja vacío para generar contraseña automática")
        else:
            st.markdown("### 🔐 Gestión de Contraseña")
            if st.checkbox("Generar nueva contraseña", help="Marca para generar nueva contraseña"):
                password = "NUEVA_PASSWORD_AUTO"

        # =========================
        # VALIDACIONES
        # =========================
        errores = []
        if not email:
            errores.append("Email obligatorio")
        if not nombre_completo:
            errores.append("Nombre completo obligatorio")
        if not rol:
            errores.append("Rol obligatorio")
        
        # Validación de empresa solo en edición
        if not es_creacion and rol in ["gestor", "comercial"] and not empresa_id:
            errores.append("Empresa obligatoria para gestores y comerciales")
        
        if errores:
            st.warning(f"⚠️ Campos pendientes: {', '.join(errores)}")

        # =========================
        # BOTÓN PRINCIPAL
        # =========================
        if es_creacion:
            submitted = st.form_submit_button("➕ Crear Usuario", type="primary", use_container_width=True)
            st.caption("💡 Después podrás asignar empresa editando el usuario")
        else:
            submitted = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
        
        # =========================
        # PROCESAMIENTO
        # =========================
        if submitted:
            if errores:
                st.error(f"❌ Corrige estos errores: {', '.join(errores)}")
                return
            
            # Preparar datos
            datos_usuario = {
                "email": email.strip(),
                "nombre_completo": nombre_completo.strip(),
                "nombre": nombre_completo.strip(),
                "telefono": telefono.strip() if telefono else None,
                "nif": nif.strip() if nif else None,
                "rol": rol,
                "empresa_id": empresa_id,  # None para creación, puede ser algo para edición
            }
            
            try:
                if es_creacion:
                    # CREAR: Sin empresa, se asigna después
                    password_final = password.strip() if password and password.strip() else None
                    
                    ok, usuario_id = auth_service.crear_usuario_con_auth(
                        datos_usuario, 
                        tabla="usuarios",
                        password=password_final
                    )
                    
                    if ok:
                        st.success("✅ Usuario creado correctamente")
                        if rol in ["gestor", "comercial"]:
                            st.info("💡 Ve a la pestaña 'Listado' para asignarle una empresa")
                        st.balloons()
                        
                        # Limpiar cache
                        if hasattr(data_service, 'get_usuarios') and hasattr(data_service.get_usuarios, 'clear'):
                            data_service.get_usuarios.clear()
                        st.rerun()
                    else:
                        st.error("❌ Error al crear usuario")
                        
                else:
                    # ACTUALIZAR: Incluye empresa
                    if password == "NUEVA_PASSWORD_AUTO":
                        # Generar nueva contraseña
                        import secrets
                        import string
                        caracteres = string.ascii_letters + string.digits + "!@#$%^&*"
                        nueva_password = ''.join(secrets.choice(caracteres) for _ in range(12))
                        
                        try:
                            auth_id = datos.get("auth_id")
                            if auth_id:
                                auth_service.supabase.auth.admin.update_user_by_id(auth_id, {"password": nueva_password})
                                st.success(f"🔑 Nueva contraseña generada: {nueva_password}")
                        except Exception as e:
                            st.warning(f"⚠️ Error actualizando contraseña: {e}")
                    
                    ok = auth_service.actualizar_usuario_con_auth(
                        tabla="usuarios",
                        registro_id=datos["id"],
                        datos_editados=datos_usuario
                    )
                    
                    if ok:
                        st.success("✅ Usuario actualizado correctamente")
                        if hasattr(data_service, 'get_usuarios') and hasattr(data_service.get_usuarios, 'clear'):
                            data_service.get_usuarios.clear()
                        st.rerun()
                    else:
                        st.error("❌ Error al actualizar usuario")
                        
            except Exception as e:
                st.error(f"❌ Error procesando usuario: {str(e)}")

    # =========================
    # BOTÓN ELIMINAR (solo edición, fuera del form)
    # =========================
    if not es_creacion:
        st.markdown("---")
        col1, col2, col3 = st.columns([1,1,1])
        with col2:
            if st.button("🗑️ Eliminar Usuario", type="secondary", use_container_width=True):
                if st.session_state.get("confirmar_eliminar_usuario"):
                    try:
                        ok = auth_service.eliminar_usuario_con_auth(
                            tabla="usuarios",
                            registro_id=datos["id"]
                        )
                        
                        if ok:
                            st.success("✅ Usuario eliminado correctamente")
                            del st.session_state["confirmar_eliminar_usuario"]
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

        with tabs[0]:
        st.markdown("### 📊 Listado de Usuarios")

        # =========================
        # Leer columnas dinámicas desde ajustes
        # =========================
        ajustes = get_ajustes_app(supabase, campos=["columnas_usuarios"])
        columnas_mostrar = ajustes.get("columnas_usuarios")

        # ✅ Fallback si viene None o vacío
        if not columnas_mostrar:
            columnas_mostrar = [
                "nombre_completo", "email", "telefono",
                "rol", "empresa_nombre", "created_at"
            ]

        # Filtrar solo las columnas que existen en df
        columnas_mostrar = [col for col in columnas_mostrar if col in df_usuarios.columns]

        # =========================
        # Configuración de columnas visibles (solo admin)
        # =========================
        if session_state.role == "admin":
            st.subheader("⚙️ Configuración de columnas visibles")

            columnas_disponibles = df_usuarios.columns.tolist()

            columnas_seleccionadas = st.multiselect(
                "Selecciona las columnas a mostrar",
                options=columnas_disponibles,
                default=columnas_mostrar if columnas_mostrar else columnas_disponibles
            )

            if st.button("💾 Guardar columnas", type="primary"):
                if not columnas_seleccionadas:
                    st.warning("⚠️ Debes seleccionar al menos una columna")
                else:
                    from utils import update_ajustes_app
                    update_ajustes_app(supabase, {"columnas_usuarios": columnas_seleccionadas})
                    st.success("✅ Columnas guardadas correctamente")
                    st.rerun()

        # =========================
        # Mostrar tabla con columnas dinámicas
        # =========================
        try:
            df_filtered = df_usuarios[df_usuarios["rol"].isin(["admin", "gestor", "comercial"])].copy()
            seleccionado, df_paged = mostrar_tabla_usuarios(df_filtered, session_state, columnas_mostrar)

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
