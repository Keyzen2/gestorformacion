import streamlit as st
import pandas as pd
from datetime import datetime, time
from utils import export_csv, validar_dni_cif, get_ajustes_app
from components.listado_con_ficha import listado_con_ficha
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
    # CARGAR DATOS
    # =========================
    try:
        df_grupos = grupos_service.get_grupos_completos()
        acciones_dict = grupos_service.get_acciones_dict()
        empresas_dict = grupos_service.get_empresas_dict() if session_state.role == "admin" else {}
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # =========================
    # LISTADO CON FICHA
    # =========================
    st.markdown("### 📊 Grupos Formativos")

    campos_obligatorios = [
        "codigo_grupo", "accion_formativa_id", "modalidad",
        "localidad", "fecha_inicio", "fecha_fin_prevista",
        "n_participantes_previstos"
    ]

    campos_help = {
        "codigo_grupo": "Código único identificativo (máx. 50 caracteres)",
        "accion_formativa_id": "Selecciona la acción formativa",
        "modalidad": "PRESENCIAL / TELEFORMACION / MIXTA",
        "localidad": "Localidad de impartición (obligatoria FUNDAE)",
        "provincia": "Opcional",
        "cp": "Código postal",
        "fecha_inicio": "Fecha de inicio",
        "fecha_fin_prevista": "Fecha fin planificada",
        "n_participantes_previstos": "Entre 1 y 30",
        "observaciones": "Información adicional"
    }

    campos_select = {
        "accion_formativa_id": {nombre: id_accion for nombre, id_accion in acciones_dict.items()},
        "modalidad": {
            "PRESENCIAL": "PRESENCIAL",
            "TELEFORMACION": "TELEFORMACION",
            "MIXTA": "MIXTA"
        }
    }

    if session_state.role == "admin":
        campos_select["empresa_id"] = empresas_dict

    def on_create(data):
        data["updated_at"] = datetime.utcnow().isoformat()
        if session_state.role == "gestor":
            data["empresa_id"] = session_state.user.get("empresa_id")
        return grupos_service.create_grupo_completo(data)

    def on_save(grupo_id, data):
        data["updated_at"] = datetime.utcnow().isoformat()
        return grupos_service.update_grupo(grupo_id, data)

    def on_delete(grupo_id):
        return grupos_service.delete_grupo(grupo_id)

    grupo_id = listado_con_ficha(
        df=df_grupos,
        campos_obligatorios=campos_obligatorios,
        campos_select=campos_select,
        campos_help=campos_help,
        on_create=on_create,
        on_save=on_save,
        on_delete=on_delete,
    )

    # =========================
    # SECCIONES ADICIONALES
    # =========================
    if grupo_id:
        st.divider()
        st.header("🏁 Finalización del Grupo")
        mostrar_seccion_finalizacion(supabase, session_state, grupos_service, grupo_id)

        st.divider()
        st.header("👨‍🏫 Tutores y Centro Gestor")
        mostrar_seccion_tutores_centro(supabase, session_state, grupos_service, grupo_id)

        st.divider()
        st.header("🏢 Empresas Participantes")
        mostrar_seccion_empresas(supabase, session_state, grupos_service, grupo_id, empresas_dict)

        st.divider()
        st.header("👥 Participantes del Grupo")
        mostrar_seccion_participantes(supabase, session_state, grupos_service, grupo_id)

        st.divider()
        st.header("💰 Costes FUNDAE")
        mostrar_seccion_costes_fundae(supabase, session_state, grupos_service, grupo_id)
# =========================
# SECCIÓN FINALIZACIÓN
# =========================

