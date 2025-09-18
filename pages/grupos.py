import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from services.grupos_service import get_grupos_service
from utils import validar_dni_cif, export_csv
import re
import math

# =========================
# CONFIGURACIÓN Y CONSTANTES (del código original)
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

# Estados con iconos mejorados
ESTADOS_GRUPO_ICONOS = {
    "ABIERTO": "🟢 Abierto",
    "FINALIZAR": "🟡 Pendiente Finalizar", 
    "FINALIZADO": "✅ Finalizado"
}

# =========================
# FUNCIONES AUXILIARES (del código original)
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
# FUNCIONES DE ESTADO (mejoradas)
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
# FUNCIONES DE VALIDACIÓN FUNDAE (del código original)
# =========================

def validar_campos_obligatorios_fundae(datos):
    """Valida campos obligatorios para XML FUNDAE."""
    errores = []
    
    # Campos básicos obligatorios
    campos_requeridos = {
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
# FUNCIONES DE HORARIOS FUNDAE (del código original)
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
# COMPONENTES UI MEJORADOS - MODERNOS
# =========================

def mostrar_kpis_grupos_modernos(df_grupos):
    """
    Muestra KPIs de grupos con métricas modernas y deltas visuales.
    🎨 Mejora: st.metric() con deltas coloridas y ayuda contextual
    """
    if df_grupos.empty:
        st.info("📋 No hay grupos registrados.")
        return
    
    # Calcular métricas por estados
    total = len(df_grupos)
    abiertos = sum(1 for _, g in df_grupos.iterrows() if determinar_estado_grupo(g.to_dict()) == "ABIERTO")
    por_finalizar = sum(1 for _, g in df_grupos.iterrows() if determinar_estado_grupo(g.to_dict()) == "FINALIZAR") 
    finalizados = sum(1 for _, g in df_grupos.iterrows() if determinar_estado_grupo(g.to_dict()) == "FINALIZADO")
    
    # Layout de métricas con deltas visuales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "📊 Total Grupos", 
            total,
            help="Número total de grupos en el sistema"
        )
    
    with col2:
        # Porcentaje de abiertos con delta verde
        porcentaje_abiertos = (abiertos/total*100) if total > 0 else 0
        st.metric(
            "🟢 Abiertos", 
            abiertos,
            delta=f"{porcentaje_abiertos:.1f}%",
            delta_color="normal",
            help="Grupos activos en formación"
        )
    
    with col3:
        # Alerta visual si hay grupos por finalizar
        if por_finalizar > 0:
            st.metric(
                "🟡 Por Finalizar", 
                por_finalizar,
                delta=f"¡{por_finalizar} pendientes!",
                delta_color="inverse",
                help="⚠️ Grupos que necesitan finalización urgente"
            )
        else:
            st.metric(
                "🟡 Por Finalizar", 
                por_finalizar,
                delta="✅ Todo al día",
                delta_color="normal",
                help="No hay grupos pendientes de finalización"
            )
    
    with col4:
        # Porcentaje de finalizados
        porcentaje_finalizados = (finalizados/total*100) if total > 0 else 0
        st.metric(
            "✅ Finalizados", 
            finalizados,
            delta=f"{porcentaje_finalizados:.1f}%",
            delta_color="normal",
            help="Grupos completados exitosamente"
        )

def mostrar_avisos_grupos_expandible(grupos_pendientes):
    """
    Muestra avisos de grupos pendientes con alertas expandibles mejoradas.
    🎨 Mejora: Alertas con iconos, expandibles y acciones rápidas
    """
    if not grupos_pendientes:
        return
    
    # Alerta crítica para grupos por finalizar
    st.error(f"🚨 **URGENTE**: {len(grupos_pendientes)} grupos necesitan finalización")
    
    with st.expander(f"Ver {len(grupos_pendientes)} grupos por finalizar", expanded=True):
        for grupo in grupos_pendientes[:5]:  # Mostrar máximo 5
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.write(f"**{grupo.get('codigo_grupo', 'N/A')}**")
                if grupo.get('accion_nombre'):
                    st.caption(grupo['accion_nombre'])
            
            with col2:
                fecha_fin = grupo.get('fecha_fin_prevista', 'N/A')
                st.write(f"📅 Fin: {fecha_fin}")
            
            with col3:
                # Botón acción rápida
                if st.button(f"✏️ Finalizar", key=f"finalizar_{grupo.get('id', 'unknown')}", help="Ir a finalización del grupo"):
                    # Establecer el grupo para edición y forzar estado FINALIZAR
                    grupo_copy = grupo.copy()
                    # Asegurarse de que aparezca la sección de finalización
                    if not grupo_copy.get('fecha_fin'):
                        grupo_copy['_mostrar_finalizacion'] = True
                    st.session_state.grupo_seleccionado = grupo_copy
                    st.rerun()
        
        if len(grupos_pendientes) > 5:
            st.info(f"... y {len(grupos_pendientes) - 5} grupos más")

# =========================
# MODAL CREAR GRUPO - @st.dialog() MODERNO
# =========================

