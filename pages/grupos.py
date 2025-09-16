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
# FUNCIONES AUXILIARES 
# =========================

def safe_int_conversion(value, default=0):
    """Convierte un valor a entero de forma segura, manejando NaN y None."""
    if value is None:
        return default
    if pd.isna(value):  # Maneja NaN de pandas
        return default
    if math.isnan(float(value)) if isinstance(value, (int, float)) else False:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default
        
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
    
    # Si tiene datos de finalización completos
    if all([fecha_fin_real, n_finalizados is not None, n_aptos is not None, n_no_aptos is not None]):
        return "FINALIZADO"
    
    # Si la fecha prevista ya pasó
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
    hoy = date.today()
    
    for _, grupo in df_grupos.iterrows():
        estado = determinar_estado_grupo(grupo.to_dict())
        if estado == "FINALIZAR":
            pendientes.append(grupo.to_dict())
    
    return pendientes

# =========================
# FUNCIONES DE HORARIOS FUNDAE
# =========================

def validar_horario_fundae(horario_str):
    """Valida que el horario cumpla con el formato FUNDAE."""
    if not horario_str:
        return False, "Horario requerido"
    
    # Debe contener días
    if "Días:" not in horario_str:
        return False, "Debe especificar días de la semana"
    
    # Debe contener al menos un tramo horario
    if not any(x in horario_str for x in ["Mañana:", "Tarde:"]):
        return False, "Debe especificar al menos un tramo horario"
    
    return True, ""

def construir_horario_fundae(manana_inicio, manana_fin, tarde_inicio, tarde_fin, dias_seleccionados):
    """Construye string de horario en formato FUNDAE."""
    partes = []
    
    # Tramo mañana
    if manana_inicio and manana_fin:
        partes.append(f"Mañana: {manana_inicio} - {manana_fin}")
    
    # Tramo tarde  
    if tarde_inicio and tarde_fin:
        partes.append(f"Tarde: {tarde_inicio} - {tarde_fin}")
    
    # Días
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
        # Separar por | y procesar cada parte
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

# =========================
# FUNCIONES DE VALIDACIÓN FUNDAE
# =========================

def validar_campos_obligatorios_fundae(datos):
    """Valida campos obligatorios para XML FUNDAE."""
    errores = []
    
    # Campos básicos obligatorios
    campos_requeridos = {
        "codigo_grupo": "Código de grupo",
        "accion_formativa_id": "Acción formativa", 
        "modalidad": "Modalidad",
        "fecha_inicio": "Fecha de inicio",
        "fecha_fin_prevista": "Fecha fin prevista",
        "localidad": "Localidad",
        "n_participantes_previstos": "Participantes previstos"
    }
    
    for campo, nombre in campos_requeridos.items():
        if not datos.get(campo):
            errores.append(f"{nombre} es obligatorio para FUNDAE")
    
    # Validaciones específicas
    modalidad = datos.get("modalidad")
    if modalidad and modalidad not in MODALIDADES_FUNDAE:
        errores.append("Modalidad debe ser PRESENCIAL, TELEFORMACION o MIXTA")
    
    # Participantes entre 1 y 30
    try:
        n_part = int(datos.get("n_participantes_previstos", 0))
        if n_part < 1 or n_part > 30:
            errores.append("Participantes previstos debe estar entre 1 y 30")
    except:
        errores.append("Participantes previstos debe ser un número")
    
    # Horario válido
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
        no_aptos = int(datos.get("n_no_apaptos", 0))
        
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
# COMPONENTES UI ESPECIALIZADOS
# =========================

def mostrar_kpis_grupos(df_grupos):
    """Muestra KPIs de grupos con estados automáticos."""
    if df_grupos.empty:
        st.info("📋 No hay grupos registrados.")
        return
    
    # Contar por estados
    total = len(df_grupos)
    abiertos = sum(1 for _, g in df_grupos.iterrows() if determinar_estado_grupo(g.to_dict()) == "ABIERTO")
    por_finalizar = sum(1 for _, g in df_grupos.iterrows() if determinar_estado_grupo(g.to_dict()) == "FINALIZAR") 
    finalizados = sum(1 for _, g in df_grupos.iterrows() if determinar_estado_grupo(g.to_dict()) == "FINALIZADO")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Total Grupos", total)
    with col2:
        st.metric("🟢 Abiertos", abiertos)
    with col3:
        if por_finalizar > 0:
            st.metric("🟡 Por Finalizar", por_finalizar, delta=f"+{por_finalizar}")
        else:
            st.metric("🟡 Por Finalizar", por_finalizar)
    with col4:
        st.metric("✅ Finalizados", finalizados)

def mostrar_avisos_grupos(grupos_pendientes):
    """Muestra avisos de grupos pendientes de finalización - CORREGIDO."""
    if not grupos_pendientes:
        return
    
    st.warning(f"⚠️ **{len(grupos_pendientes)} grupo(s) pendiente(s) de finalización**")
    
    with st.expander("Ver grupos pendientes", expanded=False):
        for grupo in grupos_pendientes[:5]:  # Mostrar máximo 5
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{grupo.get('codigo_grupo')}** - Fin previsto: {grupo.get('fecha_fin_prevista')}")
            with col2:
                # CORRECCIÓN: Implementar funcionalidad del botón finalizar
                if st.button("Finalizar", key=f"finalizar_{grupo.get('id')}", type="secondary"):
                    # Establecer el grupo para edición y forzar estado FINALIZAR
                    grupo_copy = grupo.copy()
                    # Asegurarse de que aparezca la sección de finalización
                    if not grupo_copy.get('fecha_fin'):
                        grupo_copy['_mostrar_finalizacion'] = True
                    st.session_state.grupo_seleccionado = grupo_copy
                    st.rerun()