def mostrar_seccion_finalizacion(supabase, session_state, grupos_service, grupo_id):
    """Sección para completar datos de finalización de un grupo (cuando la fecha prevista ya pasó)."""
    try:
        grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute()
        if not grupo.data:
            return
        datos = grupo.data[0]
    except Exception as e:
        st.error(f"❌ Error al cargar grupo: {e}")
        return

    # Solo mostrar si la fecha prevista ya pasó
    if not grupos_service.fecha_pasada(datos.get("fecha_fin_prevista", "")):
        return

    st.info("ℹ️ Este grupo ha superado su fecha prevista. Complete los datos de finalización para FUNDAE.")

    with st.form("form_finalizacion"):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            fecha_fin = st.date_input(
                "Fecha Fin Real *",
                value=datetime.fromisoformat(datos["fecha_fin"]).date() if datos.get("fecha_fin") else None
            )
        with col2:
            n_finalizados = st.number_input(
                "Finalizados *",
                min_value=0,
                value=int(datos.get("n_participantes_finalizados") or 0)
            )
        with col3:
            n_aptos = st.number_input(
                "Aptos *",
                min_value=0,
                value=int(datos.get("n_aptos") or 0)
            )
        with col4:
            n_no_aptos = st.number_input(
                "No Aptos *",
                min_value=0,
                value=int(datos.get("n_no_aptos") or 0)
            )

        # Validación en tiempo real
        if n_aptos + n_no_aptos != n_finalizados:
            st.error("⚠️ La suma de Aptos y No Aptos debe coincidir con Finalizados")

        submitted = st.form_submit_button("💾 Guardar Finalización", use_container_width=True)

        if submitted:
            errores = []
            if not fecha_fin:
                errores.append("La fecha fin real es obligatoria")
            if n_aptos + n_no_aptos != n_finalizados:
                errores.append("La suma de aptos y no aptos debe coincidir con finalizados")

            if errores:
                for err in errores:
                    st.error(f"❌ {err}")
                return

            datos_update = {
                "fecha_fin": fecha_fin.isoformat(),
                "n_participantes_finalizados": n_finalizados,
                "n_aptos": n_aptos,
                "n_no_aptos": n_no_aptos,
                "updated_at": datetime.utcnow().isoformat()
            }

            # Validación FUNDAE
            es_valido, errores_fundae = grupos_service.validar_grupo_fundae(datos_update, "finalizacion")
            if not es_valido:
                st.error("❌ Errores de validación FUNDAE:")
                for error in errores_fundae:
                    st.error(f"• {error}")
                return

            try:
                if grupos_service.update_grupo(grupo_id, datos_update):
                    st.success("✅ Finalización guardada correctamente.")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar finalización: {e}")
# =========================
# SECCIÓN TUTORES / CENTRO GESTOR
# =========================

