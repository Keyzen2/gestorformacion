import streamlit as st
import pandas as pd
from datetime import datetime
from utils import export_csv
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha


# =========================
# MAIN
# =========================
def main(supabase, session_state):
    st.title("👥 Gestión de Grupos")
    st.caption("Creación, administración y cierre de grupos formativos según estándares FUNDAE.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    data_service = get_data_service(supabase, session_state)

    try:
        df_grupos = data_service.get_grupos_completos()
        acciones_dict = data_service.get_acciones_dict()
        empresas_dict = data_service.get_empresas_dict() if session_state.role == "admin" else {}
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # =========================
    # PARTE SUPERIOR: ESTADÍSTICAS + FILTROS + TABLA
    # =========================
    mostrar_estadisticas_grupos(df_grupos)
    df_filtered = mostrar_filtros_busqueda(df_grupos)
    mostrar_tabla_grupos(df_filtered, data_service, supabase, session_state, acciones_dict, empresas_dict)

    st.divider()

    # =========================
    # Selección global de grupo
    # =========================
    grupo_sel = st.selectbox(
        "📌 Selecciona un grupo para gestionar:",
        [""] + df_grupos["codigo_grupo"].tolist(),
        key="grupo_selector_global"
    )
    if grupo_sel:
        grupo_id = df_grupos[df_grupos["codigo_grupo"] == grupo_sel].iloc[0]["id"]
        st.session_state["grupo_actual"] = grupo_id
    else:
        st.session_state["grupo_actual"] = None

    # =========================
    # SISTEMA DE TABS
    # =========================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📝 Descripción",
        "👨‍🏫 Tutores",
        "🏢 Empresas",
        "👥 Participantes",
        "💰 Costes FUNDAE"
    ])

    with tab1:
        mostrar_tab_descripcion(supabase, session_state, data_service, acciones_dict, empresas_dict)

    if not st.session_state.get("grupo_actual"):
        st.info("Selecciona primero un grupo para habilitar las demás pestañas.")
        return

    with tab2:
        mostrar_tab_tutores(supabase, session_state, data_service)

    with tab3:
        mostrar_tab_empresas(supabase, session_state, data_service, empresas_dict)

    with tab4:
        mostrar_tab_participantes(supabase, session_state, data_service)

    with tab5:
        mostrar_tab_costes_fundae(supabase, session_state, data_service)


# =========================
# ESTADÍSTICAS Y FILTROS
# =========================
def mostrar_estadisticas_grupos(df_grupos):
    if not df_grupos.empty:
        col1, col2, col3, col4 = st.columns(4)
        hoy = datetime.now()

        activos = len(df_grupos[
            (pd.to_datetime(df_grupos["fecha_inicio"], errors="coerce") <= hoy) &
            ((df_grupos["fecha_fin"].isna()) | (pd.to_datetime(df_grupos["fecha_fin"], errors="coerce") >= hoy))
        ])
        finalizados = len(df_grupos[pd.to_datetime(df_grupos["fecha_fin"], errors="coerce") < hoy])
        proximos = len(df_grupos[pd.to_datetime(df_grupos["fecha_inicio"], errors="coerce") > hoy])

        col1.metric("👥 Total Grupos", len(df_grupos))
        col2.metric("🟢 Activos", activos)
        col3.metric("🔴 Finalizados", finalizados)
        col4.metric("📅 Próximos", proximos)


def mostrar_filtros_busqueda(df_grupos):
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2 = st.columns(2)

    with col1:
        query = st.text_input("Buscar por código o acción formativa")
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
                ((df_filtered["fecha_fin"].isna()) | (pd.to_datetime(df_filtered["fecha_fin"], errors="coerce") >= hoy))
            ]
        elif estado_filter == "Finalizados":
            df_filtered = df_filtered[pd.to_datetime(df_filtered["fecha_fin"], errors="coerce") < hoy]
        elif estado_filter == "Próximos":
            df_filtered = df_filtered[pd.to_datetime(df_filtered["fecha_inicio"], errors="coerce") > hoy]

    if not df_filtered.empty:
        export_csv(df_filtered, filename="grupos.csv")

    return df_filtered


