import streamlit as st
import pandas as pd
from datetime import datetime
from utils import export_csv, validar_dni_cif
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
            hoy = datetime.today().date()
            grupos_activos = df_grupos[
                pd.to_datetime(df_grupos["fecha_fin_prevista"], errors="coerce").dt.date >= hoy
            ]
            st.metric("🟢 Grupos Activos", len(grupos_activos))

    st.divider()

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
        hoy = datetime.today().date()
        if estado_filter == "Activos":
            df_filtered = df_filtered[
                (pd.to_datetime(df_filtered["fecha_inicio"], errors="coerce").dt.date <= hoy) &
                (pd.to_datetime(df_filtered["fecha_fin_prevista"], errors="coerce").dt.date >= hoy)
            ]
        elif estado_filter == "Finalizados":
            df_filtered = df_filtered[
                pd.to_datetime(df_filtered["fecha_fin_prevista"], errors="coerce").dt.date < hoy
            ]
        elif estado_filter == "Próximos":
            df_filtered = df_filtered[
                pd.to_datetime(df_filtered["fecha_inicio"], errors="coerce").dt.date > hoy
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

        listado_con_ficha(
            df_display,
            columnas_visibles=[
                "id", "codigo_grupo", "accion_nombre", "fecha_inicio", 
                "fecha_fin_prevista", "localidad", "n_participantes_previstos"
            ],
            titulo="Grupo",
            on_save=guardar_grupo,
            on_create=crear_grupo,
            id_col="id",
            campos_select=campos_select,
            campos_textarea=campos_textarea,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=data_service.can_modify_data()
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
            df_part_filtrados = data_service.search_participantes(participante_query)

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

        # Botón de asignación
        if st.button("✅ Asignar participante al grupo"):
            try:
                # Verificar si ya está asignado
                existe = supabase.table("participantes_grupos")\
                    .select("id")\
                    .eq("participante_id", participante_id)\
                    .eq("grupo_id", grupo_id)\
                    .execute()
                
                if existe.data:
                    st.warning("⚠️ Este participante ya está asignado a este grupo.")
                else:
                    supabase.table("participantes_grupos").insert({
                        "participante_id": participante_id,
                        "grupo_id": grupo_id,
                        "fecha_asignacion": datetime.utcnow().isoformat()
                    }).execute()
                    st.success("✅ Participante asignado correctamente.")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error al asignar participante: {e}")

    # =========================
    # Vista de participantes por grupo
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
                    # Obtener participantes del grupo
                    pg_res = supabase.table("participantes_grupos")\
                        .select("participante_id, fecha_asignacion")\
                        .eq("grupo_id", grupo["id"])\
                        .execute()
                    
                    if pg_res.data:
                        participante_ids = [p["participante_id"] for p in pg_res.data]
                        
                        # Obtener datos de participantes
                        part_res = supabase.table("participantes")\
                            .select("id, nombre, apellidos, email, dni")\
                            .in_("id", participante_ids)\
                            .execute()
                        
                        if part_res.data:
                            for p in part_res.data:
                                col1, col2 = st.columns([4, 1])
                                col1.write(f"📝 {p.get('dni', 'Sin DNI')} - {p['nombre']} {p.get('apellidos', '')} ({p['email']})")
                                
                                if col2.button("🗑️", key=f"remove_{grupo['id']}_{p['id']}"):
                                    try:
                                        supabase.table("participantes_grupos")\
                                            .delete()\
                                            .eq("participante_id", p["id"])\
                                            .eq("grupo_id", grupo["id"])\
                                            .execute()
                                        st.success(f"✅ {p['nombre']} eliminado del grupo.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Error al eliminar: {e}")
                        else:
                            st.info("ℹ️ No se encontraron datos de participantes.")
                    else:
                        st.info("ℹ️ Este grupo no tiene participantes asignados.")
                        
                except Exception as e:
                    st.error(f"❌ Error al cargar participantes del grupo: {e}")

    # =========================
    # Importación masiva desde Excel
    # =========================
    if not df_grupos.empty and data_service.can_modify_data():
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
                        .eq("grupo_id", grupo_excel_id)\
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
                                "grupo_id": grupo_excel_id,
                                "fecha_asignacion": datetime.utcnow().isoformat()
                            }).execute()
                            creados += 1
                        except Exception as e:
                            errores.append(f"DNI {dni} - Error: {str(e)}")

                    # Mostrar resultados
                    if creados > 0:
                        st.success(f"✅ Se han asignado {creados} participantes al grupo.")
                    
                    if errores:
                        st.warning("⚠️ Errores encontrados:")
                        for error in errores[:10]:  # Mostrar solo los primeros 10
                            st.caption(f"• {error}")
                        if len(errores) > 10:
                            st.caption(f"... y {len(errores) - 10} errores más")
                    
                    if creados > 0:
                        st.rerun()
                        
            except Exception as e:
                st.error(f"❌ Error al procesar el archivo: {e}")

    st.divider()
    st.caption("💡 Los grupos son la unidad básica para organizar participantes y gestionar la formación.")
