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
    Gestión completa de diplomas por participante con Streamlit 1.49.
    Integrada con la nueva arquitectura de servicios.
    """
    st.divider()
    st.markdown("### 🎓 Gestión de Diplomas por Participante")
    st.caption("Subir, gestionar y descargar diplomas organizados por estructura empresarial")

    # Verificar permisos
    puede_gestionar = session_state.role in ["admin", "gestor"]
    if not puede_gestionar:
        st.warning("🔒 No tienes permisos para gestionar diplomas")
        return

    try:
        # Cargar participantes según rol
        df_participantes = participantes_service.get_participantes_completos()
        
        if session_state.role == "gestor":
            empresa_id = session_state.user.get("empresa_id")
            df_participantes = df_participantes[df_participantes["empresa_id"] == empresa_id]

        if df_participantes.empty:
            st.info("📋 No hay participantes para gestionar diplomas")
            return

        # Verificar conexión con Supabase Storage
        try:
            # Test de conexión al bucket 'diplomas'
            bucket_list = supabase.storage.from_("diplomas").list("", {"limit": 1})
            conexion_storage = True
        except Exception as e:
            st.error(f"❌ Error conectando con Supabase Storage: {e}")
            st.info("💡 Verifica que el bucket 'diplomas' existe y tiene permisos configurados")
            return

        # Obtener información de diplomas existentes
        participantes_con_diploma = set()
        diplomas_info = {}
        
        for _, participante in df_participantes.iterrows():
            participante_id = participante.get("id")
            if participante_id:
                try:
                    # Buscar diplomas en tabla de diplomas si existe
                    diplomas_res = supabase.table("diplomas").select("*").eq("participante_id", participante_id).execute()
                    
                    if diplomas_res.data:
                        participantes_con_diploma.add(participante_id)
                        diplomas_info[participante_id] = diplomas_res.data
                except:
                    # Si no existe tabla de diplomas, buscar directamente en storage
                    try:
                        empresa_id_part = participante.get("empresa_id", "sin_empresa")
                        files = supabase.storage.from_("diplomas").list(f"empresa_{empresa_id_part}/")
                        
                        participante_files = []
                        for file_info in files or []:
                            if isinstance(file_info, dict) and str(participante_id) in file_info.get("name", ""):
                                participante_files.append(file_info)
                        
                        if participante_files:
                            participantes_con_diploma.add(participante_id)
                            diplomas_info[participante_id] = participante_files
                    except:
                        continue

        # Filtros para gestión
        st.markdown("#### 🔍 Filtros de Gestión")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filtro_diploma = st.selectbox(
                "📊 Estado Diploma",
                ["Todos", "Con Diploma", "Sin Diploma"],
                key="filtro_diploma_gestion"
            )
        
        with col2:
            # Filtro por grupo si hay información de grupos
            grupos_disponibles = df_participantes["grupo_codigo"].dropna().unique() if "grupo_codigo" in df_participantes.columns else []
            if len(grupos_disponibles) > 0:
                filtro_grupo = st.selectbox(
                    "👥 Filtrar por Grupo", 
                    ["Todos"] + sorted(grupos_disponibles),
                    key="filtro_grupo_diploma"
                )
            else:
                filtro_grupo = "Todos"
                st.selectbox("👥 Filtrar por Grupo", ["No hay grupos"], disabled=True)
        
        with col3:
            # Filtro por empresa (solo admin)
            if session_state.role == "admin":
                empresas_disponibles = sorted(df_participantes["empresa_nombre"].dropna().unique())
                filtro_empresa = st.selectbox(
                    "🏢 Filtrar por Empresa",
                    ["Todas"] + empresas_disponibles,
                    key="filtro_empresa_diploma"
                )
            else:
                filtro_empresa = "Todas"

        # Aplicar filtros
        df_filtrado = df_participantes.copy()
        
        if filtro_diploma == "Con Diploma":
            df_filtrado = df_filtrado[df_filtrado["id"].isin(participantes_con_diploma)]
        elif filtro_diploma == "Sin Diploma":
            df_filtrado = df_filtrado[~df_filtrado["id"].isin(participantes_con_diploma)]
        
        if filtro_grupo != "Todos" and "grupo_codigo" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["grupo_codigo"] == filtro_grupo]
        
        if filtro_empresa != "Todas":
            df_filtrado = df_filtrado[df_filtrado["empresa_nombre"] == filtro_empresa]

        # Estadísticas de diplomas
        total_participantes = len(df_filtrado)
        con_diploma = len([p for p in df_filtrado["id"] if p in participantes_con_diploma])
        sin_diploma = total_participantes - con_diploma
        
        # Métricas con diseño moderno
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Total Filtrados", total_participantes)
        with col2:
            st.metric("✅ Con Diploma", con_diploma)
        with col3:
            st.metric("⏳ Sin Diploma", sin_diploma)
        with col4:
            progreso = (con_diploma / total_participantes * 100) if total_participantes > 0 else 0
            st.metric("📊 Progreso", f"{progreso:.1f}%")

        # Barra de progreso
        if total_participantes > 0:
            st.progress(con_diploma / total_participantes, f"Progreso general: {progreso:.1f}%")

        # Gestión individual de diplomas
        if not df_filtrado.empty:
            st.markdown("#### 📋 Participantes para Gestión de Diplomas")
            
            for _, participante in df_filtrado.iterrows():
                participante_id = participante["id"]
                nombre_completo = f"{participante.get('nombre', '')} {participante.get('apellidos', '')}"
                nif = participante.get("dni", participante.get("nif", "Sin documento"))
                empresa = participante.get("empresa_nombre", "Sin empresa")
                grupo = participante.get("grupo_codigo", "Sin grupo") if "grupo_codigo" in participante else "Sin grupo"
                
                # Estado del diploma
                tiene_diploma = participante_id in participantes_con_diploma
                estado_icon = "✅" if tiene_diploma else "⏳"
                
                with st.expander(f"{estado_icon} {nombre_completo} - {nif} ({empresa})", expanded=False):
                    mostrar_gestion_diploma_individual(
                        supabase, participante, tiene_diploma, 
                        diplomas_info.get(participante_id, []), session_state
                    )

    except Exception as e:
        st.error(f"❌ Error en gestión de diplomas: {e}")

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

def subir_diploma_participante(supabase, diploma_file, participante, session_state):
    """Sube diploma de participante con estructura organizacional."""
    try:
        with st.spinner("📤 Subiendo diploma..."):
            # Validar archivo
            file_bytes = diploma_file.getvalue()
            if len(file_bytes) == 0:
                st.error("❌ El archivo está vacío")
                return False
            
            # Generar estructura de carpetas organizadas
            timestamp = int(datetime.now().timestamp())
            empresa_id = participante.get("empresa_id", "sin_empresa")
            participante_doc = participante.get("dni", participante.get("nif", participante["id"]))
            
            # Limpiar nombre para archivo seguro
            participante_doc_limpio = "".join(c for c in str(participante_doc) if c.isalnum() or c in "_-")
            
            # Estructura: empresa_{id}/diplomas/participante_{doc}_{timestamp}.pdf
            filename = f"empresa_{empresa_id}/diplomas/diploma_{participante_doc_limpio}_{timestamp}.pdf"
            
            # Subir a Supabase Storage
            upload_result = supabase.storage.from_("diplomas").upload(filename, file_bytes)
            
            if hasattr(upload_result, 'error') and upload_result.error:
                st.error(f"❌ Error al subir: {upload_result.error}")
                return False
            
            # Obtener URL pública
            public_url = supabase.storage.from_("diplomas").get_public_url(filename)
            
            # Guardar referencia en tabla diplomas (si existe)
            try:
                supabase.table("diplomas").insert({
                    "participante_id": participante["id"],
                    "grupo_id": participante.get("grupo_id"),
                    "url": public_url,
                    "filename": filename,
                    "archivo_nombre": diploma_file.name,
                    "fecha_subida": datetime.now().isoformat(),
                    "subido_por": session_state.user.get("email", "sistema")
                }).execute()
            except Exception as e:
                # Si no existe tabla diplomas, continuar sin error
                st.info(f"💡 Diploma subido. Referencia no guardada en BD: {e}")
            
            st.success(f"✅ Diploma subido correctamente para {participante.get('nombre', 'participante')}")
            return True
            
    except Exception as e:
        st.error(f"❌ Error subiendo diploma: {e}")
        return False

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
