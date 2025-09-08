import streamlit as st
import pandas as pd
from datetime import datetime
from utils import is_module_active


def main(supabase, session_state):
    st.markdown("## 👨‍🏫 Grupos")
    st.caption("Gestión de grupos de formación y vinculación con participantes.")
    st.divider()

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    empresa_id = session_state.user.get("empresa_id")

    # Cargar acciones formativas
    try:
        acciones_res = supabase.table("acciones_formativas").select("id,nombre").eq(
            "empresa_id", empresa_id
        ).execute() if session_state.role == "gestor" else supabase.table(
            "acciones_formativas"
        ).select("id,nombre").execute()
        acciones_dict = {a["nombre"]: a["id"] for a in (acciones_res.data or [])}
        acciones_id_to_nombre = {
            a["id"]: a["nombre"] for a in (acciones_res.data or [])
        }
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las acciones formativas: {e}")
        acciones_dict = {}
        acciones_id_to_nombre = {}

    # Cargar grupos
    try:
        grupos_res = supabase.table("grupos").select("*").eq(
            "empresa_id", empresa_id
        ).execute() if session_state.role == "gestor" else supabase.table(
            "grupos"
        ).select("*").execute()
        df_grupos = pd.DataFrame(grupos_res.data or [])
        df_grupos["accion_nombre"] = df_grupos["accion_formativa_id"].map(
            acciones_id_to_nombre
        )
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los grupos: {e}")
        df_grupos = pd.DataFrame()

    col1, col2 = st.columns(2)
    col1.metric("Total grupos", len(df_grupos))
    col2.metric(
        "Participantes previstos",
        int(df_grupos.get("n_participantes_previstos", pd.Series()).sum())
        if "n_participantes_previstos" in df_grupos.columns
        else 0,
    )
    st.divider()

    # Crear grupo
    puede_crear = (
        session_state.role == "admin"
        or (
            session_state.role == "gestor"
            and empresa_id
            and is_module_active(
                session_state.user.get("empresa", {}),
                session_state.user.get("empresa_crm", {}),
                "formacion",
                datetime.today().date(),
                "gestor",
            )
        )
    )

    if puede_crear:
    st.markdown("### ➕ Crear Grupo")
    with st.form("crear_grupo", clear_on_submit=True):
        codigo_grupo = st.text_input("Código del grupo *")
        accion_sel = st.selectbox("Acción formativa", sorted(acciones_dict.keys()))
        fecha_inicio = st.date_input("Fecha inicio")
        fecha_fin_prevista = st.date_input("Fecha fin prevista")
        localidad = st.text_input("Localidad")
        provincia = st.text_input("Provincia")
        cp = st.text_input("Código postal")
        n_previstos = st.number_input("Nº participantes previstos", min_value=0, step=1)
        observaciones = st.text_area("Observaciones")

        # Si es admin, permitir elegir empresa
        empresa_id_sel = empresa_id
        if session_state.role == "admin":
            empresas_res = supabase.table("empresas").select("id,nombre").execute()
            empresas_dict = {e["nombre"]: e["id"] for e in (empresas_res.data or [])}
            empresa_nombre_sel = st.selectbox("Empresa", sorted(empresas_dict.keys()))
            empresa_id_sel = empresas_dict.get(empresa_nombre_sel)

        submitted_new = st.form_submit_button("➕ Crear Grupo")

    if submitted_new:
        if not codigo_grupo:
            st.error("⚠️ El código de grupo es obligatorio.")
        elif not accion_sel or acciones_dict.get(accion_sel) is None:
            st.error("⚠️ Debes seleccionar una acción formativa válida.")
        elif not empresa_id_sel:
            st.error("⚠️ Debes seleccionar una empresa.")
        else:
            try:
                supabase.table("grupos").insert({
                    "codigo_grupo": codigo_grupo,
                    "empresa_id": empresa_id_sel,
                    "accion_formativa_id": acciones_dict.get(accion_sel),
                    "fecha_inicio": fecha_inicio.isoformat(),
                    "fecha_fin_prevista": fecha_fin_prevista.isoformat(),
                    "localidad": localidad,
                    "provincia": provincia,
                    "cp": cp,
                    "n_participantes_previstos": int(n_previstos),
                    "observaciones": observaciones,
                    "estado": "abierto",
                }).execute()
                st.success(f"✅ Grupo '{codigo_grupo}' creado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al crear el grupo: {e}")

    st.divider()

    # Asignar participantes
    if session_state.role in ["admin", "gestor"] and not df_grupos.empty:
        st.markdown("### 👥 Asignar participantes a grupo")

        try:
            if session_state.role == "gestor":
                part_res = (
                    supabase.table("participantes")
                    .select("id,nombre,email,dni")
                    .eq("empresa_id", empresa_id)
                    .execute()
                )
            else:
                part_res = supabase.table("participantes").select("id,nombre,email,dni").execute()
            df_part = pd.DataFrame(part_res.data or [])
        except Exception as e:
            st.error(f"❌ Error al cargar participantes: {e}")
            df_part = pd.DataFrame()

        grupo_query = st.text_input("🔍 Buscar grupo por código o curso")
        df_grupos_filtrados = (
            df_grupos[
                df_grupos["codigo_grupo"].str.contains(grupo_query, case=False, na=False)
                | df_grupos["accion_nombre"].str.contains(grupo_query, case=False, na=False)
            ]
            if grupo_query
            else df_grupos
        )

        participante_query = st.text_input("🔍 Buscar participante por nombre, email o DNI")
        df_part_filtrados = (
            df_part[
                df_part["nombre"].str.contains(participante_query, case=False, na=False)
                | df_part["email"].str.contains(participante_query, case=False, na=False)
                | df_part["dni"].str.contains(participante_query, case=False, na=False)
            ]
            if participante_query
            else df_part
        )

        if not df_grupos_filtrados.empty and not df_part_filtrados.empty:
            grupo_sel = st.selectbox(
                "Grupo",
                df_grupos_filtrados.apply(
                    lambda g: f"{g['codigo_grupo']} - {g['accion_nombre']}", axis=1
                ),
            )
            grupo_id = df_grupos_filtrados[
                df_grupos_filtrados.apply(
                    lambda g: f"{g['codigo_grupo']} - {g['accion_nombre']}", axis=1
                )
                == grupo_sel
            ]["id"].values[0]

            participante_sel = st.selectbox(
                "Participante",
                df_part_filtrados.apply(lambda p: f"{p['dni']} - {p['nombre']}", axis=1),
            )
            participante_id = df_part_filtrados[
                df_part_filtrados["dni"] == participante_sel.split(" - ")[0]
            ]["id"].values[0]

            asignar = st.button("✅ Asignar participante")

            if asignar:
                try:
                    existe = (
                        supabase.table("participantes_grupos")
                        .select("id")
                        .eq("participante_id", participante_id)
                        .eq("grupo_id", grupo_id)
                        .execute()
                    )
                    if existe.data:
                        st.warning("⚠️ Este participante ya está asignado a este grupo.")
                    else:
                        supabase.table("participantes_grupos").insert(
                            {"participante_id": participante_id, "grupo_id": grupo_id}
                        ).execute()
                        st.success("✅ Participante asignado correctamente.")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al asignar: {e}")

    # Importar participantes por Excel
    st.markdown("### 📤 Importar participantes a grupo desde Excel")
    archivo_excel = st.file_uploader("Archivo Excel (.xlsx)", type=["xlsx"])
    grupo_sel_excel = st.selectbox(
        "Grupo destino",
        df_grupos.apply(lambda g: f"{g['codigo_grupo']} - {g['accion_nombre']}", axis=1),
        key="grupo_excel",
    )
    grupo_id_excel = df_grupos[
        df_grupos.apply(lambda g: f"{g['codigo_grupo']} - {g['accion_nombre']}", axis=1)
        == grupo_sel_excel
    ]["id"].values[0]
    importar_excel = st.button("📥 Importar Excel")

    if importar_excel and archivo_excel:
        try:
            df_import = pd.read_excel(archivo_excel)
            if "dni" not in df_import.columns:
                st.error("❌ El archivo debe contener la columna 'dni'.")
            else:
                if session_state.role == "gestor":
                    part_res = (
                        supabase.table("participantes")
                        .select("id,dni")
                        .eq("empresa_id", empresa_id)
                        .execute()
                    )
                else:
                    part_res = supabase.table("participantes").select("id,dni").execute()
                participantes_existentes = {p["dni"]: p["id"] for p in (part_res.data or [])}

                creados = 0
                errores = []

                for _, fila in df_import.iterrows():
                    dni = str(fila.get("dni", "")).strip()
                    participante_id = participantes_existentes.get(dni)

                    if not participante_id:
                        errores.append(f"DNI {dni} no encontrado.")
                        continue

                    # Verificar duplicado
                    ya_asignado = (
                        supabase.table("participantes_grupos")
                        .select("id")
                        .eq("participante_id", participante_id)
                        .eq("grupo_id", grupo_id_excel)
                        .execute()
                    )
                    if ya_asignado.data:
                        errores.append(f"DNI {dni} ya asignado.")
                        continue

                    try:
                        supabase.table("participantes_grupos").insert(
                            {"participante_id": participante_id, "grupo_id": grupo_id_excel}
                        ).execute()
                        creados += 1
                    except Exception as e:
                        errores.append(f"DNI {dni} - Error: {e}")

                st.success(f"✅ Se han asignado {creados} participantes.")
                if errores:
                    st.warning("⚠️ Errores:")
                    for err in errores:
                        st.write(f"- {err}")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {e}")

    # Vista de participantes por grupo + cierre automático
    st.markdown("### 📋 Participantes por grupo")

    grupo_filtro = st.text_input("🔍 Filtrar grupos por código o curso", key="filtro_grupos")
    df_grupos_vista = (
        df_grupos[
            df_grupos["codigo_grupo"].str.contains(grupo_filtro, case=False, na=False)
            | df_grupos["accion_nombre"].str.contains(grupo_filtro, case=False, na=False)
        ]
        if grupo_filtro
        else df_grupos
    )

    for _, grupo in df_grupos_vista.iterrows():
        with st.expander(f"👥 {grupo['codigo_grupo']} - {grupo['accion_nombre']}"):
            try:
                pg_res = (
                    supabase.table("participantes_grupos")
                    .select("id,participante_id")
                    .eq("grupo_id", grupo["id"])
                    .execute()
                )
                pg_data = pg_res.data or []
                ids = [p["participante_id"] for p in pg_data]
                if ids:
                    part_res = (
                        supabase.table("participantes")
                        .select("id,nombre,email,dni")
                        .in_("id", ids)
                        .execute()
                    )
                    df_part = pd.DataFrame(part_res.data or [])
                    for _, p in df_part.iterrows():
                        col1, col2 = st.columns([4, 1])
                        col1.write(f"- {p['nombre']} ({p['email']})")
                        eliminar = col2.button("🗑️", key=f"del_{grupo['id']}_{p['id']}")
                        if eliminar:
                            try:
                                supabase.table("participantes_grupos").delete().eq(
                                    "participante_id", p["id"]
                                ).eq("grupo_id", grupo["id"]).execute()
                                st.success(
                                    f"✅ Participante {p['nombre']} eliminado del grupo."
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al eliminar participante: {e}")
                else:
                    st.info("ℹ️ Este grupo no tiene participantes asignados.")
            except Exception as e:
                st.error(f"❌ Error al cargar participantes del grupo: {e}")

            # Cierre automático si vencido
            try:
                fecha_fin_prevista = (
                    pd.to_datetime(grupo.get("fecha_fin_prevista")).date()
                    if grupo.get("fecha_fin_prevista")
                    else None
                )
                estado = grupo.get("estado", "abierto")

                if (
                    estado == "abierto"
                    and fecha_fin_prevista
                    and fecha_fin_prevista < datetime.today().date()
                ):
                    st.warning("⚠️ Este grupo ha vencido y aún no ha sido cerrado.")

                    with st.form(f"cerrar_grupo_{grupo['id']}"):
                        fecha_fin_real = st.date_input(
                            "Fecha real de fin", value=datetime.today().date()
                        )
                        n_finalizados = st.number_input(
                            "Nº participantes finalizados", min_value=0, step=1
                        )
                        n_aptos = st.number_input(
                            "Nº participantes aptos", min_value=0, step=1
                        )
                        n_no_aptos = st.number_input(
                            "Nº participantes no aptos", min_value=0, step=1
                        )
                        observaciones_final = st.text_area(
                            "Observaciones de cierre", value=grupo.get("observaciones", "")
                        )
                        cerrar = st.form_submit_button("✅ Cerrar grupo")

                        if cerrar:
                            try:
                                supabase.table("grupos").update(
                                    {
                                        "fecha_fin": fecha_fin_real.isoformat(),
                                        "n_participantes_finalizados": int(n_finalizados),
                                        "n_aptos": int(n_aptos),
                                        "n_no_aptos": int(n_no_aptos),
                                        "observaciones": observaciones_final,
                                        "estado": "cerrado",
                                    }
                                ).eq("id", grupo["id"]).execute()
                                st.success("✅ Grupo cerrado correctamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al cerrar el grupo: {e}")
            except Exception as e:
                st.error(f"❌ Error al evaluar vencimiento del grupo: {e}")
