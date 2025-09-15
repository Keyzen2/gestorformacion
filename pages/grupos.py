import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from utils import export_csv, formato_fecha
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

    # Inicializar servicio de datos
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
    mostrar_tabla_grupos_mejorada(df_filtered, data_service, supabase, session_state, acciones_dict, empresas_dict)

    # =========================
    # SISTEMA DE TABS
    # =========================
    st.divider()
    tab1, tab2, tab3 = st.tabs([
        "📝 Crear Grupo Completo",
        "👥 Gestionar Participantes",
        "💰 Costes FUNDAE"
    ])

    with tab1:
        mostrar_tab_crear_grupo(supabase, session_state, data_service, acciones_dict, empresas_dict)

    with tab2:
        mostrar_tab_participantes(supabase, session_state, data_service, df_grupos)

    with tab3:
        mostrar_tab_costes_fundae(supabase, session_state, data_service, df_grupos)


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
def mostrar_tabla_grupos_mejorada(df_filtered, data_service, supabase, session_state, acciones_dict, empresas_dict):
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

            # Validación FUNDAE: coherencia en finalización
            if "n_participantes_finalizados" in datos_editados:
                n_finalizados = datos_editados.get("n_participantes_finalizados", 0)
                aptos = datos_editados.get("n_aptos", 0)
                no_aptos = datos_editados.get("n_no_aptos", 0)
                if (aptos + no_aptos) != n_finalizados:
                    st.error("⚠️ La suma de aptos y no aptos debe coincidir con finalizados.")
                    return

            datos_editados["updated_at"] = datetime.utcnow().isoformat()
            supabase.table("grupos").update(datos_editados).eq("id", grupo_id).execute()
            limpiar_cache_grupos(data_service)
            st.success("✅ Grupo actualizado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar grupo: {e}")

    # Campos dinámicos: si el grupo ya debería haber finalizado
    def get_campos_dinamicos(datos):
        campos = ["codigo_grupo", "accion_sel", "modalidad", "localidad", "provincia", "cp",
                  "fecha_inicio", "fecha_fin_prevista", "observaciones"]
        if datos.get("fecha_fin_prevista") and pd.to_datetime(datos["fecha_fin_prevista"]) < datetime.now():
            campos += ["fecha_fin", "n_participantes_finalizados", "n_aptos", "n_no_aptos"]
        return campos

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
        campos_dinamicos=get_campos_dinamicos,
        campos_obligatorios=["codigo_grupo", "accion_sel", "modalidad", "fecha_inicio", "fecha_fin_prevista"]
    )


# =========================
# CREAR GRUPO
# =========================
def mostrar_tab_crear_grupo(supabase, session_state, data_service, acciones_dict, empresas_dict):
    st.markdown("#### 📝 Crear Nuevo Grupo")
    st.caption("Formulario completo para crear grupos según estándares FUNDAE.")

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

            if session_state.role == "admin":
                empresa_sel = st.selectbox("Empresa *", options=[""] + list(empresas_dict.keys()))

        with col2:
            fecha_inicio = st.date_input("Fecha de Inicio *")
            fecha_fin_prevista = st.date_input("Fecha Fin Prevista *")
            n_participantes_previstos = st.number_input("Participantes Previstos *", min_value=1, max_value=50, value=10)

            st.markdown("**🕐 Horario FUNDAE**")
            horario_tipo = st.radio("Seleccionar Horario", ["Solo Mañana", "Solo Tarde", "Mañana y Tarde"], horizontal=True)
            if horario_tipo in ["Solo Mañana", "Mañana y Tarde"]:
                hora_m_inicio = st.time_input("Mañana - Inicio")
                hora_m_fin = st.time_input("Mañana - Fin")
            else:
                hora_m_inicio = hora_m_fin = None
            if horario_tipo in ["Solo Tarde", "Mañana y Tarde"]:
                hora_t_inicio = st.time_input("Tarde - Inicio")
                hora_t_fin = st.time_input("Tarde - Fin")
            else:
                hora_t_inicio = hora_t_fin = None

        st.markdown("**👨‍🏫 Tutor Responsable**")
        df_tutores = data_service.get_tutores_por_empresa(session_state.empresa_id if session_state.role == "gestor" else None)
        if df_tutores.empty:
            st.error("⚠️ Debe existir al menos un tutor en la empresa para crear un grupo.")
            tutor_sel = None
        else:
            tutor_opciones = {f"{t['nombre']} {t['apellidos']}": t["id"] for _, t in df_tutores.iterrows()}
            tutor_sel = st.selectbox("Seleccionar Tutor *", options=[""] + list(tutor_opciones.keys()))

        observaciones = st.text_area("Observaciones")

        btn_crear = st.form_submit_button("🚀 Crear Grupo", type="primary")
        if btn_crear:
            if not codigo_grupo or not accion_sel or not modalidad or not lugar_imparticion or not fecha_inicio or not fecha_fin_prevista:
                st.error("⚠️ Todos los campos obligatorios deben estar completos.")
                return
            if tutor_sel == "":
                st.error("⚠️ Debe seleccionar un tutor.")
                return

            # Verificar código único
            existe = supabase.table("grupos").select("id").eq("codigo_grupo", codigo_grupo).execute()
            if existe.data:
                st.error("⚠️ Ya existe un grupo con ese código.")
                return

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
                "aula_virtual": modalidad in ["TELEFORMACION", "MIXTA"],
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            if session_state.role == "admin":
                datos_grupo["empresa_id"] = empresas_dict.get(empresa_sel)
            else:
                datos_grupo["empresa_id"] = session_state.user.get("empresa_id")

            # Horario
            partes = []
            if hora_m_inicio and hora_m_fin:
                partes.append(f"Mañana: {hora_m_inicio.strftime('%H:%M')} - {hora_m_fin.strftime('%H:%M')}")
            if hora_t_inicio and hora_t_fin:
                partes.append(f"Tarde: {hora_t_inicio.strftime('%H:%M')} - {hora_t_fin.strftime('%H:%M')}")
            datos_grupo["horario"] = " | ".join(partes)

            res = supabase.table("grupos").insert(datos_grupo).execute()
            if res.data:
                grupo_id = res.data[0]["id"]
                # Asignar tutor
                supabase.table("tutores_grupos").insert({
                    "grupo_id": grupo_id,
                    "tutor_id": tutor_opciones[tutor_sel],
                    "created_at": datetime.utcnow().isoformat()
                }).execute()

                limpiar_cache_grupos(data_service)
                st.success("✅ Grupo creado correctamente.")
                st.balloons()
                st.rerun()
            else:
                st.error("❌ Error al crear grupo.")