def mostrar_seccion_tutores_centro(supabase, session_state, grupos_service, grupo_id):
    # === TUTORES ===
    st.subheader("👨‍🏫 Tutores Asignados")

    df_tutores = grupos_service.get_tutores_grupo(grupo_id)

    if not df_tutores.empty:
        tutores_display = []
        for _, row in df_tutores.iterrows():
            tutor = row.get("tutor", {}) or {}
            tutores_display.append({
                "id": row.get("id") or "",
                "nombre": f"{tutor.get('nombre', '')} {tutor.get('apellidos', '')}".strip(),
                "email": tutor.get("email", ""),
                "especialidad": tutor.get("especialidad", "")
            })

        st.dataframe(
            pd.DataFrame(tutores_display)[["nombre", "email", "especialidad"]],
            use_container_width=True, hide_index=True
        )

        with st.expander("🗑️ Quitar Tutores"):
            seleccionados = st.multiselect("Selecciona tutores:", [t["nombre"] for t in tutores_display])
            if seleccionados and st.button("Confirmar Eliminación", type="secondary"):
                for sel in seleccionados:
                    for tutor in tutores_display:
                        if tutor["nombre"] == sel:
                            grupos_service.delete_tutor_grupo(tutor["id"])
                st.success("✅ Tutores eliminados.")
                st.rerun()
    else:
        st.info("ℹ️ No hay tutores asignados.")

    with st.expander("➕ Añadir Tutores"):
        df_disp = grupos_service.get_tutores_completos()
        if not df_disp.empty:
            asignados_ids = { (row.get("tutor") or {}).get("id") for _, row in df_tutores.iterrows() }
            df_disp = df_disp[~df_disp["id"].isin(asignados_ids)]
            if not df_disp.empty:
                opciones = {row["nombre_completo"]: row["id"] for _, row in df_disp.iterrows()}
                seleccion = st.multiselect("Seleccionar tutores:", opciones.keys())
                if seleccion and st.button("Asignar", type="primary"):
                    for nombre in seleccion:
                        grupos_service.create_tutor_grupo(grupo_id, opciones[nombre])
                    st.success("✅ Tutores asignados.")
                    st.rerun()
            else:
                st.info("ℹ️ Todos los tutores disponibles ya están asignados.")
        else:
            st.info("ℹ️ No hay tutores disponibles en el sistema.")

    st.divider()
    # === CENTRO GESTOR ===
    st.subheader("🏢 Centro Gestor")

    try:
        grupo_info = supabase.table("grupos").select("modalidad").eq("id", grupo_id).execute()
        modalidad = grupo_info.data[0]["modalidad"] if grupo_info.data else "PRESENCIAL"
        centro_obligatorio = modalidad in ["TELEFORMACION", "MIXTA"]

        if centro_obligatorio:
            st.warning("⚠️ Centro Gestor obligatorio para modalidad TELEFORMACION/MIXTA")
        else:
            st.info("ℹ️ Centro Gestor opcional para modalidad PRESENCIAL")
    except Exception as e:
        st.error(f"❌ Error al verificar modalidad: {e}")
        return

    centro_actual = grupos_service.get_centro_gestor_grupo(grupo_id)
    if centro_actual and centro_actual.get("centro"):
        centro = centro_actual["centro"]
        st.success(f"✅ Centro asignado: {centro.get('razon_social', '')}")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**CIF:** {centro.get('cif', '')}")
            st.write(f"**Teléfono:** {centro.get('telefono', '')}")
            st.write(f"**Localidad:** {centro.get('localidad', '')}")
        with col2:
            st.write(f"**Domicilio:** {centro.get('domicilio', '')}")
            st.write(f"**CP:** {centro.get('codigo_postal', '')}")

        if st.button("🗑️ Desasignar Centro", type="secondary"):
            if grupos_service.unassign_centro_gestor_de_grupo(grupo_id):
                st.success("✅ Centro desasignado correctamente.")
                st.rerun()
    else:
        st.info("ℹ️ No hay centro gestor asignado.")

    with st.expander("🏢 Gestionar Centro Gestor"):
        tab1, tab2 = st.tabs(["📋 Asignar Existente", "➕ Crear y Asignar"])

        with tab1:
            df_centros = grupos_service.get_centros_para_grupo(grupo_id)
            if not df_centros.empty:
                opciones = {f"{r['razon_social']} - {r['localidad']}": r['id'] for _, r in df_centros.iterrows()}
                sel = st.selectbox("Seleccionar centro:", [""] + list(opciones.keys()))
                if sel and st.button("Asignar Centro", type="primary"):
                    if grupos_service.assign_centro_gestor_a_grupo(grupo_id, opciones[sel]):
                        st.success("✅ Centro asignado correctamente.")
                        st.rerun()
            else:
                st.info("ℹ️ No hay centros disponibles. Crea uno nuevo en la pestaña siguiente.")

        with tab2:
            with st.form("crear_centro_gestor"):
                st.markdown("**Crear Nuevo Centro Gestor**")
                col1, col2 = st.columns(2)
                with col1:
                    cif = st.text_input("CIF", help="Opcional")
                    razon = st.text_input("Razón Social *")
                    nombre_comercial = st.text_input("Nombre Comercial", help="Opcional")
                    telefono = st.text_input("Teléfono *")
                with col2:
                    domicilio = st.text_input("Domicilio *")
                    localidad = st.text_input("Localidad *")
                    cp = st.text_input("Código Postal *", help="5 dígitos o 99999 para extranjero")

                crear = st.form_submit_button("Crear y Asignar Centro", use_container_width=True)

                if crear:
                    errores = []
                    if not razon: errores.append("Razón Social obligatoria")
                    if not telefono: errores.append("Teléfono obligatorio")
                    if not domicilio: errores.append("Domicilio obligatorio")
                    if not localidad: errores.append("Localidad obligatoria")
                    if not cp: errores.append("Código Postal obligatorio")
                    elif not (cp.isdigit() and len(cp) == 5) and cp != "99999":
                        errores.append("Código Postal debe tener 5 dígitos o ser 99999")

                    if errores:
                        for e in errores:
                            st.error(f"⚠️ {e}")
                        return

                    if session_state.role == "gestor":
                        empresa_id = session_state.user.get("empresa_id")
                    else:
                        grupo_info = supabase.table("grupos").select("empresa_id").eq("id", grupo_id).execute()
                        empresa_id = grupo_info.data[0]["empresa_id"] if grupo_info.data else None

                    if not empresa_id:
                        st.error("❌ No se pudo determinar la empresa para el centro.")
                        return

                    datos_centro = {
                        "cif": cif or None,
                        "razon_social": razon,
                        "nombre_comercial": nombre_comercial or None,
                        "telefono": telefono,
                        "domicilio": domicilio,
                        "localidad": localidad,
                        "codigo_postal": cp
                    }

                    ok, centro_id = grupos_service.create_centro_gestor(empresa_id, datos_centro)
                    if ok and grupos_service.assign_centro_gestor_a_grupo(grupo_id, centro_id):
                        st.success("✅ Centro creado y asignado correctamente.")
                        st.rerun()
                    elif ok:
                        st.error("❌ Centro creado pero no se pudo asignar al grupo.")
                    else:
                        st.error("❌ Error al crear centro.")