@st.dialog("➕ Crear Nuevo Grupo")
def modal_crear_grupo_moderno(grupos_service):
    """
    Modal moderno para crear grupo con validaciones en tiempo real.
    🎨 Mejora: Modal nativo de Streamlit con UX optimizada
    """
    st.markdown("### 📋 Datos básicos del grupo")
    
    # Obtener datos necesarios
    acciones_dict = grupos_service.get_acciones_dict()
    if not acciones_dict:
        st.error("❌ No hay acciones formativas disponibles. Crea una acción formativa primero.")
        return
    
    # Inicializar datos del formulario en session_state
    if "nuevo_grupo_data" not in st.session_state:
        st.session_state.nuevo_grupo_data = {
            "codigo_grupo": "",
            "fecha_inicio": date.today(),
            "fecha_fin_prevista": None,
            "n_participantes_previstos": 8,
            "localidad": "",
            "provincia": "",
            "cp": "",
            "lugar_imparticion": "",
            "responsable": "",
            "telefono_contacto": "",
            "observaciones": ""
        }
    
    datos = st.session_state.nuevo_grupo_data
    
    # === SECCIÓN 1: IDENTIFICACIÓN ===
    with st.container():
        st.markdown("#### 🏷️ Identificación")
        
        col1, col2 = st.columns(2)
        
        with col1:
            datos["codigo_grupo"] = st.text_input(
                "Código de grupo *",
                value=datos["codigo_grupo"],
                placeholder="GR2025001",
                help="Código único identificativo (máx. 50 caracteres)",
                max_chars=50,
                key="modal_codigo_grupo"
            )
        
        with col2:
            # Select de acción formativa
            acciones_nombres = list(acciones_dict.keys())
            
            # Mantener selección anterior si existe
            indice_seleccionado = 0
            if datos.get("accion_sel") in acciones_nombres:
                indice_seleccionado = acciones_nombres.index(datos["accion_sel"])
            
            accion_seleccionada = st.selectbox(
                "Acción formativa *",
                options=[""] + acciones_nombres,
                index=indice_seleccionado,
                help="Selecciona la acción formativa que se impartirá",
                key="modal_accion_formativa"
            )
            
            if accion_seleccionada:
                datos["accion_sel"] = accion_seleccionada
                datos["accion_formativa_id"] = acciones_dict[accion_seleccionada]
                
                # Obtener modalidad automáticamente
                accion_id = acciones_dict[accion_seleccionada]
                modalidad_raw = grupos_service.get_accion_modalidad(accion_id)
                modalidad_fundae = grupos_service.normalizar_modalidad_fundae(modalidad_raw)
                datos["modalidad"] = modalidad_fundae
                
                # Mostrar modalidad
                st.text_input(
                    "Modalidad (automática)",
                    value=modalidad_fundae,
                    disabled=True,
                    help="Modalidad tomada de la acción formativa"
                )
    
    # === SECCIÓN 2: UBICACIÓN Y FECHAS ===
    with st.container():
        st.markdown("#### 🌐 Ubicación y planificación")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Obtener provincias y localidades usando el servicio existente
            provincias = grupos_service.get_provincias()
            prov_opciones = {p["nombre"]: p["id"] for p in provincias}
            
            provincia_sel = st.selectbox(
                "Provincia *",
                options=list(prov_opciones.keys()),
                help="Provincia de impartición (obligatorio FUNDAE)",
                key="modal_provincia"
            )
            datos["provincia"] = provincia_sel
            
            localidades = grupos_service.get_localidades_por_provincia(prov_opciones[provincia_sel])
            loc_nombres = [l["nombre"] for l in localidades]
            
            if loc_nombres:
                localidad_sel = st.selectbox(
                    "Localidad *",
                    options=loc_nombres,
                    help="Localidad de impartición (obligatorio FUNDAE)",
                    key="modal_localidad"
                )
                datos["localidad"] = localidad_sel
            else:
                st.warning("No hay localidades para esta provincia")
        
        with col2:
            datos["fecha_inicio"] = st.date_input(
                "Fecha inicio *",
                value=datos["fecha_inicio"],
                help="Fecha de inicio de la formación",
                key="modal_fecha_inicio"
            )
            
            datos["cp"] = st.text_input(
                "Código postal",
                value=datos["cp"],
                placeholder="28001",
                max_chars=5,
                key="modal_cp"
            )
        
        with col3:
            datos["fecha_fin_prevista"] = st.date_input(
                "Fecha fin prevista *",
                value=datos["fecha_fin_prevista"],
                help="Fecha prevista de finalización",
                key="modal_fecha_fin_prevista"
            )
            
            datos["n_participantes_previstos"] = st.number_input(
                "Participantes previstos *",
                min_value=1,
                max_value=30,
                value=datos["n_participantes_previstos"],
                help="Número de participantes previstos (1-30 según FUNDAE)",
                key="modal_participantes"
            )
    
    # === SECCIÓN 3: CONTACTO ===
    col1, col2 = st.columns(2)
    
    with col1:
        datos["responsable"] = st.text_input(
            "Responsable del Grupo *",
            value=datos["responsable"],
            help="Persona responsable del grupo (obligatorio FUNDAE)",
            key="modal_responsable"
        )
    
    with col2:
        datos["telefono_contacto"] = st.text_input(
            "Teléfono de Contacto *",
            value=datos["telefono_contacto"],
            help="Teléfono de contacto del responsable (obligatorio FUNDAE)",
            key="modal_telefono"
        )
    
    # === SECCIÓN 4: DETALLES OPCIONALES ===
    datos["lugar_imparticion"] = st.text_area(
        "Lugar de Impartición",
        value=datos["lugar_imparticion"],
        placeholder="Descripción detallada del lugar...",
        height=60,
        help="Descripción detallada del lugar donde se impartirá la formación",
        key="modal_lugar"
    )
    
    datos["observaciones"] = st.text_area(
        "Observaciones",
        value=datos["observaciones"],
        placeholder="Información adicional sobre el grupo...",
        height=80,
        help="Información adicional opcional",
        key="modal_observaciones"
    )
    
    # === VALIDACIÓN EN TIEMPO REAL ===
    errores = validar_campos_obligatorios_fundae(datos)
    
    # Validaciones adicionales del modal
    if not datos.get("codigo_grupo"):
        errores.append("Código de grupo es obligatorio")
    if not accion_seleccionada:
        errores.append("Acción formativa es obligatoria")
    if not datos.get("responsable"):
        errores.append("Responsable es obligatorio")
    if not datos.get("telefono_contacto"):
        errores.append("Teléfono de contacto es obligatorio")
    
    if errores:
        st.error("❌ Errores de validación:")
        for error in errores:
            st.write(f"• {error}")
    
    # === BOTONES DE ACCIÓN ===
    st.divider()
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("❌ Cancelar", use_container_width=True):
            # Limpiar datos del modal
            if "nuevo_grupo_data" in st.session_state:
                del st.session_state.nuevo_grupo_data
            st.rerun()
    
    with col2:
        # Botón limpiar formulario
        if st.button("🔄 Limpiar", use_container_width=True, help="Resetear formulario"):
            st.session_state.nuevo_grupo_data = {
                "codigo_grupo": "",
                "fecha_inicio": date.today(),
                "fecha_fin_prevista": None,
                "n_participantes_previstos": 8,
                "localidad": "",
                "provincia": "",
                "cp": "",
                "lugar_imparticion": "",
                "responsable": "",
                "telefono_contacto": "",
                "observaciones": ""
            }
            st.rerun()
    
    with col3:
        # Botón crear grupo
        btn_crear = st.button(
            "✅ Crear Grupo",
            use_container_width=True,
            disabled=len(errores) > 0,
            type="primary",
            help="Crear grupo con los datos introducidos" if not errores else "Corrige los errores antes de continuar"
        )
        
        if btn_crear and not errores:
            with st.spinner("Creando grupo..."):
                try:
                    # Preparar datos para crear usando la estructura existente
                    datos_crear = {
                        "codigo_grupo": datos["codigo_grupo"],
                        "accion_formativa_id": datos["accion_formativa_id"],
                        "modalidad": datos["modalidad"],
                        "fecha_inicio": datos["fecha_inicio"].isoformat(),
                        "fecha_fin_prevista": datos["fecha_fin_prevista"].isoformat() if datos["fecha_fin_prevista"] else None,
                        "provincia": datos["provincia"],
                        "localidad": datos["localidad"],
                        "cp": datos["cp"],
                        "responsable": datos["responsable"],
                        "telefono_contacto": datos["telefono_contacto"],
                        "n_participantes_previstos": datos["n_participantes_previstos"],
                        "lugar_imparticion": datos["lugar_imparticion"],
                        "observaciones": datos["observaciones"]
                    }
                    
                    # Asignar empresa según rol automáticamente
                    if grupos_service.rol == "gestor":
                        datos_crear["empresa_id"] = grupos_service.empresa_id
                    
                    # Crear grupo usando el servicio existente
                    exito, grupo_id = grupos_service.create_grupo_completo(datos_crear)
                    
                    if exito:
                        st.success("✅ Grupo creado correctamente!")
                        st.balloons()  # 🎨 Efecto visual de éxito
                        
                        # Cargar el grupo recién creado para edición
                        grupo_creado = grupos_service.supabase.table("grupos").select("*").eq("id", grupo_id).execute()
                        if grupo_creado.data:
                            st.session_state.grupo_seleccionado = grupo_creado.data[0]
                        
                        # Limpiar modal
                        if "nuevo_grupo_data" in st.session_state:
                            del st.session_state.nuevo_grupo_data
                        
                        # Recargar página principal
                        st.rerun()
                    else:
                        st.error("❌ Error al crear el grupo")
                
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

