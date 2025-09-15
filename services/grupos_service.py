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
    # MODO DE OPERACIÓN
    # =========================
    # Determinar si estamos en modo edición
    modo_edicion = "grupo_editando" in st.session_state and st.session_state.grupo_editando
    grupo_editando_id = st.session_state.get("grupo_editando") if modo_edicion else None

    # Botones de control principal
    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 2])
    
    with col_btn1:
        if st.button("➕ Crear Nuevo Grupo", type="primary", use_container_width=True):
            st.session_state.grupo_editando = "nuevo"
            st.rerun()
    
    with col_btn2:
        if modo_edicion:
            if st.button("❌ Cancelar Edición", type="secondary", use_container_width=True):
                if "grupo_editando" in st.session_state:
                    del st.session_state.grupo_editando
                st.rerun()
    
    with col_btn3:
        if not df_grupos.empty:
            export_csv(df_grupos, filename="grupos.csv", button_text="📥 Exportar CSV")

    # =========================
    # MODO EDICIÓN/CREACIÓN
    # =========================
    if modo_edicion:
        if grupo_editando_id == "nuevo":
            mostrar_formulario_grupo_secciones(supabase, session_state, grupos_service, acciones_dict, empresas_dict, None)
        else:
            mostrar_formulario_grupo_secciones(supabase, session_state, grupos_service, acciones_dict, empresas_dict, grupo_editando_id)
    else:
        # =========================
        # TABLA PRINCIPAL
        # =========================
        mostrar_tabla_grupos_seleccionable(df_grupos, session_state)