def crear_selector_horario_fundae(prefix=""):
    """Crea un selector de horario compatible con FUNDAE - IMPLEMENTACIÓN COMPLETA."""
    st.markdown("#### Configuración de Horarios FUNDAE")
    st.caption("Intervalos de 15 minutos obligatorios según normativa FUNDAE")
    
    # Opción de configuración
    tipo_horario = st.radio(
        "Tipo de jornada:",
        ["Solo Mañana", "Solo Tarde", "Mañana y Tarde"],
        horizontal=True,
        key=f"{prefix}_tipo_horario"
    )
    
    col1, col2 = st.columns(2)
    
    manana_inicio = manana_fin = tarde_inicio = tarde_fin = None
    
    # Generar intervalos de tiempo correctamente
    intervalos_manana = []
    intervalos_tarde = []
    
    for h in range(6, 15):  # 06:00 a 14:45
        for m in [0, 15, 30, 45]:
            hora_str = f"{h:02d}:{m:02d}"
            intervalos_manana.append(hora_str)
    
    for h in range(15, 24):  # 15:00 a 23:45
        for m in [0, 15, 30, 45]:
            if h == 23 and m > 0:  # Máximo 23:00
                break
            hora_str = f"{h:02d}:{m:02d}"
            intervalos_tarde.append(hora_str)
    
    # Tramo mañana
    if tipo_horario in ["Solo Mañana", "Mañana y Tarde"]:
        with col1:
            st.markdown("**Tramo Mañana (06:00 - 15:00)**")
            
            sub_col1, sub_col2 = st.columns(2)
            with sub_col1:
                manana_inicio = st.selectbox(
                    "Hora inicio:",
                    intervalos_manana[:-1],  # Hasta 14:45
                    index=12,  # 09:00
                    key=f"{prefix}_manana_inicio"
                )
            with sub_col2:
                if manana_inicio:
                    # Filtrar horas fin que sean posteriores al inicio
                    idx_inicio = intervalos_manana.index(manana_inicio)
                    horas_fin_validas = intervalos_manana[idx_inicio + 1:]
                    
                    manana_fin = st.selectbox(
                        "Hora fin:",
                        horas_fin_validas,
                        index=min(15, len(horas_fin_validas)-1) if horas_fin_validas else 0,
                        key=f"{prefix}_manana_fin"
                    )
    
    # Tramo tarde
    if tipo_horario in ["Solo Tarde", "Mañana y Tarde"]:
        with col2:
            st.markdown("**Tramo Tarde (15:00 - 23:00)**")
            
            sub_col1, sub_col2 = st.columns(2)
            with sub_col1:
                tarde_inicio = st.selectbox(
                    "Hora inicio:",
                    intervalos_tarde[:-1],  # Hasta 22:45
                    index=0,  # 15:00
                    key=f"{prefix}_tarde_inicio"
                )
            with sub_col2:
                if tarde_inicio:
                    # Filtrar horas fin que sean posteriores al inicio
                    idx_inicio = intervalos_tarde.index(tarde_inicio)
                    horas_fin_validas = intervalos_tarde[idx_inicio + 1:]
                    
                    tarde_fin = st.selectbox(
                        "Hora fin:",
                        horas_fin_validas,
                        index=min(15, len(horas_fin_validas)-1) if horas_fin_validas else 0,
                        key=f"{prefix}_tarde_fin"
                    )
    
    # Días de la semana
    st.markdown("**Días de Impartición**")
    cols = st.columns(7)
    dias_seleccionados = []
    
    for i, (dia_corto, dia_largo) in enumerate(zip(DIAS_SEMANA, NOMBRES_DIAS)):
        with cols[i]:
            if st.checkbox(
                dia_largo,
                value=dia_corto in ["L", "M", "X", "J", "V"],  # L-V por defecto
                key=f"{prefix}_dia_{dia_corto}"
            ):
                dias_seleccionados.append(dia_corto)
    
    # Construir horario final
    horario_final = construir_horario_fundae(
        manana_inicio, manana_fin, tarde_inicio, tarde_fin, dias_seleccionados
    )
    
    if horario_final:
        st.success(f"Horario FUNDAE: {horario_final}")
        
        # Validar formato
        es_valido, error = validar_horario_fundae(horario_final)
        if not es_valido:
            st.error(f"Error: {error}")
    else:
        st.warning("Configure al menos un tramo horario y días")
    
    return horario_final

# =========================
# FORMULARIO PRINCIPAL UNIFICADO
# =========================

