import streamlit as st
import pandas as pd
from datetime import datetime, time
from utils import export_csv, validar_dni_cif, get_ajustes_app
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha
import re
from typing import Dict, Any, Tuple

# =========================
# VALIDACIONES FUNDAE
# =========================

def validar_grupo_fundae(datos_grupo, tipo_xml="inicio"):
    """Valida que un grupo cumpla con los requisitos FUNDAE para generar XML."""
    errores = []
    
    # Campos obligatorios para XML de inicio
    campos_obligatorios = {
        "codigo_grupo": "Código de grupo",
        "fecha_inicio": "Fecha de inicio", 
        "fecha_fin_prevista": "Fecha fin prevista",
        "modalidad": "Modalidad",
        "horario": "Horario",
        "localidad": "Localidad",
        "n_participantes_previstos": "Participantes previstos"
    }
    
    # Verificar campos obligatorios
    for campo, nombre in campos_obligatorios.items():
        valor = datos_grupo.get(campo)
        if not valor:
            errores.append(f"{nombre} es obligatorio para FUNDAE")
    
    # Validar modalidad FUNDAE
    modalidad = datos_grupo.get("modalidad")
    if modalidad and modalidad not in ["PRESENCIAL", "TELEFORMACION", "MIXTA"]:
        errores.append("Modalidad debe ser PRESENCIAL, TELEFORMACION o MIXTA")
    
    # Validar participantes
    participantes = datos_grupo.get("n_participantes_previstos")
    if participantes:
        try:
            num_part = int(participantes)
            if num_part < 1 or num_part > 30:
                errores.append("Participantes previstos debe estar entre 1 y 30")
        except (ValueError, TypeError):
            errores.append("Participantes previstos debe ser un número")
    
    # Validar horario FUNDAE
    horario = datos_grupo.get("horario")
    if horario:
        es_valido_horario, error_horario = validar_horario_fundae(horario)
        if not es_valido_horario:
            errores.append(f"Horario: {error_horario}")
    
    # Validaciones específicas de finalización
    if tipo_xml == "finalizacion":
        campos_finalizacion = {
            "fecha_fin": "Fecha de finalización real",
            "n_participantes_finalizados": "Participantes finalizados",
            "n_aptos": "Número de aptos",
            "n_no_aptos": "Número de no aptos"
        }
        
        for campo, nombre in campos_finalizacion.items():
            valor = datos_grupo.get(campo)
            if valor is None or valor == "":
                errores.append(f"{nombre} es obligatorio para finalización FUNDAE")
        
        # Validar coherencia de participantes finalizados
        try:
            finalizados = int(datos_grupo.get("n_participantes_finalizados", 0))
            aptos = int(datos_grupo.get("n_aptos", 0))
            no_aptos = int(datos_grupo.get("n_no_aptos", 0))
            
            if aptos + no_aptos != finalizados:
                errores.append("La suma de aptos + no aptos debe igual participantes finalizados")
                
            if finalizados < 0 or aptos < 0 or no_aptos < 0:
                errores.append("Los números de participantes no pueden ser negativos")
                
        except (ValueError, TypeError):
            errores.append("Los campos de participantes deben ser números enteros")
        
        # Validar fechas
        fecha_inicio = datos_grupo.get("fecha_inicio")
        fecha_fin = datos_grupo.get("fecha_fin")
        
        if fecha_inicio and fecha_fin:
            try:
                if isinstance(fecha_inicio, str):
                    inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
                else:
                    inicio = fecha_inicio
                    
                if isinstance(fecha_fin, str):
                    fin = datetime.strptime(fecha_fin, "%Y-%m-%d")
                else:
                    fin = fecha_fin
                    
                if fin < inicio:
                    errores.append("La fecha de fin no puede ser anterior a la de inicio")
            except (ValueError, TypeError):
                errores.append("Formato de fecha inválido")
    
    return len(errores) == 0, errores


def normalizar_modalidad_fundae(modalidad_input, aula_virtual=None):
    """Convierte modalidad a formato FUNDAE."""
    if modalidad_input == "Presencial":
        return "PRESENCIAL"
    elif modalidad_input == "Teleformación":
        return "TELEFORMACION"
    elif modalidad_input == "Mixta":
        return "MIXTA"
    elif modalidad_input in ["PRESENCIAL", "TELEFORMACION", "MIXTA"]:
        return modalidad_input  # Ya está en formato FUNDAE
    else:
        # Retrocompatibilidad con aula_virtual
        return "TELEFORMACION" if aula_virtual else "PRESENCIAL"


