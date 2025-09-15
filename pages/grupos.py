# /pages/grupos.py  — v2.3 (alineado con data_service actual)
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
    st.caption("Creación, administración y cierre de grupos formativos (FUNDAE).")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    data_service = get_data_service(supabase, session_state)

    # ---------- Carga principal ----------
    try:
        df_grupos = data_service.get_grupos_completos()   # incluye accion_formativa (nombre, horas, modalidad)
        acciones_dict = data_service.get_acciones_dict()
        empresas_dict = data_service.get_empresas_dict() if session_state.role == "admin" else {}
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # ---------- KPIs + Filtros + Tabla (una sola vez) ----------
    mostrar_estadisticas_grupos(df_grupos)
    df_filtered = mostrar_filtros_busqueda(df_grupos)
    mostrar_tabla_grupos(df_filtered, data_service, supabase, session_state, acciones_dict)

    st.divider()

    # ---------- Selector global de grupo ----------
    col_sel1, col_sel2 = st.columns([2, 3])
    with col_sel1:
        st.markdown("### 🎯 Grupo actual")
        opciones_grupo = [""] + (df_grupos["codigo_grupo"].tolist() if not df_grupos.empty else [])
        sel = st.selectbox("Selecciona un grupo para gestionar:", opciones_grupo, key="grupo_selector_global")
        if sel:
            grupo_id = df_grupos.loc[df_grupos["codigo_grupo"] == sel, "id"].iloc[0]
            st.session_state["grupo_actual"] = grupo_id
        else:
            st.session_state["grupo_actual"] = None
    with col_sel2:
        if st.session_state.get("grupo_actual"):
            g = df_grupos[df_grupos["id"] == st.session_state["grupo_actual"]]
            if not g.empty:
                g = g.iloc[0]
                st.info(
                    f"**Código:** {g['codigo_grupo']}  \n"
                    f"**Acción:** {g.get('accion_nombre','')}  \n"
                    f"**Modalidad:** {g.get('accion_modalidad','')}  \n"
                    f"**Horas:** {int(g.get('accion_horas') or 0)}"
                )
        else:
            st.caption("No hay grupo seleccionado. Puedes **crear** uno abajo y se seleccionará automáticamente.")

    # ---------- Sistema de tabs ----------
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📝 Descripción", "👨‍🏫 Tutores", "🏢 Empresas", "👥 Participantes", "💰 Costes FUNDAE"
    ])

    with tab1:
        mostrar_tab_descripcion(supabase, session_state, data_service, acciones_dict)

    # Las demás tabs requieren un grupo seleccionado
    if not st.session_state.get("grupo_actual"):
        with tab2:
            st.info("Selecciona o crea primero un grupo en la pestaña **Descripción**.")
        with tab3:
            st.info("Selecciona o crea primero un grupo en la pestaña **Descripción**.")
        with tab4:
            st.info("Selecciona o crea primero un grupo en la pestaña **Descripción**.")
        with tab5:
            st.info("Selecciona o crea primero un grupo en la pestaña **Descripción**.")
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
def mostrar_estadisticas_grupos(df_grupos: pd.DataFrame):
    if df_grupos.empty:
        return
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


def mostrar_filtros_busqueda(df_grupos: pd.DataFrame) -> pd.DataFrame:
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2 = st.columns(2)
    with col1:
        query = st.text_input("Buscar por código o acción formativa", key="filtro_q")
    with col2:
        estado = st.selectbox("Estado", ["Todos", "Activos", "Finalizados", "Próximos"], key="filtro_estado")

    df = df_grupos.copy()
    if query and not df.empty:
        q = query.lower()
        df = df[
            df["codigo_grupo"].str.lower().str.contains(q, na=False) |
            df["accion_nombre"].fillna("").str.lower().str.contains(q, na=False)
        ]

    if estado != "Todos" and not df.empty:
        hoy = datetime.now()
        if estado == "Activos":
            df = df[
                (pd.to_datetime(df["fecha_inicio"], errors="coerce") <= hoy) &
                ((df["fecha_fin"].isna()) | (pd.to_datetime(df["fecha_fin"], errors="coerce") >= hoy))
            ]
        elif estado == "Finalizados":
            df = df[pd.to_datetime(df["fecha_fin"], errors="coerce") < hoy]
        elif estado == "Próximos":
            df = df[pd.to_datetime(df["fecha_inicio"], errors="coerce") > hoy]

    if not df.empty:
        export_csv(df, filename="grupos.csv")
    return df


