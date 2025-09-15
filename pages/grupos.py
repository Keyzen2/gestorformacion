import streamlit as st
import pandas as pd
from datetime import datetime
from utils import export_csv, validar_dni_cif, get_ajustes_app
from components.listado_con_ficha import listado_con_ficha
from services.grupos_service import get_grupos_service


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
        nombre_seccion="grupo"
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
from datetime import datetime
import pandas as pd
import streamlit as st

# =========================
# SECCIÓN FINALIZACIÓN
# =========================

def mostrar_seccion_finalizacion(supabase, session_state, grupos_service, grupo_id):
    try:
        grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute()
        if not grupo.data:
            return
        datos = grupo.data[0]
    except Exception:
        return

    if not grupos_service.fecha_pasada(datos.get("fecha_fin_prevista", "")):
        return

    with st.form("form_finalizacion"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            fecha_fin = st.date_input(
                "Fecha Fin Real *",
                value=datetime.fromisoformat(datos["fecha_fin"]).date() if datos.get("fecha_fin") else None
            )
        with col2:
            n_finalizados = st.number_input("Finalizados *", min_value=0, value=int(datos.get("n_participantes_finalizados") or 0))
        with col3:
            n_aptos = st.number_input("Aptos *", min_value=0, value=int(datos.get("n_aptos") or 0))
        with col4:
            n_no_aptos = st.number_input("No Aptos *", min_value=0, value=int(datos.get("n_no_aptos") or 0))

        if n_aptos + n_no_aptos != n_finalizados:
            st.error("⚠️ La suma de Aptos y No Aptos debe coincidir con Finalizados")

        if st.form_submit_button("💾 Guardar Finalización", use_container_width=True):
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
# SECCIÓN TUTORES / CENTRO GESTOR
# =========================

def mostrar_seccion_tutores_centro(supabase, session_state, grupos_service, grupo_id):
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
        st.dataframe(pd.DataFrame(tutores_display)[["nombre", "email", "especialidad"]],
                     use_container_width=True, hide_index=True)

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
            st.info("ℹ️ No hay tutores disponibles.")

    st.subheader("🏢 Centro Gestor")
    centro_actual = grupos_service.get_centro_gestor_grupo(grupo_id)
    if centro_actual and centro_actual.get("centro"):
        st.success(f"✅ Centro asignado: {centro_actual['centro'].get('razon_social', '')}")
        if st.button("🗑️ Desasignar Centro", type="secondary"):
            if grupos_service.unassign_centro_gestor_de_grupo(grupo_id):
                st.success("Centro desasignado.")
                st.rerun()
    else:
        st.info("ℹ️ No hay centro asignado.")
    # Nota: aquí podrías añadir la lógica de crear/asignar centro nuevo como en la versión previa


# =========================
# SECCIÓN EMPRESAS
# =========================

def mostrar_seccion_empresas(supabase, session_state, grupos_service, grupo_id, empresas_dict):
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
        st.dataframe(pd.DataFrame(empresas_display)[["nombre", "cif", "fecha_asignacion"]],
                     use_container_width=True, hide_index=True)

        if session_state.role == "admin":
            with st.expander("🗑️ Quitar Empresas"):
                seleccionadas = st.multiselect("Selecciona empresas:", [e["nombre"] for e in empresas_display])
                if seleccionadas and st.button("Confirmar Eliminación", type="secondary"):
                    for sel in seleccionadas:
                        for empresa in empresas_display:
                            if empresa["nombre"] == sel:
                                grupos_service.delete_empresa_grupo(empresa["id"])
                    st.success("✅ Empresas eliminadas.")
                    st.rerun()
    else:
        st.info("ℹ️ No hay empresas asignadas.")

    if session_state.role == "admin" and empresas_dict:
        with st.expander("➕ Añadir Empresas"):
            disponibles = {n: i for n, i in empresas_dict.items()
                           if n not in [e.get("empresa", {}).get("nombre", "") for _, e in df_empresas.iterrows()]}
            seleccionadas = st.multiselect("Seleccionar empresas:", disponibles.keys())
            if seleccionadas and st.button("Asignar Empresas", type="primary"):
                for nombre in seleccionadas:
                    grupos_service.create_empresa_grupo(grupo_id, disponibles[nombre])
                st.success("✅ Empresas asignadas.")
                st.rerun()


# =========================
# SECCIÓN PARTICIPANTES
# =========================

def mostrar_seccion_participantes(supabase, session_state, grupos_service, grupo_id):
    df_part = grupos_service.get_participantes_grupo(grupo_id)
    if not df_part.empty:
        st.dataframe(df_part[["nif", "nombre", "apellidos", "email", "telefono"]],
                     use_container_width=True, hide_index=True)
        with st.expander("🗑️ Desasignar"):
            seleccionados = st.multiselect("Selecciona:", [f"{r['nif']} - {r['nombre']} {r['apellidos']}" for _, r in df_part.iterrows()])
            if seleccionados and st.button("Confirmar", type="secondary"):
                for s in seleccionados:
                    nif = s.split(" - ")[0]
                    row = df_part[df_part["nif"] == nif]
                    if not row.empty:
                        grupos_service.desasignar_participante_de_grupo(row.iloc[0].get("id") or "")
                st.success("✅ Participantes desasignados.")
                st.rerun()
    else:
        st.info("ℹ️ No hay participantes.")

    with st.expander("➕ Asignar Participantes"):
        df_disp = grupos_service.get_participantes_disponibles(grupo_id)
        if not df_disp.empty:
            opciones = {f"{r['nif']} - {r['nombre']} {r['apellidos']}": r["id"] for _, r in df_disp.iterrows()}
            seleccion = st.multiselect("Selecciona:", opciones.keys())
            if seleccion and st.button("Asignar", type="primary"):
                for s in seleccion:
                    grupos_service.asignar_participante_a_grupo(opciones[s], grupo_id)
                st.success("✅ Participantes asignados.")
                st.rerun()
        else:
            st.info("ℹ️ No hay participantes disponibles.")

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
