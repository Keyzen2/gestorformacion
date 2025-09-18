import streamlit as st
import pandas as pd
from datetime import datetime
from utils import export_csv, validar_dni_cif
from services.data_service import get_data_service
from services.participantes_service import get_participantes_service
from services.grupos_service import get_grupos_service
from services.empresas_service import get_empresas_service


def main(supabase, session_state):
    st.markdown("## 👥 Participantes")
    st.caption("Gestión de participantes en los grupos de formación.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # =========================
    # Inicializar servicios
    # =========================
    data_service = get_data_service(supabase, session_state)
    participantes_service = get_participantes_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)
    empresas_service = get_empresas_service(supabase, session_state)

    empresa_id = session_state.user.get("empresa_id")

    # =========================
    # Cargar empresas y grupos según rol
    # =========================
    try:
        empresas_dict = empresas_service.get_empresas_para_grupos()
    except Exception as e:
        st.error(f"❌ Error cargando empresas: {e}")
        empresas_dict = {}

    try:
        if session_state.role == "admin":
            df_grupos = grupos_service.get_grupos_completos()
        else:
            # Grupos solo de la empresa del gestor + clientes
            df_grupos = grupos_service.get_grupos_por_empresas(list(empresas_dict.values()))
    except Exception as e:
        st.error(f"❌ Error cargando grupos: {e}")
        df_grupos = pd.DataFrame()

    # =========================
    # Cargar participantes
    # =========================
    try:
        df_participantes = participantes_service.get_participantes_completos()
    except Exception as e:
        st.error(f"❌ Error al cargar participantes: {e}")
        return

    # =========================
    # Métricas básicas
    # =========================
    if not df_participantes.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("👥 Total Participantes", len(df_participantes))
        with col2:
            finalizados = len(df_participantes[df_participantes["estado"] == "finalizado"])
            st.metric("✅ Finalizados", finalizados)
        with col3:
            este_mes = len(df_participantes[
                pd.to_datetime(df_participantes["created_at"], errors="coerce").dt.month == datetime.now().month
            ])
            st.metric("🆕 Nuevos este mes", este_mes)

    st.divider()

    # =========================
    # Listado de participantes
    # =========================
    st.markdown("### 📊 Listado de Participantes")

    if df_participantes.empty:
        st.info("📋 No hay participantes registrados todavía.")
    else:
        columnas = ["dni", "nombre", "apellidos", "email", "telefono", "grupo_nombre"]
        if session_state.role == "admin" and "empresa_nombre" in df_participantes.columns:
            columnas.insert(2, "empresa_nombre")

        event = st.dataframe(
            df_participantes[columnas],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="tabla_participantes"
        )

        if event.selection.rows:
            selected_idx = event.selection.rows[0]
            participante_seleccionado = df_participantes.iloc[selected_idx]
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("✏️ Editar Participante", type="primary", use_container_width=True):
                    st.session_state.participante_editando = participante_seleccionado["id"]
                    st.rerun()

    st.divider()

    # =========================
    # Crear nuevo participante
    # =========================
    if session_state.role in ["admin", "gestor"]:
        with st.expander("➕ Crear Nuevo Participante", expanded=False):
            mostrar_formulario_participante(
                supabase,
                session_state,
                participantes_service,
                empresas_dict,
                df_grupos,
                participante_id="nuevo"
            )

    # =========================
    # Formulario de edición
    # =========================
    if hasattr(st.session_state, "participante_editando") and st.session_state.participante_editando:
        mostrar_formulario_participante(
            supabase,
            session_state,
            participantes_service,
            empresas_dict,
            df_grupos,
            participante_id=st.session_state.participante_editando
        )

    # =========================
    # Exportación
    # =========================
    if not df_participantes.empty:
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Exportar a CSV"):
                export_csv(df_participantes, filename="participantes.csv")
        with col2:
            st.metric("📋 Registros mostrados", len(df_participantes))


