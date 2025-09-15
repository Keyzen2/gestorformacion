import streamlit as st
import pandas as pd
from datetime import datetime, time
from utils import export_csv, validar_dni_cif, get_ajustes_app
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.title("👥 Gestión de Grupos")
    st.caption("Creación y administración de grupos formativos según estándares FUNDAE.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicio de datos
    data_service = get_data_service(supabase, session_state)

    # =========================
    # Cargar datos principales
    # =========================
    try:
        df_grupos = data_service.get_grupos_completos()
        acciones_dict = data_service.get_acciones_dict()
        
        if session_state.role == "admin":
            empresas_dict = data_service.get_empresas_dict()
        else:
            empresas_dict = {}
            
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # =========================
    # PARTE SUPERIOR: ESTADÍSTICAS + FILTROS + TABLA
    # =========================
    mostrar_estadisticas_grupos(df_grupos)
    df_filtered = mostrar_filtros_busqueda(df_grupos)
    mostrar_tabla_grupos(df_filtered, data_service, supabase, session_state, acciones_dict, empresas_dict)

    # =========================
    # PARTE INFERIOR: SISTEMA DE TABS
    # =========================
    st.divider()
    st.markdown("### 📑 Gestión Avanzada de Grupos")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📝 Descripción", 
        "👨‍🏫 Tutores", 
        "🏢 Empresas", 
        "👥 Participantes", 
        "💰 Costes FUNDAE"
    ])
    
    with tab1:
        mostrar_tab_descripcion(supabase, session_state, data_service, acciones_dict, empresas_dict)
    
    with tab2:
        mostrar_tab_tutores(supabase, session_state, data_service)
    
    with tab3:
        mostrar_tab_empresas(supabase, session_state, data_service, empresas_dict)
    
    with tab4:
        mostrar_tab_participantes(supabase, session_state, data_service, df_grupos)
    
    with tab5:
        mostrar_tab_costes_fundae(supabase, session_state, data_service, df_grupos)


def mostrar_estadisticas_grupos(df_grupos):
    """Muestra estadísticas rápidas de grupos."""
    if not df_grupos.empty:
        col1, col2, col3, col4 = st.columns(4)
        hoy = datetime.now()
        
        activos = len(df_grupos[
            (pd.to_datetime(df_grupos["fecha_inicio"], errors="coerce") <= hoy) & 
            (df_grupos["fecha_fin"].isna() | (pd.to_datetime(df_grupos["fecha_fin"], errors="coerce") >= hoy))
        ])
        finalizados = len(df_grupos[pd.to_datetime(df_grupos["fecha_fin"], errors="coerce") < hoy])
        proximos = len(df_grupos[pd.to_datetime(df_grupos["fecha_inicio"], errors="coerce") > hoy])
        promedio = df_grupos["n_participantes_previstos"].mean() if "n_participantes_previstos" in df_grupos.columns else 0
        
        col1.metric("👥 Total Grupos", len(df_grupos))
        col2.metric("🟢 Activos", activos)
        col3.metric("🔴 Finalizados", finalizados)
        col4.metric("📅 Próximos", proximos)


def mostrar_filtros_busqueda(df_grupos):
    """Muestra filtros de búsqueda y devuelve DataFrame filtrado."""
    st.markdown("### 🔍 Buscar y Filtrar")
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

    if not df_filtered.empty:
        export_csv(df_filtered, filename="grupos.csv")
    
    return df_filtered


