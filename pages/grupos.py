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
# FUNCIONES AUXILIARES MEJORADAS
# =========================

def safe_int_conversion(value, default=0):
    """Convierte un valor a entero de forma segura, manejando NaN y None."""
    if value is None:
        return default
    if pd.isna(value):
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
# FUNCIONES DE ESTADO AUTOMÁTICO
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

# =========================
# COMPONENTES UI MODERNOS
# =========================

def mostrar_metricas_grupos(df_grupos, session_state):
    """Muestra métricas con información jerárquica usando Streamlit 1.49."""
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
    
    # Métricas adicionales por rol
    if session_state.role == "admin":
        with st.container():
            st.markdown("##### 🌳 Distribución por Empresa")
            if "empresa_nombre" in df_grupos.columns:
                empresas = df_grupos["empresa_nombre"].value_counts().head(5)
                col1, col2, col3 = st.columns(3)
                for i, (empresa, count) in enumerate(empresas.items()):
                    with [col1, col2, col3][i % 3]:
                        st.metric(empresa[:20], count)

def mostrar_avisos_grupos(grupos_pendientes):
    """Muestra avisos de grupos pendientes de finalización con acciones."""
    if not grupos_pendientes:
        return
    
    st.warning(f"⚠️ **{len(grupos_pendientes)} grupo(s) pendiente(s) de finalización**")
    
    with st.expander("Ver grupos pendientes", expanded=False):
        for grupo in grupos_pendientes[:5]:
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{grupo.get('codigo_grupo')}** - Fin previsto: {grupo.get('fecha_fin_prevista')}")
                    st.caption(f"Acción: {grupo.get('accion_nombre', 'N/A')} | Participantes: {grupo.get('n_participantes_previstos', 0)}")
                with col2:
                    if st.button("Finalizar", key=f"finalizar_{grupo.get('id')}", type="secondary"):
                        grupo_copy = grupo.copy()
                        grupo_copy['_mostrar_finalizacion'] = True
                        st.session_state.grupo_seleccionado = grupo_copy
                        st.rerun()

def crear_selector_horario_fundae(prefix=""):
    """Crea un selector de horario compatible con FUNDAE usando Streamlit 1.49."""
    st.markdown("#### 🕐 Configuración de Horarios FUNDAE")
    st.caption("Intervalos de 15 minutos obligatorios según normativa FUNDAE")
    
    # Opción de configuración con estilo moderno
    tipo_horario = st.radio(
        "Tipo de jornada:",
        ["Solo Mañana", "Solo Tarde", "Mañana y Tarde"],
        horizontal=True,
        key=f"{prefix}_tipo_horario"
    )
    
    col1, col2 = st.columns(2)
    
    manana_inicio = manana_fin = tarde_inicio = tarde_fin = None
    
    # Generar intervalos de tiempo
    intervalos_manana = [f"{h:02d}:{m:02d}" for h in range(6, 15) for m in [0, 15, 30, 45]]
    intervalos_tarde = [f"{h:02d}:{m:02d}" for h in range(15, 24) for m in [0, 15, 30, 45] if not (h == 23 and m > 0)]
    
    # Tramo mañana
    if tipo_horario in ["Solo Mañana", "Mañana y Tarde"]:
        with col1:
            with st.container(border=True):
                st.markdown("**🌅 Tramo Mañana (06:00 - 15:00)**")
                
                sub_col1, sub_col2 = st.columns(2)
                with sub_col1:
                    manana_inicio = st.selectbox(
                        "Hora inicio:",
                        intervalos_manana[:-1],
                        index=12,  # 09:00
                        key=f"{prefix}_manana_inicio"
                    )
                with sub_col2:
                    if manana_inicio:
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
            with st.container(border=True):
                st.markdown("**🌆 Tramo Tarde (15:00 - 23:00)**")
                
                sub_col1, sub_col2 = st.columns(2)
                with sub_col1:
                    tarde_inicio = st.selectbox(
                        "Hora inicio:",
                        intervalos_tarde[:-1],
                        index=0,  # 15:00
                        key=f"{prefix}_tarde_inicio"
                    )
                with sub_col2:
                    if tarde_inicio:
                        idx_inicio = intervalos_tarde.index(tarde_inicio)
                        horas_fin_validas = intervalos_tarde[idx_inicio + 1:]
                        
                        tarde_fin = st.selectbox(
                            "Hora fin:",
                            horas_fin_validas,
                            index=min(15, len(horas_fin_validas)-1) if horas_fin_validas else 0,
                            key=f"{prefix}_tarde_fin"
                        )
    
    # Días de la semana con diseño moderno
    st.markdown("**📅 Días de Impartición**")
    with st.container(border=True):
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
        st.success(f"✅ Horario FUNDAE: {horario_final}")
        
        # Validar formato
        es_valido, error = validar_horario_fundae(horario_final)
        if not es_valido:
            st.error(f"❌ Error: {error}")
    else:
        st.warning("⚠️ Configure al menos un tramo horario y días")
    
    return horario_final

# =========================
# FORMULARIO PRINCIPAL CON JERARQUÍA
# =========================

# =========================
# FORMULARIO PRINCIPAL CON VALIDACIONES FUNDAE INTEGRADAS
# =========================