def validar_horario_fundae(horario):
    """Valida que el horario cumpla formato FUNDAE."""
    if not horario or not isinstance(horario, str):
        return False, "Horario requerido en formato FUNDAE"
    
    # Verificar que contenga días
    if "Días:" not in horario:
        return False, "Debe especificar días de la semana"
    
    # Verificar formato de horas (HH:MM)
    if not re.search(r'\d{2}:\d{2}', horario):
        return False, "Debe incluir horas en formato HH:MM"
    
    return True, ""


def mostrar_ayuda_fundae():
    """Muestra información de ayuda sobre requisitos FUNDAE."""
    with st.expander("ℹ️ Información FUNDAE"):
        st.markdown("""
        **Requisitos FUNDAE para grupos:**
        - Código único de grupo (máx. 50 caracteres)
        - Modalidad: PRESENCIAL, TELEFORMACION o MIXTA
        - Horario en formato específico con días y horas
        - Localidad obligatoria
        - Entre 1 y 30 participantes previstos
        
        **Para finalización:**
        - Fecha real de finalización
        - Participantes finalizados = Aptos + No aptos
        - Todos los números deben ser mayor o igual a 0
        """)


# =========================
# FUNCIÓN PRINCIPAL
# =========================

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
    mostrar_tabla_grupos_mejorada(df_filtered, data_service, supabase, session_state, acciones_dict, empresas_dict)

    # =========================
    # PARTE INFERIOR: SISTEMA DE TABS CORREGIDO
    # =========================
    st.divider()
    st.markdown("### 📑 Gestión Completa de Grupos")
    
    tab1, tab2, tab3 = st.tabs([
        "📝 Crear Grupo Completo", 
        "👥 Gestionar Participantes", 
        "💰 Costes FUNDAE"
    ])
    
    with tab1:
        mostrar_tab_crear_grupo_completo(supabase, session_state, data_service, acciones_dict, empresas_dict)
    
    with tab2:
        mostrar_tab_gestionar_participantes(supabase, session_state, data_service, df_grupos)
    
    with tab3:
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