def mostrar_tabla_grupos(df_filtered, data_service, supabase, session_state, acciones_dict, empresas_dict):
    """Muestra tabla de grupos con edición rápida."""
    st.markdown("### 📊 Lista de Grupos")
    
    if df_filtered.empty:
        st.info("ℹ️ No hay grupos para mostrar.")
        return

    # Funciones CRUD con cache corregido
    def guardar_grupo(grupo_id, datos_editados):
        try:
            # Procesar selects
            if "accion_sel" in datos_editados:
                accion_sel = datos_editados.pop("accion_sel")
                if accion_sel in acciones_dict:
                    datos_editados["accion_formativa_id"] = acciones_dict[accion_sel]

            if session_state.role == "admin" and "empresa_sel" in datos_editados:
                empresa_sel = datos_editados.pop("empresa_sel")
                if empresa_sel in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[empresa_sel]

            # Validaciones
            if not datos_editados.get("codigo_grupo"):
                st.error("⚠️ El código de grupo es obligatorio.")
                return

            # Actualizar
            datos_editados["updated_at"] = datetime.utcnow().isoformat()
            supabase.table("grupos").update(datos_editados).eq("id", grupo_id).execute()
            
            # LIMPIEZA COMPLETA DE CACHE
            limpiar_cache_completo(data_service)
            
            st.success("✅ Grupo actualizado correctamente.")
            st.rerun()
                
        except Exception as e:
            st.error(f"❌ Error al actualizar grupo: {e}")

    def eliminar_grupo(grupo_id):
        try:
            # Verificar dependencias
            participantes = supabase.table("participantes").select("id").eq("grupo_id", grupo_id).execute()
            if participantes.data:
                st.error("⚠️ No se puede eliminar. El grupo tiene participantes asignados.")
                return

            # Eliminar
            supabase.table("grupos").delete().eq("id", grupo_id).execute()
            
            # LIMPIEZA COMPLETA DE CACHE
            limpiar_cache_completo(data_service)
            
            st.success("✅ Grupo eliminado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al eliminar grupo: {e}")

    # Configuración para listado_con_ficha
    def get_campos_dinamicos(datos):
        return ["codigo_grupo", "accion_sel", "fecha_inicio", "fecha_fin_prevista", "localidad", "observaciones"]

    campos_select = {
        "accion_sel": list(acciones_dict.keys()) if acciones_dict else ["No hay acciones disponibles"]
    }
    if session_state.role == "admin" and empresas_dict:
        campos_select["empresa_sel"] = list(empresas_dict.keys())

    # Preparar datos display
    df_display = df_filtered.copy()
    if "accion_nombre" in df_display.columns:
        df_display["accion_sel"] = df_display["accion_nombre"]
    else:
        df_display["accion_sel"] = "Acción no disponible"

    if session_state.role == "admin" and empresas_dict:
        if "empresa_nombre" in df_display.columns:
            df_display["empresa_sel"] = df_display["empresa_nombre"]
        else:
            df_display["empresa_sel"] = "Sin empresa"

    # Columnas visibles
    columnas_visibles = ["codigo_grupo", "accion_nombre", "fecha_inicio", "fecha_fin_prevista", "localidad"]
    if session_state.role == "admin":
        columnas_visibles.insert(2, "empresa_nombre")

    # Mostrar tabla con edición
    listado_con_ficha(
        df=df_display,
        columnas_visibles=[col for col in columnas_visibles if col in df_display.columns],
        titulo="Grupo",
        on_save=guardar_grupo,
        on_create=None,  # Creación se hace en tab descripción
        on_delete=eliminar_grupo if session_state.role == "admin" else None,
        id_col="id",
        campos_select=campos_select,
        campos_dinamicos=get_campos_dinamicos,
        allow_creation=False,
        search_columns=["codigo_grupo", "accion_nombre"]
    )