# =========================
# TABLA DE GRUPOS
# =========================
def mostrar_tabla_grupos(df_filtered, data_service, supabase, session_state, acciones_dict, empresas_dict):
    st.markdown("### 📊 Lista de Grupos")

    if df_filtered.empty:
        st.info("ℹ️ No hay grupos para mostrar.")
        return

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

            if "n_participantes_finalizados" in datos_editados:
                n_finalizados = datos_editados.get("n_participantes_finalizados", 0)
                aptos = datos_editados.get("n_aptos", 0)
                no_aptos = datos_editados.get("n_no_aptos", 0)
                if (aptos + no_aptos) != n_finalizados:
                    st.error("⚠️ La suma de aptos y no aptos debe coincidir con finalizados.")
                    return

            datos_editados["updated_at"] = datetime.utcnow().isoformat()
            supabase.table("grupos").update(datos_editados).eq("id", grupo_id).execute()
            limpiar_cache_completo(data_service)
            st.success("✅ Grupo actualizado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar grupo: {e}")

    campos_select = {"accion_sel": list(acciones_dict.keys())}
    if session_state.role == "admin" and empresas_dict:
        campos_select["empresa_sel"] = list(empresas_dict.keys())

    df_display = df_filtered.copy()
    df_display["accion_sel"] = df_display.get("accion_nombre", "Acción no disponible")
    if session_state.role == "admin":
        df_display["empresa_sel"] = df_display.get("empresa_nombre", "Sin empresa")

    columnas_visibles = ["codigo_grupo", "accion_nombre", "modalidad", "fecha_inicio", "fecha_fin_prevista"]
    if session_state.role == "admin":
        columnas_visibles.insert(2, "empresa_nombre")

    listado_con_ficha(
        df=df_display,
        columnas_visibles=[c for c in columnas_visibles if c in df_display.columns],
        titulo="Grupo",
        on_save=guardar_grupo,
        id_col="id",
        campos_select=campos_select,
        campos_obligatorios=["codigo_grupo", "accion_sel", "modalidad", "fecha_inicio", "fecha_fin_prevista"]
    )