# =========================
# TABLA DE GRUPOS (edición rápida; sin Empresa)
# =========================
def mostrar_tabla_grupos(df_filtered: pd.DataFrame, data_service, supabase, session_state, acciones_dict):
    st.markdown("### 📊 Lista de Grupos")
    if df_filtered.empty:
        st.info("ℹ️ No hay grupos para mostrar.")
        return

    def guardar_grupo(grupo_id: str, datos_editados: dict):
        try:
            # Mapear acción seleccionada
            if "accion_sel" in datos_editados:
                accion_sel = datos_editados.pop("accion_sel")
                if accion_sel in acciones_dict:
                    datos_editados["accion_formativa_id"] = acciones_dict[accion_sel]

            # Validaciones de cierre FUNDAE
            if "n_participantes_finalizados" in datos_editados or "n_aptos" in datos_editados or "n_no_aptos" in datos_editados:
                # Leer valores actuales del df para completar si no llegan editados
                fila = df_filtered[df_filtered["id"] == grupo_id].iloc[0]
                n_final = int(datos_editados.get("n_participantes_finalizados", fila.get("n_participantes_finalizados") or 0))
                aptos = int(datos_editados.get("n_aptos", fila.get("n_aptos") or 0))
                no_aptos = int(datos_editados.get("n_no_aptos", fila.get("n_no_aptos") or 0))
                if (aptos + no_aptos) != n_final:
                    st.error("⚠️ La suma de **aptos** y **no aptos** debe coincidir con **finalizados**.")
                    return

            datos_editados["updated_at"] = datetime.utcnow().isoformat()
            supabase.table("grupos").update(datos_editados).eq("id", grupo_id).execute()
            limpiar_cache(data_service)
            st.success("✅ Grupo actualizado.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar grupo: {e}")

    # Columnas visibles / selects
    df_display = df_filtered.copy()
    df_display["accion_sel"] = df_display.get("accion_nombre", "Acción no disponible")

    # Campos que se editan en fila (dinámicos)
    def campos_dinamicos(datos_fila: dict):
        base = ["codigo_grupo", "accion_sel", "modalidad", "fecha_inicio", "fecha_fin_prevista", "localidad", "provincia", "cp", "observaciones"]
        # Si el grupo ya debería haber finalizado (por fecha fin prevista pasada), mostramos campos de cierre
        try:
            hoy = datetime.now().date()
            fprev = datos_fila.get("fecha_fin_prevista")
            fprev = pd.to_datetime(fprev).date() if fprev else None
            if fprev and fprev < hoy:
                base += ["fecha_fin", "n_participantes_finalizados", "n_aptos", "n_no_aptos"]
        except:
            pass
        return base

    listado_con_ficha(
        df=df_display,
        columnas_visibles=[c for c in ["codigo_grupo", "accion_nombre", "modalidad", "fecha_inicio", "fecha_fin_prevista"] if c in df_display.columns],
        titulo="Grupo",
        on_save=guardar_grupo,
        id_col="id",
        campos_select={"accion_sel": list(acciones_dict.keys())},
        campos_dinamicos=campos_dinamicos,
        allow_creation=False,
        search_columns=["codigo_grupo", "accion_nombre"]
    )