def crear_selector_horario_fundae_modal(prefix="modal"):
    """
    Crea un selector de horario compatible con FUNDAE para modal.
    Basado en la función existente del código original.
    """
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
    
    # Generar intervalos de tiempo
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

def crear_filtros_grupos_mejorados():
    """
    Crea filtros mejorados para la tabla de grupos.
    🎨 Mejora: Filtros más intuitivos con placeholders y ayuda
    
    Returns:
        Tuple[str, str]: (filtro_texto, filtro_estado)
    """
    col1, col2 = st.columns([2, 1])
    
    with col1:
        filtro_texto = st.text_input(
            "🔍 Buscar grupos",
            placeholder="Código grupo, acción formativa, localidad...",
            help="Busca por código, nombre de acción, localidad o cualquier texto",
            key="filtro_texto_grupos"
        )
    
    with col2:
        filtro_estado = st.selectbox(
            "📊 Estado",
            options=["Todos", "🟢 Abiertos", "🟡 Por Finalizar", "✅ Finalizados"],
            help="Filtrar grupos por su estado actual",
            key="filtro_estado_grupos"
        )
    
    return filtro_texto, filtro_estado

# =========================
# FUNCIÓN CREAR SELECTOR DE HORARIO (del código original)
# =========================

def crear_selector_horario_fundae(prefix=""):
    """Crea un selector de horario compatible con FUNDAE - del código original."""
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
                            st.balloons()  # Efecto visual de éxito
                            
                            # Cargar el grupo recién creado para edición
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
                    "modalidad": modalidad_grupo,
                    "fecha_inicio": fecha_inicio.isoformat(),
                    "fecha_fin_prevista": fecha_fin_prevista.isoformat() if fecha_fin_prevista else None,
                    "provincia": provincia,
                    "localidad": localidad,
                    "cp": cp,
                    "responsable": responsable,
                    "telefono_contacto": telefono_contacto,
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
                            # Recargar datos del grupo actualizado
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
                # Recargar datos del grupo desde BD
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

