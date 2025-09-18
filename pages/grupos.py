import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from services.grupos_service import get_grupos_service
from utils import validar_dni_cif, export_csv
import re
import math

# =========================
# CONFIGURACIÓN Y CONSTANTES
# =========================

MODALIDADES_FUNDAE = {
    "PRESENCIAL": "PRESENCIAL",
    "TELEFORMACION": "TELEFORMACION", 
    "MIXTA": "MIXTA"
}

INTERVALOS_TIEMPO = [
    f"{h:02d}:{m:02d}" for h in range(6, 24) for m in [0, 15, 30, 45]
]

DIAS_SEMANA = ["L", "M", "X", "J", "V", "S", "D"]
NOMBRES_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
# =========================
# HELPERS GENERALES
# =========================

def safe_int_conversion(value, default=0):
    """Convierte un valor a entero de forma segura, manejando NaN y None."""
    if value is None:
        return default
    if pd.isna(value):
        return default
    if isinstance(value, (int, float)):
        try:
            if math.isnan(float(value)):
                return default
        except:
            return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

def safe_date_conversion(date_value):
    """Convierte valores de fecha de forma segura."""
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
# FUNCIONES DE ESTADO
# =========================

def determinar_estado_grupo(grupo_data):
    """Determina el estado automático del grupo según las fechas y datos."""
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
    """Obtiene grupos que están pendientes de finalización."""
    if df_grupos.empty:
        return []
    
    pendientes = []
    for _, grupo in df_grupos.iterrows():
        estado = determinar_estado_grupo(grupo.to_dict())
        if estado == "FINALIZAR":
            pendientes.append(grupo.to_dict())
    return pendientes
# =========================
# FUNCIONES DE VALIDACIÓN FUNDAE
# =========================

def validar_horario_fundae(horario_str):
    """Valida que el horario cumpla con el formato FUNDAE."""
    if not horario_str:
        return False, "Horario requerido"
    if "Días:" not in horario_str:
        return False, "Debe especificar días de la semana"
    if not any(x in horario_str for x in ["Mañana:", "Tarde:"]):
        return False, "Debe especificar al menos un tramo horario"
    return True, ""

def construir_horario_fundae(manana_inicio, manana_fin, tarde_inicio, tarde_fin, dias_seleccionados):
    """Construye string de horario en formato FUNDAE."""
    partes = []
    if manana_inicio and manana_fin:
        partes.append(f"Mañana: {manana_inicio} - {manana_fin}")
    if tarde_inicio and tarde_fin:
        partes.append(f"Tarde: {tarde_inicio} - {tarde_fin}")
    if dias_seleccionados:
        dias_str = "-".join([d for d in DIAS_SEMANA if d in dias_seleccionados])
        if dias_str:
            partes.append(f"Días: {dias_str}")
    return " | ".join(partes)

def parsear_horario_fundae(horario_str):
    """Parsea un horario FUNDAE a sus componentes."""
    if not horario_str:
        return None, None, None, None, []
    manana_inicio = manana_fin = tarde_inicio = tarde_fin = None
    dias = []
    try:
        partes = horario_str.split(" | ")
        for parte in partes:
            parte = parte.strip()
            if parte.startswith("Mañana:"):
                horas = parte.replace("Mañana: ", "").split(" - ")
                if len(horas) == 2:
                    manana_inicio, manana_fin = horas[0].strip(), horas[1].strip()
            elif parte.startswith("Tarde:"):
                horas = parte.replace("Tarde: ", "").split(" - ")  
                if len(horas) == 2:
                    tarde_inicio, tarde_fin = horas[0].strip(), horas[1].strip()
            elif parte.startswith("Días:"):
                dias_str = parte.replace("Días: ", "").strip()
                dias = dias_str.split("-")
    except Exception:
        pass
    return manana_inicio, manana_fin, tarde_inicio, tarde_fin, dias