# =========================
# TAB DESCRIPCIÓN
# =========================
def mostrar_tab_descripcion(supabase, session_state, data_service, acciones_dict, empresas_dict):
    st.markdown("#### 📝 Crear Nuevo Grupo")
    st.caption("Formulario FUNDAE completo (sin tutores ni empresas, que se gestionan en sus pestañas).")

    with st.form("crear_grupo_fundae", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            codigo_grupo = st.text_input("Código de Grupo *")
            accion_sel = st.selectbox("Acción Formativa *", options=[""] + list(acciones_dict.keys()))
            modalidad = st.selectbox("Modalidad *", ["PRESENCIAL", "TELEFORMACION", "MIXTA"])
            lugar_imparticion = st.text_input("Lugar de Impartición *")
            localidad = st.text_input("Localidad")
            provincia = st.text_input("Provincia")
            cp = st.text_input("Código Postal")

        with col2:
            fecha_inicio = st.date_input("Fecha de Inicio *")
            fecha_fin_prevista = st.date_input("Fecha Fin Prevista *")
            n_participantes_previstos = st.number_input("Participantes Previstos *", min_value=1, max_value=200, value=10)

            st.markdown("**🕐 Horario FUNDAE**")
            add_maniana = st.checkbox("Añadir tramo de Mañana")
            if add_maniana:
                hora_m_inicio = st.time_input("Mañana - Inicio", key="m_inicio")
                hora_m_fin = st.time_input("Mañana - Fin", key="m_fin")
            else:
                hora_m_inicio = hora_m_fin = None

            add_tarde = st.checkbox("Añadir tramo de Tarde")
            if add_tarde:
                hora_t_inicio = st.time_input("Tarde - Inicio", key="t_inicio")
                hora_t_fin = st.time_input("Tarde - Fin", key="t_fin")
            else:
                hora_t_inicio = hora_t_fin = None

            dias_semana = st.multiselect("Días de impartición", ["L", "M", "X", "J", "V", "S", "D"], key="dias_semana")

        observaciones = st.text_area("Observaciones")

        empresa_sel = None
        if session_state.role == "admin":
            st.markdown("**🏢 Empresa**")
            if not empresas_dict:
                st.warning("No hay empresas disponibles.")
            else:
                empresa_sel = st.selectbox("Empresa *", options=list(empresas_dict.keys()), key="empresa_sel_descripcion")

        btn_crear = st.form_submit_button("🚀 Crear Grupo", type="primary")
        if btn_crear:
            if not codigo_grupo or not accion_sel or not modalidad or not lugar_imparticion or not fecha_inicio or not fecha_fin_prevista:
                st.error("⚠️ Todos los campos obligatorios deben estar completos.")
                return

            existe = supabase.table("grupos").select("id").eq("codigo_grupo", codigo_grupo).execute()
            if existe.data:
                st.error("⚠️ Ya existe un grupo con ese código.")
                return

            partes = []
            if hora_m_inicio and hora_m_fin:
                partes.append(f"Mañana: {hora_m_inicio.strftime('%H:%M')} - {hora_m_fin.strftime('%H:%M')}")
            if hora_t_inicio and hora_t_fin:
                partes.append(f"Tarde: {hora_t_inicio.strftime('%H:%M')} - {hora_t_fin.strftime('%H:%M')}")
            if dias_semana:
                partes.append("Días: " + "-".join(dias_semana))
            horario_str = " | ".join(partes)

            datos_grupo = {
                "codigo_grupo": codigo_grupo,
                "accion_formativa_id": acciones_dict[accion_sel],
                "modalidad": modalidad,
                "lugar_imparticion": lugar_imparticion,
                "localidad": localidad,
                "provincia": provincia,
                "cp": cp,
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin_prevista": fecha_fin_prevista.isoformat(),
                "n_participantes_previstos": n_participantes_previstos,
                "observaciones": observaciones,
                "horario": horario_str,
                "aula_virtual": modalidad in ["TELEFORMACION", "MIXTA"],
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            if session_state.role == "admin":
                if not empresa_sel:
                    st.error("⚠️ Selecciona una empresa.")
                    return
                datos_grupo["empresa_id"] = empresas_dict[empresa_sel]
            else:
                datos_grupo["empresa_id"] = session_state.user.get("empresa_id")

            res = supabase.table("grupos").insert(datos_grupo).execute()
            if res.data:
                limpiar_cache_completo(data_service)
                st.success("✅ Grupo creado correctamente.")
                st.balloons()
                st.rerun()
            else:
                st.error("❌ Error al crear grupo.")
# =========================
# TAB TUTORES
# =========================
def mostrar_tab_tutores(supabase, session_state, data_service):
    st.markdown("#### 👨‍🏫 Tutores por Grupo")
    grupo_id = st.session_state.get("grupo_actual")
    if not grupo_id:
        return

    try:
        df_asignados = data_service.get_tutores_grupo(grupo_id)
        if not df_asignados.empty:
            df_asignados["nombre"] = df_asignados["tutor"].apply(lambda x: x.get("nombre") if isinstance(x, dict) else "")
            df_asignados["apellidos"] = df_asignados["tutor"].apply(lambda x: x.get("apellidos") if isinstance(x, dict) else "")
            df_asignados["email"] = df_asignados["tutor"].apply(lambda x: x.get("email") if isinstance(x, dict) else "")
            df_asignados["especialidad"] = df_asignados["tutor"].apply(lambda x: x.get("especialidad") if isinstance(x, dict) else "")
            st.dataframe(df_asignados[["nombre", "apellidos", "email", "especialidad"]])

        df_tutores = data_service.get_tutores_por_empresa(None if session_state.role == "admin" else session_state.empresa_id)
        if not df_tutores.empty:
            opciones = {f"{r['nombre']} {r.get('apellidos','')}": r["id"] for _, r in df_tutores.iterrows()}
            nuevos = st.multiselect("Añadir tutores:", options=list(opciones.keys()), key="tutores_add")
            if nuevos and st.button("➕ Asignar", key="btn_tutores_add"):
                for nom in nuevos:
                    data_service.create_tutor_grupo(grupo_id, opciones[nom])
                limpiar_cache_completo(data_service)
                st.success("✅ Tutores asignados.")
                st.rerun()

        if not df_asignados.empty:
            rel_map = {f"{r.get('nombre','')} {r.get('apellidos','')}": r["id"] for _, r in df_asignados.iterrows()}
            quitar = st.selectbox("Quitar tutor:", [""] + list(rel_map.keys()), key="tutor_quitar")
            if quitar and st.button("❌ Quitar", key="btn_tutor_quitar"):
                data_service.delete_tutor_grupo(rel_map[quitar])
                limpiar_cache_completo(data_service)
                st.success("✅ Tutor eliminado.")
                st.rerun()
    except Exception as e:
        st.error(f"❌ Error en gestión de tutores: {e}")


# =========================
# TAB EMPRESAS
# =========================
def mostrar_tab_empresas(supabase, session_state, data_service, empresas_dict):
    st.markdown("#### 🏢 Empresas por Grupo")
    grupo_id = st.session_state.get("grupo_actual")
    if not grupo_id:
        return

    try:
        df_asignadas = data_service.get_empresas_grupo(grupo_id)
        if not df_asignadas.empty:
            df_asignadas["nombre"] = df_asignadas["empresa"].apply(lambda x: x.get("nombre") if isinstance(x, dict) else "")
            df_asignadas["cif"] = df_asignadas["empresa"].apply(lambda x: x.get("cif") if isinstance(x, dict) else "")
            st.dataframe(df_asignadas[["nombre", "cif"]])

        if session_state.role == "admin" and empresas_dict:
            nuevas = st.multiselect("Añadir empresas:", options=list(empresas_dict.keys()), key="empresas_add")
            if nuevas and st.button("➕ Asignar Empresas", key="btn_emp_add"):
                for nom in nuevas:
                    data_service.create_empresa_grupo(grupo_id, empresas_dict[nom])
                limpiar_cache_completo(data_service)
                st.success("✅ Empresas asignadas.")
                st.rerun()
        elif session_state.role != "admin":
            st.info("ℹ️ Como gestor, tu empresa ya está vinculada al grupo.")

        if session_state.role == "admin" and not df_asignadas.empty:
            rel_map = {r.get("nombre",""): r["id"] for _, r in df_asignadas.iterrows()}
            quitar = st.selectbox("Quitar empresa:", [""] + list(rel_map.keys()), key="empresa_quitar")
            if quitar and st.button("❌ Quitar Empresa", key="btn_emp_quitar"):
                data_service.delete_empresa_grupo(rel_map[quitar])
                limpiar_cache_completo(data_service)
                st.success("✅ Empresa eliminada.")
                st.rerun()
    except Exception as e:
        st.error(f"❌ Error en gestión de empresas: {e}")


# =========================
# TAB PARTICIPANTES
# =========================
def mostrar_tab_participantes(supabase, session_state, data_service):
    st.markdown("#### 👥 Gestión de Participantes")
    grupo_id = st.session_state.get("grupo_actual")
    if not grupo_id:
        return

    try:
        df_asignados = data_service.get_participantes_grupo(grupo_id)
        if not df_asignados.empty:
            df_asignados["nombre_completo"] = df_asignados.apply(
                lambda r: f"{r.get('nombre','')} {r.get('apellidos','')}".strip(), axis=1
            )
            st.dataframe(df_asignados[["nombre_completo", "email"]])

        libres = data_service.get_participantes_sin_grupo()
        if not libres.empty:
            opciones = {f"{r['nombre']} {r.get('apellidos','')}".strip(): r["id"] for _, r in libres.iterrows()}
            nuevos = st.multiselect("Añadir participantes:", options=list(opciones.keys()), key="parts_add")
            if nuevos and st.button("➕ Asignar Participantes", key="btn_parts_add"):
                for nom in nuevos:
                    supabase.table("participantes_grupos").insert({
                        "grupo_id": grupo_id,
                        "participante_id": opciones[nom],
                        "fecha_asignacion": datetime.utcnow().isoformat()
                    }).execute()
                limpiar_cache_completo(data_service)
                st.success("✅ Participantes asignados.")
                st.rerun()

        if not df_asignados.empty:
            rel_map = {r["nombre_completo"]: r["id"] for _, r in df_asignados.iterrows()}
            quitar = st.selectbox("Quitar participante:", [""] + list(rel_map.keys()), key="part_quitar")
            if quitar and st.button("❌ Quitar Participante", key="btn_part_quitar"):
                supabase.table("participantes_grupos").delete().eq("grupo_id", grupo_id).eq("participante_id", rel_map[quitar]).execute()
                limpiar_cache_completo(data_service)
                st.success("✅ Participante eliminado.")
                st.rerun()
    except Exception as e:
        st.error(f"❌ Error en gestión de participantes: {e}")


# =========================
# TAB COSTES FUNDAE
# =========================
def mostrar_tab_costes_fundae(supabase, session_state, data_service):
    st.markdown("#### 💰 Costes FUNDAE")
    grupo_id = st.session_state.get("grupo_actual")
    if not grupo_id:
        return

    try:
        grupo = data_service.get_grupos_completos()
        grupo = grupo[grupo["id"] == grupo_id].iloc[0]

        coste = data_service.get_grupo_costes(grupo_id)
        horas = int(grupo.get("accion_horas") or 0)
        participantes = int(grupo.get("n_participantes_previstos") or 1)
        tarifa_max = 13 if grupo["modalidad"] == "PRESENCIAL" else 7.5

        with st.form("form_costes", clear_on_submit=False):
            costes_directos = st.number_input("Costes Directos (€)", min_value=0.0, value=float(coste.get("costes_directos", 0)))
            costes_indirectos = st.number_input("Costes Indirectos (€)", min_value=0.0, value=float(coste.get("costes_indirectos", 0)))
            costes_organizacion = st.number_input("Costes de Organización (€)", min_value=0.0, value=float(coste.get("costes_organizacion", 0)))
            costes_salariales = st.number_input("Costes Salariales Cofinanciación (€)", min_value=0.0, value=float(coste.get("costes_salariales", 0)))
            cofinanciacion_privada = st.number_input("Aportación Privada (€)", min_value=0.0, value=float(coste.get("cofinanciacion_privada", 0)))
            tarifa_hora = st.number_input("Tarifa Hora (€)", min_value=0.0, value=float(coste.get("tarifa_hora", tarifa_max)))

            limite_boni = horas * participantes * tarifa_hora
            total_costes = costes_directos + costes_indirectos + costes_organizacion

            st.metric("Total Costes Formación", f"{total_costes:.2f} €")
            st.info(f"💡 Límite de bonificación: {limite_boni:.2f} €")

            if tarifa_hora > tarifa_max:
                st.error(f"⚠️ La tarifa por hora no puede superar {tarifa_max} € para modalidad {grupo['modalidad']}.")
                return

            btn_guardar = st.form_submit_button("💾 Guardar Costes", type="primary")
            if btn_guardar:
                datos_coste = {
                    "grupo_id": grupo_id,
                    "costes_directos": costes_directos,
                    "costes_indirectos": costes_indirectos,
                    "costes_organizacion": costes_organizacion,
                    "total_costes_formacion": total_costes,
                    "costes_salariales": costes_salariales,
                    "cofinanciacion_privada": cofinanciacion_privada,
                    "modalidad": grupo["modalidad"],
                    "tarifa_hora": tarifa_hora,
                    "limite_maximo_bonificacion": limite_boni,
                    "updated_at": datetime.utcnow().isoformat()
                }
                if coste:
                    supabase.table("grupo_costes").update(datos_coste).eq("grupo_id", grupo_id).execute()
                else:
                    datos_coste["created_at"] = datetime.utcnow().isoformat()
                    supabase.table("grupo_costes").insert(datos_coste).execute()
                limpiar_cache_completo(data_service)
                st.success("✅ Costes guardados.")
                st.rerun()

        # Bonificaciones
        st.divider()
        st.markdown("#### 📅 Bonificaciones Mensuales")
        bonificaciones = data_service.get_grupo_bonificaciones(grupo_id)
        if not bonificaciones.empty:
            st.table(bonificaciones[["mes", "importe"]])
        with st.form("form_bonificaciones", clear_on_submit=True):
            mes = st.selectbox("Mes", ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"])
            importe = st.number_input("Importe Bonificación (€)", min_value=0.0)
            btn_bonif = st.form_submit_button("➕ Añadir Bonificación")
            if btn_bonif:
                existe = supabase.table("grupo_bonificaciones").select("id").eq("grupo_id", grupo_id).eq("mes", mes).execute()
                if existe.data:
                    st.error("⚠️ Ya existe una bonificación para ese mes.")
                else:
                    total_bonificado = float(bonificaciones["importe"].fillna(0).sum()) if not bonificaciones.empty else 0
                    if total_bonificado + importe > limite_boni:
                        st.error(f"⚠️ La suma de bonificaciones ({total_bonificado + importe:.2f} €) supera el límite ({limite_boni:.2f} €).")
                    else:
                        supabase.table("grupo_bonificaciones").insert({
                            "grupo_id": grupo_id,
                            "mes": mes,
                            "importe": importe,
                            "created_at": datetime.utcnow().isoformat()
                        }).execute()
                        limpiar_cache_completo(data_service)
                        st.success("✅ Bonificación añadida.")
                        st.rerun()
    except Exception as e:
        st.error(f"❌ Error en costes FUNDAE: {e}")


# =========================
# UTILIDADES
# =========================
def limpiar_cache_completo(data_service):
    try:
        data_service.get_grupos_completos.clear()
        data_service.get_participantes_completos.clear()
        data_service.get_participantes_grupo.clear()
        data_service.get_participantes_sin_grupo.clear()
        data_service.get_tutores_por_empresa.clear()
        data_service.get_tutores_grupo.clear()
        data_service.get_empresas_grupo.clear()
        data_service.get_grupo_costes.clear()
        data_service.get_grupo_bonificaciones.clear()
    except:
        pass
