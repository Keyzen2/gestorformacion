import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
from utils import validar_dni_cif, export_csv
from services.participantes_service import get_participantes_service
from services.grupos_service import get_grupos_service
from services.empresas_service import EmpresasService


# ======================================================
# Helpers internos (opciones jerárquicas y consultas rápidas)
# ======================================================
def _get_clientes_de_gestora(supabase, gestora_id: str) -> dict:
    """Devuelve dict nombre->id de empresas cliente de una gestora."""
    try:
        res = (
            supabase.table("empresas")
            .select("id, nombre")
            .eq("empresa_matriz_id", gestora_id)
            .order("nombre")
            .execute()
        )
        return {row["nombre"]: row["id"] for row in (res.data or [])}
    except Exception:
        return {}

def _get_participantes_de_empresa(supabase, empresa_id: str) -> pd.DataFrame:
    """Participantes de una empresa (para elegir en diplomas)."""
    try:
        res = (
            supabase.table("participantes")
            .select("id, nif, nombre, apellidos, email, telefono, grupo_id, empresa_id")
            .eq("empresa_id", empresa_id)
            .order("nombre")
            .execute()
        )
        return pd.DataFrame(res.data or [])
    except Exception:
        return pd.DataFrame()

def _get_accion_id_y_codigo(supabase, grupo_id: str) -> tuple[str | None, str | None]:
    """Devuelve (accion_id, codigo_grupo) para un grupo."""
    try:
        res = (
            supabase.table("grupos")
            .select("accion_formativa_id, codigo_grupo")
            .eq("id", grupo_id)
            .limit(1)
            .execute()
        )
        if res.data:
            row = res.data[0]
            return row.get("accion_formativa_id"), row.get("codigo_grupo")
        return None, None
    except Exception:
        return None, None

def _get_diplomas_participante_grupo(supabase, participante_id: str, grupo_id: str) -> pd.DataFrame:
    try:
        res = (
            supabase.table("diplomas")
            .select("id, url, archivo_nombre, fecha_subida")
            .eq("participante_id", participante_id)
            .eq("grupo_id", grupo_id)
            .order("fecha_subida", desc=True)
            .execute()
        )
        return pd.DataFrame(res.data or [])
    except Exception:
        return pd.DataFrame()


