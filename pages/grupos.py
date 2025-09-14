import streamlit as st
import pandas as pd
from datetime import datetime
from utils import export_csv, validar_dni_cif, get_ajustes_app
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.title("👥 Gestión de Grupos")
    st.caption("Creación y administración de grupos formativos.")

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
    # Métricas rápidas
    # =========================
    if not df_grupos.empty:
        col1, col2, col3, col4 = st.columns(4)
        hoy = datetime.now()
        activos = len(df_grupos[
            (pd.to_datetime(df_grupos["fecha_inicio"], errors="coerce") <= hoy) & 
            (df_grupos["fecha_fin"].isna() | (pd.to_datetime(df_grupos["fecha_fin"], errors="coerce") >= hoy))
        ])
        proximos = len(df_grupos[pd.to_datetime(df_grupos["fecha_inicio"], errors="coerce") > hoy])
        promedio = df_grupos["n_participantes_previstos"].mean() if "n_participantes_previstos" in df_grupos.columns else 0
        
        col1.metric("👥 Total Grupos", len(df_grupos))
        col2.metric("🟢 Activos", activos)
        col3.metric("📊 Promedio Participantes", round(promedio, 1))
        col4.metric("📅 Próximos", proximos)

    # =========================
    # Filtros de búsqueda
    # =========================
    st.divider()
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
        if estado_filter == "Activos":
            df_filtered = df_filtered[
                (pd.to_datetime(df_filtered["fecha_inicio"], errors="coerce") <= hoy) & 
                (df_filtered["fecha_fin"].isna() | (pd.to_datetime(df_filtered["fecha_fin"], errors="coerce") >= hoy))
            ]
        elif estado_filter == "Finalizados":
            df_filtered = df_filtered[
                pd.to_datetime(df_filtered["fecha_fin"], errors="coerce") < hoy
            ]
        elif estado_filter == "Próximos":
            df_filtered = df_filtered[
                pd.to_datetime(df_filtered["fecha_inicio"], errors="coerce") > hoy
            ]

    if not df_filtered.empty:
        export_csv(df_filtered, filename="grupos.csv")

    st.divider()

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_grupo(grupo_id, datos_editados):
        try:
            if "accion_sel" in datos_editados:
                accion_sel = datos_editados.pop("accion_sel")
                if accion_sel in acciones_dict:
                    datos_editados["accion_formativa_id"] = acciones_dict[accion_sel]

            if session_state.role == "admin" and "empresa_sel" in datos_editados:
                empresa_sel = datos_editados.pop("empresa_sel")
                if empresa_sel in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[empresa_sel]

            if not datos_editados.get("codigo_grupo"):
                st.error("⚠️ El código de grupo es obligatorio.")
                return

            datos_editados["updated_at"] = datetime.utcnow().isoformat()
            supabase.table("grupos").update(datos_editados).eq("id", grupo_id).execute()
            
            # LIMPIEZA DE CACHE CORREGIDA
            data_service.get_grupos_completos.clear()
            data_service.get_participantes_completos.clear()
            
            st.success("✅ Grupo actualizado correctamente.")
            st.rerun()
                
        except Exception as e:
            st.error(f"❌ Error al actualizar grupo: {e}")

    def crear_grupo(datos_nuevos):
        try:
            if "accion_sel" in datos_nuevos:
                accion_sel = datos_nuevos.pop("accion_sel")
                if accion_sel in acciones_dict:
                    datos_nuevos["accion_formativa_id"] = acciones_dict[accion_sel]

            if session_state.role == "admin" and "empresa_sel" in datos_nuevos:
                empresa_sel = datos_nuevos.pop("empresa_sel")
                if empresa_sel in empresas_dict:
                    datos_nuevos["empresa_id"] = empresas_dict[empresa_sel]
            elif session_state.role == "gestor":
                datos_nuevos["empresa_id"] = session_state.user.get("empresa_id")

            if not datos_nuevos.get("codigo_grupo"):
                st.error("⚠️ El código de grupo es obligatorio.")
                return

            codigo_existe = supabase.table("grupos").select("id").eq("codigo_grupo", datos_nuevos["codigo_grupo"]).execute()
            if codigo_existe.data:
                st.error("⚠️ Ya existe un grupo con ese código.")
                return

            datos_nuevos["created_at"] = datetime.utcnow().isoformat()
            result = supabase.table("grupos").insert(datos_nuevos).execute()
            
            if result.data:
                # LIMPIEZA DE CACHE CORREGIDA
                data_service.get_grupos_completos.clear()
                data_service.get_participantes_completos.clear()
                
                st.success("✅ Grupo creado correctamente.")
                st.rerun()
            else:
                st.error("❌ Error al crear el grupo.")
                
        except Exception as e:
            st.error(f"❌ Error al crear grupo: {e}")

    def eliminar_grupo(grupo_id):
        try:
            participantes = supabase.table("participantes").select("id").eq("grupo_id", grupo_id).execute()
            if participantes.data:
                st.error("⚠️ No se puede eliminar. El grupo tiene participantes asignados.")
                return

            supabase.table("grupos").delete().eq("id", grupo_id).execute()
            
            # LIMPIEZA DE CACHE CORREGIDA
            data_service.get_grupos_completos.clear()
            data_service.get_participantes_completos.clear()
            
            st.success("✅ Grupo eliminado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al eliminar grupo: {e}")

    # =========================
    # Campos dinámicos adaptativos (creación + finalización)
    # =========================
    def get_campos_dinamicos(datos):
        campos = [
            "codigo_grupo", "accion_sel", "fecha_inicio", "fecha_fin_prevista",
            "aula_virtual", "horario", "localidad", "provincia", "cp",
            "n_participantes_previstos", "observaciones"
        ]
        if session_state.role == "admin":
            campos.insert(2, "empresa_sel")

        # Mostrar campos de finalización si fecha_fin_prevista <= hoy o fecha_fin ya existe
        hoy = datetime.now()
        fecha_fin_prevista = pd.to_datetime(datos.get("fecha_fin_prevista"), errors="coerce")
        if (fecha_fin_prevista and fecha_fin_prevista <= hoy) or datos.get("fecha_fin"):
            campos += ["fecha_fin", "n_participantes_finalizados", "n_aptos", "n_no_aptos"]

        return campos

    campos_select = {
        "accion_sel": list(acciones_dict.keys()) if acciones_dict else ["No hay acciones disponibles"],
        "aula_virtual": [True, False]
    }
    if session_state.role == "admin" and empresas_dict:
        campos_select["empresa_sel"] = list(empresas_dict.keys())

    campos_textarea = {"observaciones": {"label": "Observaciones del grupo"}}

    campos_help = {
        "codigo_grupo": "Código único identificativo del grupo",
        "accion_sel": "Acción formativa que se impartirá",
        "empresa_sel": "Empresa a la que pertenece el grupo",
        "fecha_inicio": "Fecha de inicio de la formación",
        "fecha_fin": "Fecha de fin real",
        "fecha_fin_prevista": "Fecha prevista de finalización",
        "aula_virtual": "Indica si se imparte en aula virtual",
        "horario": "Horario de impartición",
        "localidad": "Ciudad donde se impartirá",
        "provincia": "Provincia donde se imparte",
        "cp": "Código postal",
        "n_participantes_previstos": "Número estimado de participantes",
        "n_participantes_finalizados": "Número de participantes que finalizaron",
        "n_aptos": "Número de participantes aptos",
        "n_no_aptos": "Número de participantes no aptos"
    }

    campos_obligatorios = ["codigo_grupo"]
    campos_readonly = ["id", "created_at"]

    columnas_base = ["codigo_grupo", "fecha_inicio", "fecha_fin_prevista", "localidad", "n_participantes_previstos"]
    columnas_visibles = [col for col in columnas_base if col in df_grupos.columns]
    if "accion_nombre" in df_grupos.columns:
        columnas_visibles.insert(1, "accion_nombre")
    elif "accion_formativa_id" in df_grupos.columns:
        columnas_visibles.insert(1, "accion_formativa_id")
    if session_state.role == "admin":
        if "empresa_nombre" in df_grupos.columns:
            columnas_visibles.insert(2, "empresa_nombre")
        elif "empresa_id" in df_grupos.columns:
            columnas_visibles.insert(2, "empresa_id")

    # =========================
    # Mostrar interfaz principal unificada
    # =========================
    if df_filtered.empty:
        st.info("ℹ️ No hay grupos para mostrar.")
        if session_state.role in ["admin", "gestor"]:
            st.markdown("### ➕ Crear primer grupo")
    else:
        df_display = df_filtered.copy()
        if "accion_nombre" in df_display.columns:
            df_display["accion_sel"] = df_display["accion_nombre"]
        else:
            df_display["accion_sel"] = "Acción no disponible"

        if session_state.role == "admin" and empresas_dict:
            if "empresa_nombre" in df_display.columns:
                df_display["empresa_sel"] = df_display["empresa_nombre"]
            elif "empresa_id" in df_display.columns:
                empresa_nombres = {}
                for empresa_id in df_display["empresa_id"].dropna().unique():
                    empresa_nombre = next((k for k, v in empresas_dict.items() if v == empresa_id), f"Empresa {empresa_id}")
                    empresa_nombres[empresa_id] = empresa_nombre
                df_display["empresa_sel"] = df_display["empresa_id"].map(empresa_nombres).fillna("Sin empresa")
            else:
                df_display["empresa_sel"] = "Sin empresa"

        listado_con_ficha(
            df=df_display,
            columnas_visibles=columnas_visibles,
            titulo="Grupo",
            on_save=guardar_grupo,
            on_create=crear_grupo,
            on_delete=eliminar_grupo if session_state.role == "admin" else None,
            id_col="id",
            campos_select=campos_select,
            campos_textarea=campos_textarea,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=session_state.role in ["admin", "gestor"],
            campos_help=campos_help,
            campos_obligatorios=campos_obligatorios,
            search_columns=["codigo_grupo", "accion_nombre"],
            campos_readonly=campos_readonly
        )

    # =========================
    # GESTIÓN DE PARTICIPANTES
    # =========================
    if not df_grupos.empty and session_state.role in ["admin", "gestor"]:
        st.divider()
        st.markdown("### 👥 Asignar Participantes a Grupos")
        st.caption("Gestiona la asignación de participantes a grupos de forma rápida y eficiente.")
        
        try:
            # Cargar participantes según el rol
            df_participantes = data_service.get_participantes_completos()
            
            if df_participantes.empty:
                st.info("ℹ️ No hay participantes disponibles para asignar.")
            else:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 🎯 Selección de Grupo")
                    # Crear opciones de grupos con información útil
                    if not df_grupos.empty:
                        grupo_options = []
                        for _, grupo in df_grupos.iterrows():
                            accion_info = grupo.get("accion_nombre", "Sin acción")
                            fecha_inicio = ""
                            if pd.notna(grupo.get("fecha_inicio")):
                                fecha_inicio = f" - {pd.to_datetime(grupo['fecha_inicio']).strftime('%d/%m/%Y')}"
                            
                            opcion = f"{grupo['codigo_grupo']} - {accion_info}{fecha_inicio}"
                            grupo_options.append(opcion)
                        
                        grupo_sel = st.selectbox(
                            "Seleccionar grupo:",
                            options=[""] + grupo_options,
                            key="grupo_asignacion_selector"
                        )
                        
                        if grupo_sel:
                            # Encontrar el ID del grupo seleccionado
                            grupo_idx = grupo_options.index(grupo_sel)
                            grupo_id = df_grupos.iloc[grupo_idx]["id"]
                            grupo_data = df_grupos.iloc[grupo_idx]
                            
                            # Mostrar información del grupo seleccionado
                            with st.container():
                                st.markdown("**📋 Información del grupo:**")
                                st.markdown(f"**Código:** {grupo_data['codigo_grupo']}")
                                st.markdown(f"**Acción:** {grupo_data.get('accion_nombre', 'Sin especificar')}")
                                st.markdown(f"**Participantes previstos:** {grupo_data.get('n_participantes_previstos', 'No definido')}")
                                
                                # Contar participantes actuales
                                participantes_actuales = len(df_participantes[df_participantes["grupo_id"] == grupo_id])
                                st.markdown(f"**Participantes actuales:** {participantes_actuales}")
                        else:
                            grupo_id = None
                            
                with col2:
                    st.markdown("#### 👤 Selección de Participante")
                    if grupo_id:
                        # Filtrar participantes sin grupo o del grupo actual
                        participantes_disponibles = df_participantes[
                            (df_participantes["grupo_id"].isna()) | 
                            (df_participantes["grupo_id"] == grupo_id)
                        ]
                        
                        if participantes_disponibles.empty:
                            st.info("ℹ️ No hay participantes disponibles para este grupo.")
                            participante_id = None
                        else:
                            # Crear opciones de participantes
                            participante_options = []
                            for _, participante in participantes_disponibles.iterrows():
                                nombre_completo = f"{participante['nombre']} {participante.get('apellidos', '')}".strip()
                                dni_info = f" ({participante.get('dni', 'Sin DNI')})" if participante.get('dni') else ""
                                estado_grupo = ""
                                
                                if pd.notna(participante.get("grupo_id")):
                                    if participante["grupo_id"] == grupo_id:
                                        estado_grupo = " - ✅ Ya asignado"
                                    else:
                                        grupo_actual = df_grupos[df_grupos["id"] == participante["grupo_id"]]
                                        if not grupo_actual.empty:
                                            estado_grupo = f" - 📌 En: {grupo_actual.iloc[0]['codigo_grupo']}"
                                else:
                                    estado_grupo = " - 🆓 Sin grupo"
                                
                                opcion = f"{nombre_completo}{dni_info}{estado_grupo}"
                                participante_options.append(opcion)
                            
                            participante_sel = st.selectbox(
                                "Seleccionar participante:",
                                options=[""] + participante_options,
                                key="participante_asignacion_selector"
                            )
                            
                            if participante_sel:
                                participante_idx = participante_options.index(participante_sel)
                                participante_id = participantes_disponibles.iloc[participante_idx]["id"]
                                participante_data = participantes_disponibles.iloc[participante_idx]
                                
                                # Mostrar información del participante
                                with st.container():
                                    st.markdown("**👤 Información del participante:**")
                                    st.markdown(f"**Nombre:** {participante_data['nombre']} {participante_data.get('apellidos', '')}")
                                    st.markdown(f"**Email:** {participante_data.get('email', 'Sin email')}")
                                    if participante_data.get('dni'):
                                        st.markdown(f"**DNI:** {participante_data['dni']}")
                            else:
                                participante_id = None
                    else:
                        participante_id = None
                        st.info("👆 Primero selecciona un grupo")

                # Sección de acciones
                st.markdown("#### 🔧 Acciones")
                
                if grupo_id and participante_id:
                    participante_data = df_participantes[df_participantes["id"] == participante_id].iloc[0]
                    ya_asignado = pd.notna(participante_data.get("grupo_id")) and participante_data["grupo_id"] == grupo_id
                    
                    col_accion1, col_accion2 = st.columns(2)
                    
                    with col_accion1:
                        if ya_asignado:
                            # Opción para desasignar
                            if st.button("🔄 Desasignar del grupo", key="btn_desasignar", type="secondary"):
                                try:
                                    supabase.table("participantes").update({
                                        "grupo_id": None,
                                        "updated_at": datetime.utcnow().isoformat()
                                    }).eq("id", participante_id).execute()
                                    
                                    # LIMPIEZA DE CACHE
                                    data_service.get_grupos_completos.clear()
                                    data_service.get_participantes_completos.clear()
                                    
                                    st.success("✅ Participante desasignado correctamente.")
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ Error al desasignar participante: {e}")
                        else:
                            # Opción para asignar
                            if st.button("✅ Asignar al grupo", key="btn_asignar", type="primary"):
                                try:
                                    supabase.table("participantes").update({
                                        "grupo_id": grupo_id,
                                        "updated_at": datetime.utcnow().isoformat()
                                    }).eq("id", participante_id).execute()
                                    
                                    # LIMPIEZA DE CACHE
                                    data_service.get_grupos_completos.clear()
                                    data_service.get_participantes_completos.clear()
                                    
                                    st.success("✅ Participante asignado correctamente.")
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ Error al asignar participante: {e}")
                    
                    with col_accion2:
                        # Mostrar estado actual
                        if ya_asignado:
                            st.info("ℹ️ Este participante ya está en el grupo seleccionado.")
                        elif pd.notna(participante_data.get("grupo_id")):
                            grupo_anterior = df_grupos[df_grupos["id"] == participante_data["grupo_id"]]
                            if not grupo_anterior.empty:
                                st.warning(f"⚠️ Cambiará del grupo: {grupo_anterior.iloc[0]['codigo_grupo']}")
                        else:
                            st.success("🆓 Participante sin grupo asignado.")

                # Resumen de participantes sin grupo
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
            st.error(f"❌ Error al cargar datos para gestión de participantes: {e}")

    st.divider()
    st.caption("💡 Los grupos son la unidad básica para organizar participantes y gestionar la formación.")
