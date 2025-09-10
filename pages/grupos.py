"""
Módulo para la gestión de grupos formativos.
Versión mejorada con integración completa de DataService y listado_con_ficha.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import export_csv, export_excel, formato_fecha, formato_moneda
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.title("👨‍🏫 Grupos")
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
        ds = get_data_service(supabase, session_state)

        df_grupos = ds.get_grupos_completos()
        acciones_dict = ds.get_acciones_dict()
        empresas_dict = ds.get_empresas_dict()
        df_participantes = ds.get_participantes_completos()
        df_tutores = ds.get_tutores()

        acciones_opciones = [""] + sorted(acciones_dict.keys())
        empresas_opciones = [""] + sorted(empresas_dict.keys())

        tutores_dict = {}
        if not df_tutores.empty:
            tutores_dict = {
                f"{row.get('nombre','')} {row.get('apellidos','')}".strip(): row["id"]
                for _, row in df_tutores.iterrows()
            }
        tutores_opciones = [""] + sorted(tutores_dict.keys())

    # Fallback de columnas de fecha si faltan
    if "fecha_inicio_prevista" not in df_grupos.columns and "fecha_inicio" in df_grupos.columns:
        df_grupos["fecha_inicio_prevista"] = df_grupos["fecha_inicio"]
    if "fecha_fin_prevista" not in df_grupos.columns:
        df_grupos["fecha_fin_prevista"] = None

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
            hoy = date.today()
            try:
                grupos_activos = df_grupos[
                    pd.to_datetime(df_grupos["fecha_fin_prevista"], errors="coerce").dt.date >= hoy
                ]
                st.metric("🟢 Grupos Activos", len(grupos_activos))
            except:
                st.metric("🟢 Grupos Activos", "N/D")

    if not df_grupos.empty:
        col1, col2 = st.columns(2)
        with col1:
            export_csv(df_grupos, filename="grupos.csv")
        with col2:
            export_excel(df_grupos, filename="grupos.xlsx")

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
        hoy = date.today()
        if estado_filter == "Activos":
            mask = (
                (pd.to_datetime(df_filtered["fecha_inicio_prevista"], errors="coerce").dt.date <= hoy) &
                (pd.to_datetime(df_filtered["fecha_fin_prevista"], errors="coerce").dt.date >= hoy)
            )
            df_filtered = df_filtered[mask]
        elif estado_filter == "Finalizados":
            mask = pd.to_datetime(df_filtered["fecha_fin_prevista"], errors="coerce").dt.date < hoy
            df_filtered = df_filtered[mask]
        elif estado_filter == "Próximos":
            mask = pd.to_datetime(df_filtered["fecha_inicio_prevista"], errors="coerce").dt.date > hoy
            df_filtered = df_filtered[mask]

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_grupo(grupo_id, datos_editados):
        try:
            if "accion_nombre" in datos_editados and datos_editados["accion_nombre"]:
                nombre = datos_editados.pop("accion_nombre")
                if nombre in acciones_dict:
                    datos_editados["accion_formativa_id"] = acciones_dict[nombre]
                else:
                    st.error(f"⚠️ Acción formativa '{nombre}' no encontrada.")
                    return

            if "empresa_nombre" in datos_editados and datos_editados["empresa_nombre"]:
                nombre = datos_editados.pop("empresa_nombre")
                if nombre in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[nombre]
                else:
                    st.error(f"⚠️ Empresa '{nombre}' no encontrada.")
                    return

            if "tutor_nombre" in datos_editados and datos_editados["tutor_nombre"]:
                nombre = datos_editados.pop("tutor_nombre")
                if nombre in tutores_dict:
                    datos_editados["tutor_id"] = tutores_dict[nombre]
                else:
                    st.error(f"⚠️ Tutor '{nombre}' no encontrado.")
                    return

            if "fecha_inicio_prevista" in datos_editados:
                fi = datos_editados.pop("fecha_inicio_prevista")
                if fi:
                    datos_editados["fecha_inicio"] = fi

            fin = datos_editados.get("fecha_fin_prevista")
            inicio = datos_editados.get("fecha_inicio")
            if inicio and fin and inicio > fin:
                st.error("⚠️ La fecha de inicio no puede ser posterior a la fecha de fin prevista.")
                return

            supabase.table("grupos").update(datos_editados).eq("id", grupo_id).execute()
            st.success("✅ Grupo actualizado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"⚠️ Error al actualizar grupo: {e}")

    def crear_grupo(datos_nuevos):
        try:
            if not datos_nuevos.get("codigo_grupo") or not datos_nuevos.get("accion_nombre"):
                st.error("⚠️ Código de grupo y acción formativa son obligatorios.")
                return

            existe = supabase.table("grupos").select("id").eq("codigo_grupo", datos_nuevos["codigo_grupo"]).execute()
            if existe.data:
                st.error(f"⚠️ Ya existe un grupo con el código {datos_nuevos['codigo_grupo']}.")
                return

            accion_formativa_id = None
            if datos_nuevos.get("accion_nombre") in acciones_dict:
                accion_formativa_id = acciones_dict[datos_nuevos["accion_nombre"]]
            else:
                st.error(f"⚠️ Acción formativa '{datos_nuevos.get('accion_nombre','')}' no encontrada.")
                return

            if datos_nuevos.get("empresa_nombre"):
                if datos_nuevos["empresa_nombre"] in empresas_dict:
                    empresa_id = empresas_dict[datos_nuevos["empresa_nombre"]]
                else:
                    st.error(f"⚠️ Empresa '{datos_nuevos['empresa_nombre']}' no encontrada.")
                    return
            else:
                empresa_id = session_state.user.get("empresa_id") if session_state.role == "gestor" else None

            tutor_id = None
            if datos_nuevos.get("tutor_nombre"):
                if datos_nuevos["tutor_nombre"] in tutores_dict:
                    tutor_id = tutores_dict[datos_nuevos["tutor_nombre"]]
                else:
                    st.error(f"⚠️ Tutor '{datos_nuevos['tutor_nombre']}' no encontrado.")
                    return

            fecha_inicio = datos_nuevos.get("fecha_inicio_prevista") or datos_nuevos.get("fecha_inicio")
            fecha_fin_prevista = datos_nuevos.get("fecha_fin_prevista")

            if fecha_inicio and fecha_fin_prevista and fecha_inicio > fecha_fin_prevista:
                st.error("⚠️ La fecha de inicio no puede ser posterior a la fecha de fin prevista.")
                return

            payload = {
                "codigo_grupo": datos_nuevos["codigo_grupo"],
                "accion_formativa_id": accion_formativa_id,
                "empresa_id": empresa_id,
                "tutor_id": tutor_id,
                "fecha_inicio": fecha_inicio,
                "fecha_fin_prevista": fecha_fin_prevista,
                "n_participantes_previstos": datos_nuevos.get("n_participantes_previstos"),
                "estado": datos_nuevos.get("estado"),
                "observaciones": datos_nuevos.get("observaciones")
            }

            res = supabase.table("grupos").insert(payload).execute()
            if res.data:
                st.success("✅ Grupo creado correctamente.")
                st.rerun()
            else:
                st.error("⚠️ No se pudo crear el grupo.")
        except Exception as e:
            st.error(f"⚠️ Error al crear grupo: {e}")

    # =========================
    # Configuración de campos para listado_con_ficha
    # =========================
    campos_select = {
        "accion_nombre": acciones_opciones,
        "empresa_nombre": empresas_opciones,
        "tutor_nombre": tutores_opciones,
        "estado": ["En preparación", "En curso", "Finalizado", "Cancelado", "Pausado"]
    }

    campos_readonly = ["id", "created_at"]

    campos_help = {
        "codigo_grupo": "Código único del grupo (obligatorio)",
        "accion_nombre": "Acción formativa asignada (obligatorio)",
        "empresa_nombre": "Empresa a la que pertenece el grupo",
        "tutor_nombre": "Tutor asignado al grupo",
        "fecha_inicio_prevista": "Fecha prevista de inicio del grupo",
        "fecha_fin_prevista": "Fecha prevista de finalización del grupo",
        "n_participantes_previstos": "Número de participantes previstos",
        "estado": "Estado actual del grupo",
        "observaciones": "Notas adicionales sobre el grupo"
    }

    campos_obligatorios = ["codigo_grupo", "accion_nombre"]

    campos_textarea = {
        "observaciones": {"label": "Observaciones", "height": 100}
    }

    # =========================
    # Mostrar interfaz principal
    # =========================
    if df_filtered.empty:
        if df_grupos.empty:
            st.info("ℹ️ No hay grupos registrados en el sistema.")
        else:
            st.warning("🔍 No se encontraron grupos que coincidan con los filtros aplicados.")
    
    # Mostrar el listado con ficha
    listado_con_ficha(
        df=df_filtered,
        columnas_visibles=["codigo_grupo", "accion_nombre", "empresa_nombre", "fecha_inicio_prevista", "fecha_fin_prevista", "n_participantes_previstos", "estado"],
        titulo="Grupo",
        on_save=guardar_grupo,
        on_create=crear_grupo,
        on_delete=eliminar_grupo,
        id_col="id",
        campos_select=campos_select,
        campos_readonly=campos_readonly,
        campos_help=campos_help,
        campos_obligatorios=campos_obligatorios,
        campos_textarea=campos_textarea,
        search_columns=["codigo_grupo", "accion_nombre", "empresa_nombre"]
    )

    # =========================
    # Sección de Participantes
    # =========================
    if not df_grupos.empty:
        st.divider()
        st.subheader("👥 Gestión de Participantes por Grupo")
        
        # Seleccionar grupo
        grupo_selected = st.selectbox(
            "Seleccionar grupo para gestionar participantes",
            options=[""] + sorted(df_grupos["codigo_grupo"].dropna().unique().tolist()),
            format_func=lambda x: f"{x}" if x else "Selecciona un grupo"
        )
        
        if grupo_selected:
            # Obtener información del grupo seleccionado
            grupo_info = df_grupos[df_grupos["codigo_grupo"] == grupo_selected].iloc[0]
            grupo_id = grupo_info["id"]
            
            # Mostrar información del grupo
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Acción Formativa", grupo_info["accion_nombre"])
            with col2:
                st.metric("Fecha Inicio", formato_fecha(grupo_info["fecha_inicio_prevista"]))
            with col3:
                st.metric("Fecha Fin", formato_fecha(grupo_info["fecha_fin_prevista"]))
            
            # Obtener participantes del grupo
            participantes_grupo = df_participantes[df_participantes["grupo_id"] == grupo_id]
            
            # Mostrar participantes
            if not participantes_grupo.empty:
                st.write(f"**Participantes asignados al grupo ({len(participantes_grupo)}):**")
                
                # Mostrar tabla de participantes
                cols_display = ["nombre", "apellidos", "dni", "email", "telefono", "asistencia", "evaluacion"]
                st.dataframe(participantes_grupo[cols_display])
                
                # Botón para gestionar asistencia y evaluación
                if st.button("📝 Gestionar Asistencia y Evaluación"):
                    st.session_state["tab_asistencia"] = True
                
                # Formulario de evaluación
                if st.session_state.get("tab_asistencia", False):
                    with st.form("form_evaluacion"):
                        st.write("### 📊 Asistencia y Evaluación")
                        
                        # Crear campos para cada participante
                        datos_evaluacion = {}
                        
                        for i, row in participantes_grupo.iterrows():
                            st.write(f"**{row['nombre']} {row['apellidos']}** ({row['dni']})")
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                asistencia = st.number_input(
                                    "% Asistencia",
                                    min_value=0.0,
                                    max_value=100.0,
                                    value=float(row["asistencia"] or 0.0),
                                    key=f"asistencia_{row['id']}"
                                )
                            
                            with col2:
                                evaluacion = st.number_input(
                                    "Calificación",
                                    min_value=0.0,
                                    max_value=100.0,
                                    value=float(row["evaluacion"] or 0.0),
                                    key=f"evaluacion_{row['id']}"
                                )
                            
                            datos_evaluacion[row["id"]] = {
                                "asistencia": asistencia,
                                "evaluacion": evaluacion
                            }
                            
                            st.divider()
                        
                        submit = st.form_submit_button("💾 Guardar Evaluaciones")
                        
                        if submit:
                            # Actualizar cada participante
                            for participante_id, datos in datos_evaluacion.items():
                                try:
                                    supabase.table("participantes").update({
                                        "asistencia": datos["asistencia"],
                                        "evaluacion": datos["evaluacion"],
                                        "updated_at": datetime.now().isoformat()
                                    }).eq("id", participante_id).execute()
                                except Exception as e:
                                    st.error(f"⚠️ Error al actualizar participante {participante_id}: {e}")
                            
                            st.success("✅ Evaluaciones guardadas correctamente.")
                            st.rerun()
            else:
                st.info("ℹ️ No hay participantes asignados a este grupo.")
                
                # Opción para asignar participantes
                st.write("### Asignar Participantes al Grupo")
                
                # Obtener participantes disponibles (sin grupo o de la misma empresa)
                if session_state.role == "admin":
                    # Administrador puede ver todos los participantes
                    participantes_disponibles = df_participantes[
                        (df_participantes["grupo_id"].isna()) | 
                        (df_participantes["grupo_id"] == grupo_id)
                    ]
                else:
                    # Gestor solo ve participantes de su empresa
                    empresa_id = session_state.user.get("empresa_id")
                    participantes_disponibles = df_participantes[
                        ((df_participantes["grupo_id"].isna()) | 
                        (df_participantes["grupo_id"] == grupo_id)) &
                        (df_participantes["empresa_id"] == empresa_id)
                    ]
                
                if not participantes_disponibles.empty:
                    # Crear multiselect para seleccionar participantes
                    participantes_seleccionados = st.multiselect(
                        "Selecciona participantes para asignar al grupo",
                        options=participantes_disponibles["id"].tolist(),
                        format_func=lambda x: f"{participantes_disponibles[participantes_disponibles['id'] == x]['nombre'].iloc[0]} {participantes_disponibles[participantes_disponibles['id'] == x]['apellidos'].iloc[0]} ({participantes_disponibles[participantes_disponibles['id'] == x]['dni'].iloc[0]})"
                    )
                    
                    if participantes_seleccionados and st.button("✅ Asignar Participantes"):
                        # Asignar participantes al grupo
                        for participante_id in participantes_seleccionados:
                            try:
                                # Actualizar participante
                                supabase.table("participantes").update({
                                    "grupo_id": grupo_id,
                                    "updated_at": datetime.now().isoformat()
                                }).eq("id", participante_id).execute()
                            except Exception as e:
                                st.error(f"⚠️ Error al asignar participante {participante_id}: {e}")
                        
                        st.success("✅ Participantes asignados correctamente.")
                        st.rerun()
                else:
                    st.warning("⚠️ No hay participantes disponibles para asignar.")
            
            # Subir listado de participantes por DNI
            st.divider()
            st.write("### 📥 Importar Participantes por DNI")
            st.caption("Asigna participantes existentes mediante un listado de DNIs.")
            
            dnis_input = st.text_area(
                "Introduce los DNIs separados por comas, espacios o líneas nuevas",
                height=100
            )
            
            if dnis_input and st.button("🔍 Buscar y Asignar Participantes"):
                # Procesar DNIs
                dnis_raw = dnis_input.replace(",", " ").replace(";", " ").split()
                dnis = [dni.strip().upper() for dni in dnis_raw if dni.strip()]
                
                if not dnis:
                    st.error("⚠️ No se encontraron DNIs válidos.")
                else:
                    # Verificar DNIs
                    dnis_validos = [dni for dni in dnis if validar_dni_cif(dni)]
                    dnis_invalidos = set(dnis) - set(dnis_validos)
                    
                    if dnis_invalidos:
                        st.warning(f"⚠️ DNIs inválidos detectados: {', '.join(dnis_invalidos)}")
                    
                    # Buscar participantes por DNI
                    encontrados = []
                    no_encontrados = []
                    ya_asignados = []
                    asignados = []
                    
                    for dni in dnis_validos:
                        # Buscar participante
                        participante_res = supabase.table("participantes").select("id, nombre, apellidos, grupo_id").eq("dni", dni).execute()
                        
                        if not participante_res.data:
                            no_encontrados.append(dni)
                            continue
                        
                        participante = participante_res.data[0]
                        
                        # Verificar si ya está asignado al grupo
                        if participante["grupo_id"] == grupo_id:
                            ya_asignados.append(f"{participante['nombre']} {participante['apellidos']} ({dni})")
                            continue
                        
                        # Asignar al grupo
                        try:
                            supabase.table("participantes").update({
                                "grupo_id": grupo_id,
                                "updated_at": datetime.now().isoformat()
                            }).eq("id", participante["id"]).execute()
                            
                            asignados.append(f"{participante['nombre']} {participante['apellidos']} ({dni})")
                        except Exception as e:
                            st.error(f"⚠️ Error al asignar participante con DNI {dni}: {e}")
                    
                    # Mostrar resultados
                    if asignados:
                        st.success(f"✅ {len(asignados)} participantes asignados correctamente.")
                    
                    if ya_asignados:
                        st.info(f"ℹ️ {len(ya_asignados)} participantes ya estaban asignados al grupo.")
                    
                    if no_encontrados:
                        st.warning(f"⚠️ {len(no_encontrados)} DNIs no encontrados en el sistema: {', '.join(no_encontrados)}")
                    
                    if asignados:
                        st.rerun()
