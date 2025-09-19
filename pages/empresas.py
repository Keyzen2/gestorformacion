import streamlit as st
import pandas as pd
from datetime import datetime
from utils import export_csv, validar_dni_cif
from services.empresas_service import get_empresas_service

def main(supabase, session_state):
    st.markdown("## 🏢 Empresas")
    st.caption("Gestión de empresas SaaS, gestoras y empresas cliente.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicio
    empresas_service = get_empresas_service(supabase, session_state)

    # =========================
    # Cargar empresas
    # =========================
    try:
        df_empresas = empresas_service.get_empresas_completas()
    except Exception as e:
        st.error(f"❌ Error al cargar empresas: {e}")
        return

    # =========================
    # Métricas básicas
    # =========================
    if not df_empresas.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏢 Total Empresas", len(df_empresas))
        with col2:
            st.metric("📊 Gestoras", len(df_empresas[df_empresas["tipo_empresa"] == "GESTORA"]))
        with col3:
            st.metric("👥 Clientes Gestoras", len(df_empresas[df_empresas["tipo_empresa"] == "CLIENTE_GESTOR"]))
        with col4:
            st.metric("💻 SaaS Directos", len(df_empresas[df_empresas["tipo_empresa"] == "CLIENTE_SAAS"]))

    st.divider()

    # =========================
    # Filtros avanzados
    # =========================
    st.markdown("### 🔍 Filtros avanzados")

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_tipo = st.selectbox("Tipo de empresa", ["", "CLIENTE_SAAS", "GESTORA", "CLIENTE_GESTOR"])
    with col2:
        filtro_provincia = st.text_input("Provincia")
    with col3:
        filtro_ciudad = st.text_input("Ciudad")

    df_filtrado = df_empresas.copy()
    if filtro_tipo:
        df_filtrado = df_filtrado[df_filtrado["tipo_empresa"] == filtro_tipo]
    if filtro_provincia:
        df_filtrado = df_filtrado[df_filtrado["provincia"].str.contains(filtro_provincia, case=False, na=False)]
    if filtro_ciudad:
        df_filtrado = df_filtrado[df_filtrado["ciudad"].str.contains(filtro_ciudad, case=False, na=False)]
    # =========================
    # Tablas principales
    # =========================
    st.markdown("### 📋 Listado de Empresas")

    if df_filtrado.empty:
        st.info("📭 No hay empresas registradas con los filtros aplicados.")
    else:
        # Separar la empresa del gestor
        empresa_id = session_state.user.get("empresa_id")
        df_mi_empresa = df_filtrado[df_filtrado["id"] == empresa_id] if empresa_id else pd.DataFrame()
        df_clientes = df_filtrado[df_filtrado["empresa_matriz_id"] == empresa_id] if empresa_id else df_filtrado

        # =========================
        # Mostrar Mi Empresa
        # =========================
        if not df_mi_empresa.empty:
            st.markdown("#### 🏢 Mi Empresa")
            event_mi = st.dataframe(
                df_mi_empresa[["nombre", "cif", "tipo_empresa", "provincia", "ciudad"]],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="tabla_mi_empresa"
            )
            if event_mi.selection.rows:
                idx = event_mi.selection.rows[0]
                empresa_sel = df_mi_empresa.iloc[idx]
                st.session_state.empresa_editando = empresa_sel["id"]
                st.rerun()

        st.divider()

        # =========================
        # Mostrar Empresas Cliente
        # =========================
        st.markdown("#### 👥 Empresas Cliente")
        event_clientes = st.dataframe(
            df_clientes[["nombre", "cif", "tipo_empresa", "provincia", "ciudad"]],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="tabla_empresas_clientes"
        )
        if event_clientes.selection.rows:
            idx = event_clientes.selection.rows[0]
            empresa_sel = df_clientes.iloc[idx]
            st.session_state.empresa_editando = empresa_sel["id"]
            st.rerun()

    st.divider()

    # =========================
    # Botón Crear Nueva Empresa
    # =========================
    if session_state.role in ["admin", "gestor"]:
        if st.button("➕ Crear Nueva Empresa", type="primary", use_container_width=True):
            st.session_state.empresa_editando = "nueva"
            st.rerun()

    # =========================
    # Mostrar formulario si corresponde
    # =========================
    if hasattr(st.session_state, "empresa_editando") and st.session_state.empresa_editando:
        es_creacion = st.session_state.empresa_editando == "nueva"
        datos_empresa = {}
        if not es_creacion:
            try:
                datos_empresa = empresas_service.get_empresa_by_id(st.session_state.empresa_editando)
            except Exception as e:
                st.error(f"❌ Error al cargar empresa: {e}")
                datos_empresa = {}
        mostrar_formulario_empresa_interactivo(datos_empresa, empresas_service, session_state, es_creacion=es_creacion)
def mostrar_formulario_empresa_interactivo(datos, empresas_service, session_state, es_creacion=False):
    """Formulario unificado para crear o editar empresa con todos los campos."""
    st.markdown("### 📝 Datos de la Empresa")

    with st.form("form_empresa", clear_on_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            nombre = st.text_input("Nombre *", value=datos.get("nombre", ""), key="nombre_empresa")
            cif = st.text_input("CIF *", value=datos.get("cif", ""), key="cif_empresa")
            email = st.text_input("Email", value=datos.get("email", ""), key="email_empresa")
            telefono = st.text_input("Teléfono", value=datos.get("telefono", ""), key="telefono_empresa")
            tipo_empresa = st.selectbox(
                "Tipo de Empresa",
                ["CLIENTE_SAAS", "GESTORA", "CLIENTE_GESTOR"],
                index=["CLIENTE_SAAS", "GESTORA", "CLIENTE_GESTOR"].index(datos.get("tipo_empresa", "CLIENTE_SAAS")),
                key="tipo_empresa"
            )

        with col2:
            direccion = st.text_area("Dirección", value=datos.get("direccion", ""), key="direccion_empresa")
            provincia = st.text_input("Provincia", value=datos.get("provincia", ""), key="provincia_empresa")
            ciudad = st.text_input("Ciudad", value=datos.get("ciudad", ""), key="ciudad_empresa")
            cp = st.text_input("Código Postal", value=datos.get("codigo_postal", ""), key="cp_empresa")

        st.divider()

        # Información adicional
        with st.expander("📑 Información adicional"):
            representante_nombre = st.text_input("Representante", value=datos.get("representante_nombre", ""), key="rep_nombre")
            representante_dni = st.text_input("DNI Representante", value=datos.get("representante_dni", ""), key="rep_dni")
            iso_activo = st.checkbox("ISO 9001 Activo", value=datos.get("iso_activo", False), key="iso_activo")
            rgpd_activo = st.checkbox("RGPD Activo", value=datos.get("rgpd_activo", False), key="rgpd_activo")

        st.divider()

        # Botones
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 Guardar", type="primary"):
                datos_empresa = {
                    "nombre": nombre.strip(),
                    "cif": cif.strip().upper(),
                    "email": email.strip().lower() if email else None,
                    "telefono": telefono.strip(),
                    "direccion": direccion.strip(),
                    "provincia": provincia.strip(),
                    "ciudad": ciudad.strip(),
                    "codigo_postal": cp.strip(),
                    "tipo_empresa": tipo_empresa,
                    "representante_nombre": representante_nombre.strip(),
                    "representante_dni": representante_dni.strip(),
                    "iso_activo": iso_activo,
                    "rgpd_activo": rgpd_activo,
                    "empresa_matriz_id": session_state.user.get("empresa_id") if tipo_empresa == "CLIENTE_GESTOR" else None,
                    "creado_por_usuario_id": session_state.user.get("id")
                }
                try:
                    if es_creacion:
                        exito = empresas_service.create_empresa(datos_empresa)
                        if exito:
                            st.success("✅ Empresa creada correctamente")
                    else:
                        exito = empresas_service.update_empresa(datos.get("id"), datos_empresa)
                        if exito:
                            st.success("✅ Empresa actualizada correctamente")
                    st.session_state.empresa_editando = None
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar empresa: {e}")

        with col2:
            if st.form_submit_button("❌ Cancelar"):
                st.session_state.empresa_editando = None
                st.rerun()
def mostrar_estadisticas_empresas(df_empresas):
    """Muestra métricas básicas de empresas."""
    if df_empresas.empty:
        st.info("No hay empresas registradas todavía.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏢 Total Empresas", len(df_empresas))
    with col2:
        st.metric("📊 Gestoras", len(df_empresas[df_empresas["tipo_empresa"] == "GESTORA"]))
    with col3:
        st.metric("👥 Clientes SaaS", len(df_empresas[df_empresas["tipo_empresa"] == "CLIENTE_SAAS"]))
    with col4:
        st.metric("🤝 Clientes Gestor", len(df_empresas[df_empresas["tipo_empresa"] == "CLIENTE_GESTOR"]))

    st.divider()


def aplicar_filtros_empresas(df_empresas):
    """Aplica filtros avanzados a las empresas."""
    with st.expander("🔍 Filtros Avanzados", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            tipo_filtro = st.multiselect(
                "Tipo de Empresa",
                options=df_empresas["tipo_empresa"].dropna().unique().tolist(),
                default=[]
            )
        with col2:
            provincia_filtro = st.multiselect(
                "Provincia",
                options=df_empresas["provincia"].dropna().unique().tolist(),
                default=[]
            )
        with col3:
            ciudad_filtro = st.text_input("Ciudad contiene")

        # Aplicar filtros
        if tipo_filtro:
            df_empresas = df_empresas[df_empresas["tipo_empresa"].isin(tipo_filtro)]
        if provincia_filtro:
            df_empresas = df_empresas[df_empresas["provincia"].isin(provincia_filtro)]
        if ciudad_filtro:
            df_empresas = df_empresas[df_empresas["ciudad"].str.contains(ciudad_filtro, case=False, na=False)]

    return df_empresas


def exportar_empresas(df_empresas):
    """Botón para exportar empresas a CSV."""
    st.divider()
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("📤 Exportar a CSV", use_container_width=True):
            from utils import export_csv
            export_csv(df_empresas, filename="empresas.csv")
    with col2:
        st.caption(f"Mostrando {len(df_empresas)} registros")
