import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta, time
from services.grupos_service import get_grupos_service
from utils import validar_dni_cif, export_csv
import math
import re

# =========================
# CONFIGURACIÓN Y CONSTANTES
# =========================

MODALIDADES_FUNDAE = {
    "PRESENCIAL": "PRESENCIAL",
    "TELEFORMACION": "TELEFORMACION",
    "MIXTA": "MIXTA"
}

DIAS_SEMANA = ["L", "M", "X", "J", "V", "S", "D"]
NOMBRES_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# =========================
# HELPERS GENERALES
# =========================

def safe_int_conversion(value, default=0):
    if value is None or pd.isna(value):
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

def safe_date_conversion(date_value):
    if not date_value:
        return None
    if isinstance(date_value, str):
        try:
            return datetime.fromisoformat(date_value.replace('Z', '+00:00')).date()
        except:
            return None
    elif hasattr(date_value, 'date'):
        return date_value.date() if callable(getattr(date_value, 'date', None)) else date_value
    return date_value

# =========================
# ESTADO DEL GRUPO
# =========================

def determinar_estado_grupo(grupo_data):
    if not grupo_data:
        return "ABIERTO"

    fecha_fin_prevista = grupo_data.get("fecha_fin_prevista")
    fecha_fin_real = grupo_data.get("fecha_fin")
    n_finalizados = grupo_data.get("n_participantes_finalizados")
    n_aptos = grupo_data.get("n_aptos")
    n_no_aptos = grupo_data.get("n_no_aptos")

    if all([fecha_fin_real, n_finalizados is not None, n_aptos is not None, n_no_aptos is not None]):
        return "FINALIZADO"

    if fecha_fin_prevista:
        try:
            fecha_fin_dt = datetime.fromisoformat(str(fecha_fin_prevista).replace('Z', '+00:00'))
            if fecha_fin_dt.date() <= date.today():
                return "FINALIZAR"
        except:
            pass

    return "ABIERTO"

def get_grupos_pendientes_finalizacion(df_grupos):
    if df_grupos.empty:
        return []
    pendientes = []
    for _, grupo in df_grupos.iterrows():
        if determinar_estado_grupo(grupo.to_dict()) == "FINALIZAR":
            pendientes.append(grupo.to_dict())
    return pendientes

# =========================
# VALIDACIONES FUNDAE
# =========================

def validar_horario_fundae(horario_str):
    if not horario_str:
        return False, "Horario requerido"
    if "Días:" not in horario_str:
        return False, "Debe especificar días de la semana"
    if not any(x in horario_str for x in ["Mañana:", "Tarde:"]):
        return False, "Debe especificar al menos un tramo horario"
    return True, ""

def validar_campos_obligatorios_fundae(datos):
    errores = []
    campos_requeridos = {
        "fecha_inicio": "Fecha de inicio",
        "fecha_fin_prevista": "Fecha fin prevista",
        "localidad": "Localidad",
        "n_participantes_previstos": "Participantes previstos"
    }
    for campo, nombre in campos_requeridos.items():
        if not datos.get(campo):
            errores.append(f"{nombre} es obligatorio para FUNDAE")

    modalidad = datos.get("modalidad")
    if modalidad and modalidad not in MODALIDADES_FUNDAE:
        errores.append("Modalidad debe ser PRESENCIAL, TELEFORMACION o MIXTA")

    try:
        n_part = int(datos.get("n_participantes_previstos", 0))
        if n_part < 1 or n_part > 30:
            errores.append("Participantes previstos debe estar entre 1 y 30")
    except:
        errores.append("Participantes previstos debe ser un número")

    horario = datos.get("horario")
    if horario:
        es_valido, error_horario = validar_horario_fundae(horario)
        if not es_valido:
            errores.append(f"Horario: {error_horario}")

    return errores

def validar_datos_finalizacion(datos):
    errores = []
    try:
        finalizados = int(datos.get("n_participantes_finalizados", 0))
        aptos = int(datos.get("n_aptos", 0))
        no_aptos = int(datos.get("n_no_aptos", 0))

        if finalizados <= 0:
            errores.append("Debe haber al menos 1 participante finalizado")
        if aptos + no_aptos != finalizados:
            errores.append("La suma de aptos + no aptos debe igualar finalizados")
        if aptos < 0 or no_aptos < 0:
            errores.append("Los números no pueden ser negativos")
    except ValueError:
        errores.append("Los campos numéricos deben ser números enteros")
    return errores

# =========================
# SELECTOR DE HORARIOS FUNDAE
# =========================