def validar_campos_obligatorios_fundae(datos):
    """Valida campos obligatorios para XML FUNDAE."""
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
    """Valida datos de finalización de grupo."""
    errores = []
    try:
        finalizados = int(datos.get("n_participantes_finalizados", 0))
        aptos = int(datos.get("n_aptos", 0))
        no_aptos = int(datos.get("n_no_aptos", 0))
        if finalizados <= 0:
            errores.append("Debe haber al menos 1 participante finalizado")
        if aptos + no_aptos != finalizados:
            errores.append("La suma de aptos + no aptos debe igual participantes finalizados")
        if aptos < 0 or no_aptos < 0:
            errores.append("Los números no pueden ser negativos")
    except ValueError:
        errores.append("Los campos numéricos deben ser números enteros")
    return errores
# =========================
# COMPONENTES UI MEJORADOS
# =========================

def mostrar_kpis_grupos(df_grupos):
    """Muestra KPIs de grupos con métricas."""
    if df_grupos.empty:
        st.info("📋 No hay grupos registrados.")
        return
    total = len(df_grupos)
    abiertos = sum(1 for _, g in df_grupos.iterrows() if determinar_estado_grupo(g.to_dict()) == "ABIERTO")
    por_finalizar = sum(1 for _, g in df_grupos.iterrows() if determinar_estado_grupo(g.to_dict()) == "FINALIZAR") 
    finalizados = sum(1 for _, g in df_grupos.iterrows() if determinar_estado_grupo(g.to_dict()) == "FINALIZADO")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Total Grupos", total)
    with col2:
        st.metric("🟢 Abiertos", abiertos, delta=f"{(abiertos/total*100):.1f}%" if total > 0 else None)
    with col3:
        if por_finalizar > 0:
            st.metric("🟡 Por Finalizar", por_finalizar, delta=f"¡{por_finalizar} pendientes!", delta_color="inverse")
        else:
            st.metric("🟡 Por Finalizar", 0, delta="Todo al día ✅")
    with col4:
        st.metric("✅ Finalizados", finalizados, delta=f"{(finalizados/total*100):.1f}%" if total > 0 else None)

def mostrar_avisos_grupos(grupos_pendientes):
    """Muestra avisos de grupos pendientes de finalización."""
    if not grupos_pendientes:
        return
    st.warning(f"⚠️ {len(grupos_pendientes)} grupo(s) pendiente(s) de finalización", icon="⚠️")
    with st.expander("Ver grupos pendientes de finalización", expanded=False):
        for i, grupo in enumerate(grupos_pendientes[:5]):
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{grupo.get('codigo_grupo')}**")
                    fecha_fin = grupo.get('fecha_fin_prevista', 'Sin fecha')
                    empresa = grupo.get('empresa_nombre', 'Sin empresa')
                    st.caption(f"📅 Fin previsto: {fecha_fin} | 🏢 {empresa}")
                with col2:
                    if st.button("🏁 Finalizar", key=f"finalizar_{grupo.get('id')}", type="secondary", use_container_width=True):
                        grupo_copy = grupo.copy()
                        if not grupo_copy.get('fecha_fin'):
                            grupo_copy['_mostrar_finalizacion'] = True
                        st.session_state.grupo_seleccionado = grupo_copy
                        st.rerun()
                if i < len(grupos_pendientes[:5]) - 1:
                    st.divider()
# =========================
# SELECTOR DE HORARIO FUNDAE
# =========================

