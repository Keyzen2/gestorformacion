import streamlit as st
import pandas as pd
import io
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from utils import validar_dni_cif, export_csv
from services.participantes_service import get_participantes_service
from services.empresas_service import get_empresas_service
from services.grupos_service import get_grupos_service

# =========================
# CONFIG STREAMLIT
# =========================
st.set_page_config(
    page_title="👥 Participantes",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# HELPERS CACHEADOS
# =========================
@st.cache_data(ttl=300)
def cargar_empresas_disponibles(_empresas_service, _session_state):
    """Devuelve las empresas disponibles según rol."""
    try:
        df = _empresas_service.get_empresas_con_jerarquia()
        if df.empty:
            return df

        if _session_state.role == "gestor":
            empresa_id = _session_state.user.get("empresa_id")
            # Solo su propia empresa y las que dependen de ella
            df = df[(df["id"] == empresa_id) | (df["empresa_matriz_id"] == empresa_id)]

        return df
    except Exception as e:
        st.error(f"❌ Error cargando empresas disponibles: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def cargar_grupos(_grupos_service, _session_state):
    """Carga grupos disponibles según permisos."""
    try:
        df_grupos = _grupos_service.get_grupos_completos()
        if _session_state.role == "admin":
            return df_grupos
        elif _session_state.role == "gestor":
            empresa_id = _session_state.user.get("empresa_id")
            return df_grupos[df_grupos["empresa_id"] == empresa_id]
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error cargando grupos: {e}")
        return pd.DataFrame()

# =========================
# MÉTRICAS DE PARTICIPANTES
# =========================
def mostrar_metricas_participantes(participantes_service, session_state):
    """Muestra métricas generales de los participantes."""
    try:
        metricas = participantes_service.get_estadisticas_participantes()

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("👥 Total Participantes", metricas.get("total", 0))
        with col2:
            st.metric("🆕 Nuevos (30 días)", metricas.get("nuevos_mes", 0))
        with col3:
            st.metric("🎓 En curso", metricas.get("en_curso", 0))
        with col4:
            st.metric("✅ Finalizados", metricas.get("finalizados", 0))
        with col5:
            st.metric("📜 Con diploma", metricas.get("con_diploma", 0))

    except Exception as e:
        st.error(f"❌ Error cargando métricas de participantes: {e}")

# =========================
# TABLA GENERAL
# =========================
def mostrar_tabla_participantes(df_participantes, session_state, titulo_tabla="📋 Lista de Participantes"):
    """Muestra tabla de participantes con filtros, paginación y selección de fila."""
    if df_participantes.empty:
        st.info("📋 No hay participantes para mostrar")
        return None

    st.markdown(f"### {titulo_tabla}")

    # 🔎 Filtros avanzados (fijos arriba)
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_nombre = st.text_input("👤 Nombre/Apellidos contiene", key="filtro_tabla_nombre")
    with col2:
        filtro_dni = st.text_input("🆔 Documento contiene", key="filtro_tabla_dni")
    with col3:
        filtro_empresa = st.text_input("🏢 Empresa contiene", key="filtro_tabla_empresa")

    if filtro_nombre:
        df_participantes = df_participantes[
            df_participantes["nombre"].str.contains(filtro_nombre, case=False, na=False) |
            df_participantes["apellidos"].str.contains(filtro_nombre, case=False, na=False)
        ]
    if filtro_dni:
        df_participantes = df_participantes[df_participantes["dni"].str.contains(filtro_dni, case=False, na=False)]
    if filtro_empresa:
        df_participantes = df_participantes[df_participantes["empresa_nombre"].str.contains(filtro_empresa, case=False, na=False)]

    # 🔢 Selector de registros por página
    page_size = st.selectbox("📑 Registros por página", [10, 20, 50, 100], index=1, key="page_size_tabla")

    # 📄 Paginación
    total_rows = len(df_participantes)
    total_pages = (total_rows // page_size) + (1 if total_rows % page_size else 0)
    page_number = st.number_input("Página", min_value=1, max_value=max(total_pages, 1), step=1, value=1, key="page_num_tabla")

    start_idx = (page_number - 1) * page_size
    end_idx = start_idx + page_size
    df_paged = df_participantes.iloc[start_idx:end_idx]

    # Configuración columnas
    columnas = ["nombre", "apellidos", "dni", "email", "telefono", "empresa_nombre"]
    column_config = {
        "nombre": st.column_config.TextColumn("👤 Nombre", width="medium"),
        "apellidos": st.column_config.TextColumn("👥 Apellidos", width="large"),
        "dni": st.column_config.TextColumn("🆔 Documento", width="small"),
        "email": st.column_config.TextColumn("📧 Email", width="large"),
        "telefono": st.column_config.TextColumn("📞 Teléfono", width="medium"),
        "empresa_nombre": st.column_config.TextColumn("🏢 Empresa", width="large")
    }

    # Mostrar tabla
    evento = st.dataframe(
        df_paged[columnas],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    if evento.selection.rows:
        return df_paged.iloc[evento.selection.rows[0]], df_paged
    return None, df_paged
    
# =========================
# FORMULARIO DE PARTICIPANTE
# =========================
def mostrar_formulario_participante(participante_data, participantes_service, empresas_service, grupos_service, session_state, es_creacion=False):
    """Formulario para crear o editar un participante."""

    if es_creacion:
        st.subheader("➕ Crear Participante")
        datos = {}
    else:
        st.subheader(f"✏️ Editar Participante: {participante_data['nombre']} {participante_data.get('apellidos','')}")
        datos = participante_data.copy()

    # form_id único
    form_id = f"participante_{datos.get('id','nuevo')}_{'crear' if es_creacion else 'editar'}"

    with st.form(form_id, clear_on_submit=es_creacion):
        # =========================
        # DATOS PERSONALES
        # =========================
        st.markdown("### 👤 Datos Personales")
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre", value=datos.get("nombre",""), key=f"{form_id}_nombre")
            apellidos = st.text_input("Apellidos", value=datos.get("apellidos",""), key=f"{form_id}_apellidos")
            tipo_documento = st.selectbox(
                "Tipo de Documento",
                options=["", "DNI", "NIE", "PASAPORTE"],
                index=["","DNI","NIE","PASAPORTE"].index(datos.get("tipo_documento","")) if datos.get("tipo_documento","") in ["","DNI","NIE","PASAPORTE"] else 0,
                key=f"{form_id}_tipo_doc"
            )
            dni = st.text_input("Documento", value=datos.get("dni",""), key=f"{form_id}_dni")
            nif = st.text_input("NIF", value=datos.get("nif",""), key=f"{form_id}_nif")
            niss = st.text_input("NISS", value=datos.get("niss",""), key=f"{form_id}_niss")
        with col2:
            fecha_nacimiento = st.date_input(
                "Fecha de nacimiento",
                value=datos.get("fecha_nacimiento") if datos.get("fecha_nacimiento") else date(1990,1,1),
                key=f"{form_id}_fecha_nac"
            )
            sexo = st.selectbox(
                "Sexo",
                options=["", "M", "F", "O"],
                index=["","M","F","O"].index(datos.get("sexo","")) if datos.get("sexo","") in ["","M","F","O"] else 0,
                key=f"{form_id}_sexo"
            )
            telefono = st.text_input("Teléfono", value=datos.get("telefono",""), key=f"{form_id}_tel")
            email = st.text_input("Email", value=datos.get("email",""), key=f"{form_id}_email")

        # =========================
        # DATOS EMPRESA
        # =========================
        st.markdown("### 🏢 Empresa Asociada")
        df_empresas = cargar_empresas_disponibles(empresas_service, session_state)
        empresa_options = {row["nombre"]: row["id"] for _,row in df_empresas.iterrows()}

        empresa_actual_id = datos.get("empresa_id")
        empresa_actual_nombre = next((k for k,v in empresa_options.items() if v == empresa_actual_id), "")

        empresa_sel = st.selectbox(
            "Selecciona Empresa",
            options=[""] + list(empresa_options.keys()),
            index=list(empresa_options.keys()).index(empresa_actual_nombre)+1 if empresa_actual_nombre else 0,
            key=f"{form_id}_empresa"
        )
        empresa_id = empresa_options.get(empresa_sel) if empresa_sel else None

        # =========================
        # DATOS FORMACIÓN
        # =========================
        st.markdown("### 🎓 Formación")
        df_grupos = cargar_grupos(grupos_service, session_state)
        grupo_options = {row["codigo_grupo"]: row["id"] for _,row in df_grupos.iterrows()} if not df_grupos.empty else {}

        grupo_actual_id = datos.get("grupo_id")
        grupo_actual_nombre = next((k for k,v in grupo_options.items() if v == grupo_actual_id), "")

        grupo_sel = st.selectbox(
            "Asignar a Grupo",
            options=[""] + list(grupo_options.keys()),
            index=list(grupo_options.keys()).index(grupo_actual_nombre)+1 if grupo_actual_nombre else 0,
            key=f"{form_id}_grupo"
        )
        grupo_id = grupo_options.get(grupo_sel) if grupo_sel else None

        # =========================
        # VALIDACIONES
        # =========================
        errores = []
        if not nombre:
            errores.append("Nombre requerido")
        if not apellidos:
            errores.append("Apellidos requeridos")
        if dni and not validar_dni_cif(dni):
            errores.append("Documento inválido")
        if not empresa_id:
            errores.append("Debe seleccionar una empresa")

        if errores:
            st.error("⚠️ Errores: " + ", ".join(errores))

        # =========================
        # BOTONES
        # =========================
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button(
                "➕ Crear Participante" if es_creacion else "💾 Guardar Cambios",
                type="primary",
                use_container_width=True
            )
        with col2:
            eliminar = st.form_submit_button(
                "🗑️ Eliminar" if not es_creacion and session_state.role == "admin" else "Cancelar",
                type="secondary",
                use_container_width=True
            ) if not es_creacion else False

        # =========================
        # PROCESAMIENTO
        # =========================
        if submitted:
            procesar_guardado_participante(
                datos, nombre, apellidos, tipo_documento, dni, nif, niss,
                fecha_nacimiento, sexo, telefono, email, empresa_id, grupo_id,
                participantes_service, es_creacion
            )

        if eliminar:
            if st.session_state.get("confirmar_eliminar_participante"):
                try:
                    ok = participantes_service.delete_participante(datos["id"])
                    if ok:
                        st.success("✅ Participante eliminado correctamente")
                        del st.session_state["confirmar_eliminar_participante"]
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error eliminando participante: {e}")
            else:
                st.session_state["confirmar_eliminar_participante"] = True
                st.warning("⚠️ Pulsa nuevamente para confirmar eliminación")

# =========================
# PROCESAR GUARDADO
# =========================
def procesar_guardado_participante(datos, nombre, apellidos, tipo_documento, dni, nif, niss,
                                   fecha_nacimiento, sexo, telefono, email, empresa_id, grupo_id,
                                   participantes_service, es_creacion=False):
    """Procesa creación o actualización de un participante."""
    try:
        payload = {
            "nombre": nombre,
            "apellidos": apellidos,
            "tipo_documento": tipo_documento or None,
            "dni": dni or None,
            "nif": nif or None,
            "niss": niss or None,
            "fecha_nacimiento": fecha_nacimiento.isoformat() if fecha_nacimiento else None,
            "sexo": sexo or None,
            "telefono": telefono or None,
            "email": email or None,
            "empresa_id": empresa_id,
            "grupo_id": grupo_id or None,
            "updated_at": datetime.utcnow().isoformat()
        }

        if es_creacion:
            ok, _ = participantes_service.crear_participante(payload)
            if ok:
                st.success("✅ Participante creado correctamente")
                st.rerun()
            else:
                st.error("❌ Error al crear participante")
        else:
            ok = participantes_service.update_participante(datos["id"], payload)
            if ok:
                st.success("✅ Cambios guardados correctamente")
                st.rerun()
            else:
                st.error("❌ Error al actualizar participante")
    except Exception as e:
        st.error(f"❌ Error procesando participante: {e}")


# =========================
# EXPORTACIÓN DE PARTICIPANTES
# =========================
def exportar_participantes(participantes_service, session_state, df_filtrado=None, solo_visibles=False):
    """Exporta participantes a CSV respetando filtros, paginación y rol."""
    try:
        # Si no se pasa df_filtrado, cargamos todo desde el servicio
        if df_filtrado is None:
            df = participantes_service.get_participantes_completos()
            # 🔒 Filtrado por rol
            if session_state.role == "gestor":
                empresa_id = session_state.user.get("empresa_id")
                df = df[df["empresa_id"] == empresa_id]
        else:
            df = df_filtrado.copy()

        if df.empty:
            st.warning("⚠️ No hay participantes para exportar.")
            return

        # 🔘 Opción de exportación
        export_scope = st.radio(
            "¿Qué quieres exportar?",
            ["📄 Solo registros visibles en la tabla", "🌍 Todos los registros filtrados"],
            horizontal=True
        )

        if export_scope == "📄 Solo registros visibles en la tabla" and solo_visibles:
            df_export = df
        else:
            # Recargamos completo para "Todos los registros filtrados"
            df_export = participantes_service.get_participantes_completos()
            if session_state.role == "gestor":
                empresa_id = session_state.user.get("empresa_id")
                df_export = df_export[df_export["empresa_id"] == empresa_id]

        st.download_button(
            "📥 Exportar participantes a CSV",
            data=df_export.to_csv(index=False).encode("utf-8"),
            file_name=f"participantes_{datetime.today().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    except Exception as e:
        st.error(f"❌ Error exportando participantes: {e}")

# =========================
# IMPORTACIÓN DE PARTICIPANTES (con validaciones extendidas)
# =========================
def importar_participantes(participantes_service, empresas_service, session_state):
    """Importa participantes desde un archivo CSV/XLSX, con validaciones de datos y control de rol."""
    uploaded = st.file_uploader("📤 Subir archivo CSV/XLSX", type=["csv", "xlsx"], accept_multiple_files=False)

    # 📑 Plantilla ejemplo
    ejemplo_df = pd.DataFrame([{
        "nombre": "Juan",
        "apellidos": "Pérez Gómez",
        "dni": "12345678A",
        "nif": "12345678A",
        "niss": "12345678901",
        "email": "juan.perez@correo.com",
        "telefono": "600123456",
        "fecha_nacimiento": "1985-06-15",
        "sexo": "M",
        "empresa_id": "",  # Solo lo usa admin
        "grupo_id": ""     # Opcional
    }])

    # ⚠️ Guardar plantilla en memoria correctamente
    buffer = io.BytesIO()
    ejemplo_df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    st.download_button(
        "📑 Descargar plantilla XLSX",
        data=buffer,
        file_name="plantilla_participantes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    if not uploaded:
        return

    try:
        if uploaded.name.endswith(".csv"):
            df = pd.read_csv(uploaded, dtype=str)
        else:
            df = pd.read_excel(uploaded, dtype=str)

        st.success(f"✅ {len(df)} filas cargadas desde {uploaded.name}")
        st.dataframe(df.head(10), use_container_width=True)

        if st.button("🚀 Importar participantes", type="primary", use_container_width=True):
            errores = []
            for idx, fila in df.iterrows():
                try:
                    # === Validaciones básicas ===
                    if not fila.get("nombre") or not fila.get("apellidos"):
                        raise ValueError("Nombre y apellidos son obligatorios")

                    dni = fila.get("dni")
                    if dni and not validar_dni_cif(dni):
                        raise ValueError(f"DNI/NIF inválido: {dni}")

                    niss = fila.get("niss")
                    if niss and not validar_niss(niss):
                        raise ValueError(f"NISS inválido: {niss}")

                    email = fila.get("email")
                    if email and ("@" not in email or "." not in email.split("@")[-1]):
                        raise ValueError(f"Email inválido: {email}")

                    telefono = fila.get("telefono")
                    if telefono and not telefono.isdigit():
                        raise ValueError(f"Teléfono inválido: {telefono}")

                    # === Empresa y Grupo según rol ===
                    if session_state.role == "gestor":
                        empresa_id = session_state.user.get("empresa_id")
                    else:  # admin
                        empresa_id = fila.get("empresa_id") or None

                    grupo_id = fila.get("grupo_id") or None

                    # === Construcción de datos ===
                    datos = {
                        "nombre": fila.get("nombre"),
                        "apellidos": fila.get("apellidos"),
                        "dni": dni,
                        "nif": fila.get("nif"),
                        "niss": niss,
                        "email": email,
                        "telefono": telefono,
                        "fecha_nacimiento": fila.get("fecha_nacimiento"),
                        "sexo": fila.get("sexo"),
                        "empresa_id": empresa_id,
                        "grupo_id": grupo_id,
                        "created_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat()
                    }

                    # Guardar en BD
                    participantes_service.crear_participante(datos)

                except Exception as ex:
                    errores.append(f"Fila {idx+1}: {ex}")

            if errores:
                st.error("⚠️ Errores detectados durante la importación:")
                for e in errores:
                    st.text(e)
            else:
                st.success("✅ Importación completada sin errores")
                st.rerun()

    except Exception as e:
        st.error(f"❌ Error importando participantes: {e}")
        
# =========================
# MAIN PARTICIPANTES
# =========================
def main(supabase, session_state):
    st.title("👥 Gestión de Participantes")

    participantes_service = get_participantes_service(supabase, session_state)
    empresas_service = get_empresas_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)

    # Tabs principales (simplificado)
    tabs = st.tabs(["📋 Listado", "➕ Crear", "📊 Métricas"])

    # =========================
    # TAB LISTADO
    # =========================
    with tabs[0]:
    st.header("📋 Listado de Participantes")
    try:
        df_participantes = participantes_service.get_participantes_completos()

        # 🔒 Filtrado por rol gestor
        if session_state.role == "gestor":
            empresas_df = cargar_empresas_disponibles(empresas_service, session_state)
            empresas_ids = empresas_df["id"].tolist()
            df_participantes = df_participantes[df_participantes["empresa_id"].isin(empresas_ids)]

        # Mostrar tabla (con filtros + paginación ya integrados)
        seleccionado, df_paged = mostrar_tabla_participantes(df_participantes, session_state)

        # Exportación, importación y ayuda
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            exportar_participantes(participantes_service, session_state, df_filtrado=df_paged, solo_visibles=True)
        with col2:
            importar_participantes(participantes_service, empresas_service, session_state)

        with st.expander("ℹ️ Ayuda sobre Participantes"):
            st.markdown("""
            - Usa los filtros para buscar rápidamente.
            - Haz clic en una fila para **editar un participante**.
            - Usa exportar/importar para gestión en bloque.
            - Los gestores solo verán sus empresas y grupos.
            """)

        if seleccionado is not None:
            mostrar_formulario_participante(
                seleccionado, participantes_service, empresas_service, grupos_service, session_state, es_creacion=False
            )
    except Exception as e:
        st.error(f"❌ Error cargando participantes: {e}")

    # =========================
    # TAB CREAR
    # =========================
    with tabs[1]:
        st.header("➕ Crear Nuevo Participante")
        mostrar_formulario_participante({}, participantes_service, empresas_service, grupos_service, session_state, es_creacion=True)

    # =========================
    # TAB MÉTRICAS
    # =========================
    with tabs[2]:
        st.header("📊 Métricas de Participantes")
        mostrar_metricas_participantes(participantes_service, session_state)

# =========================
# HELPERS DE ESTADO Y VALIDACIÓN
# =========================
def formatear_estado_participante(fila: dict) -> str:
    """Devuelve el estado de formación de un participante según fechas."""
    if not fila.get("grupo_fecha_inicio"):
        return "Sin grupo asignado"
    hoy = date.today()
    if fila.get("grupo_fecha_inicio") > hoy:
        return "Pendiente de inicio"
    if fila.get("grupo_fecha_fin_prevista") and fila.get("grupo_fecha_fin_prevista") < hoy:
        return "Curso finalizado"
    return "En curso"

def validar_niss(niss: str) -> bool:
    """Valida un número de NISS básico (solo dígitos y longitud >= 10)."""
    return bool(niss and niss.isdigit() and len(niss) >= 10)
