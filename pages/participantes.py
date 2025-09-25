import streamlit as st
import pandas as pd
import io
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from utils import validar_dni_cif, export_csv
from services.participantes_service import get_participantes_service
from services.empresas_service import get_empresas_service
from services.grupos_service import get_grupos_service
from services.auth_service import get_auth_service

# =========================
# CONFIG STREAMLIT
# =========================
st.set_page_config(
    page_title="👥 Participantes",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# HELPERS CACHEADOS
# =========================
@st.cache_data(ttl=300)
def cargar_empresas_disponibles(_empresas_service, _session_state):
    """CORREGIDO: Devuelve las empresas disponibles según rol usando el nuevo sistema de jerarquía."""
    try:
        # Tu EmpresasService ya tiene implementado get_empresas_con_jerarquia() correctamente
        df = _empresas_service.get_empresas_con_jerarquia()
        
        if df.empty:
            return df

        # El método get_empresas_con_jerarquia() ya maneja el filtrado por rol internamente
        # Para gestor: devuelve su empresa + sus clientes
        # Para admin: devuelve todas las empresas
        # No necesitamos filtrado adicional aquí
        
        return df
            
    except Exception as e:
        st.error(f"❌ Error cargando empresas disponibles: {e}")
        # Debug mejorado
        st.write(f"Debug - Role: {_session_state.role}")
        if hasattr(_session_state, 'user'):
            st.write(f"Debug - User: {_session_state.user}")
        st.write(f"Debug - Error details: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def cargar_grupos(_grupos_service, _session_state):
    """CORREGIDO: Carga grupos disponibles según permisos, simplificado."""
    try:
        # Usar el método que existe en grupos_service
        df_grupos = _grupos_service.get_grupos_completos()
        
        if df_grupos.empty:
            return df_grupos
            
        # Para admin: devolver todos los grupos
        if _session_state.role == "admin":
            return df_grupos
            
        # Para gestor: filtrar por empresa usando empresas_grupos (relación N:N)
        elif _session_state.role == "gestor":
            empresa_id = _session_state.user.get("empresa_id")
            if not empresa_id:
                return pd.DataFrame()
                
            try:
                # Obtener todos los grupos donde participa la empresa del gestor
                # O cualquiera de sus empresas clientes
                
                # 1. Obtener empresas gestionables (su empresa + clientes)
                empresas_gestionables = [empresa_id]
                
                # Añadir empresas clientes
                clientes_res = _grupos_service.supabase.table("empresas").select("id").eq(
                    "empresa_matriz_id", empresa_id
                ).execute()
                
                if clientes_res.data:
                    empresas_gestionables.extend([c["id"] for c in clientes_res.data])
                
                # 2. Obtener grupos de estas empresas
                empresas_grupos = _grupos_service.supabase.table("empresas_grupos").select(
                    "grupo_id"
                ).in_("empresa_id", empresas_gestionables).execute()
                
                grupo_ids = [eg["grupo_id"] for eg in (empresas_grupos.data or [])]
                
                if grupo_ids:
                    return df_grupos[df_grupos["id"].isin(grupo_ids)]
                else:
                    return pd.DataFrame()
                    
            except Exception as e:
                st.error(f"Error filtrando grupos para gestor: {e}")
                return pd.DataFrame()
                
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Error cargando grupos: {e}")
        return pd.DataFrame()

# =========================
# MÉTRICAS DE PARTICIPANTES
# =========================
def mostrar_metricas_participantes(participantes_service, session_state):
    """Muestra métricas generales calculadas directamente desde los datos."""
    try:
        # Calcular métricas directamente desde get_participantes_completos
        df = participantes_service.get_participantes_completos()
        
        if df.empty:
            metricas = {"total": 0, "con_grupo": 0, "sin_grupo": 0, "nuevos_mes": 0, "con_diploma": 0}
        else:
            # Filtrar por rol si es gestor
            if session_state.role == "gestor":
                empresa_id = session_state.user.get("empresa_id")
                df = df[df["empresa_id"] == empresa_id]
            
            total = len(df)
            con_grupo = len(df[df["grupo_id"].notna()]) if "grupo_id" in df.columns else 0
            sin_grupo = total - con_grupo
            
            # Participantes nuevos este mes
            nuevos_mes = 0
            if "created_at" in df.columns:
                try:
                    df['created_at_dt'] = pd.to_datetime(df["created_at"], errors="coerce")
                    mes_actual = datetime.now().month
                    año_actual = datetime.now().year
                    nuevos_mes = len(df[
                        (df['created_at_dt'].dt.month == mes_actual) & 
                        (df['created_at_dt'].dt.year == año_actual)
                    ])
                except:
                    nuevos_mes = 0
            
            # Diplomas (consulta directa si es necesario)
            con_diploma = 0
            try:
                if not df.empty:
                    participante_ids = df["id"].tolist()
                    diplomas_res = participantes_service.supabase.table("diplomas").select("participante_id").in_("participante_id", participante_ids).execute()
                    con_diploma = len(set(d["participante_id"] for d in (diplomas_res.data or [])))
            except:
                pass
            
            metricas = {
                "total": total,
                "con_grupo": con_grupo,
                "sin_grupo": sin_grupo,
                "nuevos_mes": nuevos_mes,
                "con_diploma": con_diploma
            }

        # Mostrar métricas con mejor diseño
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("👥 Total", metricas["total"], 
                     delta=f"+{metricas['nuevos_mes']}" if metricas['nuevos_mes'] > 0 else None)
        with col2:
            st.metric("🎓 Con grupo", metricas["con_grupo"])
        with col3:
            st.metric("❓ Sin grupo", metricas["sin_grupo"])
        with col4:
            st.metric("🆕 Nuevos (mes)", metricas["nuevos_mes"])
        with col5:
            st.metric("📜 Con diploma", metricas["con_diploma"])
        
        # Gráfico de distribución si hay datos
        if metricas["total"] > 0:
            st.markdown("#### 📊 Distribución")
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                # Gráfico de grupos
                import plotly.express as px
                data_grupos = {
                    "Estado": ["Con grupo", "Sin grupo"],
                    "Cantidad": [metricas["con_grupo"], metricas["sin_grupo"]]
                }
                fig_grupos = px.pie(values=data_grupos["Cantidad"], names=data_grupos["Estado"], 
                                   title="Asignación a grupos")
                st.plotly_chart(fig_grupos, use_container_width=True)
            
            with col_chart2:
                # Gráfico de diplomas
                data_diplomas = {
                    "Estado": ["Con diploma", "Sin diploma"],
                    "Cantidad": [metricas["con_diploma"], metricas["total"] - metricas["con_diploma"]]
                }
                fig_diplomas = px.pie(values=data_diplomas["Cantidad"], names=data_diplomas["Estado"],
                                     title="Diplomas obtenidos")
                st.plotly_chart(fig_diplomas, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Error calculando métricas: {e}")
        # Mostrar métricas vacías
        col1, col2, col3, col4, col5 = st.columns(5)
        for col, label in zip([col1, col2, col3, col4, col5], 
                             ["👥 Total", "🎓 Con grupo", "❓ Sin grupo", "🆕 Nuevos", "📜 Diplomas"]):
            with col:
                st.metric(label, 0)

# =========================
# TABLA GENERAL
# =========================
def mostrar_tabla_participantes(df_participantes, session_state, titulo_tabla="📋 Lista de Participantes"):
    """Muestra tabla de participantes con filtros, paginación y selección de fila."""
    if df_participantes.empty:
        st.info("📋 No hay participantes para mostrar")
        return None

    st.markdown(f"### {titulo_tabla}")

    # 🔎 Filtros avanzados (fijos arriba)
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_nombre = st.text_input("👤 Nombre/Apellidos contiene", key="filtro_tabla_nombre")
    with col2:
        filtro_dni = st.text_input("🆔 Documento contiene", key="filtro_tabla_dni")
    with col3:
        filtro_empresa = st.text_input("🏢 Empresa contiene", key="filtro_tabla_empresa")

    if filtro_nombre:
        df_participantes = df_participantes[
            df_participantes["nombre"].str.contains(filtro_nombre, case=False, na=False) |
            df_participantes["apellidos"].str.contains(filtro_nombre, case=False, na=False)
        ]
    if filtro_dni:
        df_participantes = df_participantes[df_participantes["dni"].str.contains(filtro_dni, case=False, na=False)]
    if filtro_empresa:
        df_participantes = df_participantes[df_participantes["empresa_nombre"].str.contains(filtro_empresa, case=False, na=False)]

    # 📢 Selector de registros por página
    page_size = st.selectbox("📊 Registros por página", [10, 20, 50, 100], index=1, key="page_size_tabla")

    # 📄 Paginación
    total_rows = len(df_participantes)
    total_pages = (total_rows // page_size) + (1 if total_rows % page_size else 0)
    page_number = st.number_input("Página", min_value=1, max_value=max(total_pages, 1), step=1, value=1, key="page_num_tabla")

    start_idx = (page_number - 1) * page_size
    end_idx = start_idx + page_size
    df_paged = df_participantes.iloc[start_idx:end_idx]

    # Configuración columnas
    columnas = ["nombre", "apellidos", "dni", "email", "telefono", "empresa_nombre"]
    column_config = {
        "nombre": st.column_config.TextColumn("👤 Nombre", width="medium"),
        "apellidos": st.column_config.TextColumn("👥 Apellidos", width="large"),
        "dni": st.column_config.TextColumn("🆔 Documento", width="small"),
        "email": st.column_config.TextColumn("📧 Email", width="large"),
        "telefono": st.column_config.TextColumn("📞 Teléfono", width="medium"),
        "empresa_nombre": st.column_config.TextColumn("🏢 Empresa", width="large")
    }

    # Mostrar tabla
    evento = st.dataframe(
        df_paged[columnas],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    if evento.selection.rows:
        return df_paged.iloc[evento.selection.rows[0]], df_paged
    return None, df_paged

# =========================
# FORMULARIO DE PARTICIPANTE INTEGRADO
# =========================
def mostrar_formulario_participante(
    participante_data,
    participantes_service,
    empresas_service,
    grupos_service,
    auth_service,
    session_state,
    es_creacion=False
):
    """CORREGIDO: Formulario completamente integrado con todos los campos dentro."""

    if es_creacion:
        st.subheader("➕ Crear Participante")
        datos = {}
    else:
        st.subheader(f"✏️ Editar Participante: {participante_data['nombre']} {participante_data.get('apellidos','')}")
        datos = participante_data.copy()

    form_id = f"participante_{datos.get('id','nuevo')}_{'crear' if es_creacion else 'editar'}"

    # Cargar datos para selectboxes
    df_empresas = cargar_empresas_disponibles(empresas_service, session_state)
    empresa_options = {row["nombre"]: row["id"] for _, row in df_empresas.iterrows()}
    
    df_grupos = cargar_grupos(grupos_service, session_state)
    grupos_completos = {f"{row['codigo_grupo']} - {row.get('accion_formativa_titulo', 'Sin título')}": row["id"] for _, row in df_grupos.iterrows()}

    with st.form(form_id, clear_on_submit=es_creacion):
        
        # =========================
        # DATOS PERSONALES
        # =========================
        st.markdown("### 👤 Datos Personales")
        col1, col2 = st.columns(2)
        
        with col1:
            nombre = st.text_input("Nombre", value=datos.get("nombre",""), key=f"{form_id}_nombre")
            apellidos = st.text_input("Apellidos", value=datos.get("apellidos",""), key=f"{form_id}_apellidos")
            tipo_documento = st.selectbox(
                "Tipo de Documento",
                options=["", "DNI", "NIE", "PASAPORTE"],
                index=["","DNI","NIE","PASAPORTE"].index(datos.get("tipo_documento","")) if datos.get("tipo_documento","") in ["","DNI","NIE","PASAPORTE"] else 0,
                key=f"{form_id}_tipo_doc"
            )
            documento = st.text_input("Número de Documento", value=datos.get("dni",""), key=f"{form_id}_documento", help="DNI, NIE, CIF o Pasaporte")
            niss = st.text_input("NISS", value=datos.get("niss",""), key=f"{form_id}_niss", help="Número de la Seguridad Social")
        
        with col2:
            fecha_nacimiento = st.date_input(
                "Fecha de nacimiento",
                value=datos.get("fecha_nacimiento") if datos.get("fecha_nacimiento") else date(1990,1,1),
                key=f"{form_id}_fecha_nac"
            )
            sexo = st.selectbox(
                "Sexo",
                options=["", "M", "F", "O"],
                index=["","M","F","O"].index(datos.get("sexo","")) if datos.get("sexo","") in ["","M","F","O"] else 0,
                key=f"{form_id}_sexo"
            )
            telefono = st.text_input("Teléfono", value=datos.get("telefono",""), key=f"{form_id}_tel")
            email = st.text_input("Email", value=datos.get("email",""), key=f"{form_id}_email")

        # =========================
        # EMPRESA Y GRUPO (INTEGRADO Y CORREGIDO)
        # =========================
        st.markdown("### 🏢 Empresa y Formación")
        col1, col2 = st.columns(2)
        
        with col1:
            # Empresa - Manejo robusto de opciones
            try:
                empresa_actual_id = datos.get("empresa_id")
                empresa_actual_nombre = ""
                
                # Buscar nombre actual de forma segura
                if empresa_actual_id and empresa_options:
                    empresa_actual_nombre = next(
                        (k for k, v in empresa_options.items() if v == empresa_actual_id), 
                        ""
                    )
            
                empresa_sel = st.selectbox(
                    "🏢 Empresa",
                    options=[""] + list(empresa_options.keys()) if empresa_options else ["Sin empresas disponibles"],
                    index=list(empresa_options.keys()).index(empresa_actual_nombre) + 1 if empresa_actual_nombre and empresa_actual_nombre in empresa_options else 0,
                    key=f"{form_id}_empresa",
                    help="Empresa a la que pertenece el participante",
                    disabled=not empresa_options  # Deshabilitar si no hay opciones
                )
                
                # Obtener empresa_id de forma segura
                if empresa_sel and empresa_sel != "Sin empresas disponibles":
                    empresa_id = empresa_options.get(empresa_sel)
                else:
                    empresa_id = None
                    if not empresa_options:
                        st.warning("⚠️ No hay empresas disponibles para tu rol")
                        
            except Exception as e:
                st.error(f"❌ Error cargando empresas: {e}")
                empresa_id = None
        
        with col2:
            # Grupo (filtrado por empresa) - CORREGIDO
            try:
                if empresa_id and grupos_completos:
                    # NUEVA LÓGICA: Filtrar grupos por empresa de forma más robusta
                    grupos_empresa = {}
                    
                    for grupo_nombre, grupo_id_val in grupos_completos.items():
                        # Buscar el grupo en el DataFrame original
                        grupo_row = df_grupos[df_grupos["id"] == grupo_id_val]
                        
                        if not grupo_row.empty:
                            grupo_data = grupo_row.iloc[0]
                            grupo_empresa_id = None
                            
                            # Extraer empresa_id de diferentes formatos posibles
                            if "empresa_id" in grupo_data and pd.notna(grupo_data["empresa_id"]):
                                grupo_empresa_id = grupo_data["empresa_id"]
                            elif "empresa" in grupo_data and isinstance(grupo_data["empresa"], dict):
                                grupo_empresa_id = grupo_data["empresa"].get("id")
                            elif "empresa" in grupo_data and pd.notna(grupo_data["empresa"]):
                                # Caso de empresa como string o ID directo
                                try:
                                    grupo_empresa_id = str(grupo_data["empresa"])
                                except:
                                    pass
                            
                            # También verificar en empresas_grupos (relación N:N)
                            if not grupo_empresa_id:
                                try:
                                    empresas_grupo_check = grupos_service.supabase.table("empresas_grupos").select("empresa_id").eq("grupo_id", grupo_id_val).execute()
                                    if empresas_grupo_check.data:
                                        grupo_empresas_ids = [eg["empresa_id"] for eg in empresas_grupo_check.data]
                                        if empresa_id in grupo_empresas_ids:
                                            grupos_empresa[grupo_nombre] = grupo_id_val
                                except:
                                    pass
                            elif str(grupo_empresa_id) == str(empresa_id):
                                grupos_empresa[grupo_nombre] = grupo_id_val
                    
                    # Mostrar selector de grupo
                    if grupos_empresa:
                        grupo_actual_id = datos.get("grupo_id")
                        grupo_actual_nombre = next((k for k, v in grupos_empresa.items() if v == grupo_actual_id), "")
                
                        grupo_sel = st.selectbox(
                            "🎓 Grupo de Formación",
                            options=[""] + list(grupos_empresa.keys()),
                            index=list(grupos_empresa.keys()).index(grupo_actual_nombre) + 1 if grupo_actual_nombre else 0,
                            key=f"{form_id}_grupo",
                            help="Grupo de formación (opcional)"
                        )
                        grupo_id = grupos_empresa.get(grupo_sel) if grupo_sel else None
                    else:
                        st.selectbox(
                            "🎓 Grupo de Formación",
                            options=["No hay grupos disponibles para esta empresa"],
                            disabled=True,
                            key=f"{form_id}_grupo_no_disponible"
                        )
                        grupo_id = None
                        
                elif empresa_id:
                    # Tiene empresa pero no hay grupos cargados
                    st.selectbox(
                        "🎓 Grupo de Formación", 
                        options=["Cargando grupos..."],
                        disabled=True,
                        key=f"{form_id}_grupo_cargando"
                    )
                    grupo_id = None
                else:
                    # No tiene empresa seleccionada
                    st.selectbox(
                        "🎓 Grupo de Formación",
                        options=["Seleccione empresa primero"],
                        disabled=True,
                        key=f"{form_id}_grupo_disabled"
                    )
                    grupo_id = None
                    
            except Exception as e:
                st.error(f"❌ Error procesando grupos: {e}")
                st.selectbox(
                    "🎓 Grupo de Formación",
                    options=["Error cargando grupos"],
                    disabled=True,
                    key=f"{form_id}_grupo_error"
                )
                grupo_id = None
        
        # Credenciales Auth (solo en creación)
        if es_creacion:
            st.markdown("### 🔐 Credenciales de acceso")
            password = st.text_input(
                "Contraseña (opcional - se genera automáticamente si se deja vacío)", 
                type="password", 
                key=f"{form_id}_password",
                help="Deja vacío para generar una contraseña automática segura"
            )
        else:
            password = None
            # Mostrar opción para resetear contraseña
            st.markdown("### 🔐 Gestión de contraseña")
            if st.checkbox(
                "Generar nueva contraseña",
                key=f"{form_id}_reset_pass",
                help="Marca para generar nueva contraseña automática"
            ):
                st.info("Se generará una nueva contraseña al guardar los cambios")
                password = "NUEVA_PASSWORD_AUTO"  # Flag para generar nueva

        # =========================
        # VALIDACIONES
        # =========================
        errores = []
        if not nombre:
            errores.append("Nombre requerido")
        if not apellidos:
            errores.append("Apellidos requeridos")
        if documento and not validar_dni_cif(documento):
            errores.append("Documento inválido")
        if not empresa_id:
            errores.append("Debe seleccionar una empresa")
        if es_creacion and not email:
            errores.append("Email obligatorio para crear participante")

        # Mostrar errores pero no deshabilitar botón
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
                "➕ Crear Participante" if es_creacion else "💾 Guardar Cambios",
                type="primary",
                use_container_width=True
            )
        with col2:
            eliminar = st.form_submit_button(
                "🗑️ Eliminar" if not es_creacion and session_state.role == "admin" else "❌ Cancelar",
                type="secondary",
                use_container_width=True
            ) if not es_creacion else False

        # =========================
        # PROCESAMIENTO
        # =========================
        if submitted:
            # Validación final antes de procesar
            if errores:
                st.error(f"❌ Corrige estos errores: {', '.join(errores)}")
            else:
                datos_payload = {
                    "nombre": nombre,
                    "apellidos": apellidos,
                    "tipo_documento": tipo_documento or None,
                    "dni": documento or None,  # Guardamos el documento en el campo dni
                    "niss": niss or None,
                    "fecha_nacimiento": fecha_nacimiento.isoformat() if fecha_nacimiento else None,
                    "sexo": sexo or None,
                    "telefono": telefono or None,
                    "email": email or None,
                    "empresa_id": empresa_id,
                    "grupo_id": grupo_id or None,
                }

                if es_creacion:
                    # USAR AUTHSERVICE CENTRALIZADO
                    password_final = password if password and password != "" else None
                    
                    ok, participante_id = auth_service.crear_usuario_con_auth(
                        datos_payload, 
                        tabla="participantes", 
                        password=password_final
                    )
                    
                    if ok:
                        st.success("✅ Participante creado correctamente con acceso al portal")
                        st.rerun()
                else:
                    # ACTUALIZAR USANDO AUTHSERVICE
                    password_final = None
                    if password == "NUEVA_PASSWORD_AUTO":
                        # Generar nueva contraseña
                        import secrets
                        import string
                        caracteres = string.ascii_letters + string.digits + "!@#$%^&*"
                        password_final = ''.join(secrets.choice(caracteres) for _ in range(12))
                        
                        # Actualizar en Auth también
                        try:
                            # Buscar auth_id
                            participante_auth = participantes_service.supabase.table("participantes").select("auth_id").eq("id", datos["id"]).execute()
                            if participante_auth.data and participante_auth.data[0].get("auth_id"):
                                auth_id = participante_auth.data[0]["auth_id"]
                                participantes_service.supabase.auth.admin.update_user_by_id(auth_id, {"password": password_final})
                                st.success(f"🔑 Nueva contraseña generada: {password_final}")
                        except Exception as e:
                            st.warning(f"⚠️ Error actualizando contraseña en Auth: {e}")
                    
                    ok = auth_service.actualizar_usuario_con_auth(
                        tabla="participantes",
                        registro_id=datos["id"],
                        datos_editados=datos_payload
                    )
                    
                    if ok:
                        st.success("✅ Cambios guardados correctamente")
                        st.rerun()

        if eliminar:
            if st.session_state.get("confirmar_eliminar_participante"):
                try:
                    # ELIMINAR USANDO AUTHSERVICE
                    ok = auth_service.eliminar_usuario_con_auth(
                        tabla="participantes",
                        registro_id=datos["id"]
                    )
                    
                    if ok:
                        st.success("✅ Participante eliminado correctamente")
                        del st.session_state["confirmar_eliminar_participante"]
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error eliminando participante: {e}")
            else:
                st.session_state["confirmar_eliminar_participante"] = True
                st.warning("⚠️ Pulsa nuevamente para confirmar eliminación")

# =========================
# EXPORTACIÓN DE PARTICIPANTES
# =========================
def exportar_participantes(participantes_service, session_state, df_filtrado=None, solo_visibles=False):
    """Exporta participantes a CSV respetando filtros, paginación y rol."""
    try:
        # Si no se pasa df_filtrado, cargamos todo desde el servicio
        if df_filtrado is None:
            df = participantes_service.get_participantes_completos()
            # 🔒 Filtrado por rol
            if session_state.role == "gestor":
                empresa_id = session_state.user.get("empresa_id")
                df = df[df["empresa_id"] == empresa_id]
        else:
            df = df_filtrado.copy()

        if df.empty:
            st.warning("⚠️ No hay participantes para exportar.")
            return

        # 📘 Opción de exportación
        export_scope = st.radio(
            "¿Qué quieres exportar?",
            ["📄 Solo registros visibles en la tabla", "🌍 Todos los registros filtrados"],
            horizontal=True
        )

        if export_scope == "📄 Solo registros visibles en la tabla" and solo_visibles:
            df_export = df
        else:
            # Recargamos completo para "Todos los registros filtrados"
            df_export = participantes_service.get_participantes_completos()
            if session_state.role == "gestor":
                empresa_id = session_state.user.get("empresa_id")
                df_export = df_export[df_export["empresa_id"] == empresa_id]

        st.download_button(
            "📥 Exportar participantes a CSV",
            data=df_export.to_csv(index=False).encode("utf-8"),
            file_name=f"participantes_{datetime.today().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    except Exception as e:
        st.error(f"❌ Error exportando participantes: {e}")

# =========================
# IMPORTACIÓN DE PARTICIPANTES
# =========================
def importar_participantes(auth_service, empresas_service, session_state):
    """CORREGIDO: Importa participantes usando AuthService centralizado."""
    uploaded = st.file_uploader("📤 Subir archivo CSV/XLSX", type=["csv", "xlsx"], accept_multiple_files=False)

    # 📊 Plantilla de ejemplo
    ejemplo_df = pd.DataFrame([{
        "nombre": "Juan",
        "apellidos": "Pérez Gómez",
        "dni": "12345678A",
        "email": "juan.perez@correo.com",
        "telefono": "600123456",
        "empresa_id": "",
        "grupo_id": "",
        "password": ""   # opcional → si está vacío se genera aleatorio
    }])

    buffer = io.BytesIO()
    ejemplo_df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    st.download_button(
        "📊 Descargar plantilla XLSX",
        data=buffer,
        file_name="plantilla_participantes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    if not uploaded:
        return

    try:
        if uploaded.name.endswith(".csv"):
            df = pd.read_csv(uploaded, dtype=str).fillna("")
        else:
            df = pd.read_excel(uploaded, dtype=str).fillna("")

        st.success(f"✅ {len(df)} filas cargadas desde {uploaded.name}")
        st.dataframe(df.head(10), use_container_width=True)

        if st.button("🚀 Importar participantes", type="primary", use_container_width=True):
            errores, creados = [], 0
            for idx, fila in df.iterrows():
                try:
                    # === Validaciones mínimas ===
                    if not fila.get("nombre") or not fila.get("apellidos") or not fila.get("email"):
                        raise ValueError("Nombre, apellidos y email son obligatorios")

                    if "@" not in fila["email"]:
                        raise ValueError(f"Email inválido: {fila['email']}")

                    # Empresa según rol
                    if session_state.role == "gestor":
                        empresa_id = session_state.user.get("empresa_id")
                    else:
                        empresa_id = fila.get("empresa_id") or None

                    grupo_id = fila.get("grupo_id") or None
                    password = fila.get("password") or None  # AuthService generará una si es None

                    datos = {
                        "nombre": fila.get("nombre"),
                        "apellidos": fila.get("apellidos"),
                        "dni": fila.get("dni") or fila.get("documento"),  # Compatibilidad con ambos nombres
                        "email": fila.get("email"),
                        "telefono": fila.get("telefono"),
                        "empresa_id": empresa_id,
                        "grupo_id": grupo_id,
                    }

                    # USAR AUTHSERVICE CENTRALIZADO
                    ok, participante_id = auth_service.crear_usuario_con_auth(
                        datos, 
                        tabla="participantes", 
                        password=password
                    )
                    
                    if ok:
                        creados += 1
                    else:
                        raise ValueError("Error al crear participante con AuthService")

                except Exception as ex:
                    errores.append(f"Fila {idx+1}: {ex}")

            if errores:
                st.error("⚠️ Errores durante la importación:")
                for e in errores:
                    st.text(e)
            if creados:
                st.success(f"✅ {creados} participantes importados correctamente")
                st.rerun()

    except Exception as e:
        st.error(f"❌ Error importando participantes: {e}")
        
# =========================
# MAIN PARTICIPANTES
# =========================
def main(supabase, session_state):
    st.title("👥 Gestión de Participantes")

    participantes_service = get_participantes_service(supabase, session_state)
    empresas_service = get_empresas_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)
    auth_service = get_auth_service(supabase, session_state)  # NUEVO: AuthService centralizado

    # Tabs principales (títulos simplificados)
    tabs = st.tabs(["Listado", "Crear", "Métricas", "Diplomas"])

    # =========================
    # TAB LISTADO
    # =========================
    with tabs[0]:
        try:
            df_participantes = participantes_service.get_participantes_completos()

            # Filtrado por rol gestor
            if session_state.role == "gestor":
                empresas_df = cargar_empresas_disponibles(empresas_service, session_state)
                empresas_ids = empresas_df["id"].tolist()
                df_participantes = df_participantes[df_participantes["empresa_id"].isin(empresas_ids)]

            # Mostrar tabla (con filtros + paginación ya integrados)
            resultado = mostrar_tabla_participantes(df_participantes, session_state)
            if resultado is not None and len(resultado) == 2:
                seleccionado, df_paged = resultado
            else:
                seleccionado, df_paged = None, pd.DataFrame()

            # Exportación e importación en expanders organizados
            st.divider()
            
            with st.expander("📥 Exportar Participantes"):
                exportar_participantes(participantes_service, session_state, df_filtrado=df_paged, solo_visibles=True)
            
            with st.expander("📤 Importar Participantes"):
                importar_participantes(auth_service, empresas_service, session_state)

            with st.expander("ℹ️ Ayuda sobre Participantes"):
                st.markdown("""
                **Funcionalidades principales:**
                - 🔍 **Filtros**: Usa los campos de búsqueda para encontrar participantes rápidamente
                - ✏️ **Edición**: Haz clic en una fila para editar un participante
                - 📊 **Exportar/Importar**: Gestión masiva de datos en los expanders superiores
                - 🏢 **Empresas y grupos**: Los selectores están conectados - primero empresa, luego grupo
                - 🎓 **Diplomas**: Nueva pestaña para gestionar certificados
                
                **Permisos por rol:**
                - 👑 **Admin**: Ve todos los participantes de todas las empresas
                - 👨‍💼 **Gestor**: Solo ve participantes de su empresa y empresas clientes
                
                **Importante:**
                - Los participantes creados aquí automáticamente tienen acceso al portal de alumnos
                - Las contraseñas se generan automáticamente de forma segura
                - Los campos empresa y grupo están integrados en el formulario para mejor usabilidad
                """)

            if seleccionado is not None:
                with st.container(border=True):
                    mostrar_formulario_participante(
                        seleccionado, participantes_service, empresas_service, grupos_service, auth_service, session_state, es_creacion=False
                    )
        except Exception as e:
            st.error(f"❌ Error cargando participantes: {e}")

    # =========================
    # TAB CREAR
    # =========================
    with tabs[1]:
        with st.container(border=True):
            mostrar_formulario_participante(
                {}, participantes_service, empresas_service, grupos_service, auth_service, session_state, es_creacion=True
            )

    # =========================
    # TAB MÉTRICAS
    # =========================
    with tabs[2]:
        mostrar_metricas_participantes(participantes_service, session_state)
        
    # =========================
    # NUEVO TAB DIPLOMAS
    # =========================
    with tabs[3]:
        mostrar_gestion_diplomas_participantes(supabase, session_state, participantes_service)   

# =========================
# HELPERS DE ESTADO Y VALIDACIÓN
# =========================
def mostrar_gestion_diplomas_participantes(supabase, session_state, participantes_service):
    """
    Gestión completa de diplomas con jerarquía empresarial y subida de archivos.
    INTEGRADO desde participantesultimo.py para participantes(13).py
    """
    st.divider()
    st.markdown("### 🎓 Gestión de Diplomas por Participante")
    st.caption("Subir y gestionar diplomas organizados por estructura empresarial")

    # Verificar permisos
    puede_gestionar = session_state.role in ["admin", "gestor"]
    if not puede_gestionar:
        st.warning("🔒 No tienes permisos para gestionar diplomas")
        return

    try:
        # Obtener empresas permitidas según jerarquía
        empresas_permitidas = participantes_service._get_empresas_gestionables()
        if not empresas_permitidas:
            st.info("No tienes grupos finalizados disponibles.")
            return
        
        hoy = datetime.now().date()
        
        # Consulta con filtro jerárquico para grupos finalizados
        query = supabase.table("grupos").select("""
            id, codigo_grupo, fecha_fin, fecha_fin_prevista, empresa_id,
            accion_formativa:acciones_formativas(nombre)
        """).in_("empresa_id", empresas_permitidas)
        
        grupos_res = query.execute()
        grupos_data = grupos_res.data or []
        
        # Filtrar grupos finalizados
        grupos_finalizados = []
        for grupo in grupos_data:
            fecha_fin = grupo.get("fecha_fin") or grupo.get("fecha_fin_prevista")
            if fecha_fin:
                try:
                    fecha_fin_dt = pd.to_datetime(fecha_fin, errors='coerce').date()
                    if fecha_fin_dt <= hoy:
                        grupos_finalizados.append(grupo)
                except:
                    continue
        
        if not grupos_finalizados:
            st.info("No hay grupos finalizados en las empresas que gestionas.")
            return

        # Obtener participantes de grupos finalizados
        grupos_finalizados_ids = [g["id"] for g in grupos_finalizados]
        
        participantes_res = supabase.table("participantes").select("""
            id, nombre, apellidos, email, grupo_id, nif, empresa_id
        """).in_("grupo_id", grupos_finalizados_ids).in_("empresa_id", empresas_permitidas).execute()
        
        participantes_finalizados = participantes_res.data or []
        
        if not participantes_finalizados:
            st.info("No hay participantes en grupos finalizados de tus empresas.")
            return

        # Crear diccionario de grupos para mapeo
        grupos_dict_completo = {g["id"]: g for g in grupos_finalizados}
        
        # Obtener diplomas existentes
        participantes_ids = [p["id"] for p in participantes_finalizados]
        diplomas_res = supabase.table("diplomas").select("participante_id, id").in_(
            "participante_id", participantes_ids
        ).execute()
        participantes_con_diploma = {d["participante_id"] for d in diplomas_res.data or []}
        
        # Métricas principales
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Participantes", len(participantes_finalizados))
        with col2:
            st.metric("📚 Grupos Finalizados", len(grupos_finalizados))
        with col3:
            diplomas_count = len(participantes_con_diploma)
            st.metric("🏅 Diplomas Subidos", diplomas_count)
        with col4:
            pendientes = len(participantes_finalizados) - diplomas_count
            st.metric("⏳ Pendientes", pendientes)

        # FILTROS DE BÚSQUEDA
        st.markdown("#### 🔍 Filtros de Búsqueda")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            buscar_participante = st.text_input(
                "🔍 Buscar participante",
                placeholder="Nombre, email o NIF...",
                key="buscar_diploma_participante"
            )
        
        with col2:
            grupos_opciones = ["Todos"] + [g["codigo_grupo"] for g in grupos_finalizados]
            grupo_filtro = st.selectbox(
                "Filtrar por grupo",
                grupos_opciones,
                key="filtro_grupo_diplomas"
            )
        
        with col3:
            estado_diploma = st.selectbox(
                "Estado diploma",
                ["Todos", "Con diploma", "Sin diploma"],
                key="filtro_estado_diploma"
            )

        # Aplicar filtros
        participantes_filtrados = participantes_finalizados.copy()
        
        # Filtro de búsqueda
        if buscar_participante:
            buscar_lower = buscar_participante.lower()
            participantes_filtrados = [
                p for p in participantes_filtrados 
                if (buscar_lower in p.get("nombre", "").lower() or 
                    buscar_lower in p.get("apellidos", "").lower() or 
                    buscar_lower in p.get("email", "").lower() or
                    buscar_lower in p.get("nif", "").lower())
            ]
        
        # Filtro por grupo
        if grupo_filtro != "Todos":
            grupo_id_filtro = None
            for g in grupos_finalizados:
                if g["codigo_grupo"] == grupo_filtro:
                    grupo_id_filtro = g["id"]
                    break
            if grupo_id_filtro:
                participantes_filtrados = [
                    p for p in participantes_filtrados 
                    if p["grupo_id"] == grupo_id_filtro
                ]
        
        # Filtro por estado de diploma
        if estado_diploma == "Con diploma":
            participantes_filtrados = [
                p for p in participantes_filtrados 
                if p["id"] in participantes_con_diploma
            ]
        elif estado_diploma == "Sin diploma":
            participantes_filtrados = [
                p for p in participantes_filtrados 
                if p["id"] not in participantes_con_diploma
            ]

        st.markdown(f"#### 🎯 Participantes encontrados: {len(participantes_filtrados)}")

        if not participantes_filtrados:
            st.warning("🔍 No se encontraron participantes con los filtros aplicados.")
            return

        # PAGINACIÓN
        items_por_pagina = 10
        total_paginas = (len(participantes_filtrados) + items_por_pagina - 1) // items_por_pagina
        
        if total_paginas > 1:
            pagina_actual = st.selectbox(
                "Página",
                range(1, total_paginas + 1),
                key="pagina_diplomas"
            )
            inicio = (pagina_actual - 1) * items_por_pagina
            fin = inicio + items_por_pagina
            participantes_pagina = participantes_filtrados[inicio:fin]
        else:
            participantes_pagina = participantes_filtrados

        # GESTIÓN INDIVIDUAL DE DIPLOMAS
        for i, participante in enumerate(participantes_pagina):
            grupo_info = grupos_dict_completo.get(participante["grupo_id"], {})
            tiene_diploma = participante["id"] in participantes_con_diploma
            
            # Crear expander con información del participante
            accion_nombre = grupo_info.get("accion_formativa", {}).get("nombre", "Sin acción") if grupo_info.get("accion_formativa") else "Sin acción"
            nombre_completo = f"{participante['nombre']} {participante.get('apellidos', '')}".strip()
            
            status_emoji = "✅" if tiene_diploma else "⏳"
            status_text = "Con diploma" if tiene_diploma else "Pendiente"
            
            with st.expander(
                f"{status_emoji} {nombre_completo} - {grupo_info.get('codigo_grupo', 'Sin código')} ({status_text})",
                expanded=False
            ):
                col_info, col_actions = st.columns([2, 1])
                
                with col_info:
                    st.markdown(f"**📧 Email:** {participante['email']}")
                    st.markdown(f"**🆔 NIF:** {participante.get('nif', 'No disponible')}")
                    st.markdown(f"**📚 Grupo:** {grupo_info.get('codigo_grupo', 'Sin código')}")
                    st.markdown(f"**📖 Acción:** {accion_nombre}")
                    
                    fecha_fin = grupo_info.get("fecha_fin") or grupo_info.get("fecha_fin_prevista")
                    if fecha_fin:
                        fecha_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')
                        st.markdown(f"**📅 Finalizado:** {fecha_str}")
                
                with col_actions:
                    if tiene_diploma:
                        # Mostrar diploma existente
                        diplomas_part = supabase.table("diplomas").select("*").eq(
                            "participante_id", participante["id"]
                        ).execute()
                        
                        if diplomas_part.data:
                            diploma = diplomas_part.data[0]
                            st.markdown("**🏅 Diploma:**")
                            if st.button("👁️ Ver", key=f"ver_diploma_{participante['id']}"):
                                st.markdown(f"[🔗 Abrir diploma]({diploma['url']})")
                            
                            if st.button("🗑️ Eliminar", key=f"delete_diploma_{participante['id']}"):
                                confirmar_key = f"confirm_delete_{participante['id']}"
                                if st.session_state.get(confirmar_key, False):
                                    supabase.table("diplomas").delete().eq("id", diploma["id"]).execute()
                                    st.success("✅ Diploma eliminado.")
                                    st.rerun()
                                else:
                                    st.session_state[confirmar_key] = True
                                    st.warning("⚠️ Confirmar eliminación")
                    else:
                        # Subir diploma
                        st.markdown("**📤 Subir Diploma**")
                        
                        st.info("📱 **Para móviles:** Asegúrate de que el archivo PDF esté guardado en tu dispositivo")
                        
                        diploma_file = st.file_uploader(
                            "Seleccionar diploma (PDF)",
                            type=["pdf"],
                            key=f"upload_diploma_{participante['id']}",
                            help="Solo archivos PDF, máximo 10MB"
                        )
                        
                        if diploma_file is not None:
                            file_size_mb = diploma_file.size / (1024 * 1024)
                            
                            col_info_file, col_size_file = st.columns(2)
                            with col_info_file:
                                st.success(f"✅ **Archivo:** {diploma_file.name}")
                            with col_size_file:
                                color = "🔴" if file_size_mb > 10 else "🟢"
                                st.write(f"{color} **Tamaño:** {file_size_mb:.2f} MB")
                            
                            if file_size_mb > 10:
                                st.error("❌ Archivo muy grande. Máximo 10MB.")
                            else:
                                if st.button(
                                    f"📤 Subir diploma de {participante['nombre']}", 
                                    key=f"btn_upload_{participante['id']}", 
                                    type="primary",
                                    use_container_width=True
                                ):
                                    subir_diploma_participante(supabase, participante, grupo_info, diploma_file)
                        else:
                            st.info("📂 Selecciona un archivo PDF para continuar")

        # Estadísticas finales
        if participantes_filtrados:
            st.markdown("#### 📊 Estadísticas")
            total_mostrados = len(participantes_filtrados)
            con_diploma_filtrados = sum(1 for p in participantes_filtrados if p["id"] in participantes_con_diploma)
            sin_diploma_filtrados = total_mostrados - con_diploma_filtrados
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("👥 Mostrados", total_mostrados)
            with col2:
                st.metric("✅ Con diploma", con_diploma_filtrados)
            with col3:
                st.metric("⏳ Sin diploma", sin_diploma_filtrados)
            
            if total_mostrados > 0:
                progreso = (con_diploma_filtrados / total_mostrados) * 100
                st.progress(con_diploma_filtrados / total_mostrados, f"Progreso: {progreso:.1f}%")
        
    except Exception as e:
        st.error(f"❌ Error al cargar gestión de diplomas: {e}")


def mostrar_gestion_diploma_individual(supabase, participante, tiene_diploma, diplomas_existentes, session_state):
    """Gestión de diploma para un participante individual."""
    
    participante_id = participante["id"]
    nombre_completo = f"{participante.get('nombre', '')} {participante.get('apellidos', '')}"
    
    col_info, col_accion = st.columns([2, 1])
    
    with col_info:
        st.write(f"**👤 Participante:** {nombre_completo}")
        st.write(f"**📄 Documento:** {participante.get('dni', participante.get('nif', 'Sin documento'))}")
        st.write(f"**🏢 Empresa:** {participante.get('empresa_nombre', 'Sin empresa')}")
        if "grupo_codigo" in participante:
            st.write(f"**👥 Grupo:** {participante.get('grupo_codigo', 'Sin grupo')}")
    
    with col_accion:
        if tiene_diploma and diplomas_existentes:
            # Mostrar diplomas existentes
            st.success(f"📜 {len(diplomas_existentes)} diploma(s)")
            
            for i, diploma in enumerate(diplomas_existentes):
                if isinstance(diploma, dict):
                    col_ver, col_del = st.columns(2)
                    
                    with col_ver:
                        # Botón para ver/descargar diploma
                        if diploma.get("url"):
                            st.link_button("👀 Ver", diploma["url"], use_container_width=True)
                        elif diploma.get("name"):
                            try:
                                public_url = supabase.storage.from_("diplomas").get_public_url(diploma["name"])
                                st.link_button("👀 Ver", public_url, use_container_width=True)
                            except:
                                st.button("❌ Error", disabled=True, use_container_width=True)
                    
                    with col_del:
                        if st.button("🗑️ Eliminar", key=f"del_diploma_{participante_id}_{i}", use_container_width=True):
                            if eliminar_diploma(supabase, diploma, participante_id):
                                st.success("✅ Diploma eliminado")
                                st.rerun()
        
        # Subida de nuevo diploma
        st.markdown("**📤 Subir Diploma**")
        
        diploma_file = st.file_uploader(
            "Seleccionar PDF",
            type=["pdf"],
            key=f"upload_diploma_{participante_id}",
            help="Solo archivos PDF, máximo 10MB"
        )
        
        if diploma_file:
            file_size_mb = diploma_file.size / (1024 * 1024)
            
            col_size, col_btn = st.columns([1, 1])
            with col_size:
                color = "🔴" if file_size_mb > 10 else "🟢"
                st.caption(f"{color} {file_size_mb:.2f} MB")
            
            with col_btn:
                if file_size_mb <= 10:
                    if st.button("📤 Subir", key=f"btn_upload_{participante_id}", type="primary", use_container_width=True):
                        if subir_diploma_participante(supabase, diploma_file, participante, session_state):
                            st.success("✅ Diploma subido")
                            st.rerun()
                else:
                    st.error("Archivo muy grande")

def subir_diploma_participante_optimizado(supabase, participante, grupo_info, diploma_file):
    """
    Función optimizada para subir diploma con estructura única e inequívoca.
    Basada en el análisis del esquema de base de datos.
    """
    try:
        with st.spinner("📤 Subiendo diploma..."):
            # Validar archivo
            try:
                file_bytes = diploma_file.getvalue()
                if len(file_bytes) == 0:
                    raise ValueError("El archivo está vacío")
            except Exception as e:
                st.error(f"❌ Error al leer el archivo: {e}")
                return
            
            # =====================================
            # OBTENER DATOS COMPLETOS DEL CONTEXTO
            # =====================================
            
            # 1. Datos del grupo (incluyendo año y empresa)
            grupo_id = participante["grupo_id"]
            grupo_res = supabase.table("grupos").select("""
                id, codigo_grupo, empresa_id, ano_inicio,
                accion_formativa_id,
                accion_formativa:acciones_formativas(
                    codigo_accion, ano_fundae, empresa_id, nombre
                )
            """).eq("id", grupo_id).execute()
            
            if not grupo_res.data:
                st.error("❌ No se pudo obtener información del grupo")
                return
                
            grupo_completo = grupo_res.data[0]
            accion_formativa = grupo_completo.get("accion_formativa", {})
            
            # 2. Determinar empresa responsable (gestora) usando jerarquía
            empresa_responsable = determinar_empresa_responsable_diploma(
                supabase, 
                grupo_completo["empresa_id"], 
                participante.get("empresa_id"),
                accion_formativa.get("empresa_id")
            )
            
            # 3. Generar timestamp único
            timestamp = int(datetime.now().timestamp())
            
            # =====================================
            # CONSTRUIR RUTA ÚNICA E INEQUÍVOCA
            # =====================================
            
            # Estructura propuesta: 
            # gestora_{id}/año_{año}/accion_{codigo}_{id}/grupo_{codigo}_{id}/participante_{nif}_{timestamp}.pdf
            
            # Limpiar datos para nombres de archivo seguros
            import re
            
            # Datos básicos
            gestora_id = empresa_responsable["id"]
            año = grupo_completo.get("ano_inicio") or accion_formativa.get("ano_fundae", datetime.now().year)
            
            # Acción formativa (código + ID para unicidad)
            accion_codigo = limpiar_para_archivo(accion_formativa.get("codigo_accion", "SIN_CODIGO"))
            accion_id = grupo_completo["accion_formativa_id"]
            
            # Grupo (código + ID para unicidad)
            grupo_codigo = limpiar_para_archivo(grupo_completo.get("codigo_grupo", "SIN_CODIGO"))
            grupo_id_corto = str(grupo_id)[:8]  # Primeros 8 caracteres del UUID
            
            # Participante
            participante_nif = limpiar_para_archivo(participante.get('nif', participante['id']))
            
            # RUTA FINAL ÚNICA
            filename = (
                f"gestora_{gestora_id}/"
                f"año_{año}/"
                f"accion_{accion_codigo}_{accion_id}/"
                f"grupo_{grupo_codigo}_{grupo_id_corto}/"
                f"diploma_{participante_nif}_{timestamp}.pdf"
            )
            
            # =====================================
            # SUBIR ARCHIVO CON METADATA COMPLETA
            # =====================================
            
            # Subir a bucket de Supabase con metadata
            upload_res = supabase.storage.from_("diplomas").upload(
                filename, 
                file_bytes, 
                file_options={
                    "content-type": "application/pdf",
                    "cache-control": "3600",
                    "upsert": "true",
                    "metadata": {
                        "participante_id": str(participante["id"]),
                        "grupo_id": str(grupo_id),
                        "empresa_responsable": empresa_responsable["nombre"],
                        "accion_nombre": accion_formativa.get("nombre", ""),
                        "año_formacion": str(año),
                        "fecha_subida": datetime.now().isoformat()
                    }
                }
            )
            
            # Verificar subida exitosa
            if hasattr(upload_res, 'error') and upload_res.error:
                raise Exception(f"Error de subida: {upload_res.error}")
            
            # Obtener URL pública
            public_url = supabase.storage.from_("diplomas").get_public_url(filename)
            if not public_url:
                raise Exception("No se pudo generar URL pública")
            
            # =====================================
            # GUARDAR REFERENCIA EN BASE DE DATOS
            # =====================================
            
            diploma_data = {
                "participante_id": participante["id"],
                "grupo_id": grupo_id,
                "url": public_url,
                "archivo_nombre": diploma_file.name,
                "fecha_subida": datetime.now().isoformat(),
                # Campos adicionales para trazabilidad
                "ruta_archivo": filename,
                "empresa_responsable_id": gestora_id,
                "accion_formativa_id": grupo_completo["accion_formativa_id"],
                "año_formacion": año
            }
            
            diploma_insert = supabase.table("diplomas").insert(diploma_data).execute()
            
            if hasattr(diploma_insert, 'error') and diploma_insert.error:
                # Si falla la BD, eliminar archivo subido
                try:
                    supabase.storage.from_("diplomas").remove([filename])
                except:
                    pass
                raise Exception(f"Error de base de datos: {diploma_insert.error}")
            
            # =====================================
            # CONFIRMACIÓN Y LOGGING
            # =====================================
            
            st.success("✅ Diploma subido correctamente!")
            
            # Información detallada para el usuario
            with st.expander("📋 Detalles de la subida", expanded=False):
                st.write(f"**📁 Ruta:** `{filename}`")
                st.write(f"**🏢 Empresa responsable:** {empresa_responsable['nombre']}")
                st.write(f"**📅 Año formación:** {año}")
                st.write(f"**📚 Acción:** {accion_formativa.get('nombre', 'Sin nombre')}")
                st.write(f"**👥 Grupo:** {grupo_completo.get('codigo_grupo', 'Sin código')}")
            
            st.markdown(f"🔗 [Ver diploma subido]({public_url})")
            st.rerun()
                
    except Exception as e:
        st.error(f"❌ Error general: {e}")
        # Log detallado para debugging
        st.error(f"Contexto: Participante {participante.get('nombre', 'desconocido')}, "
                f"Grupo {participante.get('grupo_id', 'sin grupo')}")

def eliminar_diploma(supabase, diploma, participante_id):
    """Elimina diploma de participante."""
    try:
        # Eliminar del storage
        if diploma.get("filename"):
            supabase.storage.from_("diplomas").remove([diploma["filename"]])
        elif diploma.get("name"):
            supabase.storage.from_("diplomas").remove([diploma["name"]])
        
        # Eliminar de tabla diplomas si existe
        try:
            if diploma.get("id"):
                supabase.table("diplomas").delete().eq("id", diploma["id"]).execute()
        except:
            pass
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error eliminando diploma: {e}")
        return False
        
 def determinar_empresa_responsable_diploma(supabase, grupo_empresa_id, participante_empresa_id, accion_empresa_id):
    """
    Determina qué empresa es responsable ante FUNDAE para el diploma.
    Sigue la lógica de jerarquía empresarial.
    """
    try:
        # Prioridad: empresa de la acción formativa > empresa del grupo > empresa del participante
        empresa_id_candidata = accion_empresa_id or grupo_empresa_id or participante_empresa_id
        
        if not empresa_id_candidata:
            raise ValueError("No se pudo determinar empresa responsable")
        
        # Obtener datos de la empresa candidata
        empresa_res = supabase.table("empresas").select("""
            id, nombre, cif, tipo_empresa, empresa_matriz_id
        """).eq("id", empresa_id_candidata).execute()
        
        if not empresa_res.data:
            raise ValueError("Empresa candidata no encontrada")
        
        empresa = empresa_res.data[0]
        
        # Si es CLIENTE_GESTOR, la responsable es su gestora matriz
        if empresa["tipo_empresa"] == "CLIENTE_GESTOR" and empresa["empresa_matriz_id"]:
            gestora_res = supabase.table("empresas").select("*").eq(
                "id", empresa["empresa_matriz_id"]
            ).execute()
            
            if gestora_res.data:
                return gestora_res.data[0]
        
        # En otros casos, la empresa candidata es la responsable
        return empresa
        
    except Exception as e:
        # Fallback: buscar primera empresa GESTORA del sistema
        gestora_res = supabase.table("empresas").select("*").eq(
            "tipo_empresa", "GESTORA"
        ).limit(1).execute()
        
        if gestora_res.data:
            return gestora_res.data[0]
        
        raise ValueError(f"No se pudo determinar empresa responsable: {e}")
        
def formatear_estado_participante(fila: dict) -> str:
    """Devuelve el estado de formación de un participante según fechas."""
    if not fila.get("grupo_fecha_inicio"):
        return "Sin grupo asignado"
    hoy = date.today()
    if fila.get("grupo_fecha_inicio") > hoy:
        return "Pendiente de inicio"
    if fila.get("grupo_fecha_fin_prevista") and fila.get("grupo_fecha_fin_prevista") < hoy:
        return "Curso finalizado"
    return "En curso"

def validar_niss(niss: str) -> bool:
    """Valida un número de NISS básico (solo dígitos y longitud >= 10)."""
    return bool(niss and niss.isdigit() and len(niss) >= 10)