def crear_selector_horario_fundae(prefix=""):
    """Crea un selector de horario compatible con FUNDAE."""
    st.markdown("#### ⏰ Configuración de Horarios FUNDAE")
    st.caption("Intervalos de 15 minutos obligatorios según normativa FUNDAE")

    tipo_horario = st.radio(
        "Tipo de jornada:",
        ["Solo Mañana", "Solo Tarde", "Mañana y Tarde"],
        horizontal=True,
        key=f"{prefix}_tipo_horario",
        help="Selecciona los tramos horarios que necesitas"
    )

    col1, col2 = st.columns(2)
    manana_inicio = manana_fin = tarde_inicio = tarde_fin = None

    intervalos_manana = [f"{h:02d}:{m:02d}" for h in range(6, 15) for m in [0, 15, 30, 45]]
    intervalos_tarde = [f"{h:02d}:{m:02d}" for h in range(15, 23) for m in [0, 15, 30, 45]]

    if tipo_horario in ["Solo Mañana", "Mañana y Tarde"]:
        with col1:
            st.markdown("**🌅 Tramo Mañana (06:00 - 15:00)**")
            sub_col1, sub_col2 = st.columns(2)
            with sub_col1:
                manana_inicio = st.selectbox("Hora inicio:", intervalos_manana[:-1], index=12, key=f"{prefix}_manana_inicio")
            with sub_col2:
                if manana_inicio:
                    idx_inicio = intervalos_manana.index(manana_inicio)
                    horas_fin_validas = intervalos_manana[idx_inicio + 1:]
                    manana_fin = st.selectbox("Hora fin:", horas_fin_validas, index=min(15, len(horas_fin_validas)-1), key=f"{prefix}_manana_fin")

    if tipo_horario in ["Solo Tarde", "Mañana y Tarde"]:
        with col2:
            st.markdown("**🌆 Tramo Tarde (15:00 - 23:00)**")
            sub_col1, sub_col2 = st.columns(2)
            with sub_col1:
                tarde_inicio = st.selectbox("Hora inicio:", intervalos_tarde[:-1], index=0, key=f"{prefix}_tarde_inicio")
            with sub_col2:
                if tarde_inicio:
                    idx_inicio = intervalos_tarde.index(tarde_inicio)
                    horas_fin_validas = intervalos_tarde[idx_inicio + 1:]
                    tarde_fin = st.selectbox("Hora fin:", horas_fin_validas, index=min(15, len(horas_fin_validas)-1), key=f"{prefix}_tarde_fin")

    st.markdown("**📅 Días de Impartición**")
    cols = st.columns(7)
    dias_seleccionados = []
    for i, (dia_corto, dia_largo) in enumerate(zip(DIAS_SEMANA, NOMBRES_DIAS)):
        with cols[i]:
            if st.checkbox(f"{dia_corto}\n{dia_largo[:3]}", value=dia_corto in ["L", "M", "X", "J", "V"], key=f"{prefix}_dia_{dia_corto}"):
                dias_seleccionados.append(dia_corto)

    horario_final = construir_horario_fundae(manana_inicio, manana_fin, tarde_inicio, tarde_fin, dias_seleccionados)

    if horario_final:
        st.success(f"✅ **Horario FUNDAE generado:** `{horario_final}`", icon="✅")
        es_valido, error = validar_horario_fundae(horario_final)
        if not es_valido:
            st.error(f"❌ Error en horario: {error}", icon="❌")
    else:
        st.warning("⚠️ Configure al menos un tramo horario y días para generar el horario FUNDAE", icon="⚠️")

    return horario_final
# =========================
# MODAL PARA CREAR GRUPO
# =========================