def mostrar_tab_descripcion(supabase, session_state, data_service, acciones_dict, empresas_dict):
    """Tab de descripción con formulario de creación mejorado según FUNDAE."""
    st.markdown("#### 📝 Crear Nuevo Grupo")
    st.caption("Formulario completo para crear grupos según estándares FUNDAE.")
    
    with st.form("crear_grupo_fundae"):
        col1, col2 = st.columns(2)
        
        # Columna 1: Datos básicos
        with col1:
            st.markdown("**📋 Información Básica**")
            codigo_grupo = st.text_input("Código de Grupo *", help="Código único identificativo")
            
            # Acción formativa con duración calculada
            accion_sel = st.selectbox(
                "Acción Formativa *", 
                options=[""] + list(acciones_dict.keys()),
                help="Selecciona la acción formativa"
            )
            
            # Mostrar duración automática
            if accion_sel and accion_sel in acciones_dict:
                # Obtener horas de la acción
                df_acciones = data_service.get_acciones_formativas()
                accion_data = df_acciones[df_acciones["nombre"] == accion_sel]
                if not accion_data.empty:
                    horas = accion_data.iloc[0].get("num_horas", 0)
                    st.info(f"⏱️ Duración: {horas} horas")
            
            # Empresa (solo para admin)
            if session_state.role == "admin":
                empresa_sel = st.selectbox(
                    "Empresa *",
                    options=[""] + list(empresas_dict.keys()),
                    help="Empresa propietaria del grupo"
                )
            
            # Modalidad y ubicación
            modalidad = st.selectbox("Modalidad *", ["Presencial", "Teleformación", "Mixta"])
            aula_virtual = modalidad in ["Teleformación", "Mixta"]
            
            localidad = st.text_input("Localidad")
            provincia = st.text_input("Provincia")
            cp = st.text_input("Código Postal")
            
        # Columna 2: Fechas y participantes
        with col2:
            st.markdown("**📅 Fechas y Participantes**")
            fecha_inicio = st.date_input("Fecha de Inicio *")
            fecha_fin_prevista = st.date_input("Fecha Fin Prevista *")
            
            n_participantes_previstos = st.number_input(
                "Participantes Previstos *", 
                min_value=1, 
                max_value=30, 
                value=10,
                help="Número de participantes estimado"
            )
            
            st.markdown("**🕐 Horarios FUNDAE**")
            
            # Horario Mañana
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                hora_manana_inicio = st.time_input("Mañana - Inicio", value=time(9, 0))
            with col_m2:
                hora_manana_fin = st.time_input("Mañana - Fin", value=time(13, 0))
            
            # Horario Tarde
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                hora_tarde_inicio = st.time_input("Tarde - Inicio", value=time(15, 0))
            with col_t2:
                hora_tarde_fin = st.time_input("Tarde - Fin", value=time(19, 0))
        
        # Días de la semana (FUNDAE)
        st.markdown("**📅 Días de Impartición**")
        dias_cols = st.columns(7)
        dias_semana = {}
        dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        
        for i, dia in enumerate(dias_nombres):
            with dias_cols[i]:
                dias_semana[dia] = st.checkbox(dia, value=(i < 5))  # L-V por defecto
        
        # Observaciones
        observaciones = st.text_area("Observaciones", help="Información adicional sobre el grupo")
        
        # Botón crear
        btn_crear = st.form_submit_button("🚀 Crear Grupo", type="primary")
        
        if btn_crear:
            crear_grupo_completo(
                supabase, session_state, data_service, 
                codigo_grupo, accion_sel, modalidad, fecha_inicio, fecha_fin_prevista,
                n_participantes_previstos, localidad, provincia, cp,
                hora_manana_inicio, hora_manana_fin, hora_tarde_inicio, hora_tarde_fin,
                dias_semana, observaciones, acciones_dict, empresas_dict
            )


def mostrar_tab_tutores(supabase, session_state, data_service):
    """Tab de gestión de tutores para grupos."""
    st.markdown("#### 👨‍🏫 Asignación de Tutores")
    
    try:
        # Cargar tutores FILTRADOS POR ROL
        df_tutores = data_service.get_tutores_completos()  # Ya aplica filtro empresa en data_service
        df_grupos = data_service.get_grupos_completos()    # Ya aplica filtro empresa en data_service
        
        if df_tutores.empty:
            if session_state.role == "gestor":
                st.info("ℹ️ No hay tutores disponibles en tu empresa. Crea tutores primero en la sección correspondiente.")
            else:
                st.info("ℹ️ No hay tutores disponibles. Crea tutores primero en la sección correspondiente.")
            return
        
        if df_grupos.empty:
            st.info("ℹ️ No hay grupos disponibles.")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Selector de grupo (ya filtrado por empresa si es gestor)
            grupo_options = df_grupos.apply(
                lambda g: f"{g['codigo_grupo']} - {g.get('accion_nombre', 'Sin acción')}", 
                axis=1
            ).tolist()
            
            grupo_sel = st.selectbox("Seleccionar Grupo:", [""] + grupo_options)
            
            if grupo_sel:
                grupo_id = df_grupos.iloc[grupo_options.index(grupo_sel)]["id"]
                
                # Mostrar tutores actuales del grupo
                tutores_actuales = supabase.table("tutores_grupos").select("*").eq("grupo_id", grupo_id).execute()
                if tutores_actuales.data:
                    st.markdown("**Tutores asignados:**")
                    for tg in tutores_actuales.data:
                        tutor_data = df_tutores[df_tutores["id"] == tg["tutor_id"]]
                        if not tutor_data.empty:
                            tutor_nombre = f"{tutor_data.iloc[0]['nombre']} {tutor_data.iloc[0]['apellidos']}"
                            if st.button(f"❌ {tutor_nombre}", key=f"remove_{tg['id']}"):
                                supabase.table("tutores_grupos").delete().eq("id", tg["id"]).execute()
                                st.rerun()
        
        with col2:
            if 'grupo_sel' in locals() and grupo_sel:
                # Selector de tutor (solo tutores de la empresa del gestor)
                tutor_options = df_tutores.apply(
                    lambda t: f"{t['nombre']} {t['apellidos']} - {t.get('especialidad', 'Sin especialidad')}", 
                    axis=1
                ).tolist()
                
                tutor_sel = st.selectbox("Seleccionar Tutor:", [""] + tutor_options)
                
                if tutor_sel and st.button("➕ Asignar Tutor"):
                    tutor_id = df_tutores.iloc[tutor_options.index(tutor_sel)]["id"]
                    
                    # Verificar si ya está asignado
                    existe = supabase.table("tutores_grupos").select("id").eq("grupo_id", grupo_id).eq("tutor_id", tutor_id).execute()
                    if existe.data:
                        st.warning("⚠️ Este tutor ya está asignado al grupo.")
                    else:
                        supabase.table("tutores_grupos").insert({
                            "grupo_id": grupo_id,
                            "tutor_id": tutor_id,
                            "created_at": datetime.utcnow().isoformat()
                        }).execute()
                        st.success("✅ Tutor asignado correctamente.")
                        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error en gestión de tutores: {e}")

