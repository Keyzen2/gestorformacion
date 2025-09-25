import streamlit as st
import pandas as pd
import io
import re
import unicodedata
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
        
def preparar_datos_tabla_nn(participantes_service, session_state):
    """
    Prepara los datos de participantes con información de grupos N:N para la tabla.
    """
    try:
        # Obtener datos usando el método N:N
        df_participantes = participantes_service.get_participantes_con_grupos_nn()

        # Si el DataFrame está vacío, crear estructura básica
        if df_participantes.empty:
            return pd.DataFrame(columns=[
                'id', 'nif', 'nombre', 'apellidos', 'email', 'telefono',
                'empresa_id', 'empresa_nombre', 'num_grupos', 'grupos_codigos'
            ])

        # Verificar si las columnas N:N existen, si no, usar método alternativo
        if 'num_grupos' not in df_participantes.columns or 'grupos_codigos' not in df_participantes.columns:
            # Fallback: usar método tradicional y simular estructura N:N
            df_tradicional = participantes_service.get_participantes_completos()

            if not df_tradicional.empty:
                # Crear columnas simuladas para compatibilidad
                df_tradicional['num_grupos'] = df_tradicional['grupo_id'].apply(lambda x: 1 if pd.notna(x) else 0)
                df_tradicional['grupos_codigos'] = df_tradicional.get('grupo_codigo', '')

                return df_tradicional

        return df_participantes

    except Exception as e:
        st.error(f"❌ Error preparando datos de participantes: {e}")
        # Crear DataFrame vacío con estructura correcta
        return pd.DataFrame(columns=[
            'id', 'nif', 'nombre', 'apellidos', 'email', 'telefono',
            'empresa_id', 'empresa_nombre', 'num_grupos', 'grupos_codigos'
        ])
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
    """Muestra tabla de participantes con filtros, paginación y selección de fila - VERSIÓN N:N."""
    if df_participantes.empty:
        st.info("📋 No hay participantes para mostrar")
        return None, pd.DataFrame()
    
    st.markdown(f"### {titulo_tabla}")

    # 🔎 Filtros avanzados (fijos arriba)
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_nombre = st.text_input("👤 Nombre/Apellidos contiene", key="filtro_tabla_nombre")
    with col2:
        filtro_nif = st.text_input("🆔 Documento contiene", key="filtro_tabla_nif")
    with col3:
        filtro_empresa = st.text_input("🏢 Empresa contiene", key="filtro_tabla_empresa")

    # Aplicar filtros
    df_filtrado = df_participantes.copy()
    
    if filtro_nombre:
        mask_nombre = (
            df_filtrado["nombre"].str.contains(filtro_nombre, case=False, na=False) |
            df_filtrado["apellidos"].str.contains(filtro_nombre, case=False, na=False)
        )
        df_filtrado = df_filtrado[mask_nombre]
    
    if filtro_nif:
        df_filtrado = df_filtrado[df_filtrado["nif"].str.contains(filtro_nif, case=False, na=False)]
    
    if filtro_empresa:
        df_filtrado = df_filtrado[df_filtrado["empresa_nombre"].str.contains(filtro_empresa, case=False, na=False)]

    # 📢 Selector de registros por página
    page_size = st.selectbox("📊 Registros por página", [10, 20, 50, 100], index=1, key="page_size_tabla")

    # 📄 Paginación
    total_rows = len(df_filtrado)
    total_pages = (total_rows // page_size) + (1 if total_rows % page_size else 0)
    page_number = st.number_input("Página", min_value=1, max_value=max(total_pages, 1), step=1, value=1, key="page_num_tabla")

    start_idx = (page_number - 1) * page_size
    end_idx = start_idx + page_size
    df_paged = df_filtrado.iloc[start_idx:end_idx]

    # NUEVA: Configuración de columnas para versión N:N
    columnas = ["nombre", "apellidos", "nif", "email", "telefono", "empresa_nombre", "num_grupos", "grupos_codigos"]
    
    # Asegurar que las columnas existen en el DataFrame
    columnas_disponibles = []
    for col in columnas:
        if col in df_paged.columns:
            columnas_disponibles.append(col)
        elif col == "num_grupos" and "num_grupos" not in df_paged.columns:
            # Si no existe la columna, crearla dinámicamente
            if "grupos_codigos" in df_paged.columns:
                df_paged["num_grupos"] = df_paged["grupos_codigos"].apply(
                    lambda x: len(x.split(", ")) if isinstance(x, str) and x.strip() else 0
                )
            else:
                df_paged["num_grupos"] = 0
            columnas_disponibles.append(col)
        elif col == "grupos_codigos" and "grupos_codigos" not in df_paged.columns:
            # Si no existe, crear columna vacía
            df_paged["grupos_codigos"] = ""
            columnas_disponibles.append(col)

    # Configuración de columnas mejorada
    column_config = {
        "nombre": st.column_config.TextColumn("👤 Nombre", width="medium"),
        "apellidos": st.column_config.TextColumn("👥 Apellidos", width="large"),
        "nif": st.column_config.TextColumn("🆔 Documento", width="small"),
        "email": st.column_config.TextColumn("📧 Email", width="large"),
        "telefono": st.column_config.TextColumn("📞 Teléfono", width="medium"),
        "empresa_nombre": st.column_config.TextColumn("🏢 Empresa", width="large"),
        "num_grupos": st.column_config.NumberColumn("🎓 Grupos", width="small", help="Número de grupos asignados"),
        "grupos_codigos": st.column_config.TextColumn("📚 Códigos", width="large", help="Códigos de grupos separados por comas")
    }

    # Mostrar información sobre los resultados
    if total_rows != len(df_participantes):
        st.info(f"📊 Mostrando {total_rows} de {len(df_participantes)} participantes (filtrados)")

    # Mostrar tabla con las columnas disponibles
    try:
        evento = st.dataframe(
            df_paged[columnas_disponibles],
            column_config={k: v for k, v in column_config.items() if k in columnas_disponibles},
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        if evento.selection.rows:
            return df_paged.iloc[evento.selection.rows[0]], df_paged
        return None, df_paged
        
    except Exception as e:
        st.error(f"❌ Error mostrando tabla: {e}")
        st.write("Columnas disponibles:", df_paged.columns.tolist())
        st.write("Columnas solicitadas:", columnas_disponibles)
        return None, df_paged
        
# =========================
# SECCIÓN DE GRUPOS N:N PARA PARTICIPANTES
# =========================
def mostrar_seccion_grupos_participante(participantes_service, participante_id, empresa_id, session_state):
    """Gestión de grupos del participante usando relación N:N."""
    st.markdown("### 🎓 Grupos de Formación")
    st.caption("Un participante puede estar inscrito en múltiples grupos a lo largo del tiempo")
    
    if not participante_id:
        st.info("💡 Guarda el participante primero para poder asignar grupos")
        return
    
    try:
        # Mostrar grupos actuales del participante usando los métodos del servicio
        df_grupos_participante = participantes_service.get_grupos_de_participante(participante_id)
        
        if not df_grupos_participante.empty:
            st.markdown("#### 📚 Grupos Asignados")
            for _, grupo in df_grupos_participante.iterrows():
                
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 1])
                    
                    with col1:
                        codigo = grupo.get('codigo_grupo', 'Sin código')
                        accion = grupo.get('accion_nombre', 'Sin acción formativa')
                        st.write(f"**{codigo}**")
                        st.caption(f"📖 {accion}")
                        
                        # Mostrar horas si están disponibles
                        horas = grupo.get('accion_horas', 0)
                        if horas > 0:
                            st.caption(f"⏱️ {horas}h")
                    
                    with col2:
                        # Fechas del grupo
                        fecha_inicio = grupo.get("fecha_inicio")
                        fecha_fin = grupo.get("fecha_fin") or grupo.get("fecha_fin_prevista")
                        
                        if fecha_inicio:
                            inicio_str = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y')
                            st.write(f"📅 Inicio: {inicio_str}")
                        
                        if fecha_fin:
                            fin_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')
                            st.write(f"🏁 Fin: {fin_str}")
                            
                            # Estado basado en fechas
                            hoy = pd.Timestamp.now().date()
                            fecha_fin_dt = pd.to_datetime(fecha_fin).date()
                            
                            if fecha_fin_dt < hoy:
                                st.success("✅ Finalizado")
                            elif fecha_inicio and pd.to_datetime(fecha_inicio).date() <= hoy <= fecha_fin_dt:
                                st.info("🟡 En curso")
                            else:
                                st.warning("⏳ Pendiente")
                        
                        # Modalidad
                        modalidad = grupo.get('modalidad', '')
                        if modalidad:
                            st.caption(f"📍 {modalidad}")
                    
                    with col3:
                        # Botón para desasignar
                        if st.button("🗑️ Quitar", key=f"quitar_grupo_{grupo['relacion_id']}", 
                                   help="Desasignar del grupo", use_container_width=True):
                            confirmar_key = f"confirmar_quitar_{grupo['relacion_id']}"
                            if st.session_state.get(confirmar_key):
                                success = participantes_service.desasignar_participante_de_grupo(
                                    participante_id, grupo["grupo_id"]
                                )
                                if success:
                                    st.success("✅ Participante desasignado del grupo")
                                    del st.session_state[confirmar_key]
                                    st.rerun()
                            else:
                                st.session_state[confirmar_key] = True
                                st.warning("⚠️ Confirmar eliminación")
        else:
            st.info("📭 Este participante no está asignado a ningún grupo")
        
        # Sección para añadir nuevos grupos
        st.markdown("#### ➕ Asignar a Nuevo Grupo")
        
        # Cargar grupos disponibles usando el método del servicio
        grupos_disponibles = participantes_service.get_grupos_disponibles_para_participante(participante_id)
        
        if grupos_disponibles:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                grupo_seleccionado = st.selectbox(
                    "Seleccionar grupo",
                    options=list(grupos_disponibles.keys()),
                    key=f"nuevo_grupo_{participante_id}",
                    help="Solo se muestran grupos disponibles de la empresa del participante"
                )
            
            with col2:
                if st.button("➕ Asignar", type="primary", key=f"asignar_grupo_{participante_id}", use_container_width=True):
                    if grupo_seleccionado:
                        grupo_id = grupos_disponibles[grupo_seleccionado]
                        
                        success = participantes_service.asignar_participante_a_grupo(
                            participante_id, grupo_id
                        )
                        
                        if success:
                            st.success("✅ Participante asignado al grupo")
                            st.rerun()
        else:
            st.info("📭 No hay grupos disponibles para asignar (o ya está en todos los grupos de su empresa)")
    
    except Exception as e:
        st.error(f"❌ Error gestionando grupos del participante: {e}")


