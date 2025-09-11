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
        
        # Cargar empresas solo si es admin
        if session_state.role == "admin":
            empresas_dict = data_service.get_empresas_dict()
        else:
            empresas_dict = {}
        
        # Debug: verificar qué columnas tenemos - REMOVER después de diagnosticar
        if not df_grupos.empty:
            with st.expander("🔍 Debug - Información del DataFrame"):
                st.write("**Columnas disponibles:**", list(df_grupos.columns))
                st.write("**Primeras filas:**")
                st.dataframe(df_grupos.head())
            
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # =========================
    # Métricas rápidas
    # =========================
    if not df_grupos.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("👥 Total Grupos", len(df_grupos))
        
        with col2:
            # Grupos activos (en curso)
            hoy = datetime.now()
            activos = len(df_grupos[
                (pd.to_datetime(df_grupos["fecha_inicio"], errors="coerce") <= hoy) & 
                (df_grupos["fecha_fin"].isna() | (pd.to_datetime(df_grupos["fecha_fin"], errors="coerce") >= hoy))
            ])
            st.metric("🟢 Activos", activos)
        
        with col3:
            # Promedio de participantes previstos
            promedio = df_grupos["n_participantes_previstos"].mean() if "n_participantes_previstos" in df_grupos.columns else 0
            st.metric("📊 Promedio Participantes", round(promedio, 1))
        
        with col4:
            # Grupos próximos
            proximos = len(df_grupos[pd.to_datetime(df_grupos["fecha_inicio"], errors="coerce") > hoy])
            st.metric("📅 Próximos", proximos)

    # =========================
    # Filtros de búsqueda
    # =========================
    st.divider()
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2 = st.columns(2)
    
    with col1:
        query = st.text_input("🔍 Buscar por código o acción formativa")
    with col2:
        estado_filter = st.selectbox(
            "Filtrar por estado", 
            ["Todos", "Activos", "Finalizados", "Próximos"]
        )

    # Aplicar filtros
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
            df_filtered = df_filtered[
                pd.to_datetime(df_filtered["fecha_fin"], errors="coerce") < hoy
            ]
        elif estado_filter == "Próximos":
            df_filtered = df_filtered[
                pd.to_datetime(df_filtered["fecha_inicio"], errors="coerce") > hoy
            ]

    # Exportar CSV
    if not df_filtered.empty:
        export_csv(df_filtered, filename="grupos.csv")

    st.divider()

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_grupo(grupo_id, datos_editados):
        """Función para guardar cambios en un grupo."""
        try:
            # Procesar acción formativa si está presente
            if "accion_sel" in datos_editados:
                accion_sel = datos_editados.pop("accion_sel")
                if accion_sel and accion_sel in acciones_dict:
                    datos_editados["accion_formativa_id"] = acciones_dict[accion_sel]

            # Procesar empresa si está presente (solo admin)
            if session_state.role == "admin" and "empresa_sel" in datos_editados:
                empresa_sel = datos_editados.pop("empresa_sel")
                if empresa_sel and empresa_sel in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[empresa_sel]

            # Validaciones básicas
            if not datos_editados.get("codigo_grupo"):
                st.error("⚠️ El código de grupo es obligatorio.")
                return

            # Usar DataService para actualizar (simulando funcionalidad)
            try:
                # Añadir timestamp de actualización
                datos_editados["updated_at"] = datetime.utcnow().isoformat()
                
                # Actualizar en Supabase
                supabase.table("grupos").update(datos_editados).eq("id", grupo_id).execute()
                
                # Limpiar cache del DataService
                data_service.get_grupos_completos.clear()
                
                st.success("✅ Grupo actualizado correctamente.")
                st.rerun()
                
            except Exception as db_error:
                st.error(f"❌ Error en base de datos: {db_error}")
                
        except Exception as e:
            st.error(f"❌ Error al actualizar grupo: {e}")

    def crear_grupo(datos_nuevos):
        """Función para crear un nuevo grupo."""
        try:
            # Procesar acción formativa
            if "accion_sel" in datos_nuevos:
                accion_sel = datos_nuevos.pop("accion_sel")
                if accion_sel and accion_sel in acciones_dict:
                    datos_nuevos["accion_formativa_id"] = acciones_dict[accion_sel]

            # Procesar empresa
            if session_state.role == "admin" and "empresa_sel" in datos_nuevos:
                empresa_sel = datos_nuevos.pop("empresa_sel")
                if empresa_sel and empresa_sel in empresas_dict:
                    datos_nuevos["empresa_id"] = empresas_dict[empresa_sel]
            elif session_state.role == "gestor":
                datos_nuevos["empresa_id"] = session_state.user.get("empresa_id")

            # Validaciones
            if not datos_nuevos.get("codigo_grupo"):
                st.error("⚠️ El código de grupo es obligatorio.")
                return

            # Verificar código único
            codigo_existe = supabase.table("grupos").select("id").eq("codigo_grupo", datos_nuevos["codigo_grupo"]).execute()
            if codigo_existe.data:
                st.error("⚠️ Ya existe un grupo con ese código.")
                return

            # Añadir timestamps
            datos_nuevos["created_at"] = datetime.utcnow().isoformat()

            # Crear en Supabase
            result = supabase.table("grupos").insert(datos_nuevos).execute()
            
            if result.data:
                # Limpiar cache del DataService
                data_service.get_grupos_completos.clear()
                
                st.success("✅ Grupo creado correctamente.")
                st.rerun()
            else:
                st.error("❌ Error al crear el grupo.")
                
        except Exception as e:
            st.error(f"❌ Error al crear grupo: {e}")

    def eliminar_grupo(grupo_id):
        """Función para eliminar un grupo."""
        try:
            # Verificar dependencias (participantes asignados)
            participantes = supabase.table("participantes").select("id").eq("grupo_id", grupo_id).execute()
            if participantes.data:
                st.error("⚠️ No se puede eliminar. El grupo tiene participantes asignados.")
                return

            # Eliminar grupo
            supabase.table("grupos").delete().eq("id", grupo_id).execute()
            
            # Limpiar cache del DataService
            data_service.get_grupos_completos.clear()
            
            st.success("✅ Grupo eliminado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al eliminar grupo: {e}")

    # =========================
    # Campos dinámicos
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente."""
        campos = [
            "codigo_grupo", "accion_sel", "fecha_inicio", "fecha_fin_prevista",
            "localidad", "provincia", "cp", "n_participantes_previstos", "observaciones"
        ]
        
        # Solo admin puede seleccionar empresa
        if session_state.role == "admin":
            campos.insert(2, "empresa_sel")
            
        return campos

    # Configurar opciones para selects
    campos_select = {
        "accion_sel": list(acciones_dict.keys()) if acciones_dict else ["No hay acciones disponibles"]
    }
    
    if session_state.role == "admin" and empresas_dict:
        campos_select["empresa_sel"] = list(empresas_dict.keys())

    campos_textarea = {
        "observaciones": {"label": "Observaciones del grupo"}
    }

    # Campos de ayuda
    campos_help = {
        "codigo_grupo": "Código único identificativo del grupo",
        "accion_sel": "Acción formativa que se impartirá",
        "empresa_sel": "Empresa a la que pertenece el grupo",
        "fecha_inicio": "Fecha de inicio de la formación",
        "fecha_fin_prevista": "Fecha prevista de finalización",
        "localidad": "Ciudad donde se impartirá",
        "n_participantes_previstos": "Número estimado de participantes"
    }

    # Columnas visibles - usar solo las que sabemos que existen
    columnas_base = ["codigo_grupo", "fecha_inicio", "fecha_fin_prevista", "localidad", "n_participantes_previstos"]
    
    # Añadir columnas opcionales solo si existen
    columnas_visibles = []
    for col in columnas_base:
        if col in df_grupos.columns:
            columnas_visibles.append(col)
    
    # Verificar si tenemos información de acción formativa
    if "accion_nombre" in df_grupos.columns:
        columnas_visibles.insert(1, "accion_nombre")
    elif "accion_formativa_id" in df_grupos.columns:
        # Si tenemos el ID pero no el nombre, lo añadimos
        columnas_visibles.insert(1, "accion_formativa_id")
    
    # Para admin, añadir empresa si existe
    if session_state.role == "admin":
        if "empresa_nombre" in df_grupos.columns:
            columnas_visibles.insert(2, "empresa_nombre")
        elif "empresa_id" in df_grupos.columns:
            columnas_visibles.insert(2, "empresa_id")

    # =========================
    # Mostrar interfaz principal
    # =========================
    if df_filtered.empty:
        st.info("ℹ️ No hay grupos para mostrar.")
        
        if session_state.role in ["admin", "gestor"]:
            st.markdown("### ➕ Crear primer grupo")
            # El formulario de creación se mostrará automáticamente por listado_con_ficha
    else:
        # Preparar datos para mostrar
        df_display = df_filtered.copy()
        
        # Añadir campos para selects - usar columnas que realmente existen
        if "accion_nombre" in df_display.columns:
            df_display["accion_sel"] = df_display["accion_nombre"]
        else:
            # Si no tenemos accion_nombre, crear un valor por defecto
            df_display["accion_sel"] = "Acción no disponible"
            
        if session_state.role == "admin" and empresas_dict:
            if "empresa_nombre" in df_display.columns:
                df_display["empresa_sel"] = df_display["empresa_nombre"]
            elif "empresa_id" in df_display.columns:
                # Mapear IDs a nombres si tenemos el diccionario
                empresa_nombres = {}
                for empresa_id in df_display["empresa_id"].dropna().unique():
                    empresa_nombre = next((k for k, v in empresas_dict.items() if v == empresa_id), f"Empresa {empresa_id}")
                    empresa_nombres[empresa_id] = empresa_nombre
                df_display["empresa_sel"] = df_display["empresa_id"].map(empresa_nombres).fillna("Sin empresa")
            else:
                df_display["empresa_sel"] = "Sin empresa"

        # Usar el componente listado_con_ficha
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
            campos_help=campos_help
        )

    st.divider()

    # =========================
    # Gestión de participantes
    # =========================
    if not df_grupos.empty and session_state.role in ["admin", "gestor"]:
        st.markdown("### 👥 Asignar Participantes a Grupos")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Selección de grupo
            if not df_grupos.empty:
                grupo_options = df_grupos.apply(
                    lambda g: f"{g['codigo_grupo']} - {g['accion_nombre']}", axis=1
                ).tolist()
                grupo_sel = st.selectbox("Seleccionar grupo", [""] + grupo_options)
                
                if grupo_sel:
                    grupo_id = df_grupos[
                        df_grupos.apply(
                            lambda g: f"{g['codigo_grupo']} - {g['accion_nombre']}", axis=1
                        ) == grupo_sel
                    ]["id"].iloc[0]
                else:
                    grupo_id = None

        with col2:
            # Selección de participantes
            if grupo_id:
                try:
                    # Cargar participantes disponibles
                    query = supabase.table("participantes").select("id, nombre, apellidos, dni, email")
                    if session_state.role == "gestor":
                        query = query.eq("empresa_id", session_state.user.get("empresa_id"))
                    
                    participantes_res = query.execute()
                    df_participantes = pd.DataFrame(participantes_res.data or [])
                    
                    if not df_participantes.empty:
                        participante_options = df_participantes.apply(
                            lambda p: f"{p.get('dni', 'Sin DNI')} - {p['nombre']} {p.get('apellidos', '')}", axis=1
                        ).tolist()
                        participante_sel = st.selectbox("Seleccionar participante", [""] + participante_options)
                        
                        if participante_sel:
                            participante_id = df_participantes[
                                df_participantes.apply(
                                    lambda p: f"{p.get('dni', 'Sin DNI')} - {p['nombre']} {p.get('apellidos', '')}", axis=1
                                ) == participante_sel
                            ]["id"].iloc[0]
                        else:
                            participante_id = None
                    else:
                        participante_id = None
                        st.info("ℹ️ No hay participantes disponibles.")
                        
                except Exception as e:
                    st.error(f"❌ Error al cargar participantes: {e}")
                    participante_id = None
            else:
                participante_id = None

        # Botón de asignación
        if grupo_id and participante_id and st.button("✅ Asignar participante al grupo"):
            try:
                # Verificar que no esté ya asignado
                existe = supabase.table("participantes").select("id").eq("id", participante_id).eq("grupo_id", grupo_id).execute()
                
                if existe.data:
                    st.warning("⚠️ Este participante ya está asignado a este grupo.")
                else:
                    # Asignar participante al grupo
                    supabase.table("participantes").update({"grupo_id": grupo_id}).eq("id", participante_id).execute()
                    st.success("✅ Participante asignado correctamente.")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Error al asignar participante: {e}")

    st.divider()
    st.caption("💡 Los grupos son la unidad básica para organizar participantes y gestionar la formación.")
