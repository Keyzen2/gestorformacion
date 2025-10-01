import streamlit as st
import pandas as pd
import io
import re
import unicodedata
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from utils import validar_dni_cif, export_csv
from services.participantes_service import get_participantes_service
from services.empresas_service import get_empresas_service
from services.grupos_service import get_grupos_service
from services.auth_service import get_auth_service
from services.clases_service import get_clases_service

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
    """Devuelve las empresas disponibles según rol usando el nuevo sistema de jerarquía."""
    try:
        df = _empresas_service.get_empresas_con_jerarquia()
        if df.empty:
            return df
        return df
    except Exception as e:
        st.error(f"❌ Error cargando empresas disponibles: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def cargar_grupos(_grupos_service, _session_state):
    """Carga grupos disponibles según permisos."""
    try:
        df_grupos = _grupos_service.get_grupos_completos()
        
        if df_grupos.empty:
            return df_grupos
            
        if _session_state.role == "admin":
            return df_grupos
            
        elif _session_state.role == "gestor":
            empresa_id = _session_state.user.get("empresa_id")
            if not empresa_id:
                return pd.DataFrame()
                
            try:
                empresas_gestionables = [empresa_id]
                
                clientes_res = _grupos_service.supabase.table("empresas").select("id").eq(
                    "empresa_matriz_id", empresa_id
                ).execute()
                
                if clientes_res.data:
                    empresas_gestionables.extend([c["id"] for c in clientes_res.data])
                
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
    """Prepara los datos de participantes con información de grupos N:N para la tabla."""
    try:
        df_participantes = participantes_service.get_participantes_con_grupos_nn()

        if df_participantes.empty:
            return pd.DataFrame(columns=[
                'id', 'nif', 'nombre', 'apellidos', 'email', 'telefono',
                'empresa_id', 'empresa_nombre', 'num_grupos', 'grupos_codigos'
            ])

        if 'num_grupos' not in df_participantes.columns or 'grupos_codigos' not in df_participantes.columns:
            df_tradicional = participantes_service.get_participantes_completos()

            if not df_tradicional.empty:
                df_tradicional['num_grupos'] = df_tradicional['grupo_id'].apply(lambda x: 1 if pd.notna(x) else 0)
                df_tradicional['grupos_codigos'] = df_tradicional.get('grupo_codigo', '')
                return df_tradicional

        return df_participantes

    except Exception as e:
        st.error(f"❌ Error preparando datos de participantes: {e}")
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
        df = participantes_service.get_participantes_completos()
        
        if df.empty:
            metricas = {"total": 0, "con_grupo": 0, "sin_grupo": 0, "nuevos_mes": 0, "con_diploma": 0}
        else:
            if session_state.role == "gestor":
                empresa_id = session_state.user.get("empresa_id")
                df = df[df["empresa_id"] == empresa_id]
            
            total = len(df)
            con_grupo = len(df[df["grupo_id"].notna()]) if "grupo_id" in df.columns else 0
            sin_grupo = total - con_grupo
            
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
        
        if metricas["total"] > 0:
            st.markdown("#### 📊 Distribución")
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                import plotly.express as px
                data_grupos = {
                    "Estado": ["Con grupo", "Sin grupo"],
                    "Cantidad": [metricas["con_grupo"], metricas["sin_grupo"]]
                }
                fig_grupos = px.pie(values=data_grupos["Cantidad"], names=data_grupos["Estado"], 
                                   title="Asignación a grupos")
                st.plotly_chart(fig_grupos, use_container_width=True)
            
            with col_chart2:
                data_diplomas = {
                    "Estado": ["Con diploma", "Sin diploma"],
                    "Cantidad": [metricas["con_diploma"], metricas["total"] - metricas["con_diploma"]]
                }
                fig_diplomas = px.pie(values=data_diplomas["Cantidad"], names=data_diplomas["Estado"],
                                     title="Diplomas obtenidos")
                st.plotly_chart(fig_diplomas, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Error calculando métricas: {e}")
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
        return None, pd.DataFrame()
    
    st.markdown(f"### {titulo_tabla}")

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_nombre = st.text_input("👤 Nombre/Apellidos contiene", key="filtro_tabla_nombre")
    with col2:
        filtro_nif = st.text_input("🆔 Documento contiene", key="filtro_tabla_nif")
    with col3:
        filtro_empresa = st.text_input("🏢 Empresa contiene", key="filtro_tabla_empresa")

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

    page_size = st.selectbox("📊 Registros por página", [10, 20, 50, 100], index=1, key="page_size_tabla")

    total_rows = len(df_filtrado)
    total_pages = (total_rows // page_size) + (1 if total_rows % page_size else 0)
    page_number = st.number_input("Página", min_value=1, max_value=max(total_pages, 1), step=1, value=1, key="page_num_tabla")

    start_idx = (page_number - 1) * page_size
    end_idx = start_idx + page_size
    df_paged = df_filtrado.iloc[start_idx:end_idx]

    columnas = ["nombre", "apellidos", "nif", "email", "telefono", "empresa_nombre", "num_grupos", "grupos_codigos"]
    
    columnas_disponibles = []
    for col in columnas:
        if col in df_paged.columns:
            columnas_disponibles.append(col)
        elif col == "num_grupos" and "num_grupos" not in df_paged.columns:
            if "grupos_codigos" in df_paged.columns:
                df_paged["num_grupos"] = df_paged["grupos_codigos"].apply(
                    lambda x: len(x.split(", ")) if isinstance(x, str) and x.strip() else 0
                )
            else:
                df_paged["num_grupos"] = 0
            columnas_disponibles.append(col)
        elif col == "grupos_codigos" and "grupos_codigos" not in df_paged.columns:
            df_paged["grupos_codigos"] = ""
            columnas_disponibles.append(col)

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

    if total_rows != len(df_participantes):
        st.info(f"📊 Mostrando {total_rows} de {len(df_participantes)} participantes (filtrados)")

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
        return None, df_paged

# =========================
# SECCIÓN DE GRUPOS N:N PARA PARTICIPANTES
# =========================
def mostrar_seccion_grupos_participante_nn(participantes_service, participante_id, empresa_id, session_state):
    """Gestión de grupos del participante usando relación N:N."""
    st.markdown("### 🎓 Grupos de Formación")
    st.caption("Un participante puede estar inscrito en múltiples grupos a lo largo del tiempo")
    
    if not participante_id:
        st.info("💡 Guarda el participante primero para poder asignar grupos")
        return
    
    try:
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
                        
                        horas = grupo.get('accion_horas', 0)
                        if horas > 0:
                            st.caption(f"⏱️ {horas}h")
                    
                    with col2:
                        fecha_inicio = grupo.get("fecha_inicio")
                        fecha_fin = grupo.get("fecha_fin") or grupo.get("fecha_fin_prevista")
                        
                        if fecha_inicio:
                            inicio_str = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y')
                            st.write(f"📅 Inicio: {inicio_str}")
                        
                        if fecha_fin:
                            fin_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')
                            st.write(f"🏁 Fin: {fin_str}")
                            
                            hoy = pd.Timestamp.now().date()
                            fecha_fin_dt = pd.to_datetime(fecha_fin).date()
                            
                            if fecha_fin_dt < hoy:
                                st.success("✅ Finalizado")
                            elif fecha_inicio and pd.to_datetime(fecha_inicio).date() <= hoy <= fecha_fin_dt:
                                st.info("🟡 En curso")
                            else:
                                st.warning("⏳ Pendiente")
                        
                        modalidad = grupo.get('modalidad', '')
                        if modalidad:
                            st.caption(f"📍 {modalidad}")
                    
                    with col3:
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
        
        st.markdown("#### ➕ Asignar a Nuevo Grupo")
        
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
# SECCIÓN DE CLASES Y SUSCRIPCIONES (NUEVO)
# =========================
def mostrar_seccion_suscripcion_clases(clases_service, participante_id, empresa_id, session_state):
    """Gestión de suscripción a clases del participante."""
    st.markdown("### 🏃‍♀️ Suscripción de Clases")
    st.caption("Sistema de clases con cupos limitados y horarios específicos")
    
    if not participante_id:
        st.info("💡 Guarda el participante primero para configurar su suscripción")
        return
    
    try:
        # Obtener suscripción actual
        suscripcion = clases_service.get_suscripcion_participante(participante_id)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if suscripcion and suscripcion.get("activa"):
                st.success("✅ **Suscripción Activa**")
                
                # Mostrar detalles de la suscripción
                clases_mensuales = suscripcion.get("clases_mensuales", 0)
                clases_usadas = suscripcion.get("clases_usadas_mes", 0)
                disponibles = clases_mensuales - clases_usadas
                
                col_stats1, col_stats2, col_stats3 = st.columns(3)
                with col_stats1:
                    st.metric("🎯 Mensuales", clases_mensuales)
                with col_stats2:
                    st.metric("✅ Usadas", clases_usadas)
                with col_stats3:
                    st.metric("⚡ Disponibles", disponibles, 
                             delta=None if disponibles > 0 else "Sin clases")
                
                # Información adicional
                if suscripcion.get("fecha_activacion"):
                    fecha_activacion = pd.to_datetime(suscripcion["fecha_activacion"]).strftime('%d/%m/%Y')
                    st.caption(f"📅 Activada: {fecha_activacion}")
                
                # Mostrar progreso
                if clases_mensuales > 0:
                    progreso = clases_usadas / clases_mensuales
                    st.progress(progreso, f"Uso mensual: {clases_usadas}/{clases_mensuales}")
                
            else:
                st.warning("❌ **Sin Suscripción Activa**")
                st.info("Este participante no puede reservar clases hasta que se active su suscripción.")
        
        with col2:
            # Configuración de suscripción
            st.markdown("**⚙️ Configurar Suscripción**")
            
            if suscripcion and suscripcion.get("activa"):
                # Modificar suscripción existente
                nuevas_clases = st.number_input(
                    "Clases mensuales",
                    min_value=0,
                    max_value=50,
                    value=suscripcion.get("clases_mensuales", 8),
                    key=f"modificar_clases_{participante_id}"
                )
                
                col_update, col_disable = st.columns(2)
                
                with col_update:
                    if st.button("💾 Actualizar", key=f"update_suscripcion_{participante_id}", use_container_width=True):
                        success = clases_service.actualizar_suscripcion(
                            participante_id, nuevas_clases
                        )
                        if success:
                            st.success("✅ Suscripción actualizada")
                            st.rerun()
                
                with col_disable:
                    if st.button("❌ Desactivar", key=f"disable_suscripcion_{participante_id}", use_container_width=True):
                        confirmar_key = f"confirmar_desactivar_{participante_id}"
                        if st.session_state.get(confirmar_key):
                            success = clases_service.desactivar_suscripcion(participante_id)
                            if success:
                                st.success("✅ Suscripción desactivada")
                                del st.session_state[confirmar_key]
                                st.rerun()
                        else:
                            st.session_state[confirmar_key] = True
                            st.warning("⚠️ Confirmar")
            
            else:
                # Activar nueva suscripción
                clases_mensuales = st.number_input(
                    "Clases mensuales",
                    min_value=1,
                    max_value=50,
                    value=8,
                    key=f"nueva_suscripcion_{participante_id}",
                    help="Número de clases que puede reservar por mes"
                )
                
                if st.button("🚀 Activar Suscripción", key=f"activar_suscripcion_{participante_id}", 
                           type="primary", use_container_width=True):
                    success = clases_service.activar_suscripcion(
                        participante_id, empresa_id, clases_mensuales
                    )
                    if success:
                        st.success("✅ Suscripción activada correctamente")
                        st.rerun()
        
        # Mostrar reservas actuales si tiene suscripción activa
        if suscripcion and suscripcion.get("activa"):
            st.markdown("#### 📅 Reservas Actuales")
            
            reservas = clases_service.get_reservas_participante(participante_id)
            
            if not reservas.empty:
                st.dataframe(
                    reservas,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "clase_nombre": "🏃‍♀️ Clase",
                        "fecha_clase": "📅 Fecha",
                        "horario_display": "⏰ Horario",
                        "estado": "📊 Estado"
                    }
                )
            else:
                st.info("📭 No hay reservas activas")
    
    except Exception as e:
        st.error(f"❌ Error gestionando suscripción de clases: {e}")

# =========================
# SECCIÓN DE AVATAR (NUEVO)
# =========================
def mostrar_seccion_avatar(participantes_service, participante_id, session_state):
    """Gestión de avatar del participante."""
    st.markdown("### 👤 Avatar del Participante")
    st.caption("Imagen de perfil para el portal del alumno")
    
    if not participante_id:
        st.info("💡 Guarda el participante primero para gestionar su avatar")
        return
    
    try:
        # Obtener avatar actual
        avatar_actual = participantes_service.get_avatar_participante(participante_id)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if avatar_actual and avatar_actual.get("archivo_url"):
                avatar_url = avatar_actual["archivo_url"]
                st.image(
                    avatar_url,
                    width=50,                 # miniatura tipo perfil
                    use_container_width=False # evita que se estire
                )
                
                # Información del archivo
                st.caption(f"📁 {avatar_actual.get('archivo_nombre', 'Sin nombre')}")
                if avatar_actual.get("tamaño_bytes"):
                    tamaño_mb = avatar_actual["tamaño_bytes"] / (1024 * 1024)
                    st.caption(f"📏 {tamaño_mb:.2f} MB")
                
                # Botón para eliminar avatar
                if st.button("🗑️ Eliminar Avatar", key=f"eliminar_avatar_{participante_id}"):
                    confirmar_key = f"confirmar_eliminar_avatar_{participante_id}"
                    if st.session_state.get(confirmar_key):
                        success = participantes_service.eliminar_avatar(participante_id)
                        if success:
                            st.success("✅ Avatar eliminado")
                            del st.session_state[confirmar_key]
                            st.rerun()
                    else:
                        st.session_state[confirmar_key] = True
                        st.warning("⚠️ Confirmar eliminación")
            else:
                st.info("📷 Sin avatar")
                st.image(
                    "https://via.placeholder.com/150x150/CCCCCC/FFFFFF?text=Sin+Avatar",
                    width=150,
                    use_column_width=False
                )
        
        with col2:
            st.markdown("**📤 Subir Nuevo Avatar**")
            
            avatar_file = st.file_uploader(
                "Seleccionar imagen",
                type=["jpg", "jpeg", "png"],
                key=f"upload_avatar_{participante_id}",
                help="Archivos JPG o PNG, máximo 2MB. Se redimensionará automáticamente a 150x150px"
            )
            
            if avatar_file is not None:
                file_size_mb = avatar_file.size / (1024 * 1024)
                
                # Previsualización
                st.image(avatar_file, caption="Vista previa", width=150)
                
                # Información del archivo
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.write(f"**📁 Archivo:** {avatar_file.name}")
                with col_info2:
                    color = "🔴" if file_size_mb > 2 else "🟢"
                    st.write(f"{color} **Tamaño:** {file_size_mb:.2f} MB")
                
                if file_size_mb > 2:
                    st.error("❌ Archivo muy grande. Máximo 2MB.")
                else:
                    if st.button(
                        "📤 Subir Avatar", 
                        key=f"btn_upload_avatar_{participante_id}", 
                        type="primary",
                        use_container_width=True
                    ):
                        success = participantes_service.subir_avatar(participante_id, avatar_file)
                        if success:
                            st.success("✅ Avatar subido correctamente")
                            st.rerun()
            else:
                st.info("📂 Selecciona una imagen para continuar")
                
                # Instrucciones
                st.markdown("""
                **📋 Requisitos:**
                - Formatos: JPG, JPEG, PNG
                - Tamaño máximo: 2MB
                - Se redimensionará automáticamente a 150x150px
                - Recomendado: imagen cuadrada para mejor resultado
                """)
    
    except Exception as e:
        st.error(f"❌ Error gestionando avatar: {e}")

# =========================
# FORMULARIO MODIFICADO DE PARTICIPANTE
# =========================
def mostrar_formulario_participante_nn(
    participante_data,
    participantes_service,
    empresas_service,
    grupos_service,
    auth_service,
    clases_service,
    session_state,
    es_creacion=False
):
    """Formulario de participante con gestión N:N de grupos y nuevas funcionalidades."""

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
        # EMPRESA
        # =========================
        st.markdown("### 🏢 Empresa")
        
        try:
            empresa_actual_id = datos.get("empresa_id")
            empresa_actual_nombre = ""
            
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
                    password_final = None
                    if password == "NUEVA_PASSWORD_AUTO":
                        import secrets
                        import string
                        caracteres = string.ascii_letters + string.digits + "!@#$%^&*"
                        password_final = ''.join(secrets.choice(caracteres) for _ in range(12))
                        
                        try:
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
    # SECCIONES ADICIONALES (FUERA DEL FORMULARIO)
    # =========================
    
    mostrar_secciones = False
    participante_id_para_secciones = None
    
    if not es_creacion:
        mostrar_secciones = True
        participante_id_para_secciones = datos.get("id")
    else:
        participante_creado_key = f"participante_creado_{form_id}"
        if st.session_state.get(participante_creado_key):
            mostrar_secciones = True
            participante_id_para_secciones = st.session_state[participante_creado_key]
    
    if mostrar_secciones and participante_id_para_secciones and empresa_id:
        st.markdown("---")
        
        # Crear tabs para las diferentes secciones
        tab_grupos, tab_clases, tab_avatar = st.tabs(["🎓 Grupos FUNDAE", "🏃‍♀️ Clases", "👤 Avatar"])
        
        with tab_grupos:
            mostrar_seccion_grupos_participante_nn(
                participantes_service, 
                participante_id_para_secciones, 
                empresa_id, 
                session_state
            )
        
        with tab_clases:
            mostrar_seccion_suscripcion_clases(
                clases_service,
                participante_id_para_secciones,
                empresa_id,
                session_state
            )
        
        with tab_avatar:
            mostrar_seccion_avatar(
                participantes_service,
                participante_id_para_secciones,
                session_state
            )

# =========================
# PESTAÑA SUSCRIPCIONES DE CLASES (NUEVO)
# =========================
def mostrar_pestana_suscripciones_clases(clases_service, participantes_service, session_state):
    """Pestaña completa para gestión de suscripciones de clases."""
    st.header("🏃‍♀️ Suscripciones de Clases")
    st.caption("Gestión del sistema de clases con horarios específicos y cupos limitados")
    
    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para gestionar suscripciones de clases")
        return
    
    # Sub-tabs para organizar la información
    tab_lista, tab_masiva, tab_reportes = st.tabs([
        "📋 Lista de Suscripciones", 
        "🎯 Activación Masiva", 
        "📊 Reportes"
    ])
    
    with tab_lista:
        mostrar_lista_suscripciones(clases_service, participantes_service, session_state)
    
    with tab_masiva:
        mostrar_activacion_masiva_suscripciones(clases_service, participantes_service, session_state)
    
    with tab_reportes:
        mostrar_reportes_suscripciones(clases_service, session_state)

def mostrar_lista_suscripciones(clases_service, participantes_service, session_state):
    """Lista de todas las suscripciones con filtros."""
    st.markdown("#### 📋 Lista de Suscripciones Activas")
    
    try:
        # Obtener participantes con suscripciones
        df_participantes = participantes_service.get_participantes_completos()
        
        if session_state.role == "gestor":
            empresa_id = session_state.user.get("empresa_id")
            df_participantes = df_participantes[df_participantes["empresa_id"] == empresa_id]
        
        if df_participantes.empty:
            st.info("📋 No hay participantes disponibles")
            return
        
        # Obtener datos de suscripciones para cada participante
        participantes_con_suscripcion = []
        
        for _, participante in df_participantes.iterrows():
            suscripcion = clases_service.get_suscripcion_participante(participante["id"])
            
            estado = "❌ Inactiva"
            clases_mensuales = 0
            clases_usadas = 0
            disponibles = 0
            
            if suscripcion:
                if suscripcion.get("activa"):
                    estado = "✅ Activa"
                    clases_mensuales = suscripcion.get("clases_mensuales", 0)
                    clases_usadas = suscripcion.get("clases_usadas_mes", 0)
                    disponibles = clases_mensuales - clases_usadas
            
            participantes_con_suscripcion.append({
                "id": participante["id"],
                "nombre": f"{participante['nombre']} {participante.get('apellidos', '')}",
                "email": participante["email"],
                "empresa_nombre": participante.get("empresa_nombre", ""),
                "suscripcion_activa": suscripcion.get("activa", False) if suscripcion else False,
                "estado": estado,
                "clases_mensuales": clases_mensuales,
                "clases_usadas": clases_usadas,
                "disponibles": disponibles
            })
        
        df_suscripciones = pd.DataFrame(participantes_con_suscripcion)
        
        # Filtros
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filtro_nombre = st.text_input(
                "🔍 Buscar participante",
                key="filtro_suscripciones_nombre"
            )
        
        with col2:
            filtro_estado = st.selectbox(
                "Estado suscripción",
                ["Todos", "Activas", "Inactivas"],
                key="filtro_suscripciones_estado"
            )
        
        with col3:
            filtro_empresa = st.text_input(
                "🏢 Empresa contiene",
                key="filtro_suscripciones_empresa"
            )
        
        # Aplicar filtros
        df_filtrado = df_suscripciones.copy()
        
        if filtro_nombre:
            df_filtrado = df_filtrado[
                df_filtrado["nombre"].str.contains(filtro_nombre, case=False, na=False) |
                df_filtrado["email"].str.contains(filtro_nombre, case=False, na=False)
            ]
        
        if filtro_estado == "Activas":
            df_filtrado = df_filtrado[df_filtrado["suscripcion_activa"] == True]
        elif filtro_estado == "Inactivas":
            df_filtrado = df_filtrado[df_filtrado["suscripcion_activa"] == False]
        
        if filtro_empresa:
            df_filtrado = df_filtrado[
                df_filtrado["empresa_nombre"].str.contains(filtro_empresa, case=False, na=False)
            ]
        
        # Mostrar tabla
        if not df_filtrado.empty:
            st.dataframe(
                df_filtrado[["nombre", "email", "empresa_nombre", "estado", "clases_mensuales", "clases_usadas", "disponibles"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "nombre": "👤 Participante",
                    "email": "📧 Email",
                    "empresa_nombre": "🏢 Empresa",
                    "estado": "📊 Estado",
                    "clases_mensuales": "🎯 Mensuales",
                    "clases_usadas": "✅ Usadas",
                    "disponibles": "⚡ Disponibles"
                }
            )
            
            # Resumen
            activas = len(df_filtrado[df_filtrado["suscripcion_activa"] == True])
            inactivas = len(df_filtrado[df_filtrado["suscripcion_activa"] == False])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("✅ Activas", activas)
            with col2:
                st.metric("❌ Inactivas", inactivas)
            with col3:
                total_clases_usadas = df_filtrado[df_filtrado["suscripcion_activa"] == True]["clases_usadas"].sum()
                st.metric("🏃‍♀️ Total Usadas", total_clases_usadas)
        
        else:
            st.info("📋 No hay participantes que coincidan con los filtros")
    
    except Exception as e:
        st.error(f"❌ Error mostrando lista de suscripciones: {e}")

def mostrar_activacion_masiva_suscripciones(clases_service, participantes_service, session_state):
    """Activación masiva de suscripciones."""
    st.markdown("#### 🎯 Activación Masiva de Suscripciones")
    
    try:
        # Obtener participantes sin suscripción activa
        df_participantes = participantes_service.get_participantes_completos()
        
        if session_state.role == "gestor":
            empresa_id = session_state.user.get("empresa_id")
            df_participantes = df_participantes[df_participantes["empresa_id"] == empresa_id]
        
        # Filtrar solo los que no tienen suscripción activa
        participantes_sin_suscripcion = []
        
        for _, participante in df_participantes.iterrows():
            suscripcion = clases_service.get_suscripcion_participante(participante["id"])
            
            if not suscripcion or not suscripcion.get("activa"):
                participantes_sin_suscripcion.append({
                    "id": participante["id"],
                    "nombre": f"{participante['nombre']} {participante.get('apellidos', '')}",
                    "email": participante["email"],
                    "empresa_id": participante["empresa_id"],
                    "empresa_nombre": participante.get("empresa_nombre", "")
                })
        
        if not participantes_sin_suscripcion:
            st.success("🎉 Todos los participantes ya tienen suscripción activa")
            return
        
        st.info(f"📋 {len(participantes_sin_suscripcion)} participantes sin suscripción activa")
        
        # Configuración masiva
        col1, col2 = st.columns(2)
        
        with col1:
            clases_mensuales_masivo = st.number_input(
                "🎯 Clases mensuales para todos",
                min_value=1,
                max_value=50,
                value=8,
                help="Número de clases que podrán reservar por mes"
            )
        
        with col2:
            if st.button(
                f"🚀 Activar para {len(participantes_sin_suscripcion)} participantes",
                type="primary",
                use_container_width=True
            ):
                with st.spinner("Activando suscripciones..."):
                    exitos = 0
                    errores = 0
                    
                    progress_bar = st.progress(0)
                    
                    for i, participante in enumerate(participantes_sin_suscripcion):
                        try:
                            success = clases_service.activar_suscripcion(
                                participante["id"],
                                participante["empresa_id"],
                                clases_mensuales_masivo
                            )
                            
                            if success:
                                exitos += 1
                            else:
                                errores += 1
                        
                        except Exception as e:
                            errores += 1
                        
                        # Actualizar barra de progreso
                        progress_bar.progress((i + 1) / len(participantes_sin_suscripcion))
                    
                    if exitos > 0:
                        st.success(f"✅ {exitos} suscripciones activadas correctamente")
                    
                    if errores > 0:
                        st.warning(f"⚠️ {errores} errores durante la activación")
                    
                    if exitos > 0:
                        st.rerun()
        
        # Lista de participantes sin suscripción
        st.markdown("#### 📋 Participantes Sin Suscripción")
        
        df_sin_suscripcion = pd.DataFrame(participantes_sin_suscripcion)
        
        st.dataframe(
            df_sin_suscripcion[["nombre", "email", "empresa_nombre"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "nombre": "👤 Participante",
                "email": "📧 Email",
                "empresa_nombre": "🏢 Empresa"
            }
        )
    
    except Exception as e:
        st.error(f"❌ Error en activación masiva: {e}")

def mostrar_reportes_suscripciones(clases_service, session_state):
    """Reportes y métricas de suscripciones."""
    st.markdown("#### 📊 Reportes de Suscripciones y Clases")
    
    try:
        # Período de análisis
        col1, col2 = st.columns(2)
        
        with col1:
            fecha_inicio = st.date_input(
                "📅 Desde",
                value=datetime.now().date() - timedelta(days=30),
                key="reporte_fecha_inicio"
            )
        
        with col2:
            fecha_fin = st.date_input(
                "📅 Hasta",
                value=datetime.now().date(),
                key="reporte_fecha_fin"
            )
        
        if fecha_inicio > fecha_fin:
            st.error("❌ La fecha de inicio debe ser anterior a la fecha de fin")
            return
        
        # Obtener datos de ocupación
        df_ocupacion = clases_service.get_ocupacion_detallada(fecha_inicio, fecha_fin)
        
        if not df_ocupacion.empty:
            st.markdown("##### 📈 Ocupación por Clase")
            
            # Gráfico de ocupación
            import plotly.express as px
            
            fig_ocupacion = px.bar(
                df_ocupacion,
                x="clase_nombre",
                y="porcentaje_ocupacion",
                color="categoria",
                title="Ocupación por Clase (%)",
                labels={
                    "clase_nombre": "Clase",
                    "porcentaje_ocupacion": "Ocupación (%)",
                    "categoria": "Categoría"
                }
            )
            
            st.plotly_chart(fig_ocupacion, use_container_width=True)
            
            # Tabla detallada
            st.dataframe(
                df_ocupacion,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "clase_nombre": "🏃‍♀️ Clase",
                    "categoria": "🏷️ Categoría",
                    "dia_semana": "📅 Día",
                    "horario": "⏰ Horario",
                    "capacidad_maxima": "👥 Capacidad",
                    "reservas_activas": "✅ Reservas",
                    "porcentaje_ocupacion": st.column_config.ProgressColumn(
                        "📊 Ocupación",
                        min_value=0,
                        max_value=100
                    )
                }
            )
        else:
            st.info("📋 No hay datos de ocupación para el período seleccionado")
        
        # Exportar datos
        if not df_ocupacion.empty:
            st.markdown("##### 📥 Exportar Datos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Exportar ocupación
                csv_ocupacion = df_ocupacion.to_csv(index=False)
                st.download_button(
                    "📊 Exportar Ocupación CSV",
                    data=csv_ocupacion,
                    file_name=f"ocupacion_clases_{fecha_inicio}_{fecha_fin}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col2:
                # Exportar reservas detalladas
                df_reservas = clases_service.exportar_datos_clases(
                    fecha_inicio, fecha_fin, "reservas"
                )
                
                if not df_reservas.empty:
                    csv_reservas = df_reservas.to_csv(index=False)
                    st.download_button(
                        "📝 Exportar Reservas CSV",
                        data=csv_reservas,
                        file_name=f"reservas_clases_{fecha_inicio}_{fecha_fin}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
    
    except Exception as e:
        st.error(f"❌ Error generando reportes: {e}")

# =========================
# EXPORTACIÓN E IMPORTACIÓN
# =========================
def exportar_participantes(participantes_service, session_state, df_filtrado=None, solo_visibles=False):
    """Exporta participantes a CSV respetando filtros, paginación y rol."""
    try:
        if df_filtrado is None:
            df = participantes_service.get_participantes_completos()
            if session_state.role == "gestor":
                empresa_id = session_state.user.get("empresa_id")
                df = df[df["empresa_id"] == empresa_id]
        else:
            df = df_filtrado.copy()

        if df.empty:
            st.warning("⚠️ No hay participantes para exportar.")
            return

        export_scope = st.radio(
            "¿Qué quieres exportar?",
            ["📄 Solo registros visibles en la tabla", "🌍 Todos los registros filtrados"],
            horizontal=True
        )

        if export_scope == "📄 Solo registros visibles en la tabla" and solo_visibles:
            df_export = df
        else:
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

def importar_participantes(auth_service, empresas_service, session_state):
    """Importa participantes usando AuthService centralizado."""
    uploaded = st.file_uploader("📤 Subir archivo CSV/XLSX", type=["csv", "xlsx"], accept_multiple_files=False)

    # Plantilla de ejemplo
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
                    if not fila.get("nombre") or not fila.get("apellidos") or not fila.get("email"):
                        raise ValueError("Nombre, apellidos y email son obligatorios")

                    if "@" not in fila["email"]:
                        raise ValueError(f"Email inválido: {fila['email']}")

                    if session_state.role == "gestor":
                        empresa_id = session_state.user.get("empresa_id")
                    else:
                        empresa_id = fila.get("empresa_id") or None

                    grupo_id = fila.get("grupo_id") or None
                    password = fila.get("password") or None

                    datos = {
                        "nombre": fila.get("nombre"),
                        "apellidos": fila.get("apellidos"),
                        "nif": fila.get("nif") or fila.get("documento"),
                        "email": fila.get("email"),
                        "telefono": fila.get("telefono"),
                        "empresa_id": empresa_id,
                        "grupo_id": grupo_id,
                    }

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
# GESTIÓN DE DIPLOMAS
# =========================
def mostrar_gestion_diplomas_participantes(supabase, session_state, participantes_service):
    """Versión optimizada de gestión de diplomas con nueva estructura de archivos."""
    st.divider()
    st.markdown("### 🎓 Gestión Avanzada de Diplomas")
    st.caption("Sistema optimizado con estructura única por empresa gestora y año")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para gestionar diplomas")
        return

    try:
        empresas_permitidas = participantes_service._get_empresas_gestionables()
        if not empresas_permitidas:
            st.info("No tienes grupos finalizados disponibles.")
            return
        
        hoy = datetime.now().date()
        
        # Obtener grupos finalizados
        query = supabase.table("grupos").select("""
            id, codigo_grupo, fecha_fin, fecha_fin_prevista, empresa_id, ano_inicio,
            accion_formativa:acciones_formativas(id, codigo_accion, ano_fundae, nombre)
        """).in_("empresa_id", empresas_permitidas)
        
        grupos_res = query.execute()
        grupos_data = grupos_res.data or []
        
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
        
        participantes_res = supabase.table("participantes_grupos").select(
            "id, grupo_id, fecha_asignacion, participante:participantes(id, nombre, apellidos, email, nif, empresa_id)"
        ).in_("grupo_id", grupos_finalizados_ids).execute()
        
        participantes_finalizados = participantes_res.data or []
        
        if not participantes_finalizados:
            st.info("No hay participantes en grupos finalizados de tus empresas.")
            return

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

        # Filtros de búsqueda
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
        
        if buscar_participante:
            buscar_lower = buscar_participante.lower()
            participantes_filtrados = [
                p for p in participantes_filtrados 
                if (buscar_lower in p.get("nombre", "").lower() or 
                    buscar_lower in p.get("apellidos", "").lower() or 
                    buscar_lower in p.get("email", "").lower() or
                    buscar_lower in p.get("nif", "").lower())
            ]
        
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

        # Paginación
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

        # Gestión individual de diplomas
        for participante in participantes_pagina:
            grupo_info = grupos_dict_completo.get(participante["grupo_id"], {})
            tiene_diploma = participante["id"] in participantes_con_diploma
        
            accion_info = grupo_info.get("accion_formativa") or {}
            accion_nombre = accion_info.get("nombre", "Sin acción")
            p_info = participante.get("participante", {})
            nombre_completo = f"{p_info.get('nombre', '')} {p_info.get('apellidos', '')}".strip()
        
            status_emoji = "✅" if tiene_diploma else "⏳"
            status_text = "Con diploma" if tiene_diploma else "Pendiente"
        
            with st.expander(
                f"{status_emoji} {nombre_completo} - {grupo_info.get('codigo_grupo', 'Sin código')} ({status_text})",
                expanded=False
            ):
                col_info, col_actions = st.columns([2, 1])
        
                with col_info:
                    st.markdown(f"**📧 Email:** {p_info.get('email', '-')}")
                    st.markdown(f"**🆔 NIF:** {p_info.get('nif', 'No disponible')}")
                    st.markdown(f"**📚 Grupo:** {grupo_info.get('codigo_grupo', 'Sin código')}")
                    st.markdown(f"**📖 Acción:** {accion_nombre}")
        
                    fecha_fin = grupo_info.get("fecha_fin") or grupo_info.get("fecha_fin_prevista")
                    if fecha_fin:
                        fecha_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')
                        st.markdown(f"**📅 Finalizado:** {fecha_str}")
        
                with col_actions:
                    if tiene_diploma:
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
                        st.markdown("**📤 Subir Diploma**")
        
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
                                    f"📤 Subir diploma de {nombre_completo}", 
                                    key=f"btn_upload_{participante['id']}", 
                                    type="primary",
                                    use_container_width=True
                                ):
                                    try:
                                        # 1. Preparar nombres de archivo
                                        file_name = f"{participante['id']}_{diploma_file.name}"
                                        file_path = (
                                            f"diplomas/"
                                            f"{grupo_info.get('ano_inicio', datetime.now().year)}/"
                                            f"{grupo_info.get('empresa_id')}/"
                                            f"{grupo_info.get('id')}/"
                                            f"{file_name}"
                                        )
                        
                                        # 2. Subir archivo al bucket
                                        supabase.storage.from_("diplomas").upload(
                                            file_path,
                                            diploma_file.getvalue()
                                        )
                        
                                        # 3. Obtener URL pública
                                        url = supabase.storage.from_("diplomas").get_public_url(file_path)
                        
                                        # 4. Insertar registro en tabla diplomas
                                        supabase.table("diplomas").insert({
                                            "participante_id": p_info.get("id"),
                                            "grupo_id": grupo_info.get("id"),
                                            "url": url,
                                            "archivo_nombre": diploma_file.name
                                        }).execute()
                        
                                        st.success("✅ Diploma subido y registrado correctamente")
                                        st.rerun()
                        
                                    except Exception as e:
                                        st.error(f"❌ Error al subir diploma: {e}")
                        else:
                            st.info("📂 Selecciona un archivo PDF para continuar")


# =========================
# MAIN PARTICIPANTES
# =========================
def render(supabase, session_state):
    st.title("👥 Gestión de Participantes")

    participantes_service = get_participantes_service(supabase, session_state)
    empresas_service = get_empresas_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)
    auth_service = get_auth_service(supabase, session_state)
    clases_service = get_clases_service(supabase, session_state)

    # Tabs principales expandidos con sistema de clases
    tabs = st.tabs([
        "📋 Listado", 
        "➕ Crear", 
        "🏃‍♀️ Suscripciones",
        "📊 Métricas", 
        "🎓 Diplomas"
    ])

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
    
            # Mostrar tabla
            resultado = mostrar_tabla_participantes(df_participantes, session_state)
            if resultado is not None and len(resultado) == 2:
                seleccionado, df_paged = resultado
            else:
                seleccionado, df_paged = None, pd.DataFrame()
    
            # 👉 FORMULARIO: aparece justo después de la tabla
            if seleccionado is not None:
                with st.container(border=True):
                    mostrar_formulario_participante_nn(
                        seleccionado, 
                        participantes_service, 
                        empresas_service, 
                        grupos_service, 
                        auth_service, 
                        clases_service,
                        session_state, 
                        es_creacion=False
                    )
    
            st.divider()
    
            # Exportación e importación en expanders organizados
            with st.expander("📥 Exportar Participantes"):
                exportar_participantes(participantes_service, session_state, df_filtrado=df_paged, solo_visibles=True)
            
            with st.expander("📤 Importar Participantes"):
                importar_participantes(auth_service, empresas_service, session_state)
    
            with st.expander("ℹ️ Información sobre participantes"):
                st.markdown("""
                - Aquí puedes consultar, filtrar y gestionar los participantes registrados.
                - Desde esta tabla puedes editar sus datos, asignarlos a grupos y gestionar diplomas.
                - Usa los filtros superiores para localizar rápidamente un participante.
                - Mantén actualizados los datos de contacto y el NIF para asegurar la validez de la formación.
                """)
    
        except Exception as e:
            st.error(f"❌ Error cargando participantes: {e}")

    # =========================
    # TAB CREAR
    # =========================
    with tabs[1]:
        with st.container(border=True):
            mostrar_formulario_participante_nn(
                {}, 
                participantes_service, 
                empresas_service, 
                grupos_service, 
                auth_service, 
                clases_service,
                session_state, 
                es_creacion=True
            )

    # =========================
    # NUEVA TAB SUSCRIPCIONES DE CLASES
    # =========================
    with tabs[2]:
        mostrar_pestana_suscripciones_clases(clases_service, participantes_service, session_state)

    # =========================
    # TAB MÉTRICAS
    # =========================
    with tabs[3]:
        mostrar_metricas_participantes(participantes_service, session_state)
        
    # =========================
    # TAB DIPLOMAS
    # =========================
    with tabs[4]:
        mostrar_gestion_diplomas_participantes(supabase, session_state, participantes_service)