# =========================
# SECCIONES ADICIONALES (basadas en código original)
# =========================

def mostrar_secciones_adicionales_mejoradas(grupos_service, grupo_id):
    """
    Muestra las secciones adicionales para grupos ya creados.
    Basado en el código original pero con mejor organización visual.
    """
    
    # SECCIÓN 4: TUTORES
    with st.expander("👨‍🏫 4. Tutores Asignados", expanded=False):
        mostrar_seccion_tutores_mejorada(grupos_service, grupo_id)
        
    # SECCIÓN 4.b: CENTRO GESTOR
    with st.expander("🏢 4.b Centro Gestor", expanded=False):
        mostrar_seccion_centro_gestor_mejorada(grupos_service, grupo_id)
        
    # SECCIÓN 5: EMPRESAS PARTICIPANTES  
    with st.expander("🏢 5. Empresas Participantes", expanded=False):
        mostrar_seccion_empresas_mejorada(grupos_service, grupo_id)
    
    # SECCIÓN 6: PARTICIPANTES
    with st.expander("👥 6. Participantes del Grupo", expanded=False):
        mostrar_seccion_participantes_mejorada(grupos_service, grupo_id)
    
    # SECCIÓN 7: COSTES FUNDAE
    with st.expander("💰 7. Costes y Bonificaciones FUNDAE", expanded=False):
        mostrar_seccion_costes_mejorada(grupos_service, grupo_id)

def mostrar_seccion_tutores_mejorada(grupos_service, grupo_id):
    """Gestión de tutores del grupo - versión mejorada del código original."""
    st.markdown("**Gestión de Tutores**")
    
    try:
        # Tutores actuales
        df_tutores = grupos_service.get_tutores_grupo(grupo_id)
        
        if not df_tutores.empty:
            st.markdown("##### 👨‍🏫 Tutores Asignados")
            
            # Mostrar en formato de cards mejorado
            for _, row in df_tutores.iterrows():
                tutor = row.get("tutor", {})
                if not tutor:
                    continue
                    
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        nombre_completo = f"{tutor.get('nombre', '')} {tutor.get('apellidos', '')}"
                        st.markdown(f"**{nombre_completo.strip()}**")
                        
                        # Información adicional en líneas separadas
                        email = tutor.get('email', 'N/A')
                        especialidad = tutor.get('especialidad', 'N/A')
                        st.caption(f"📧 {email}")
                        st.caption(f"🎯 Especialidad: {especialidad}")
                    
                    with col2:
                        if st.button("❌ Quitar", key=f"quitar_tutor_{row.get('id')}", help="Desasignar tutor del grupo"):
                            try:
                                if grupos_service.delete_tutor_grupo(row.get("id")):
                                    st.success("✅ Tutor eliminado")
                                    st.rerun()
                                else:
                                    st.error("❌ Error al eliminar tutor")
                            except Exception as e:
                                st.error(f"❌ Error: {e}")
                    
                    st.divider()
        else:
            st.info("ℹ️ No hay tutores asignados")
        
        # Añadir tutores
        st.markdown("##### ➕ Añadir Tutores")
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
                        key=f"tutores_add_{grupo_id}",
                        help="Puedes seleccionar múltiples tutores a la vez"
                    )
                    
                    if tutores_seleccionados:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.info(f"Se asignarán {len(tutores_seleccionados)} tutores")
                        
                        with col2:
                            if st.button("✅ Asignar Tutores", type="primary", use_container_width=True):
                                exitos = 0
                                for tutor_nombre in tutores_seleccionados:
                                    tutor_id = opciones_tutores[tutor_nombre]
                                    try:
                                        if grupos_service.create_tutor_grupo(grupo_id, tutor_id):
                                            exitos += 1
                                    except Exception as e:
                                        st.error(f"❌ Error al asignar {tutor_nombre}: {e}")
                                
                                if exitos > 0:
                                    st.success(f"✅ Se asignaron {exitos} tutores")
                                    st.rerun()
                else:
                    st.info("ℹ️ Todos los tutores disponibles ya están asignados")
            else:
                st.warning("⚠️ No hay tutores disponibles en el sistema")
        except Exception as e:
            st.error(f"❌ Error al cargar tutores disponibles: {e}")
            
    except Exception as e:
        st.error(f"❌ Error al cargar sección de tutores: {e}")