def mostrar_tab_empresas(supabase, session_state, data_service, empresas_dict):
    """Tab de gestión de empresas participantes (solo admin por ahora)."""
    st.markdown("#### 🏢 Empresas Participantes")
    
    if session_state.role != "admin":
        st.info("ℹ️ Esta funcionalidad está disponible solo para administradores.")
        return
    
    try:
        df_grupos = data_service.get_grupos_completos()
        
        if df_grupos.empty:
            st.info("ℹ️ No hay grupos disponibles.")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Selector de grupo
            grupo_options = df_grupos.apply(
                lambda g: f"{g['codigo_grupo']} - {g.get('accion_nombre', 'Sin acción')}", 
                axis=1
            ).tolist()
            
            grupo_sel = st.selectbox("Seleccionar Grupo:", [""] + grupo_options, key="empresas_grupo_sel")
            
            if grupo_sel:
                grupo_id = df_grupos.iloc[grupo_options.index(grupo_sel)]["id"]
                
                # Mostrar empresas actuales
                empresas_actuales = supabase.table("empresas_grupos").select("*").eq("grupo_id", grupo_id).execute()
                if empresas_actuales.data:
                    st.markdown("**Empresas participantes:**")
                    for eg in empresas_actuales.data:
                        empresa_nombre = next((k for k, v in empresas_dict.items() if v == eg["empresa_id"]), "Empresa desconocida")
                        if st.button(f"❌ {empresa_nombre}", key=f"remove_emp_{eg['id']}"):
                            supabase.table("empresas_grupos").delete().eq("id", eg["id"]).execute()
                            st.rerun()
        
        with col2:
            if 'grupo_sel' in locals() and grupo_sel:
                # Selector de empresa
                empresa_sel = st.selectbox("Seleccionar Empresa:", [""] + list(empresas_dict.keys()), key="empresas_empresa_sel")
                
                if empresa_sel and st.button("➕ Añadir Empresa"):
                    empresa_id = empresas_dict[empresa_sel]
                    
                    # Verificar si ya está asignada
                    existe = supabase.table("empresas_grupos").select("id").eq("grupo_id", grupo_id).eq("empresa_id", empresa_id).execute()
                    if existe.data:
                        st.warning("⚠️ Esta empresa ya participa en el grupo.")
                    else:
                        supabase.table("empresas_grupos").insert({
                            "grupo_id": grupo_id,
                            "empresa_id": empresa_id,
                            "created_at": datetime.utcnow().isoformat()
                        }).execute()
                        st.success("✅ Empresa añadida al grupo correctamente.")
                        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error en gestión de empresas: {e}")