def crear_selector_horario_fundae(prefix=""):
    """Crea un selector de horario dinámico para FUNDAE."""
    tipo_horario = st.radio(
        "Tipo de jornada:",
        ["Solo Mañana", "Solo Tarde", "Mañana y Tarde"],
        horizontal=True,
        key=f"{prefix}_tipo_horario"
    )

    col_h1, col_h2 = st.columns(2)

    intervalos_manana = [f"{h:02d}:{m:02d}" for h in range(6, 15) for m in [0, 15, 30, 45]]
    intervalos_tarde = [f"{h:02d}:{m:02d}" for h in range(15, 24) for m in [0, 15, 30, 45] if not (h == 23 and m > 0)]

    manana_inicio = manana_fin = tarde_inicio = tarde_fin = None

    if tipo_horario in ["Solo Mañana", "Mañana y Tarde"]:
        with col_h1:
            manana_inicio = st.selectbox(
                "Inicio Mañana:",
                intervalos_manana[:-1],
                index=12,
                key=f"{prefix}_manana_inicio"
            )
            idx_inicio = intervalos_manana.index(manana_inicio)
            horas_fin_validas = intervalos_manana[idx_inicio + 1:]
            manana_fin = st.selectbox(
                "Fin Mañana:",
                horas_fin_validas,
                key=f"{prefix}_manana_fin"
            )

    if tipo_horario in ["Solo Tarde", "Mañana y Tarde"]:
        with col_h2:
            tarde_inicio = st.selectbox(
                "Inicio Tarde:",
                intervalos_tarde[:-1],
                index=0,
                key=f"{prefix}_tarde_inicio"
            )
            idx_inicio = intervalos_tarde.index(tarde_inicio)
            horas_fin_validas = intervalos_tarde[idx_inicio + 1:]
            tarde_fin = st.selectbox(
                "Fin Tarde:",
                horas_fin_validas,
                key=f"{prefix}_tarde_fin"
            )

    st.markdown("**Días de Impartición**")
    dias_cols = st.columns(7)
    dias_seleccionados = []
    for i, (dia_corto, dia_largo) in enumerate(zip(DIAS_SEMANA, NOMBRES_DIAS)):
        with dias_cols[i]:
            if st.checkbox(
                dia_largo,
                value=dia_corto in ["L", "M", "X", "J", "V"],
                key=f"{prefix}_dia_{dia_corto}"
            ):
                dias_seleccionados.append(dia_corto)

    horarios_partes = []
    if manana_inicio and manana_fin:
        horarios_partes.append(f"Mañana: {manana_inicio} - {manana_fin}")
    if tarde_inicio and tarde_fin:
        horarios_partes.append(f"Tarde: {tarde_inicio} - {tarde_fin}")
    if dias_seleccionados:
        horarios_partes.append(f"Días: {'-'.join(dias_seleccionados)}")

    horario_final = " | ".join(horarios_partes)
    if horario_final:
        st.success(f"Horario FUNDAE: {horario_final}")

    return horario_final
    
# =========================
# GESTIÓN DE TUTORES DEL GRUPO (N:N)
# =========================

def seccion_tutores_grupo(grupo_id, grupos_service, modo="editar"):
    """
    Sección completa de gestión de tutores para un grupo (N:N).
    - modo="crear": solo muestra selección, no inserta aún.
    - modo="editar": permite vincular/desvincular tutores.
    """
    st.markdown("### 👨‍🏫 Tutores del Grupo")

    try:
        # Cargar tutores vinculados
        df_tutores = grupos_service.get_tutores_grupo(grupo_id)
    except Exception as e:
        st.error(f"❌ Error al cargar tutores: {e}")
        df_tutores = pd.DataFrame()

    # Mostrar tutores asignados
    if not df_tutores.empty:
        st.write("**Tutores asignados:**")
        for _, row in df_tutores.iterrows():
            tutor = row.get("tutor", {})
            if tutor:
                nombre_completo = f"{tutor.get('nombre', '')} {tutor.get('apellidos', '')}".strip()
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"- {nombre_completo} ({tutor.get('especialidad', 'Sin especialidad')})")
                with col2:
                    if modo == "editar":
                        if st.button("❌ Quitar", key=f"quitar_tutor_{row['id']}"):
                            try:
                                grupos_service.desvincular_tutor_de_grupo(grupo_id, row["tutor_id"])
                                st.success("Tutor desvinculado correctamente")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al desvincular tutor: {e}")
    else:
        st.info("No hay tutores asignados a este grupo")

    # Selección para añadir tutor
    if modo == "editar":
        try:
            df_all_tutores = grupos_service.get_tutores()
            if not df_all_tutores.empty:
                opciones = {
                    f"{row['nombre']} {row.get('apellidos','')} - {row.get('especialidad','') or 'Sin especialidad'}": row["id"]
                    for _, row in df_all_tutores.iterrows()
                }
                tutor_sel = st.selectbox("➕ Asignar nuevo tutor", ["—"] + list(opciones.keys()), key=f"sel_tutor_{grupo_id}")
                if tutor_sel != "—":
                    tutor_id = opciones[tutor_sel]
                    if st.button("Asignar Tutor", key=f"btn_asignar_tutor_{grupo_id}"):
                        try:
                            grupos_service.vincular_tutor_a_grupo(grupo_id, tutor_id)
                            st.success("Tutor asignado correctamente")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al asignar tutor: {e}")
            else:
                st.info("No hay tutores disponibles en la base de datos")
        except Exception as e:
            st.error(f"Error al cargar listado de tutores: {e}")
            
# =========================
# GESTIÓN DE EMPRESAS DEL GRUPO (N:N)
# =========================