def mostrar_seccion_centro_gestor_mejorada(grupos_service, grupo_id):
    """Gestión de Centro Gestor mejorada."""
    try:
        info_mod = grupos_service.supabase.table("grupos").select(
            "accion_formativa:acciones_formativas(modalidad)"
        ).eq("id", grupo_id).limit(1).execute()
        
        modalidad_accion_raw = ""
        if info_mod.data and info_mod.data[0].get("accion_formativa"):
            modalidad_accion_raw = info_mod.data[0]["accion_formativa"].get("modalidad", "")
        
        modalidad_norm = grupos_service.normalizar_modalidad_fundae(modalidad_accion_raw)
        
        if modalidad_norm in ["TELEFORMACION", "MIXTA"]:
            st.markdown("### 🖥️ Centro Gestor de Teleformación")
            st.caption("Obligatorio para modalidades de Teleformación y Mixta según FUNDAE")
            
            centro_actual = grupos_service.get_centro_gestor_grupo(grupo_id)
            
            if centro_actual and centro_actual.get("centro"):
                c = centro_actual["centro"]
                
                # Mostrar centro actual en formato card
                with st.container():
                    st.success("✅ Centro gestor asignado:")
                    st.markdown(f"**{c.get('razon_social','(sin nombre)')}**")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.caption(f"🆔 CIF: {c.get('cif','N/A')}")
                    with col2:
                        st.caption(f"📮 CP: {c.get('codigo_postal','N/A')}")
                    with col3:
                        if st.button("❌ Desasignar", key="desasignar_centro", type="secondary"):
                            if grupos_service.unassign_centro_gestor_de_grupo(grupo_id):
                                st.success("✅ Centro gestor desasignado")
                                st.rerun()
            else:
                st.warning("⚠️ Este grupo necesita un centro gestor asignado")

            # Seleccionar nuevo centro
            st.markdown("##### Seleccionar Centro Gestor")
            df_centros = grupos_service.get_centros_para_grupo(grupo_id)
            
            if df_centros.empty:
                st.warning("⚠️ No hay centros gestores disponibles para este grupo.")
            else:
                opciones = {}
                for _, row in df_centros.iterrows():
                    nombre_display = (
                        str(row.get("razon_social") or 
                            row.get("nombre_comercial") or 
                            row.get("cif") or 
                            row.get("id"))
                    )
                    opciones[nombre_display] = row["id"]
                
                centro_seleccionado = st.selectbox(
                    "Centro gestor disponible:",
                    [""] + list(opciones.keys()),
                    help="Selecciona el centro que gestionará la plataforma de teleformación"
                )
                
                if centro_seleccionado:
                    if st.button("✅ Asignar Centro Gestor", type="primary", use_container_width=True):
                        if grupos_service.assign_centro_gestor_a_grupo(grupo_id, opciones[centro_seleccionado]):
                            st.success("✅ Centro gestor asignado correctamente")
                            st.rerun()
                        else:
                            st.error("❌ Error al asignar centro gestor")
        else:
            st.info("ℹ️ Centro gestor no requerido para modalidad PRESENCIAL")
                                
    except Exception as e:
        st.error(f"❌ Error en sección Centro Gestor: {e}")

def mostrar_seccion_empresas_mejorada(grupos_service, grupo_id):
    """Gestión de empresas participantes mejorada."""
    st.markdown("**Empresas Participantes**")
    
    if grupos_service.rol == "gestor":
        st.info("ℹ️ Como gestor, tu empresa está vinculada automáticamente al grupo")
    
    try:
        # Empresas actuales
        df_empresas = grupos_service.get_empresas_grupo(grupo_id)
        
        if not df_empresas.empty:
            st.markdown("##### 🏢 Empresas Asignadas")
            
            for _, row in df_empresas.iterrows():
                empresa = row.get("empresa", {})
                if not empresa:
                    continue
                
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown(f"**{empresa.get('nombre', 'Sin nombre')}**")
                        
                        cif = empresa.get('cif', 'Sin CIF')
                        fecha = row.get('fecha_asignacion', 'Sin fecha')
                        if isinstance(fecha, str) and len(fecha) > 10:
                            fecha = fecha[:10]
                        
                        st.caption(f"🆔 CIF: {cif}")
                        st.caption(f"📅 Fecha asignación: {fecha}")
                    
                    with col2:
                        if grupos_service.rol == "admin":
                            if st.button("❌ Quitar", key=f"quitar_empresa_{row.get('id')}", help="Desasignar empresa del grupo"):
                                try:
                                    if grupos_service.delete_empresa_grupo(row.get("id")):
                                        st.success("✅ Empresa eliminada")
                                        st.rerun()
                                    else:
                                        st.error("❌ Error al eliminar empresa")
                                except Exception as e:
                                    st.error(f"❌ Error: {e}")
                    
                    st.divider()
        else:
            st.info("ℹ️ No hay empresas asignadas")
        
        # Añadir empresas (solo admin)
        if grupos_service.rol == "admin":
            st.markdown("##### ➕ Añadir Empresas")
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
                            key=f"empresas_add_{grupo_id}",
                            help="Puedes seleccionar múltiples empresas participantes"
                        )
                        
                        if empresas_seleccionadas:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.info(f"Se asignarán {len(empresas_seleccionadas)} empresas")
                            
                            with col2:
                                if st.button("✅ Asignar Empresas", type="primary", use_container_width=True):
                                    exitos = 0
                                    for empresa_nombre in empresas_seleccionadas:
                                        empresa_id = empresas_disponibles[empresa_nombre]
                                        try:
                                            if grupos_service.create_empresa_grupo(grupo_id, empresa_id):
                                                exitos += 1
                                        except Exception as e:
                                            st.error(f"❌ Error al asignar {empresa_nombre}: {e}")
                                    
                                    if exitos > 0:
                                        st.success(f"✅ Se asignaron {exitos} empresas")
                                        st.rerun()
                    else:
                        st.info("ℹ️ Todas las empresas disponibles ya están asignadas")
                else:
                    st.warning("⚠️ No hay empresas disponibles en el sistema")
            except Exception as e:
                st.error(f"❌ Error al cargar empresas disponibles: {e}")
                
    except Exception as e:
        st.error(f"❌ Error al cargar sección de empresas: {e}")