def mostrar_tab_participantes(supabase, session_state, data_service, df_grupos):
    """Tab de gestión de participantes (funcionalidad existente mejorada)."""
    st.markdown("#### 👥 Gestión de Participantes")
    
    try:
        df_participantes = data_service.get_participantes_completos()
        
        if df_participantes.empty:
            st.info("ℹ️ No hay participantes disponibles.")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🎯 Selección de Grupo**")
            if not df_grupos.empty:
                grupo_options = []
                for _, grupo in df_grupos.iterrows():
                    accion_info = grupo.get("accion_nombre", "Sin acción")
                    fecha_inicio = ""
                    if pd.notna(grupo.get("fecha_inicio")):
                        fecha_inicio = f" - {pd.to_datetime(grupo['fecha_inicio']).strftime('%d/%m/%Y')}"
                    
                    opcion = f"{grupo['codigo_grupo']} - {accion_info}{fecha_inicio}"
                    grupo_options.append(opcion)
                
                grupo_sel = st.selectbox("Seleccionar grupo:", [""] + grupo_options, key="part_grupo_sel")
                
                if grupo_sel:
                    grupo_idx = grupo_options.index(grupo_sel)
                    grupo_id = df_grupos.iloc[grupo_idx]["id"]
                    grupo_data = df_grupos.iloc[grupo_idx]
                    
                    # Info del grupo
                    st.markdown(f"**Código:** {grupo_data['codigo_grupo']}")
                    st.markdown(f"**Acción:** {grupo_data.get('accion_nombre', 'Sin especificar')}")
                    
                    participantes_actuales = len(df_participantes[df_participantes["grupo_id"] == grupo_id])
                    st.markdown(f"**Participantes actuales:** {participantes_actuales}")
                else:
                    grupo_id = None
        
        with col2:
            st.markdown("**👤 Selección de Participante**")
            if 'grupo_id' in locals() and grupo_id:
                participantes_disponibles = df_participantes[
                    (df_participantes["grupo_id"].isna()) | 
                    (df_participantes["grupo_id"] == grupo_id)
                ]
                
                if participantes_disponibles.empty:
                    st.info("ℹ️ No hay participantes disponibles.")
                else:
                    participante_options = []
                    for _, participante in participantes_disponibles.iterrows():
                        nombre_completo = f"{participante['nombre']} {participante.get('apellidos', '')}".strip()
                        email = f" ({participante.get('email', 'Sin email')})"
                        estado = " - ✅ Asignado" if pd.notna(participante.get("grupo_id")) else " - 🆓 Disponible"
                        
                        opcion = f"{nombre_completo}{email}{estado}"
                        participante_options.append(opcion)
                    
                    participante_sel = st.selectbox("Seleccionar participante:", [""] + participante_options, key="part_participante_sel")
                    
                    if participante_sel:
                        participante_idx = participante_options.index(participante_sel)
                        participante_id = participantes_disponibles.iloc[participante_idx]["id"]
                        participante_data = participantes_disponibles.iloc[participante_idx]
                        
                        ya_asignado = pd.notna(participante_data.get("grupo_id")) and participante_data["grupo_id"] == grupo_id
                        
                        if ya_asignado:
                            if st.button("🔄 Desasignar del grupo", key="btn_desasignar"):
                                supabase.table("participantes").update({
                                    "grupo_id": None,
                                    "updated_at": datetime.utcnow().isoformat()
                                }).eq("id", participante_id).execute()
                                limpiar_cache_completo(data_service)
                                st.success("✅ Participante desasignado.")
                                st.rerun()
                        else:
                            if st.button("✅ Asignar al grupo", key="btn_asignar"):
                                supabase.table("participantes").update({
                                    "grupo_id": grupo_id,
                                    "updated_at": datetime.utcnow().isoformat()
                                }).eq("id", participante_id).execute()
                                limpiar_cache_completo(data_service)
                                st.success("✅ Participante asignado.")
                                st.rerun()
        
        # Resumen participantes sin grupo
        participantes_sin_grupo = df_participantes[df_participantes["grupo_id"].isna()]
        if not participantes_sin_grupo.empty:
            with st.expander(f"📋 Participantes sin grupo ({len(participantes_sin_grupo)})"):
                for _, p in participantes_sin_grupo.head(10).iterrows():
                    nombre = f"{p['nombre']} {p.get('apellidos', '')}".strip()
                    email = p.get('email', 'Sin email')
                    st.markdown(f"• **{nombre}** - {email}")
                
                if len(participantes_sin_grupo) > 10:
                    st.caption(f"... y {len(participantes_sin_grupo) - 10} participantes más")
    
    except Exception as e:
        st.error(f"❌ Error en gestión de participantes: {e}")


