"""
Módulo para la gestión de grupos formativos.
Versión corregida para funcionar con el nuevo componente listado_con_ficha.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import export_csv
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.markdown("## 👨‍🏫 Grupos")
    st.caption("Gestión de grupos de formación y vinculación con participantes.")
    
    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicio de datos
    data_service = get_data_service(supabase, session_state)

    # =========================
    # Cargar datos
    # =========================
    with st.spinner("Cargando datos..."):
        df_grupos = data_service.get_grupos_completos()
        acciones_dict = data_service.get_acciones_dict()
        empresas_dict = data_service.get_empresas_dict()
        df_participantes = data_service.get_participantes_completos()

    # =========================
    # Métricas
    # =========================
    if not df_grupos.empty:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("👥 Total Grupos", len(df_grupos))
        
        with col2:
            total_previstos = df_grupos["n_participantes_previstos"].fillna(0).sum()
            st.metric("🎯 Participantes Previstos", int(total_previstos))
        
        with col3:
            # Grupos activos (fecha fin no pasada)
            hoy = date.today()
            try:
                grupos_activos = df_grupos[
                    pd.to_datetime(df_grupos["fecha_fin_prevista"], errors="coerce").dt.date >= hoy
                ]
                st.metric("🟢 Grupos Activos", len(grupos_activos))
            except:
                st.metric("🟢 Grupos Activos", "N/D")

    # =========================
    # Filtros de búsqueda
    # =========================
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2 = st.columns(2)
    
    with col1:
        query = st.text_input("🔍 Buscar por código de grupo o acción")
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
            df_filtered["accion_nombre"].str.lower().str.contains(q_lower, na=False)
        ]
    
    if estado_filter != "Todos":
        hoy = date.today()
        if estado_filter == "Activos":
            # Grupos que ya han comenzado pero no han terminado
            mask = (
                (pd.to_datetime(df_filtered["fecha_inicio_prevista"], errors="coerce").dt.date <= hoy) &
                (pd.to_datetime(df_filtered["fecha_fin_prevista"], errors="coerce").dt.date >= hoy)
            )
            df_filtered = df_filtered[mask]
        elif estado_filter == "Finalizados":
            # Grupos que ya han terminado
            mask = pd.to_datetime(df_filtered["fecha_fin_prevista"], errors="coerce").dt.date < hoy
            df_filtered = df_filtered[mask]
        elif estado_filter == "Próximos":
            # Grupos que aún no han comenzado
            mask = pd.to_datetime(df_filtered["fecha_inicio_prevista"], errors="coerce").dt.date > hoy
            df_filtered = df_filtered[mask]

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
            # Validaciones
            if not datos_editados.get("codigo_grupo"):
                st.error("⚠️ El código de grupo es obligatorio.")
                return
                
            if "fecha_fin_prevista" in datos_editados and "fecha_inicio" in datos_editados:
                if datos_editados["fecha_fin_prevista"] < datos_editados["fecha_inicio"]:
                    st.error("⚠️ La fecha de fin no puede ser anterior a la de inicio.")
                    return

            # Procesar acción formativa
            if "accion_sel" in datos_editados:
                accion_sel = datos_editados.pop("accion_sel")
                datos_editados["accion_formativa_id"] = acciones_dict.get(accion_sel)

            # Procesar empresa (solo para admin)
            if "empresa_sel" in datos_editados and session_state.role == "admin":
                empresa_sel = datos_editados.pop("empresa_sel")
                datos_editados["empresa_id"] = empresas_dict.get(empresa_sel)

            supabase.table("grupos").update(datos_editados).eq("id", grupo_id).execute()
            # Limpiar cache
            data_service.get_grupos_completos.clear()
            st.success("✅ Grupo actualizado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar grupo: {e}")

    def crear_grupo(datos_nuevos):
        """Función para crear un nuevo grupo."""
        try:
            # Validaciones
            if not datos_nuevos.get("codigo_grupo"):
                st.error("⚠️ El código de grupo es obligatorio.")
                return
                
            if not datos_nuevos.get("accion_sel"):
                st.error("⚠️ Debes seleccionar una acción formativa.")
                return

            # Procesar acción formativa
            accion_sel = datos_nuevos.pop("accion_sel")
            datos_nuevos["accion_formativa_id"] = acciones_dict.get(accion_sel)

            # Procesar empresa
            if session_state.role == "admin" and "empresa_sel" in datos_nuevos:
                empresa_sel = datos_nuevos.pop("empresa_sel")
                datos_nuevos["empresa_id"] = empresas_dict.get(empresa_sel)
            elif session_state.role == "gestor":
                datos_nuevos["empresa_id"] = session_state.user.get("empresa_id")

            # Establecer estado por defecto
            datos_nuevos["estado"] = "abierto"

            supabase.table("grupos").insert(datos_nuevos).execute()
            # Limpiar cache
            data_service.get_grupos_completos.clear()
            st.success("✅ Grupo creado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al crear grupo: {e}")

    def eliminar_grupo(grupo_id):
        """Función para eliminar un grupo."""
        try:
            # Verificar si hay participantes asignados
            check_part = supabase.table("participantes").select("id").eq("grupo_id", grupo_id).execute()
            if check_part.data:
                st.error("⚠️ No se puede eliminar el grupo porque tiene participantes asignados.")
                return False
                
            # Eliminar grupo
            supabase.table("grupos").delete().eq("id", grupo_id).execute()
            
            # Limpiar cache
            data_service.get_grupos_completos.clear()
            
            st.success("✅ Grupo eliminado correctamente.")
            st.rerun()
            return True
        except Exception as e:
            st.error(f"❌ Error al eliminar grupo: {e}")
            return False

    # =========================
    # Campos dinámicos
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente."""
        campos = [
            "codigo_grupo", "accion_sel", "fecha_inicio_prevista", "fecha_fin_prevista",
            "localidad", "provincia", "codigo_postal", "n_participantes_previstos", "observaciones", "estado"
        ]
        
        # Solo admin puede seleccionar empresa
        if session_state.role == "admin":
            campos.insert(2, "empresa_sel")
            
        return campos

    # Configurar opciones para selects
    campos_select = {
        "accion_sel": list(acciones_dict.keys()) if acciones_dict else ["No disponible"],
        "estado": ["abierto", "cerrado", "cancelado", "en_curso", "finalizado"]
    }
    
    if session_state.role == "admin":
        campos_select["empresa_sel"] = list(empresas_dict.keys()) if empresas_dict else ["No disponible"]

    campos_textarea = {
        "observaciones": {"label": "Observaciones del grupo", "height": 100}
    }

    campos_help = {
        "codigo_grupo": "Código único identificativo del grupo (obligatorio)",
        "accion_sel": "Acción formativa asociada al grupo (obligatorio)",
        "empresa_sel": "Empresa a la que pertenece el grupo",
        "fecha_inicio_prevista": "Fecha de inicio prevista del grupo",
        "fecha_fin_prevista": "Fecha de finalización prevista del grupo",
        "localidad": "Localidad donde se imparte la formación",
        "provincia": "Provincia donde se imparte la formación",
        "codigo_postal": "Código postal de la ubicación",
        "n_participantes_previstos": "Número de participantes previstos",
        "observaciones": "Notas adicionales sobre el grupo",
        "estado": "Estado actual del grupo (abierto, en curso, finalizado, etc.)"
    }

    # =========================
    # Mostrar interfaz principal
    # =========================
    if df_filtered.empty:
        st.info("ℹ️ No hay grupos para mostrar.")
        if data_service.can_modify_data():
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

        # Usar el componente listado_con_ficha con todos los parámetros necesarios
        listado_con_ficha(
            df=df_display,
            columnas_visibles=[
                "codigo_grupo", "accion_nombre", "fecha_inicio_prevista", 
                "fecha_fin_prevista", "localidad", "n_participantes_previstos", "estado"
            ],
            titulo="Grupo",
            on_save=guardar_grupo,
            on_create=crear_grupo,
            on_delete=eliminar_grupo,  # Añadido el parámetro para eliminar
            id_col="id",
            campos_select=campos_select,
            campos_textarea=campos_textarea,
            campos_dinamicos=get_campos_dinamicos,
            campos_help=campos_help,
            allow_creation=data_service.can_modify_data(),
            search_columns=["codigo_grupo", "accion_nombre", "localidad"],  # Parámetro necesario
            campos_obligatorios=["codigo_grupo", "accion_sel"]  # Parámetro necesario
        )

    st.divider()

    # =========================
    # Asignación de participantes
    # =========================
    if not df_grupos.empty and data_service.can_modify_data():
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
            # Filtro de participantes
            participante_query = st.text_input("🔍 Buscar participante")
            
            # Filtrar participantes por empresa del usuario
            if session_state.role == "gestor":
                empresa_id = session_state.user.get("empresa_id")
                df_parts = df_participantes[df_participantes["empresa_id"] == empresa_id]
            else:
                df_parts = df_participantes.copy()
            
            # Aplicar filtro de búsqueda
            if participante_query:
                q_lower = participante_query.lower()
                df_parts = df_parts[
                    df_parts["nombre"].str.lower().str.contains(q_lower, na=False) |
                    df_parts["apellidos"].str.lower().str.contains(q_lower, na=False) |
                    df_parts["dni"].str.lower().str.contains(q_lower, na=False)
                ]
            
            # Filtrar participantes que no están en el grupo seleccionado
            if 'grupo_id' in df_parts.columns:
                df_parts = df_parts[
                    (df_parts["grupo_id"].isna()) | 
                    (df_parts["grupo_id"] != grupo_id)
                ]
            
            if not df_parts.empty:
                participantes_options = df_parts.apply(
                    lambda p: f"{p['nombre']} {p['apellidos']} ({p['dni']})", axis=1
                ).tolist()
                participante_sel = st.multiselect(
                    "Seleccionar participantes para asignar",
                    options=participantes_options
                )
                
                # Obtener IDs de participantes seleccionados
                part_ids = []
                for sel in participante_sel:
                    for _, p in df_parts.iterrows():
                        if f"{p['nombre']} {p['apellidos']} ({p['dni']})" == sel:
                            part_ids.append(p['id'])
                            break
            else:
                st.info("No hay participantes disponibles para asignar.")
                part_ids = []
        
        # Botón para asignar participantes
        if 'grupo_id' in locals() and 'part_ids' in locals() and part_ids:
            if st.button("✅ Asignar participantes seleccionados", type="primary"):
                asignados = 0
                errores = 0
                
                for part_id in part_ids:
                    try:
                        # Actualizar participante para asignarlo al grupo
                        supabase.table("participantes").update({
                            "grupo_id": grupo_id,
                            "updated_at": datetime.now().isoformat()
                        }).eq("id", part_id).execute()
                        asignados += 1
                    except Exception as e:
                        st.error(f"❌ Error al asignar participante {part_id}: {e}")
                        errores += 1
                
                if asignados > 0:
                    st.success(f"✅ {asignados} participantes asignados correctamente.")
                    if errores > 0:
                        st.warning(f"⚠️ {errores} participantes no pudieron ser asignados.")
                    # Limpiar cache
                    data_service.get_participantes_completos.clear()
                    st.rerun()
                elif errores > 0:
                    st.error("❌ No se pudo asignar ningún participante.")
        
        # Mostrar participantes del grupo seleccionado
        if 'grupo_id' in locals():
            st.markdown(f"### 📋 Participantes en grupo seleccionado")
            
            # Obtener participantes del grupo
            participantes_grupo = df_participantes[df_participantes["grupo_id"] == grupo_id]
            
            if not participantes_grupo.empty:
                st.write(f"**Total:** {len(participantes_grupo)} participantes")
                
                # Mostrar tabla con opción de desasignar
                for i, p in participantes_grupo.iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"{p['nombre']} {p['apellidos']} ({p['dni']})")
                    with col2:
                        if st.button("❌ Desasignar", key=f"desasignar_{p['id']}"):
                            try:
                                # Desasignar participante del grupo
                                supabase.table("participantes").update({
                                    "grupo_id": None,
                                    "updated_at": datetime.now().isoformat()
                                }).eq("id", p['id']).execute()
                                
                                st.success(f"✅ Participante desasignado correctamente.")
                                # Limpiar cache
                                data_service.get_participantes_completos.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al desasignar participante: {e}")
            else:
                st.info("ℹ️ No hay participantes asignados a este grupo.")

    # =========================
    # Sección de importación de Excel
    # =========================
    if data_service.can_modify_data():
        st.divider()
        st.markdown("### 📥 Importar Grupos desde Excel")
        
        with st.expander("📊 Importar grupos y participantes desde Excel"):
            uploaded_file = st.file_uploader("Selecciona un archivo Excel", type=["xlsx", "xls"])
            
            if uploaded_file is not None:
                try:
                    # Leer archivo Excel
                    df_excel = pd.read_excel(uploaded_file, sheet_name=None)
                    
                    # Verificar si tiene las hojas necesarias
                    if "Grupos" in df_excel:
                        st.success(f"✅ Archivo cargado correctamente.")
                        df_grupos_excel = df_excel["Grupos"]
                        
                        # Mostrar vista previa
                        st.write("Vista previa de grupos:")
                        st.dataframe(df_grupos_excel.head(5))
                        
                        # Mapeo de columnas
                        st.markdown("### Mapeo de columnas")
                        st.caption("Selecciona las columnas correspondientes en tu Excel:")
                        
                        col_codigo = st.selectbox("Columna para Código de Grupo", options=df_grupos_excel.columns.tolist())
                        col_accion = st.selectbox("Columna para Acción Formativa", options=df_grupos_excel.columns.tolist())
                        col_inicio = st.selectbox("Columna para Fecha Inicio", options=df_grupos_excel.columns.tolist())
                        col_fin = st.selectbox("Columna para Fecha Fin", options=df_grupos_excel.columns.tolist())
                        
                        if st.button("✅ Importar Grupos", type="primary"):
                            grupos_creados = 0
                            errores = 0
                            
                            for i, row in df_grupos_excel.iterrows():
                                try:
                                    # Obtener código de