def mostrar_seccion_participantes_mejorada(grupos_service, grupo_id):
    """Gestión de participantes mejorada."""
    st.markdown("**Participantes del Grupo**")
    
    try:
        # Participantes actuales
        df_participantes = grupos_service.get_participantes_grupo(grupo_id)
        
        if not df_participantes.empty:
            st.markdown("##### 👥 Participantes Asignados")
            
            # Verificar columnas y mostrar tabla
            columnas_mostrar = []
            columnas_disponibles = ["nif", "nombre", "apellidos", "email", "telefono"]
            for col in columnas_disponibles:
                if col in df_participantes.columns:
                    columnas_mostrar.append(col)
            
            if columnas_mostrar:
                st.dataframe(
                    df_participantes[columnas_mostrar],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "nif": st.column_config.TextColumn("NIF", width="small"),
                        "nombre": st.column_config.TextColumn("Nombre", width="medium"),
                        "apellidos": st.column_config.TextColumn("Apellidos", width="medium"),
                        "email": st.column_config.TextColumn("Email", width="large"),
                        "telefono": st.column_config.TextColumn("Teléfono", width="small")
                    }
                )
            else:
                st.warning("⚠️ No se pueden mostrar los datos de participantes")
            
            # Desasignar participantes
            with st.expander("❌ Desasignar Participantes"):
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
                    
                    if participantes_quitar and st.button("❌ Desasignar Seleccionados", type="secondary"):
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
                                st.error(f"❌ Error al desasignar {participante_str}: {e}")
                        
                        if exitos > 0:
                            st.success(f"✅ Se desasignaron {exitos} participantes")
                            st.rerun()
        else:
            st.info("ℹ️ No hay participantes asignados")
        
        # Asignar participantes con tabs
        st.markdown("##### ➕ Asignar Participantes")
        
        tab1, tab2 = st.tabs(["👤 Individual", "📄 Masivo (Excel)"])
        
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
                        key=f"participantes_add_{grupo_id}",
                        help="Selecciona uno o varios participantes para asignar al grupo"
                    )
                    
                    if participantes_seleccionados:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.info(f"Se asignarán {len(participantes_seleccionados)} participantes")
                        
                        with col2:
                            if st.button("✅ Asignar Seleccionados", type="primary", use_container_width=True):
                                exitos = 0
                                for participante_str in participantes_seleccionados:
                                    participante_id = participantes_opciones[participante_str]
                                    try:
                                        if grupos_service.asignar_participante_a_grupo(participante_id, grupo_id):
                                            exitos += 1
                                    except Exception as e:
                                        st.error(f"❌ Error al asignar {participante_str}: {e}")
                                
                                if exitos > 0:
                                    st.success(f"✅ Se asignaron {exitos} participantes")
                                    st.rerun()
                else:
                    st.info("ℹ️ No hay participantes disponibles")
            except Exception as e:
                st.error(f"❌ Error al cargar participantes disponibles: {e}")
        
        with tab2:
            st.markdown("**📤 Importación masiva desde Excel**")
            
            with st.expander("ℹ️ Instrucciones de uso"):
                st.markdown("""
                1. **Formato del archivo**: Excel (.xlsx) 
                2. **Columna requerida**: Debe contener una columna llamada 'dni', 'nif', 'DNI' o 'NIF'
                3. **Proceso**: Se buscarán automáticamente los participantes en el sistema por su NIF
                4. **Resultado**: Solo se asignarán los participantes encontrados y disponibles
                """)
            
            archivo_excel = st.file_uploader(
                "📁 Subir archivo Excel",
                type=["xlsx"],
                key=f"excel_participantes_{grupo_id}",
                help="Archivo Excel con columna de NIFs de participantes"
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
                        st.error("❌ El archivo debe contener una columna 'dni' o 'nif'")
                    else:
                        st.markdown("**📋 Vista previa del archivo:**")
                        st.dataframe(df_import.head(10), use_container_width=True)
                        
                        st.info(f"📊 Total filas detectadas: {len(df_import)}")
                        
                        if st.button("🚀 Procesar Archivo", type="primary", use_container_width=True):
                            with st.spinner("Procesando archivo..."):
                                try:
                                    nifs = [str(d).strip() for d in df_import[col_nif] if pd.notna(d)]
                                    nifs_validos = [d for d in nifs if validar_dni_cif(d)]
                                    
                                    st.info(f"🔍 NIFs válidos encontrados: {len(nifs_validos)}")
                                    
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
                                    
                                    # Mostrar resultados
                                    col1, col2 = st.columns(2)
                                    
                                    with col1:
                                        if asignados > 0:
                                            st.success(f"✅ {asignados} participantes asignados correctamente")
                                    
                                    with col2:
                                        if errores:
                                            st.warning(f"⚠️ {len(errores)} errores encontrados")
                                    
                                    if errores and st.checkbox("Ver errores detallados"):
                                        for error in errores[:20]:  # Mostrar máximo 20 errores
                                            st.caption(f"• {error}")
                                        
                                        if len(errores) > 20:
                                            st.caption(f"... y {len(errores) - 20} errores más")
                                    
                                    if asignados > 0:
                                        st.rerun()
                                        
                                except Exception as e:
                                    st.error(f"❌ Error al procesar datos: {e}")
                
                except Exception as e:
                    st.error(f"❌ Error al leer archivo Excel: {e}")
                    
    except Exception as e:
        st.error(f"❌ Error al cargar sección de participantes: {e}")

def mostrar_seccion_costes_mejorada(grupos_service, grupo_id):
    """Gestión de costes FUNDAE mejorada."""
    st.markdown("**💰 Costes y Bonificaciones FUNDAE**")
    
    # Obtener datos del grupo para cálculos (del código original)
    try:
        grupo_info = grupos_service.supabase.table("grupos").select("""
            modalidad, n_participantes_previstos,
            accion_formativa:acciones_formativas(num_horas)
        """).eq("id", grupo_id).execute()
        
        if not grupo_info.data:
            st.error("❌ No se pudo cargar información del grupo")
            return
            
        datos_grupo = grupo_info.data[0]
        modalidad = datos_grupo.get("modalidad", "PRESENCIAL")
        
        # Validar participantes
        participantes_raw = datos_grupo.get("n_participantes_previstos")
        if participantes_raw is None or participantes_raw == 0:
            participantes = 1
            st.warning("⚠️ Número de participantes no definido, usando valor por defecto: 1")
        else:
            participantes = int(participantes_raw)
        
        # Validar horas de la acción formativa
        accion_formativa = datos_grupo.get("accion_formativa")
        if accion_formativa and accion_formativa.get("num_horas"):
            horas = int(accion_formativa.get("num_horas", 0))
        else:
            horas = 0
            st.warning("⚠️ Horas de la acción formativa no definidas")
            
    except Exception as e:
        st.error(f"❌ Error al cargar datos del grupo: {e}")
        return
    
    # Calcular límite FUNDAE
    if horas > 0 and participantes > 0:
        try:
            limite_boni, tarifa_max = grupos_service.calcular_limite_fundae(modalidad, horas, participantes)
        except Exception as e:
            st.error(f"Error al calcular límites FUNDAE: {e}")
            limite_boni, tarifa_max = 0, 13.0  # Valores por defecto
    else:
        limite_boni, tarifa_max = 0, 13.0
        st.warning("No se pueden calcular límites FUNDAE sin horas y participantes válidos")
    
    # Mostrar información base con métricas
    st.markdown("##### 📊 Información Base del Grupo")
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
    
    st.markdown("##### 💰 Configuración de Costes")
    
    with st.form(f"costes_{grupo_id}"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Costes Directos e Indirectos**")
            
            costes_directos = st.number_input(
                "Costes Directos (€)",
                value=float(costes_actuales.get("costes_directos", 0)),
                min_value=0.0,
                key=f"directos_{grupo_id}",
                help="Gastos directamente relacionados con la formación"
            )
            
            costes_indirectos = st.number_input(
                "Costes Indirectos (€)",
                value=float(costes_actuales.get("costes_indirectos", 0)),
                min_value=0.0,
                help="Máximo 30% de costes directos según FUNDAE",
                key=f"indirectos_{grupo_id}"
            )
            
            costes_organizacion = st.number_input(
                "Costes Organización (€)",
                value=float(costes_actuales.get("costes_organizacion", 0)),
                min_value=0.0,
                key=f"organizacion_{grupo_id}",
                help="Costes de organización y coordinación"
            )
        
        with col2:
            st.markdown("**Costes Salariales y Tarifas**")
            
            costes_salariales = st.number_input(
                "Costes Salariales (€)",
                value=float(costes_actuales.get("costes_salariales", 0)),
                min_value=0.0,
                key=f"salariales_{grupo_id}",
                help="Salarios de trabajadores durante la formación"
            )
            
            cofinanciacion_privada = st.number_input(
                "Cofinanciación Privada (€)",
                value=float(costes_actuales.get("cofinanciacion_privada", 0)),
                min_value=0.0,
                key=f"cofinanciacion_{grupo_id}",
                help="Aportación privada de la empresa"
            )
            
            tarifa_hora = st.number_input(
                "Tarifa por Hora (€)",
                value=float(costes_actuales.get("tarifa_hora", tarifa_max)),
                min_value=0.0,
                max_value=tarifa_max,
                help=f"Máximo FUNDAE: {tarifa_max} €/h",
                key=f"tarifa_{grupo_id}"
            )
        
        # Observaciones
        observaciones_costes = st.text_area(
            "Observaciones sobre los costes",
            value=costes_actuales.get("observaciones", ""),
            key=f"obs_costes_{grupo_id}",
            height=60
        )
        
        # Validaciones en tiempo real
        total_costes = costes_directos + costes_indirectos + costes_organizacion + costes_salariales
        limite_calculado = tarifa_hora * horas * participantes
        
        st.markdown("##### 🧮 Resumen de Cálculos")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Costes", f"{total_costes:,.2f} €")
        
        with col2:
            st.metric("Límite Calculado", f"{limite_calculado:,.2f} €")
        
        with col3:
            diferencia = limite_calculado - total_costes
            st.metric(
                "Diferencia", 
                f"{diferencia:,.2f} €",
                delta=f"{'Dentro del límite' if diferencia >= 0 else 'Excede límite'}"
            )
        
        # Validaciones FUNDAE
        errores_costes = []
        
        # Validar porcentaje indirectos
        if costes_directos > 0:
            pct_indirectos = (costes_indirectos / costes_directos) * 100
            if pct_indirectos > 30:
                errores_costes.append(f"Costes indirectos ({pct_indirectos:.1f}%) superan el 30% permitido")
                st.error(f"❌ Costes indirectos ({pct_indirectos:.1f}%) superan el 30% permitido")
            else:
                st.success(f"✅ Costes indirectos dentro del límite ({pct_indirectos:.1f}%)")
        
        # Validar tarifa máxima
        if tarifa_hora > tarifa_max:
            errores_costes.append(f"Tarifa/hora ({tarifa_hora} €) supera el máximo ({tarifa_max} €)")
            st.error(f"❌ Tarifa/hora supera el máximo permitido")
        else:
            st.success(f"✅ Tarifa/hora dentro del límite FUNDAE")
        
        # Botón guardar
        col1, col2 = st.columns(2)
        
        with col1:
            guardar_disabled = len(errores_costes) > 0
            if st.form_submit_button("💾 Guardar Costes", type="primary", disabled=guardar_disabled):
                if errores_costes:
                    st.error("❌ No se puede guardar: corrige los errores de validación")
                    for error in errores_costes:
                        st.error(f"• {error}")
                else:
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
                    
                    try:
                        if costes_actuales:
                            exito = grupos_service.update_grupo_coste(grupo_id, datos_costes)
                        else:
                            exito = grupos_service.create_grupo_coste(datos_costes)
                        
                        if exito:
                            st.success("✅ Costes guardados correctamente")
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar costes")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
        
        with col2:
            if st.form_submit_button("🧹 Limpiar Formulario", type="secondary"):
                st.rerun()

# =========================
# FUNCIÓN PRINCIPAL MAIN MEJORADA
# =========================

def main(supabase, session_state):
    """
    Función principal de gestión de grupos con diseño moderno.
    Basada en el código original pero con mejoras de UX y modal.
    """
    st.title("👥 Gestión de Grupos FUNDAE")
    st.caption("Creación y administración de grupos formativos según estándares FUNDAE")
    
    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección")
        return
    
    # Inicializar servicio
    try:
        grupos_service = get_grupos_service(supabase, session_state)
    except Exception as e:
        st.error(f"❌ Error al inicializar servicio: {e}")
        return
    
    # Cargar datos
    try:
        df_grupos = grupos_service.get_grupos_completos()
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return
    
    # === SECCIÓN 1: KPIs MODERNOS ===
    mostrar_kpis_grupos_modernos(df_grupos)
    
    # === SECCIÓN 2: AVISOS Y ALERTAS ===
    if not df_grupos.empty:
        grupos_pendientes = get_grupos_pendientes_finalizacion(df_grupos)
        mostrar_avisos_grupos_expandible(grupos_pendientes)
    
    st.divider()
    
    # === SECCIÓN 3: FILTROS ===
    if not df_grupos.empty:
        filtro_texto, filtro_estado = crear_filtros_grupos_mejorados()
        
        # Aplicar filtros
        df_filtrado = aplicar_filtros_grupos(df_grupos, filtro_texto, filtro_estado)
    else:
        df_filtrado = df_grupos
    
    # === SECCIÓN 4: TABLA PRINCIPAL CON MODAL ===
    grupo_seleccionado = mostrar_tabla_grupos_con_modal(df_filtrado, grupos_service)
    
    st.divider()
    
    # === SECCIÓN 5: FORMULARIO DE GRUPO ===
    if hasattr(st.session_state, 'grupo_seleccionado'):
        if st.session_state.grupo_seleccionado == "nuevo":
            # Mostrar formulario de creación
            mostrar_formulario_grupo_mejorado(grupos_service, es_creacion=True)
        elif st.session_state.grupo_seleccionado:
            # Mostrar formulario de edición
            grupo_id = mostrar_formulario_grupo_mejorado(grupos_service, st.session_state.grupo_seleccionado)
            
            # === SECCIÓN 6: GESTIÓN AVANZADA ===
            if grupo_id:
                st.divider()
                st.markdown("## 🛠️ Gestión Avanzada del Grupo")
                mostrar_secciones_adicionales_mejoradas(grupos_service, grupo_id)
    
    # Footer informativo
    st.divider()
    st.caption("💡 Sistema de Gestión FUNDAE - Grupos de Formación | Rediseñado Enero 2025")

# =========================
# PUNTO DE ENTRADA
# =========================

if __name__ == "__main__":
    # Para testing local - mantener estructura del código original
    pass