def seccion_empresas_grupo(grupo_id, grupos_service, modo="editar"):
    """
    Sección completa de gestión de empresas para un grupo (N:N).
    - modo="crear": solo muestra selección, no inserta aún.
    - modo="editar": permite vincular/desvincular empresas.
    """
    st.markdown("### 🏢 Empresas Participantes")

    try:
        # Cargar empresas vinculadas
        df_empresas = grupos_service.get_empresas_grupo(grupo_id)
    except Exception as e:
        st.error(f"❌ Error al cargar empresas: {e}")
        df_empresas = pd.DataFrame()

    # Mostrar empresas asignadas
    if not df_empresas.empty:
        st.write("**Empresas asignadas:**")
        for _, row in df_empresas.iterrows():
            empresa = row.get("empresa", {})
            if empresa:
                nombre = empresa.get("nombre", "—")
                cif = empresa.get("cif", "N/A")
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"- {nombre} (CIF: {cif})")
                with col2:
                    if modo == "editar":
                        if st.button("❌ Quitar", key=f"quitar_empresa_{row['id']}"):
                            try:
                                grupos_service.desvincular_empresa_de_grupo(grupo_id, row["empresa_id"])
                                st.success("Empresa desvinculada correctamente")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al desvincular empresa: {e}")
    else:
        st.info("No hay empresas asignadas a este grupo")

    # Selección para añadir empresa
    if modo == "editar":
        try:
            df_all_empresas = grupos_service.get_empresas()
            if not df_all_empresas.empty:
                opciones = {
                    f"{row['nombre']} - CIF: {row.get('cif','')}": row["id"]
                    for _, row in df_all_empresas.iterrows()
                }
                empresa_sel = st.selectbox("➕ Asignar nueva empresa", ["—"] + list(opciones.keys()), key=f"sel_empresa_{grupo_id}")
                if empresa_sel != "—":
                    empresa_id = opciones[empresa_sel]
                    if st.button("Asignar Empresa", key=f"btn_asignar_empresa_{grupo_id}"):
                        try:
                            grupos_service.vincular_empresa_a_grupo(grupo_id, empresa_id)
                            st.success("Empresa asignada correctamente")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al asignar empresa: {e}")
            else:
                st.info("No hay empresas disponibles en la base de datos")
        except Exception as e:
            st.error(f"Error al cargar listado de empresas: {e}")
# =========================
# GESTIÓN DE PARTICIPANTES DEL GRUPO (1:N)
# =========================