def mostrar_formulario_participante(
    supabase,
    session_state,
    participantes_service,
    empresas_dict,
    df_grupos,
    participante_id="nuevo"
):
    """Formulario unificado para crear/editar participantes."""

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
            nombre = st.text_input("Nombre *", value=participante_data.get("nombre", ""), key=f"part_nombre_{participante_id}")
            apellidos = st.text_input("Apellidos *", value=participante_data.get("apellidos", ""), key=f"part_apellidos_{participante_id}")
            dni = st.text_input("DNI/NIE *", value=participante_data.get("dni", ""), key=f"part_dni_{participante_id}")
            email = st.text_input("Email", value=participante_data.get("email", ""), key=f"part_email_{participante_id}")
        with col2:
            telefono = st.text_input("Teléfono", value=participante_data.get("telefono", ""), key=f"part_telefono_{participante_id}")
            fecha_nacimiento = st.date_input(
                "Fecha de Nacimiento",
                value=pd.to_datetime(participante_data.get("fecha_nacimiento"), errors="coerce").date()
                if participante_data.get("fecha_nacimiento") else datetime.today().date(),
                key=f"part_fecha_nacimiento_{participante_id}"
            )

            # =========================
            # Selector de empresa y grupo según jerarquía
            # =========================
            empresa_sel = None
            grupo_sel = None

            if empresas_dict:
                empresa_sel = st.selectbox(
                    "Empresa *",
                    options=[""] + list(empresas_dict.keys()),
                    index=([""] + list(empresas_dict.keys())).index(participante_data.get("empresa_nombre"))
                    if participante_data.get("empresa_nombre") in ([""] + list(empresas_dict.keys())) else 0,
                    key=f"part_empresa_{participante_id}"
                )

            if empresa_sel and not df_grupos.empty:
                grupos_empresa = df_grupos[df_grupos["empresa_nombre"] == empresa_sel]
                if not grupos_empresa.empty:
                    grupo_sel = st.selectbox(
                        "Grupo *",
                        options=[""] + list(grupos_empresa["codigo_grupo"].astype(str)),
                        index=([""] + list(grupos_empresa["codigo_grupo"].astype(str))).index(
                            participante_data.get("grupo_nombre")
                        )
                        if participante_data.get("grupo_nombre") in ([""] + list(grupos_empresa["codigo_grupo"].astype(str))) else 0,
                        key=f"part_grupo_{participante_id}"
                    )

        # =========================
        # Botones
        # =========================
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 Guardar", type="primary"):
                if not nombre or not apellidos or not dni:
                    st.error("Los campos Nombre, Apellidos y DNI son obligatorios.")
                elif not validar_dni_cif(dni):
                    st.error("El DNI/NIE no tiene un formato válido.")
                elif not empresa_sel or not grupo_sel:
                    st.error("Debe seleccionar empresa y grupo.")
                else:
                    datos = {
                        "nombre": nombre,
                        "apellidos": apellidos,
                        "dni": dni.upper(),
                        "email": email,
                        "telefono": telefono,
                        "fecha_nacimiento": fecha_nacimiento.isoformat() if fecha_nacimiento else None,
                        "empresa_id": empresas_dict.get(empresa_sel),
                        "grupo_id": int(df_grupos[df_grupos["codigo_grupo"].astype(str) == grupo_sel]["id"].values[0])
                        if grupo_sel else None,
                        "updated_at": datetime.utcnow().isoformat()
                    }

                    if es_creacion:
                        datos["created_at"] = datetime.utcnow().isoformat()
                        participantes_service.create_participante(datos)
                        st.success("Participante creado correctamente.")
                    else:
                        participantes_service.update_participante(participante_id, datos)
                        st.success("Participante actualizado correctamente.")

                    if hasattr(st.session_state, "participante_editando"):
                        del st.session_state.participante_editando
                    st.rerun()
        with col2:
            if not es_creacion and st.form_submit_button("❌ Cancelar"):
                del st.session_state.participante_editando
                st.rerun()