def mostrar_tab_costes_fundae(supabase, session_state, data_service, df_grupos):
    """Tab de gestión de costes según normativa FUNDAE."""
    st.markdown("#### 💰 Gestión de Costes FUNDAE")
    st.caption("Gestión de costes de formación según normativa de bonificaciones FUNDAE.")
    
    try:
        if df_grupos.empty:
            st.info("ℹ️ No hay grupos disponibles.")
            return
        
        # Selector de grupo finalizado
        grupos_finalizados = df_grupos[pd.to_datetime(df_grupos["fecha_fin"], errors="coerce").notna()]
        
        if grupos_finalizados.empty:
            st.info("ℹ️ Los costes FUNDAE solo se pueden gestionar en grupos finalizados.")
            return
        
        grupo_options = grupos_finalizados.apply(
            lambda g: f"{g['codigo_grupo']} - {g.get('accion_nombre', 'Sin acción')}", 
            axis=1
        ).tolist()
        
        grupo_sel = st.selectbox("Seleccionar Grupo Finalizado:", [""] + grupo_options, key="costes_grupo_sel")
        
        if not grupo_sel:
            return
        
        grupo_idx = grupo_options.index(grupo_sel)
        grupo_data = grupos_finalizados.iloc[grupo_idx]
        grupo_id = grupo_data["id"]
        
        # Información del grupo
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.markdown(f"**📚 Grupo:** {grupo_data['codigo_grupo']}")
            st.markdown(f"**🎯 Acción:** {grupo_data.get('accion_nombre', 'Sin especificar')}")
            st.markdown(f"**⏱️ Horas:** {grupo_data.get('accion_horas', 0)}")
        
        with col_info2:
            modalidad = "Teleformación" if grupo_data.get('aula_virtual') else "Presencial"
            st.markdown(f"**🏫 Modalidad:** {modalidad}")
            st.markdown(f"**👥 Participantes:** {grupo_data.get('n_participantes_finalizados', grupo_data.get('n_participantes_previstos', 0))}")
        
        st.divider()
        
        # Cargar o crear registro de costes
        costes_res = supabase.table("grupo_costes").select("*").eq("grupo_id", grupo_id).execute()
        costes_data = costes_res.data[0] if costes_res.data else {}
        
        # 1. BLOQUE: COSTES DE FORMACIÓN
        st.markdown("### 📊 Costes de Formación")
        
        col1, col2 = st.columns(2)
        with col1:
            costes_directos = st.number_input(
                "Costes Directos (€)", 
                value=float(costes_data.get('costes_directos', 0)),
                min_value=0.0,
                format="%.2f",
                help="Costes directos de la formación"
            )
            costes_indirectos = st.number_input(
                "Costes Indirectos (€)", 
                value=float(costes_data.get('costes_indirectos', 0)),
                min_value=0.0,
                format="%.2f",
                help="Costes indirectos asociados"
            )
        
        with col2:
            costes_organizacion = st.number_input(
                "Costes de Organización (€)", 
                value=float(costes_data.get('costes_organizacion', 0)),
                min_value=0.0,
                format="%.2f",
                help="Costes de organización del curso"
            )
            
            # Total automático (readonly)
            total_costes = costes_directos + costes_indirectos + costes_organizacion
            st.markdown(f"**💰 Total Costes Formación:** {total_costes:.2f} €")
        
        st.divider()
        
        # 2. BLOQUE: LÍMITES DE COSTES FUNDAE
        st.markdown("### 📏 Límites de Costes FUNDAE")
        
        horas = grupo_data.get('accion_horas', 0)
        participantes = grupo_data.get('n_participantes_finalizados', grupo_data.get('n_participantes_previstos', 0))
        
        # Cálculo automático según modalidad
        tarifa_hora = 7.5 if modalidad == "Teleformación" else 13.0
        limite_maximo = tarifa_hora * horas * participantes
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**💡 Tarifa por hora:** {tarifa_hora} € ({modalidad})")
            st.info(f"**⏱️ Horas totales:** {horas}")
            st.info(f"**👥 Participantes:** {participantes}")
        
        with col2:
            st.success(f"**🎯 Límite Máximo Bonificación:** {limite_maximo:.2f} €")
            
            # Comparación con costes reales
            if total_costes > limite_maximo:
                diferencia = total_costes - limite_maximo
                st.error(f"⚠️ Exceso sobre límite: {diferencia:.2f} €")
            else:
                margen = limite_maximo - total_costes
                st.success(f"✅ Margen disponible: {margen:.2f} €")
        
        st.divider()
        
        # 3. BLOQUE: COFINANCIACIÓN PRIVADA
        st.markdown("### 💼 Cofinanciación Privada")
        
        col1, col2 = st.columns(2)
        with col1:
            costes_salariales = st.number_input(
                "Costes Salariales Participantes (€)",
                value=float(costes_data.get('costes_salariales', 0)),
                min_value=0.0,
                format="%.2f",
                help="Costes salariales durante la formación"
            )
        
        with col2:
            cofinanciacion_privada = st.number_input(
                "Cofinanciación Privada (€)",
                value=float(costes_data.get('cofinanciacion_privada', 0)),
                min_value=0.0,
                format="%.2f",
                help="Aportación privada adicional"
            )
        
        st.divider()
        
        # 4. BLOQUE: BONIFICACIÓN MENSUAL
        st.markdown("### 📅 Bonificación Mensual")
        
        # Cargar bonificaciones existentes
        bonificaciones_res = supabase.table("grupo_bonificaciones").select("*").eq("grupo_id", grupo_id).execute()
        bonificaciones_existentes = bonificaciones_res.data or []
        
        # Formulario para nueva bonificación
        col1, col2, col3 = st.columns(3)
        with col1:
            mes_bonificacion = st.selectbox(
                "Mes de Bonificación",
                ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                 "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            )
        
        with col2:
            importe_bonificacion = st.number_input(
                "Importe a Bonificar (€)",
                min_value=0.0,
                max_value=limite_maximo,
                format="%.2f"
            )
        
        with col3:
            if st.button("➕ Añadir Bonificación") and mes_bonificacion and importe_bonificacion > 0:
                # Verificar que no existe ya ese mes
                mes_existe = any(b['mes'] == mes_bonificacion for b in bonificaciones_existentes)
                if mes_existe:
                    st.error(f"⚠️ Ya existe bonificación para {mes_bonificacion}")
                else:
                    supabase.table("grupo_bonificaciones").insert({
                        "grupo_id": grupo_id,
                        "mes": mes_bonificacion,
                        "importe": importe_bonificacion,
                        "created_at": datetime.utcnow().isoformat()
                    }).execute()
                    st.success(f"✅ Bonificación añadida para {mes_bonificacion}")
                    st.rerun()
        
        # Tabla de bonificaciones existentes
        if bonificaciones_existentes:
            st.markdown("**💰 Bonificaciones Programadas:**")
            
            bonif_df = pd.DataFrame(bonificaciones_existentes)
            total_bonificado = bonif_df['importe'].sum()
            
            for bonif in bonificaciones_existentes:
                col_mes, col_importe, col_accion = st.columns([2, 2, 1])
                with col_mes:
                    st.text(bonif['mes'])
                with col_importe:
                    st.text(f"{bonif['importe']:.2f} €")
                with col_accion:
                    if st.button("🗑️", key=f"del_bonif_{bonif['id']}"):
                        supabase.table("grupo_bonificaciones").delete().eq("id", bonif['id']).execute()
                        st.rerun()
            
            st.success(f"**📊 Total Bonificado:** {total_bonificado:.2f} €")
            
            if total_bonificado > limite_maximo:
                st.error(f"⚠️ Total bonificado excede el límite máximo en {total_bonificado - limite_maximo:.2f} €")
        
        st.divider()
        
        # Botón guardar costes generales
        if st.button("💾 Guardar Costes FUNDAE", type="primary"):
            datos_costes = {
                "grupo_id": grupo_id,
                "costes_directos": costes_directos,
                "costes_indirectos": costes_indirectos,
                "costes_organizacion": costes_organizacion,
                "total_costes_formacion": total_costes,
                "limite_maximo_bonificacion": limite_maximo,
                "costes_salariales": costes_salariales,
                "cofinanciacion_privada": cofinanciacion_privada,
                "modalidad": modalidad,
                "tarifa_hora": tarifa_hora,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if costes_data:
                # Actualizar existente
                supabase.table("grupo_costes").update(datos_costes).eq("grupo_id", grupo_id).execute()
            else:
                # Crear nuevo
                datos_costes["created_at"] = datetime.utcnow().isoformat()
                supabase.table("grupo_costes").insert(datos_costes).execute()
            
            st.success("✅ Costes FUNDAE guardados correctamente.")
            st.rerun()
    
    except Exception as e:
        st.error(f"❌ Error en gestión de costes FUNDAE: {e}")


def crear_grupo_completo(supabase, session_state, data_service, codigo_grupo, accion_sel, modalidad, 
                        fecha_inicio, fecha_fin_prevista, n_participantes_previstos, localidad, provincia, cp,
                        hora_manana_inicio, hora_manana_fin, hora_tarde_inicio, hora_tarde_fin,
                        dias_semana, observaciones, acciones_dict, empresas_dict):
    """Crea un grupo completo con todas las validaciones FUNDAE."""
    try:
        # Validaciones básicas
        if not codigo_grupo:
            st.error("⚠️ El código de grupo es obligatorio.")
            return
        
        if not accion_sel:
            st.error("⚠️ Debe seleccionar una acción formativa.")
            return
        
        # Verificar código único
        codigo_existe = supabase.table("grupos").select("id").eq("codigo_grupo", codigo_grupo).execute()
        if codigo_existe.data:
            st.error("⚠️ Ya existe un grupo con ese código.")
            return
        
        # Preparar datos del grupo
        datos_grupo = {
            "codigo_grupo": codigo_grupo,
            "accion_formativa_id": acciones_dict[accion_sel],
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin_prevista": fecha_fin_prevista.isoformat(),
            "n_participantes_previstos": n_participantes_previstos,
            "localidad": localidad,
            "provincia": provincia,
            "cp": cp,
            "aula_virtual": modalidad in ["Teleformación", "Mixta"],
            "observaciones": observaciones,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Gestión de empresa según rol
        if session_state.role == "admin":
            empresa_sel = st.session_state.get("empresa_sel")
            if empresa_sel and empresa_sel in empresas_dict:
                datos_grupo["empresa_id"] = empresas_dict[empresa_sel]
        elif session_state.role == "gestor":
            datos_grupo["empresa_id"] = session_state.user.get("empresa_id")
        
        # Construir horario FUNDAE
        horario_fundae = construir_horario_fundae(
            hora_manana_inicio, hora_manana_fin, hora_tarde_inicio, hora_tarde_fin, dias_semana
        )
        datos_grupo["horario"] = horario_fundae
        
        # Crear grupo
        result = supabase.table("grupos").insert(datos_grupo).execute()
        
        if result.data:
            # Limpieza completa de cache
            limpiar_cache_completo(data_service)
            
            st.success("✅ Grupo creado correctamente según estándares FUNDAE.")
            st.balloons()
            st.rerun()
        else:
            st.error("❌ Error al crear el grupo.")
    
    except Exception as e:
        st.error(f"❌ Error al crear grupo: {e}")


def construir_horario_fundae(hora_manana_inicio, hora_manana_fin, hora_tarde_inicio, hora_tarde_fin, dias_semana):
    """Construye el horario según formato FUNDAE."""
    horario_parts = []
    
    # Días seleccionados
    dias_seleccionados = [dia for dia, seleccionado in dias_semana.items() if seleccionado]
    if dias_seleccionados:
        horario_parts.append(f"Días: {', '.join(dias_seleccionados)}")
    
    # Horario mañana
    if hora_manana_inicio and hora_manana_fin:
        horario_parts.append(f"Mañana: {hora_manana_inicio.strftime('%H:%M')} - {hora_manana_fin.strftime('%H:%M')}")
    
    # Horario tarde
    if hora_tarde_inicio and hora_tarde_fin:
        horario_parts.append(f"Tarde: {hora_tarde_inicio.strftime('%H:%M')} - {hora_tarde_fin.strftime('%H:%M')}")
    
    return " | ".join(horario_parts)


def limpiar_cache_completo(data_service):
    """Limpia todo el cache del data_service."""
    try:
        data_service.get_grupos_completos.clear()
        data_service.get_participantes_completos.clear()
        data_service.get_acciones_formativas.clear()
        data_service.get_empresas.clear()
        data_service.get_empresas_con_modulos.clear()
        data_service.get_tutores_completos.clear()
    except:
        pass  # Algunos métodos pueden no existir


if __name__ == "__main__":
    # Esta función se llama desde app.py
    pass