def seccion_participantes_grupo(grupo_id, grupos_service, modo="editar"):
    """
    Sección completa de gestión de participantes para un grupo (1:N).
    - modo="crear": solo muestra placeholder.
    - modo="editar": permite alta, importación y listado.
    """
    st.markdown("### 👥 Participantes del Grupo")

    try:
        df_participantes = grupos_service.get_participantes_grupo(grupo_id)
    except Exception as e:
        st.error(f"❌ Error al cargar participantes: {e}")
        df_participantes = pd.DataFrame()

    # Mostrar participantes
    if not df_participantes.empty:
        st.write(f"**Participantes actuales ({len(df_participantes)}):**")
        st.dataframe(
            df_participantes[["dni", "nombre", "apellidos", "email", "telefono"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No hay participantes asignados a este grupo")

    if modo == "editar":
        st.divider()
        st.subheader("➕ Añadir Participante Manualmente")

        with st.form(key=f"form_add_participante_{grupo_id}"):
            col1, col2 = st.columns(2)
            with col1:
                dni = st.text_input("DNI/NIE *", max_chars=15)
                nombre = st.text_input("Nombre *")
                apellidos = st.text_input("Apellidos *")
            with col2:
                email = st.text_input("Email")
                telefono = st.text_input("Teléfono")
            submitted = st.form_submit_button("Añadir Participante")
            if submitted:
                if not dni or not nombre or not apellidos:
                    st.error("⚠️ DNI, Nombre y Apellidos son obligatorios")
                elif not validar_dni_cif(dni):
                    st.error("⚠️ DNI no válido")
                else:
                    data = {
                        "dni": dni,
                        "nombre": nombre,
                        "apellidos": apellidos,
                        "email": email,
                        "telefono": telefono,
                        "grupo_id": grupo_id
                    }
                    try:
                        grupos_service.create_participante(data)
                        st.success("✅ Participante añadido correctamente")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al añadir participante: {e}")

        st.divider()
        st.subheader("📥 Importar Participantes desde Excel")

        archivo_excel = st.file_uploader("Subir archivo Excel", type=["xlsx"], key=f"excel_{grupo_id}")
        if archivo_excel is not None:
            try:
                df_excel = pd.read_excel(archivo_excel)
                st.write("Vista previa de los datos importados:")
                st.dataframe(df_excel.head(), use_container_width=True)
                if st.button("Importar Participantes", key=f"import_participantes_{grupo_id}"):
                    try:
                        n_importados = grupos_service.importar_participantes_excel(grupo_id, df_excel)
                        st.success(f"✅ {n_importados} participantes importados correctamente")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al importar: {e}")
            except Exception as e:
                st.error(f"❌ Error al leer archivo Excel: {e}")
# =========================
# GESTIÓN DE COSTES FUNDAE
# =========================

def seccion_costes_fundae(grupo_id, grupos_service, modo="editar"):
    """
    Sección de gestión de costes FUNDAE.
    - modo="crear": placeholder
    - modo="editar": permite alta/edición de costes
    """
    st.markdown("### 💶 Costes FUNDAE")

    try:
        df_costes = grupos_service.get_costes_grupo(grupo_id)
    except Exception as e:
        st.error(f"❌ Error al cargar costes: {e}")
        df_costes = pd.DataFrame()

    # Mostrar costes actuales
    if not df_costes.empty:
        st.write("**Costes registrados:**")
        st.dataframe(
            df_costes[["tipo", "concepto", "importe"]],
            use_container_width=True,
            hide_index=True
        )
        total_directos = df_costes[df_costes["tipo"] == "DIRECTO"]["importe"].sum()
        total_indirectos = df_costes[df_costes["tipo"] == "INDIRECTO"]["importe"].sum()
        st.metric("Total Costes Directos", f"{total_directos:.2f} €")
        st.metric("Total Costes Indirectos", f"{total_indirectos:.2f} €")
        if total_indirectos > (0.3 * total_directos):
            st.error("⚠️ Los costes indirectos no pueden superar el 30% de los directos")
    else:
        st.info("No hay costes registrados para este grupo")

    if modo == "editar":
        st.divider()
        st.subheader("➕ Añadir Coste")

        with st.form(key=f"form_add_coste_{grupo_id}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                tipo = st.selectbox("Tipo", ["DIRECTO", "INDIRECTO"], key=f"tipo_coste_{grupo_id}")
            with col2:
                concepto = st.text_input("Concepto", key=f"concepto_coste_{grupo_id}")
            with col3:
                importe = st.number_input("Importe (€)", min_value=0.0, step=0.01, key=f"importe_coste_{grupo_id}")

            submitted = st.form_submit_button("Añadir Coste")
            if submitted:
                if not concepto:
                    st.error("⚠️ El concepto es obligatorio")
                else:
                    data = {"tipo": tipo, "concepto": concepto, "importe": importe, "grupo_id": grupo_id}
                    try:
                        grupos_service.create_coste(data)
                        st.success("✅ Coste añadido correctamente")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al añadir coste: {e}")

        st.divider()
        st.subheader("📅 Bonificaciones Mensuales")

        try:
            df_bonificaciones = grupos_service.get_bonificaciones_grupo(grupo_id)
        except Exception as e:
            st.error(f"❌ Error al cargar bonificaciones: {e}")
            df_bonificaciones = pd.DataFrame()

        if not df_bonificaciones.empty:
            st.write("**Bonificaciones registradas:**")
            st.dataframe(
                df_bonificaciones[["mes", "importe"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No hay bonificaciones registradas")

        with st.form(key=f"form_add_bonificacion_{grupo_id}"):
            col1, col2 = st.columns(2)
            with col1:
                mes = st.selectbox("Mes", list(range(1, 13)), key=f"mes_bon_{grupo_id}")
            with col2:
                importe_bon = st.number_input("Importe (€)", min_value=0.0, step=0.01, key=f"importe_bon_{grupo_id}")

            submitted_bon = st.form_submit_button("Añadir Bonificación")
            if submitted_bon:
                data = {"mes": mes, "importe": importe_bon, "grupo_id": grupo_id}
                try:
                    grupos_service.create_bonificacion(data)
                    st.success("✅ Bonificación añadida correctamente")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al añadir bonificación: {e}")
# =========================
# MODALES COMPLETOS PARA GRUPOS
# =========================

@st.dialog("Crear Nuevo Grupo FUNDAE", width="large")
def modal_crear_grupo_completo(grupos_service):
    """Modal completo para crear grupo con todas las secciones"""
    st.markdown("### ✨ Nuevo Grupo Formativo FUNDAE")
    st.caption("Complete los datos del grupo. Podrá añadir tutores, empresas, participantes y costes una vez creado.")

    acciones_dict = grupos_service.get_acciones_dict()
    if not acciones_dict:
        st.error("❌ No hay acciones formativas disponibles. Crea una acción formativa primero.")
        return

    with st.form("form_crear_grupo_completo", clear_on_submit=False):
        # =====================
        # SECCIÓN 1: DATOS BÁSICOS FUNDAE
        # =====================
        with st.expander("📋 1. Datos Básicos FUNDAE", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                codigo_grupo = st.text_input("Código del Grupo *", max_chars=50)
                acciones_nombres = list(acciones_dict.keys())
                accion_formativa = st.selectbox("Acción Formativa *", acciones_nombres)
                accion_id = acciones_dict[accion_formativa]
                modalidad_grupo = grupos_service.normalizar_modalidad_fundae(
                    grupos_service.get_accion_modalidad(accion_id)
                )
                st.text_input("Modalidad", value=modalidad_grupo, disabled=True)
                fecha_inicio = st.date_input("Fecha de Inicio *", value=datetime.now().date())
            with col2:
                provincias = grupos_service.get_provincias()
                prov_opciones = {p["nombre"]: p["id"] for p in provincias}
                provincia_sel = st.selectbox("Provincia *", options=list(prov_opciones.keys()))
                localidades = grupos_service.get_localidades_por_provincia(prov_opciones[provincia_sel])
                loc_nombres = [l["nombre"] for l in localidades]
                localidad_sel = st.selectbox("Localidad *", options=loc_nombres)
                cp = st.text_input("Código Postal")
                fecha_fin_prevista = st.date_input("Fecha Fin Prevista *", value=datetime.now().date() + timedelta(days=30))

            col3, col4 = st.columns(2)
            with col3:
                responsable = st.text_input("Responsable del Grupo *")
                n_participantes_previstos = st.number_input("Participantes Previstos *", min_value=1, max_value=30, value=8)
            with col4:
                telefono_contacto = st.text_input("Teléfono de Contacto *")

            lugar_imparticion = st.text_area("Lugar de Impartición", height=60)
            observaciones = st.text_area("Observaciones", height=80)

        # =====================
        # SECCIÓN 2: HORARIOS FUNDAE
        # =====================
        with st.expander("🕐 2. Horarios de Impartición", expanded=True):
            horario_final = crear_selector_horario_fundae(prefix="crear")

        st.divider()
        col_submit, col_cancel = st.columns([2, 1])
        with col_submit:
            submitted = st.form_submit_button("✅ Crear Grupo", type="primary")
        with col_cancel:
            if st.form_submit_button("❌ Cancelar"):
                st.rerun()

        if submitted:
            errores = []
            if not codigo_grupo:
                errores.append("El código del grupo es obligatorio")
            if not responsable:
                errores.append("El responsable es obligatorio")
            if not telefono_contacto:
                errores.append("El teléfono de contacto es obligatorio")
            if fecha_inicio >= fecha_fin_prevista:
                errores.append("La fecha de fin debe ser posterior a la de inicio")

            if errores:
                for error in errores:
                    st.error(f"⚠️ {error}")
                return

            datos_crear = {
                "codigo_grupo": codigo_grupo,
                "accion_formativa_id": accion_id,
                "modalidad": modalidad_grupo,
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin_prevista": fecha_fin_prevista.isoformat(),
                "provincia": provincia_sel,
                "localidad": localidad_sel,
                "cp": cp,
                "responsable": responsable,
                "telefono_contacto": telefono_contacto,
                "n_participantes_previstos": n_participantes_previstos,
                "lugar_imparticion": lugar_imparticion,
                "observaciones": observaciones,
                "horario": horario_final
            }
            if grupos_service.rol == "gestor":
                datos_crear["empresa_id"] = grupos_service.empresa_id

            try:
                exito, grupo_id = grupos_service.create_grupo_completo(datos_crear)
                if exito:
                    st.success(f"✅ Grupo '{codigo_grupo}' creado correctamente")
                    st.balloons()
                    grupos_service.get_grupos_completos.clear()
                    st.rerun()
                else:
                    st.error("❌ Error al crear el grupo")
            except Exception as e:
                st.error(f"❌ Error al crear grupo: {e}")


@st.dialog("Editar Grupo FUNDAE", width="large")
def modal_editar_grupo_completo(grupo_data, grupos_service):
    """Modal completo para editar grupo con todas las secciones"""
    st.markdown(f"### ✏️ Editar Grupo: {grupo_data['codigo_grupo']}")
    estado_actual = determinar_estado_grupo(grupo_data)
    color_estado = {"ABIERTO": "🟢", "FINALIZAR": "🟡", "FINALIZADO": "✅"}
    st.caption(f"Estado: {color_estado.get(estado_actual, '⚪')} {estado_actual}")

    acciones_dict = grupos_service.get_acciones_dict()

    with st.form("form_editar_grupo_completo", clear_on_submit=False):
        # =====================
        # SECCIÓN 1: DATOS BÁSICOS
        # =====================
        with st.expander("📋 1. Datos Básicos FUNDAE", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.text_input("Código del Grupo", value=grupo_data.get('codigo_grupo', ''), disabled=True)
                acciones_nombres = list(acciones_dict.keys())
                accion_actual = next((nombre for nombre, id_accion in acciones_dict.items() if id_accion == grupo_data.get('accion_formativa_id')), "")
                idx_accion = acciones_nombres.index(accion_actual) if accion_actual in acciones_nombres else 0
                accion_formativa = st.selectbox("Acción Formativa *", acciones_nombres, index=idx_accion)
                accion_id = acciones_dict[accion_formativa]
                modalidad_grupo = grupos_service.normalizar_modalidad_fundae(
                    grupos_service.get_accion_modalidad(accion_id)
                )
                st.text_input("Modalidad", value=modalidad_grupo, disabled=True)
                fecha_inicio = st.date_input("Fecha de Inicio *", value=safe_date_conversion(grupo_data.get('fecha_inicio')))
            with col2:
                provincias = grupos_service.get_provincias()
                prov_opciones = {p["nombre"]: p["id"] for p in provincias}
                provincia_actual = grupo_data.get("provincia", "")
                idx_prov = list(prov_opciones.keys()).index(provincia_actual) if provincia_actual in prov_opciones else 0
                provincia_sel = st.selectbox("Provincia *", list(prov_opciones.keys()), index=idx_prov)
                localidades = grupos_service.get_localidades_por_provincia(prov_opciones[provincia_sel])
                loc_nombres = [l["nombre"] for l in localidades]
                localidad_actual = grupo_data.get("localidad", "")
                idx_loc = loc_nombres.index(localidad_actual) if localidad_actual in loc_nombres else 0
                localidad_sel = st.selectbox("Localidad *", loc_nombres, index=idx_loc if loc_nombres else 0)
                cp = st.text_input("Código Postal", value=grupo_data.get('cp', ''))
                fecha_fin_prevista = st.date_input("Fecha Fin Prevista *", value=safe_date_conversion(grupo_data.get('fecha_fin_prevista')))
            col3, col4 = st.columns(2)
            with col3:
                responsable = st.text_input("Responsable del Grupo *", value=grupo_data.get('responsable', ''))
                n_participantes_previstos = st.number_input("Participantes Previstos *", min_value=1, max_value=30, value=int(grupo_data.get('n_participantes_previstos', 8)))
            with col4:
                telefono_contacto = st.text_input("Teléfono de Contacto *", value=grupo_data.get('telefono_contacto', ''))
            lugar_imparticion = st.text_area("Lugar de Impartición", value=grupo_data.get('lugar_imparticion', ''), height=60)
            observaciones = st.text_area("Observaciones", value=grupo_data.get('observaciones', ''), height=80)

        # =====================
        # SECCIÓN 2: HORARIOS
        # =====================
        with st.expander("🕐 2. Horarios de Impartición", expanded=False):
            horario_actual = grupo_data.get('horario', '')
            if horario_actual:
                st.info(f"**Horario actual**: {horario_actual}")
                cambiar_horario = st.checkbox("Modificar horario", key=f"cambiar_horario_{grupo_data['id']}")
                if cambiar_horario:
                    horario_nuevo = crear_selector_horario_fundae(prefix=f"editar_{grupo_data['id']}")
                else:
                    horario_nuevo = horario_actual
            else:
                horario_nuevo = crear_selector_horario_fundae(prefix=f"editar_{grupo_data['id']}")

        # =====================
        # SECCIÓN 3: FINALIZACIÓN
        # =====================
        mostrar_finalizacion = (
            estado_actual in ["FINALIZAR", "FINALIZADO"] or
            (grupo_data.get("fecha_fin_prevista") and safe_date_conversion(grupo_data.get("fecha_fin_prevista")) <= datetime.now().date())
        )
        datos_finalizacion = {}
        if mostrar_finalizacion:
            with st.expander("🏁 3. Datos de Finalización", expanded=(estado_actual == "FINALIZAR")):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    fecha_fin_real = st.date_input("Fecha Fin Real *", value=safe_date_conversion(grupo_data.get("fecha_fin")) or datetime.now().date())
                    n_finalizados = st.number_input("Participantes Finalizados *", min_value=0, max_value=n_participantes_previstos, value=safe_int_conversion(grupo_data.get("n_participantes_finalizados"), 0))
                with col_f2:
                    n_aptos = st.number_input("Participantes Aptos *", min_value=0, max_value=n_finalizados if n_finalizados > 0 else n_participantes_previstos, value=safe_int_conversion(grupo_data.get("n_aptos"), 0))
                    n_no_aptos = st.number_input("Participantes No Aptos *", min_value=0, max_value=n_finalizados if n_finalizados > 0 else n_participantes_previstos, value=safe_int_conversion(grupo_data.get("n_no_aptos"), 0))
                datos_finalizacion = {
                    "fecha_fin": fecha_fin_real.isoformat(),
                    "n_participantes_finalizados": n_finalizados,
                    "n_aptos": n_aptos,
                    "n_no_aptos": n_no_aptos
                }

        # =====================
        # SECCIÓN 4: TUTORES
        # =====================
        with st.expander("👨‍🏫 4. Tutores del Grupo", expanded=False):
            seccion_tutores_grupo(grupo_data["id"], grupos_service, modo="editar")

        # =====================
        # SECCIÓN 5: EMPRESAS
        # =====================
        with st.expander("🏢 5. Empresas Participantes", expanded=False):
            seccion_empresas_grupo(grupo_data["id"], grupos_service, modo="editar")

        # =====================
        # SECCIÓN 6: PARTICIPANTES
        # =====================
        with st.expander("👥 6. Participantes del Grupo", expanded=False):
            seccion_participantes_grupo(grupo_data["id"], grupos_service, modo="editar")

        # =====================
        # SECCIÓN 7: COSTES FUNDAE
        # =====================
        with st.expander("💶 7. Costes FUNDAE", expanded=False):
            seccion_costes_fundae(grupo_data["id"], grupos_service, modo="editar")

        st.divider()
        col_save, col_reload, col_delete = st.columns([2, 1, 1])
        with col_save:
            submitted = st.form_submit_button("💾 Guardar Cambios", type="primary")
        with col_reload:
            if st.form_submit_button("🔄 Recargar"):
                st.rerun()
        with col_delete:
            if grupos_service.session_state.role == "admin":
                if st.form_submit_button("🗑️ Eliminar"):
                    confirmar_key = f"confirm_delete_grupo_{grupo_data['id']}"
                    if st.session_state.get(confirmar_key, False):
                        try:
                            if grupos_service.delete_grupo(grupo_data['id']):
                                st.success("Grupo eliminado correctamente")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")
                    else:
                        st.session_state[confirmar_key] = True
                        st.warning("Presione de nuevo para confirmar eliminación")

        if submitted:
            datos_actualizar = {
                "modalidad": modalidad_grupo,
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin_prevista": fecha_fin_prevista.isoformat(),
                "provincia": provincia_sel,
                "localidad": localidad_sel,
                "cp": cp,
                "responsable": responsable,
                "telefono_contacto": telefono_contacto,
                "n_participantes_previstos": n_participantes_previstos,
                "lugar_imparticion": lugar_imparticion,
                "observaciones": observaciones,
                "horario": horario_nuevo
            }
            if datos_finalizacion:
                datos_actualizar.update(datos_finalizacion)
            try:
                if grupos_service.update_grupo(grupo_data["id"], datos_actualizar):
                    st.success("✅ Cambios guardados correctamente")
                    grupos_service.get_grupos_completos.clear()
                    st.rerun()
                else:
                    st.error("❌ Error al guardar cambios")
            except Exception as e:
                st.error(f"❌ Error al actualizar: {e}")
# =========================
# KPIs Y AVISOS
# =========================

def mostrar_kpis_grupos(df_grupos: pd.DataFrame):
    if df_grupos.empty:
        st.info("📋 No hay grupos registrados.")
        return
    total = len(df_grupos)
    abiertos = 0
    por_finalizar = 0
    finalizados = 0
    for _, g in df_grupos.iterrows():
        estado = determinar_estado_grupo(g.to_dict())
        if estado == "ABIERTO":
            abiertos += 1
        elif estado == "FINALIZAR":
            por_finalizar += 1
        elif estado == "FINALIZADO":
            finalizados += 1
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("📊 Total Grupos", total)
    with c2: st.metric("🟢 Abiertos", abiertos)
    with c3: st.metric("🟡 Por Finalizar", por_finalizar)
    with c4: st.metric("✅ Finalizados", finalizados)

def mostrar_avisos_grupos(grupos_pendientes: list):
    if not grupos_pendientes:
        return
    st.warning(f"⚠️ **{len(grupos_pendientes)} grupo(s) pendiente(s) de finalización**")
    with st.expander("Ver grupos pendientes", expanded=False):
        for grupo in grupos_pendientes[:5]:
            col1, col2 = st.columns([3, 1])
            with col1:
                fin_prev = grupo.get('fecha_fin_prevista')
                fin_prev_str = str(fin_prev)[:10] if fin_prev else "—"
                st.write(f"**{grupo.get('codigo_grupo', '—')}** · Fin previsto: {fin_prev_str}")
            with col2:
                if st.button("Finalizar", key=f"finalizar_{grupo.get('id')}", type="secondary"):
                    g = grupo.copy()
                    if not g.get('fecha_fin'):
                        g['_mostrar_finalizacion'] = True
                    st.session_state.grupo_seleccionado = g
                    st.rerun()

# =========================
# FILTROS AVANZADOS
# =========================

def crear_filtros_avanzados_grupos(grupos_service):
    st.markdown("#### 🔍 Filtros de Búsqueda")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        buscar_texto = st.text_input("Buscar grupo", placeholder="Código, localidad...", key="buscar_grupo_texto")
    with col2:
        estados_opciones = ["Todos", "ABIERTO", "FINALIZAR", "FINALIZADO"]
        estado_filtro = st.selectbox("Estado", estados_opciones, key="filtro_estado_grupo")
    with col3:
        modalidades_opciones = ["Todas", "PRESENCIAL", "TELEFORMACION", "MIXTA"]
        modalidad_filtro = st.selectbox("Modalidad", modalidades_opciones, key="filtro_modalidad_grupo")
    with col4:
        try:
            provincias = grupos_service.get_provincias()
            prov_opciones = ["Todas"] + [p["nombre"] for p in provincias]
            provincia_filtro = st.selectbox("Provincia", prov_opciones, key="filtro_provincia_grupo")
        except:
            provincia_filtro = "Todas"
    with col5:
        filtro_fecha = st.selectbox("Período", ["Todos", "Este mes", "Próximos 30 días", "Finalizados este año"], key="filtro_fecha_grupo")

    filtros = {
        'buscar_texto': buscar_texto if buscar_texto else None,
        'estado': estado_filtro if estado_filtro != "Todos" else None,
        'modalidad': modalidad_filtro if modalidad_filtro != "Todas" else None,
        'provincia': provincia_filtro if provincia_filtro != "Todas" else None,
        'periodo': filtro_fecha if filtro_fecha != "Todos" else None
    }
    st.session_state.filtros_grupos = filtros
    return filtros

def aplicar_filtros_grupos(df_grupos, filtros):
    if df_grupos.empty:
        return df_grupos
    df_filtrado = df_grupos.copy()
    if "Estado" not in df_filtrado.columns:
        df_filtrado["Estado"] = df_filtrado.apply(lambda row: determinar_estado_grupo(row.to_dict()), axis=1)

    if filtros.get('buscar_texto'):
        texto = filtros['buscar_texto'].lower()
        mask = (
            df_filtrado['codigo_grupo'].str.lower().str.contains(texto, na=False) |
            df_filtrado.get('localidad', pd.Series(dtype='object')).str.lower().str.contains(texto, na=False) |
            df_filtrado.get('accion_nombre', pd.Series(dtype='object')).str.lower().str.contains(texto, na=False)
        )
        df_filtrado = df_filtrado[mask]

    if filtros.get('estado'):
        df_filtrado = df_filtrado[df_filtrado['Estado'] == filtros['estado']]
    if filtros.get('modalidad'):
        df_filtrado = df_filtrado[df_filtrado['modalidad'] == filtros['modalidad']]
    if filtros.get('provincia'):
        df_filtrado = df_filtrado[df_filtrado.get('provincia', '') == filtros['provincia']]

    if filtros.get('periodo'):
        hoy = datetime.now().date()
        if filtros['periodo'] == "Este mes":
            inicio_mes = hoy.replace(day=1)
            fin_mes = (inicio_mes + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            mask = (
                (pd.to_datetime(df_filtrado['fecha_inicio'], errors='coerce').dt.date >= inicio_mes) &
                (pd.to_datetime(df_filtrado['fecha_inicio'], errors='coerce').dt.date <= fin_mes)
            )
            df_filtrado = df_filtrado[mask]
        elif filtros['periodo'] == "Próximos 30 días":
            fecha_limite = hoy + timedelta(days=30)
            mask = (
                (pd.to_datetime(df_filtrado['fecha_inicio'], errors='coerce').dt.date >= hoy) &
                (pd.to_datetime(df_filtrado['fecha_inicio'], errors='coerce').dt.date <= fecha_limite)
            )
            df_filtrado = df_filtrado[mask]
        elif filtros['periodo'] == "Finalizados este año":
            inicio_año = hoy.replace(month=1, day=1)
            mask = (
                (df_filtrado['Estado'] == 'FINALIZADO') &
                (pd.to_datetime(df_filtrado.get('fecha_fin', df_filtrado['fecha_fin_prevista']), errors='coerce').dt.date >= inicio_año)
            )
            df_filtrado = df_filtrado[mask]
    return df_filtrado

# =========================
# MAIN
# =========================

def main_grupos_con_modales(supabase, session_state):
    st.title("👥 Gestión de Grupos de Formación")
    st.caption("Creación, edición y seguimiento de grupos FUNDAE con todas sus secciones.")
    st.divider()

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    grupos_service = get_grupos_service(supabase, session_state)

    try:
        df_grupos = grupos_service.get_grupos_completos()
        mostrar_kpis_grupos(df_grupos)
        grupos_pendientes = get_grupos_pendientes_finalizacion(df_grupos)
        mostrar_avisos_grupos(grupos_pendientes)
    except Exception as e:
        st.error(f"Error al cargar estadísticas: {e}")
        df_grupos = pd.DataFrame()

    filtros = crear_filtros_avanzados_grupos(grupos_service)
    df_filtrado = aplicar_filtros_grupos(df_grupos, filtros)

    st.markdown("### 📋 Listado de Grupos")
    if df_filtrado.empty:
        st.info("No hay grupos que cumplan los filtros.")
    else:
        st.dataframe(
            df_filtrado[[
                "codigo_grupo", "accion_nombre", "modalidad", "provincia",
                "localidad", "fecha_inicio", "fecha_fin_prevista", "Estado"
            ]],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            key="tabla_grupos"
        )
        if "tabla_grupos" in st.session_state:
            seleccion = st.session_state["tabla_grupos"].selection
            if seleccion and seleccion.rows:
                idx = seleccion.rows[0]
                grupo_sel = df_filtrado.iloc[idx].to_dict()
                st.session_state.grupo_seleccionado = grupo_sel
                modal_editar_grupo_completo(grupo_sel, grupos_service)

    st.divider()
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("➕ Crear Nuevo Grupo"):
            modal_crear_grupo_completo(grupos_service)
    with col2:
        if "grupo_seleccionado" in st.session_state and st.session_state.grupo_seleccionado:
            grupo_data = st.session_state.grupo_seleccionado
            modal_editar_grupo_completo(grupo_data, grupos_service)

# =========================
# ALIAS PARA COMPATIBILIDAD CON app.py
# =========================

def main(supabase, session_state):
    return main_grupos_con_modales(supabase, session_state)