# =========================
# SECCIÓN EMPRESAS
# =========================

def mostrar_seccion_empresas(supabase, session_state, grupos_service, grupo_id, empresas_dict):
    st.subheader("🏢 Empresas Participantes")

    if session_state.role == "gestor":
        st.info("ℹ️ Como gestor, tu empresa está vinculada automáticamente al grupo.")

    df_empresas = grupos_service.get_empresas_grupo(grupo_id)

    if not df_empresas.empty:
        empresas_display = []
        for _, row in df_empresas.iterrows():
            emp = row.get("empresa", {}) or {}
            empresas_display.append({
                "id": row.get("id") or "",
                "nombre": emp.get("nombre", ""),
                "cif": emp.get("cif", ""),
                "fecha_asignacion": row.get("fecha_asignacion", "")
            })

        st.dataframe(
            pd.DataFrame(empresas_display)[["nombre", "cif", "fecha_asignacion"]],
            use_container_width=True, hide_index=True
        )

        if session_state.role == "admin":
            with st.expander("🗑️ Quitar Empresas"):
                seleccionadas = st.multiselect(
                    "Selecciona empresas:",
                    [e["nombre"] for e in empresas_display]
                )
                if seleccionadas and st.button("Confirmar Eliminación", type="secondary"):
                    for sel in seleccionadas:
                        for empresa in empresas_display:
                            if empresa["nombre"] == sel:
                                grupos_service.delete_empresa_grupo(empresa["id"])
                    st.success("✅ Empresas eliminadas.")
                    st.rerun()
    else:
        st.info("ℹ️ No hay empresas asignadas a este grupo.")

    # Solo admin puede añadir empresas
    if session_state.role == "admin" and empresas_dict:
        with st.expander("➕ Añadir Empresas"):
            # Filtrar empresas ya asignadas
            asignadas = {
                (row.get("empresa") or {}).get("nombre", "")
                for _, row in df_empresas.iterrows()
            }
            disponibles = {
                nombre: id_emp for nombre, id_emp in empresas_dict.items()
                if nombre not in asignadas
            }

            if disponibles:
                seleccionadas = st.multiselect(
                    "Seleccionar empresas:",
                    list(disponibles.keys()),
                    help="Empresas cuyos trabajadores participarán en el grupo"
                )
                if seleccionadas and st.button("Asignar Empresas", type="primary"):
                    for nombre in seleccionadas:
                        grupos_service.create_empresa_grupo(grupo_id, disponibles[nombre])
                    st.success(f"✅ Se han asignado {len(seleccionadas)} empresas.")
                    st.rerun()
            else:
                st.info("ℹ️ Todas las empresas disponibles ya están asignadas.")
