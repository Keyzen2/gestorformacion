import streamlit as st
import pandas as pd
from datetime import datetime
from utils import export_csv, validar_dni_cif, get_ajustes_app
from services.grupos_service import get_grupos_service
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.title("👥 Gestión de Grupos")
    st.caption("Creación y administración de grupos formativos.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicio de grupos
    grupos_service = get_grupos_service(supabase, session_state)

    # =========================
    # Cargar datos principales
    # =========================
    try:
        df_grupos = grupos_service.get_grupos_completos()
        acciones_dict = grupos_service.get_acciones_dict()
        empresas_dict = grupos_service.get_empresas_dict()
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # =========================
    # Métricas rápidas usando estadísticas del servicio
    # =========================
    if not df_grupos.empty:
        stats = grupos_service.get_estadisticas_grupos()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Total Grupos", stats["total"])
        with col2:
            st.metric("🟢 Activos", stats["activos"])
        with col3:
            st.metric("📊 Promedio Participantes", stats["promedio_participantes"])
        with col4:
            st.metric("📅 Próximos", stats["proximos"])

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
    
    if query:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["codigo_grupo"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["accion_nombre"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]
    
    if estado_filter != "Todos":
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
    # Funciones CRUD usando grupos_service
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

            # Usar servicio para actualizar
            success = grupos_service.update_grupo(grupo_id, datos_editados)
            if success:
                st.success("✅ Grupo actualizado correctamente.")
                st.rerun()
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

            # Usar servicio para crear
            success = grupos_service.create_grupo(datos_nuevos)
            if success:
                st.success("✅ Grupo creado correctamente.")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error al crear grupo: {e}")

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
        "accion_sel": list(acciones_dict.keys()) if acciones_dict else ["No disponible"]
    }
    
    if session_state.role == "admin":
        campos_select["empresa_sel"] = list(empresas_dict.keys()) if empresas_dict else ["No disponible"]

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

    # Campos obligatorios
    campos_obligatorios = ["codigo_grupo", "accion_sel"]

    # Columnas visibles
    columnas_visibles = ["codigo_grupo", "accion_nombre", "fecha_inicio", "fecha_fin_prevista", "localidad", "n_participantes_previstos"]
    if session_state.role == "admin":
        columnas_visibles.insert(2, "empresa_nombre")

    # =========================
    # Mostrar interfaz principal
    # =========================
    if df_filtered.empty:
        st.info("ℹ️ No hay grupos para mostrar.")
        
        if grupos_service.can_modify_data():
            st.markdown("### ➕ Crear primer grupo")
    else:
        # Preparar datos para mostrar
        df_display = df_filtered.copy()
        
        # Añadir campos para selects
        df_display["accion_sel"] = df_display["accion_nombre"]
        if session_state.role == "admin":
            # Obtener nombres de empresa
            empresa_nombres = {}
            for empresa_id in df_display["empresa_id"].unique():
                if pd.notna(empresa_id):
                    empresa_nombre = next((k for k, v in empresas_dict.items() if v == empresa_id), "")
                    empresa_nombres[empresa_id] = empresa_nombre
            df_display["empresa_sel"] = df_display["empresa_id"].map(empresa_nombres)

        listado_con_ficha(
            df_display,
            columnas_visibles=columnas_visibles,
            titulo="Grupo",
            on_save=guardar_grupo,
            on_create=crear_grupo,
            id_col="id",
            campos_select=campos_select,
            campos_textarea=campos_textarea,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=grupos_service.can_modify_data(),
            campos_help=campos_help
        )

    st.divider()

    # =========================
    # Asignación de participantes usando grupos_service
    # =========================
    if not df_grupos.empty and grupos_service.can_modify_data():
        st.markdown("### 👥 Asignar Participantes a Grupos")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Filtro de grupos
            grupo_query = st.text_input("🔍 Buscar grupo")
            df_grupos_filtrados = df_grupos[
                df_grupos["codigo_grupo"].str.contains(grupo_query, case=False, na=False) |
                df_grupos["accion_nombre"].str.contains(grupo_query, case=False, na=False)
            ] if grupo_query else df_grupos

            if not df_grupos_filtrados.empty:
                grupo_options = df_grupos_filtrados.apply(
                    lambda g: f"{g['codigo_grupo']} - {g['accion_nombre']}", axis=1
                ).tolist()
                grupo_sel = st.selectbox("Seleccionar grupo", grupo_options)
                grupo_id = df_grupos_filtrados[
                    df_grupos_filtrados.apply(
                        lambda g: f"{g['codigo_grupo']} - {g['accion_nombre']}", axis=1
                    ) == grupo_sel
                ]["id"].iloc[0]

        with col2:
            # Filtro de participantes usando servicio
            participante_query = st.text_input("🔍 Buscar participante")
            
            try:
                df_participantes = grupos_service.get_participantes_disponibles()
                
                if not df_participantes.empty and participante_query:
                    q_lower = participante_query.lower()
                    df_part_filtrados = df_participantes[
                        df_participantes["nombre"].str.lower().str.contains(q_lower, na=False) |
                        df_participantes["apellidos"].fillna("").str.lower().str.contains(q_lower, na=False) |
                        df_participantes["dni"].fillna("").str.lower().str.contains(q_lower, na=False) |
                        df_participantes["email"].str.lower().str.contains(q_lower, na=False)
                    ]
                else:
                    df_part_filtrados = df_participantes

                if not df_part_filtrados.empty:
                    participante_options = df_part_filtrados.apply(
                        lambda p: f"{p.get('dni', 'Sin DNI')} - {p['nombre']} {p.get('apellidos', '')}", axis=1
                    ).tolist()
                    participante_sel = st.selectbox("Seleccionar participante", participante_options)
                    participante_id = df_part_filtrados[
                        df_part_filtrados.apply(
                            lambda p: f"{p.get('dni', 'Sin DNI')} - {p['nombre']} {p.get('apellidos', '')}", axis=1
                        ) == participante_sel
                    ]["id"].iloc[0]
                else:
                    participante_id = None
                    st.info("ℹ️ No se encontraron participantes.")
                    
            except Exception as e:
                st.error(f"❌ Error al cargar participantes: {e}")
                participante_id = None

        # Botón de asignación usando servicio
        if participante_id and st.button("✅ Asignar participante al grupo"):
            success = grupos_service.asignar_participante_grupo(participante_id, grupo_id)
            if success:
                st.success("✅ Participante asignado correctamente.")
                st.rerun()

    # =========================
    # Vista de participantes por grupo usando servicio
    # =========================
    if not df_grupos.empty:
        st.divider()
        st.markdown("### 📋 Participantes por Grupo")
        
        grupo_vista_query = st.text_input("🔍 Filtrar grupos para ver participantes", key="vista_grupos")
        df_grupos_vista = df_grupos[
            df_grupos["codigo_grupo"].str.contains(grupo_vista_query, case=False, na=False) |
            df_grupos["accion_nombre"].str.contains(grupo_vista_query, case=False, na=False)
        ] if grupo_vista_query else df_grupos

        for _, grupo in df_grupos_vista.iterrows():
            with st.expander(f"👥 {grupo['codigo_grupo']} - {grupo['accion_nombre']}"):
                try:
                    # Usar servicio para obtener participantes del grupo
                    df_participantes_grupo = grupos_service.get_participantes_grupo(grupo["id"])
                    
                    if not df_participantes_grupo.empty:
                        for _, p in df_participantes_grupo.iterrows():
                            col1, col2 = st.columns([4, 1])
                            col1.write(f"📝 {p.get('dni', 'Sin DNI')} - {p['nombre']} {p.get('apellidos', '')} ({p['email']})")
                            
                            if col2.button("🗑️", key=f"remove_{grupo['id']}_{p['id']}"):
                                success = grupos_service.desasignar_participante_grupo(p["id"], grupo["id"])
                                if success:
                                    st.success(f"✅ {p['nombre']} eliminado del grupo.")
                                    st.rerun()
                    else:
                        st.info("ℹ️ Este grupo no tiene participantes asignados.")
                        
                except Exception as e:
                    st.error(f"❌ Error al cargar participantes del grupo: {e}")

    # =========================
    # Importación masiva desde Excel usando servicio
    # =========================
    if not df_grupos.empty and grupos_service.can_modify_data():
        st.divider()
        st.markdown("### 📤 Importación Masiva desde Excel")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            archivo_excel = st.file_uploader(
                "📁 Archivo Excel con DNIs (.xlsx)", 
                type=["xlsx"],
                help="El archivo debe contener una columna 'dni' con los documentos de los participantes"
            )
            
            grupo_excel_options = df_grupos.apply(
                lambda g: f"{g['codigo_grupo']} - {g['accion_nombre']}", axis=1
            ).tolist()
            grupo_excel_sel = st.selectbox("Grupo destino", grupo_excel_options, key="grupo_excel")
            grupo_excel_id = df_grupos[
                df_grupos.apply(lambda g: f"{g['codigo_grupo']} - {g['accion_nombre']}", axis=1) == grupo_excel_sel
            ]["id"].iloc[0]

        with col2:
            st.markdown("**Formato requerido:**")
            st.code("""dni
12345678A
87654321B
11223344C""")

        if st.button("📥 Importar desde Excel") and archivo_excel:
            try:
                df_import = pd.read_excel(archivo_excel)
                
                if "dni" not in df_import.columns:
                    st.error("❌ El archivo debe contener la columna 'dni'.")
                else:
                    # Procesar DNIs
                    dnis_import = [str(d).strip() for d in df_import["dni"] if pd.notna(d)]
                    
                    # Usar servicio para importación masiva
                    resultado = grupos_service.importar_participantes_masivo(grupo_excel_id, dnis_import)
                    
                    if resultado["success"]:
                        if resultado["creados"] > 0:
                            st.success(f"✅ Se han asignado {resultado['creados']} participantes al grupo.")
                        
                        if resultado["errores"]:
                            st.warning("⚠️ Errores encontrados:")
                            for error in resultado["errores"][:10]:  # Mostrar solo los primeros 10
                                st.caption(f"• {error}")
                            if len(resultado["errores"]) > 10:
                                st.caption(f"... y {len(resultado['errores']) - 10} errores más")
                        
                        if resultado["dnis_invalidos"]:
                            st.warning(f"⚠️ DNIs inválidos: {', '.join(resultado['dnis_invalidos'])}")
                        
                        if resultado["creados"] > 0:
                            st.rerun()
                    else:
                        st.error(f"❌ Error: {resultado['error']}")
                        
            except Exception as e:
                st.error(f"❌ Error al procesar el archivo: {e}")

    st.divider()
    st.caption("💡 Los grupos son la unidad básica para organizar participantes y gestionar la formación.")