def mostrar_formulario_grupo(grupos_service, grupo_seleccionado=None, es_creacion=False):
    """Formulario unificado para crear/editar grupos con validaciones FUNDAE completas."""
    
    # Obtener datos necesarios
    acciones_dict = grupos_service.get_acciones_dict()
    
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
    
    # Título del formulario con estilo moderno
    if es_creacion:
        st.markdown("### ➕ Crear Nuevo Grupo")
        st.caption("🎯 Complete los datos básicos obligatorios para crear el grupo")
    else:
        codigo = datos_grupo.get("codigo_grupo", "Sin código")
        st.markdown(f"### ✏️ Editar Grupo: {codigo}")
        
        # Mostrar estado actual con colores
        color_estado = {"ABIERTO": "🟢", "FINALIZAR": "🟡", "FINALIZADO": "✅"}
        st.caption(f"Estado: {color_estado.get(estado_actual, '⚪')} {estado_actual}")
    
    # Usar formulario con key único
    form_key = f"grupo_form_{datos_grupo.get('id', 'nuevo')}_{datetime.now().timestamp()}"
    
    with st.form(form_key, clear_on_submit=es_creacion):
        
        # =====================
        # SECCIÓN 1: DATOS BÁSICOS FUNDAE CON VALIDACIONES
        # =====================
        with st.container(border=True):
            st.markdown("### 🆔 Datos Básicos FUNDAE")
            st.markdown("**Información obligatoria para XML FUNDAE**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Acción formativa PRIMERO (necesaria para validaciones)
                acciones_nombres = list(acciones_dict.keys())
                if grupo_seleccionado and datos_grupo.get("accion_formativa_id"):
                    accion_actual = None
                    for nombre, id_accion in acciones_dict.items():
                        if id_accion == datos_grupo.get("accion_formativa_id"):
                            accion_actual = nombre
                            break
                    indice_actual = acciones_nombres.index(accion_actual) if accion_actual else 0
                else:
                    indice_actual = 0
                
                accion_formativa = st.selectbox(
                    "📚 Acción Formativa *",
                    acciones_nombres,
                    index=indice_actual,
                    help="Selecciona la acción formativa asociada",
                    key="accion_formativa_select"
                )
                
                accion_id = acciones_dict[accion_formativa]
                
                # CÓDIGO DEL GRUPO CON VALIDACIONES FUNDAE
                if es_creacion:
                    # Generar código sugerido automáticamente
                    codigo_sugerido, error_sugerido = grupos_service.generar_codigo_grupo_sugerido(accion_id)
                    
                    if codigo_sugerido and not error_sugerido:
                        st.info(f"💡 Código sugerido: **{codigo_sugerido}**")
                        # Usar el código sugerido como valor por defecto
                        codigo_default = datos_grupo.get("codigo_grupo", codigo_sugerido)
                    else:
                        codigo_default = datos_grupo.get("codigo_grupo", "")
                        if error_sugerido:
                            st.warning(f"⚠️ No se pudo generar código sugerido: {error_sugerido}")
                    
                    codigo_grupo = st.text_input(
                        "🏷️ Código del Grupo *",
                        value=codigo_default,
                        max_chars=50,
                        help="Código único por acción formativa, empresa gestora y año",
                        key="codigo_grupo_input"
                    )
                    
                    # VALIDACIÓN EN TIEMPO REAL DEL CÓDIGO
                    if codigo_grupo and accion_id:
                        es_valido, mensaje_error = grupos_service.validar_codigo_grupo_unico_fundae(
                            codigo_grupo, accion_id
                        )
                        
                        if es_valido:
                            st.success(f"✅ Código '{codigo_grupo}' disponible")
                        else:
                            st.error(f"❌ {mensaje_error}")
                            
                            # Botón para usar código sugerido como alternativa
                            if codigo_sugerido and codigo_grupo != codigo_sugerido:
                                if st.button(f"Usar código sugerido: {codigo_sugerido}", key="usar_sugerido"):
                                    st.session_state.codigo_grupo_input = codigo_sugerido
                                    st.rerun()
                
                else:
                    # Modo edición - código no editable
                    codigo_grupo = datos_grupo.get("codigo_grupo", "")
                    st.text_input(
                        "🏷️ Código del Grupo",
                        value=codigo_grupo,
                        disabled=True,
                        help="No se puede modificar después de la creación"
                    )
                    
                    # Mostrar validación del código existente
                    if codigo_grupo and accion_id:
                        es_valido, mensaje_error = grupos_service.validar_codigo_grupo_unico_fundae(
                            codigo_grupo, accion_id, datos_grupo.get("id")
                        )
                        
                        if es_valido:
                            st.success(f"✅ Código válido")
                        else:
                            st.error(f"❌ {mensaje_error}")
        
                # Calcular modalidad automáticamente
                accion_modalidad_raw = grupos_service.get_accion_modalidad(accion_id)
                modalidad_grupo = grupos_service.normalizar_modalidad_fundae(accion_modalidad_raw)
        
                # Mostrar modalidad en solo lectura
                st.text_input(
                    "🎯 Modalidad",
                    value=modalidad_grupo,
                    disabled=True,
                    help="Modalidad tomada automáticamente de la acción formativa"
                )
                
                # Fechas
                fecha_inicio_value = safe_date_conversion(datos_grupo.get("fecha_inicio")) or date.today()
                fecha_inicio = st.date_input(
                    "📅 Fecha de Inicio *",
                    value=fecha_inicio_value,
                    help="Fecha de inicio de la formación"
                )
        
                fecha_fin_prevista_value = safe_date_conversion(datos_grupo.get("fecha_fin_prevista"))
                fecha_fin_prevista = st.date_input(
                    "📅 Fecha Fin Prevista *",
                    value=fecha_fin_prevista_value,
                    help="Fecha prevista de finalización"
                )
                
                # VALIDACIÓN TEMPORAL EN TIEMPO REAL
                if fecha_inicio and fecha_fin_prevista and accion_id:
                    errores_temporales = grupos_service.validar_coherencia_temporal_grupo(
                        fecha_inicio, fecha_fin_prevista, accion_id
                    )
                    
                    if errores_temporales:
                        st.error("❌ Errores de coherencia temporal:")
                        for error in errores_temporales:
                            st.error(f"• {error}")
                    else:
                        st.success("✅ Fechas coherentes con la acción formativa")
            
            with col2:
                # Empresa propietaria (solo admin)
                if grupos_service.rol == "admin":
                    empresas_opciones = grupos_service.get_empresas_para_grupos()
                    
                    if empresas_opciones:
                        empresa_actual = datos_grupo.get("empresa_id")
                        empresa_nombre_actual = None
                        
                        # Buscar nombre actual
                        for nombre, id_emp in empresas_opciones.items():
                            if id_emp == empresa_actual:
                                empresa_nombre_actual = nombre
                                break
                        
                        empresa_propietaria = st.selectbox(
                            "🏢 Empresa Propietaria *",
                            list(empresas_opciones.keys()),
                            index=list(empresas_opciones.keys()).index(empresa_nombre_actual) if empresa_nombre_actual else 0,
                            help="Empresa propietaria del grupo (obligatorio para admin)"
                        )
                        empresa_id = empresas_opciones[empresa_propietaria]
                    else:
                        st.error("❌ No hay empresas disponibles")
                        empresa_id = None
                else:
                    # Para gestores, se usa su empresa automáticamente
                    empresa_id = grupos_service.empresa_id
                    st.info(f"🏢 Tu empresa será la propietaria del grupo")
                
                # MOSTRAR EMPRESA RESPONSABLE ANTE FUNDAE
                if accion_id and empresa_id:
                    empresa_responsable, error_empresa = grupos_service.determinar_empresa_gestora_responsable(
                        accion_id, empresa_id
                    )
                    
                    if empresa_responsable and not error_empresa:
                        with st.container(border=True):
                            st.markdown("#### 🏢 Empresa Responsable ante FUNDAE")
                            st.write(f"**Nombre:** {empresa_responsable['nombre']}")
                            st.write(f"**CIF:** {empresa_responsable.get('cif', 'N/A')}")
                            st.write(f"**Tipo:** {empresa_responsable['tipo_empresa']}")
                            
                            if empresa_responsable['tipo_empresa'] == "GESTORA":
                                st.success("✅ Gestora - Responsable directa ante FUNDAE")
                            else:
                                st.info("ℹ️ Los XMLs se generarán bajo la gestora correspondiente")
                    elif error_empresa:
                        st.warning(f"⚠️ {error_empresa}")
                
                # Localidad y Provincia con selectores jerárquicos
                try:
                    provincias = grupos_service.get_provincias()
                    prov_opciones = {p["nombre"]: p["id"] for p in provincias}
                    
                    provincia_actual = datos_grupo.get("provincia") if datos_grupo else None
                    
                    provincia_sel = st.selectbox(
                        "🗺️ Provincia *",
                        options=list(prov_opciones.keys()),
                        index=list(prov_opciones.keys()).index(provincia_actual) if provincia_actual in prov_opciones else 0,
                        help="Provincia de impartición (obligatorio FUNDAE)"
                    )
                    
                    if provincia_sel:
                        localidades = grupos_service.get_localidades_por_provincia(prov_opciones[provincia_sel])
                        loc_nombres = [l["nombre"] for l in localidades]
                        
                        localidad_actual = datos_grupo.get("localidad") if datos_grupo else None
                        
                        localidad_sel = st.selectbox(
                            "🏘️ Localidad *",
                            options=loc_nombres,
                            index=loc_nombres.index(localidad_actual) if localidad_actual in loc_nombres else 0 if loc_nombres else -1,
                            help="Localidad de impartición (obligatorio FUNDAE)"
                        )
                    else:
                        localidad_sel = None
                except Exception as e:
                    st.error(f"Error al cargar provincias/localidades: {e}")
                    # Fallback a campos de texto libre
                    provincia_sel = st.text_input(
                        "🗺️ Provincia *",
                        value=datos_grupo.get("provincia", ""),
                        help="Provincia de impartición (obligatorio FUNDAE)"
                    )
                    localidad_sel = st.text_input(
                        "🏘️ Localidad *", 
                        value=datos_grupo.get("localidad", ""),
                        help="Localidad de impartición (obligatorio FUNDAE)"
                    )
                
                cp = st.text_input(
                    "📮 Código Postal",
                    value=datos_grupo.get("cp", ""),
                    help="Código postal de impartición"
                )

                responsable = st.text_input(
                    "👤 Responsable del Grupo *",
                    value=datos_grupo.get("responsable", ""),
                    help="Persona responsable del grupo (obligatorio FUNDAE)"
                )
                
                telefono_contacto = st.text_input(
                    "📞 Teléfono de Contacto *",
                    value=datos_grupo.get("telefono_contacto", ""),
                    help="Teléfono de contacto del responsable (obligatorio FUNDAE)"
                )
                
                # Participantes previstos
                n_participantes_actual = datos_grupo.get("n_participantes_previstos")
                if n_participantes_actual is None or n_participantes_actual == 0:
                    n_participantes_actual = 8
                
                n_participantes_previstos = st.number_input(
                    "👥 Participantes Previstos *",
                    min_value=1,
                    max_value=30,
                    value=int(n_participantes_actual),
                    help="Número de participantes previstos (1-30)"
                )
            
            # Lugar de impartición
            lugar_imparticion = st.text_area(
                "📍 Lugar de Impartición",
                value=datos_grupo.get("lugar_imparticion", ""),
                height=60,
                help="Descripción detallada del lugar donde se impartirá la formación"
            )
            
            # Observaciones
            observaciones = st.text_area(
                "📝 Observaciones",
                value=datos_grupo.get("observaciones", ""),
                height=80,
                help="Información adicional sobre el grupo (opcional)"
            )
        
        # =====================
        # SECCIÓN 2: HORARIOS FUNDAE (mantener igual)
        # =====================
        with st.container(border=True):
            st.markdown("### ⏰ Horarios de Impartición")
            
            # Cargar horario actual si existe
            horario_actual = datos_grupo.get("horario", "")
            
            if horario_actual and not es_creacion:
                st.info(f"**Horario actual**: {horario_actual}")
                
                cambiar_horario = st.checkbox("Modificar horario")
                
                if cambiar_horario:
                    horario_nuevo = crear_selector_horario_fundae("edit")
                else:
                    horario_nuevo = horario_actual
            else:
                horario_nuevo = crear_selector_horario_fundae("new")
        
        # =====================
        # SECCIÓN 3: FINALIZACIÓN (Condicional)
        # =====================
        mostrar_finalizacion = (
            not es_creacion
            and (
                estado_actual in ["FINALIZAR", "FINALIZADO"]
                or (fecha_fin_prevista and fecha_fin_prevista <= date.today())
                or datos_grupo.get("_mostrar_finalizacion", False)
            )
        )
    
        datos_finalizacion = {}
        if mostrar_finalizacion:
            with st.container(border=True):
                st.markdown("### 🏁 Datos de Finalización")
                st.markdown("**Complete los datos de finalización para FUNDAE**")
                
                if estado_actual == "FINALIZAR":
                    st.warning("⚠️ Este grupo ha superado su fecha prevista y necesita ser finalizado")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    fecha_fin_real = st.date_input(
                        "📅 Fecha Fin Real *",
                        value=datetime.fromisoformat(datos_grupo["fecha_fin"]).date() if datos_grupo.get("fecha_fin") else date.today(),
                        help="Fecha real de finalización del grupo"
                    )
                    
                    n_finalizados_raw = datos_grupo.get("n_participantes_finalizados")
                    n_finalizados_actual = safe_int_conversion(n_finalizados_raw, 0)
                    
                    n_finalizados = st.number_input(
                        "👥 Participantes Finalizados *",
                        min_value=0,
                        max_value=n_participantes_previstos,
                        value=n_finalizados_actual,
                        help="Número de participantes que finalizaron la formación"
                    )
                
                with col2:
                    n_aptos_raw = datos_grupo.get("n_aptos")
                    n_aptos_actual = safe_int_conversion(n_aptos_raw, 0)
                    
                    n_no_aptos_raw = datos_grupo.get("n_no_aptos")
                    n_no_aptos_actual = safe_int_conversion(n_no_aptos_raw, 0)
                    
                    n_aptos = st.number_input(
                        "✅ Participantes Aptos *",
                        min_value=0,
                        max_value=n_finalizados if n_finalizados > 0 else n_participantes_previstos,
                        value=n_aptos_actual,
                        help="Número de participantes aptos"
                    )
                    
                    n_no_aptos = st.number_input(
                        "❌ Participantes No Aptos *",
                        min_value=0,
                        max_value=n_finalizados if n_finalizados > 0 else n_participantes_previstos,
                        value=n_no_aptos_actual,
                        help="Número de participantes no aptos"
                    )
                
                # VALIDACIÓN DE COHERENCIA EN TIEMPO REAL
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
        # VALIDACIONES FINALES Y BOTONES
        # =====================
        
        # Validaciones FUNDAE completas
        errores = []
        if not codigo_grupo:
            errores.append("Código del grupo requerido")
        if not accion_formativa:
            errores.append("Acción formativa requerida")
        if not fecha_inicio:
            errores.append("Fecha de inicio requerida")
        if not fecha_fin_prevista:
            errores.append("Fecha fin prevista requerida")
        if not localidad_sel:
            errores.append("Localidad requerida")
        if not responsable:
            errores.append("Responsable requerido")
        if not telefono_contacto:
            errores.append("Teléfono de contacto requerido")
        if grupos_service.rol == "admin" and not empresa_id:
            errores.append("Empresa propietaria requerida")
        if not horario_nuevo:
            errores.append("Horario requerido")
        
        # Validar código único si estamos creando
        if es_creacion and codigo_grupo and accion_id:
            es_valido_codigo, error_codigo = grupos_service.validar_codigo_grupo_unico_fundae(
                codigo_grupo, accion_id
            )
            if not es_valido_codigo:
                errores.append(f"Código no válido: {error_codigo}")
        
        # Validar datos de finalización si aplica
        if datos_finalizacion:
            if n_finalizados > 0 and (n_aptos + n_no_aptos != n_finalizados):
                errores.append("La suma de aptos + no aptos debe igual participantes finalizados")
        
        # Mostrar errores si existen
        if errores:
            st.error("❌ Faltan campos obligatorios:")
            for error in errores:
                st.error(f"• {error}")
        
        # Botones de acción
        st.divider()
        
        if es_creacion:
            col1, col2 = st.columns([2, 1])
            with col1:
                submitted = st.form_submit_button(
                    "➕ Crear Grupo", 
                    type="primary", 
                    use_container_width=True,
                    disabled=len(errores) > 0
                )
            with col2:
                cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)
                
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                submitted = st.form_submit_button(
                    "💾 Guardar Cambios", 
                    type="primary", 
                    use_container_width=True,
                    disabled=len(errores) > 0
                )
            with col2:
                recargar = st.form_submit_button("🔄 Recargar", use_container_width=True)
            with col3:
                cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)
        
        # Procesar formulario
        if submitted and len(errores) == 0:
            # Preparar datos según operación
            datos_para_guardar = {
                "accion_formativa_id": acciones_dict[accion_formativa],
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
            
            # Añadir código solo en creación
            if es_creacion:
                datos_para_guardar["codigo_grupo"] = codigo_grupo
                datos_para_guardar["empresa_id"] = empresa_id
            
            # Añadir datos de finalización si están disponibles
            if datos_finalizacion:
                datos_para_guardar.update(datos_finalizacion)
            
            try:
                if es_creacion:
                    # Usar método mejorado con validaciones FUNDAE
                    exito, grupo_id = grupos_service.create_grupo_con_jerarquia_mejorado(datos_para_guardar)
                    if exito:
                        st.success(f"✅ Grupo '{codigo_grupo}' creado correctamente con validaciones FUNDAE")
                        # Cargar el grupo recién creado para edición
                        grupo_creado = grupos_service.supabase.table("grupos").select("*").eq("id", grupo_id).execute()
                        if grupo_creado.data:
                            st.session_state.grupo_seleccionado = grupo_creado.data[0]
                            st.rerun()
                    else:
                        st.error("❌ Error al crear el grupo")
                else:
                    if grupos_service.update_grupo(datos_grupo["id"], datos_para_guardar):
                        st.success("✅ Cambios guardados correctamente")
                        # Recargar datos del grupo actualizado
                        grupo_actualizado = grupos_service.supabase.table("grupos").select("*").eq("id", datos_grupo["id"]).execute()
                        if grupo_actualizado.data:
                            st.session_state.grupo_seleccionado = grupo_actualizado.data[0]
                        st.rerun()
                    else:
                        st.error("❌ Error al guardar cambios")
            except Exception as e:
                st.error(f"❌ Error al procesar grupo: {e}")
        
        elif cancelar:
            st.session_state.grupo_seleccionado = None
            st.rerun()
        
        elif not es_creacion and 'recargar' in locals() and recargar:
            try:
                grupo_recargado = grupos_service.supabase.table("grupos").select("*").eq("id", datos_grupo["id"]).execute()
                if grupo_recargado.data:
                    st.session_state.grupo_seleccionado = grupo_recargado.data[0]
                st.rerun()
            except Exception as e:
                st.error(f"Error al recargar: {e}")
    
    return datos_grupo.get("id") if datos_grupo else None

# =========================
# SECCIONES ADICIONALES CON JERARQUÍA
# =========================

def mostrar_secciones_adicionales(grupos_service, grupo_id):
    """Muestra las secciones adicionales para grupos ya creados con soporte jerárquico."""
    
    # SECCIÓN 4: TUTORES CON JERARQUÍA
    with st.expander("👨‍🏫 4. Tutores Asignados", expanded=False):
        mostrar_seccion_tutores_jerarquia(grupos_service, grupo_id)
        
    # SECCIÓN 4.b: CENTRO GESTOR
    with st.expander("🏢 4.b Centro Gestor", expanded=False):
        mostrar_seccion_centro_gestor(grupos_service, grupo_id)
        
    # SECCIÓN 5: EMPRESAS PARTICIPANTES CON JERARQUÍA
    with st.expander("🏢 5. Empresas Participantes", expanded=False):
        mostrar_seccion_empresas_jerarquia(grupos_service, grupo_id)
    
    # SECCIÓN 6: PARTICIPANTES CON JERARQUÍA
    with st.expander("👥 6. Participantes del Grupo", expanded=False):
        mostrar_seccion_participantes_jerarquia(grupos_service, grupo_id)
    
    # SECCIÓN 7: COSTES FUNDAE
    with st.expander("💰 7. Costes y Bonificaciones FUNDAE", expanded=False):
        mostrar_seccion_costes(grupos_service, grupo_id)

def mostrar_seccion_tutores_jerarquia(grupos_service, grupo_id):
    """Gestión de tutores del grupo con soporte jerárquico."""
    st.markdown("**Gestión de Tutores con Jerarquía**")
    
    # Validar permisos
    if not grupos_service.validar_permisos_grupo(grupo_id):
        st.warning("⚠️ No tienes permisos para gestionar tutores de este grupo")
        return
    
    try:
        # Tutores actuales
        df_tutores = grupos_service.get_tutores_grupo(grupo_id)
        
        if not df_tutores.empty:
            st.markdown("##### Tutores Asignados")
            
            # Mostrar tutores con información de empresa
            for _, row in df_tutores.iterrows():
                tutor = row.get("tutor", {})
                if not tutor:
                    continue
                    
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        nombre_completo = f"{tutor.get('nombre', '')} {tutor.get('apellidos', '')}"
                        st.write(f"**{nombre_completo.strip()}**")
                        st.caption(f"📧 {tutor.get('email', 'N/A')} | 🎯 {tutor.get('especialidad', 'Sin especialidad')}")
                    with col2:
                        if st.button("Quitar", key=f"quitar_tutor_{row.get('id')}", type="secondary"):
                            try:
                                if grupos_service.delete_tutor_grupo(row.get("id")):
                                    st.success("✅ Tutor eliminado")
                                    st.rerun()
                                else:
                                    st.error("❌ Error al eliminar tutor")
                            except Exception as e:
                                st.error(f"Error: {e}")
        else:
            st.info("📋 No hay tutores asignados")
        
        # Añadir tutores con jerarquía
        st.markdown("##### Añadir Tutores")
        try:
            df_tutores_disponibles = grupos_service.get_tutores_disponibles_jerarquia(grupo_id)
            
            if not df_tutores_disponibles.empty:
                opciones_tutores = {}
                for _, row in df_tutores_disponibles.iterrows():
                    nombre = row.get('nombre_completo', f"{row.get('nombre', '')} {row.get('apellidos', '')}")
                    especialidad = row.get('especialidad', 'Sin especialidad')
                    empresa = row.get('empresa_nombre', 'Sin empresa')
                    opciones_tutores[f"{nombre} - {especialidad} ({empresa})"] = row["id"]
                
                tutores_seleccionados = st.multiselect(
                    "Seleccionar tutores:",
                    opciones_tutores.keys(),
                    key=f"tutores_add_{grupo_id}",
                    help="Solo se muestran tutores de empresas con las que tienes relación jerárquica"
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
                        st.success(f"✅ Se asignaron {exitos} tutores")
                        st.rerun()
            else:
                st.info("📋 No hay tutores disponibles en tu ámbito jerárquico")
        except Exception as e:
            st.error(f"Error al cargar tutores disponibles: {e}")
            
    except Exception as e:
        st.error(f"Error al cargar sección de tutores: {e}")

def mostrar_seccion_centro_gestor(grupos_service, grupo_id):
    """Gestión de Centro Gestor con validaciones jerárquicas."""
    st.markdown("**Centro Gestor (solo Teleformación/Mixta)**")
    
    try:
        # Verificar modalidad del grupo
        info_mod = grupos_service.supabase.table("grupos").select(
            "modalidad"
        ).eq("id", grupo_id).limit(1).execute()
        
        modalidad_norm = "PRESENCIAL"
        if info_mod.data:
            modalidad_norm = info_mod.data[0].get("modalidad", "PRESENCIAL")
        
        if modalidad_norm in ["TELEFORMACION", "MIXTA"]:
            centro_actual = grupos_service.get_centro_gestor_grupo(grupo_id)
            
            if centro_actual and centro_actual.get("centro"):
                c = centro_actual["centro"]
                with st.container(border=True):
                    st.success(f"✅ Centro gestor actual: **{c.get('razon_social','(sin nombre)')}**")
                    st.caption(f"CIF: {c.get('cif','N/A')} | CP: {c.get('codigo_postal','N/A')}")

            df_centros = grupos_service.get_centros_gestores_jerarquia(grupo_id)
            
            if df_centros.empty:
                st.warning("⚠️ No hay centros gestores disponibles para este grupo.")
            else:
                opciones = {}
                for _, row in df_centros.iterrows():
                    nombre_centro = str(row.get("razon_social") or row.get("nombre_comercial") or row.get("cif") or row.get("id"))
                    opciones[nombre_centro] = row["id"]
                
                sel = st.selectbox(
                    "Seleccionar centro gestor", 
                    list(opciones.keys()),
                    help="Solo se muestran centros de empresas en tu ámbito jerárquico"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Asignar centro gestor", type="primary"):
                        ok = grupos_service.assign_centro_gestor_a_grupo(grupo_id, opciones[sel])
                        if ok:
                            st.success("✅ Centro gestor asignado correctamente.")
                            st.rerun()
                
                with col2:
                    if centro_actual and st.button("❌ Desasignar centro gestor"):
                        ok = grupos_service.unassign_centro_gestor_de_grupo(grupo_id)
                        if ok:
                            st.success("✅ Centro gestor desasignado.")
                            st.rerun()
        else:
            st.info("ℹ️ Centro gestor solo requerido para modalidades Teleformación y Mixta")
                                
    except Exception as e:
        st.error(f"Error en sección Centro Gestor: {e}")

def mostrar_seccion_empresas_jerarquia(grupos_service, grupo_id):
    """Gestión de empresas participantes con soporte jerárquico."""
    st.markdown("**Empresas Participantes con Jerarquía**")
    
    # Información contextual por rol
    if grupos_service.rol == "gestor":
        st.info("ℹ️ Como gestor, puedes asignar tu empresa y empresas clientes")
    elif grupos_service.rol == "admin":
        st.info("ℹ️ Como admin, puedes asignar cualquier empresa del sistema")
    
    try:
        # Empresas actuales
        df_empresas = grupos_service.get_empresas_grupo(grupo_id)
        
        if not df_empresas.empty:
            st.markdown("##### Empresas Asignadas")
            for _, row in df_empresas.iterrows():
                empresa = row.get("empresa", {})
                if not empresa:
                    continue
                    
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{empresa.get('nombre', 'Sin nombre')}**")
                        cif = empresa.get('cif', 'Sin CIF')
                        fecha = row.get('fecha_asignacion', 'Sin fecha')
                        if isinstance(fecha, str) and len(fecha) > 10:
                            fecha = fecha[:10]
                        st.caption(f"📄 CIF: {cif} | 📅 Fecha: {fecha}")
                    with col2:
                        # Solo permitir quitar si tiene permisos
                        if grupos_service.validar_permisos_grupo(grupo_id) and st.button(
                            "Quitar", 
                            key=f"quitar_empresa_{row.get('id')}", 
                            type="secondary"
                        ):
                            try:
                                if grupos_service.delete_empresa_grupo(row.get("id")):
                                    st.success("✅ Empresa eliminada")
                                    st.rerun()
                                else:
                                    st.error("❌ Error al eliminar empresa")
                            except Exception as e:
                                st.error(f"Error: {e}")
        else:
            st.info("📋 No hay empresas asignadas")
        
        # Añadir empresas con jerarquía
        st.markdown("##### Añadir Empresas")
        try:
            empresas_disponibles = grupos_service.get_empresas_asignables_a_grupo(grupo_id)
            
            if empresas_disponibles:
                empresas_seleccionadas = st.multiselect(
                    "Seleccionar empresas:",
                    empresas_disponibles.keys(),
                    key=f"empresas_add_{grupo_id}",
                    help="Solo se muestran empresas en tu ámbito jerárquico"
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
                        st.success(f"✅ Se asignaron {exitos} empresas")
                        st.rerun()
            else:
                st.info("📋 No hay empresas disponibles para asignar")
        except Exception as e:
            st.error(f"Error al cargar empresas disponibles: {e}")
                
    except Exception as e:
        st.error(f"Error al cargar sección de empresas: {e}")

def mostrar_seccion_participantes_jerarquia(grupos_service, grupo_id):
    """Gestión de participantes del grupo con soporte jerárquico."""
    st.markdown("**Participantes del Grupo con Jerarquía**")
    
    try:
        # Participantes actuales
        df_participantes = grupos_service.get_participantes_grupo(grupo_id)
        
        if not df_participantes.empty:
            st.markdown("##### Participantes Asignados")
            
            # Verificar columnas disponibles
            columnas_mostrar = []
            columnas_disponibles = ["nif", "nombre", "apellidos", "email", "telefono"]
            for col in columnas_disponibles:
                if col in df_participantes.columns:
                    columnas_mostrar.append(col)
            
            if columnas_mostrar:
                # Usar dataframe moderno de Streamlit 1.49
                st.dataframe(
                    df_participantes[columnas_mostrar],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "nif": st.column_config.TextColumn("📄 NIF", width="small"),
                        "nombre": st.column_config.TextColumn("👤 Nombre", width="medium"),
                        "apellidos": st.column_config.TextColumn("👤 Apellidos", width="medium"),
                        "email": st.column_config.TextColumn("📧 Email", width="large"),
                        "telefono": st.column_config.TextColumn("📞 Teléfono", width="medium")
                    }
                )
            else:
                st.warning("⚠️ No se pueden mostrar los datos de participantes")
            
            # Desasignar participantes con diseño moderno
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
                    
                    if participantes_quitar and st.button("Desasignar Seleccionados", type="secondary"):
                        exitos = 0
                        for participante_str in participantes_quitar:
                            try:
                                nif = participante_str.split(" - ")[0]
                                participante_row = df_participantes[df_participantes["nif"] == nif]
                                if not participante_row.empty:
                                    relacion_id = participante_row.iloc[0]["relacion_id"]
                                    if grupos_service.desasignar_participante_de_grupo(relacion_id):
                                        exitos += 1
                            except Exception as e:
                                st.error(f"Error al desasignar {participante_str}: {e}")
                        
                        if exitos > 0:
                            st.success(f"✅ Se desasignaron {exitos} participantes")
                            st.rerun()
        else:
            st.info("📋 No hay participantes asignados")
        
        # Asignar participantes con jerarquía
        st.markdown("##### Asignar Participantes")
        
        tab1, tab2 = st.tabs(["👤 Individual", "📊 Masivo (Excel)"])
        
        with tab1:
            try:
                df_disponibles = grupos_service.get_participantes_disponibles_jerarquia(grupo_id)
                
                if not df_disponibles.empty:
                    participantes_opciones = {}
                    for _, row in df_disponibles.iterrows():
                        nif = row.get('nif', 'Sin NIF')
                        nombre = row.get('nombre', '')
                        apellidos = row.get('apellidos', '')
                        empresa = row.get('empresa_nombre', 'Sin empresa')
                        participantes_opciones[f"{nif} - {nombre} {apellidos} ({empresa})"] = row["id"]
                    
                    participantes_seleccionados = st.multiselect(
                        "Seleccionar participantes:",
                        participantes_opciones.keys(),
                        key=f"participantes_add_{grupo_id}",
                        help="Solo se muestran participantes de empresas participantes en el grupo"
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
                            st.success(f"✅ Se asignaron {exitos} participantes")
                            st.rerun()
                else:
                    st.info("📋 No hay participantes disponibles en tu ámbito jerárquico")
            except Exception as e:
                st.error(f"Error al cargar participantes disponibles: {e}")
        
        with tab2:
            st.markdown("**📊 Importación masiva desde Excel**")
            with st.container(border=True):
                st.markdown("1. 📁 Sube un archivo Excel con una columna 'dni' o 'nif'")
                st.markdown("2. 🔍 Se buscarán automáticamente en el sistema")
                st.markdown("3. ✅ Solo se asignarán participantes disponibles")
            
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
                        st.error("❌ El archivo debe contener una columna 'dni' o 'nif'")
                    else:
                        st.markdown("**Vista previa del archivo:**")
                        st.dataframe(df_import.head(), use_container_width=True)
                        
                        if st.button("🔄 Procesar Archivo", type="primary"):
                            try:
                                nifs = [str(d).strip() for d in df_import[col_nif] if pd.notna(d)]
                                nifs_validos = [d for d in nifs if validar_dni_cif(d)]
                                
                                df_disp_masivo = grupos_service.get_participantes_disponibles_jerarquia(grupo_id)
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
                                    st.success(f"✅ Se asignaron {asignados} participantes")
                                if errores:
                                    st.warning("⚠️ Errores encontrados:")
                                    for error in errores[:10]:
                                        st.warning(f"• {error}")
                                
                                if asignados > 0:
                                    st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al procesar datos: {e}")
                
                except Exception as e:
                    st.error(f"❌ Error al leer archivo Excel: {e}")
                    
    except Exception as e:
        st.error(f"Error al cargar sección de participantes: {e}")

def mostrar_seccion_costes(grupos_service, grupo_id):
    """Gestión de costes y bonificaciones FUNDAE con validaciones mejoradas."""
    st.markdown("**💰 Costes y Bonificaciones FUNDAE**")
    
    # Obtener datos del grupo para cálculos
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
            st.error(f"❌ Error al calcular límites FUNDAE: {e}")
            limite_boni, tarifa_max = 0, 13.0
    else:
        limite_boni, tarifa_max = 0, 13.0
        st.warning("⚠️ No se pueden calcular límites FUNDAE sin horas y participantes válidos")
    
    # Mostrar información base con métricas modernas
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🎯 Modalidad", modalidad)
        with col2:
            st.metric("👥 Participantes", participantes)
        with col3:
            st.metric("⏱️ Horas", horas)
        with col4:
            st.metric("💰 Límite Bonificación", f"{limite_boni:,.2f} €")
    
    # Formulario de costes con diseño mejorado
    try:
        costes_actuales = grupos_service.get_grupo_costes(grupo_id)
    except Exception as e:
        st.error(f"Error al cargar costes actuales: {e}")
        costes_actuales = {}
    
    with st.form(f"costes_{grupo_id}", clear_on_submit=False):
        st.markdown("##### 💳 Costes de Formación")
        
        col1, col2 = st.columns(2)
        
        with col1:
            costes_directos = st.number_input(
                "💼 Costes Directos (€)",
                value=float(costes_actuales.get("costes_directos", 0)),
                min_value=0.0,
                key=f"directos_{grupo_id}"
            )
            
            costes_indirectos = st.number_input(
                "📋 Costes Indirectos (€)",
                value=float(costes_actuales.get("costes_indirectos", 0)),
                min_value=0.0,
                help="Máximo 30% de costes directos",
                key=f"indirectos_{grupo_id}"
            )
            
            costes_organizacion = st.number_input(
                "🏢 Costes Organización (€)",
                value=float(costes_actuales.get("costes_organizacion", 0)),
                min_value=0.0,
                key=f"organizacion_{grupo_id}"
            )
        
        with col2:
            costes_salariales = st.number_input(
                "👥 Costes Salariales (€)",
                value=float(costes_actuales.get("costes_salariales", 0)),
                min_value=0.0,
                key=f"salariales_{grupo_id}"
            )
            
            cofinanciacion_privada = st.number_input(
                "🏦 Cofinanciación Privada (€)",
                value=float(costes_actuales.get("cofinanciacion_privada", 0)),
                min_value=0.0,
                key=f"cofinanciacion_{grupo_id}"
            )
            
            tarifa_hora = st.number_input(
                "⏰ Tarifa por Hora (€)",
                value=float(costes_actuales.get("tarifa_hora", tarifa_max)),
                min_value=0.0,
                max_value=tarifa_max,
                help=f"Máximo FUNDAE: {tarifa_max} €/h",
                key=f"tarifa_{grupo_id}"
            )
        
        # Validaciones con métricas modernas
        total_costes = costes_directos + costes_indirectos + costes_organizacion + costes_salariales
        limite_calculado = tarifa_hora * horas * participantes
        
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("💰 Total Costes", f"{total_costes:,.2f} €")
            with col2:
                st.metric("🎯 Límite Calculado", f"{limite_calculado:,.2f} €")
            with col3:
                diferencia = limite_calculado - total_costes
                delta_color = "normal" if diferencia >= 0 else "inverse"
                st.metric("📊 Diferencia", f"{diferencia:,.2f} €", delta=f"{diferencia:,.2f} €")
        
        # Validar porcentaje indirectos
        if costes_directos > 0:
            pct_indirectos = (costes_indirectos / costes_directos) * 100
            if pct_indirectos > 30:
                st.error(f"❌ Costes indirectos ({pct_indirectos:.1f}%) superan el 30% permitido")
            else:
                st.success(f"✅ Costes indirectos dentro del límite ({pct_indirectos:.1f}%)")
        
        observaciones_costes = st.text_area(
            "📝 Observaciones",
            value=costes_actuales.get("observaciones", ""),
            height=60,
            key=f"obs_costes_{grupo_id}"
        )
        
        if st.form_submit_button("💾 Guardar Costes", type="primary"):
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
                st.error("❌ No se puede guardar: costes indirectos superan el 30%")
            elif tarifa_hora > tarifa_max:
                st.error(f"❌ No se puede guardar: tarifa/hora supera el máximo ({tarifa_max} €)")
            else:
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
    
    # Sección de bonificaciones mensuales
    st.divider()
    st.markdown("##### 📅 Bonificaciones Mensuales")
    
    try:
        df_bonificaciones = grupos_service.get_grupo_bonificaciones(grupo_id)
        
        if not df_bonificaciones.empty:
            # Mostrar bonificaciones existentes con diseño moderno
            st.dataframe(
                df_bonificaciones[["mes", "importe", "observaciones"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "mes": st.column_config.NumberColumn("📅 Mes", width="small"),
                    "importe": st.column_config.NumberColumn("💰 Importe €", width="medium", format="%.2f"),
                    "observaciones": st.column_config.TextColumn("📝 Observaciones", width="large")
                }
            )
            
            total_bonificado = df_bonificaciones["importe"].sum()
            st.metric("💰 Total Bonificado", f"{total_bonificado:,.2f} €")
        else:
            st.info("📋 No hay bonificaciones registradas")
            
        # Añadir nueva bonificación
        with st.expander("➕ Añadir Bonificación Mensual"):
            with st.form(f"bonificacion_{grupo_id}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    mes_bonif = st.selectbox(
                        "📅 Mes",
                        options=list(range(1, 13)),
                        format_func=lambda x: f"{x:02d} - {['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'][x-1]}",
                        key=f"mes_bonif_{grupo_id}"
                    )
                    
                    importe_bonif = st.number_input(
                        "💰 Importe (€)",
                        min_value=0.0,
                        max_value=limite_boni if limite_boni > 0 else 999999.0,
                        value=0.0,
                        key=f"importe_bonif_{grupo_id}"
                    )
                
                with col2:
                    observaciones_bonif = st.text_area(
                        "📝 Observaciones",
                        height=80,
                        key=f"obs_bonif_{grupo_id}"
                    )
                
                if st.form_submit_button("➕ Añadir Bonificación", type="primary"):
                    # Verificar que el mes no esté duplicado
                    mes_existente = df_bonificaciones[df_bonificaciones["mes"] == mes_bonif] if not df_bonificaciones.empty else pd.DataFrame()
                    
                    if not mes_existente.empty:
                        st.error(f"❌ Ya existe una bonificación para el mes {mes_bonif}")
                    elif importe_bonif <= 0:
                        st.error("❌ El importe debe ser mayor que 0")
                    else:
                        datos_bonif = {
                            "grupo_id": grupo_id,
                            "mes": mes_bonif,
                            "importe": importe_bonif,
                            "observaciones": observaciones_bonif
                        }
                        
                        try:
                            if grupos_service.create_grupo_bonificacion(datos_bonif):
                                st.success("✅ Bonificación añadida correctamente")
                                st.rerun()
                            else:
                                st.error("❌ Error al añadir bonificación")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                            
    except Exception as e:
        st.error(f"Error al cargar bonificaciones: {e}")

# =========================
# FUNCIÓN PRINCIPAL
# =========================

def main(supabase, session_state):
    """Función principal de gestión de grupos con jerarquía mejorada."""
    st.title("👥 Gestión de Grupos FUNDAE")
    st.caption("🎯 Creación y administración de grupos formativos con jerarquía empresarial")
    
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
    
    # Mostrar métricas con información jerárquica
    mostrar_metricas_grupos(df_grupos, session_state)
    
    # Mostrar avisos de grupos pendientes
    grupos_pendientes = get_grupos_pendientes_finalizacion(df_grupos)
    mostrar_avisos_grupos(grupos_pendientes)
    
    st.divider()
    
    # Tabla principal de grupos con diseño moderno
    st.markdown("### 📊 Listado de Grupos")
    
    if df_grupos.empty:
        with st.container(border=True):
            st.info("📋 No hay grupos registrados en tu ámbito.")
            if session_state.role == "gestor":
                st.markdown("Como **gestor**, puedes crear grupos para tu empresa y empresas clientes.")
            elif session_state.role == "admin":
                st.markdown("Como **administrador**, puedes crear grupos para cualquier empresa.")
    else:
        # Preparar datos para mostrar
        df_display = df_grupos.copy()
        
        # Añadir columna de estado con colores
        df_display["Estado"] = df_display.apply(lambda row: determinar_estado_grupo(row.to_dict()), axis=1)
        
        # Seleccionar columnas para mostrar
        columnas_mostrar = [
            "codigo_grupo", "accion_nombre", "modalidad", 
            "fecha_inicio", "fecha_fin_prevista", "localidad", 
            "n_participantes_previstos", "Estado"
        ]
        
        if session_state.role == "admin":
            columnas_mostrar.insert(-1, "empresa_nombre")
        
        columnas_disponibles = [col for col in columnas_mostrar if col in df_display.columns]
        
        # Configuración de columnas moderna
        column_config = {
            "codigo_grupo": st.column_config.TextColumn("🏷️ Código", width="medium"),
            "accion_nombre": st.column_config.TextColumn("📚 Acción Formativa", width="large"),
            "modalidad": st.column_config.TextColumn("🎯 Modalidad", width="small"),
            "fecha_inicio": st.column_config.DateColumn("📅 Inicio", width="small"),
            "fecha_fin_prevista": st.column_config.DateColumn("📅 Fin Previsto", width="small"),
            "localidad": st.column_config.TextColumn("🏘️ Localidad", width="medium"),
            "n_participantes_previstos": st.column_config.NumberColumn("👥 Participantes", width="small"),
            "Estado": st.column_config.TextColumn("📊 Estado", width="small"),
            "empresa_nombre": st.column_config.TextColumn("🏢 Empresa", width="medium")
        }
        
        # Mostrar tabla con selección
        event = st.dataframe(
            df_display[columnas_disponibles],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config=column_config
        )
        
        # Procesar selección
        if event.selection.rows:
            selected_idx = event.selection.rows[0]
            grupo_seleccionado = df_grupos.iloc[selected_idx].to_dict()
            st.session_state.grupo_seleccionado = grupo_seleccionado
    
    st.divider()
    
    # Botones de acción con diseño moderno
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("➕ Crear Nuevo Grupo", type="primary", use_container_width=True):
            st.session_state.grupo_seleccionado = "nuevo"
    
    with col2:
        if st.button("📊 Exportar CSV", use_container_width=True):
            if not df_grupos.empty:
                csv_data = export_csv(df_grupos)
                st.download_button(
                    label="⬇️ Descargar",
                    data=csv_data,
                    file_name=f"grupos_fundae_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No hay datos para exportar")
    
    with col3:
        if st.button("🔄 Actualizar", use_container_width=True):
            grupos_service.limpiar_cache_grupos()
            st.rerun()
    
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

# =========================
# PUNTO DE ENTRADA
# =========================

if __name__ == "__main__":
    # Esta función será llamada desde el sistema principal de navegación
    pass