# ======================================================
# Pantalla principal
# ======================================================
def main(supabase, session_state):
    st.markdown("## 🧑‍🎓 Participantes")
    st.caption("Gestión de participantes y diplomas (compatible con empresas cliente de gestoras).")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicios
    participantes_service = get_participantes_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)
    empresas_service = EmpresasService(supabase, session_state)
    empresa_id = session_state.user.get("empresa_id")

    # =========================
    # Cargar datos
    # =========================
    with st.spinner("Cargando datos..."):
        try:
            df_participantes = participantes_service.get_participantes_completos()
            grupos_dict = grupos_service.get_grupos_dict()  # Todos (se filtra en UI)
            if session_state.role == "admin":
                empresas_dict = empresas_service.get_empresas_dict()  # Todas
            else:
                empresas_dict = empresas_service.get_empresas_para_gestor(empresa_id)  # Gestora + clientes
        except Exception as e:
            st.error(f"❌ Error al cargar datos: {e}")
            return

    # =========================
    # Filtros de búsqueda
    # =========================
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2, col3 = st.columns(3)

    with col1:
        query = st.text_input("🔍 Buscar por nombre, email o NIF")
    with col2:
        grupo_filter = st.selectbox("Filtrar por grupo", ["Todos"] + sorted(grupos_dict.keys()))
    with col3:
        if session_state.role == "admin":
            empresa_filter = st.selectbox("Filtrar por empresa", ["Todas"] + sorted(empresas_dict.keys()))

    df_filtered = df_participantes.copy()

    if query and not df_filtered.empty:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["apellidos"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["email"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["nif"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]

    if grupo_filter != "Todos" and not df_filtered.empty:
        grupo_id = grupos_dict.get(grupo_filter)
        df_filtered = df_filtered[df_filtered["grupo_id"] == grupo_id]

    if session_state.role == "admin" and 'empresa_filter' in locals() and empresa_filter != "Todas" and not df_filtered.empty:
        empresa_id_filter = empresas_dict.get(empresa_filter)
        df_filtered = df_filtered[df_filtered["empresa_id"] == empresa_id_filter]

    # =========================
    # TABLA PARTICIPANTES
    # =========================
    st.markdown("### 📊 Listado de Participantes")

    if df_filtered.empty:
        st.info("📋 No hay participantes registrados o que coincidan con los filtros.")
    else:
        df_display = df_filtered.copy()
        columnas_base = ["nif", "nombre", "apellidos", "email", "telefono"]
        if "grupo_codigo" in df_display.columns:
            columnas_base.append("grupo_codigo")
        if session_state.role == "admin" and "empresa_nombre" in df_display.columns:
            columnas_base.append("empresa_nombre")

        columnas_visibles = [col for col in columnas_base if col in df_display.columns]

        event = st.dataframe(
            df_display[columnas_visibles],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="tabla_participantes"
        )

        if hasattr(event, "selection") and event.selection and event.selection.rows:
            selected_idx = event.selection.rows[0]
            if 0 <= selected_idx < len(df_filtered):
                participante_seleccionado = df_filtered.iloc[selected_idx]
                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.button("✏️ Editar Participante", type="primary", use_container_width=True, key="btn_editar_sel"):
                        st.session_state.participante_editando = participante_seleccionado["id"]
                        st.rerun()

    st.divider()

    # =========================
    # CREACIÓN (expander cerrado por defecto)
    # =========================
    puede_crear = (
        session_state.role == "admin" or
        (session_state.role == "gestor" and empresa_id)
    )

    if puede_crear:
        with st.expander("➕ Crear Nuevo Participante", expanded=False):
            mostrar_formulario_participante(
                supabase, session_state, participantes_service, grupos_service,
                empresas_service, "nuevo", empresas_dict, grupos_dict, empresa_id
            )

    # =========================
    # EDICIÓN
    # =========================
    if hasattr(st.session_state, 'partcipante_editando_typo_fix'):  # limpieza de estados viejos
        del st.session_state.partcipante_editando_typo_fix
    if hasattr(st.session_state, 'partcipante_editando'):
        del st.session_state.partcipante_editando

    if hasattr(st.session_state, 'partcipante_editando'):
        del st.session_state.partcipante_editando

    if hasattr(st.session_state, 'participante_editando') and st.session_state.participante_editando and st.session_state.participante_editando != "nuevo":
        mostrar_formulario_participante(
            supabase, session_state, participantes_service, grupos_service,
            empresas_service, st.session_state.participante_editando, empresas_dict, grupos_dict, empresa_id
        )

    # =========================
    # DIPLOMAS (Jerárquico)
    # =========================
    st.divider()
    mostrar_seccion_diplomas(supabase, session_state, empresas_service, grupos_service, empresa_id)

    # =========================
    # IMPORTACIÓN MASIVA (placeholder para tu lógica previa)
    # =========================
    if puede_crear:
        st.divider()
        mostrar_importacion_masiva()

    # =========================
    # Exportación rápida
    # =========================
    if not df_filtered.empty:
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Exportar a CSV"):
                export_csv(df_filtered[columnas_visibles], filename="participantes.csv")
        with col2:
            st.metric("📋 Registros mostrados", len(df_filtered))


# ======================================================
# FORMULARIO PARTICIPANTE
# ======================================================
def mostrar_formulario_participante(supabase, session_state, participantes_service, grupos_service,
                                   empresas_service, participante_id, empresas_dict, grupos_dict, empresa_id_gestor):
    es_creacion = participante_id == "nuevo"

    if es_creacion:
        st.markdown("### ➕ Crear Nuevo Participante")
        participante_data = {}
    else:
        st.markdown("### ✏️ Editar Participante")
        try:
            result = supabase.table("participantes").select("*").eq("id", participante_id).execute()
            if result.data:
                participante_data = result.data[0]
            else:
                st.error("Participante no encontrado")
                return
        except Exception as e:
            st.error(f"Error al cargar participante: {e}")
            return

    with st.form(f"form_participante_{participante_id}", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre *", value=participante_data.get("nombre", ""))
            apellidos = st.text_input("Apellidos *", value=participante_data.get("apellidos", ""))
            email = st.text_input("Email *", value=participante_data.get("email", ""))
        with col2:
            nif = st.text_input("NIF/DNI", value=participante_data.get("nif", ""))
            telefono = st.text_input("Teléfono", value=participante_data.get("telefono", ""))

        # Empresa y Grupo (filtrado por rol)
        if session_state.role == "gestor":
            empresa_sel_id = empresa_id_gestor
            # Mostrar nombre de la gestora (si está en dict)
            nombre_empresa = next((n for n, _id in empresas_dict.items() if _id == empresa_sel_id), "")
            st.text_input("Empresa (gestora)", value=nombre_empresa or "Tu empresa", disabled=True)

            grupos_empresa = grupos_service.get_grupos_dict(empresa_sel_id)
            grupo_opciones = [""] + list(grupos_empresa.keys())

            grupo_nombre_actual = None
            if participante_data.get("grupo_id"):
                for n, gid in grupos_empresa.items():
                    if gid == participante_data.get("grupo_id"):
                        grupo_nombre_actual = n
                        break

            idx = grupo_opciones.index(grupo_nombre_actual) if grupo_nombre_actual in grupo_opciones else 0
            grupo_sel = st.selectbox("Grupo", grupo_opciones, index=idx)
            grupo_sel_id = grupos_empresa.get(grupo_sel) if grupo_sel else None

        else:  # admin
            empresa_opciones = list(empresas_dict.keys())
            empresa_nombre_actual = None
            if participante_data.get("empresa_id"):
                for n, eid in empresas_dict.items():
                    if eid == participante_data.get("empresa_id"):
                        empresa_nombre_actual = n
                        break
            idx_emp = empresa_opciones.index(empresa_nombre_actual) if (empresa_nombre_actual in empresa_opciones) else 0
            empresa_sel = st.selectbox("Empresa *", empresa_opciones, index=idx_emp)
            empresa_sel_id = empresas_dict[empresa_sel]

            grupos_empresa = grupos_service.get_grupos_dict(empresa_sel_id)
            grupo_opciones = [""] + list(grupos_empresa.keys())

            grupo_nombre_actual = None
            if participante_data.get("grupo_id"):
                for n, gid in grupos_empresa.items():
                    if gid == participante_data.get("grupo_id"):
                        grupo_nombre_actual = n
                        break

            idx_g = grupo_opciones.index(grupo_nombre_actual) if (grupo_nombre_actual in grupo_opciones) else 0
            grupo_sel = st.selectbox("Grupo", grupo_opciones, index=idx_g)
            grupo_sel_id = grupos_empresa.get(grupo_sel) if grupo_sel else None

        st.divider()
        col1, col2, col3 = st.columns(3)
        if es_creacion:
            with col1:
                if st.form_submit_button("➕ Crear", type="primary"):
                    participantes_service.crear_participante(
                        nombre, apellidos, email, nif, telefono, empresa_sel_id, grupo_sel_id
                    )
                    st.success("✅ Participante creado.")
                    st.rerun()
        else:
            with col1:
                if st.form_submit_button("💾 Guardar", type="primary"):
                    participantes_service.actualizar_participante(
                        participante_id, nombre, apellidos, email, nif, telefono, empresa_sel_id, grupo_sel_id
                    )
                    st.success("✅ Datos actualizados.")
                    del st.session_state.participante_editando
                    st.rerun()
            with col2:
                if st.form_submit_button("❌ Cancelar"):
                    del st.session_state.participante_editando
                    st.rerun()


# ======================================================
# DIPLOMAS (Jerárquico): gestora → cliente → acción → grupo → participante
# ======================================================
def mostrar_seccion_diplomas(supabase, session_state, empresas_service, grupos_service, empresa_id_gestora):
    st.markdown("### 🏅 Gestión de Diplomas")
    st.caption("Subida jerárquica: gestora → cliente → acción → grupo → participante (bucket 'diplomas').")

    tab_subir, tab_listado = st.tabs(["⬆️ Subir diploma", "📚 Listado / consulta"])

    # --------------------------
    # TAB: SUBIR
    # --------------------------
    with tab_subir:
        st.markdown("#### ⬆️ Subir nuevo diploma")

        # 1) Selección de Gestora y Cliente (según rol)
        if session_state.role == "admin":
            # Admin elige una gestora (o cualquier empresa raíz)
            empresas_dict_all = empresas_service.get_empresas_dict()  # todas
            # Heurística simple: primero elige empresa "titular" del bucket
            gestora_nombre = st.selectbox("Empresa titular (gestora o raíz) *", sorted(empresas_dict_all.keys()))
            gestora_id = empresas_dict_all[gestora_nombre]

            # Clientes de esa gestora
            clientes_dict = _get_clientes_de_gestora(supabase, gestora_id)
            # Si no tiene clientes, puede subir en su propia carpeta
            opciones_clientes = ["(Sin cliente: usar gestora)"] + sorted(clientes_dict.keys())
            cliente_nombre = st.selectbox("Empresa cliente (opcional)", opciones_clientes)
            if cliente_nombre == "(Sin cliente: usar gestora)":
                cliente_id = gestora_id
            else:
                cliente_id = clientes_dict[cliente_nombre]
        else:
            # Gestor: su empresa es la titular del bucket
            gestora_id = empresa_id_gestora
            # Puede elegir uno de sus clientes o su propia empresa
            clientes_dict = empresas_service.get_empresas_para_gestor(gestora_id)  # incluye gestora + clientes
            # Normalizar: dict nombre->id
            # (si tu servicio ya devuelve solo clientes, añadimos una entrada para la gestora)
            if not any(_id == gestora_id for _id in clientes_dict.values()):
                # añadir su propia empresa
                try:
                    res = supabase.table("empresas").select("id, nombre").eq("id", gestora_id).execute()
                    if res.data:
                        clientes_dict[res.data[0]["nombre"]] = gestora_id
                except Exception:
                    pass

            cliente_nombre = st.selectbox("Empresa cliente / tu empresa *", sorted(clientes_dict.keys()))
            cliente_id = clientes_dict[cliente_nombre]

        # 2) Grupo (filtrado por empresa cliente elegida)
        grupos_dict_empresa = grupos_service.get_grupos_dict(cliente_id)
        if not grupos_dict_empresa:
            st.warning("La empresa seleccionada no tiene grupos.")
            return

        grupo_nombre = st.selectbox("Grupo *", sorted(grupos_dict_empresa.keys()))
        grupo_id = grupos_dict_empresa[grupo_nombre]

        # 3) Acción formativa (para la ruta)
        accion_id, codigo_grupo = _get_accion_id_y_codigo(supabase, grupo_id)
        accion_segment = accion_id or "sin_accion"

        # 4) Participante (filtrado por empresa seleccionada y opcionalmente por grupo)
        df_part_empresa = _get_participantes_de_empresa(supabase, cliente_id)
        if df_part_empresa.empty:
            st.warning("No hay participantes en la empresa seleccionada.")
            return

        # Si quieres filtrar solo los del grupo:
        df_part_empresa = df_part_empresa[df_part_empresa["grupo_id"].fillna("") == grupo_id]

        if df_part_empresa.empty:
            st.warning("No hay participantes de esa empresa asignados a este grupo.")
            return

        opciones_part = {
            f"{r.get('nombre','')} {r.get('apellidos','')} — {r.get('email','')}": r["id"]
            for _, r in df_part_empresa.iterrows()
        }
        part_label = st.selectbox("Participante *", sorted(opciones_part.keys()))
        participante_id = opciones_part[part_label]

        # 5) Uploader
        archivo = st.file_uploader("Archivo diploma (PDF, JPG, PNG)", type=["pdf", "jpg", "jpeg", "png"])
        if archivo and st.button("⬆️ Subir diploma", type="primary"):
            try:
                # Ruta jerárquica: diplomas/{gestora}/{cliente}/{accion}/{grupo}/{participante}/{filename}
                ruta = f"diplomas/{gestora_id}/{cliente_id}/{accion_segment}/{grupo_id}/{participante_id}/{archivo.name}"

                supabase.storage.from_("diplomas").upload(
                    ruta,
                    archivo.getvalue(),
                    {"upsert": "true", "contentType": archivo.type or "application/octet-stream"}
                )
                url = supabase.storage.from_("diplomas").get_public_url(ruta)

                # Insertar registro en tabla diplomas
                supabase.table("diplomas").insert({
                    "participante_id": participante_id,
                    "grupo_id": grupo_id,
                    "url": url,
                    "fecha_subida": datetime.utcnow().isoformat(),
                    "archivo_nombre": archivo.name
                }).execute()

                st.success("✅ Diploma subido y registrado correctamente.")
            except Exception as e:
                st.error(f"❌ Error al subir diploma: {e}")

    # --------------------------
    # TAB: LISTADO / CONSULTA
    # --------------------------
    with tab_listado:
        st.markdown("#### 📚 Buscar diplomas por Empresa → Grupo → Participante")

        # Selección empresa (admin/gestor)
        if session_state.role == "admin":
            empresas_dict_all = empresas_service.get_empresas_dict()
            empresa_nombre = st.selectbox("Empresa", sorted(empresas_dict_all.keys()), key="dipl_list_emp")
            empresa_sel_id = empresas_dict_all[empresa_nombre]
        else:
            # gestora + clientes
            empresas_gestor = empresas_service.get_empresas_para_gestor(empresa_id_gestora)
            # Si viniera solo clientes, añadimos gestora
            if not any(_id == empresa_id_gestora for _id in empresas_gestor.values()):
                try:
                    res = supabase.table("empresas").select("id, nombre").eq("id", empresa_id_gestora).execute()
                    if res.data:
                        empresas_gestor[res.data[0]["nombre"]] = empresa_id_gestora
                except Exception:
                    pass
            empresa_nombre = st.selectbox("Empresa", sorted(empresas_gestor.keys()), key="dipl_list_emp_gestor")
            empresa_sel_id = empresas_gestor[empresa_nombre]

        grupos_dict_emp = grupos_service.get_grupos_dict(empresa_sel_id)
        if not grupos_dict_emp:
            st.info("La empresa seleccionada no tiene grupos.")
            return

        grupo_nombre = st.selectbox("Grupo", sorted(grupos_dict_emp.keys()), key="dipl_list_grupo")
        grupo_id = grupos_dict_emp[grupo_nombre]

        # Participantes del grupo (de esa empresa)
        df_part_emp = _get_participantes_de_empresa(supabase, empresa_sel_id)
        df_part_emp = df_part_emp[df_part_emp["grupo_id"].fillna("") == grupo_id]
        if df_part_emp.empty:
            st.info("No hay participantes de esa empresa en el grupo seleccionado.")
            return

        opciones_part = {f"{r.get('nombre','')} {r.get('apellidos','')} — {r.get('email','')}": r["id"] for _, r in df_part_emp.iterrows()}
        part_label = st.selectbox("Participante", sorted(opciones_part.keys()), key="dipl_list_part")
        participante_id = opciones_part[part_label]

        # Mostrar diplomas
        df_diplomas = _get_diplomas_participante_grupo(supabase, participante_id, grupo_id)
        if df_diplomas.empty:
            st.info("No hay diplomas subidos para este participante en el grupo seleccionado.")
        else:
            st.dataframe(
                df_diplomas.rename(columns={"archivo_nombre": "Archivo", "fecha_subida": "Fecha", "url": "URL"}),
                use_container_width=True,
                hide_index=True
            )

            # Opcional: eliminar registro (no borramos del storage por no tener ruta guardada)
            borrar = st.checkbox("Quiero eliminar un registro de diploma")
            if borrar:
                opciones = {
                    f"{row['archivo_nombre']} — {row['fecha_subida'][:19]}": row["id"]
                    for _, row in df_diplomas.iterrows()
                }
                sel = st.selectbox("Registro a eliminar", list(opciones.keys()))
                if st.button("🗑️ Eliminar registro en BD", type="secondary"):
                    try:
                        supabase.table("diplomas").delete().eq("id", opciones[sel]).execute()
                        st.success("Registro eliminado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al eliminar: {e}")


# ======================================================
# IMPORTACIÓN MASIVA (placeholder)
# ======================================================
def mostrar_importacion_masiva():
    with st.expander("📂 Importación masiva de participantes"):
        st.markdown("Sube un archivo Excel con participantes (ajusta aquí tu lógica de importación).")
        archivo_subido = st.file_uploader("Subir archivo Excel", type=['xlsx', 'xls'])
        if archivo_subido and st.button("🚀 Procesar importación"):
            st.info("Procesamiento pendiente de tu lógica de importación masiva.")
