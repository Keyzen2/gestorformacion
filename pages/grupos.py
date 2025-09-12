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
            hoy = datetime.now()
            activos = len(df_grupos[
                (pd.to_datetime(df_grupos["fecha_inicio"], errors="coerce") <= hoy) & 
                (df_grupos["fecha_fin"].isna() | (pd.to_datetime(df_grupos["fecha_fin"], errors="coerce") >= hoy))
            ])
            st.metric("🟢 Activos", activos)
        
        with col3:
            promedio = df_grupos["n_participantes_previstos"].mean() if "n_participantes_previstos" in df_grupos.columns else 0
            st.metric("📊 Promedio Participantes", round(promedio, 1))
        
        with col4:
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
        try:
            if "accion_sel" in datos_editados:
                accion_sel = datos_editados.pop("accion_sel")
                if accion_sel and accion_sel in acciones_dict:
                    datos_editados["accion_formativa_id"] = acciones_dict[accion_sel]

            if session_state.role == "admin" and "empresa_sel" in datos_editados:
                empresa_sel = datos_editados.pop("empresa_sel")
                if empresa_sel and empresa_sel in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[empresa_sel]

            if not datos_editados.get("codigo_grupo"):
                st.error("⚠️ El código de grupo es obligatorio.")
                return

            supabase.table("grupos").update(datos_editados).eq("id", grupo_id).execute()
            data_service.get_grupos_completos.clear()
            st.success("✅ Grupo actualizado correctamente.")
            st.rerun()
                
        except Exception as e:
            st.error(f"❌ Error al actualizar grupo: {e}")

    def crear_grupo(datos_nuevos):
        try:
            if "accion_sel" in datos_nuevos:
                accion_sel = datos_nuevos.pop("accion_sel")
                if accion_sel and accion_sel in acciones_dict:
                    datos_nuevos["accion_formativa_id"] = acciones_dict[accion_sel]

            if session_state.role == "admin" and "empresa_sel" in datos_nuevos:
                empresa_sel = datos_nuevos.pop("empresa_sel")
                if empresa_sel and empresa_sel in empresas_dict:
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
                data_service.get_grupos_completos.clear()
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
            data_service.get_grupos_completos.clear()
            st.success("✅ Grupo eliminado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al eliminar grupo: {e}")

    # =========================
    # Campos dinámicos
    # =========================
    def get_campos_dinamicos(datos):
        campos = [
            "codigo_grupo", "accion_sel", "fecha_inicio", "fecha_fin",
            "fecha_fin_prevista", "aula_virtual", "horario", "localidad",
            "provincia", "cp", "n_participantes_previstos", "n_participantes_finalizados",
            "n_aptos", "n_no_aptos", "observaciones"
        ]
        if session_state.role == "admin":
            campos.insert(2, "empresa_sel")
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
    # Mostrar interfaz principal
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

    st.divider()

    # =========================
    # Gestión de finalización de grupo
    # =========================
    if session_state.role in ["admin", "gestor"] and not df_grupos.empty:
        st.markdown("### ✅ Finalizar Grupo")
        grupo_finalizar = st.selectbox(
            "Seleccionar grupo a finalizar",
            [""] + df_grupos["codigo_grupo"].tolist()
        )

        if grupo_finalizar:
            grupo_data = df_grupos[df_grupos["codigo_grupo"] == grupo_finalizar].iloc[0]
            grupo_id = grupo_data["id"]

            participantes = supabase.table("participantes").select("id, estado_finalizacion").eq("grupo_id", grupo_id).execute()
            df_part = pd.DataFrame(participantes.data or [])

            n_finalizados = len(df_part)
            n_aptos = len(df_part[df_part["estado_finalizacion"] == "Apto"])
            n_no_aptos = len(df_part[df_part["estado_finalizacion"] == "No apto"])

            st.write(f"- Total participantes finalizados: {n_finalizados}")
            st.write(f"- Participantes aptos: {n_aptos}")
            st.write(f"- Participantes no aptos: {n_no_aptos}")

            fecha_fin_real = st.date_input("Fecha de fin real", value=datetime.now())

            if st.button("📌 Finalizar grupo"):
                try:
                    supabase.table("grupos").update({
                        "fecha_fin": fecha_fin_real.isoformat(),
                        "n_participantes_finalizados": n_finalizados,
                        "n_aptos": n_aptos,
                        "n_no_aptos": n_no_aptos
                    }).eq("id", grupo_id).execute()

                    data_service.get_grupos_completos.clear()
                    st.success("✅ Grupo finalizado correctamente. Puedes exportar el XML de finalización.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al finalizar grupo: {e}")

    st.divider()
    st.caption("💡 Los grupos son la unidad básica para organizar participantes y gestionar la formación.")  