# =========================
# TAB DESCRIPCIÓN (crear grupo)
# =========================
def mostrar_tab_descripcion(supabase, session_state, data_service, acciones_dict):
    st.markdown("#### 📝 Crear Nuevo Grupo")
    st.caption("La empresa no se selecciona aquí. Las **empresas participantes** se gestionan en su pestaña.")

    with st.form("form_crear_grupo", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            codigo_grupo = st.text_input("Código de Grupo *", key="cg_codigo")
            accion_sel = st.selectbox("Acción Formativa *", options=[""] + list(acciones_dict.keys()), key="cg_accion")
            modalidad = st.selectbox("Modalidad *", ["PRESENCIAL", "TELEFORMACION", "MIXTA"], key="cg_modalidad")
            lugar_imparticion = st.text_input("Lugar de Impartición *", key="cg_lugar")
            localidad = st.text_input("Localidad", key="cg_loc")
            provincia = st.text_input("Provincia", key="cg_prov")
            cp = st.text_input("Código Postal", key="cg_cp")
        with col2:
            fecha_inicio = st.date_input("Fecha de Inicio *", key="cg_ini")
            fecha_fin_prevista = st.date_input("Fecha Fin Prevista *", key="cg_finprev")
            n_prev = st.number_input("Participantes Previstos *", min_value=1, max_value=200, value=10, key="cg_prev")

            st.markdown("**🕐 Horario**")
            add_m = st.checkbox("Añadir tramo de Mañana", key="cg_add_m")
            if add_m:
                h_m_i = st.time_input("Mañana - Inicio", key="cg_m_i")
                h_m_f = st.time_input("Mañana - Fin", key="cg_m_f")
            else:
                h_m_i = h_m_f = None

            add_t = st.checkbox("Añadir tramo de Tarde", key="cg_add_t")
            if add_t:
                h_t_i = st.time_input("Tarde - Inicio", key="cg_t_i")
                h_t_f = st.time_input("Tarde - Fin", key="cg_t_f")
            else:
                h_t_i = h_t_f = None

            dias = st.multiselect("Días de impartición", ["L","M","X","J","V","S","D"], key="cg_dias")

        observaciones = st.text_area("Observaciones", key="cg_obs")

        crear = st.form_submit_button("🚀 Crear Grupo", type="primary")

    if crear:
        # Validaciones mínimas
        if not codigo_grupo or not accion_sel or not modalidad or not lugar_imparticion or not fecha_inicio or not fecha_fin_prevista:
            st.error("⚠️ Completa todos los campos obligatorios.")
            return
        # Código único
        existe = supabase.table("grupos").select("id").eq("codigo_grupo", codigo_grupo).execute()
        if existe.data:
            st.error("⚠️ Ya existe un grupo con ese código.")
            return

        # Construcción de horario
        partes = []
        if h_m_i and h_m_f:
            partes.append(f"Mañana: {h_m_i.strftime('%H:%M')} - {h_m_f.strftime('%H:%M')}")
        if h_t_i and h_t_f:
            partes.append(f"Tarde: {h_t_i.strftime('%H:%M')} - {h_t_f.strftime('%H:%M')}")
        if dias:
            partes.append("Días: " + "-".join(dias))
        horario = " | ".join(partes)

        nuevo = {
            "codigo_grupo": codigo_grupo,
            "accion_formativa_id": acciones_dict[accion_sel],
            "modalidad": modalidad,
            "lugar_imparticion": lugar_imparticion,
            "localidad": localidad,
            "provincia": provincia,
            "cp": cp,
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin_prevista": fecha_fin_prevista.isoformat(),
            "n_participantes_previstos": int(n_prev),
            "horario": horario,
            "aula_virtual": modalidad in ["TELEFORMACION", "MIXTA"],
            "observaciones": observaciones,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # Empresa según rol (sin selector en el formulario)
        if session_state.role == "gestor":
            emp_id = session_state.user.get("empresa_id")
            if emp_id:
                nuevo["empresa_id"] = emp_id

        res = supabase.table("grupos").insert(nuevo).execute()
        if not res.data:
            st.error("❌ Error al crear grupo.")
            return

        grupo_id = res.data[0]["id"]

        # Si es gestor: vincular su empresa como participante del grupo (multi-empresa)
        try:
            if session_state.role == "gestor":
                emp_id = session_state.user.get("empresa_id")
                if emp_id:
                    ya = supabase.table("empresas_grupos").select("id").eq("grupo_id", grupo_id).eq("empresa_id", emp_id).execute()
                    if not ya.data:
                        supabase.table("empresas_grupos").insert({
                            "grupo_id": grupo_id,
                            "empresa_id": emp_id,
                            "created_at": datetime.utcnow().isoformat()
                        }).execute()
        except Exception as e:
            st.warning(f"⚠️ Grupo creado, pero no se pudo vincular tu empresa automáticamente: {e}")

        # Seleccionar el nuevo grupo y limpiar cache
        st.session_state["grupo_actual"] = grupo_id
        limpiar_cache(data_service)
        st.success("✅ Grupo creado correctamente.")
        st.balloons()
        st.rerun()


# =========================
# TAB TUTORES
# =========================
def mostrar_tab_tutores(supabase, session_state, data_service):
    st.markdown("#### 👨‍🏫 Tutores por Grupo")
    grupo_id = st.session_state.get("grupo_actual")
    if not grupo_id:
        return
    try:
        df_asig = data_service.get_tutores_grupo(grupo_id)
        if not df_asig.empty and "tutor" in df_asig.columns:
            df_asig["nombre"] = df_asig["tutor"].apply(lambda x: x.get("nombre") if isinstance(x, dict) else "")
            df_asig["apellidos"] = df_asig["tutor"].apply(lambda x: x.get("apellidos") if isinstance(x, dict) else "")
            df_asig["email"] = df_asig["tutor"].apply(lambda x: x.get("email") if isinstance(x, dict) else "")
            df_asig["especialidad"] = df_asig["tutor"].apply(lambda x: x.get("especialidad") if isinstance(x, dict) else "")
            st.dataframe(df_asig[["nombre", "apellidos", "email", "especialidad"]])

        # Tutores disponibles (filtrados por rol/empresa en data_service)
        df_tutores = data_service.get_tutores_por_empresa(None if session_state.role == "admin" else session_state.user.get("empresa_id"))
        if not df_tutores.empty:
            opciones = {f"{r['nombre']} {r.get('apellidos','')}".strip(): r["id"] for _, r in df_tutores.iterrows()}
            nuevos = st.multiselect("Añadir tutores:", list(opciones.keys()), key="tutores_add_sel")
            if nuevos and st.button("➕ Asignar", key="tutores_add_btn"):
                for nom in nuevos:
                    data_service.create_tutor_grupo(grupo_id, opciones[nom])
                limpiar_cache(data_service)
                st.success("✅ Tutores asignados.")
                st.rerun()

        if not df_asig.empty:
            rel_map = {f"{r.get('nombre','')} {r.get('apellidos','')}".strip(): r["id"] for _, r in df_asig.iterrows()}
            quitar = st.selectbox("Quitar tutor:", [""] + list(rel_map.keys()), key="tutores_del_sel")
            if quitar and st.button("❌ Quitar", key="tutores_del_btn"):
                data_service.delete_tutor_grupo(rel_map[quitar])
                limpiar_cache(data_service)
                st.success("✅ Tutor eliminado.")
                st.rerun()
    except Exception as e:
        st.error(f"❌ Error en gestión de tutores: {e}")


# =========================
# TAB EMPRESAS
# =========================
def mostrar_tab_empresas(supabase, session_state, data_service, empresas_dict):
    st.markdown("#### 🏢 Empresas participantes")
    grupo_id = st.session_state.get("grupo_actual")
    if not grupo_id:
        return

    try:
        df_asig = data_service.get_empresas_grupo(grupo_id)
        if not df_asig.empty and "empresa" in df_asig.columns:
            df_asig["nombre"] = df_asig["empresa"].apply(lambda x: x.get("nombre") if isinstance(x, dict) else "")
            df_asig["cif"] = df_asig["empresa"].apply(lambda x: x.get("cif") if isinstance(x, dict) else "")
            st.dataframe(df_asig[["nombre", "cif"]])

        # admin puede añadir/quitar
        if session_state.role == "admin" and empresas_dict:
            nuevas = st.multiselect("Añadir empresas:", list(empresas_dict.keys()), key="emp_add_sel")
            if nuevas and st.button("➕ Asignar Empresas", key="emp_add_btn"):
                for nom in nuevas:
                    data_service.create_empresa_grupo(grupo_id, empresas_dict[nom])
                limpiar_cache(data_service)
                st.success("✅ Empresas asignadas.")
                st.rerun()
            if not df_asig.empty:
                rel_map = {r.get("nombre",""): r["id"] for _, r in df_asig.iterrows()}
                quitar = st.selectbox("Quitar empresa:", [""] + list(rel_map.keys()), key="emp_del_sel")
                if quitar and st.button("❌ Quitar Empresa", key="emp_del_btn"):
                    data_service.delete_empresa_grupo(rel_map[quitar])
                    limpiar_cache(data_service)
                    st.success("✅ Empresa eliminada.")
                    st.rerun()
        else:
            # gestor solo ve su empresa
            st.info("Como gestor, tu empresa está vinculada automáticamente al crear el grupo.")
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
        df_part = data_service.get_participantes_completos()
        if df_part.empty:
            st.info("ℹ️ No hay participantes.")
            return

        asignados = df_part[df_part["grupo_id"] == grupo_id].copy()
        if not asignados.empty:
            asignados["nombre_completo"] = asignados.apply(lambda r: f"{r.get('nombre','')} {r.get('apellidos','')}".strip(), axis=1)
            st.dataframe(asignados[["nombre_completo", "email"]])

        disponibles = df_part[(df_part["grupo_id"].isna()) | (df_part["grupo_id"] == grupo_id)].copy()
        if not disponibles.empty:
            opciones = {f"{r['nombre']} {r.get('apellidos','')}".strip(): r["id"] for _, r in disponibles.iterrows()}
            nuevos = st.multiselect("Añadir participantes:", list(opciones.keys()), key="part_add_sel")
            if nuevos and st.button("➕ Asignar Participantes", key="part_add_btn"):
                for nom in nuevos:
                    supabase.table("participantes").update({
                        "grupo_id": grupo_id,
                        "updated_at": datetime.utcnow().isoformat()
                    }).eq("id", opciones[nom]).execute()
                limpiar_cache(data_service)
                st.success("✅ Participantes asignados.")
                st.rerun()

        if not asignados.empty:
            rel_map = {f"{r['nombre']} {r.get('apellidos','')}".strip(): r["id"] for _, r in asignados.iterrows()}
            quitar = st.selectbox("Quitar participante:", [""] + list(rel_map.keys()), key="part_del_sel")
            if quitar and st.button("❌ Quitar Participante", key="part_del_btn"):
                supabase.table("participantes").update({
                    "grupo_id": None,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", rel_map[quitar]).execute()
                limpiar_cache(data_service)
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
        df_g = data_service.get_grupos_completos()
        g = df_g[df_g["id"] == grupo_id]
        if g.empty:
            st.info("No se encontró el grupo.")
            return
        g = g.iloc[0]

        coste = data_service.get_grupo_costes(grupo_id)  # dict o {}
        horas = int(g.get("accion_horas") or 0)
        participantes = int(g.get("n_participantes_previstos") or 1)
        modalidad = g.get("modalidad") or g.get("accion_modalidad") or "PRESENCIAL"
        tarifa_max = 7.5 if modalidad == "TELEFORMACION" else 13.0  # Mixta -> 13

        with st.form("form_costes", clear_on_submit=False):
            cd = st.number_input("Costes Directos (€)", min_value=0.0, value=float(coste.get("costes_directos", 0)), key="c_cd")
            ci = st.number_input("Costes Indirectos (€)", min_value=0.0, value=float(coste.get("costes_indirectos", 0)), key="c_ci")
            co = st.number_input("Costes de Organización (€)", min_value=0.0, value=float(coste.get("costes_organizacion", 0)), key="c_co")
            cs = st.number_input("Costes Salariales (cofinanciación) (€)", min_value=0.0, value=float(coste.get("costes_salariales", 0)), key="c_cs")
            ap = st.number_input("Aportación Privada (€)", min_value=0.0, value=float(coste.get("cofinanciacion_privada", 0)), key="c_ap")
            th = st.number_input("Tarifa Hora (€)", min_value=0.0, value=float(coste.get("tarifa_hora", tarifa_max)), key="c_th")

            limite_boni = horas * participantes * th
            total_costes = cd + ci + co

            st.metric("Total Costes Formación", f"{total_costes:.2f} €")
            st.info(f"💡 Límite de bonificación estimado: {limite_boni:.2f} € (horas x participantes x tarifa)")

            if th > tarifa_max:
                st.error(f"⚠️ La tarifa/hora no puede superar {tarifa_max} € para modalidad {modalidad}.")
                return

            guardar = st.form_submit_button("💾 Guardar Costes", type="primary")
            if guardar:
                payload = {
                    "grupo_id": grupo_id,
                    "costes_directos": cd,
                    "costes_indirectos": ci,
                    "costes_organizacion": co,
                    "total_costes_formacion": total_costes,
                    "limite_maximo_bonificacion": limite_boni,
                    "costes_salariales": cs,
                    "cofinanciacion_privada": ap,
                    "modalidad": modalidad,
                    "tarifa_hora": th,
                    "updated_at": datetime.utcnow().isoformat()
                }
                if coste:
                    supabase.table("grupo_costes").update(payload).eq("grupo_id", grupo_id).execute()
                else:
                    payload["created_at"] = datetime.utcnow().isoformat()
                    supabase.table("grupo_costes").insert(payload).execute()
                limpiar_cache(data_service)
                st.success("✅ Costes guardados.")
                st.rerun()

        # Bonificaciones
        st.divider()
        st.markdown("#### 📅 Bonificaciones Mensuales")
        bonis = data_service.get_grupo_bonificaciones(grupo_id)
        if not bonis.empty:
            st.table(bonis[["mes", "importe"]])

        with st.form("form_boni", clear_on_submit=True):
            mes = st.selectbox("Mes", ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"], key="boni_mes")
            imp = st.number_input("Importe (€)", min_value=0.0, key="boni_imp")
            add = st.form_submit_button("➕ Añadir Bonificación")
            if add:
                # No duplicar mes
                existe = supabase.table("grupo_bonificaciones").select("id").eq("grupo_id", grupo_id).eq("mes", mes).execute()
                if existe.data:
                    st.error("⚠️ Ya existe una bonificación para ese mes.")
                else:
                    total_bonificado = float(bonis["importe"].fillna(0).sum()) if not bonis.empty else 0.0
                    if total_bonificado + imp > limite_boni:
                        st.error(f"⚠️ La suma ({total_bonificado + imp:.2f} €) supera el límite ({limite_boni:.2f} €).")
                    else:
                        supabase.table("grupo_bonificaciones").insert({
                            "grupo_id": grupo_id,
                            "mes": mes,
                            "importe": imp,
                            "created_at": datetime.utcnow().isoformat()
                        }).execute()
                        limpiar_cache(data_service)
                        st.success("✅ Bonificación añadida.")
                        st.rerun()

    except Exception as e:
        st.error(f"❌ Error en costes FUNDAE: {e}")


# =========================
# UTILIDADES
# =========================
def limpiar_cache(data_service):
    # Si existe la util del servicio, úsala; si no, limpia manualmente
    try:
        if hasattr(data_service, "limpiar_cache_grupos"):
            data_service.limpiar_cache_grupos()  # limpia caches de grupos/bonificaciones/costes/tutores/empresas
        else:
            # fallback conservador
            data_service.get_grupos_completos.clear()
            data_service.get_grupo_costes.clear()
            data_service.get_grupo_bonificaciones.clear()
            data_service.get_tutores_grupo.clear()
            data_service.get_empresas_grupo.clear()
            data_service.get_participantes_completos.clear()
    except:
        pass