# =========================
# SECCIÓN PARTICIPANTES
# =========================

def mostrar_seccion_participantes(supabase, session_state, grupos_service, grupo_id):
    st.subheader("👥 Participantes del Grupo")

    # ---- PARTICIPANTES ACTUALES ----
    df_part = grupos_service.get_participantes_grupo(grupo_id)

    if not df_part.empty:
        st.markdown("### 👤 Participantes Asignados")

        columnas_mostrar = ["nif", "nombre", "apellidos", "email", "telefono"]
        columnas_existentes = [c for c in columnas_mostrar if c in df_part.columns]

        st.dataframe(
            df_part[columnas_existentes],
            use_container_width=True,
            hide_index=True
        )

        with st.expander("🗑️ Desasignar Participantes"):
            seleccionados = st.multiselect(
                "Selecciona participantes:",
                [f"{r['nif']} - {r['nombre']} {r['apellidos']}" for _, r in df_part.iterrows()]
            )
            if seleccionados and st.button("Confirmar Desasignación", type="secondary"):
                for s in seleccionados:
                    nif = s.split(" - ")[0]
                    row = df_part[df_part["nif"] == nif]
                    if not row.empty:
                        grupos_service.desasignar_participante_de_grupo(row.iloc[0].get("id") or "")
                st.success("✅ Participantes desasignados.")
                st.rerun()
    else:
        st.info("ℹ️ No hay participantes asignados a este grupo.")

    # ---- ASIGNACIÓN NUEVA ----
    st.markdown("### ➕ Asignar Participantes")

    tab1, tab2 = st.tabs(["📋 Selección Individual", "📊 Importación Masiva"])

    with tab1:
        df_disp = grupos_service.get_participantes_disponibles(grupo_id)
        if not df_disp.empty:
            opciones = {
                f"{r['nif']} - {r['nombre']} {r['apellidos']}": r["id"]
                for _, r in df_disp.iterrows()
            }
            seleccion = st.multiselect("Selecciona participantes:", opciones.keys())
            if seleccion and st.button("Asignar Seleccionados", type="primary"):
                for s in seleccion:
                    grupos_service.asignar_participante_a_grupo(opciones[s], grupo_id)
                st.success(f"✅ Se han asignado {len(seleccion)} participantes.")
                st.rerun()
        else:
            st.info("ℹ️ No hay participantes disponibles.")

    with tab2:
        st.markdown("**Instrucciones:**")
        st.markdown("1. Sube un archivo Excel (.xlsx) con una columna llamada 'dni' o 'nif'.")
        st.markdown("2. El sistema buscará automáticamente los participantes por NIF.")
        st.markdown("3. Solo se asignarán los que existan en el sistema y estén disponibles.")

        uploaded = st.file_uploader("Subir archivo Excel", type=["xlsx"], key=f"excel_participantes_{grupo_id}")

        if uploaded:
            try:
                df_import = pd.read_excel(uploaded)

                # Detectar columna de NIF
                col_nif = None
                for c in ["dni", "nif", "DNI", "NIF"]:
                    if c in df_import.columns:
                        col_nif = c
                        break

                if not col_nif:
                    st.error("⚠️ El archivo debe contener una columna llamada 'dni' o 'nif'.")
                else:
                    st.dataframe(df_import.head(), use_container_width=True)

                    if st.button("🚀 Procesar Archivo", type="primary"):
                        nifs = [str(d).strip() for d in df_import[col_nif] if pd.notna(d)]
                        nifs_validos = [d for d in nifs if validar_dni_cif(d)]
                        nifs_invalidos = set(nifs) - set(nifs_validos)

                        if nifs_invalidos:
                            st.warning(f"⚠️ NIFs inválidos detectados: {', '.join(list(nifs_invalidos)[:5])}")

                        df_disp_masivo = grupos_service.get_participantes_disponibles(grupo_id)
                        disponibles = {p["nif"]: p["id"] for _, p in df_disp_masivo.iterrows()}

                        asignados, errores = 0, []
                        for nif in nifs_validos:
                            part_id = disponibles.get(nif)
                            if not part_id:
                                errores.append(f"NIF {nif} no encontrado o ya asignado")
                                continue
                            try:
                                grupos_service.asignar_participante_a_grupo(part_id, grupo_id)
                                asignados += 1
                            except Exception as e:
                                errores.append(f"NIF {nif} - Error: {str(e)}")

                        if asignados > 0:
                            st.success(f"✅ Se han asignado {asignados} participantes.")
                        if errores:
                            st.warning("⚠️ Errores encontrados:")
                            for e in errores[:10]:
                                st.warning(f"• {e}")
                        if asignados > 0:
                            st.rerun()

            except Exception as e:
                st.error(f"❌ Error al procesar archivo: {e}")