# =========================
# PARTICIPANTES
# =========================
def mostrar_tab_participantes(supabase, session_state, data_service, df_grupos):
    st.markdown("#### 👥 Gestión de Participantes")
    try:
        df_participantes = data_service.get_participantes_completos()
        if df_participantes.empty:
            st.info("ℹ️ No hay participantes disponibles.")
            return

        col1, col2 = st.columns(2)
        with col1:
            grupo_sel = st.selectbox("Seleccionar Grupo:", [""] + df_grupos["codigo_grupo"].tolist())
            if grupo_sel:
                grupo_id = df_grupos[df_grupos["codigo_grupo"] == grupo_sel].iloc[0]["id"]
                st.markdown(f"**Grupo:** {grupo_sel}")

        with col2:
            if grupo_sel:
                participantes_disponibles = df_participantes[
                    (df_participantes["grupo_id"].isna()) | (df_participantes["grupo_id"] == grupo_id)
                ]
                participante_sel = st.selectbox(
                    "Seleccionar Participante:",
                    [""] + [f"{p['nombre']} {p['apellidos']}" for _, p in participantes_disponibles.iterrows()]
                )
                if participante_sel:
                    part_id = participantes_disponibles.iloc[
                        [f"{p['nombre']} {p['apellidos']}" for _, p in participantes_disponibles.iterrows()].index(participante_sel)
                    ]["id"]
                    if st.button("✅ Asignar"):
                        supabase.table("participantes").update({
                            "grupo_id": grupo_id,
                            "updated_at": datetime.utcnow().isoformat()
                        }).eq("id", part_id).execute()
                        limpiar_cache_grupos(data_service)
                        st.success("Participante asignado.")
                        st.rerun()
    except Exception as e:
        st.error(f"❌ Error en gestión de participantes: {e}")


# =========================
# COSTES FUNDAE
# =========================
def mostrar_tab_costes_fundae(supabase, session_state, data_service, df_grupos):
    st.markdown("#### 💰 Costes FUNDAE")
    try:
        if df_grupos.empty:
            st.info("ℹ️ No hay grupos disponibles.")
            return
        grupos_finalizados = df_grupos[pd.to_datetime(df_grupos["fecha_fin"], errors="coerce").notna()]
        if grupos_finalizados.empty:
            st.info("ℹ️ Los costes FUNDAE solo se pueden gestionar en grupos finalizados.")
            return
        st.info("⚠️ Implementar lógica de costes según necesidades (ya soportado en data_service).")
    except Exception as e:
        st.error(f"❌ Error en costes FUNDAE: {e}")


# =========================
# UTILIDADES
# =========================
def limpiar_cache_grupos(data_service):
    try:
        data_service.get_grupos_completos.clear()
        data_service.get_participantes_completos.clear()
        data_service.get_tutores_por_empresa.clear()
    except:
        pass