def mostrar_tabla_grupos_mejorada(df_filtered, data_service, supabase, session_state, acciones_dict, empresas_dict):
    """Muestra tabla de grupos con edición mejorada incluyendo campos de finalización."""
    st.markdown("### 📊 Lista de Grupos")
    
    if df_filtered.empty:
        st.info("ℹ️ No hay grupos para mostrar.")
        return

    # Funciones CRUD mejoradas
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

            # Validaciones básicas
            if not datos_editados.get("codigo_grupo"):
                st.error("⚠️ El código de grupo es obligatorio.")
                return

            # VALIDACIÓN FUNDAE ANTES DE GUARDAR
            if datos_editados:
                # Determinar si es finalización
                tiene_campos_finalizacion = any(
                    campo in datos_editados 
                    for campo in ["fecha_fin", "n_participantes_finalizados", "n_aptos", "n_no_aptos"]
                )
                
                tipo_validacion = "finalizacion" if tiene_campos_finalizacion else "inicio"
                
                # Obtener datos actuales del grupo para validación completa
                grupo_actual = supabase.table("grupos").select("*").eq("id", grupo_id).execute()
                if grupo_actual.data:
                    datos_completos = grupo_actual.data[0].copy()
                    datos_completos.update(datos_editados)  # Aplicar cambios
                    
                    # Normalizar modalidad si es necesaria
                    if datos_completos.get("modalidad"):
                        datos_completos["modalidad"] = normalizar_modalidad_fundae(
                            datos_completos["modalidad"],
                            datos_completos.get("aula_virtual")
                        )
                    
                    # Validar con FUNDAE
                    es_valido, errores_fundae = validar_grupo_fundae(datos_completos, tipo_validacion)
                    
                    if not es_valido:
                        st.error("❌ Errores de validación FUNDAE:")
                        for error in errores_fundae:
                            st.error(f"• {error}")
                        return

            # Actualizar
            datos_editados["updated_at"] = datetime.utcnow().isoformat()
            supabase.table("grupos").update(datos_editados).eq("id", grupo_id).execute()
            
            # LIMPIEZA COMPLETA DE CACHE
            data_service.limpiar_cache_grupos()
            
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

            # Eliminar relaciones primero
            supabase.table("tutores_grupos").delete().eq("grupo_id", grupo_id).execute()
            supabase.table("empresas_grupos").delete().eq("grupo_id", grupo_id).execute()
            supabase.table("grupo_costes").delete().eq("grupo_id", grupo_id).execute()
            supabase.table("grupo_bonificaciones").delete().eq("grupo_id", grupo_id).execute()
            supabase.table("grupos").delete().eq("id", grupo_id).execute()
            
            data_service.limpiar_cache_grupos()
            st.success("✅ Grupo eliminado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al eliminar grupo: {e}")

    # Campos dinámicos según estado del grupo y requisitos FUNDAE
    def get_campos_dinamicos(datos):
        """Campos dinámicos según estado del grupo y requisitos FUNDAE."""
        campos_base = [
            "codigo_grupo", 
            "accion_sel", 
            "modalidad",  # Modalidad explícita FUNDAE
            "fecha_inicio", 
            "fecha_fin_prevista", 
            "localidad",
            "provincia",
            "cp",
            "lugar_imparticion",  # Para FUNDAE
            "n_participantes_previstos"
        ]
        
        # Si el grupo está finalizado o próximo a finalizar, añadir campos de finalización
        fecha_fin = datos.get("fecha_fin_prevista")
        hoy = datetime.now()
        
        # Mostrar campos de finalización si:
        # 1. Ya pasó la fecha prevista, O
        # 2. Falta menos de 7 días para la fecha prevista
        if fecha_fin:
            try:
                fecha_fin_dt = pd.to_datetime(fecha_fin, errors="coerce")
                if pd.notna(fecha_fin_dt):
                    dias_para_fin = (fecha_fin_dt - hoy).days
                    
                    if dias_para_fin <= 7:  # Si falta una semana o menos
                        campos_base.extend([
                            "fecha_fin",  # Fecha REAL de finalización
                            "n_participantes_finalizados", 
                            "n_aptos", 
                            "n_no_aptos"
                        ])
            except:
                pass  # Si hay error en la fecha, no mostrar campos adicionales
        
        return campos_base

    campos_select = {
        "accion_sel": list(acciones_dict.keys()) if acciones_dict else ["No hay acciones disponibles"],
        "modalidad": ["PRESENCIAL", "TELEFORMACION", "MIXTA"]  # Modalidades FUNDAE
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

    # Columnas visibles dinámicas
    columnas_base = ["codigo_grupo", "accion_nombre", "modalidad", "fecha_inicio", "fecha_fin_prevista", "localidad"]
    if session_state.role == "admin":
        columnas_base.insert(2, "empresa_nombre")

    # Mostrar tabla con edición
    listado_con_ficha(
        df=df_display,
        columnas_visibles=[col for col in columnas_base if col in df_display.columns],
        titulo="Grupo",
        on_save=guardar_grupo,
        on_create=None,  # Creación se hace en tab 1
        on_delete=eliminar_grupo if session_state.role == "admin" else None,
        id_col="id",
        campos_select=campos_select,
        campos_dinamicos=get_campos_dinamicos,
        allow_creation=False,
        search_columns=["codigo_grupo", "accion_nombre"]
    )


def mostrar_tab_crear_grupo_completo(supabase, session_state, data_service, acciones_dict, empresas_dict):
    """Tab 1: Crear grupo completo con tutores y empresas."""
    st.markdown("#### 📝 Crear Grupo Completo")
    st.caption("Crea un grupo con toda la información necesaria: datos básicos, tutores y empresas participantes.")
    
    # Mostrar ayuda FUNDAE
    mostrar_ayuda_fundae()
    
    # Cargar datos necesarios
    try:
        df_tutores = data_service.get_tutores_completos()
        df_participantes = data_service.get_participantes_completos()
    except Exception as e:
        st.error(f"❌ Error al cargar tutores/participantes: {e}")
        return
    
    with st.form("crear_grupo_completo"):
        # === SECCIÓN 1: DATOS BÁSICOS ===
        st.markdown("### 📋 Información Básica del Grupo")
        
        col1, col2 = st.columns(2)
        
        with col1:
            codigo_grupo = st.text_input("Código de Grupo *", help="Código único identificativo (máx. 50 caracteres)")
            
            accion_sel = st.selectbox(
                "Acción Formativa *", 
                options=[""] + list(acciones_dict.keys()),
                help="Selecciona la acción formativa"
            )
            
            # Mostrar duración automática
            if accion_sel and accion_sel in acciones_dict:
                df_acciones = data_service.get_acciones_formativas()
                accion_data = df_acciones[df_acciones["nombre"] == accion_sel]
                if not accion_data.empty:
                    horas = accion_data.iloc[0].get("num_horas", 0)
                    st.info(f"⏱️ Duración: {horas} horas")
            
            modalidad = st.selectbox("Modalidad *", ["Presencial", "Teleformación", "Mixta"])
            localidad = st.text_input("Localidad *", help="Obligatorio para FUNDAE")
            provincia = st.text_input("Provincia")
            cp = st.text_input("Código Postal")
            lugar_imparticion = st.text_area("Lugar de Impartición", help="Dirección completa del lugar de formación")
        
        with col2:
            fecha_inicio = st.date_input("Fecha de Inicio *")
            fecha_fin_prevista = st.date_input("Fecha Fin Prevista *")
            
            n_participantes_previstos = st.number_input(
                "Participantes Previstos *", 
                min_value=1, 
                max_value=30, 
                value=10,
                help="Entre 1 y 30 participantes (requisito FUNDAE)"
            )
            
            # Empresa (solo para admin)
            if session_state.role == "admin":
                empresa_sel = st.selectbox(
                    "Empresa Propietaria *",
                    options=[""] + list(empresas_dict.keys()),
                    help="Empresa que organiza el grupo"
                )
        
        # === SECCIÓN 2: HORARIOS CORREGIDOS ===
        st.markdown("### 🕐 Horarios de Impartición")
        
        # Opción de horario
        tipo_horario = st.radio(
            "Tipo de horario:",
            ["Solo Mañana", "Solo Tarde", "Mañana y Tarde"],
            horizontal=True
        )
        
        horario_parts = []
        
        # Horarios dinámicos
        if tipo_horario in ["Solo Mañana", "Mañana y Tarde"]:
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                hora_manana_inicio = st.time_input("Mañana - Inicio", value=time(9, 0))
            with col_m2:
                hora_manana_fin = st.time_input("Mañana - Fin", value=time(13, 0))
            horario_parts.append(f"Mañana: {hora_manana_inicio.strftime('%H:%M')} - {hora_manana_fin.strftime('%H:%M')}")
        
        if tipo_horario in ["Solo Tarde", "Mañana y Tarde"]:
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                hora_tarde_inicio = st.time_input("Tarde - Inicio", value=time(15, 0))
            with col_t2:
                hora_tarde_fin = st.time_input("Tarde - Fin", value=time(19, 0))
            horario_parts.append(f"Tarde: {hora_tarde_inicio.strftime('%H:%M')} - {hora_tarde_fin.strftime('%H:%M')}")
        
        # Días de la semana
        st.markdown("**📅 Días de Impartición**")
        dias_cols = st.columns(7)
        dias_semana = {}
        dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        
        for i, dia in enumerate(dias_nombres):
            with dias_cols[i]:
                dias_semana[dia] = st.checkbox(dia, value=(i < 5))  # L-V por defecto
        
        # === SECCIÓN 3: TUTORES ===
        st.markdown("### 👨‍🏫 Asignación de Tutores")
        
        tutores_disponibles = df_tutores["nombre_completo"].tolist() if not df_tutores.empty else []
        tutores_seleccionados = st.multiselect(
            "Seleccionar Tutores *",
            options=tutores_disponibles,
            help="Al menos un tutor es obligatorio"
        )
        
        # === SECCIÓN 4: EMPRESAS PARTICIPANTES ===
        if session_state.role == "admin":
            st.markdown("### 🏢 Empresas Participantes")
            
            empresas_participantes = st.multiselect(
                "Empresas del Grupo",
                options=list(empresas_dict.keys()),
                help="Empresas cuyos trabajadores participan en el grupo"
            )
        
        # === BOTÓN DE CREACIÓN ===
        submitted = st.form_submit_button("🎯 Crear Grupo Completo", use_container_width=True)
        
        if submitted:
            # Validaciones previas
            errores = []
            
            if not codigo_grupo:
                errores.append("El código de grupo es obligatorio")
            
            if not accion_sel:
                errores.append("Debes seleccionar una acción formativa")
            
            if not localidad:
                errores.append("La localidad es obligatoria para FUNDAE")
            
            if not tutores_seleccionados:
                errores.append("Debes asignar al menos un tutor")
            
            if session_state.role == "admin" and not empresa_sel:
                errores.append("Debes seleccionar una empresa propietaria")
            
            if fecha_inicio >= fecha_fin_prevista:
                errores.append("La fecha de fin debe ser posterior a la de inicio")
            
            # Verificar código único
            codigo_existe = supabase.table("grupos").select("id").eq("codigo_grupo", codigo_grupo).execute()
            if codigo_existe.data:
                errores.append("Ya existe un grupo con ese código")
            
            if errores:
                for error in errores:
                    st.error(f"⚠️ {error}")
                return
            
            # Construcción del horario FUNDAE
            dias_seleccionados = [dia for dia, seleccionado in dias_semana.items() if seleccionado]
            if not dias_seleccionados:
                st.error("⚠️ Debes seleccionar al menos un día de la semana")
                return
            
            horario_completo = f"Días: {', '.join(dias_seleccionados)} | {' | '.join(horario_parts)}"
            
            # Preparar datos del grupo
            modalidad_fundae = normalizar_modalidad_fundae(modalidad)
            
            datos_grupo = {
                "codigo_grupo": codigo_grupo,
                "accion_formativa_id": acciones_dict[accion_sel],
                "modalidad": modalidad_fundae,
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin_prevista": fecha_fin_prevista.isoformat(),
                "localidad": localidad,
                "provincia": provincia,
                "cp": cp,
                "lugar_imparticion": lugar_imparticion,
                "n_participantes_previstos": n_participantes_previstos,
                "horario": horario_completo,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Asignar empresa
            if session_state.role == "admin":
                datos_grupo["empresa_id"] = empresas_dict[empresa_sel]
            else:
                datos_grupo["empresa_id"] = session_state.user.get("empresa_id")
            
            # VALIDACIÓN FUNDAE ANTES DE CREAR
            es_valido, errores_fundae = validar_grupo_fundae(datos_grupo, "inicio")
            
            if not es_valido:
                st.error("❌ Errores de validación FUNDAE:")
                for error in errores_fundae:
                    st.error(f"• {error}")
                return
            
            try:
                # Crear grupo
                resultado = supabase.table("grupos").insert(datos_grupo).execute()
                
                if resultado.data:
                    grupo_id = resultado.data[0]["id"]
                    
                    # Asignar tutores
                    tutores_dict = {row["nombre_completo"]: row["id"] for _, row in df_tutores.iterrows()}
                    
                    for tutor_nombre in tutores_seleccionados:
                        if tutor_nombre in tutores_dict:
                            supabase.table("tutores_grupos").insert({
                                "tutor_id": tutores_dict[tutor_nombre],
                                "grupo_id": grupo_id,
                                "fecha_asignacion": datetime.utcnow().isoformat()
                            }).execute()
                    
                    # Asignar empresas participantes (solo admin)
                    if session_state.role == "admin" and empresas_participantes:
                        for empresa_nombre in empresas_participantes:
                            if empresa_nombre in empresas_dict:
                                supabase.table("empresas_grupos").insert({
                                    "empresa_id": empresas_dict[empresa_nombre],
                                    "grupo_id": grupo_id,
                                    "fecha_asignacion": datetime.utcnow().isoformat()
                                }).execute()
                    
                    # Limpiar cache
                    data_service.limpiar_cache_grupos()
                    
                    st.success("✅ Grupo creado exitosamente con todos sus componentes.")
                    st.balloons()
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Error al crear el grupo: {e}")


def mostrar_tab_gestionar_participantes(supabase, session_state, data_service, df_grupos):
    """Tab 2: Gestionar participantes de grupos existentes."""
    st.markdown("#### 👥 Gestionar Participantes")
    st.caption("Asigna o desasigna participantes a grupos ya creados.")
    
    if df_grupos.empty:
        st.info("ℹ️ No hay grupos disponibles. Crea un grupo primero en la pestaña anterior.")
        return
    
    # Selector de grupo
    opciones_grupos = {
        f"{row['codigo_grupo']} - {row.get('accion_nombre', 'Sin acción')}": row['id']
        for _, row in df_grupos.iterrows()
    }
    
    grupo_seleccionado = st.selectbox(
        "Seleccionar Grupo:",
        options=[""] + list(opciones_grupos.keys()),
        help="Escoge el grupo al que quieres gestionar participantes"
    )
    
    if not grupo_seleccionado:
        return
    
    grupo_id = opciones_grupos[grupo_seleccionado]
    
    # Obtener información del grupo seleccionado
    grupo_info = df_grupos[df_grupos["id"] == grupo_id].iloc[0]
    
    # Mostrar info del grupo
    with st.expander("ℹ️ Información del Grupo", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Código:** {grupo_info.get('codigo_grupo', '')}")
            st.write(f"**Modalidad:** {grupo_info.get('modalidad', '')}")
        with col2:
            st.write(f"**Fecha Inicio:** {grupo_info.get('fecha_inicio', '')}")
            st.write(f"**Participantes Previstos:** {grupo_info.get('n_participantes_previstos', 0)}")
        with col3:
            st.write(f"**Localidad:** {grupo_info.get('localidad', '')}")
            st.write(f"**Acción:** {grupo_info.get('accion_nombre', 'No asignada')}")
    
    # Obtener participantes actuales del grupo
    try:
        participantes_grupo = supabase.table("participantes_grupos")\
            .select("*, participantes(*)")\
            .eq("grupo_id", grupo_id)\
            .execute()
        
        df_participantes_grupo = pd.DataFrame(participantes_grupo.data) if participantes_grupo.data else pd.DataFrame()
        
        # Obtener todos los participantes disponibles
        if session_state.role == "gestor":
            todos_participantes = supabase.table("participantes")\
                .select("*")\
                .eq("empresa_id", session_state.user.get("empresa_id"))\
                .execute()
        else:
            todos_participantes = supabase.table("participantes")\
                .select("*")\
                .execute()
                
        df_todos_participantes = pd.DataFrame(todos_participantes.data) if todos_participantes.data else pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Error al cargar participantes: {e}")
        return
    
    # === SECCIÓN: PARTICIPANTES ACTUALES ===
    st.markdown("### 👤 Participantes Actuales del Grupo")
    
    if not df_participantes_grupo.empty:
        # Preparar datos para mostrar
        participantes_display = []
        for _, row in df_participantes_grupo.iterrows():
            participante = row["participantes"]
            if participante:
                participantes_display.append({
                    "id": row["id"],
                    "dni": participante.get("dni", ""),
                    "nombre": participante.get("nombre", ""),
                    "apellidos": participante.get("apellidos", ""),
                    "email": participante.get("email", ""),
                    "fecha_asignacion": row.get("fecha_asignacion", "")
                })
        
        if participantes_display:
            df_display = pd.DataFrame(participantes_display)
            st.dataframe(df_display, use_container_width=True)
            
            # Botón para desasignar participantes
            if st.button("🗑️ Desasignar Participantes Seleccionados"):
                # Por simplicidad, se puede implementar multiselect aquí
                participantes_a_desasignar = st.multiselect(
                    "Selecciona participantes a desasignar:",
                    options=[f"{p['dni']} - {p['nombre']} {p['apellidos']}" for p in participantes_display],
                    key="desasignar_participantes"
                )
                
                if participantes_a_desasignar and st.button("Confirmar Desasignación", type="primary"):
                    try:
                        for participante_str in participantes_a_desasignar:
                            dni = participante_str.split(" - ")[0]
                            # Buscar el registro en participantes_grupos
                            for p in participantes_display:
                                if p["dni"] == dni:
                                    supabase.table("participantes_grupos").delete().eq("id", p["id"]).execute()
                                    break
                        
                        st.success("✅ Participantes desasignados correctamente.")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error al desasignar participantes: {e}")
        else:
            st.info("ℹ️ No hay participantes asignados a este grupo.")
    else:
        st.info("ℹ️ No hay participantes asignados a este grupo.")
    
    # === SECCIÓN: ASIGNAR NUEVOS PARTICIPANTES ===
    st.markdown("### ➕ Asignar Nuevos Participantes")
    
    # Método 1: Selección individual
    with st.expander("📋 Selección Individual", expanded=False):
        if not df_todos_participantes.empty:
            # Filtrar participantes ya asignados
            dnis_asignados = set()
            if not df_participantes_grupo.empty:
                for _, row in df_participantes_grupo.iterrows():
                    participante = row["participantes"]
                    if participante:
                        dnis_asignados.add(participante.get("dni", ""))
            
            participantes_disponibles = df_todos_participantes[
                ~df_todos_participantes["dni"].isin(dnis_asignados)
            ]
            
            if not participantes_disponibles.empty:
                opciones_participantes = {
                    f"{row['dni']} - {row['nombre']} {row['apellidos']}": row['id']
                    for _, row in participantes_disponibles.iterrows()
                }
                
                participantes_seleccionados = st.multiselect(
                    "Seleccionar Participantes:",
                    options=list(opciones_participantes.keys()),
                    help="Puedes seleccionar múltiples participantes"
                )
                
                if participantes_seleccionados and st.button("➕ Asignar Participantes", type="primary"):
                    try:
                        asignaciones_exitosas = 0
                        for participante_str in participantes_seleccionados:
                            participante_id = opciones_participantes[participante_str]
                            
                            supabase.table("participantes_grupos").insert({
                                "participante_id": participante_id,
                                "grupo_id": grupo_id,
                                "fecha_asignacion": datetime.utcnow().isoformat()
                            }).execute()
                            
                            asignaciones_exitosas += 1
                        
                        st.success(f"✅ Se han asignado {asignaciones_exitosas} participantes al grupo.")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error al asignar participantes: {e}")
            else:
                st.info("ℹ️ No hay participantes disponibles para asignar.")
        else:
            st.info("ℹ️ No hay participantes disponibles en el sistema.")
    
    # Método 2: Importación por Excel
    with st.expander("📊 Importación Masiva por Excel", expanded=False):
        st.markdown("**Instrucciones:**")
        st.markdown("1. Sube un archivo Excel (.xlsx) con una columna llamada 'dni'")
        st.markdown("2. El sistema buscará automáticamente los participantes por DNI")
        st.markdown("3. Solo se asignarán los participantes que existan en el sistema")
        
        uploaded_file = st.file_uploader("Subir archivo Excel", type=["xlsx"], key="excel_participantes")
        
        if uploaded_file:
            try:
                df_import = pd.read_excel(uploaded_file)
                
                # Verificar que existe columna dni
                if "dni" not in df_import.columns:
                    st.error("⚠️ El archivo debe contener una columna llamada 'dni'")
                else:
                    # Mostrar preview
                    st.markdown("**Vista previa del archivo:**")
                    st.dataframe(df_import.head(), use_container_width=True)
                    
                    if st.button("🚀 Procesar Archivo Excel", type="primary"):
                        # Procesar DNIs
                        dnis_import = [str(d).strip() for d in df_import["dni"] if pd.notna(d)]
                        dnis_validos = [d for d in dnis_import if validar_dni_cif(d)]
                        dnis_invalidos = set(dnis_import) - set(dnis_validos)

                        if dnis_invalidos:
                            st.warning(f"⚠️ DNIs inválidos detectados: {', '.join(dnis_invalidos)}")

                        # Buscar participantes existentes
                        if session_state.role == "gestor":
                            part_res = supabase.table("participantes")\
                                .select("id, dni")\
                                .eq("empresa_id", session_state.user.get("empresa_id"))\
                                .execute()
                        else:
                            part_res = supabase.table("participantes")\
                                .select("id, dni")\
                                .execute()
                        
                        participantes_existentes = {p["dni"]: p["id"] for p in (part_res.data or [])}

                        # Verificar asignaciones existentes
                        ya_asignados_res = supabase.table("participantes_grupos")\
                            .select("participante_id")\
                            .eq("grupo_id", grupo_id)\
                            .execute()
                        ya_asignados_ids = {p["participante_id"] for p in (ya_asignados_res.data or [])}

                        # Procesar asignaciones
                        creados = 0
                        errores = []

                        for dni in dnis_validos:
                            participante_id = participantes_existentes.get(dni)
                            
                            if not participante_id:
                                errores.append(f"DNI {dni} no encontrado en participantes")
                                continue
                                
                            if participante_id in ya_asignados_ids:
                                errores.append(f"DNI {dni} ya asignado al grupo")
                                continue
                                
                            try:
                                supabase.table("participantes_grupos").insert({
                                    "participante_id": participante_id,
                                    "grupo_id": grupo_id,
                                    "fecha_asignacion": datetime.utcnow().isoformat()
                                }).execute()
                                creados += 1
                            except Exception as e:
                                errores.append(f"DNI {dni} - Error: {str(e)}")

                        # Mostrar resultados
                        if creados > 0:
                            st.success(f"✅ Se han asignado {creados} participantes al grupo.")
                            
                        if errores:
                            st.warning(f"⚠️ Se encontraron {len(errores)} errores:")
                            for error in errores[:10]:  # Mostrar máximo 10 errores
                                st.warning(f"• {error}")
                        
                        if creados > 0:
                            st.rerun()
                            
            except Exception as e:
                st.error(f"❌ Error al procesar archivo: {e}")


def mostrar_tab_costes_fundae(supabase, session_state, data_service, df_grupos):
    """Tab 3: Gestión de costes FUNDAE para planificación y grupos finalizados."""
    st.markdown("#### 💰 Costes FUNDAE")
    st.caption("Gestiona los costes directos e indirectos para planificación de bonificaciones FUNDAE.")
    
    if df_grupos.empty:
        st.info("ℹ️ No hay grupos disponibles.")
        return
    
    # Selector de grupo
    opciones_grupos = {
        f"{row['codigo_grupo']} - {row.get('accion_nombre', 'Sin acción')}": row['id']
        for _, row in df_grupos.iterrows()
    }
    
    grupo_seleccionado = st.selectbox(
        "Seleccionar Grupo:",
        options=[""] + list(opciones_grupos.keys()),
        help="Escoge el grupo para gestionar sus costes FUNDAE",
        key="costes_grupo_selector"
    )
    
    if not grupo_seleccionado:
        return
    
    grupo_id = opciones_grupos[grupo_seleccionado]
    grupo_info = df_grupos[df_grupos["id"] == grupo_id].iloc[0]
    
    # Mostrar información del grupo
    with st.expander("ℹ️ Información del Grupo", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Código:** {grupo_info.get('codigo_grupo', '')}")
            st.write(f"**Participantes Previstos:** {grupo_info.get('n_participantes_previstos', 0)}")
        with col2:
            st.write(f"**Fecha Inicio:** {grupo_info.get('fecha_inicio', '')}")
            st.write(f"**Fecha Fin Prevista:** {grupo_info.get('fecha_fin_prevista', '')}")
        with col3:
            st.write(f"**Modalidad:** {grupo_info.get('modalidad', '')}")
            st.write(f"**Localidad:** {grupo_info.get('localidad', '')}")
    
    # Obtener costes actuales
    try:
        costes_actuales = supabase.table("grupo_costes")\
            .select("*")\
            .eq("grupo_id", grupo_id)\
            .execute()
        
        df_costes = pd.DataFrame(costes_actuales.data) if costes_actuales.data else pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Error al cargar costes: {e}")
        return
    
    # === FORMULARIO DE COSTES ===
    st.markdown("### 💵 Gestión de Costes")
    
    with st.form("costes_fundae_form"):
        col1, col2 = st.columns(2)
        
        # Valores por defecto si ya existen costes
        costes_directos_default = 0.0
        costes_indirectos_default = 0.0
        observaciones_default = ""
        
        if not df_costes.empty:
            ultimo_coste = df_costes.iloc[-1]  # Tomar el más reciente
            costes_directos_default = float(ultimo_coste.get("costes_directos", 0))
            costes_indirectos_default = float(ultimo_coste.get("costes_indirectos", 0))
            observaciones_default = ultimo_coste.get("observaciones", "")
        
        with col1:
            costes_directos = st.number_input(
                "Costes Directos (€)", 
                value=costes_directos_default,
                min_value=0.0,
                help="Costes directamente imputables al grupo (salarios formadores, material, etc.)"
            )
            
            costes_indirectos = st.number_input(
                "Costes Indirectos (€)", 
                value=costes_indirectos_default,
                min_value=0.0,
                help="Costes indirectos según criterios FUNDAE (máx. 30% de directos)"
            )
        
        with col2:
            # Calcular total automáticamente
            total_costes = costes_directos + costes_indirectos
            
            st.metric("💰 Total Costes", f"{total_costes:,.2f} €")
            
            # Validación del 30% para indirectos
            if costes_directos > 0:
                porcentaje_indirectos = (costes_indirectos / costes_directos) * 100
                
                if porcentaje_indirectos > 30:
                    st.error(f"⚠️ Costes indirectos ({porcentaje_indirectos:.1f}%) superan el 30% permitido por FUNDAE")
                else:
                    st.success(f"✅ Costes indirectos dentro del límite ({porcentaje_indirectos:.1f}%)")
        
        observaciones = st.text_area(
            "Observaciones",
            value=observaciones_default,
            help="Detalles adicionales sobre los costes del grupo"
        )
        
        # Botón de guardado
        guardar_costes = st.form_submit_button("💾 Guardar Costes", use_container_width=True)
        
        if guardar_costes:
            # Validaciones
            if costes_directos < 0 or costes_indirectos < 0:
                st.error("⚠️ Los costes no pueden ser negativos.")
                return
            
            if costes_directos > 0 and (costes_indirectos / costes_directos) > 0.30:
                st.error("⚠️ Los costes indirectos no pueden superar el 30% de los directos según normativa FUNDAE.")
                return
            
            try:
                # Insertar nuevo registro de costes
                datos_costes = {
                    "grupo_id": grupo_id,
                    "costes_directos": costes_directos,
                    "costes_indirectos": costes_indirectos,
                    "total_costes": total_costes,
                    "observaciones": observaciones,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                supabase.table("grupo_costes").insert(datos_costes).execute()
                
                st.success("✅ Costes guardados correctamente.")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error al guardar costes: {e}")
    
    # === HISTORIAL DE COSTES ===
    if not df_costes.empty:
        st.markdown("### 📊 Historial de Costes")
        
        # Ordenar por fecha de creación descendente
        df_costes_display = df_costes.sort_values("created_at", ascending=False)
        
        # Formatear para mostrar
        df_costes_display["Fecha"] = pd.to_datetime(df_costes_display["created_at"]).dt.strftime("%d/%m/%Y %H:%M")
        df_costes_display["Costes Directos"] = df_costes_display["costes_directos"].apply(lambda x: f"{float(x):,.2f} €")
        df_costes_display["Costes Indirectos"] = df_costes_display["costes_indirectos"].apply(lambda x: f"{float(x):,.2f} €")
        df_costes_display["Total"] = df_costes_display["total_costes"].apply(lambda x: f"{float(x):,.2f} €")
        
        columnas_mostrar = ["Fecha", "Costes Directos", "Costes Indirectos", "Total", "observaciones"]
        st.dataframe(
            df_costes_display[columnas_mostrar],
            use_container_width=True,
            hide_index=True
        )
        
        # Exportar historial
        export_csv(df_costes_display[columnas_mostrar], filename=f"costes_grupo_{grupo_info.get('codigo_grupo', 'sin_codigo')}.csv")
    
    # === INFORMACIÓN ADICIONAL ===
    with st.expander("ℹ️ Información sobre Costes FUNDAE"):
        st.markdown("""
        **Costes Directos FUNDAE:**
        - Salarios y seguros sociales del personal formador
        - Material didáctico y fungible
        - Gastos de desplazamiento del personal formador
        - Costes de certificaciones oficiales
        
        **Costes Indirectos FUNDAE:**
        - Máximo 30% de los costes directos
        - Gastos generales de estructura
        - Amortización de equipos
        - Servicios generales (luz, agua, etc.)
        
        **Importante:**
        - Los costes deben estar debidamente justificados
        - Conservar toda la documentación justificativa
        - Los costes indirectos tienen límite del 30%
        """)