def mostrar_tabla_grupos_seleccionable(df_grupos, session_state):
    """Muestra tabla principal con filas clicables para editar."""
    st.markdown("### 📊 Listado de Grupos")
    
    if df_grupos.empty:
        st.info("ℹ️ No hay grupos disponibles. Crea el primero usando el botón de arriba.")
        return

    # KPIs rápidos
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

    # Filtros
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        query = st.text_input("🔍 Buscar por código o acción formativa")
    with col_f2:
        estado_filter = st.selectbox("Filtrar por estado", ["Todos", "Activos", "Finalizados", "Próximos"])

    # Aplicar filtros
    df_filtered = df_grupos.copy()
    
    if query:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["codigo_grupo"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["accion_nombre"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]
    
    if estado_filter != "Todos":
        if estado_filter == "Activos":
            df_filtered = df_filtered[
                (pd.to_datetime(df_filtered["fecha_inicio"], errors="coerce") <= hoy) & 
                (df_filtered["fecha_fin"].isna() | (pd.to_datetime(df_filtered["fecha_fin"], errors="coerce") >= hoy))
            ]
        elif estado_filter == "Finalizados":
            df_filtered = df_filtered[pd.to_datetime(df_filtered["fecha_fin"], errors="coerce") < hoy]
        elif estado_filter == "Próximos":
            df_filtered = df_filtered[pd.to_datetime(df_filtered["fecha_inicio"], errors="coerce") > hoy]

    # Tabla clicable
    if not df_filtered.empty:
        st.markdown("**👆 Haz clic en una fila para editar el grupo**")
        
        # Preparar columnas para mostrar
        columnas_mostrar = [
            "codigo_grupo", "accion_nombre", "modalidad", 
            "fecha_inicio", "fecha_fin_prevista", "localidad", 
            "n_participantes_previstos"
        ]
        columnas_existentes = [col for col in columnas_mostrar if col in df_filtered.columns]
        
        # Crear tabla clicable usando dataframe
        selected_rows = st.dataframe(
            df_filtered[columnas_existentes],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Si se selecciona una fila, entrar en modo edición
        if selected_rows and "selection" in selected_rows and selected_rows["selection"]["rows"]:
            selected_idx = selected_rows["selection"]["rows"][0]
            grupo_seleccionado = df_filtered.iloc[selected_idx]
            st.session_state.grupo_editando = grupo_seleccionado["id"]
            st.rerun()
    else:
        st.info("ℹ️ No se encontraron grupos con los filtros aplicados.")


# =========================
# FORMULARIO POR SECCIONES PROGRESIVAS
# =========================

def mostrar_formulario_grupo_secciones(supabase, session_state, grupos_service, acciones_dict, empresas_dict, grupo_id):
    """Formulario de grupo con secciones progresivas estilo ecommerce."""
    
    es_creacion = grupo_id is None or grupo_id == "nuevo"
    titulo = "➕ Crear Nuevo Grupo" if es_creacion else "✏️ Editar Grupo"
    
    st.markdown(f"## {titulo}")
    
    # Obtener datos del grupo si es edición
    datos_grupo_actual = {}
    if not es_creacion:
        try:
            resultado = supabase.table("grupos").select("*").eq("id", grupo_id).execute()
            if resultado.data:
                datos_grupo_actual = resultado.data[0]
                st.info(f"📝 Editando grupo: **{datos_grupo_actual.get('codigo_grupo', 'Sin código')}**")
        except Exception as e:
            st.error(f"❌ Error al cargar datos del grupo: {e}")
            return

    # =========================
    # SECCIÓN 1: DATOS BÁSICOS FUNDAE (OBLIGATORIO)
    # =========================
    with st.container():
        st.markdown("### 📋 1. Datos Básicos FUNDAE")
        st.markdown("*Información mínima requerida para crear el grupo*")
        
        with st.form("form_datos_basicos"):
            col1, col2 = st.columns(2)
            
            with col1:
                codigo_grupo = st.text_input(
                    "Código de Grupo *", 
                    value=datos_grupo_actual.get("codigo_grupo", ""),
                    help="Código único identificativo (máx. 50 caracteres)",
                    disabled=not es_creacion
                )
                
                accion_actual = ""
                if not es_creacion and datos_grupo_actual.get("accion_formativa_id"):
                    for nombre, id_accion in acciones_dict.items():
                        if id_accion == datos_grupo_actual["accion_formativa_id"]:
                            accion_actual = nombre
                            break
                
                accion_sel = st.selectbox(
                    "Acción Formativa *", 
                    options=[""] + list(acciones_dict.keys()),
                    index=list(acciones_dict.keys()).index(accion_actual) + 1 if accion_actual else 0
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
                
                lugar_imparticion = st.text_area(
                    "Lugar de Impartición", 
                    value=datos_grupo_actual.get("lugar_imparticion", ""),
                    help="Dirección completa del lugar de formación"
                )

            # === HORARIOS MEJORADOS ===
            st.markdown("#### 🕐 Horarios de Impartición")
            
            # Parsear horario actual
            horario_actual = datos_grupo_actual.get("horario", "")
            m_inicio, m_fin, t_inicio, t_fin, dias_actuales = grupos_service.parse_horario(horario_actual)
            if dias_actuales is None:
                dias_actuales = []

            col_h1, col_h2, col_h3, col_h4 = st.columns(4)
            
            with col_h1:
                horario_manana_inicio = st.time_input(
                    "Mañana - Inicio",
                    value=m_inicio if m_inicio else None,
                    help="Horario de mañana (hasta 15:00)"
                )
            
            with col_h2:
                horario_manana_fin = st.time_input(
                    "Mañana - Fin",
                    value=m_fin if m_fin else None,
                    help="Fin del horario de mañana"
                )
            
            with col_h3:
                horario_tarde_inicio = st.time_input(
                    "Tarde - Inicio", 
                    value=t_inicio if t_inicio else None,
                    help="Horario de tarde (desde 15:00)"
                )
            
            with col_h4:
                horario_tarde_fin = st.time_input(
                    "Tarde - Fin",
                    value=t_fin if t_fin else None,
                    help="Fin del horario de tarde"
                )

            # Días de la semana
            st.markdown("**📅 Días de Impartición**")
            dias_cols = st.columns(7)
            dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            dias_seleccionados = {}
            
            for i, dia in enumerate(dias_nombres):
                with dias_cols[i]:
                    default_value = dia in dias_actuales if dias_actuales else (i < 5)
                    dias_seleccionados[dia] = st.checkbox(dia, value=default_value)

            # Campos adicionales opcionales
            col_adic1, col_adic2 = st.columns(2)
            with col_adic1:
                provincia = st.text_input("Provincia", value=datos_grupo_actual.get("provincia", ""))
                cp = st.text_input("Código Postal", value=datos_grupo_actual.get("cp", ""))
            with col_adic2:
                observaciones = st.text_area(
                    "Observaciones",
                    value=datos_grupo_actual.get("observaciones", ""),
                    help="Información adicional sobre el grupo"
                )

            # Campos de finalización si aplica
            mostrar_finalizacion = not es_creacion and grupos_service.fecha_pasada(datos_grupo_actual.get("fecha_fin_prevista", ""))
            
            if mostrar_finalizacion:
                st.markdown("#### 🏁 Datos de Finalización")
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

            # Botón de guardar sección 1
            texto_boton = "💾 Actualizar Datos Básicos" if not es_creacion else "🎯 Crear Grupo"
            submitted_basicos = st.form_submit_button(texto_boton, type="primary", use_container_width=True)
            
            if submitted_basicos:
                # Validaciones
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
                if es_creacion:
                    codigo_existe = supabase.table("grupos").select("id").eq("codigo_grupo", codigo_grupo).execute()
                    if codigo_existe.data:
                        errores.append("Ya existe un grupo con ese código")
                
                # Validar días seleccionados
                dias_elegidos = [dia for dia, seleccionado in dias_seleccionados.items() if seleccionado]
                if not dias_elegidos:
                    errores.append("Debes seleccionar al menos un día de la semana")

                # Validar horarios
                if horario_manana_inicio and horario_manana_fin:
                    if horario_manana_inicio >= horario_manana_fin:
                        errores.append("La hora de fin de mañana debe ser posterior a la de inicio")
                    if horario_manana_fin > time(15, 0):
                        errores.append("El horario de mañana no puede terminar después de las 15:00")

                if horario_tarde_inicio and horario_tarde_fin:
                    if horario_tarde_inicio >= horario_tarde_fin:
                        errores.append("La hora de fin de tarde debe ser posterior a la de inicio")
                    if horario_tarde_inicio < time(15, 0):
                        errores.append("El horario de tarde no puede empezar antes de las 15:00")

                if not horario_manana_inicio and not horario_tarde_inicio:
                    errores.append("Debe especificar al menos un horario (mañana o tarde)")

                # Validaciones de finalización
                if mostrar_finalizacion:
                    if not fecha_fin:
                        errores.append("La fecha de finalización real es obligatoria")
                    if n_aptos + n_no_aptos != n_participantes_finalizados:
                        errores.append("La suma de aptos + no aptos debe igual participantes finalizados")
                
                if errores:
                    for error in errores:
                        st.error(f"⚠️ {error}")
                else:
                    # Construir horario
                    horario_completo = grupos_service.build_horario_string(
                        horario_manana_inicio, horario_manana_fin, horario_tarde_inicio, horario_tarde_fin, dias_elegidos
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
                    
                    # Asignar empresa según rol
                    if session_state.role == "gestor":
                        datos_grupo["empresa_id"] = session_state.user.get("empresa_id")
                    
                    # Validar con FUNDAE
                    tipo_validacion = "finalizacion" if mostrar_finalizacion else "inicio"
                    es_valido, errores_fundae = grupos_service.validar_grupo_fundae(datos_grupo, tipo_validacion)
                    
                    if not es_valido:
                        st.error("❌ Errores de validación FUNDAE:")
                        for error in errores_fundae:
                            st.error(f"• {error}")
                    else:
                        try:
                            if es_creacion:
                                # Crear nuevo grupo
                                exito, nuevo_grupo_id = grupos_service.create_grupo_completo(datos_grupo)
                                
                                if exito:
                                    st.success("✅ Grupo creado exitosamente.")
                                    st.balloons()
                                    # Cambiar a modo edición del grupo recién creado
                                    st.session_state.grupo_editando = nuevo_grupo_id
                                    st.rerun()
                                else:
                                    st.error("❌ Error al crear el grupo.")
                            else:
                                # Actualizar grupo existente
                                if grupos_service.update_grupo(grupo_id, datos_grupo):
                                    st.success("✅ Grupo actualizado correctamente.")
                                    st.rerun()
                                else:
                                    st.error("❌ Error al actualizar el grupo.")
                        except Exception as e:
                            st.error(f"❌ Error al guardar grupo: {e}")

    # =========================
    # SECCIONES ADICIONALES (solo si grupo ya existe)
    # =========================
    if not es_creacion:
        grupo_existe_id = grupo_id
        
        st.divider()
        
        # Sección 2: Tutores
        mostrar_seccion_tutores(supabase, session_state, grupos_service, grupo_existe_id)
        
        st.divider()
        
        # Sección 3: Empresas
        mostrar_seccion_empresas(supabase, session_state, grupos_service, grupo_existe_id, empresas_dict)
        
        st.divider()
        
        # Sección 4: Participantes
        mostrar_seccion_participantes(supabase, session_state, grupos_service, grupo_existe_id)
        
        st.divider()
        
        # Sección 5: Costes FUNDAE
        mostrar_seccion_costes(supabase, session_state, grupos_service, grupo_existe_id)
    else:
        st.info("ℹ️ Las secciones adicionales (Tutores, Empresas, Participantes, Costes) se habilitarán después de crear el grupo.")


# =========================
# SECCIONES ADICIONALES
# =========================

def mostrar_seccion_tutores(supabase, session_state, grupos_service, grupo_id):
    """Sección 2: Gestión de tutores."""
    with st.expander("👨‍🏫 2. Tutores del Grupo", expanded=False):
        # Tutores actuales
        df_tutores_grupo = grupos_service.get_tutores_grupo(grupo_id)
        
        if not df_tutores_grupo.empty:
            st.markdown("**Tutores Asignados:**")
            tutores_display = []
            for _, row in df_tutores_grupo.iterrows():
                tutor_data = row.get("tutor", {})
                if isinstance(tutor_data, dict):
                    tutores_display.append({
                        "nombre": f"{tutor_data.get('nombre', '')} {tutor_data.get('apellidos', '')}".strip(),
                        "email": tutor_data.get("email", ""),
                        "especialidad": tutor_data.get("especialidad", "")
                    })
            
            if tutores_display:
                df_display = pd.DataFrame(tutores_display)
                st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Añadir/Quitar tutores
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
                    "Añadir tutores:",
                    options=list(opciones_tutores.keys()),
                    help="Puedes seleccionar múltiples tutores"
                )
                
                if tutores_nuevos and st.button("➕ Asignar Tutores Seleccionados", type="primary"):
                    try:
                        for nombre_tutor in tutores_nuevos:
                            tutor_id = opciones_tutores[nombre_tutor]
                            grupos_service.create_tutor_grupo(grupo_id, tutor_id)
                        
                        st.success(f"✅ Se han asignado {len(tutores_nuevos)} tutores.")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error al asignar tutores: {e}")


def mostrar_seccion_empresas(supabase, session_state, grupos_service, grupo_id, empresas_dict):
    """Sección 3: Gestión de empresas participantes."""
    with st.expander("🏢 3. Empresas Participantes", expanded=False):
        
        if session_state.role == "gestor":
            st.info("ℹ️ Como gestor, tu empresa está automáticamente vinculada al grupo.")
        
        # Empresas actuales
        df_empresas_grupo = grupos_service.get_empresas_grupo(grupo_id)
        
        if not df_empresas_grupo.empty:
            st.markdown("**Empresas Participantes:**")
            empresas_display = []
            for _, row in df_empresas_grupo.iterrows():
                empresa_data = row.get("empresa", {})
                if isinstance(empresa_data, dict):
                    empresas_display.append({
                        "nombre": empresa_data.get("nombre", ""),
                        "cif": empresa_data.get("cif", "")
                    })
            
            if empresas_display:
                df_display = pd.DataFrame(empresas_display)
                st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Solo admin puede añadir empresas
        if session_state.role == "admin" and empresas_dict:
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
                    "Añadir empresas:",
                    options=list(empresas_disponibles.keys()),
                    help="Empresas cuyos trabajadores participarán en el grupo"
                )
                
                if empresas_nuevas and st.button("➕ Asignar Empresas Seleccionadas", type="primary"):
                    try:
                        for nombre_empresa in empresas_nuevas:
                            empresa_id = empresas_disponibles[nombre_empresa]
                            grupos_service.create_empresa_grupo(grupo_id, empresa_id)
                        
                        st.success(f"✅ Se han asignado {len(empresas_nuevas)} empresas.")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error al asignar empresas: {e}")


def mostrar_seccion_participantes(supabase, session_state, grupos_service, grupo_id):
    """Sección 4: Gestión de participantes."""
    with st.expander("👥 4. Participantes del Grupo", expanded=False):
        
        # Participantes actuales
        df_participantes_grupo = grupos_service.get_participantes_grupo(grupo_id)
        
        if not df_participantes_grupo.empty:
            st.markdown("**Participantes Asignados:**")
            columnas_mostrar = ["nif", "nombre", "apellidos", "email", "telefono"]
            columnas_existentes = [col for col in columnas_mostrar if col in df_participantes_grupo.columns]
            
            st.dataframe(
                df_participantes_grupo[columnas_existentes],
                use_container_width=True,
                hide_index=True
            )
            
            # Desasignar participantes
            participantes_a_desasignar = st.multiselect(
                "Desasignar participantes:",
                options=[
                    f"{row['nif']} - {row['nombre']} {row['apellidos']}"
                    for _, row in df_participantes_grupo.iterrows()
                ],
                help="Selecciona participantes para quitar del grupo"
            )
            
            if participantes_a_desasignar and st.button("🗑️ Desasignar Seleccionados", type="secondary"):
                try:
                    for participante_str in participantes_a_desasignar:
                        nif = participante_str.split(" - ")[0]
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
        
        # Asignar nuevos participantes
        st.markdown("**Asignar Nuevos Participantes:**")
        
        tab_individual, tab_masivo = st.tabs(["👤 Individual", "📊 Masivo (Excel)"])
        
        with tab_individual:
            df_disponibles = grupos_service.get_participantes_disponibles(grupo_id)
            
            if not df_disponibles.empty:
                opciones_participantes = {
                    f"{row['nif']} - {row['nombre']} {row['apellidos']}": row['id']
                    for _, row in df_disponibles.iterrows()
                }
                
                participantes_seleccionados = st.multiselect(
                    "Seleccionar participantes:",
                    options=list(opciones_participantes.keys()),
                    help="Participantes disponibles para asignar"
                )
                
                if participantes_seleccionados and st.button("➕ Asignar Participantes Seleccionados", type="primary"):
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
            st.markdown("3. Solo se asignarán los participantes disponibles")
            
            uploaded_file = st.file_uploader("Subir archivo Excel", type=["xlsx"], key="excel_participantes")
            
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
                        st.markdown("**Vista previa del archivo:**")
                        st.dataframe(df_import.head(), use_container_width=True)
                        
                        if st.button("🚀 Procesar Archivo Excel", type="primary"):
                            # Procesar NIFs
                            nifs_import = [str(d).strip() for d in df_import[columna_nif] if pd.notna(d)]
                            nifs_validos = [d for d in nifs_import if validar_dni_cif(d)]
                            nifs_invalidos = set(nifs_import) - set(nifs_validos)

                            if nifs_invalidos:
                                st.warning(f"⚠️ NIFs inválidos detectados: {', '.join(list(nifs_invalidos)[:5])}")

                            # Buscar participantes disponibles
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
                                for error in errores[:10]:
                                    st.warning(f"• {error}")
                            
                            if asignados > 0:
                                st.rerun()
                                
                except Exception as e:
                    st.error(f"❌ Error al procesar archivo: {e}")


def mostrar_seccion_costes(supabase, session_state, grupos_service, grupo_id):
    """Sección 5: Gestión de costes FUNDAE."""
    with st.expander("💰 5. Costes FUNDAE", expanded=False):
        
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
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Modalidad", modalidad)
        with col2:
            st.metric("Participantes", participantes)
        with col3:
            st.metric("Horas", horas)
        with col4:
            st.metric("Límite Bonificación", f"{limite_boni:,.2f} €")
        
        # Gestión de costes
        costes_actuales = grupos_service.get_grupo_costes(grupo_id)
        
        with st.form("form_costes_fundae"):
            st.markdown("**Costes del Grupo:**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                costes_directos = st.number_input(
                    "Costes Directos (€)", 
                    value=float(costes_actuales.get("costes_directos", 0)),
                    min_value=0.0,
                    help="Costes directamente imputables"
                )
                
                costes_indirectos = st.number_input(
                    "Costes Indirectos (€)", 
                    value=float(costes_actuales.get("costes_indirectos", 0)),
                    min_value=0.0,
                    help="Máx. 30% de directos según FUNDAE"
                )
                
                costes_organizacion = st.number_input(
                    "Costes Organización (€)", 
                    value=float(costes_actuales.get("costes_organizacion", 0)),
                    min_value=0.0
                )
            
            with col2:
                costes_salariales = st.number_input(
                    "Costes Salariales (€)", 
                    value=float(costes_actuales.get("costes_salariales", 0)),
                    min_value=0.0
                )
                
                cofinanciacion_privada = st.number_input(
                    "Cofinanciación Privada (€)", 
                    value=float(costes_actuales.get("cofinanciacion_privada", 0)),
                    min_value=0.0
                )
                
                tarifa_hora = st.number_input(
                    "Tarifa por Hora (€)", 
                    value=float(costes_actuales.get("tarifa_hora", tarifa_max)),
                    min_value=0.0,
                    max_value=tarifa_max,
                    help=f"Máximo: {tarifa_max} €/hora para {modalidad}"
                )
            
            # Cálculos automáticos
            total_costes = costes_directos + costes_indirectos + costes_organizacion + costes_salariales
            limite_calculado = tarifa_hora * horas * participantes
            
            col_calc1, col_calc2 = st.columns(2)
            with col_calc1:
                st.metric("💰 Total Costes", f"{total_costes:,.2f} €")
            with col_calc2:
                st.metric("🎯 Límite Calculado", f"{limite_calculado:,.2f} €")
            
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
                st.error(f"⚠️ Tarifa/hora ({tarifa_hora}€) supera el máximo de {tarifa_max}€")
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
                            
                except Exception as e:
                    st.error(f"❌ Error al guardar costes: {e}")
        
        # Bonificaciones mensuales
        st.markdown("**Bonificaciones Mensuales:**")
        
        df_bonificaciones = grupos_service.get_grupo_bonificaciones(grupo_id)
        
        if not df_bonificaciones.empty:
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
            """)


if __name__ == "__main__":
    # Para testing local
    pass
