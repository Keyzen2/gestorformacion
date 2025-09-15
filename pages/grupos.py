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

    grupos_service = get_grupos_service(supabase, session_state)

    # =========================
    # CARGAR DATOS PRINCIPALES
    # =========================
    try:
        df_grupos = grupos_service.get_grupos_completos()
        acciones_dict = grupos_service.get_acciones_dict()
        empresas_dict = grupos_service.get_empresas_dict() if session_state.role == "admin" else {}
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # =========================
    # PARTE SUPERIOR: KPIs + FILTROS + TABLA
    # =========================
    mostrar_kpis_grupos(df_grupos)
    df_filtered = mostrar_filtros_busqueda(df_grupos)
    mostrar_tabla_informativa(df_filtered)

    # =========================
    # SELECTOR GLOBAL DE GRUPO
    # =========================
    st.divider()
    grupo_seleccionado = mostrar_selector_grupo(df_grupos)

    # =========================
    # SECCIONES EN UNA SOLA PÁGINA
    # =========================
    st.divider()
    st.header("📋 Datos Básicos FUNDAE")
    mostrar_seccion_descripcion(supabase, session_state, grupos_service, acciones_dict, empresas_dict, grupo_seleccionado)

    if grupo_seleccionado:
        st.divider()
        st.header("👨‍🏫 Tutores y Centro Gestor")
        mostrar_seccion_tutores_centro(supabase, session_state, grupos_service, grupo_seleccionado)

        st.divider()
        st.header("🏢 Empresas Participantes")
        mostrar_seccion_empresas(supabase, session_state, grupos_service, grupo_seleccionado, empresas_dict)

        st.divider()
        st.header("👥 Participantes del Grupo")
        mostrar_seccion_participantes(supabase, session_state, grupos_service, grupo_seleccionado)

        st.divider()
        st.header("💰 Costes FUNDAE")
        mostrar_seccion_costes_fundae(supabase, session_state, grupos_service, grupo_seleccionado)


# =========================
# KPIs + FILTROS + TABLA
# =========================

def mostrar_kpis_grupos(df_grupos):
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
    st.markdown("### 🔍 Filtros y Búsqueda")
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

    return df_filtered


def mostrar_tabla_informativa(df_filtered):
    st.markdown("### 📊 Vista General de Grupos")
    if df_filtered.empty:
        st.info("ℹ️ No hay grupos para mostrar.")
        return

    columnas_mostrar = [
        "codigo_grupo", "accion_nombre", "modalidad", 
        "fecha_inicio", "fecha_fin_prevista", "localidad", 
        "n_participantes_previstos"
    ]
    columnas_existentes = [col for col in columnas_mostrar if col in df_filtered.columns]

    st.dataframe(
        df_filtered[columnas_existentes],
        use_container_width=True,
        hide_index=True
    )

    export_csv(df_filtered, filename="grupos.csv")


def mostrar_selector_grupo(df_grupos):
    st.markdown("### 🎯 Selector de Grupo")

    if df_grupos.empty:
        st.info("ℹ️ No hay grupos disponibles. Crea uno nuevo en la sección de Datos Básicos.")
        return None

    opciones_grupos = [""] + df_grupos["codigo_grupo"].tolist()
    grupo_codigo_sel = st.selectbox(
        "Selecciona un grupo para gestionar:",
        options=opciones_grupos,
        key="grupo_selector_global",
        help="Escoge un grupo existente para editar o gestionar sus componentes"
    )

    if grupo_codigo_sel:
        grupo_info = df_grupos[df_grupos["codigo_grupo"] == grupo_codigo_sel]
        if not grupo_info.empty:
            grupo_id = grupo_info.iloc[0]["id"]

            with st.expander("ℹ️ Información del Grupo Seleccionado", expanded=False):
                col1, col2, col3 = st.columns(3)
                grupo_data = grupo_info.iloc[0]

                with col1:
                    st.write(f"**Código:** {grupo_data.get('codigo_grupo', '')}")
                    st.write(f"**Modalidad:** {grupo_data.get('modalidad', '')}")

                with col2:
                    st.write(f"**Fecha Inicio:** {grupo_data.get('fecha_inicio', '')}")
                    st.write(f"**Acción:** {grupo_data.get('accion_nombre', 'No asignada')}")

                with col3:
                    st.write(f"**Participantes Previstos:** {grupo_data.get('n_participantes_previstos', 0)}")
                    st.write(f"**Localidad:** {grupo_data.get('localidad', '')}")

            return grupo_id

    return None