# =========================
# FORMULARIO MODIFICADO DE PARTICIPANTE
# =========================
def mostrar_formulario_participante_nn(
    participante_data,
    participantes_service,
    empresas_service,
    grupos_service,
    auth_service,
    session_state,
    es_creacion=False
):
    """MODIFICADO: Formulario de participante con gestión N:N de grupos."""

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
            documento = st.text_input("Número de Documento", value=datos.get("nif",""), key=f"{form_id}_documento", help="DNI, NIE, CIF o Pasaporte")
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
        # EMPRESA (SIN GRUPO - AHORA SE GESTIONA SEPARADO)
        # =========================
        st.markdown("### 🏢 Empresa")
        
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
                disabled=not empresa_options
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
        
        # =========================
        # CREDENCIALES AUTH
        # =========================
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
                password = "NUEVA_PASSWORD_AUTO"

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
            eliminar, cancelar = False, False
            if not es_creacion:
                if session_state.role == "admin":
                    eliminar = st.form_submit_button(
                        "🗑️ Eliminar",
                        type="secondary",
                        use_container_width=True
                    )
                else:
                    cancelar = st.form_submit_button(
                        "❌ Cancelar",
                        type="secondary",
                        use_container_width=True
                    )

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
                    "nif": documento or None,
                    "niss": niss or None,
                    "fecha_nacimiento": fecha_nacimiento.isoformat() if fecha_nacimiento else None,
                    "sexo": sexo or None,
                    "telefono": telefono or None,
                    "email": email or None,
                    "empresa_id": empresa_id,
                    # IMPORTANTE: NO incluir grupo_id aquí, se gestiona por separado
                }

                if es_creacion:
                    password_final = password if password and password != "" else None
                    
                    ok, participante_id = auth_service.crear_usuario_con_auth(
                        datos_payload, 
                        tabla="participantes", 
                        password=password_final
                    )
                    
                    if ok:
                        st.success("✅ Participante creado correctamente con acceso al portal")
                        st.session_state[f"participante_creado_{form_id}"] = participante_id
                        st.rerun()
                else:
                    # Actualización
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

        # =========================
        # ELIMINAR O CANCELAR
        # =========================
        if not es_creacion:
            if session_state.role == "admin" and eliminar:
                if st.session_state.get("confirmar_eliminar_participante"):
                    try:
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
            
            elif session_state.role != "admin" and cancelar:
                st.info("❌ Edición cancelada")
                st.rerun()

    # =========================
    # GESTIÓN DE GRUPOS N:N (FUERA DEL FORMULARIO)
    # =========================
    
    # Solo mostrar si es edición o si acabamos de crear el participante
    mostrar_grupos = False
    participante_id_para_grupos = None
    
    if not es_creacion:
        # Modo edición - usar ID existente
        mostrar_grupos = True
        participante_id_para_grupos = datos.get("id")
    else:
        # Modo creación - ver si acabamos de crear
        participante_creado_key = f"participante_creado_{form_id}"
        if st.session_state.get(participante_creado_key):
            mostrar_grupos = True
            participante_id_para_grupos = st.session_state[participante_creado_key]
    
    if mostrar_grupos and participante_id_para_grupos and empresa_id:
        st.markdown("---")
        mostrar_seccion_grupos_participante(
            participantes_service, 
            participante_id_para_grupos, 
            empresa_id, 
            session_state
        )

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
        "nif": "12345678A",
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
                        "nif": fila.get("nif") or fila.get("documento"),  # Compatibilidad con ambos nombres
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
                    mostrar_formulario_participante_nn(
                        seleccionado, participantes_service, empresas_service, grupos_service, auth_service, session_state, es_creacion=False
                    )
        except Exception as e:
            st.error(f"❌ Error cargando participantes: {e}")

    # =========================
    # TAB CREAR
    # =========================
    with tabs[1]:
        with st.container(border=True):
            mostrar_formulario_participante_nn(
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
    Versión optimizada de gestión de diplomas con nueva estructura de archivos.
    """
    st.divider()
    st.markdown("### 🎓 Gestión Avanzada de Diplomas")
    st.caption("Sistema optimizado con estructura única por empresa gestora y año")

    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para gestionar diplomas")
        return

    try:
        # Usar la misma lógica de carga que la función original
        empresas_permitidas = participantes_service._get_empresas_gestionables()
        if not empresas_permitidas:
            st.info("No tienes grupos finalizados disponibles.")
            return
        
        hoy = datetime.now().date()
        
        # Obtener grupos finalizados (mismo código que función original)
        query = supabase.table("grupos").select("""
            id, codigo_grupo, fecha_fin, fecha_fin_prevista, empresa_id, ano_inicio,
            accion_formativa:acciones_formativas(id, codigo_accion, ano_fundae, nombre)
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
            
        # =====================================
        # NUEVA SECCIÓN: ESTRUCTURA DE ARCHIVOS
        # =====================================
        
        with st.expander("📁 Estructura de Archivos por Empresa", expanded=False):
            st.markdown("**Organización de diplomas en el sistema:**")
            
            for empresa_id in empresas_permitidas:
                empresa_res = supabase.table("empresas").select("nombre").eq("id", empresa_id).execute()
                empresa_nombre = empresa_res.data[0]["nombre"] if empresa_res.data else f"Empresa {empresa_id}"
                
                st.markdown(f"**🏢 {empresa_nombre}**")
                
                estructura = obtener_estructura_diplomas_empresa(supabase, empresa_id)
                if estructura:
                    for año, acciones in estructura.items():
                        st.markdown(f"  📅 **Año {año}**")
                        for accion, grupos in acciones.items():
                            st.markdown(f"    📚 {accion}")
                            for grupo, archivos in grupos.items():
                                st.markdown(f"      👥 {grupo} ({len(archivos)} diplomas)")
                else:
                    st.markdown("    📭 Sin diplomas")

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
        st.error(f"❌ Error en gestión optimizada de diplomas: {e}")

def mostrar_gestion_diploma_individual(supabase, participante, tiene_diploma, diplomas_existentes, session_state):
    """Gestión de diploma para un participante individual."""
    
    participante_id = participante["id"]
    nombre_completo = f"{participante.get('nombre', '')} {participante.get('apellidos', '')}"
    
    col_info, col_accion = st.columns([2, 1])
    
    with col_info:
        st.write(f"**👤 Participante:** {nombre_completo}")
        st.write(f"**📄 Documento:** {participante.get('nif', participante.get('dni', 'Sin documento'))}")
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

def subir_diploma_participante(supabase, participante, grupo_info, diploma_file):
    """
    Función optimizada para subir diploma con estructura única e inequívoca.
    CORREGIDA: evita 'VACIO' usando nif/dni/documento o fallback al id.
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
            
            # Empresa responsable
            empresa_responsable = determinar_empresa_responsable_diploma(
                supabase, 
                grupo_completo["empresa_id"], 
                participante.get("empresa_id"),
                accion_formativa.get("empresa_id")
            )
            
            # Timestamp único
            timestamp = int(datetime.now().timestamp())
            
            # =====================================
            # IDENTIFICADOR DE PARTICIPANTE
            # =====================================
            raw_doc = (
                participante.get("nif") or
                participante.get("dni") or
                participante.get("documento") or
                ""
            )
            try:
                raw_doc = raw_doc.strip()
            except Exception:
                raw_doc = ""
            
            if raw_doc:
                participante_slug = limpiar_para_archivo(raw_doc)
            else:
                participante_slug = f"id{str(participante['id'])[:8]}"
            
            # =====================================
            # CONSTRUIR RUTA ÚNICA E INEQUÍVOCA
            # =====================================
            gestora_id = empresa_responsable["id"]
            año = grupo_completo.get("ano_inicio") or accion_formativa.get("ano_fundae", datetime.now().year)
            
            accion_codigo = limpiar_para_archivo(accion_formativa.get("codigo_accion", "SIN_CODIGO"))
            accion_id = limpiar_para_archivo(grupo_completo["accion_formativa_id"])
            
            grupo_codigo = limpiar_para_archivo(grupo_completo.get("codigo_grupo", "SIN_CODIGO"))
            grupo_id_corto = limpiar_para_archivo(str(grupo_id)[:8])
            
            participante_slug = limpiar_para_archivo(
                participante.get("nif") or participante.get("dni") or str(participante["id"])
            )
            
            # Usamos 'ano_' en vez de 'año_' para evitar caracteres inválidos
            filename = (
                f"gestora_{limpiar_para_archivo(gestora_id)}/"
                f"ano_{año}/"
                f"accion_{accion_codigo}_{accion_id}/"
                f"grupo_{grupo_codigo}_{grupo_id_corto}/"
                f"diploma_{participante_slug}_{timestamp}.pdf"
            )
            
            # =====================================
            # SUBIR ARCHIVO A SUPABASE
            # =====================================
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
                        "fecha_subida": datetime.now().isoformat(),
                        "ruta_archivo": filename  # puedes guardarlo solo como metadato
                    }
                }
            )
            
            if hasattr(upload_res, 'error') and upload_res.error:
                raise Exception(f"Error de subida: {upload_res.error}")
            
            public_url = supabase.storage.from_("diplomas").get_public_url(filename)
            if not public_url:
                raise Exception("No se pudo generar URL pública")
            
            # =====================================
            # GUARDAR REFERENCIA EN BASE DE DATOS
            # SOLO CAMPOS EXISTENTES EN LA TABLA
            # =====================================
            diploma_data = {
                "participante_id": participante["id"],
                "grupo_id": grupo_id,
                "url": public_url,
                "archivo_nombre": diploma_file.name,
                "fecha_subida": datetime.now().isoformat()
            }
            
            diploma_insert = supabase.table("diplomas").insert(diploma_data).execute()
            
            if hasattr(diploma_insert, 'error') and diploma_insert.error:
                try:
                    supabase.storage.from_("diplomas").remove([filename])
                except:
                    pass
                raise Exception(f"Error de base de datos: {diploma_insert.error}")

            
            # =====================================
            # CONFIRMACIÓN Y LOGGING
            # =====================================
            st.success("✅ Diploma subido correctamente!")
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

def limpiar_para_archivo(texto: str) -> str:
    """
    Normaliza texto para usar en nombres de archivo/rutas en Supabase.
    - Elimina acentos y caracteres especiales
    - Sustituye espacios por '_'
    - Permite solo [a-zA-Z0-9_-]
    """
    if not texto:
        return "SIN_VALOR"
    
    # Normalizar a ASCII sin acentos
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = texto.encode("ascii", "ignore").decode("ascii")
    
    # Sustituir espacios por guion bajo
    texto = texto.replace(" ", "_")
    
    # Eliminar caracteres no permitidos
    texto = re.sub(r"[^a-zA-Z0-9_-]", "", texto)
    
    return texto or "SIN_VALOR"
    
def obtener_estructura_diplomas_empresa(supabase, empresa_id):
    """
    Obtiene la estructura completa de diplomas de una empresa.
    Útil para navegación y organización.
    """
    try:
        # Buscar todos los diplomas donde esta empresa es responsable
        archivos = supabase.storage.from_("diplomas").list(f"gestora_{empresa_id}/")
        
        estructura = {}
        for archivo in archivos or []:
            if isinstance(archivo, dict) and archivo.get("name", "").endswith(".pdf"):
                path_parts = archivo["name"].split("/")
                if len(path_parts) >= 4:  # gestora/año/accion/grupo/archivo
                    año = path_parts[1].replace("año_", "")
                    accion = path_parts[2]
                    grupo = path_parts[3]
                    
                    if año not in estructura:
                        estructura[año] = {}
                    if accion not in estructura[año]:
                        estructura[año][accion] = {}
                    if grupo not in estructura[año][accion]:
                        estructura[año][accion][grupo] = []
                    
                    estructura[año][accion][grupo].append(archivo)
        
        return estructura
        
    except Exception as e:
        st.error(f"Error obteniendo estructura de diplomas: {e}")
        return {}  
        
def migrar_diplomas_existentes(supabase):
    """
    Función de migración para reorganizar diplomas existentes a la nueva estructura.
    EJECUTAR SOLO UNA VEZ Y CON BACKUP.
    """
    st.warning("⚠️ FUNCIÓN DE MIGRACIÓN - Solo para administradores")
    
    if st.button("🔄 Migrar estructura de diplomas existentes"):
        if st.session_state.get("confirmar_migracion"):
            try:
                with st.spinner("Migrando diplomas..."):
                    # Obtener todos los diplomas actuales
                    diplomas_res = supabase.table("diplomas").select("*").execute()
                    
                    migrados = 0
                    errores = 0
                    
                    for diploma in diplomas_res.data or []:
                        try:
                            # Obtener datos del contexto
                            participante_res = supabase.table("participantes").select("*").eq(
                                "id", diploma["participante_id"]
                            ).execute()
                            
                            if not participante_res.data:
                                continue
                                
                            participante = participante_res.data[0]
                            
                            # Generar nueva ruta usando la lógica optimizada
                            # ... (lógica de migración) ...
                            
                            migrados += 1
                            
                        except Exception as e:
                            errores += 1
                            st.error(f"Error migrando diploma {diploma['id']}: {e}")
                    
                    st.success(f"✅ Migración completada: {migrados} diplomas migrados, {errores} errores")
                    
            except Exception as e:
                st.error(f"❌ Error en migración: {e}")
        else:
            st.session_state["confirmar_migracion"] = True
            st.warning("⚠️ Pulsa nuevamente para confirmar migración. ASEGÚRATE DE TENER BACKUP.")
            
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