def mostrar_formulario_grupo(grupos_service, grupo_seleccionado=None, es_creacion=False):
    """Formulario unificado para crear/editar grupos - CORREGIDO."""
    
    # Obtener datos necesarios
    acciones_dict = grupos_service.get_acciones_dict()
    # CORRECCIÓN: Empresa solo para admin y solo en sección empresas, no en datos básicos
    
    if not acciones_dict:
        st.error("❌ No hay acciones formativas disponibles. Crea una acción formativa primero.")
        return None
    
    # Datos iniciales
    if grupo_seleccionado:
        datos_grupo = grupo_seleccionado.copy()
        estado_actual = determinar_estado_grupo(datos_grupo)
    else:
        datos_grupo = {}
        estado_actual = "ABIERTO"
        es_creacion = True
    
    # Título del formulario
    if es_creacion:
        st.markdown("### ➕ Crear Nuevo Grupo")
        st.caption("Complete los datos básicos obligatorios para crear el grupo")
    else:
        codigo = datos_grupo.get("codigo_grupo", "Sin código")
        st.markdown(f"### ✏️ Editar Grupo: {codigo}")
        
        # Mostrar estado actual
        color_estado = {"ABIERTO": "🟢", "FINALIZAR": "🟡", "FINALIZADO": "✅"}
        st.caption(f"Estado: {color_estado.get(estado_actual, '⚪')} {estado_actual}")
    
    # =====================
    # SECCIÓN 1: DATOS BÁSICOS FUNDAE (Siempre expandida)
    # =====================
    with st.expander("📋 1. Datos Básicos FUNDAE", expanded=True):
        st.markdown("**Información obligatoria para XML FUNDAE**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Código del grupo
            if es_creacion:
                codigo_grupo = st.text_input(
                    "Código del Grupo *",
                    value=datos_grupo.get("codigo_grupo", ""),
                    max_chars=50,
                    help="Código único identificativo del grupo (máximo 50 caracteres)",
                    key="form_codigo_grupo"
                )
            else:
                codigo_grupo = datos_grupo.get("codigo_grupo", "")
                st.text_input(
                    "Código del Grupo",
                    value=codigo_grupo,
                    disabled=True,
                    help="No se puede modificar después de la creación"
                )
            
            # Acción formativa
            acciones_nombres = list(acciones_dict.keys())
            if grupo_seleccionado and datos_grupo.get("accion_formativa_id"):
                # Buscar el nombre de la acción actual
                accion_actual = None
                for nombre, id_accion in acciones_dict.items():
                    if id_accion == datos_grupo.get("accion_formativa_id"):
                        accion_actual = nombre
                        break
                indice_actual = acciones_nombres.index(accion_actual) if accion_actual else 0
            else:
                indice_actual = 0
            
            accion_formativa = st.selectbox(
                "Acción Formativa *",
                acciones_nombres,
                index=indice_actual,
                help="Selecciona la acción formativa asociada",
                key="form_accion_formativa"
            )
            
            # Modalidad FUNDAE
            modalidad_actual = datos_grupo.get("modalidad", "PRESENCIAL")
            if modalidad_actual not in MODALIDADES_FUNDAE:
                modalidad_actual = "PRESENCIAL"
            
            modalidad = st.selectbox(
                "Modalidad *",
                list(MODALIDADES_FUNDAE.values()),
                index=list(MODALIDADES_FUNDAE.values()).index(modalidad_actual),
                help="Modalidad según estándares FUNDAE",
                key="form_modalidad"
            )
            
            # Fechas
            fecha_inicio = st.date_input(
                "Fecha de Inicio *",
                value=datetime.fromisoformat(datos_grupo["fecha_inicio"]).date() if datos_grupo.get("fecha_inicio") else date.today(),
                help="Fecha de inicio de la formación",
                key="form_fecha_inicio"
            )
            
            fecha_fin_prevista = st.date_input(
                "Fecha Fin Prevista *",
                value=datetime.fromisoformat(datos_grupo["fecha_fin_prevista"]).date() if datos_grupo.get("fecha_fin_prevista") else None,
                help="Fecha prevista de finalización",
                key="form_fecha_fin_prevista"
            )
        
        with col2:
            # Localidad (obligatorio FUNDAE)
            localidad = st.text_input(
                "Localidad *",
                value=datos_grupo.get("localidad", ""),
                help="Localidad de impartición (obligatorio FUNDAE)",
                key="form_localidad"
            )
            
            # Provincia y CP (opcionales)
            provincia = st.text_input(
                "Provincia",
                value=datos_grupo.get("provincia", ""),
                help="Provincia de impartición (opcional)",
                key="form_provincia"
            )
            
            cp = st.text_input(
                "Código Postal",
                value=datos_grupo.get("cp", ""),
                help="Código postal de impartición",
                key="form_cp"
            )
            
            # CORRECCIÓN: Manejar valores None y 0 correctamente
            n_participantes_actual = datos_grupo.get("n_participantes_previstos")
            if n_participantes_actual is None or n_participantes_actual == 0:
                n_participantes_actual = 8  # Valor por defecto válido
            
            n_participantes_previstos = st.number_input(
                "Participantes Previstos *",
                min_value=1,
                max_value=30,
                value=int(n_participantes_actual),
                help="Número de participantes previstos (1-30)",
                key="form_n_participantes"
            )
            
            # CORRECCIÓN: NO mostrar empresa en datos básicos
            # La empresa se gestionará en la sección de empresas participantes
        
        # Lugar de impartición
        lugar_imparticion = st.text_area(
            "Lugar de Impartición",
            value=datos_grupo.get("lugar_imparticion", ""),
            height=60,
            help="Descripción detallada del lugar donde se impartirá la formación",
            key="form_lugar_imparticion"
        )
        
        # Observaciones
        observaciones = st.text_area(
            "Observaciones",
            value=datos_grupo.get("observaciones", ""),
            height=80,
            help="Información adicional sobre el grupo (opcional)",
            key="form_observaciones"
        )
    
    # =====================
    # SECCIÓN 2: HORARIOS FUNDAE (Expandida por defecto)
    # =====================
    with st.expander("⏰ 2. Horarios de Impartición", expanded=True):
        # Cargar horario actual si existe
        horario_actual = datos_grupo.get("horario", "")
        
        if horario_actual and not es_creacion:
            st.info(f"**Horario actual**: {horario_actual}")
            
            # Opción para mantener o cambiar
            cambiar_horario = st.checkbox("Modificar horario", key="cambiar_horario")
            
            if cambiar_horario:
                # Parsear horario actual para prellenar campos
                m_ini, m_fin, t_ini, t_fin, dias = parsear_horario_fundae(horario_actual)
                horario_nuevo = crear_selector_horario_fundae("edit")
            else:
                horario_nuevo = horario_actual
        else:
            # Crear nuevo horario
            horario_nuevo = crear_selector_horario_fundae("new")
    
# =====================
# SECCIÓN 3: FINALIZACIÓN (Condicional)
# =====================
# CORRECCIÓN: Mejorar lógica de cuándo mostrar finalización
if mostrar_finalizacion:
    with st.expander("🏁 3. Datos de Finalización", expanded=(estado_actual == "FINALIZAR")):
        st.markdown("**Complete los datos de finalización para FUNDAE**")
        
        if estado_actual == "FINALIZAR":
            st.warning("⚠️ Este grupo ha superado su fecha prevista y necesita ser finalizado")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fecha_fin_real = st.date_input(
                "Fecha Fin Real *",
                value=datetime.fromisoformat(datos_grupo["fecha_fin"]).date() if datos_grupo.get("fecha_fin") else date.today(),
                help="Fecha real de finalización del grupo",
                key="form_fecha_fin_real"
            )
            
            # CORRECCIÓN: Manejo seguro de valores NaN
            n_finalizados_raw = datos_grupo.get("n_participantes_finalizados")
            n_finalizados_actual = safe_int_conversion(n_finalizados_raw, 0)
            
            n_finalizados = st.number_input(
                "Participantes Finalizados *",
                min_value=0,
                max_value=n_participantes_previstos,
                value=n_finalizados_actual,
                help="Número de participantes que finalizaron la formación",
                key="form_n_finalizados"
            )
        
        with col2:
            # CORRECCIÓN: Manejo seguro de valores NaN para aptos
            n_aptos_raw = datos_grupo.get("n_aptos")
            n_aptos_actual = safe_int_conversion(n_aptos_raw, 0)
            
            # CORRECCIÓN: Manejo seguro de valores NaN para no aptos  
            n_no_aptos_raw = datos_grupo.get("n_no_aptos")
            n_no_aptos_actual = safe_int_conversion(n_no_aptos_raw, 0)
            
            n_aptos = st.number_input(
                "Participantes Aptos *",
                min_value=0,
                max_value=n_finalizados if n_finalizados > 0 else n_participantes_previstos,
                value=n_aptos_actual,
                help="Número de participantes aptos",
                key="form_n_aptos"
            )
            
            n_no_aptos = st.number_input(
                "Participantes No Aptos *",
                min_value=0,
                max_value=n_finalizados if n_finalizados > 0 else n_participantes_previstos,
                value=n_no_aptos_actual,
                help="Número de participantes no aptos",
                key="form_n_no_aptos"
            )
        
        # Validación en tiempo real
        if n_finalizados > 0 and (n_aptos + n_no_aptos != n_finalizados):
            st.error(f"⚠️ La suma de aptos ({n_aptos}) + no aptos ({n_no_aptos}) debe ser igual a finalizados ({n_finalizados})")
        elif n_finalizados > 0:
            st.success("✅ Números de finalización coherentes")
        
        datos_finalizacion = {
            "fecha_fin": fecha_fin_real.isoformat(),
            "n_participantes_finalizados": n_finalizados,
            "n_aptos": n_aptos,
            "n_no_aptos": n_no_aptos
        }

    # =====================
    # BOTONES DE ACCIÓN
    # =====================
    st.divider()
    
    if es_creacion:
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("➕ Crear Grupo", type="primary", use_container_width=True):
                # Preparar datos para crear
                datos_crear = {
                    "codigo_grupo": codigo_grupo,
                    "accion_formativa_id": acciones_dict[accion_formativa],
                    "modalidad": modalidad,
                    "fecha_inicio": fecha_inicio.isoformat(),
                    "fecha_fin_prevista": fecha_fin_prevista.isoformat() if fecha_fin_prevista else None,
                    "localidad": localidad,
                    "provincia": provincia,
                    "cp": cp,
                    "n_participantes_previstos": n_participantes_previstos,
                    "lugar_imparticion": lugar_imparticion,
                    "observaciones": observaciones,
                    "horario": horario_nuevo if horario_nuevo else None
                }
                
                # CORRECCIÓN: Asignar empresa según rol automáticamente
                if grupos_service.rol == "gestor":
                    datos_crear["empresa_id"] = grupos_service.empresa_id
                # Para admin, se asignará la empresa en la sección empresas participantes
                
                # Validar datos obligatorios
                errores = validar_campos_obligatorios_fundae(datos_crear)
                
                if errores:
                    st.error("❌ Errores de validación:")
                    for error in errores:
                        st.error(f"• {error}")
                else:
                    # Crear grupo
                    try:
                        exito, grupo_id = grupos_service.create_grupo_completo(datos_crear)
                        if exito:
                            st.success(f"✅ Grupo '{codigo_grupo}' creado correctamente")
                            # CORRECCIÓN: Cargar el grupo recién creado para edición
                            grupo_creado = grupos_service.supabase.table("grupos").select("*").eq("id", grupo_id).execute()
                            if grupo_creado.data:
                                st.session_state.grupo_seleccionado = grupo_creado.data[0]
                                st.rerun()
                        else:
                            st.error("❌ Error al crear el grupo")
                    except Exception as e:
                        st.error(f"❌ Error al crear grupo: {e}")
        
        with col2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state.grupo_seleccionado = None
                st.rerun()
    
    else:
        # Botones para edición
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("💾 Guardar Cambios", type="primary", use_container_width=True):
                # Preparar datos para actualizar
                datos_actualizar = {
                    "modalidad": modalidad,
                    "fecha_inicio": fecha_inicio.isoformat(),
                    "fecha_fin_prevista": fecha_fin_prevista.isoformat() if fecha_fin_prevista else None,
                    "localidad": localidad,
                    "provincia": provincia,
                    "cp": cp,
                    "n_participantes_previstos": n_participantes_previstos,
                    "lugar_imparticion": lugar_imparticion,
                    "observaciones": observaciones,
                    "horario": horario_nuevo if horario_nuevo else None
                }
                
                # Agregar datos de finalización si están disponibles
                if datos_finalizacion:
                    datos_actualizar.update(datos_finalizacion)
                
                # Validar datos
                errores = validar_campos_obligatorios_fundae(datos_actualizar)
                if datos_finalizacion:
                    errores.extend(validar_datos_finalizacion(datos_actualizar))
                
                if errores:
                    st.error("❌ Errores de validación:")
                    for error in errores:
                        st.error(f"• {error}")
                else:
                    # Actualizar grupo
                    try:
                        if grupos_service.update_grupo(datos_grupo["id"], datos_actualizar):
                            st.success("✅ Cambios guardados correctamente")
                            # CORRECCIÓN: Recargar datos del grupo actualizado
                            grupo_actualizado = grupos_service.supabase.table("grupos").select("*").eq("id", datos_grupo["id"]).execute()
                            if grupo_actualizado.data:
                                st.session_state.grupo_seleccionado = grupo_actualizado.data[0]
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar cambios")
                    except Exception as e:
                        st.error(f"❌ Error al actualizar: {e}")
        
        with col2:
            if st.button("🔄 Recargar", use_container_width=True):
                # CORRECCIÓN: Recargar datos del grupo desde BD
                try:
                    grupo_recargado = grupos_service.supabase.table("grupos").select("*").eq("id", datos_grupo["id"]).execute()
                    if grupo_recargado.data:
                        st.session_state.grupo_seleccionado = grupo_recargado.data[0]
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al recargar: {e}")
        
        with col3:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state.grupo_seleccionado = None
                st.rerun()
    
    return datos_grupo.get("id") if datos_grupo else None

# CORRECCIÓN adicional para validar_datos_finalizacion
def validar_datos_finalizacion(datos):
    """Valida datos de finalización de grupo - CORREGIDO."""
    errores = []
    
    try:
        finalizados = int(datos.get("n_participantes_finalizados", 0))
        aptos = int(datos.get("n_aptos", 0))
        no_aptos = int(datos.get("n_no_aptos", 0))  # CORREGIDO: era n_no_apaptos
        
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
# SECCIONES ADICIONALES (Solo para grupos existentes)
# =========================

def mostrar_secciones_adicionales(grupos_service, grupo_id):
    """Muestra las secciones adicionales para grupos ya creados."""
    
    # SECCIÓN 4: TUTORES
    with st.expander("👨‍🏫 4. Tutores Asignados", expanded=False):
        mostrar_seccion_tutores(grupos_service, grupo_id)
    
    # SECCIÓN 5: EMPRESAS PARTICIPANTES  
    with st.expander("🏢 5. Empresas Participantes", expanded=False):
        mostrar_seccion_empresas(grupos_service, grupo_id)
    
    # SECCIÓN 6: PARTICIPANTES
    with st.expander("👥 6. Participantes del Grupo", expanded=False):
        mostrar_seccion_participantes(grupos_service, grupo_id)
    
    # SECCIÓN 7: COSTES FUNDAE
    with st.expander("💰 7. Costes y Bonificaciones FUNDAE", expanded=False):
        mostrar_seccion_costes(grupos_service, grupo_id)

def mostrar_seccion_tutores(grupos_service, grupo_id):
    """Gestión de tutores del grupo - CON MANEJO DE ERRORES."""
    st.markdown("**Gestión de Tutores**")
    
    try:
        # Tutores actuales
        df_tutores = grupos_service.get_tutores_grupo(grupo_id)
        
        if not df_tutores.empty:
            st.markdown("##### Tutores Asignados")
            for _, row in df_tutores.iterrows():
                tutor = row.get("tutor", {})
                if not tutor:  # Verificar que tutor no sea None
                    continue
                    
                col1, col2 = st.columns([3, 1])
                with col1:
                    nombre_completo = f"{tutor.get('nombre', '')} {tutor.get('apellidos', '')}"
                    st.write(f"**{nombre_completo.strip()}**")
                    st.caption(f"Email: {tutor.get('email', 'N/A')} | Especialidad: {tutor.get('especialidad', 'N/A')}")
                with col2:
                    if st.button("Quitar", key=f"quitar_tutor_{row.get('id')}", type="secondary"):
                        try:
                            if grupos_service.delete_tutor_grupo(row.get("id")):
                                st.success("Tutor eliminado")
                                st.rerun()
                            else:
                                st.error("Error al eliminar tutor")
                        except Exception as e:
                            st.error(f"Error: {e}")
        else:
            st.info("No hay tutores asignados")
        
        # Añadir tutores
        st.markdown("##### Añadir Tutores")
        try:
            df_tutores_disponibles = grupos_service.get_tutores_completos()
            
            if not df_tutores_disponibles.empty:
                # Filtrar tutores ya asignados
                tutores_asignados = set()
                for _, row in df_tutores.iterrows():
                    tutor = row.get("tutor", {})
                    if tutor and tutor.get("id"):
                        tutores_asignados.add(tutor.get("id"))
                
                df_disponibles = df_tutores_disponibles[
                    ~df_tutores_disponibles["id"].isin(tutores_asignados)
                ]
                
                if not df_disponibles.empty:
                    opciones_tutores = {}
                    for _, row in df_disponibles.iterrows():
                        nombre = row.get('nombre_completo', f"{row.get('nombre', '')} {row.get('apellidos', '')}")
                        especialidad = row.get('especialidad', 'Sin especialidad')
                        opciones_tutores[f"{nombre} - {especialidad}"] = row["id"]
                    
                    tutores_seleccionados = st.multiselect(
                        "Seleccionar tutores:",
                        opciones_tutores.keys(),
                        key=f"tutores_add_{grupo_id}"
                    )
                    
                    if tutores_seleccionados and st.button("Asignar Tutores", type="primary"):
                        exitos = 0
                        for tutor_nombre in tutores_seleccionados:
                            tutor_id = opciones_tutores[tutor_nombre]
                            try:
                                if grupos_service.create_tutor_grupo(grupo_id, tutor_id):
                                    exitos += 1
                            except Exception as e:
                                st.error(f"Error al asignar {tutor_nombre}: {e}")
                        
                        if exitos > 0:
                            st.success(f"Se asignaron {exitos} tutores")
                            st.rerun()
                else:
                    st.info("Todos los tutores disponibles ya están asignados")
            else:
                st.warning("No hay tutores disponibles en el sistema")
        except Exception as e:
            st.error(f"Error al cargar tutores disponibles: {e}")
            
    except Exception as e:
        st.error(f"Error al cargar sección de tutores: {e}")

def mostrar_seccion_empresas(grupos_service, grupo_id):
    """Gestión de empresas participantes - CON MANEJO DE ERRORES."""
    st.markdown("**Empresas Participantes**")
    
    if grupos_service.rol == "gestor":
        st.info("Como gestor, tu empresa está vinculada automáticamente al grupo")
    
    try:
        # Empresas actuales
        df_empresas = grupos_service.get_empresas_grupo(grupo_id)
        
        if not df_empresas.empty:
            st.markdown("##### Empresas Asignadas")
            for _, row in df_empresas.iterrows():
                empresa = row.get("empresa", {})
                if not empresa:  # Verificar que empresa no sea None
                    continue
                    
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{empresa.get('nombre', 'Sin nombre')}**")
                    cif = empresa.get('cif', 'Sin CIF')
                    fecha = row.get('fecha_asignacion', 'Sin fecha')
                    if isinstance(fecha, str) and len(fecha) > 10:
                        fecha = fecha[:10]  # Solo la fecha, sin hora
                    st.caption(f"CIF: {cif} | Fecha: {fecha}")
                with col2:
                    if grupos_service.rol == "admin" and st.button(
                        "Quitar", 
                        key=f"quitar_empresa_{row.get('id')}", 
                        type="secondary"
                    ):
                        try:
                            if grupos_service.delete_empresa_grupo(row.get("id")):
                                st.success("Empresa eliminada")
                                st.rerun()
                            else:
                                st.error("Error al eliminar empresa")
                        except Exception as e:
                            st.error(f"Error: {e}")
        else:
            st.info("No hay empresas asignadas")
        
        # Añadir empresas (solo admin)
        if grupos_service.rol == "admin":
            st.markdown("##### Añadir Empresas")
            try:
                empresas_dict = grupos_service.get_empresas_dict()
                
                if empresas_dict:
                    # Filtrar empresas ya asignadas
                    empresas_asignadas = set()
                    for _, row in df_empresas.iterrows():
                        empresa = row.get("empresa", {})
                        if empresa and empresa.get("nombre"):
                            empresas_asignadas.add(empresa.get("nombre"))
                    
                    empresas_disponibles = {
                        nombre: id_emp for nombre, id_emp in empresas_dict.items()
                        if nombre not in empresas_asignadas
                    }
                    
                    if empresas_disponibles:
                        empresas_seleccionadas = st.multiselect(
                            "Seleccionar empresas:",
                            empresas_disponibles.keys(),
                            key=f"empresas_add_{grupo_id}"
                        )
                        
                        if empresas_seleccionadas and st.button("Asignar Empresas", type="primary"):
                            exitos = 0
                            for empresa_nombre in empresas_seleccionadas:
                                empresa_id = empresas_disponibles[empresa_nombre]
                                try:
                                    if grupos_service.create_empresa_grupo(grupo_id, empresa_id):
                                        exitos += 1
                                except Exception as e:
                                    st.error(f"Error al asignar {empresa_nombre}: {e}")
                            
                            if exitos > 0:
                                st.success(f"Se asignaron {exitos} empresas")
                                st.rerun()
                    else:
                        st.info("Todas las empresas disponibles ya están asignadas")
                else:
                    st.warning("No hay empresas disponibles en el sistema")
            except Exception as e:
                st.error(f"Error al cargar empresas disponibles: {e}")
                
    except Exception as e:
        st.error(f"Error al cargar sección de empresas: {e}")

def mostrar_seccion_participantes(grupos_service, grupo_id):
    """Gestión de participantes del grupo - CON MANEJO DE ERRORES ROBUSTO."""
    st.markdown("**Participantes del Grupo**")
    
    try:
        # Participantes actuales
        df_participantes = grupos_service.get_participantes_grupo(grupo_id)
        
        if not df_participantes.empty:
            st.markdown("##### Participantes Asignados")
            
            # Verificar que las columnas existen
            columnas_mostrar = []
            columnas_disponibles = ["nif", "nombre", "apellidos", "email", "telefono"]
            for col in columnas_disponibles:
                if col in df_participantes.columns:
                    columnas_mostrar.append(col)
            
            if columnas_mostrar:
                st.dataframe(
                    df_participantes[columnas_mostrar],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("No se pueden mostrar los datos de participantes (columnas faltantes)")
            
            # Desasignar participantes
            with st.expander("Desasignar Participantes"):
                participantes_opciones = []
                for _, row in df_participantes.iterrows():
                    nif = row.get('nif', 'Sin NIF')
                    nombre = row.get('nombre', '')
                    apellidos = row.get('apellidos', '')
                    participantes_opciones.append(f"{nif} - {nombre} {apellidos}")
                
                if participantes_opciones:
                    participantes_quitar = st.multiselect(
                        "Seleccionar participantes a desasignar:",
                        participantes_opciones,
                        key=f"participantes_quitar_{grupo_id}"
                    )
                    
                    if participantes_quitar and st.button("Desasignar Seleccionados", type="secondary"):
                        exitos = 0
                        for participante_str in participantes_quitar:
                            try:
                                nif = participante_str.split(" - ")[0]
                                participante_row = df_participantes[df_participantes["nif"] == nif]
                                if not participante_row.empty:
                                    participante_id = participante_row.iloc[0]["id"]
                                    if grupos_service.desasignar_participante_de_grupo(participante_id):
                                        exitos += 1
                            except Exception as e:
                                st.error(f"Error al desasignar {participante_str}: {e}")
                        
                        if exitos > 0:
                            st.success(f"Se desasignaron {exitos} participantes")
                            st.rerun()
        else:
            st.info("No hay participantes asignados")
        
        # Asignar participantes
        st.markdown("##### Asignar Participantes")
        
        tab1, tab2 = st.tabs(["Individual", "Masivo (Excel)"])
        
        with tab1:
            try:
                df_disponibles = grupos_service.get_participantes_disponibles(grupo_id)
                
                if not df_disponibles.empty:
                    participantes_opciones = {}
                    for _, row in df_disponibles.iterrows():
                        nif = row.get('nif', 'Sin NIF')
                        nombre = row.get('nombre', '')
                        apellidos = row.get('apellidos', '')
                        participantes_opciones[f"{nif} - {nombre} {apellidos}"] = row["id"]
                    
                    participantes_seleccionados = st.multiselect(
                        "Seleccionar participantes:",
                        participantes_opciones.keys(),
                        key=f"participantes_add_{grupo_id}"
                    )
                    
                    if participantes_seleccionados and st.button("Asignar Seleccionados", type="primary"):
                        exitos = 0
                        for participante_str in participantes_seleccionados:
                            participante_id = participantes_opciones[participante_str]
                            try:
                                if grupos_service.asignar_participante_a_grupo(participante_id, grupo_id):
                                    exitos += 1
                            except Exception as e:
                                st.error(f"Error al asignar {participante_str}: {e}")
                        
                        if exitos > 0:
                            st.success(f"Se asignaron {exitos} participantes")
                            st.rerun()
                else:
                    st.info("No hay participantes disponibles")
            except Exception as e:
                st.error(f"Error al cargar participantes disponibles: {e}")
        
        with tab2:
            st.markdown("**Importación masiva desde Excel**")
            st.markdown("1. Sube un archivo Excel con una columna 'dni' o 'nif'")
            st.markdown("2. Se buscarán automáticamente en el sistema")
            
            archivo_excel = st.file_uploader(
                "Subir archivo Excel",
                type=["xlsx"],
                key=f"excel_participantes_{grupo_id}"
            )
            
            if archivo_excel:
                try:
                    df_import = pd.read_excel(archivo_excel)
                    
                    # Detectar columna de NIF
                    col_nif = None
                    for col in ["dni", "nif", "DNI", "NIF"]:
                        if col in df_import.columns:
                            col_nif = col
                            break
                    
                    if not col_nif:
                        st.error("El archivo debe contener una columna 'dni' o 'nif'")
                    else:
                        st.dataframe(df_import.head(), use_container_width=True)
                        
                        if st.button("Procesar Archivo", type="primary"):
                            try:
                                nifs = [str(d).strip() for d in df_import[col_nif] if pd.notna(d)]
                                nifs_validos = [d for d in nifs if validar_dni_cif(d)]
                                
                                df_disp_masivo = grupos_service.get_participantes_disponibles(grupo_id)
                                disponibles = {p["nif"]: p["id"] for _, p in df_disp_masivo.iterrows()}
                                
                                asignados = 0
                                errores = []
                                
                                for nif in nifs_validos:
                                    participante_id = disponibles.get(nif)
                                    if participante_id:
                                        try:
                                            if grupos_service.asignar_participante_a_grupo(participante_id, grupo_id):
                                                asignados += 1
                                        except Exception as e:
                                            errores.append(f"NIF {nif}: {str(e)}")
                                    else:
                                        errores.append(f"NIF {nif} no encontrado o ya asignado")
                                
                                if asignados > 0:
                                    st.success(f"Se asignaron {asignados} participantes")
                                if errores:
                                    st.warning("Errores encontrados:")
                                    for error in errores[:10]:  # Mostrar máximo 10 errores
                                        st.warning(f"• {error}")
                                
                                if asignados > 0:
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error al procesar datos: {e}")
                
                except Exception as e:
                    st.error(f"Error al leer archivo Excel: {e}")
                    
    except Exception as e:
        st.error(f"Error al cargar sección de participantes: {e}")

def mostrar_seccion_costes(grupos_service, grupo_id):
    """Gestión de costes y bonificaciones FUNDAE - CON VALIDACIONES ROBUSTAS."""
    st.markdown("**Costes y Bonificaciones FUNDAE**")
    
    # Obtener datos del grupo para cálculos
    try:
        # Consulta más robusta con manejo de errores
        grupo_info = grupos_service.supabase.table("grupos").select("""
            modalidad, n_participantes_previstos,
            accion_formativa:acciones_formativas(num_horas)
        """).eq("id", grupo_id).execute()
        
        if not grupo_info.data:
            st.error("No se pudo cargar información del grupo")
            return
            
        datos_grupo = grupo_info.data[0]
        modalidad = datos_grupo.get("modalidad", "PRESENCIAL")
        
        # Validar participantes
        participantes_raw = datos_grupo.get("n_participantes_previstos")
        if participantes_raw is None or participantes_raw == 0:
            participantes = 1  # Valor mínimo por defecto
            st.warning("Número de participantes no definido, usando valor por defecto: 1")
        else:
            participantes = int(participantes_raw)
        
        # Validar horas de la acción formativa
        accion_formativa = datos_grupo.get("accion_formativa")
        if accion_formativa and accion_formativa.get("num_horas"):
            horas = int(accion_formativa.get("num_horas", 0))
        else:
            horas = 0
            st.warning("Horas de la acción formativa no definidas")
            
    except Exception as e:
        st.error(f"Error al cargar datos del grupo: {e}")
        return
    
    # Calcular límite FUNDAE solo si tenemos datos válidos
    if horas > 0 and participantes > 0:
        try:
            limite_boni, tarifa_max = grupos_service.calcular_limite_fundae(modalidad, horas, participantes)
        except Exception as e:
            st.error(f"Error al calcular límites FUNDAE: {e}")
            limite_boni, tarifa_max = 0, 13.0  # Valores por defecto
    else:
        limite_boni, tarifa_max = 0, 13.0
        st.warning("No se pueden calcular límites FUNDAE sin horas y participantes válidos")
    
    # Mostrar información base
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Modalidad", modalidad)
    with col2:
        st.metric("Participantes", participantes)
    with col3:
        st.metric("Horas", horas)
    with col4:
        st.metric("Límite Bonificación", f"{limite_boni:,.2f} €")
    
    # Formulario de costes
    try:
        costes_actuales = grupos_service.get_grupo_costes(grupo_id)
    except Exception as e:
        st.error(f"Error al cargar costes actuales: {e}")
        costes_actuales = {}
    
    with st.form(f"costes_{grupo_id}"):
        st.markdown("##### Costes de Formación")
        
        col1, col2 = st.columns(2)
        
        with col1:
            costes_directos = st.number_input(
                "Costes Directos (€)",
                value=float(costes_actuales.get("costes_directos", 0)),
                min_value=0.0,
                key=f"directos_{grupo_id}"
            )
            
            costes_indirectos = st.number_input(
                "Costes Indirectos (€)",
                value=float(costes_actuales.get("costes_indirectos", 0)),
                min_value=0.0,
                help="Máximo 30% de costes directos",
                key=f"indirectos_{grupo_id}"
            )
            
            costes_organizacion = st.number_input(
                "Costes Organización (€)",
                value=float(costes_actuales.get("costes_organizacion", 0)),
                min_value=0.0,
                key=f"organizacion_{grupo_id}"
            )
        
        with col2:
            costes_salariales = st.number_input(
                "Costes Salariales (€)",
                value=float(costes_actuales.get("costes_salariales", 0)),
                min_value=0.0,
                key=f"salariales_{grupo_id}"
            )
            
            cofinanciacion_privada = st.number_input(
                "Cofinanciación Privada (€)",
                value=float(costes_actuales.get("cofinanciacion_privada", 0)),
                min_value=0.0,
                key=f"cofinanciacion_{grupo_id}"
            )
            
            tarifa_hora = st.number_input(
                "Tarifa por Hora (€)",
                value=float(costes_actuales.get("tarifa_hora", tarifa_max)),
                min_value=0.0,
                max_value=tarifa_max,
                help=f"Máximo FUNDAE: {tarifa_max} €/h",
                key=f"tarifa_{grupo_id}"
            )
        
        # Validaciones
        total_costes = costes_directos + costes_indirectos + costes_organizacion + costes_salariales
        limite_calculado = tarifa_hora * horas * participantes
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Costes", f"{total_costes:,.2f} €")
        with col2:
            st.metric("Límite Calculado", f"{limite_calculado:,.2f} €")
        
        # Validar porcentaje indirectos
        if costes_directos > 0:
            pct_indirectos = (costes_indirectos / costes_directos) * 100
            if pct_indirectos > 30:
                st.error(f"Costes indirectos ({pct_indirectos:.1f}%) superan el 30% permitido")
            else:
                st.success(f"Costes indirectos dentro del límite ({pct_indirectos:.1f}%)")
        
        observaciones_costes = st.text_area(
            "Observaciones",
            value=costes_actuales.get("observaciones", ""),
            key=f"obs_costes_{grupo_id}"
        )
        
        if st.form_submit_button("Guardar Costes", type="primary"):
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
                "observaciones": observaciones_costes
            }
            
            # Validar antes de guardar
            if costes_directos > 0 and (costes_indirectos / costes_directos) > 0.3:
                st.error("No se puede guardar: costes indirectos superan el 30%")
            elif tarifa_hora > tarifa_max:
                st.error(f"No se puede guardar: tarifa/hora supera el máximo ({tarifa_max} €)")
            else:
                try:
                    if costes_actuales:
                        exito = grupos_service.update_grupo_coste(grupo_id, datos_costes)
                    else:
                        exito = grupos_service.create_grupo_coste(datos_costes)
                    
                    if exito:
                        st.success("Costes guardados correctamente")
                        st.rerun()
                    else:
                        st.error("Error al guardar costes")
                except Exception as e:
                    st.error(f"Error: {e}")

# =========================
# FUNCIÓN PRINCIPAL
# =========================

def main(supabase, session_state):
    """Función principal de gestión de grupos."""
    st.title("👥 Gestión de Grupos FUNDAE")
    st.caption("Creación y administración de grupos formativos según estándares FUNDAE")
    
    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección")
        return
    
    # Inicializar servicio
    grupos_service = get_grupos_service(supabase, session_state)
    
    # Cargar datos
    try:
        df_grupos = grupos_service.get_grupos_completos()
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return
    
    # Mostrar KPIs
    mostrar_kpis_grupos(df_grupos)
    
    # Mostrar avisos de grupos pendientes
    grupos_pendientes = get_grupos_pendientes_finalizacion(df_grupos)
    mostrar_avisos_grupos(grupos_pendientes)
    
    st.divider()
    
    # Tabla principal de grupos
    st.markdown("### 📊 Listado de Grupos")
    
    if df_grupos.empty:
        st.info("📋 No hay grupos registrados. Crea tu primer grupo.")
    else:
        # Preparar datos para mostrar
        df_display = df_grupos.copy()
        
        # Añadir columna de estado
        df_display["Estado"] = df_display.apply(lambda row: determinar_estado_grupo(row.to_dict()), axis=1)
        
        # Seleccionar columnas para mostrar
        columnas_mostrar = ["codigo_grupo", "accion_nombre", "modalidad", "fecha_inicio", "fecha_fin_prevista", "localidad", "n_participantes_previstos", "Estado"]
        columnas_disponibles = [col for col in columnas_mostrar if col in df_display.columns]
        
        # Mostrar tabla
        event = st.dataframe(
            df_display[columnas_disponibles],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Procesar selección
        if event.selection.rows:
            selected_idx = event.selection.rows[0]
            grupo_seleccionado = df_grupos.iloc[selected_idx].to_dict()
            st.session_state.grupo_seleccionado = grupo_seleccionado
    
    st.divider()
    
    # Botón para crear nuevo grupo
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("➕ Crear Nuevo Grupo", type="primary", use_container_width=True):
            st.session_state.grupo_seleccionado = "nuevo"
    
    # Mostrar formulario según estado
    if hasattr(st.session_state, 'grupo_seleccionado'):
        if st.session_state.grupo_seleccionado == "nuevo":
            # Mostrar formulario de creación
            mostrar_formulario_grupo(grupos_service, es_creacion=True)
        elif st.session_state.grupo_seleccionado:
            # Mostrar formulario de edición
            grupo_id = mostrar_formulario_grupo(grupos_service, st.session_state.grupo_seleccionado)
            
            # Mostrar secciones adicionales si el grupo existe
            if grupo_id:
                st.divider()
                mostrar_secciones_adicionales(grupos_service, grupo_id)