# =========================
# SECCIÓN 1: DATOS BÁSICOS FUNDAE
# =========================

def mostrar_seccion_descripcion(supabase, session_state, grupos_service, acciones_dict, empresas_dict, grupo_id):
    """Formulario unificado para crear o editar grupo."""
    es_edicion = grupo_id is not None
    titulo = "✏️ Editar Grupo" if es_edicion else "➕ Crear Nuevo Grupo"
    st.subheader(titulo)

    # Datos actuales si es edición
    datos_grupo_actual = {}
    if es_edicion:
        try:
            resultado = supabase.table("grupos").select("*").eq("id", grupo_id).execute()
            if resultado.data:
                datos_grupo_actual = resultado.data[0]
        except Exception as e:
            st.error(f"❌ Error al cargar datos del grupo: {e}")
            return

    with st.form("form_datos_basicos"):
        col1, col2 = st.columns(2)

        with col1:
            codigo_grupo = st.text_input(
                "Código de Grupo *",
                value=datos_grupo_actual.get("codigo_grupo", ""),
                help="Código único identificativo (máx. 50 caracteres)",
                disabled=es_edicion
            )

            # Acción formativa
            accion_actual = ""
            if es_edicion and datos_grupo_actual.get("accion_formativa_id"):
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

            localidad = st.text_input("Localidad *", value=datos_grupo_actual.get("localidad", ""))
            provincia = st.text_input("Provincia", value=datos_grupo_actual.get("provincia", ""))

        with col2:
            fecha_inicio = st.date_input(
                "Fecha de Inicio *",
                value=datetime.fromisoformat(datos_grupo_actual["fecha_inicio"]).date()
                if datos_grupo_actual.get("fecha_inicio") else None
            )

            fecha_fin_prevista = st.date_input(
                "Fecha Fin Prevista *",
                value=datetime.fromisoformat(datos_grupo_actual["fecha_fin_prevista"]).date()
                if datos_grupo_actual.get("fecha_fin_prevista") else None
            )

            n_participantes_previstos = st.number_input(
                "Participantes Previstos *",
                min_value=1, max_value=30,
                value=int(datos_grupo_actual.get("n_participantes_previstos") or 0),
                help="Entre 1 y 30 participantes (requisito FUNDAE)"
            )

            cp = st.text_input("Código Postal", value=datos_grupo_actual.get("cp", ""))
            lugar_imparticion = st.text_area(
                "Lugar de Impartición",
                value=datos_grupo_actual.get("lugar_imparticion", ""),
                help="Dirección completa del lugar de formación"
            )

        # =========================
        # HORARIOS (4 campos siempre)
        # =========================
        st.markdown("### 🕐 Horarios de Impartición")
        m_inicio, m_fin, t_inicio, t_fin, dias_actuales = grupos_service.parse_horario(datos_grupo_actual.get("horario", ""))

        col_h1, col_h2 = st.columns(2)
        with col_h1:
            m_inicio_input = st.time_input("Mañana - Inicio", value=m_inicio or time(9, 0))
            t_inicio_input = st.time_input("Tarde - Inicio", value=t_inicio or time(15, 0))
        with col_h2:
            m_fin_input = st.time_input("Mañana - Fin", value=m_fin or time(13, 0))
            t_fin_input = st.time_input("Tarde - Fin", value=t_fin or time(19, 0))

        st.markdown("**📅 Días de Impartición**")
        dias_cols = st.columns(7)
        dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        dias_seleccionados = {}
        for i, dia in enumerate(dias_nombres):
            with dias_cols[i]:
                default_value = dia in dias_actuales if dias_actuales else (i < 5)
                dias_seleccionados[dia] = st.checkbox(dia, value=default_value)

        # Observaciones
        observaciones = st.text_area("Observaciones", value=datos_grupo_actual.get("observaciones", ""))

        submitted = st.form_submit_button("💾 Guardar Datos Básicos", use_container_width=True)

        if submitted:
            errores = []
            if not codigo_grupo:
                errores.append("El código de grupo es obligatorio")
            if not accion_sel:
                errores.append("Debes seleccionar una acción formativa")
            if not localidad:
                errores.append("La localidad es obligatoria")
            if not fecha_inicio or not fecha_fin_prevista:
                errores.append("Las fechas de inicio y fin prevista son obligatorias")
            if fecha_inicio and fecha_fin_prevista and fecha_inicio >= fecha_fin_prevista:
                errores.append("La fecha de fin debe ser posterior a la de inicio")

            if not es_edicion:
                codigo_existe = supabase.table("grupos").select("id").eq("codigo_grupo", codigo_grupo).execute()
                if codigo_existe.data:
                    errores.append("Ya existe un grupo con ese código")

            dias_elegidos = [dia for dia, seleccionado in dias_seleccionados.items() if seleccionado]
            if not dias_elegidos:
                errores.append("Debes seleccionar al menos un día de la semana")

            if errores:
                for error in errores:
                    st.error(f"⚠️ {error}")
                return

            horario_completo = grupos_service.build_horario_string(
                m_inicio_input, m_fin_input, t_inicio_input, t_fin_input, dias_elegidos
            )

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

            if session_state.role == "gestor":
                datos_grupo["empresa_id"] = session_state.user.get("empresa_id")

            tipo_validacion = "inicio"
            es_valido, errores_fundae = grupos_service.validar_grupo_fundae(datos_grupo, tipo_validacion)
            if not es_valido:
                for error in errores_fundae:
                    st.error(f"❌ {error}")
                return

            try:
                if es_edicion:
                    if grupos_service.update_grupo(grupo_id, datos_grupo):
                        st.success("✅ Grupo actualizado correctamente.")
                        st.rerun()
                else:
                    exito, nuevo_grupo_id = grupos_service.create_grupo_completo(datos_grupo)
                    if exito:
                        st.success("✅ Grupo creado exitosamente.")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ Error al crear el grupo.")
            except Exception as e:
                st.error(f"❌ Error al guardar grupo: {e}")