# =========================
# SECCIÓN COSTES FUNDAE
# =========================

def mostrar_seccion_costes_fundae(supabase, session_state, grupos_service, grupo_id):
    st.subheader("💰 Costes FUNDAE")

    # --- Datos base del grupo ---
    try:
        grupo_info = supabase.table("grupos").select("""
            modalidad, n_participantes_previstos,
            accion_formativa:acciones_formativas(num_horas)
        """).eq("id", grupo_id).execute()

        if not grupo_info.data:
            st.error("❌ No se pudo cargar información del grupo.")
            return

        datos = grupo_info.data[0]
        modalidad = datos.get("modalidad", "PRESENCIAL")
        participantes = int(datos.get("n_participantes_previstos") or 0)
        horas = int((datos.get("accion_formativa") or {}).get("num_horas", 0))
    except Exception as e:
        st.error(f"❌ Error al cargar datos del grupo: {e}")
        return

    # --- Límite FUNDAE ---
    limite_boni, tarifa_max = grupos_service.calcular_limite_fundae(modalidad, horas, participantes)

    with st.expander("ℹ️ Datos de Cálculo FUNDAE", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Modalidad", modalidad)
        col2.metric("Participantes", participantes)
        col3.metric("Horas", horas)
        col4.metric("Límite Bonificación", f"{limite_boni:,.2f} €")

    # --- Costes actuales ---
    costes_actuales = grupos_service.get_grupo_costes(grupo_id)

    with st.form("form_costes_fundae"):
        col1, col2 = st.columns(2)
        with col1:
            costes_directos = st.number_input(
                "Costes Directos (€)",
                value=float(costes_actuales.get("costes_directos") or 0),
                min_value=0.0
            )
            costes_indirectos = st.number_input(
                "Costes Indirectos (€)",
                value=float(costes_actuales.get("costes_indirectos") or 0),
                min_value=0.0,
                help="Máx. 30% de directos según FUNDAE"
            )
            costes_organizacion = st.number_input(
                "Costes Organización (€)",
                value=float(costes_actuales.get("costes_organizacion") or 0),
                min_value=0.0
            )
        with col2:
            costes_salariales = st.number_input(
                "Costes Salariales (€)",
                value=float(costes_actuales.get("costes_salariales") or 0),
                min_value=0.0
            )
            cofinanciacion_privada = st.number_input(
                "Cofinanciación Privada (€)",
                value=float(costes_actuales.get("cofinanciacion_privada") or 0),
                min_value=0.0
            )
            tarifa_hora = st.number_input(
                "Tarifa por Hora (€)",
                value=float(costes_actuales.get("tarifa_hora") or tarifa_max),
                min_value=0.0,
                max_value=tarifa_max,
                help=f"Máximo permitido: {tarifa_max} €/h para {modalidad}"
            )

        total_costes = costes_directos + costes_indirectos + costes_organizacion + costes_salariales
        limite_calculado = tarifa_hora * horas * participantes

        col1, col2 = st.columns(2)
        col1.metric("💰 Total Costes", f"{total_costes:,.2f} €")
        col2.metric("🎯 Límite Calculado", f"{limite_calculado:,.2f} €")

        # Validaciones
        valid_ok = True
        if costes_directos > 0:
            pct_indirectos = (costes_indirectos / costes_directos) * 100
            if pct_indirectos > 30:
                st.error(f"⚠️ Indirectos {pct_indirectos:.1f}% > 30% permitido")
                valid_ok = False
            else:
                st.success(f"✅ Indirectos dentro del límite ({pct_indirectos:.1f}%)")
        if tarifa_hora > tarifa_max:
            st.error("⚠️ Tarifa/hora supera el máximo permitido")
            valid_ok = False

        observaciones = st.text_area("Observaciones", value=costes_actuales.get("observaciones") or "")

        guardar = st.form_submit_button("💾 Guardar Costes", use_container_width=True)
        if guardar and valid_ok:
            datos_costes = {
                "grupo_id": grupo_id,
                "costes_directos": costes_directos,
                "costes_indirectos": costes_indirectos,
                "costes_organizacion": costes_organizacion,
                "costes_salariales": costes_salariales,
                "cofinanciacion_privada": cofinanciacion_privada,
                "tarifa_hora": tarifa_hora,
                "modalidad": modalidad,
                "total_costes_formacion": total_costes,
                "limite_maximo_bonificacion": limite_calculado,
                "observaciones": observaciones,
                "updated_at": datetime.utcnow().isoformat()
            }
            if costes_actuales:
                ok = grupos_service.update_grupo_coste(grupo_id, datos_costes)
            else:
                datos_costes["created_at"] = datetime.utcnow().isoformat()
                ok = grupos_service.create_grupo_coste(datos_costes)
            if ok:
                st.success("✅ Costes guardados correctamente.")
                st.rerun()
            else:
                st.error("❌ Error al guardar costes.")

    # --- Bonificaciones ---
    st.divider()
    st.markdown("### 📅 Bonificaciones Mensuales")

    df_boni = grupos_service.get_grupo_bonificaciones(grupo_id)
    if not df_boni.empty:
        st.dataframe(df_boni[["mes", "importe", "observaciones"]], use_container_width=True, hide_index=True)
        total_boni = float(df_boni["importe"].sum())
        disponible = limite_calculado - total_boni
        col1, col2 = st.columns(2)
        col1.metric("Total Bonificado", f"{total_boni:,.2f} €")
        col2.metric("Disponible", f"{disponible:,.2f} €")
    else:
        st.info("ℹ️ No hay bonificaciones registradas.")
        total_boni, disponible = 0, limite_calculado

    with st.expander("➕ Añadir Bonificación"):
        with st.form("form_bonificacion"):
            col1, col2 = st.columns(2)
            with col1:
                mes = st.selectbox("Mes", [
                    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
                ])
                importe = st.number_input("Importe (€)", min_value=0.0, max_value=disponible)
            with col2:
                obs = st.text_area("Observaciones")

            crear = st.form_submit_button("💰 Añadir Bonificación")
            if crear:
                if importe <= 0:
                    st.error("⚠️ El importe debe ser mayor que 0")
                elif total_boni + importe > limite_calculado:
                    st.error("⚠️ Se supera el límite de bonificación")
                else:
                    datos_boni = {
                        "grupo_id": grupo_id,
                        "mes": mes,
                        "importe": importe,
                        "observaciones": obs,
                        "created_at": datetime.utcnow().isoformat()
                    }
                    if grupos_service.create_grupo_bonificacion(datos_boni):
                        st.success("✅ Bonificación añadida.")
                        st.rerun()

    with st.expander("ℹ️ Información FUNDAE"):
        st.markdown("""
        **Tarifas máximas:**
        - PRESENCIAL/MIXTA → 13 €/hora
        - TELEFORMACION → 7.5 €/hora  

        **Costes Indirectos:**  
        - Máx. 30% de los costes directos  

        **Límite Bonificación:**  
        - Tarifa/hora × Horas × Participantes  
        - Nunca superar el total de costes de formación  
        """)