@st.dialog("Crear Nuevo Grupo FUNDAE", width="large")
def modal_crear_grupo(grupos_service):
    """Modal para crear grupos."""
    acciones_dict = grupos_service.get_acciones_dict()
    if not acciones_dict:
        st.error("❌ No hay acciones formativas disponibles. Crea una primero.")
        return

    st.markdown("### ➕ Crear Nuevo Grupo de Formación")
    st.caption("Complete la información básica obligatoria para FUNDAE")

    with st.form("form_crear_grupo_modal", clear_on_submit=False):
        st.markdown("#### 📋 Información Básica")
        col1, col2 = st.columns(2)
        with col1:
            codigo_grupo = st.text_input("Código del Grupo *", max_chars=50, help="Código único del grupo", placeholder="Ej: GRP001-2025")
            accion_formativa = st.selectbox("Acción Formativa *", list(acciones_dict.keys()))
            fecha_inicio = st.date_input("Fecha de Inicio *", value=date.today())
        with col2:
            n_participantes_previstos = st.number_input("Participantes Previstos *", min_value=1, max_value=30, value=8)
            fecha_fin_prevista = st.date_input("Fecha Fin Prevista *")
            accion_id = acciones_dict[accion_formativa]
            modalidad_grupo = grupos_service.normalizar_modalidad_fundae(grupos_service.get_accion_modalidad(accion_id))
            st.text_input("Modalidad", value=modalidad_grupo, disabled=True)

        st.markdown("#### 📍 Localización")
        col3, col4 = st.columns(2)
        with col3:
            provincias = grupos_service.get_provincias()
            prov_opciones = {p["nombre"]: p["id"] for p in provincias}
            provincia_sel = st.selectbox("Provincia *", options=list(prov_opciones.keys()))
        with col4:
            if provincia_sel:
                localidades = grupos_service.get_localidades_por_provincia(prov_opciones[provincia_sel])
                localidad_sel = st.selectbox("Localidad *", [l["nombre"] for l in localidades])
            else:
                localidad_sel = st.text_input("Localidad *")

        col5, col6 = st.columns(2)
        with col5:
            cp = st.text_input("Código Postal")
            responsable = st.text_input("Responsable *")
        with col6:
            telefono_contacto = st.text_input("Teléfono *")
            lugar_imparticion = st.text_area("Lugar", height=60)

        st.markdown("#### ⏰ Horario Inicial")
        horario_nuevo = crear_selector_horario_fundae("modal")

        observaciones = st.text_area("Observaciones", height=80)

        col_submit, col_cancel = st.columns([2, 1])
        with col_submit:
            submitted = st.form_submit_button("✅ Crear Grupo", type="primary", use_container_width=True)
        with col_cancel:
            if st.form_submit_button("❌ Cancelar", use_container_width=True):
                st.rerun()

        if submitted:
            errores = []
            if not codigo_grupo: errores.append("El código de grupo es obligatorio")
            if not localidad_sel: errores.append("La localidad es obligatoria")
            if not responsable: errores.append("El responsable es obligatorio")
            if not telefono_contacto: errores.append("El teléfono de contacto es obligatorio")

            if errores:
                st.error("❌ Complete los campos obligatorios:")
                for e in errores: st.error(f"• {e}")
                return

            datos_crear = {
                "codigo_grupo": codigo_grupo,
                "accion_formativa_id": accion_id,
                "modalidad": modalidad_grupo,
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin_prevista": fecha_fin_prevista.isoformat() if fecha_fin_prevista else None,
                "provincia": provincia_sel,
                "localidad": localidad_sel,
                "cp": cp,
                "responsable": responsable,
                "telefono_contacto": telefono_contacto,
                "n_participantes_previstos": n_participantes_previstos,
                "lugar_imparticion": lugar_imparticion,
                "observaciones": observaciones,
                "horario": horario_nuevo if horario_nuevo else None
            }
            if grupos_service.rol == "gestor":
                datos_crear["empresa_id"] = grupos_service.empresa_id

            try:
                with st.spinner("Creando grupo..."):
                    exito, grupo_id = grupos_service.create_grupo_completo(datos_crear)
                if exito:
                    st.success(f"✅ Grupo '{codigo_grupo}' creado correctamente")
                    grupo_creado = grupos_service.supabase.table("grupos").select("*").eq("id", grupo_id).execute()
                    if grupo_creado.data:
                        st.session_state.grupo_seleccionado = grupo_creado.data[0]
                    st.rerun()
                else:
                    st.error("❌ Error al crear el grupo")
            except Exception as e:
                st.error(f"❌ Error: {e}")
# =========================
# FORMULARIO PRINCIPAL CREAR/EDITAR
# =========================

