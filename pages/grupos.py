import streamlit as st
import pandas as pd
from datetime import datetime, time
from utils import export_csv, validar_dni_cif, get_ajustes_app
from components.listado_con_ficha import listado_con_ficha
from typing import Dict, Any, Tuple, List
from services.grupos_service import get_grupos_service

# =========================
# FUNCIÓN PRINCIPAL
# =========================

def main(supabase, session_state):
    st.title("👥 Gestión de Grupos")
    st.caption("Creación y administración de grupos formativos según estándares FUNDAE.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicio especializado de grupos
    grupos_service = get_grupos_service(supabase, session_state)

    # =========================
    # CARGAR DATOS PRINCIPALES
    # =========================
    try:
        df_grupos = grupos_service.get_grupos_completos()
        acciones_dict = grupos_service.get_acciones_dict()
        
        if session_state.role == "admin":
            empresas_dict = grupos_service.get_empresas_dict()
        else:
            empresas_dict = {}
            
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # =========================
    # PARTE SUPERIOR: KPIs + FILTROS + TABLA
    # =========================
    mostrar_kpis_grupos(df_grupos)
    df_filtered = mostrar_filtros_busqueda(df_grupos)
    mostrar_tabla_informativa(df_filtered)

    # =========================
    # SELECTOR GLOBAL DE GRUPO
    # =========================
    st.divider()
    grupo_seleccionado = mostrar_selector_grupo(df_grupos)
    
    # =========================
    # SISTEMA DE TABS MEJORADO
    # =========================
    # Solo habilitar tabs si hay grupo seleccionado, excepto Descripción
    if grupo_seleccionado:
        tabs_habilitadas = [
            "📝 Descripción",
            "👨‍🏫 Tutores / Centro Gestor", 
            "🏢 Empresas",
            "👥 Participantes",
            "💰 Costes FUNDAE"
        ]
    else:
        tabs_habilitadas = ["📝 Descripción"]
        # Mostrar mensaje informativo
        st.info("ℹ️ Selecciona un grupo existente o crea uno nuevo en la pestaña Descripción.")
    
    tabs = st.tabs(tabs_habilitadas)
    
    # TAB 1: DESCRIPCIÓN (Crear/Editar)
    with tabs[0]:
        mostrar_tab_descripcion(supabase, session_state, grupos_service, acciones_dict, empresas_dict, grupo_seleccionado)
    
    # TABS ADICIONALES (solo si hay grupo seleccionado)
    if grupo_seleccionado:
        with tabs[1]:
            mostrar_tab_tutores_centro(supabase, session_state, grupos_service, grupo_seleccionado)
        
        with tabs[2]:
            mostrar_tab_empresas(supabase, session_state, grupos_service, grupo_seleccionado, empresas_dict)
        
        with tabs[3]:
            mostrar_tab_participantes_nuevo(supabase, session_state, grupos_service, grupo_seleccionado)
        
        with tabs[4]:
            mostrar_tab_costes_fundae_nuevo(supabase, session_state, grupos_service, grupo_seleccionado)


def mostrar_kpis_grupos(df_grupos):
    """Muestra KPIs rápidos de grupos."""
    if not df_grupos.empty:
        col1, col2, col3, col4 = st.columns(4)
        hoy = datetime.now()
        
        activos = len(df_grupos[
            (pd.to_datetime(df_grupos["fecha_inicio"], errors="coerce") <= hoy) & 
            (df_grupos["fecha_fin"].isna() | (pd.to_datetime(df_grupos["fecha_fin"], errors="coerce") >= hoy))
        ])
        finalizados = len(df_grupos[pd.to_datetime(df_grupos["fecha_fin"], errors="coerce") < hoy])
        proximos = len(df_grupos[pd.to_datetime(df_grupos["fecha_inicio"], errors="coerce") > hoy])
        
        col1.metric("👥 Total Grupos", len(df_grupos))
        col2.metric("🟢 Activos", activos)
        col3.metric("🔴 Finalizados", finalizados)
        col4.metric("📅 Próximos", proximos)


def mostrar_filtros_busqueda(df_grupos):
    """Muestra filtros de búsqueda y devuelve DataFrame filtrado."""
    st.markdown("### 🔍 Filtros y Búsqueda")
    col1, col2 = st.columns(2)
    
    with col1:
        query = st.text_input("🔍 Buscar por código o acción formativa")
    with col2:
        estado_filter = st.selectbox("Filtrar por estado", ["Todos", "Activos", "Finalizados", "Próximos"])

    df_filtered = df_grupos.copy()
    
    if query and not df_filtered.empty:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["codigo_grupo"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["accion_nombre"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]
    
    if estado_filter != "Todos" and not df_filtered.empty:
        hoy = datetime.now()
        if estado_filter == "Activos":
            df_filtered = df_filtered[
                (pd.to_datetime(df_filtered["fecha_inicio"], errors="coerce") <= hoy) & 
                (df_filtered["fecha_fin"].isna() | (pd.to_datetime(df_filtered["fecha_fin"], errors="coerce") >= hoy))
            ]
        elif estado_filter == "Finalizados":
            df_filtered = df_filtered[pd.to_datetime(df_filtered["fecha_fin"], errors="coerce") < hoy]
        elif estado_filter == "Próximos":
            df_filtered = df_filtered[pd.to_datetime(df_filtered["fecha_inicio"], errors="coerce") > hoy]

    return df_filtered


def mostrar_tabla_informativa(df_filtered):
    """Muestra tabla informativa (solo lectura) con export CSV."""
    st.markdown("### 📊 Vista General de Grupos")
    
    if df_filtered.empty:
        st.info("ℹ️ No hay grupos para mostrar.")
        return

    # Preparar columnas para mostrar
    columnas_mostrar = [
        "codigo_grupo", "accion_nombre", "modalidad", 
        "fecha_inicio", "fecha_fin_prevista", "localidad", 
        "n_participantes_previstos"
    ]
    
    # Filtrar columnas que existen
    columnas_existentes = [col for col in columnas_mostrar if col in df_filtered.columns]
    
    # Mostrar tabla
    st.dataframe(
        df_filtered[columnas_existentes],
        use_container_width=True,
        hide_index=True
    )
    
    # Export CSV
    export_csv(df_filtered, filename="grupos.csv")


def mostrar_selector_grupo(df_grupos):
    """Muestra selector global de grupo."""
    st.markdown("### 🎯 Selector de Grupo")
    
    if df_grupos.empty:
        st.info("ℹ️ No hay grupos disponibles. Crea uno nuevo en la pestaña Descripción.")
        return None
    
    # Preparar opciones
    opciones_grupos = [""] + df_grupos["codigo_grupo"].tolist()
    
    grupo_codigo_sel = st.selectbox(
        "Selecciona un grupo para gestionar:",
        options=opciones_grupos,
        key="grupo_selector_global",
        help="Escoge un grupo existente para editar o gestionar sus componentes"
    )
    
    if grupo_codigo_sel:
        # Obtener ID del grupo seleccionado
        grupo_info = df_grupos[df_grupos["codigo_grupo"] == grupo_codigo_sel]
        if not grupo_info.empty:
            grupo_id = grupo_info.iloc[0]["id"]
            
            # Mostrar información básica del grupo seleccionado
            with st.expander("ℹ️ Información del Grupo Seleccionado", expanded=False):
                col1, col2, col3 = st.columns(3)
                grupo_data = grupo_info.iloc[0]
                
                with col1:
                    st.write(f"**Código:** {grupo_data.get('codigo_grupo', '')}")
                    st.write(f"**Modalidad:** {grupo_data.get('modalidad', '')}")
                
                with col2:
                    st.write(f"**Fecha Inicio:** {grupo_data.get('fecha_inicio', '')}")
                    st.write(f"**Acción:** {grupo_data.get('accion_nombre', 'No asignada')}")
                
                with col3:
                    st.write(f"**Participantes Previstos:** {grupo_data.get('n_participantes_previstos', 0)}")
                    st.write(f"**Localidad:** {grupo_data.get('localidad', '')}")
            
            return grupo_id
    
    return None


# =========================
# TAB 1: DESCRIPCIÓN (Crear/Editar)
# =========================

def mostrar_tab_descripcion(supabase, session_state, grupos_service, acciones_dict, empresas_dict, grupo_id):
    """Tab 1: Crear o editar grupo (mismo formulario para ambos)."""
    
    # Determinar si es creación o edición
    es_edicion = grupo_id is not None
    titulo = "✏️ Editar Grupo" if es_edicion else "➕ Crear Nuevo Grupo"
    
    st.markdown(f"#### {titulo}")
    
    # Obtener datos del grupo si es edición
    datos_grupo_actual = {}
    if es_edicion:
        try:
            resultado = supabase.table("grupos").select("*").eq("id", grupo_id).execute()
            if resultado.data:
                datos_grupo_actual = resultado.data[0]
        except Exception as e:
            st.error(f"❌ Error al cargar datos del grupo: {e}")
            return
    
    # Formulario unificado
    with st.form("form_descripcion_grupo"):
        # === INFORMACIÓN BÁSICA ===
        st.markdown("### 📋 Información Básica")
        
        col1, col2 = st.columns(2)
        
        with col1:
            codigo_grupo = st.text_input(
                "Código de Grupo *", 
                value=datos_grupo_actual.get("codigo_grupo", ""),
                help="Código único identificativo (máx. 50 caracteres)",
                disabled=es_edicion  # No permitir cambiar código en edición
            )
            
            accion_actual = ""
            if es_edicion and datos_grupo_actual.get("accion_formativa_id"):
                # Buscar nombre de la acción actual
                for nombre, id_accion in acciones_dict.items():
                    if id_accion == datos_grupo_actual["accion_formativa_id"]:
                        accion_actual = nombre
                        break
            
            accion_sel = st.selectbox(
                "Acción Formativa *", 
                options=[""] + list(acciones_dict.keys()),
                index=list(acciones_dict.keys()).index(accion_actual) + 1 if accion_actual else 0,
                help="Selecciona la acción formativa"
            )
            
            modalidad = st.selectbox(
                "Modalidad *", 
                ["PRESENCIAL", "TELEFORMACION", "MIXTA"],
                index=["PRESENCIAL", "TELEFORMACION", "MIXTA"].index(datos_grupo_actual.get("modalidad", "PRESENCIAL"))
            )
            
            localidad = st.text_input(
                "Localidad *", 
                value=datos_grupo_actual.get("localidad", ""),
                help="Obligatorio para FUNDAE"
            )
            
            provincia = st.text_input(
                "Provincia", 
                value=datos_grupo_actual.get("provincia", "")
            )
        
        with col2:
            fecha_inicio = st.date_input(
                "Fecha de Inicio *",
                value=datetime.fromisoformat(datos_grupo_actual["fecha_inicio"]).date() if datos_grupo_actual.get("fecha_inicio") else None
            )
            
            fecha_fin_prevista = st.date_input(
                "Fecha Fin Prevista *",
                value=datetime.fromisoformat(datos_grupo_actual["fecha_fin_prevista"]).date() if datos_grupo_actual.get("fecha_fin_prevista") else None
            )
            
            n_participantes_previstos = st.number_input(
                "Participantes Previstos *", 
                min_value=1, 
                max_value=30, 
                value=int(datos_grupo_actual.get("n_participantes_previstos", 10)),
                help="Entre 1 y 30 participantes (requisito FUNDAE)"
            )
            
            cp = st.text_input(
                "Código Postal", 
                value=datos_grupo_actual.get("cp", "")
            )
            
            lugar_imparticion = st.text_area(
                "Lugar de Impartición", 
                value=datos_grupo_actual.get("lugar_imparticion", ""),
                help="Dirección completa del lugar de formación"
            )
        
        # === HORARIOS DINÁMICOS ===
        st.markdown("### 🕐 Horarios de Impartición")
        
        # Parsear horario actual si existe
        horario_actual = datos_grupo_actual.get("horario", "")
        m_inicio, m_fin, t_inicio, t_fin, dias_actuales = grupos_service.parse_horario(horario_actual)
        
        # Tipo de horario
        tipo_horario_opciones = ["Solo Mañana", "Solo Tarde", "Mañana y Tarde"]
        tipo_horario_default = 0
        
        if m_inicio and t_inicio:
            tipo_horario_default = 2  # Mañana y Tarde
        elif t_inicio:
            tipo_horario_default = 1  # Solo Tarde
        else:
            tipo_horario_default = 0  # Solo Mañana
        
        tipo_horario = st.radio(
            "Tipo de horario:",
            tipo_horario_opciones,
            index=tipo_horario_default,
            horizontal=True
        )
        
        # Horarios dinámicos según selección
        m_inicio_input, m_fin_input, t_inicio_input, t_fin_input = None, None, None, None
        
        if tipo_horario in ["Solo Mañana", "Mañana y Tarde"]:
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                m_inicio_input = st.time_input(
                    "Mañana - Inicio", 
                    value=m_inicio if m_inicio else time(9, 0)
                )
            with col_m2:
                m_fin_input = st.time_input(
                    "Mañana - Fin", 
                    value=m_fin if m_fin else time(13, 0)
                )
        
        if tipo_horario in ["Solo Tarde", "Mañana y Tarde"]:
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                t_inicio_input = st.time_input(
                    "Tarde - Inicio", 
                    value=t_inicio if t_inicio else time(15, 0)
                )
            with col_t2:
                t_fin_input = st.time_input(
                    "Tarde - Fin", 
                    value=t_fin if t_fin else time(19, 0)
                )
        
        # Días de la semana
        st.markdown("**📅 Días de Impartición**")
        dias_cols = st.columns(7)
        dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        dias_seleccionados = {}
        
        for i, dia in enumerate(dias_nombres):
            with dias_cols[i]:
                # Marcar como seleccionado si está en horario actual o por defecto L-V
                default_value = dia in dias_actuales if dias_actuales else (i < 5)
                dias_seleccionados[dia] = st.checkbox(dia, value=default_value)
        
        # === CAMPOS DE FINALIZACIÓN (solo si fecha pasada) ===
        mostrar_finalizacion = es_edicion and grupos_service.fecha_pasada(datos_grupo_actual.get("fecha_fin_prevista", ""))
        
        if mostrar_finalizacion:
            st.markdown("### 🏁 Datos de Finalización")
            st.info("ℹ️ Este grupo ha superado su fecha prevista. Complete los datos de finalización para FUNDAE.")
            
            col_fin1, col_fin2, col_fin3, col_fin4 = st.columns(4)
            
            with col_fin1:
                fecha_fin = st.date_input(
                    "Fecha Fin Real *",
                    value=datetime.fromisoformat(datos_grupo_actual["fecha_fin"]).date() if datos_grupo_actual.get("fecha_fin") else None
                )
            
            with col_fin2:
                n_participantes_finalizados = st.number_input(
                    "Participantes Finalizados *",
                    min_value=0,
                    value=int(datos_grupo_actual.get("n_participantes_finalizados", 0))
                )
            
            with col_fin3:
                n_aptos = st.number_input(
                    "Aptos *",
                    min_value=0,
                    value=int(datos_grupo_actual.get("n_aptos", 0))
                )
            
            with col_fin4:
                n_no_aptos = st.number_input(
                    "No Aptos *",
                    min_value=0,
                    value=int(datos_grupo_actual.get("n_no_aptos", 0))
                )
            
            # Validación automática
            if n_aptos + n_no_aptos != n_participantes_finalizados:
                st.error("⚠️ La suma de Aptos y No Aptos debe ser igual a Participantes Finalizados.")
        
        # === OBSERVACIONES ===
        observaciones = st.text_area(
            "Observaciones",
            value=datos_grupo_actual.get("observaciones", ""),
            help="Información adicional sobre el grupo"
        )
        
        # === BOTÓN DE ENVÍO ===
        texto_boton = "💾 Actualizar Grupo" if es_edicion else "🎯 Crear Grupo"
        submitted = st.form_submit_button(texto_boton, use_container_width=True)
        
        if submitted:
            # Validaciones previas
            errores = []
            
            if not codigo_grupo:
                errores.append("El código de grupo es obligatorio")
            
            if not accion_sel:
                errores.append("Debes seleccionar una acción formativa")
            
            if not localidad:
                errores.append("La localidad es obligatoria para FUNDAE")
            
            if not fecha_inicio or not fecha_fin_prevista:
                errores.append("Las fechas de inicio y fin prevista son obligatorias")
            
            if fecha_inicio and fecha_fin_prevista and fecha_inicio >= fecha_fin_prevista:
                errores.append("La fecha de fin debe ser posterior a la de inicio")
            
            # Verificar código único solo en creación
            if not es_edicion:
                codigo_existe = supabase.table("grupos").select("id").eq("codigo_grupo", codigo_grupo).execute()
                if codigo_existe.data:
                    errores.append("Ya existe un grupo con ese código")
            
            # Validar días seleccionados
            dias_elegidos = [dia for dia, seleccionado in dias_seleccionados.items() if seleccionado]
            if not dias_elegidos:
                errores.append("Debes seleccionar al menos un día de la semana")
            
            # Validaciones de finalización
            if mostrar_finalizacion:
                if not fecha_fin:
                    errores.append("La fecha de finalización real es obligatoria")
                if n_aptos + n_no_aptos != n_participantes_finalizados:
                    errores.append("La suma de aptos + no aptos debe igual participantes finalizados")
            
            if errores:
                for error in errores:
                    st.error(f"⚠️ {error}")
                return
            
            # Construir horario
            horario_completo = grupos_service.build_horario_string(
                m_inicio_input, m_fin_input, t_inicio_input, t_fin_input, dias_elegidos
            )
            
            # Preparar datos
            datos_grupo = {
                "codigo_grupo": codigo_grupo,
                "accion_formativa_id": acciones_dict[accion_sel],
                "modalidad": modalidad,
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin_prevista": fecha_fin_prevista.isoformat(),
                "localidad": localidad,
                "provincia": provincia,
                "cp": cp,
                "lugar_imparticion": lugar_imparticion,
                "n_participantes_previstos": n_participantes_previstos,
                "horario": horario_completo,
                "observaciones": observaciones,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Añadir campos de finalización si aplica
            if mostrar_finalizacion:
                datos_grupo.update({
                    "fecha_fin": fecha_fin.isoformat(),
                    "n_participantes_finalizados": n_participantes_finalizados,
                    "n_aptos": n_aptos,
                    "n_no_aptos": n_no_aptos
                })
            
            # Asignar empresa
            if session_state.role == "gestor":
                datos_grupo["empresa_id"] = session_state.user.get("empresa_id")
            
            # Validar con FUNDAE
            tipo_validacion = "finalizacion" if mostrar_finalizacion else "inicio"
            es_valido, errores_fundae = grupos_service.validar_grupo_fundae(datos_grupo, tipo_validacion)
            
            if not es_valido:
                st.error("❌ Errores de validación FUNDAE:")
                for error in errores_fundae:
                    st.error(f"• {error}")
                return
            
            try:
                if es_edicion:
                    # Actualizar grupo existente
                    if grupos_service.update_grupo(grupo_id, datos_grupo):
                        st.success("✅ Grupo actualizado correctamente.")
                        st.rerun()
                else:
                    # Crear nuevo grupo
                    exito, nuevo_grupo_id = grupos_service.create_grupo_completo(datos_grupo)
                    
                    if exito:
                        st.success("✅ Grupo creado exitosamente.")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ Error al crear el grupo.")
                
            except Exception as e:
                st.error(f"❌ Error al guardar grupo: {e}")


# =========================
# TAB 2: TUTORES / CENTRO GESTOR
# =========================

def mostrar_tab_tutores_centro(supabase, session_state, grupos_service, grupo_id):
    """Tab 2: Gestión de tutores y centro gestor."""
    st.markdown("#### 👨‍🏫 Tutores y Centro Gestor")
    
    # === SECCIÓN TUTORES ===
    st.markdown("### 👥 Tutores Asignados")
    
    # Obtener tutores del grupo
    df_tutores_grupo = grupos_service.get_tutores_grupo(grupo_id)
    
    if not df_tutores_grupo.empty:
        # Mostrar tutores actuales
        tutores_display = []
        for _, row in df_tutores_grupo.iterrows():
            tutor_data = row.get("tutor", {})
            if isinstance(tutor_data, dict):
                tutores_display.append({
                    "id": row["id"],
                    "nombre": f"{tutor_data.get('nombre', '')} {tutor_data.get('apellidos', '')}".strip(),
                    "email": tutor_data.get("email", ""),
                    "especialidad": tutor_data.get("especialidad", "")
                })
        
        if tutores_display:
            df_display = pd.DataFrame(tutores_display)
            st.dataframe(df_display[["nombre", "email", "especialidad"]], use_container_width=True, hide_index=True)
            
            # Quitar tutores
            with st.expander("🗑️ Quitar Tutores"):
                tutores_a_quitar = st.multiselect(
                    "Selecciona tutores a quitar:",
                    options=[t["nombre"] for t in tutores_display],
                    key="quitar_tutores"
                )
                
                if tutores_a_quitar and st.button("Confirmar Eliminación", type="secondary"):
                    try:
                        for nombre_tutor in tutores_a_quitar:
                            # Buscar ID de la relación
                            for tutor in tutores_display:
                                if tutor["nombre"] == nombre_tutor:
                                    grupos_service.delete_tutor_grupo(tutor["id"])
                                    break
                        
                        st.success("✅ Tutores eliminados correctamente.")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error al eliminar tutores: {e}")
    else:
        st.info("ℹ️ No hay tutores asignados a este grupo.")
    
    # Añadir tutores
    with st.expander("➕ Añadir Tutores", expanded=False):
        try:
            df_tutores_disponibles = grupos_service.get_tutores_completos()
            
            if not df_tutores_disponibles.empty:
                # Filtrar tutores ya asignados
                tutores_asignados_ids = set()
                if not df_tutores_grupo.empty:
                    for _, row in df_tutores_grupo.iterrows():
                        tutor_data = row.get("tutor", {})
                        if isinstance(tutor_data, dict):
                            tutores_asignados_ids.add(tutor_data.get("id"))
                
                tutores_disponibles = df_tutores_disponibles[
                    ~df_tutores_disponibles["id"].isin(tutores_asignados_ids)
                ]
                
                if not tutores_disponibles.empty:
                    opciones_tutores = {
                        row["nombre_completo"]: row["id"]
                        for _, row in tutores_disponibles.iterrows()
                    }
                    
                    tutores_nuevos = st.multiselect(
                        "Seleccionar tutores:",
                        options=list(opciones_tutores.keys()),
                        help="Puedes seleccionar múltiples tutores"
                    )
                    
                    if tutores_nuevos and st.button("➕ Asignar Tutores", type="primary"):
                        try:
                            for nombre_tutor in tutores_nuevos:
                                tutor_id = opciones_tutores[nombre_tutor]
                                grupos_service.create_tutor_grupo(grupo_id, tutor_id)
                            
                            st.success(f"✅ Se han asignado {len(tutores_nuevos)} tutores.")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Error al asignar tutores: {e}")
                else:
                    st.info("ℹ️ Todos los tutores disponibles ya están asignados.")
            else:
                st.info("ℹ️ No hay tutores disponibles en el sistema.")
                
        except Exception as e:
            st.error(f"❌ Error al cargar tutores: {e}")
    
    # === SECCIÓN CENTRO GESTOR ===
    st.divider()
    st.markdown("### 🏢 Centro Gestor")
    
    # Verificar si es obligatorio (TELEFORMACION o MIXTA)
    try:
        grupo_info = supabase.table("grupos").select("modalidad").eq("id", grupo_id).execute()
        modalidad = grupo_info.data[0]["modalidad"] if grupo_info.data else "PRESENCIAL"
        centro_obligatorio = modalidad in ["TELEFORMACION", "MIXTA"]
        
        if centro_obligatorio:
            st.warning("⚠️ Centro Gestor obligatorio para modalidad TELEFORMACION/MIXTA")
        else:
            st.info("ℹ️ Centro Gestor opcional para modalidad PRESENCIAL")
        
    except Exception as e:
        st.error(f"❌ Error al verificar modalidad: {e}")
        return
    
    # Centro actual
    centro_actual = grupos_service.get_centro_gestor_grupo(grupo_id)
    
    if centro_actual and centro_actual.get("centro"):
        centro_data = centro_actual["centro"]
        st.success("✅ Centro Gestor Asignado:")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Razón Social:** {centro_data.get('razon_social', '')}")
            st.write(f"**CIF:** {centro_data.get('cif', 'No especificado')}")
            st.write(f"**Teléfono:** {centro_data.get('telefono', '')}")
        with col2:
            st.write(f"**Domicilio:** {centro_data.get('domicilio', '')}")
            st.write(f"**Localidad:** {centro_data.get('localidad', '')}")
            st.write(f"**CP:** {centro_data.get('codigo_postal', '')}")
        
        if st.button("🗑️ Desasignar Centro", type="secondary"):
            if grupos_service.unassign_centro_gestor_de_grupo(grupo_id):
                st.success("✅ Centro desasignado correctamente.")
                st.rerun()
    else:
        st.info("ℹ️ No hay centro gestor asignado.")
    
    # Asignar centro existente o crear nuevo
    with st.expander("🏢 Gestionar Centro Gestor", expanded=False):
        tab_centro1, tab_centro2 = st.tabs(["📋 Asignar Existente", "➕ Crear y Asignar"])
        
        with tab_centro1:
            # Seleccionar centro existente
            df_centros_disponibles = grupos_service.get_centros_para_grupo(grupo_id)
            
            if not df_centros_disponibles.empty:
                opciones_centros = {
                    f"{row['razon_social']} - {row['localidad']}": row['id']
                    for _, row in df_centros_disponibles.iterrows()
                }
                
                centro_seleccionado = st.selectbox(
                    "Seleccionar centro:",
                    options=[""] + list(opciones_centros.keys())
                )
                
                if centro_seleccionado and st.button("🔗 Asignar Centro", type="primary"):
                    centro_id = opciones_centros[centro_seleccionado]
                    if grupos_service.assign_centro_gestor_a_grupo(grupo_id, centro_id):
                        st.success("✅ Centro asignado correctamente.")
                        st.rerun()
            else:
                st.info("ℹ️ No hay centros disponibles. Crea uno nuevo en la pestaña siguiente.")
        
        with tab_centro2:
            # Crear nuevo centro
            with st.form("crear_centro_gestor"):
                st.markdown("**Crear Nuevo Centro Gestor**")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    cif_centro = st.text_input("CIF", help="Opcional")
                    razon_social = st.text_input("Razón Social *")
                    nombre_comercial = st.text_input("Nombre Comercial", help="Opcional")
                    telefono_centro = st.text_input("Teléfono *")
                
                with col2:
                    domicilio = st.text_input("Domicilio *")
                    localidad_centro = st.text_input("Localidad *")
                    cp_centro = st.text_input(
                        "Código Postal *", 
                        help="5 dígitos para España, 99999 para extranjero"
                    )
                
                crear_centro = st.form_submit_button("🏢 Crear y Asignar Centro", use_container_width=True)
                
                if crear_centro:
                    # Validaciones
                    errores_centro = []
                    
                    if not razon_social:
                        errores_centro.append("Razón Social es obligatoria")
                    if not telefono_centro:
                        errores_centro.append("Teléfono es obligatorio")
                    if not domicilio:
                        errores_centro.append("Domicilio es obligatorio")
                    if not localidad_centro:
                        errores_centro.append("Localidad es obligatoria")
                    if not cp_centro:
                        errores_centro.append("Código Postal es obligatorio")
                    elif not (cp_centro.isdigit() and len(cp_centro) == 5) and cp_centro != "99999":
                        errores_centro.append("Código Postal debe tener 5 dígitos o ser 99999")
                    
                    if errores_centro:
                        for error in errores_centro:
                            st.error(f"⚠️ {error}")
                        return
                    
                    # Determinar empresa_id
                    if session_state.role == "gestor":
                        empresa_id = session_state.user.get("empresa_id")
                    else:
                        # Admin: usar empresa propietaria del grupo
                        grupo_info = supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
                        empresa_id = grupo_info.data[0]["empresa_id"] if grupo_info.data else None
                    
                    if not empresa_id:
                        st.error("❌ No se pudo determinar la empresa para el centro.")
                        return
                    
                    # Crear centro
                    datos_centro = {
                        "cif": cif_centro if cif_centro else None,
                        "razon_social": razon_social,
                        "nombre_comercial": nombre_comercial if nombre_comercial else None,
                        "telefono": telefono_centro,
                        "domicilio": domicilio,
                        "localidad": localidad_centro,
                        "codigo_postal": cp_centro
                    }
                    
                    try:
                        ok, centro_id = grupos_service.create_centro_gestor(empresa_id, datos_centro)
                        
                        if ok:
                            # Asignar al grupo
                            if grupos_service.assign_centro_gestor_a_grupo(grupo_id, centro_id):
                                st.success("✅ Centro creado y asignado correctamente.")
                                st.rerun()
                            else:
                                st.error("❌ Centro creado pero no se pudo asignar al grupo.")
                        else:
                            st.error("❌ Error al crear el centro.")
                            
                    except Exception as e:
                        st.error(f"❌ Error al crear centro: {e}")


# =========================
# TAB 3: EMPRESAS
# =========================

def mostrar_tab_empresas(supabase, session_state, grupos_service, grupo_id, empresas_dict):
    """Tab 3: Gestión de empresas participantes."""
    st.markdown("#### 🏢 Empresas Participantes")
    
    if session_state.role == "gestor":
        st.info("ℹ️ Como gestor, tu empresa está automáticamente vinculada al grupo. Esta sección es solo informativa.")
    
    # Obtener empresas del grupo
    df_empresas_grupo = grupos_service.get_empresas_grupo(grupo_id)
    
    if not df_empresas_grupo.empty:
        st.markdown("### 🏢 Empresas Actuales")
        
        # Mostrar empresas actuales
        empresas_display = []
        for _, row in df_empresas_grupo.iterrows():
            empresa_data = row.get("empresa", {})
            if isinstance(empresa_data, dict):
                empresas_display.append({
                    "id": row["id"],
                    "nombre": empresa_data.get("nombre", ""),
                    "cif": empresa_data.get("cif", ""),
                    "fecha_asignacion": row.get("fecha_asignacion", "")
                })
        
        if empresas_display:
            df_display = pd.DataFrame(empresas_display)
            st.dataframe(
                df_display[["nombre", "cif", "fecha_asignacion"]], 
                use_container_width=True, 
                hide_index=True
            )
            
            # Solo admin puede quitar empresas
            if session_state.role == "admin":
                with st.expander("🗑️ Quitar Empresas"):
                    empresas_a_quitar = st.multiselect(
                        "Selecciona empresas a quitar:",
                        options=[e["nombre"] for e in empresas_display],
                        key="quitar_empresas"
                    )
                    
                    if empresas_a_quitar and st.button("Confirmar Eliminación", type="secondary"):
                        try:
                            for nombre_empresa in empresas_a_quitar:
                                # Buscar ID de la relación
                                for empresa in empresas_display:
                                    if empresa["nombre"] == nombre_empresa:
                                        grupos_service.delete_empresa_grupo(empresa["id"])
                                        break
                            
                            st.success("✅ Empresas eliminadas correctamente.")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Error al eliminar empresas: {e}")
    else:
        st.info("ℹ️ No hay empresas participantes asignadas.")
    
    # Solo admin puede añadir empresas
    if session_state.role == "admin":
        with st.expander("➕ Añadir Empresas Participantes", expanded=False):
            if empresas_dict:
                # Filtrar empresas ya asignadas
                empresas_asignadas = set()
                if not df_empresas_grupo.empty:
                    for _, row in df_empresas_grupo.iterrows():
                        empresa_data = row.get("empresa", {})
                        if isinstance(empresa_data, dict):
                            empresas_asignadas.add(empresa_data.get("nombre", ""))
                
                empresas_disponibles = {
                    nombre: id_empresa 
                    for nombre, id_empresa in empresas_dict.items() 
                    if nombre not in empresas_asignadas
                }
                
                if empresas_disponibles:
                    empresas_nuevas = st.multiselect(
                        "Seleccionar empresas:",
                        options=list(empresas_disponibles.keys()),
                        help="Empresas cuyos trabajadores participarán en el grupo"
                    )
                    
                    if empresas_nuevas and st.button("➕ Asignar Empresas", type="primary"):
                        try:
                            for nombre_empresa in empresas_nuevas:
                                empresa_id = empresas_disponibles[nombre_empresa]
                                grupos_service.create_empresa_grupo(grupo_id, empresa_id)
                            
                            st.success(f"✅ Se han asignado {len(empresas_nuevas)} empresas.")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Error al asignar empresas: {e}")
                else:
                    st.info("ℹ️ Todas las empresas disponibles ya están asignadas.")
            else:
                st.info("ℹ️ No hay empresas disponibles en el sistema.")


# =========================
# TAB 4: PARTICIPANTES (1:N simplificado)
# =========================

def mostrar_tab_participantes_nuevo(supabase, session_state, grupos_service, grupo_id):
    """Tab 4: Gestión de participantes con relación 1:N."""
    st.markdown("#### 👥 Participantes del Grupo")
    
    # Obtener participantes del grupo
    df_participantes_grupo = grupos_service.get_participantes_grupo(grupo_id)
    
    if not df_participantes_grupo.empty:
        st.markdown("### 👤 Participantes Actuales")
        
        # Mostrar participantes actuales
        columnas_mostrar = ["nif", "nombre", "apellidos", "email", "telefono"]
        columnas_existentes = [col for col in columnas_mostrar if col in df_participantes_grupo.columns]
        
        st.dataframe(
            df_participantes_grupo[columnas_existentes],
            use_container_width=True,
            hide_index=True
        )
        
        # Desasignar participantes
        with st.expander("🗑️ Desasignar Participantes"):
            participantes_a_desasignar = st.multiselect(
                "Selecciona participantes a desasignar:",
                options=[
                    f"{row['nif']} - {row['nombre']} {row['apellidos']}"
                    for _, row in df_participantes_grupo.iterrows()
                ],
                key="desasignar_participantes"
            )
            
            if participantes_a_desasignar and st.button("Confirmar Desasignación", type="secondary"):
                try:
                    for participante_str in participantes_a_desasignar:
                        nif = participante_str.split(" - ")[0]
                        # Buscar participante por NIF
                        participante_row = df_participantes_grupo[df_participantes_grupo["nif"] == nif]
                        if not participante_row.empty:
                            participante_id = participante_row.iloc[0]["id"]
                            grupos_service.desasignar_participante_de_grupo(participante_id)
                    
                    st.success("✅ Participantes desasignados correctamente.")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error al desasignar participantes: {e}")
    else:
        st.info("ℹ️ No hay participantes asignados a este grupo.")
    
    # === ASIGNAR NUEVOS PARTICIPANTES ===
    st.markdown("### ➕ Asignar Participantes")
    
    tab_individual, tab_masivo = st.tabs(["📋 Selección Individual", "📊 Importación Masiva"])
    
    with tab_individual:
        # Obtener participantes disponibles
        df_disponibles = grupos_service.get_participantes_disponibles(grupo_id)
        
        if not df_disponibles.empty:
            opciones_participantes = {
                f"{row['nif']} - {row['nombre']} {row['apellidos']}": row['id']
                for _, row in df_disponibles.iterrows()
            }
            
            participantes_seleccionados = st.multiselect(
                "Seleccionar participantes:",
                options=list(opciones_participantes.keys()),
                help="Participantes sin grupo asignado"
            )
            
            if participantes_seleccionados and st.button("➕ Asignar Participantes", type="primary"):
                try:
                    for participante_str in participantes_seleccionados:
                        participante_id = opciones_participantes[participante_str]
                        grupos_service.asignar_participante_a_grupo(participante_id, grupo_id)
                    
                    st.success(f"✅ Se han asignado {len(participantes_seleccionados)} participantes.")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error al asignar participantes: {e}")
        else:
            st.info("ℹ️ No hay participantes disponibles para asignar.")
    
    with tab_masivo:
        st.markdown("**Instrucciones:**")
        st.markdown("1. Sube un archivo Excel (.xlsx) con una columna llamada 'dni' o 'nif'")
        st.markdown("2. El sistema buscará automáticamente los participantes por NIF")
        st.markdown("3. Solo se asignarán los participantes que existan en el sistema y estén disponibles")
        
        uploaded_file = st.file_uploader("Subir archivo Excel", type=["xlsx"], key="excel_participantes_nuevo")
        
        if uploaded_file:
            try:
                df_import = pd.read_excel(uploaded_file)
                
                # Verificar columnas válidas
                columna_nif = None
                for col in ["dni", "nif", "DNI", "NIF"]:
                    if col in df_import.columns:
                        columna_nif = col
                        break
                
                if not columna_nif:
                    st.error("⚠️ El archivo debe contener una columna llamada 'dni' o 'nif'")
                else:
                    # Mostrar preview
                    st.markdown("**Vista previa del archivo:**")
                    st.dataframe(df_import.head(), use_container_width=True)
                    
                    if st.button("🚀 Procesar Archivo Excel", type="primary"):
                        # Procesar NIFs
                        nifs_import = [str(d).strip() for d in df_import[columna_nif] if pd.notna(d)]
                        nifs_validos = [d for d in nifs_import if validar_dni_cif(d)]
                        nifs_invalidos = set(nifs_import) - set(nifs_validos)

                        if nifs_invalidos:
                            st.warning(f"⚠️ NIFs inválidos detectados: {', '.join(list(nifs_invalidos)[:5])}")

                        # Buscar participantes existentes y disponibles
                        df_disponibles_masivo = grupos_service.get_participantes_disponibles(grupo_id)
                        participantes_disponibles = {p["nif"]: p["id"] for _, p in df_disponibles_masivo.iterrows()}

                        # Procesar asignaciones
                        asignados = 0
                        errores = []

                        for nif in nifs_validos:
                            participante_id = participantes_disponibles.get(nif)
                            
                            if not participante_id:
                                errores.append(f"NIF {nif} no encontrado o no disponible")
                                continue
                                
                            try:
                                grupos_service.asignar_participante_a_grupo(participante_id, grupo_id)
                                asignados += 1
                            except Exception as e:
                                errores.append(f"NIF {nif} - Error: {str(e)}")

                        # Mostrar resultados
                        if asignados > 0:
                            st.success(f"✅ Se han asignado {asignados} participantes al grupo.")
                            
                        if errores:
                            st.warning(f"⚠️ Se encontraron {len(errores)} errores:")
                            for error in errores[:10]:  # Mostrar máximo 10 errores
                                st.warning(f"• {error}")
                        
                        if asignados > 0:
                            st.rerun()
                            
            except Exception as e:
                st.error(f"❌ Error al procesar archivo: {e}")


# =========================
# TAB 5: COSTES FUNDAE
# =========================

def mostrar_tab_costes_fundae_nuevo(supabase, session_state, grupos_service, grupo_id):
    """Tab 5: Gestión de costes FUNDAE mejorada."""
    st.markdown("#### 💰 Costes FUNDAE")
    
    # Obtener información del grupo para cálculos
    try:
        grupo_info = supabase.table("grupos").select("""
            modalidad, n_participantes_previstos,
            accion_formativa:acciones_formativas(num_horas)
        """).eq("id", grupo_id).execute()
        
        if not grupo_info.data:
            st.error("❌ No se pudo cargar información del grupo.")
            return
        
        grupo_data = grupo_info.data[0]
        modalidad = grupo_data.get("modalidad", "PRESENCIAL")
        participantes = int(grupo_data.get("n_participantes_previstos", 0))
        
        accion_data = grupo_data.get("accion_formativa", {})
        horas = int(accion_data.get("num_horas", 0)) if isinstance(accion_data, dict) else 0
        
    except Exception as e:
        st.error(f"❌ Error al cargar datos del grupo: {e}")
        return
    
    # Calcular límite FUNDAE
    limite_boni, tarifa_max = grupos_service.calcular_limite_fundae(modalidad, horas, participantes)
    
    # Mostrar información del grupo
    with st.expander("ℹ️ Información para Cálculo FUNDAE", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Modalidad", modalidad)
        with col2:
            st.metric("Participantes", participantes)
        with col3:
            st.metric("Horas", horas)
        with col4:
            st.metric("Límite Bonificación", f"{limite_boni:,.2f} €")
    
    # === GESTIÓN DE COSTES ===
    st.markdown("### 💵 Costes del Grupo")
    
    # Obtener costes actuales
    costes_actuales = grupos_service.get_grupo_costes(grupo_id)
    
    with st.form("form_costes_fundae"):
        col1, col2 = st.columns(2)
        
        with col1:
            costes_directos = st.number_input(
                "Costes Directos (€)", 
                value=float(costes_actuales.get("costes_directos", 0)),
                min_value=0.0,
                help="Costes directamente imputables (salarios formadores, material, etc.)"
            )
            
            costes_indirectos = st.number_input(
                "Costes Indirectos (€)", 
                value=float(costes_actuales.get("costes_indirectos", 0)),
                min_value=0.0,
                help="Costes indirectos (máx. 30% de directos según FUNDAE)"
            )
            
            costes_organizacion = st.number_input(
                "Costes Organización (€)", 
                value=float(costes_actuales.get("costes_organizacion", 0)),
                min_value=0.0,
                help="Costes de organización y gestión"
            )
        
        with col2:
            costes_salariales = st.number_input(
                "Costes Salariales (€)", 
                value=float(costes_actuales.get("costes_salariales", 0)),
                min_value=0.0,
                help="Costes salariales de participantes"
            )
            
            cofinanciacion_privada = st.number_input(
                "Cofinanciación Privada (€)", 
                value=float(costes_actuales.get("cofinanciacion_privada", 0)),
                min_value=0.0,
                help="Aportación privada de la empresa"
            )
            
            tarifa_hora = st.number_input(
                "Tarifa por Hora (€)", 
                value=float(costes_actuales.get("tarifa_hora", tarifa_max)),
                min_value=0.0,
                max_value=tarifa_max,
                help=f"Máximo permitido: {tarifa_max} €/hora para {modalidad}"
            )
        
        # Cálculos automáticos
        total_costes = costes_directos + costes_indirectos + costes_organizacion + costes_salariales
        limite_calculado = tarifa_hora * horas * participantes
        
        col_calc1, col_calc2 = st.columns(2)
        with col_calc1:
            st.metric("💰 Total Costes Formación", f"{total_costes:,.2f} €")
        with col_calc2:
            st.metric("🎯 Límite Bonificación Calculado", f"{limite_calculado:,.2f} €")
        
        # Validaciones
        validacion_ok = True
        
        if costes_directos > 0:
            porcentaje_indirectos = (costes_indirectos / costes_directos) * 100
            if porcentaje_indirectos > 30:
                st.error(f"⚠️ Costes indirectos ({porcentaje_indirectos:.1f}%) superan el 30% permitido")
                validacion_ok = False
            else:
                st.success(f"✅ Costes indirectos dentro del límite ({porcentaje_indirectos:.1f}%)")
        
        if tarifa_hora > tarifa_max:
            st.error(f"⚠️ Tarifa/hora ({tarifa_hora}€) supera el máximo de {tarifa_max}€ para {modalidad}")
            validacion_ok = False
        
        observaciones_costes = st.text_area(
            "Observaciones",
            value=costes_actuales.get("observaciones", ""),
            help="Detalles adicionales sobre los costes"
        )
        
        # Botón guardar
        guardar_costes = st.form_submit_button("💾 Guardar Costes", use_container_width=True)
        
        if guardar_costes and validacion_ok:
            datos_costes = {
                "grupo_id": grupo_id,
                "costes_directos": costes_directos,
                "costes_indirectos": costes_indirectos,
                "costes_organizacion": costes_organizacion,
                "costes_salariales": costes_salariales,
                "cofinanciacion_privada": cofinanciacion_privada,
                "tarifa_hora": tarifa_hora,
                "modalidad": modalidad,
                "total_costes_formacion": total_costes,
                "limite_maximo_bonificacion": limite_calculado,
                "observaciones": observaciones_costes,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            try:
                    if costes_actuales:
                        # Actualizar existente
                        if grupos_service.update_grupo_coste(grupo_id, datos_costes):
                            st.success("✅ Costes actualizados correctamente.")
                            st.rerun()
                        else:
                            st.error("❌ Error al actualizar costes.")
                    else:
                        # Crear nuevo registro
                        datos_costes["created_at"] = datetime.utcnow().isoformat()
                        if grupos_service.create_grupo_coste(datos_costes):
                            st.success("✅ Costes guardados correctamente.")
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar costes.")
    
    # === BONIFICACIONES MENSUALES ===
    st.divider()
    st.markdown("### 📅 Bonificaciones Mensuales")
    
    df_bonificaciones = grupos_service.get_grupo_bonificaciones(grupo_id)
    
    if not df_bonificaciones.empty:
        # Mostrar bonificaciones existentes
        st.dataframe(
            df_bonificaciones[["mes", "importe", "observaciones"]],
            use_container_width=True,
            hide_index=True
        )
        
        total_bonificado = float(df_bonificaciones["importe"].sum())
        disponible = limite_calculado - total_bonificado
        
        col_boni1, col_boni2 = st.columns(2)
        with col_boni1:
            st.metric("💰 Total Bonificado", f"{total_bonificado:,.2f} €")
        with col_boni2:
            st.metric("💳 Disponible", f"{disponible:,.2f} €")
    else:
        st.info("ℹ️ No hay bonificaciones registradas.")
        total_bonificado = 0
        disponible = limite_calculado
    
    # Añadir nueva bonificación
    with st.expander("➕ Añadir Bonificación Mensual"):
        with st.form("form_bonificacion"):
            col_boni1, col_boni2 = st.columns(2)
            
            with col_boni1:
                mes_bonificacion = st.selectbox(
                    "Mes",
                    options=[
                        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
                    ]
                )
                
                importe_bonificacion = st.number_input(
                    "Importe (€)",
                    min_value=0.0,
                    max_value=disponible,
                    help=f"Máximo disponible: {disponible:,.2f} €"
                )
            
            with col_boni2:
                observaciones_boni = st.text_area("Observaciones Bonificación")
            
            crear_bonificacion = st.form_submit_button("💰 Añadir Bonificación")
            
            if crear_bonificacion:
                if importe_bonificacion <= 0:
                    st.error("⚠️ El importe debe ser mayor que 0")
                elif total_bonificado + importe_bonificacion > limite_calculado:
                    st.error("⚠️ La suma superaría el límite de bonificación")
                else:
                    datos_bonificacion = {
                        "grupo_id": grupo_id,
                        "mes": mes_bonificacion,
                        "importe": importe_bonificacion,
                        "observaciones": observaciones_boni,
                        "created_at": datetime.utcnow().isoformat()
                    }
                    
                    if grupos_service.create_grupo_bonificacion(datos_bonificacion):
                        st.success("✅ Bonificación añadida correctamente.")
                        st.rerun()
    
    # Información FUNDAE
    with st.expander("ℹ️ Información FUNDAE"):
        st.markdown("""
        **Tarifas máximas FUNDAE:**
        - PRESENCIAL/MIXTA: 13 €/hora
        - TELEFORMACION: 7.5 €/hora
        
        **Costes Indirectos:**
        - Máximo 30% de los costes directos
        
        **Límite de Bonificación:**
        - Tarifa/hora × Horas × Participantes
        - No puede superar el total de costes de formación
        """)


if __name__ == "__main__":
    # Para testing local
    pass