# =========================
# SECCIÓN 2: FINALIZACIÓN DE GRUPO
# =========================

def mostrar_seccion_finalizacion(supabase, session_state, grupos_service, grupo_id):
    """Formulario separado para finalización si fecha prevista ya pasó."""
    try:
        grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute()
        if not grupo.data:
            return
        datos = grupo.data[0]
    except Exception:
        return

    if not grupos_service.fecha_pasada(datos.get("fecha_fin_prevista", "")):
        return

    st.subheader("🏁 Finalización del Grupo")
    with st.form("form_finalizacion"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            fecha_fin = st.date_input(
                "Fecha Fin Real *",
                value=datetime.fromisoformat(datos["fecha_fin"]).date() if datos.get("fecha_fin") else None
            )
        with col2:
            n_finalizados = st.number_input(
                "Finalizados *", min_value=0, value=int(datos.get("n_participantes_finalizados") or 0)
            )
        with col3:
            n_aptos = st.number_input("Aptos *", min_value=0, value=int(datos.get("n_aptos") or 0))
        with col4:
            n_no_aptos = st.number_input("No Aptos *", min_value=0, value=int(datos.get("n_no_aptos") or 0))

        if n_aptos + n_no_aptos != n_finalizados:
            st.error("⚠️ La suma de Aptos y No Aptos debe ser igual a Finalizados")

        submitted = st.form_submit_button("💾 Guardar Finalización", use_container_width=True)
        if submitted:
            if not fecha_fin:
                st.error("La fecha fin real es obligatoria")
                return
            if n_aptos + n_no_aptos != n_finalizados:
                st.error("La suma de aptos y no aptos debe coincidir con finalizados")
                return

            datos_update = {
                "fecha_fin": fecha_fin.isoformat(),
                "n_participantes_finalizados": n_finalizados,
                "n_aptos": n_aptos,
                "n_no_aptos": n_no_aptos,
                "updated_at": datetime.utcnow().isoformat()
            }

            es_valido, errores_fundae = grupos_service.validar_grupo_fundae(datos_update, "finalizacion")
            if not es_valido:
                for error in errores_fundae:
                    st.error(f"❌ {error}")
                return

            if grupos_service.update_grupo(grupo_id, datos_update):
                st.success("✅ Finalización guardada correctamente.")
                st.rerun()
# =========================
# SECCIÓN 3: TUTORES Y CENTRO GESTOR
# =========================

def mostrar_seccion_tutores_centro(supabase, session_state, grupos_service, grupo_id):
    st.subheader("👨‍🏫 Tutores Asignados")

    df_tutores_grupo = grupos_service.get_tutores_grupo(grupo_id)
    if not df_tutores_grupo.empty:
        tutores_display = []
        for _, row in df_tutores_grupo.iterrows():
            tutor_data = row.get("tutor", {}) or {}
            tutores_display.append({
                "id": row.get("id") or "",
                "nombre": f"{tutor_data.get('nombre', '')} {tutor_data.get('apellidos', '')}".strip(),
                "email": tutor_data.get("email", ""),
                "especialidad": tutor_data.get("especialidad", "")
            })

        if tutores_display:
            st.dataframe(
                pd.DataFrame(tutores_display)[["nombre", "email", "especialidad"]],
                use_container_width=True, hide_index=True
            )

            with st.expander("🗑️ Quitar Tutores"):
                tutores_a_quitar = st.multiselect(
                    "Selecciona tutores a quitar:",
                    options=[t["nombre"] for t in tutores_display]
                )
                if tutores_a_quitar and st.button("Confirmar Eliminación", type="secondary"):
                    try:
                        for nombre_tutor in tutores_a_quitar:
                            for tutor in tutores_display:
                                if tutor["nombre"] == nombre_tutor:
                                    grupos_service.delete_tutor_grupo(tutor["id"])
                        st.success("✅ Tutores eliminados correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al eliminar tutores: {e}")
    else:
        st.info("ℹ️ No hay tutores asignados.")

    with st.expander("➕ Añadir Tutores"):
        try:
            df_tutores_disponibles = grupos_service.get_tutores_completos()
            if not df_tutores_disponibles.empty:
                tutores_asignados_ids = set()
                if not df_tutores_grupo.empty:
                    for _, row in df_tutores_grupo.iterrows():
                        tutor_data = row.get("tutor", {}) or {}
                        tutores_asignados_ids.add(tutor_data.get("id") or "")

                tutores_disponibles = df_tutores_disponibles[
                    ~df_tutores_disponibles["id"].isin(tutores_asignados_ids)
                ]

                if not tutores_disponibles.empty:
                    opciones_tutores = {
                        row["nombre_completo"]: row["id"]
                        for _, row in tutores_disponibles.iterrows()
                    }
                    tutores_nuevos = st.multiselect("Seleccionar tutores:", options=list(opciones_tutores.keys()))
                    if tutores_nuevos and st.button("➕ Asignar Tutores", type="primary"):
                        try:
                            for nombre_tutor in tutores_nuevos:
                                grupos_service.create_tutor_grupo(grupo_id, opciones_tutores[nombre_tutor])
                            st.success("✅ Tutores asignados.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al asignar tutores: {e}")
                else:
                    st.info("ℹ️ Todos los tutores disponibles ya están asignados.")
            else:
                st.info("ℹ️ No hay tutores disponibles.")
        except Exception as e:
            st.error(f"❌ Error al cargar tutores: {e}")

    # =========================
    # CENTRO GESTOR
    # =========================
    st.subheader("🏢 Centro Gestor")
    try:
        grupo_info = supabase.table("grupos").select("modalidad").eq("id", grupo_id).execute()
        modalidad = grupo_info.data[0]["modalidad"] if grupo_info.data else "PRESENCIAL"
        centro_obligatorio = modalidad in ["TELEFORMACION", "MIXTA"]
        if centro_obligatorio:
            st.warning("⚠️ Centro Gestor obligatorio para modalidad TELEFORMACION/MIXTA")
    except Exception as e:
        st.error(f"❌ Error al verificar modalidad: {e}")
        return

    centro_actual = grupos_service.get_centro_gestor_grupo(grupo_id)
    if centro_actual and centro_actual.get("centro"):
        centro_data = centro_actual["centro"]
        st.success(f"✅ Centro asignado: {centro_data.get('razon_social', '')}")
        if st.button("🗑️ Desasignar Centro", type="secondary"):
            if grupos_service.unassign_centro_gestor_de_grupo(grupo_id):
                st.success("✅ Centro desasignado.")
                st.rerun()
    else:
        st.info("ℹ️ No hay centro gestor asignado.")

    with st.expander("🏢 Gestionar Centro Gestor"):
        tab1, tab2 = st.tabs(["📋 Asignar Existente", "➕ Crear y Asignar"])
        with tab1:
            df_centros = grupos_service.get_centros_para_grupo(grupo_id)
            if not df_centros.empty:
                opciones_centros = {
                    f"{row['razon_social']} - {row['localidad']}": row["id"]
                    for _, row in df_centros.iterrows()
                }
                centro_sel = st.selectbox("Seleccionar centro:", options=[""] + list(opciones_centros.keys()))
                if centro_sel and st.button("🔗 Asignar Centro", type="primary"):
                    if grupos_service.assign_centro_gestor_a_grupo(grupo_id, opciones_centros[centro_sel]):
                        st.success("✅ Centro asignado.")
                        st.rerun()
            else:
                st.info("ℹ️ No hay centros disponibles.")
        with tab2:
            with st.form("crear_centro_gestor"):
                col1, col2 = st.columns(2)
                with col1:
                    razon_social = st.text_input("Razón Social *")
                    telefono = st.text_input("Teléfono *")
                    domicilio = st.text_input("Domicilio *")
                with col2:
                    localidad = st.text_input("Localidad *")
                    cp = st.text_input("Código Postal *", help="5 dígitos o 99999")
                submit = st.form_submit_button("🏢 Crear y Asignar Centro")
                if submit:
                    if not razon_social or not telefono or not domicilio or not localidad or not cp:
                        st.error("⚠️ Todos los campos obligatorios deben completarse")
                        return
                    empresa_id = session_state.user.get("empresa_id") if session_state.role == "gestor" else None
                    datos_centro = {
                        "razon_social": razon_social,
                        "telefono": telefono,
                        "domicilio": domicilio,
                        "localidad": localidad,
                        "codigo_postal": cp
                    }
                    ok, centro_id = grupos_service.create_centro_gestor(empresa_id, datos_centro)
                    if ok and grupos_service.assign_centro_gestor_a_grupo(grupo_id, centro_id):
                        st.success("✅ Centro creado y asignado.")
                        st.rerun()


# =========================
# SECCIÓN 4: EMPRESAS
# =========================

def mostrar_seccion_empresas(supabase, session_state, grupos_service, grupo_id, empresas_dict):
    st.subheader("🏢 Empresas Participantes")
    if session_state.role == "gestor":
        st.info("ℹ️ Como gestor, tu empresa se vincula automáticamente.")

    df_empresas_grupo = grupos_service.get_empresas_grupo(grupo_id)
    if not df_empresas_grupo.empty:
        empresas_display = []
        for _, row in df_empresas_grupo.iterrows():
            empresa_data = row.get("empresa", {}) or {}
            empresas_display.append({
                "id": row.get("id") or "",
                "nombre": empresa_data.get("nombre", ""),
                "cif": empresa_data.get("cif", ""),
                "fecha_asignacion": row.get("fecha_asignacion", "")
            })
        st.dataframe(
            pd.DataFrame(empresas_display)[["nombre", "cif", "fecha_asignacion"]],
            use_container_width=True, hide_index=True
        )

        if session_state.role == "admin":
            with st.expander("🗑️ Quitar Empresas"):
                empresas_a_quitar = st.multiselect(
                    "Selecciona empresas a quitar:",
                    options=[e["nombre"] for e in empresas_display]
                )
                if empresas_a_quitar and st.button("Confirmar Eliminación", type="secondary"):
                    try:
                        for nombre_empresa in empresas_a_quitar:
                            for empresa in empresas_display:
                                if empresa["nombre"] == nombre_empresa:
                                    grupos_service.delete_empresa_grupo(empresa["id"])
                        st.success("✅ Empresas eliminadas.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al eliminar empresas: {e}")
    else:
        st.info("ℹ️ No hay empresas asignadas.")

    if session_state.role == "admin":
        with st.expander("➕ Añadir Empresas"):
            if empresas_dict:
                asignadas = {e["nombre"] for e in empresas_display}
                disponibles = {
                    n: i for n, i in empresas_dict.items() if n not in asignadas
                }
                empresas_nuevas = st.multiselect("Seleccionar empresas:", options=list(disponibles.keys()))
                if empresas_nuevas and st.button("➕ Asignar Empresas", type="primary"):
                    try:
                        for nombre_empresa in empresas_nuevas:
                            grupos_service.create_empresa_grupo(grupo_id, disponibles[nombre_empresa])
                        st.success(f"✅ {len(empresas_nuevas)} empresas asignadas.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al asignar empresas: {e}")
            else:
                st.info("ℹ️ No hay empresas disponibles en el sistema.")
# =========================
# SECCIÓN 5: PARTICIPANTES
# =========================

def mostrar_seccion_participantes(supabase, session_state, grupos_service, grupo_id):
    st.subheader("👥 Participantes del Grupo")

    df_participantes = grupos_service.get_participantes_grupo(grupo_id)

    if not df_participantes.empty:
        columnas_mostrar = ["nif", "nombre", "apellidos", "email", "telefono"]
        columnas_existentes = [c for c in columnas_mostrar if c in df_participantes.columns]
        st.dataframe(
            df_participantes[columnas_existentes],
            use_container_width=True, hide_index=True
        )

        with st.expander("🗑️ Desasignar Participantes"):
            participantes_a_quitar = st.multiselect(
                "Selecciona participantes:",
                options=[f"{row['nif']} - {row['nombre']} {row['apellidos']}"
                         for _, row in df_participantes.iterrows()]
            )
            if participantes_a_quitar and st.button("Confirmar Desasignación", type="secondary"):
                try:
                    for p_str in participantes_a_quitar:
                        nif = p_str.split(" - ")[0]
                        row = df_participantes[df_participantes["nif"] == nif]
                        if not row.empty:
                            grupos_service.desasignar_participante_de_grupo(row.iloc[0].get("id") or "")
                    st.success("✅ Participantes desasignados.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al desasignar: {e}")
    else:
        st.info("ℹ️ No hay participantes asignados.")

    st.markdown("### ➕ Asignar Participantes")

    tab1, tab2 = st.tabs(["📋 Selección Individual", "📊 Importación Masiva"])

    # ---- INDIVIDUAL ----
    with tab1:
        df_disponibles = grupos_service.get_participantes_disponibles(grupo_id)
        if not df_disponibles.empty:
            opciones = {
                f"{row['nif']} - {row['nombre']} {row['apellidos']}": row["id"]
                for _, row in df_disponibles.iterrows()
            }
            seleccionados = st.multiselect("Seleccionar participantes:", options=list(opciones.keys()))
            if seleccionados and st.button("➕ Asignar Participantes", type="primary"):
                try:
                    for p_str in seleccionados:
                        grupos_service.asignar_participante_a_grupo(opciones[p_str], grupo_id)
                    st.success(f"✅ {len(seleccionados)} participantes asignados.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al asignar: {e}")
        else:
            st.info("ℹ️ No hay participantes disponibles.")

    # ---- MASIVO (EXCEL) ----
    with tab2:
        st.markdown("**Instrucciones:** sube un Excel con una columna 'dni' o 'nif'.")
        file = st.file_uploader("Subir archivo Excel", type=["xlsx"], key="excel_participantes")
        if file:
            try:
                df_import = pd.read_excel(file)
                col_nif = None
                for c in ["dni", "nif", "DNI", "NIF"]:
                    if c in df_import.columns:
                        col_nif = c
                        break
                if not col_nif:
                    st.error("⚠️ El archivo debe contener columna 'dni' o 'nif'.")
                else:
                    st.dataframe(df_import.head(), use_container_width=True)
                    if st.button("🚀 Procesar Archivo Excel", type="primary"):
                        nifs_import = [str(v).strip() for v in df_import[col_nif] if pd.notna(v)]
                        nifs_validos = [n for n in nifs_import if validar_dni_cif(n)]
                        nifs_invalidos = set(nifs_import) - set(nifs_validos)
                        if nifs_invalidos:
                            st.warning(f"⚠️ NIFs inválidos: {', '.join(list(nifs_invalidos)[:5])}")

                        df_disp = grupos_service.get_participantes_disponibles(grupo_id)
                        disponibles = {p["nif"]: p["id"] for _, p in df_disp.iterrows()}

                        asignados, errores = 0, []
                        for nif in nifs_validos:
                            pid = disponibles.get(nif)
                            if not pid:
                                errores.append(f"{nif} no encontrado o ya asignado")
                                continue
                            try:
                                grupos_service.asignar_participante_a_grupo(pid, grupo_id)
                                asignados += 1
                            except Exception as e:
                                errores.append(f"{nif} - Error: {str(e)}")

                        if asignados:
                            st.success(f"✅ {asignados} participantes asignados.")
                        if errores:
                            st.warning(f"⚠️ {len(errores)} incidencias:")
                            for err in errores[:10]:
                                st.warning(f"• {err}")
                        if asignados:
                            st.rerun()
            except Exception as e:
                st.error(f"❌ Error al procesar archivo: {e}")
# =========================
# SECCIÓN 6: COSTES FUNDAE
# =========================

def mostrar_seccion_costes_fundae(supabase, session_state, grupos_service, grupo_id):
    st.subheader("💰 Costes FUNDAE")

    try:
        grupo_info = supabase.table("grupos").select("""
            modalidad, n_participantes_previstos,
            accion_formativa:acciones_formativas(num_horas)
        """).eq("id", grupo_id).execute()

        if not grupo_info.data:
            st.error("❌ No se pudo cargar información del grupo.")
            return

        data = grupo_info.data[0]
        modalidad = data.get("modalidad", "PRESENCIAL")
        participantes = int(data.get("n_participantes_previstos") or 0)
        horas = int((data.get("accion_formativa") or {}).get("num_horas") or 0)

    except Exception as e:
        st.error(f"❌ Error al cargar datos del grupo: {e}")
        return

    limite_boni, tarifa_max = grupos_service.calcular_limite_fundae(modalidad, horas, participantes)

    with st.expander("ℹ️ Información para Cálculo FUNDAE", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Modalidad", modalidad)
        col2.metric("Participantes", participantes)
        col3.metric("Horas", horas)
        col4.metric("Límite Bonificación", f"{limite_boni:,.2f} €")

    # ---- FORM COSTES ----
    st.markdown("### 💵 Costes del Grupo")
    costes_actuales = grupos_service.get_grupo_costes(grupo_id)

    with st.form("form_costes"):
        col1, col2 = st.columns(2)
        with col1:
            costes_directos = st.number_input("Costes Directos (€)",
                value=float(costes_actuales.get("costes_directos") or 0), min_value=0.0)
            costes_indirectos = st.number_input("Costes Indirectos (€)",
                value=float(costes_actuales.get("costes_indirectos") or 0), min_value=0.0)
            costes_organizacion = st.number_input("Costes Organización (€)",
                value=float(costes_actuales.get("costes_organizacion") or 0), min_value=0.0)
        with col2:
            costes_salariales = st.number_input("Costes Salariales (€)",
                value=float(costes_actuales.get("costes_salariales") or 0), min_value=0.0)
            cofinanciacion_privada = st.number_input("Cofinanciación Privada (€)",
                value=float(costes_actuales.get("cofinanciacion_privada") or 0), min_value=0.0)
            tarifa_hora = st.number_input("Tarifa por Hora (€)",
                value=float(costes_actuales.get("tarifa_hora") or tarifa_max),
                min_value=0.0, max_value=tarifa_max)

        total_costes = costes_directos + costes_indirectos + costes_organizacion + costes_salariales
        limite_calc = tarifa_hora * horas * participantes

        colc1, colc2 = st.columns(2)
        colc1.metric("💰 Total Costes Formación", f"{total_costes:,.2f} €")
        colc2.metric("🎯 Límite Calculado", f"{limite_calc:,.2f} €")

        validacion_ok = True
        if costes_directos > 0:
            porc_ind = (costes_indirectos / costes_directos) * 100
            if porc_ind > 30:
                st.error(f"⚠️ Indirectos {porc_ind:.1f}% superan el 30% permitido")
                validacion_ok = False
            else:
                st.success(f"✅ Indirectos {porc_ind:.1f}% dentro del límite")

        if tarifa_hora > tarifa_max:
            st.error(f"⚠️ Tarifa/hora {tarifa_hora} > {tarifa_max} permitido")
            validacion_ok = False

        obs = st.text_area("Observaciones", value=costes_actuales.get("observaciones", ""))

        submit = st.form_submit_button("💾 Guardar Costes", use_container_width=True)
        if submit and validacion_ok:
            datos = {
                "grupo_id": grupo_id,
                "costes_directos": costes_directos,
                "costes_indirectos": costes_indirectos,
                "costes_organizacion": costes_organizacion,
                "costes_salariales": costes_salariales,
                "cofinanciacion_privada": cofinanciacion_privada,
                "tarifa_hora": tarifa_hora,
                "modalidad": modalidad,
                "total_costes_formacion": total_costes,
                "limite_maximo_bonificacion": limite_calc,
                "observaciones": obs,
                "updated_at": datetime.utcnow().isoformat()
            }
            try:
                if costes_actuales:
                    if grupos_service.update_grupo_coste(grupo_id, datos):
                        st.success("✅ Costes actualizados.")
                        st.rerun()
                else:
                    datos["created_at"] = datetime.utcnow().isoformat()
                    if grupos_service.create_grupo_coste(datos):
                        st.success("✅ Costes guardados.")
                        st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar costes: {e}")

    # ---- BONIFICACIONES ----
    st.divider()
    st.markdown("### 📅 Bonificaciones Mensuales")

    df_boni = grupos_service.get_grupo_bonificaciones(grupo_id)
    if not df_boni.empty:
        st.dataframe(df_boni[["mes", "importe", "observaciones"]],
            use_container_width=True, hide_index=True)
        total_boni = float(df_boni["importe"].sum())
        disponible = limite_calc - total_boni
        col1, col2 = st.columns(2)
        col1.metric("💰 Total Bonificado", f"{total_boni:,.2f} €")
        col2.metric("💳 Disponible", f"{disponible:,.2f} €")
    else:
        st.info("ℹ️ No hay bonificaciones registradas.")
        total_boni, disponible = 0, limite_calc

    with st.expander("➕ Añadir Bonificación"):
        with st.form("form_boni"):
            col1, col2 = st.columns(2)
            with col1:
                mes = st.selectbox("Mes", [
                    "Enero","Febrero","Marzo","Abril","Mayo","Junio",
                    "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"
                ])
                importe = st.number_input("Importe (€)", min_value=0.0, max_value=disponible)
            with col2:
                obs_boni = st.text_area("Observaciones")
            submit_boni = st.form_submit_button("💰 Añadir Bonificación")
            if submit_boni:
                if importe <= 0:
                    st.error("⚠️ El importe debe ser mayor que 0")
                elif total_boni + importe > limite_calc:
                    st.error("⚠️ La suma superaría el límite")
                else:
                    datos = {
                        "grupo_id": grupo_id,
                        "mes": mes,
                        "importe": importe,
                        "observaciones": obs_boni,
                        "created_at": datetime.utcnow().isoformat()
                    }
                    if grupos_service.create_grupo_bonificacion(datos):
                        st.success("✅ Bonificación añadida.")
                        st.rerun()

    with st.expander("ℹ️ Información FUNDAE"):
        st.markdown("""
        - PRESENCIAL/MIXTA: máx 13 €/hora  
        - TELEFORMACION: máx 7.5 €/hora  
        - Costes indirectos: ≤30% directos  
        - Límite: tarifa × horas × participantes  
        """)