def mostrar_formulario_grupo(grupos_service, grupo_seleccionado=None, es_creacion=False):
    """Formulario unificado para crear/editar grupos FUNDAE."""
    acciones_dict = grupos_service.get_acciones_dict()
    if not acciones_dict:
        st.error("❌ No hay acciones formativas disponibles. Crea una acción primero.")
        return None

    if grupo_seleccionado:
        datos_grupo = grupo_seleccionado.copy()
        estado_actual = determinar_estado_grupo(datos_grupo)
    else:
        datos_grupo, estado_actual, es_creacion = {}, "ABIERTO", True

    if es_creacion:
        st.markdown("### ➕ Crear Nuevo Grupo")
    else:
        st.markdown(f"### ✏️ Editar Grupo: {datos_grupo.get('codigo_grupo', 'Sin código')}")
        st.info(f"Estado actual: {estado_actual}")

    # =====================
    # SECCIÓN 1: DATOS BÁSICOS FUNDAE
    # =====================
    with st.expander("📋 1. Datos Básicos FUNDAE", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            if es_creacion:
                codigo_grupo = st.text_input("Código del Grupo *", value=datos_grupo.get("codigo_grupo", ""), max_chars=50)
            else:
                codigo_grupo = datos_grupo.get("codigo_grupo", "")
                st.text_input("Código del Grupo", value=codigo_grupo, disabled=True)

            acciones_nombres = list(acciones_dict.keys())
            indice_actual = 0
            if grupo_seleccionado and datos_grupo.get("accion_formativa_id"):
                for nombre, id_accion in acciones_dict.items():
                    if id_accion == datos_grupo.get("accion_formativa_id"):
                        indice_actual = acciones_nombres.index(nombre)
                        break
            accion_formativa = st.selectbox("Acción Formativa *", acciones_nombres, index=indice_actual)

            accion_id = acciones_dict[accion_formativa]
            modalidad_grupo = grupos_service.normalizar_modalidad_fundae(grupos_service.get_accion_modalidad(accion_id))
            st.text_input("Modalidad", value=modalidad_grupo, disabled=True)

            fecha_inicio = st.date_input("Fecha de Inicio *", value=safe_date_conversion(datos_grupo.get("fecha_inicio")) or date.today())
            fecha_fin_prevista = st.date_input("Fecha Fin Prevista *", value=safe_date_conversion(datos_grupo.get("fecha_fin_prevista")))

        with col2:
            provincias = grupos_service.get_provincias()
            prov_opciones = {p["nombre"]: p["id"] for p in provincias}
            provincia_sel = st.selectbox("Provincia *", list(prov_opciones.keys()), index=list(prov_opciones.keys()).index(datos_grupo.get("provincia")) if datos_grupo.get("provincia") in prov_opciones else 0)
            localidades = grupos_service.get_localidades_por_provincia(prov_opciones[provincia_sel])
            localidad_sel = st.selectbox("Localidad *", [l["nombre"] for l in localidades], index=[l["nombre"] for l in localidades].index(datos_grupo.get("localidad")) if datos_grupo.get("localidad") in [l["nombre"] for l in localidades] else 0)

            cp = st.text_input("Código Postal", value=datos_grupo.get("cp", ""))
            responsable = st.text_input("Responsable *", value=datos_grupo.get("responsable", ""))
            telefono_contacto = st.text_input("Teléfono *", value=datos_grupo.get("telefono_contacto", ""))
            n_participantes_previstos = st.number_input("Participantes Previstos *", min_value=1, max_value=30, value=int(datos_grupo.get("n_participantes_previstos") or 8))

        lugar_imparticion = st.text_area("Lugar de Impartición", value=datos_grupo.get("lugar_imparticion", ""), height=60)
        observaciones = st.text_area("Observaciones", value=datos_grupo.get("observaciones", ""), height=80)

    # =====================
    # SECCIÓN 2: HORARIOS
    # =====================
    with st.expander("⏰ 2. Horarios de Impartición", expanded=True):
        horario_actual = datos_grupo.get("horario", "")
        if horario_actual and not es_creacion:
            st.info(f"**Horario actual**: `{horario_actual}`")
            if st.checkbox("Modificar horario"):
                horario_nuevo = crear_selector_horario_fundae("edit")
            else:
                horario_nuevo = horario_actual
        else:
            horario_nuevo = crear_selector_horario_fundae("new")

    # =====================
    # SECCIÓN 3: FINALIZACIÓN
    # =====================
    mostrar_finalizacion = not es_creacion and (estado_actual in ["FINALIZAR", "FINALIZADO"] or (fecha_fin_prevista and fecha_fin_prevista <= date.today()) or datos_grupo.get("_mostrar_finalizacion"))
    datos_finalizacion = {}
    if mostrar_finalizacion:
        with st.expander("🏁 3. Datos de Finalización", expanded=(estado_actual == "FINALIZAR")):
            fecha_fin_real = st.date_input("Fecha Fin Real *", value=safe_date_conversion(datos_grupo.get("fecha_fin")) or date.today())
            n_finalizados = st.number_input("Participantes Finalizados *", min_value=0, value=safe_int_conversion(datos_grupo.get("n_participantes_finalizados"), 0))
            n_aptos = st.number_input("Participantes Aptos *", min_value=0, value=safe_int_conversion(datos_grupo.get("n_aptos"), 0))
            n_no_aptos = st.number_input("Participantes No Aptos *", min_value=0, value=safe_int_conversion(datos_grupo.get("n_no_aptos"), 0))

            if n_finalizados > 0 and n_aptos + n_no_aptos != n_finalizados:
                st.error("⚠️ La suma de aptos y no aptos debe coincidir con finalizados")
            datos_finalizacion = {"fecha_fin": fecha_fin_real.isoformat(), "n_participantes_finalizados": n_finalizados, "n_aptos": n_aptos, "n_no_aptos": n_no_aptos}

    # =====================
    # BOTONES DE ACCIÓN
    # =====================
    if es_creacion:
        if st.button("➕ Crear Grupo", type="primary"):
            datos_crear = {"codigo_grupo": codigo_grupo, "accion_formativa_id": accion_id, "modalidad": modalidad_grupo, "fecha_inicio": fecha_inicio.isoformat(), "fecha_fin_prevista": fecha_fin_prevista.isoformat() if fecha_fin_prevista else None, "provincia": provincia_sel, "localidad": localidad_sel, "cp": cp, "responsable": responsable, "telefono_contacto": telefono_contacto, "n_participantes_previstos": n_participantes_previstos, "lugar_imparticion": lugar_imparticion, "observaciones": observaciones, "horario": horario_nuevo}
            if grupos_service.rol == "gestor": datos_crear["empresa_id"] = grupos_service.empresa_id
            errores = validar_campos_obligatorios_fundae(datos_crear)
            if errores: [st.error(e) for e in errores]
            else:
                try:
                    exito, grupo_id = grupos_service.create_grupo_completo(datos_crear)
                    if exito:
                        st.success(f"✅ Grupo '{codigo_grupo}' creado")
                        st.session_state.grupo_seleccionado = grupos_service.supabase.table("grupos").select("*").eq("id", grupo_id).execute().data[0]
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {e}")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("💾 Guardar Cambios", type="primary"):
                datos_actualizar = {"modalidad": modalidad_grupo, "fecha_inicio": fecha_inicio.isoformat(), "fecha_fin_prevista": fecha_fin_prevista.isoformat() if fecha_fin_prevista else None, "provincia": provincia_sel, "localidad": localidad_sel, "cp": cp, "responsable": responsable, "telefono_contacto": telefono_contacto, "n_participantes_previstos": n_participantes_previstos, "lugar_imparticion": lugar_imparticion, "observaciones": observaciones, "horario": horario_nuevo}
                if datos_finalizacion: datos_actualizar.update(datos_finalizacion)
                errores = validar_campos_obligatorios_fundae(datos_actualizar)
                if datos_finalizacion: errores.extend(validar_datos_finalizacion(datos_actualizar))
                if errores: [st.error(e) for e in errores]
                else:
                    if grupos_service.update_grupo(datos_grupo["id"], datos_actualizar):
                        st.success("✅ Cambios guardados")
                        st.session_state.grupo_seleccionado = grupos_service.supabase.table("grupos").select("*").eq("id", datos_grupo["id"]).execute().data[0]
                        st.rerun()
        with col2:
            if st.button("🔄 Recargar"):
                st.session_state.grupo_seleccionado = grupos_service.supabase.table("grupos").select("*").eq("id", datos_grupo["id"]).execute().data[0]
                st.rerun()
        with col3:
            if st.button("❌ Cancelar"):
                st.session_state.grupo_seleccionado = None
                st.rerun()

    return datos_grupo.get("id") if datos_grupo else None
# =========================
# SECCIONES ADICIONALES
# =========================

def mostrar_secciones_adicionales(grupos_service, grupo_id):
    """Muestra las secciones adicionales para grupos ya creados."""
    with st.expander("👨‍🏫 4. Tutores Asignados"):
        mostrar_seccion_tutores(grupos_service, grupo_id)
    with st.expander("🏢 4.b Centro Gestor"):
        mostrar_seccion_centro_gestor(grupos_service, grupo_id)
    with st.expander("🏢 5. Empresas Participantes"):
        mostrar_seccion_empresas(grupos_service, grupo_id)
    with st.expander("👥 6. Participantes del Grupo"):
        mostrar_seccion_participantes(grupos_service, grupo_id)
    with st.expander("💰 7. Costes y Bonificaciones FUNDAE"):
        mostrar_seccion_costes(grupos_service, grupo_id)

# --- Tutores ---
def mostrar_seccion_tutores(grupos_service, grupo_id):
    st.markdown("**Gestión de Tutores**")
    try:
        df_tutores = grupos_service.get_tutores_grupo(grupo_id)
        if not df_tutores.empty:
            for _, row in df_tutores.iterrows():
                tutor = row.get("tutor", {})
                if tutor:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{tutor.get('nombre','')} {tutor.get('apellidos','')}**")
                        st.caption(f"{tutor.get('email','')} | {tutor.get('especialidad','')}")
                    with col2:
                        if st.button("Quitar", key=f"quitar_tutor_{row['id']}"):
                            if grupos_service.delete_tutor_grupo(row["id"]): st.success("Tutor eliminado"); st.rerun()
        else:
            st.info("No hay tutores asignados")
        df_disp = grupos_service.get_tutores_completos()
        if not df_disp.empty:
            opciones = {f"{r['nombre']} {r['apellidos']} - {r.get('especialidad','')}": r["id"] for _, r in df_disp.iterrows()}
            seleccion = st.multiselect("Añadir tutores:", opciones.keys())
            if seleccion and st.button("Asignar Tutores"):
                for s in seleccion:
                    grupos_service.create_tutor_grupo(grupo_id, opciones[s])
                st.success("Tutores asignados"); st.rerun()
    except Exception as e:
        st.error(f"Error tutores: {e}")

# --- Centro Gestor ---
def mostrar_seccion_centro_gestor(grupos_service, grupo_id):
    try:
        info_mod = grupos_service.supabase.table("grupos").select("accion_formativa:acciones_formativas(modalidad)").eq("id", grupo_id).execute()
        modalidad = grupos_service.normalizar_modalidad_fundae(info_mod.data[0]["accion_formativa"]["modalidad"]) if info_mod.data else ""
        if modalidad in ["TELEFORMACION", "MIXTA"]:
            st.markdown("### Centro gestor en Teleformación")
            centro_actual = grupos_service.get_centro_gestor_grupo(grupo_id)
            if centro_actual: st.info(f"Centro actual: {centro_actual}")
            df_centros = grupos_service.get_centros_para_grupo(grupo_id)
            if not df_centros.empty:
                opciones = {row.get("razon_social") or row.get("cif"): row["id"] for _, row in df_centros.iterrows()}
                sel = st.selectbox("Seleccionar centro gestor", list(opciones.keys()))
                if st.button("Asignar centro gestor"): grupos_service.assign_centro_gestor_a_grupo(grupo_id, opciones[sel]); st.rerun()
                if centro_actual and st.button("❌ Desasignar centro gestor"): grupos_service.unassign_centro_gestor_de_grupo(grupo_id); st.rerun()
        else:
            st.info("Solo para modalidades Teleformación o Mixta")
    except Exception as e:
        st.error(f"Error centro gestor: {e}")

# --- Empresas ---
def mostrar_seccion_empresas(grupos_service, grupo_id):
    st.markdown("**Empresas Participantes**")
    try:
        df_empresas = grupos_service.get_empresas_grupo(grupo_id)
        if not df_empresas.empty:
            for _, row in df_empresas.iterrows():
                empresa = row.get("empresa", {})
                if empresa:
                    col1, col2 = st.columns([3, 1])
                    with col1: st.write(f"**{empresa.get('nombre','')}** CIF: {empresa.get('cif','')}")
                    with col2:
                        if grupos_service.rol == "admin" and st.button("Quitar", key=f"quitar_empresa_{row['id']}"):
                            grupos_service.delete_empresa_grupo(row["id"]); st.rerun()
        if grupos_service.rol == "admin":
            empresas_dict = grupos_service.get_empresas_dict()
            if empresas_dict:
                seleccion = st.multiselect("Añadir empresas:", list(empresas_dict.keys()))
                if seleccion and st.button("Asignar Empresas"):
                    for s in seleccion: grupos_service.create_empresa_grupo(grupo_id, empresas_dict[s])
                    st.success("Empresas asignadas"); st.rerun()
    except Exception as e:
        st.error(f"Error empresas: {e}")

# --- Participantes ---
def mostrar_seccion_participantes(grupos_service, grupo_id):
    st.markdown("**Participantes del Grupo**")
    try:
        df_participantes = grupos_service.get_participantes_grupo(grupo_id)
        if not df_participantes.empty:
            st.dataframe(df_participantes[["nif","nombre","apellidos","email"]], use_container_width=True)
        df_disp = grupos_service.get_participantes_disponibles(grupo_id)
        if not df_disp.empty:
            opciones = {f"{r['nif']} - {r['nombre']} {r['apellidos']}": r["id"] for _, r in df_disp.iterrows()}
            seleccion = st.multiselect("Añadir participantes:", opciones.keys())
            if seleccion and st.button("Asignar Participantes"):
                for s in seleccion: grupos_service.asignar_participante_a_grupo(opciones[s], grupo_id)
                st.success("Participantes asignados"); st.rerun()
    except Exception as e:
        st.error(f"Error participantes: {e}")

# --- Costes FUNDAE ---
def mostrar_seccion_costes(grupos_service, grupo_id):
    st.markdown("**Costes y Bonificaciones FUNDAE**")
    try:
        grupo_info = grupos_service.supabase.table("grupos").select("modalidad, n_participantes_previstos, accion_formativa:acciones_formativas(num_horas)").eq("id", grupo_id).execute()
        datos = grupo_info.data[0] if grupo_info.data else {}
        modalidad, participantes, horas = datos.get("modalidad",""), int(datos.get("n_participantes_previstos",1)), int(datos.get("accion_formativa",{}).get("num_horas",0))
        limite_boni, tarifa_max = grupos_service.calcular_limite_fundae(modalidad, horas, participantes)
        st.metric("Límite Bonificación", f"{limite_boni:,.2f} €")
        costes_actuales = grupos_service.get_grupo_costes(grupo_id)
        with st.form(f"costes_{grupo_id}"):
            c_dir = st.number_input("Costes Directos", value=float(costes_actuales.get("costes_directos",0)))
            c_ind = st.number_input("Costes Indirectos", value=float(costes_actuales.get("costes_indirectos",0)))
            total = c_dir+c_ind
            st.metric("Total Costes", f"{total:,.2f} €")
            if st.form_submit_button("Guardar Costes"):
                datos_costes = {"grupo_id": grupo_id, "costes_directos": c_dir, "costes_indirectos": c_ind, "total_costes_formacion": total}
                if costes_actuales: grupos_service.update_grupo_coste(grupo_id, datos_costes)
                else: grupos_service.create_grupo_coste(datos_costes)
                st.success("Costes guardados"); st.rerun()
    except Exception as e:
        st.error(f"Error costes: {e}")
# =========================
# FUNCIÓN PRINCIPAL
# =========================

def main(supabase, session_state):
    """Gestión de grupos FUNDAE."""
    st.title("👥 Gestión de Grupos FUNDAE")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder")
        return

    grupos_service = get_grupos_service(supabase, session_state)

    try:
        df_grupos = grupos_service.get_grupos_completos()
    except Exception as e:
        st.error(f"❌ Error al cargar grupos: {e}")
        return

    mostrar_kpis_grupos(df_grupos)
    mostrar_avisos_grupos(get_grupos_pendientes_finalizacion(df_grupos))

    if st.button("➕ Crear Nuevo Grupo", type="primary"):
        modal_crear_grupo(grupos_service)

    if not df_grupos.empty:
        df_display = df_grupos.copy()
        df_display["Estado"] = df_display.apply(lambda r: determinar_estado_grupo(r.to_dict()), axis=1)
        event = st.dataframe(df_display[["codigo_grupo","accion_nombre","modalidad","fecha_inicio","fecha_fin_prevista","localidad","n_participantes_previstos","Estado"]], use_container_width=True, selection_mode="single-row", on_select="rerun")
        if event.selection.rows:
            st.session_state.grupo_seleccionado = df_grupos.iloc[event.selection.rows[0]].to_dict()

    if hasattr(st.session_state, "grupo_seleccionado") and st.session_state.grupo_seleccionado:
        grupo_id = mostrar_formulario_grupo(grupos_service, st.session_state.grupo_seleccionado, es_creacion=(st.session_state.grupo_seleccionado=="nuevo"))
        if grupo_id:
            mostrar_secciones_adicionales(grupos_service, grupo_id)
