import streamlit as st
import pandas as pd
import uuid
from datetime import datetime, date, time
from services.grupos_service import get_grupos_service
from utils import validar_dni_cif, export_csv, export_excel
import re
import math

# =========================
# CONFIGURACIÓN Y CONSTANTES
# =========================

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
    
def validar_uuid_seguro(uuid_str):
    """Valida que un string sea un UUID válido."""
    if not uuid_str:
        return None
    
    try:
        import uuid
        uuid.UUID(str(uuid_str))
        return str(uuid_str)
    except (ValueError, TypeError):
        return None
        
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

def validar_formato_hora(hora_str):
    """Valida que una hora tenga formato HH:MM válido."""
    if not hora_str:
        return False
    
    patron = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
    return bool(re.match(patron, hora_str.strip()))

def comparar_horas(hora_inicio, hora_fin):
    """Compara que hora_fin > hora_inicio."""
    try:
        inicio = datetime.strptime(hora_inicio, "%H:%M")
        fin = datetime.strptime(hora_fin, "%H:%M")
        return fin > inicio
    except:
        return False
# =========================
# COMPONENTES UI MODERNOS
# =========================
def mostrar_metricas_grupos(df_grupos, session_state):
    """Muestra métricas con información jerárquica mejorada."""
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
    
    # Información contextual por rol (sin métricas redundantes)
    if session_state.role == "gestor":
        st.caption("🏢 Mostrando grupos de tu empresa y empresas clientes")
    elif session_state.role == "admin":
        st.caption("🌍 Mostrando todos los grupos del sistema")

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

def construir_horario_fundae_manual(manana_inicio, manana_fin, tarde_inicio, tarde_fin, dias_seleccionados):
    """Construye string de horario en formato FUNDAE desde campos manuales."""
    if not dias_seleccionados:
        return ""
    
    partes = []
    
    # Añadir tramo mañana si está completo
    if manana_inicio and manana_fin:
        partes.append(f"Mañana: {manana_inicio} - {manana_fin}")
    
    # Añadir tramo tarde si está completo
    if tarde_inicio and tarde_fin:
        partes.append(f"Tarde: {tarde_inicio} - {tarde_fin}")
    
    # Añadir días
    if dias_seleccionados:
        dias_str = "-".join(dias_seleccionados)
        partes.append(f"Días: {dias_str}")
    
    return " | ".join(partes)

def crear_selector_horario_manual(key_suffix="", horario_inicial=""):
    """Selector de horarios manual simplificado - estilo plataforma FUNDAE."""
    
    # Parsear horario inicial si existe
    manana_i, manana_f, tarde_i, tarde_f, dias_iniciales = (None, None, None, None, [])
    if horario_inicial:
        manana_i, manana_f, tarde_i, tarde_f, dias_iniciales = parsear_horario_fundae(horario_inicial)
    
    st.markdown("### ⏰ Horarios de Impartición")
    st.caption("Complete los horarios manualmente. Formato requerido: HH:MM (ejemplo: 09:00)")
    
    # Contenedor principal con dos columnas siempre visibles
    col1, col2 = st.columns(2)
    
    # MAÑANAS - Siempre visible
    with col1:
        st.markdown("**🌅 Tramo Mañana**")
        st.caption("Horario matinal (ej: 08:00 - 14:00)")
        
        sub_col1, sub_col2 = st.columns(2)
        with sub_col1:
            manana_inicio = st.text_input(
                "Hora inicio mañana",
                value=manana_i if manana_i else "",
                placeholder="09:00",
                help="Formato HH:MM (ej: 09:00)",
                key=f"manana_inicio_{key_suffix}"
            )
        
        with sub_col2:
            manana_fin = st.text_input(
                "Hora fin mañana",
                value=manana_f if manana_f else "",
                placeholder="14:00",
                help="Formato HH:MM (ej: 14:00)",
                key=f"manana_fin_{key_suffix}"
            )
        
        # Validación en tiempo real para mañanas
        if manana_inicio or manana_fin:
            if manana_inicio and manana_fin:
                if validar_formato_hora(manana_inicio) and validar_formato_hora(manana_fin):
                    if comparar_horas(manana_inicio, manana_fin):
                        st.success(f"✅ Mañana: {manana_inicio} - {manana_fin}")
                    else:
                        st.error("❌ La hora de fin debe ser posterior a la de inicio")
                else:
                    st.warning("⚠️ Formato incorrecto. Use HH:MM")
            elif manana_inicio and not manana_fin:
                st.info("ℹ️ Complete la hora de fin")
            elif manana_fin and not manana_inicio:
                st.info("ℹ️ Complete la hora de inicio")
    
    # TARDES - Siempre visible
    with col2:
        st.markdown("**🌆 Tramo Tarde**")
        st.caption("Horario vespertino (ej: 15:00 - 20:00)")
        
        sub_col1, sub_col2 = st.columns(2)
        with sub_col1:
            tarde_inicio = st.text_input(
                "Hora inicio tarde",
                value=tarde_i if tarde_i else "",
                placeholder="15:00",
                help="Formato HH:MM (ej: 15:00)",
                key=f"tarde_inicio_{key_suffix}"
            )
        
        with sub_col2:
            tarde_fin = st.text_input(
                "Hora fin tarde",
                value=tarde_f if tarde_f else "",
                placeholder="20:00",
                help="Formato HH:MM (ej: 20:00)",
                key=f"tarde_fin_{key_suffix}"
            )
        
        # Validación en tiempo real para tardes
        if tarde_inicio or tarde_fin:
            if tarde_inicio and tarde_fin:
                if validar_formato_hora(tarde_inicio) and validar_formato_hora(tarde_fin):
                    if comparar_horas(tarde_inicio, tarde_fin):
                        st.success(f"✅ Tarde: {tarde_inicio} - {tarde_fin}")
                    else:
                        st.error("❌ La hora de fin debe ser posterior a la de inicio")
                else:
                    st.warning("⚠️ Formato incorrecto. Use HH:MM")
            elif tarde_inicio and not tarde_fin:
                st.info("ℹ️ Complete la hora de fin")
            elif tarde_fin and not tarde_inicio:
                st.info("ℹ️ Complete la hora de inicio")
    
    # Días de la semana - Compacto
    st.markdown("**📅 Días de Impartición**")
    
    # Usar columnas más compactas para días
    cols = st.columns(7)
    dias_seleccionados = []
    
    for i, (dia_corto, dia_largo) in enumerate(zip(DIAS_SEMANA, NOMBRES_DIAS)):
        with cols[i]:
            # Valor por defecto desde horario inicial o L-V
            valor_default = dia_corto in dias_iniciales if dias_iniciales else dia_corto in ["L", "M", "X", "J", "V"]
            
            if st.checkbox(
                dia_corto,
                value=valor_default,
                help=dia_largo,
                key=f"dia_{dia_corto}_{key_suffix}"
            ):
                dias_seleccionados.append(dia_corto)
    
    # Validar que al menos un tramo horario esté completo
    tiene_manana = manana_inicio and manana_fin and validar_formato_hora(manana_inicio) and validar_formato_hora(manana_fin)
    tiene_tarde = tarde_inicio and tarde_fin and validar_formato_hora(tarde_inicio) and validar_formato_hora(tarde_fin)
    
    if not tiene_manana and not tiene_tarde:
        st.warning("⚠️ Complete al menos un tramo horario (mañana o tarde)")
        return ""
    
    if not dias_seleccionados:
        st.warning("⚠️ Seleccione al menos un día de la semana")
        return ""
    
    # Construir horario final solo con tramos válidos
    horario_final = construir_horario_fundae_manual(
        manana_inicio if tiene_manana else None,
        manana_fin if tiene_manana else None,
        tarde_inicio if tiene_tarde else None, 
        tarde_fin if tiene_tarde else None,
        dias_seleccionados
    )
    
    # Mostrar resultado final
    if horario_final:
        st.success(f"✅ **Horario FUNDAE generado:** `{horario_final}`")
    
    return horario_final

# =========================
# FUNCIÓN MOSTRAR_FORMULARIO_GRUPO CORREGIDA COMPLETA
# =========================
def mostrar_formulario_grupo_separado(grupos_service, es_creacion=False, context=""):
    """Formulario con campos reactivos separados del formulario principal."""

    # Obtener grupo desde session_state
    grupo_seleccionado = st.session_state.get("grupo_seleccionado", None)

    # Obtener acciones disponibles
    acciones_dict = grupos_service.get_acciones_dict()
    if not acciones_dict:
        st.error("No hay acciones formativas disponibles. Crea una acción formativa primero.")
        return None

    # Datos iniciales
    if grupo_seleccionado and not es_creacion:
        try:
            grupo_fresh = (
                grupos_service.supabase.table("grupos")
                .select("*")
                .eq("id", grupo_seleccionado.get("id"))
                .execute()
            )
            if grupo_fresh.data:
                datos_grupo = grupo_fresh.data[0]
                estado_actual = determinar_estado_grupo(datos_grupo)
            else:
                datos_grupo = grupo_seleccionado.copy()
                estado_actual = "abierto"
        except Exception as e:
            st.error(f"Error recargando datos del grupo: {e}")
            datos_grupo = grupo_seleccionado.copy()
            estado_actual = "abierto"
    else:
        datos_grupo = {}
        estado_actual = "abierto"
        es_creacion = True

    # Título
    if es_creacion:
        st.markdown("### ➕ Crear Nuevo Grupo")
        st.caption("Complete los datos básicos obligatorios para crear el grupo")
    else:
        codigo = datos_grupo.get("codigo_grupo", "Sin código")
        st.markdown(f"### ✏️ Editar Grupo: {codigo}")
        color_estado = {"abierto": "🟢", "finalizar": "🟡", "finalizado": "✅"}
        st.caption(f"Estado: {color_estado.get(estado_actual.lower(), '⚪')} {estado_actual}")

    # ==============================================
    # SECCIÓN REACTIVA SIN CALLBACKS - USANDO SESSION_STATE
    # ==============================================
    
    st.markdown("### 🎯 Selección Básica")
    with st.container(border=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # 1. ACCIÓN FORMATIVA (SIN CALLBACK)
            acciones_nombres = list(acciones_dict.keys())
            if grupo_seleccionado and datos_grupo.get("accion_formativa_id"):
                accion_actual = next((n for n, i in acciones_dict.items() if i == datos_grupo.get("accion_formativa_id")), None)
                indice_actual = acciones_nombres.index(accion_actual) if accion_actual else 0
            else:
                indice_actual = 0

            accion_formativa = st.selectbox(
                "📚 Acción Formativa *",
                acciones_nombres,
                index=indice_actual,
                help="Selecciona la acción formativa asociada",
                key=f"accion_formativa_select_{context}"
                # ❌ QUITAR: on_change=lambda: st.rerun()
            )
            accion_id = acciones_dict[accion_formativa]
            
            # Detectar cambio usando session_state
            session_key_accion = f"accion_anterior_{context}"
            accion_anterior = st.session_state.get(session_key_accion, None)
            
            if accion_anterior != accion_id:
                st.session_state[session_key_accion] = accion_id
                if accion_anterior is not None:  # No mostrar en primera carga
                    st.info("🔄 Acción formativa actualizada. El código se recalculará automáticamente.")
            
            # Mostrar info de la acción seleccionada
            codigo_accion = grupos_service.get_codigo_accion_numerico(accion_id)
            modalidad_grupo = grupos_service.normalizar_modalidad_fundae(
                grupos_service.get_accion_modalidad(accion_id)
            )
            st.info(f"Código: {codigo_accion} | Modalidad: {modalidad_grupo}")
        
        with col2:
            # 2. EMPRESA PROPIETARIA (SIN CALLBACK TAMBIÉN)
            if grupos_service.rol == "admin":
                empresas_opciones = grupos_service.get_empresas_para_grupos()
                
                if empresas_opciones:
                    empresa_actual = datos_grupo.get("empresa_id")
                    empresa_nombre_actual = None
                    
                    for nombre, id_emp in empresas_opciones.items():
                        if id_emp == empresa_actual:
                            empresa_nombre_actual = nombre
                            break
                    
                    empresa_propietaria = st.selectbox(
                        "🏢 Empresa Propietaria *",
                        list(empresas_opciones.keys()),
                        index=list(empresas_opciones.keys()).index(empresa_nombre_actual) if empresa_nombre_actual else 0,
                        help="Empresa propietaria del grupo",
                        key=f"empresa_prop_{context}"
                        # ❌ QUITAR: on_change=lambda: st.rerun()
                    )
                    empresa_id = empresas_opciones[empresa_propietaria]
                    
                    # Detectar cambio de empresa usando session_state
                    session_key_empresa = f"empresa_anterior_{context}"
                    empresa_anterior = st.session_state.get(session_key_empresa, None)
                    
                    if empresa_anterior != empresa_id:
                        st.session_state[session_key_empresa] = empresa_id
                        if empresa_anterior is not None:
                            st.info("🔄 Empresa actualizada.")
                else:
                    st.error("No hay empresas disponibles")
                    empresa_id = None
            else:
                empresa_id = grupos_service.empresa_id
                st.info("Tu empresa será la propietaria del grupo")

        # 3. CÓDIGO DEL GRUPO (VERSIÓN SIMPLE - COMO TENÍAS ANTES)
        st.markdown("### 🏷️ Código del Grupo")
        with st.container(border=True):
            if es_creacion:
                fecha_para_codigo = safe_date_conversion(datos_grupo.get("fecha_inicio")) or date.today()
            
                try:
                    codigo_sugerido, error_sugerido = grupos_service.generar_codigo_grupo_sugerido_correlativo(
                        accion_id, fecha_para_codigo
                    )
                except Exception as e:
                    codigo_sugerido = "1"
                    error_sugerido = f"Error: {e}"

                if error_sugerido:
                    st.error(f"Error al generar código sugerido: {error_sugerido}")
                    codigo_grupo_display = ""
                else:
                    codigo_accion = grupos_service.get_codigo_accion_numerico(accion_id)
                    codigo_completo_display = f"{codigo_accion}-{codigo_sugerido}"
                
                    colc1, colc2 = st.columns([2, 1])
                    with colc1:
                        st.success(f"✅ Código sugerido: {codigo_completo_display}")
                    with colc2:
                        # Checkbox simple - solo inicializar si no existe
                        checkbox_key = f"usar_sugerido_{context}"
                        if checkbox_key not in st.session_state:
                            st.session_state[checkbox_key] = True
                        
                        usar_sugerido = st.checkbox(
                            "Usar sugerido",
                            key=checkbox_key
                        )
                    
                    if usar_sugerido:
                        codigo_grupo_display = codigo_sugerido
                        # Mostrar el código que se usará
                        st.info(f"📋 Se usará: **{codigo_completo_display}**")
                    else:
                        # Campo manual SOLO cuando no usa sugerido
                        codigo_grupo_display = st.text_input(
                            "Código del Grupo *",
                            value=codigo_sugerido,
                            placeholder="Introduce un número",
                            key=f"codigo_grupo_manual_{context}",  # KEY DIFERENTE
                            help="Introduce cualquier número disponible"
                        )

                # Validación común (si hay código)
                if codigo_grupo_display:
                    try:
                        es_valido, mensaje_error = grupos_service.validar_codigo_grupo_correlativo(
                            codigo_grupo_display, accion_id, fecha_para_codigo
                        )
                        codigo_final = grupos_service.generar_display_codigo_completo(accion_id, codigo_grupo_display)
                        
                        if es_valido:
                            st.success(f"✅ Código '{codigo_final}' válido")
                        else:
                            st.error(f"❌ {mensaje_error}")
                    except Exception as e:
                        st.error(f"❌ Error al validar: {e}")
                    
            else:
                # Modo edición - código no editable
                codigo_grupo = datos_grupo.get("codigo_grupo", "")
                codigo_accion = grupos_service.get_codigo_accion_numerico(accion_id)
                codigo_completo = f"{codigo_accion}-{codigo_grupo}"
                st.info(f"Código actual: **{codigo_completo}**")
                codigo_grupo_display = codigo_grupo

    # 4. EMPRESA RESPONSABLE ANTE FUNDAE (REACTIVA AL CAMBIO)
    if accion_id and empresa_id:
        st.markdown("### 🏢 Empresa Responsable ante FUNDAE")
        with st.container(border=True):
            # Detectar cambios para forzar recálculo
            session_key_empresa_resp = f"empresa_resp_calculada_{context}"
            clave_actual = f"{accion_id}_{empresa_id}"
            clave_anterior = st.session_state.get(session_key_empresa_resp, "")
            
            if clave_anterior != clave_actual:
                st.session_state[session_key_empresa_resp] = clave_actual
                # Limpiar cache de empresa responsable si existe
                if hasattr(grupos_service, '_cache_empresa_responsable'):
                    grupos_service._cache_empresa_responsable.clear()
            
            try:
                empresa_responsable, error_empresa = grupos_service.determinar_empresa_gestora_responsable(
                    accion_id, empresa_id
                )
                
                if empresa_responsable and not error_empresa:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**{empresa_responsable['nombre']}**")
                    with col2:
                        st.write(f"CIF: {empresa_responsable.get('cif', 'N/A')}")
                    with col3:
                        if empresa_responsable['tipo_empresa'] == "GESTORA":
                            st.success("✅ Gestora")
                        else:
                            st.info("ℹ️ Cliente")
                    
                    # Mostrar explicación del cálculo
                    with st.expander("ℹ️ ¿Cómo se determina la empresa responsable?", expanded=False):
                        st.markdown("""
                        **Reglas FUNDAE:**
                        - Si la acción formativa es de una **GESTORA** → La gestora es responsable
                        - Si la acción formativa es de un **CLIENTE_GESTOR** → Su gestora matriz es responsable  
                        - Si la acción formativa es de un **CLIENTE_SAAS** → La empresa propietaria del grupo es responsable
                        """)
                        
                elif error_empresa:
                    st.warning(f"⚠️ {error_empresa}")
                    
            except Exception as e:
                st.error(f"Error al determinar empresa responsable: {e}")
                # Debug info
                with st.expander("🔧 Debug Info", expanded=False):
                    st.write(f"Acción ID: {accion_id}")
                    st.write(f"Empresa ID: {empresa_id}")
                    st.write(f"Error: {str(e)}")

    # ==============================================
    # FORMULARIO PRINCIPAL (CAMPOS ESTÁTICOS)
    # ==============================================
    
    form_key = f"grupo_form_{datos_grupo.get('id', 'nuevo')}"
    with st.form(form_key, clear_on_submit=False):
        
        # SECCIÓN 1: DATOS BÁSICOS
        with st.container(border=True):
            st.markdown("### 📋 Datos del Grupo")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Código manual si no usa sugerido
                if es_creacion and not st.session_state.get(f"usar_sugerido_{context}", True):
                    codigo_grupo = st.text_input(
                        "Código personalizado *",
                        value=codigo_grupo_display,
                        placeholder="Introduce un número",
                        key=f"codigo_manual_{context}"
                    )
                else:
                    codigo_grupo = codigo_grupo_display
                    if codigo_grupo:
                        st.text_input(
                            "Código del grupo",
                            value=f"{codigo_accion}-{codigo_grupo}",
                            disabled=True
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
            
            with col2:
                # Localidad y Provincia
                try:
                    provincias = grupos_service.get_provincias()
                    prov_opciones = {p["nombre"]: p["id"] for p in provincias}
                    
                    provincia_actual = datos_grupo.get("provincia") if datos_grupo else None
                    
                    provincia_sel = st.selectbox(
                        "🗺️ Provincia *",
                        options=list(prov_opciones.keys()),
                        index=list(prov_opciones.keys()).index(provincia_actual) if provincia_actual in prov_opciones else 0,
                        help="Provincia de impartición"
                    )
                    
                    if provincia_sel:
                        localidades = grupos_service.get_localidades_por_provincia(prov_opciones[provincia_sel])
                        loc_nombres = [l["nombre"] for l in localidades]
                        
                        localidad_actual = datos_grupo.get("localidad") if datos_grupo else None
                        
                        localidad_sel = st.selectbox(
                            "🏘️ Localidad *",
                            options=loc_nombres,
                            index=loc_nombres.index(localidad_actual) if localidad_actual in loc_nombres else 0 if loc_nombres else -1,
                            help="Localidad de impartición"
                        )
                    else:
                        localidad_sel = None
                except Exception as e:
                    st.error(f"Error al cargar provincias/localidades: {e}")
                    provincia_sel = st.text_input("🗺️ Provincia *", value=datos_grupo.get("provincia", ""))
                    localidad_sel = st.text_input("🏘️ Localidad *", value=datos_grupo.get("localidad", ""))
                
                cp = st.text_input(
                    "📮 Código Postal",
                    value=datos_grupo.get("cp", ""),
                    help="Código postal de impartición"
                )

                responsable = st.text_input(
                    "👤 Responsable del Grupo",
                    value=str(datos_grupo.get("responsable") or ""),
                    help="Persona responsable del grupo (opcional)"
                )
                
                telefono_contacto = st.text_input(
                    "📞 Teléfono de Contacto", 
                    value=str(datos_grupo.get("telefono_contacto") or ""), 
                    help="Teléfono de contacto del responsable (opcional)"
                )
            
            # Campos de área completa
            lugar_imparticion = st.text_area(
                "📍 Lugar de Impartición",
                value=datos_grupo.get("lugar_imparticion", ""),
                height=60,
                help="Descripción detallada del lugar donde se impartirá la formación"
            )
            
            observaciones = st.text_area(
                "📝 Observaciones",
                value=datos_grupo.get("observaciones", ""),
                height=80,
                help="Información adicional sobre el grupo (opcional)"
            )

        # SECCIÓN 2: HORARIOS
        with st.container(border=True):
            horario_actual = datos_grupo.get("horario", "")
            
            if horario_actual and not es_creacion:
                st.info(f"**Horario actual:** {horario_actual}")
            
            horario_nuevo = crear_selector_horario_manual(
                f"horario_{datos_grupo.get('id', 'nuevo')}", 
                horario_actual if horario_actual else ""
            )

        # SECCIÓN 3: FINALIZACIÓN (si aplica)
        mostrar_finalizacion = (
            not es_creacion
            and (
                estado_actual in ["FINALIZAR", "FINALIZADO"]
                or (fecha_fin_prevista and fecha_fin_prevista <= date.today())
            )
        )
    
        datos_finalizacion = {}
        if mostrar_finalizacion:
            with st.container(border=True):
                st.markdown("### 🏁 Datos de Finalización")
                
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
                
                if n_finalizados > 0 and (n_aptos + n_no_aptos != n_finalizados):
                    st.error(f"La suma de aptos ({n_aptos}) + no aptos ({n_no_aptos}) debe ser igual a finalizados ({n_finalizados})")
                elif n_finalizados > 0:
                    st.success("✅ Números de finalización coherentes")
                
                datos_finalizacion = {
                    "fecha_fin": fecha_fin_real.isoformat(),
                    "n_participantes_finalizados": n_finalizados,
                    "n_aptos": n_aptos,
                    "n_no_aptos": n_no_aptos
                }

        # VALIDACIONES Y BOTONES
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
        if grupos_service.rol == "admin" and not empresa_id:
            errores.append("Empresa propietaria requerida")
        if not horario_nuevo:
            errores.append("Horario requerido")

        if errores:
            st.error("Faltan campos obligatorios:")
            for error in errores:
                st.error(f"• {error}")

        # Botones de acción
        st.divider()
        submitted = False
        cancelar = False
        recargar = False

        if es_creacion:
            col1, col2 = st.columns([2, 1])
            with col1:
                submitted = st.form_submit_button("➕ Crear Grupo", type="primary", use_container_width=True)
            with col2:
                cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                submitted = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
            with col2:
                recargar = st.form_submit_button("🔄 Recargar", use_container_width=True)
            with col3:
                cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)

        # Procesar formulario
        if submitted and not errores:
            datos_para_guardar = {
                "accion_formativa_id": accion_id,
                "modalidad": modalidad_grupo,
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin_prevista": fecha_fin_prevista.isoformat() if fecha_fin_prevista else None,
                "provincia": provincia_sel,
                "localidad": localidad_sel,
                "cp": cp,
                "responsable": responsable.strip() if responsable and responsable.strip() else None,
                "telefono_contacto": telefono_contacto.strip() if telefono_contacto and telefono_contacto.strip() else None,
                "lugar_imparticion": lugar_imparticion.strip() if lugar_imparticion and lugar_imparticion.strip() else None,
                "observaciones": observaciones.strip() if observaciones and observaciones.strip() else None,
                "n_participantes_previstos": n_participantes_previstos,
                "horario": horario_nuevo if horario_nuevo else None,
            }

            if es_creacion:
                datos_para_guardar["codigo_grupo"] = codigo_grupo
                datos_para_guardar["empresa_id"] = empresa_id
                datos_para_guardar["estado"] = "abierto"
            else:
                datos_para_guardar["estado"] = determinar_estado_grupo(datos_grupo).lower()

            if datos_finalizacion:
                datos_para_guardar.update(datos_finalizacion)

            try:
                if es_creacion:
                    exito, grupo_id = grupos_service.create_grupo_con_jerarquia_mejorado(datos_para_guardar)
                    if exito:
                        st.success("✅ Grupo creado correctamente")
                        grupo_creado = (
                            grupos_service.supabase.table("grupos")
                            .select("*")
                            .eq("id", grupo_id)
                            .execute()
                        )
                        if grupo_creado.data:
                            st.session_state.grupo_seleccionado = grupo_creado.data[0]
                        st.rerun()
                    else:
                        st.error("❌ Error al crear grupo")
                else:
                    res = (
                        grupos_service.supabase.table("grupos")
                        .update(datos_para_guardar)
                        .eq("id", datos_grupo["id"])
                        .execute()
                    )
                    if res.data:
                        st.success("✅ Cambios guardados correctamente")
                        st.session_state.grupo_seleccionado = res.data[0]
                        st.rerun()
                    else:
                        st.error("❌ No se guardaron cambios en el grupo")
            except Exception as e:
                st.error(f"❌ Error al procesar grupo: {e}")

        elif cancelar:
            st.session_state.grupo_seleccionado = None
            st.rerun()
            
        elif recargar and not es_creacion:
            try:
                grupo_recargado = (
                    grupos_service.supabase.table("grupos")
                    .select("*")
                    .eq("id", datos_grupo["id"])
                    .execute()
                )
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
        mostrar_seccion_costes_por_empresa_schema_real(grupos_service, grupo_id)

def mostrar_seccion_tutores_jerarquia(grupos_service, grupo_id):
    """CORREGIDO: Usando tabla tutores_grupos (N:N)."""
    st.markdown("**Gestión de Tutores con Jerarquía**")
    
    grupo_id_limpio = validar_uuid_seguro(grupo_id)
    if not grupo_id_limpio:
        st.error("ID de grupo no válido")
        return
    
    try:
        # CORRECCIÓN: Usar tabla de relación tutores_grupos
        tutores_res = grupos_service.supabase.table("tutores_grupos").select("""
            id, tutor_id, fecha_asignacion,
            tutor:tutores(id, nombre, apellidos, email, especialidad)
        """).eq("grupo_id", grupo_id_limpio).execute()
        
        df_tutores = pd.DataFrame(tutores_res.data or [])
        
        if not df_tutores.empty:
            st.markdown("##### Tutores Asignados")
            
            for _, row in df_tutores.iterrows():
                tutor = row.get("tutor", {})
                if isinstance(tutor, dict):
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            nombre_completo = f"{tutor.get('nombre', '')} {tutor.get('apellidos', '')}".strip()
                            st.write(f"**{nombre_completo}**")
                            st.caption(f"📧 {tutor.get('email', 'N/A')} | 🎯 {tutor.get('especialidad', 'Sin especialidad')}")
                        with col2:
                            if st.button("Quitar", key=f"quitar_tutor_{row.get('id')}", type="secondary"):
                                try:
                                    # CORRECCIÓN: Eliminar de tabla de relación
                                    grupos_service.supabase.table("tutores_grupos").delete().eq("id", row.get("id")).execute()
                                    st.success("Tutor eliminado")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
        else:
            st.info("📋 No hay tutores asignados")
        
        # Asignar nuevos tutores
        st.markdown("##### Añadir Tutores")
        
        try:
            # CORRECCIÓN: Buscar tutores disponibles (no asignados a este grupo)
            tutores_grupo = grupos_service.supabase.table("tutores_grupos").select("tutor_id").eq("grupo_id", grupo_id_limpio).execute()
            tutores_asignados = [t["tutor_id"] for t in (tutores_grupo.data or [])]
            
            # Obtener tutores según jerarquía
            if grupos_service.rol == "admin":
                query = grupos_service.supabase.table("tutores").select("""
                    id, nombre, apellidos, email, especialidad, empresa_id,
                    empresa:empresas(nombre)
                """)
            elif grupos_service.rol == "gestor" and grupos_service.empresa_id:
                # Tutores de su empresa y empresas clientes
                empresa_id_limpio = validar_uuid_seguro(grupos_service.empresa_id)
                if empresa_id_limpio:
                    clientes_res = grupos_service.supabase.table("empresas").select("id").eq("empresa_matriz_id", empresa_id_limpio).execute()
                    empresas_gestionables = [empresa_id_limpio]
                    if clientes_res.data:
                        empresas_gestionables.extend([c["id"] for c in clientes_res.data])
                    
                    query = grupos_service.supabase.table("tutores").select("""
                        id, nombre, apellidos, email, especialidad, empresa_id,
                        empresa:empresas(nombre)
                    """).in_("empresa_id", empresas_gestionables)
                else:
                    query = None
            else:
                query = None
            
            if query:
                if tutores_asignados:
                    query = query.not_.in_("id", tutores_asignados)
                
                disponibles_res = query.execute()
                df_disponibles = pd.DataFrame(disponibles_res.data or [])
                
                if not df_disponibles.empty:
                    opciones_tutores = {}
                    for _, row in df_disponibles.iterrows():
                        empresa_nombre = row.get("empresa", {}).get("nombre", "Sin empresa") if isinstance(row.get("empresa"), dict) else "Sin empresa"
                        nombre_completo = f"{row.get('nombre', '')} {row.get('apellidos', '')} - {row.get('especialidad', 'Sin especialidad')} ({empresa_nombre})"
                        opciones_tutores[nombre_completo] = row["id"]
                    
                    tutores_seleccionados = st.multiselect(
                        "Seleccionar tutores:",
                        opciones_tutores.keys(),
                        key=f"tutores_add_{grupo_id_limpio}"
                    )
                    
                    if tutores_seleccionados and st.button("Asignar Tutores", type="primary"):
                        exitos = 0
                        for tutor_nombre in tutores_seleccionados:
                            tutor_id = opciones_tutores[tutor_nombre]
                            try:
                                # CORRECCIÓN: Insertar en tabla de relación N:N
                                grupos_service.supabase.table("tutores_grupos").insert({
                                    "grupo_id": grupo_id_limpio,
                                    "tutor_id": tutor_id,
                                    "fecha_asignacion": datetime.utcnow().isoformat()
                                }).execute()
                                exitos += 1
                            except Exception as e:
                                st.error(f"Error al asignar {tutor_nombre}: {e}")
                        
                        if exitos > 0:
                            st.success(f"Se asignaron {exitos} tutores")
                            st.rerun()
                else:
                    st.info("No hay tutores disponibles")
            else:
                st.info("No hay tutores disponibles en tu ámbito")
                
        except Exception as e:
            st.error(f"Error cargando tutores disponibles: {e}")
            
    except Exception as e:
        st.error(f"Error en sección de tutores: {e}")
        
def mostrar_seccion_centro_gestor(grupos_service, grupo_id):
    """Centro Gestor simplificado usando empresas marcadas."""
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
            # Ver centro actual
            centro_actual = grupos_service.get_centro_gestor_empresa(grupo_id)
            
            if centro_actual:
                st.success(f"✅ Centro gestor actual: **{centro_actual['nombre']}**")
                st.caption(f"CIF: {centro_actual['cif']}")
            
            # Obtener empresas que pueden ser centro gestor
            empresas_centro = grupos_service.get_empresas_centro_gestor_disponibles()
            
            if empresas_centro:
                empresa_sel = st.selectbox(
                    "Seleccionar empresa como Centro Gestor",
                    options=list(empresas_centro.keys()),
                    help="Solo empresas marcadas como 'Centro Gestor'"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Asignar Centro Gestor", type="primary"):
                        empresa_id = empresas_centro[empresa_sel]
                        ok = grupos_service.asignar_empresa_como_centro_gestor(grupo_id, empresa_id)
                        if ok:
                            st.success("Centro gestor asignado")
                            st.rerun()
                
                with col2:
                    if centro_actual and st.button("❌ Quitar Centro Gestor"):
                        ok = grupos_service.quitar_centro_gestor(grupo_id)
                        if ok:
                            st.success("Centro gestor eliminado")
                            st.rerun()
            else:
                st.warning("No hay empresas marcadas como Centro Gestor disponibles")
        else:
            st.info("Centro gestor solo para Teleformación y Mixta")
            
    except Exception as e:
        st.error(f"Error en sección Centro Gestor: {e}")

def mostrar_seccion_empresas_jerarquia(grupos_service, grupo_id):
    """Gestión de empresas participantes usando empresas_grupos."""
    st.markdown("**Empresas Participantes con Jerarquía**")
    
    grupo_id_limpio = validar_uuid_seguro(grupo_id)
    if not grupo_id_limpio:
        st.error("ID de grupo no válido")
        return
    
    try:
        # Usar tabla de relación empresas_grupos
        empresas_res = grupos_service.supabase.table("empresas_grupos").select("""
            id, empresa_id, fecha_asignacion,
            empresa:empresas(id, nombre, cif, tipo_empresa)
        """).eq("grupo_id", grupo_id_limpio).execute()
        
        df_empresas = pd.DataFrame(empresas_res.data or [])
        
        if not df_empresas.empty:
            st.markdown("##### Empresas Asignadas")
            for _, row in df_empresas.iterrows():
                empresa = row.get("empresa", {})
                if isinstance(empresa, dict):
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"**{empresa.get('nombre', 'Sin nombre')}**")
                            tipo = empresa.get('tipo_empresa', 'Sin tipo')
                            cif = empresa.get('cif', 'Sin CIF')
                            fecha = row.get('fecha_asignacion', '')
                            if isinstance(fecha, str) and len(fecha) > 10:
                                fecha = fecha[:10]
                            st.caption(f"🏢 {tipo} | 📄 {cif} | 📅 {fecha}")
                        with col2:
                            if st.button("Quitar", key=f"quitar_empresa_{row.get('id')}", type="secondary"):
                                try:
                                    grupos_service.supabase.table("empresas_grupos").delete().eq("id", row.get("id")).execute()
                                    st.success("Empresa eliminada")
                                    st.rerun()
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
    """CORREGIDO: Usando tabla participantes_grupos (N:N) con validacion de UUIDs."""
    st.markdown("**Participantes del Grupo con Jerarquía**")
    
    grupo_id_limpio = validar_uuid_seguro(grupo_id)
    if not grupo_id_limpio:
        st.error("ID de grupo no válido")
        return
    
    try:
        # CORRECCIÓN: Usar tabla de relación participantes_grupos
        participantes_res = grupos_service.supabase.table("participantes_grupos").select("""
            id, participante_id, fecha_asignacion,
            participante:participantes(id, nif, nombre, apellidos, email, telefono)
        """).eq("grupo_id", grupo_id_limpio).execute()
        
        df_participantes = pd.DataFrame(participantes_res.data or [])
        
        if not df_participantes.empty:
            st.markdown("##### Participantes Asignados")
            
            # Procesar datos de participantes
            participantes_data = []
            for _, row in df_participantes.iterrows():
                participante = row.get("participante", {})
                if isinstance(participante, dict):
                    participantes_data.append({
                        "relacion_id": row.get("id"),
                        "nif": participante.get("nif", ""),
                        "nombre": participante.get("nombre", ""),
                        "apellidos": participante.get("apellidos", ""),
                        "email": participante.get("email", ""),
                        "telefono": participante.get("telefono", ""),
                        "fecha_asignacion": row.get("fecha_asignacion", "")
                    })
            
            if participantes_data:
                df_display = pd.DataFrame(participantes_data)
                st.dataframe(
                    df_display[["nif", "nombre", "apellidos", "email", "telefono"]],
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
                
                # Desasignar participantes
                with st.expander("❌ Desasignar Participantes"):
                    for _, row in df_display.iterrows():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"{row['nif']} - {row['nombre']} {row['apellidos']}")
                        with col2:
                            if st.button("Quitar", key=f"quitar_part_{row['relacion_id']}", type="secondary"):
                                try:
                                    # CORRECCIÓN: Eliminar de tabla de relación
                                    grupos_service.supabase.table("participantes_grupos").delete().eq("id", row['relacion_id']).execute()
                                    st.success("Participante desasignado")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
        else:
            st.info("📋 No hay participantes asignados")
        
        # Asignar nuevos participantes
        st.markdown("##### Asignar Participantes")
        
        try:
            # CORRECCIÓN: Buscar participantes disponibles (sin grupo asignado en la relación)
            participantes_con_grupo = grupos_service.supabase.table("participantes_grupos").select("participante_id").execute()
            participantes_asignados_raw = [p["participante_id"] for p in (participantes_con_grupo.data or [])]
            
            # ✅ VALIDAR UUIDs - Filtrar solo UUIDs válidos
            participantes_asignados = []
            for uuid_str in participantes_asignados_raw:
                uuid_limpio = validar_uuid_seguro(uuid_str)
                if uuid_limpio:
                    participantes_asignados.append(uuid_limpio)
            
            # Obtener empresas participantes del grupo
            empresas_grupo = grupos_service.supabase.table("empresas_grupos").select("empresa_id").eq("grupo_id", grupo_id_limpio).execute()
            empresas_participantes_raw = [e["empresa_id"] for e in (empresas_grupo.data or [])]
            
            # ✅ VALIDAR UUIDs - Filtrar solo UUIDs válidos
            empresas_participantes = []
            for uuid_str in empresas_participantes_raw:
                uuid_limpio = validar_uuid_seguro(uuid_str)
                if uuid_limpio:
                    empresas_participantes.append(uuid_limpio)
            
            if empresas_participantes:
                # ✅ CONSTRUIR CONSULTA CON UUIDs VALIDADOS
                query = grupos_service.supabase.table("participantes").select("""
                    id, nif, nombre, apellidos, email, empresa_id,
                    empresa:empresas(nombre)
                """).in_("empresa_id", empresas_participantes)
                
                if participantes_asignados:
                    query = query.not_.in_("id", participantes_asignados)
                
                disponibles_res = query.execute()
                df_disponibles = pd.DataFrame(disponibles_res.data or [])
                
                if not df_disponibles.empty:
                    opciones_participantes = {}
                    for _, row in df_disponibles.iterrows():
                        empresa_nombre = row.get("empresa", {}).get("nombre", "Sin empresa") if isinstance(row.get("empresa"), dict) else "Sin empresa"
                        nombre_completo = f"{row.get('nif', 'Sin NIF')} - {row.get('nombre', '')} {row.get('apellidos', '')} ({empresa_nombre})"
                        opciones_participantes[nombre_completo] = row["id"]
                    
                    participantes_seleccionados = st.multiselect(
                        "Seleccionar participantes:",
                        opciones_participantes.keys(),
                        key=f"participantes_add_{grupo_id_limpio}"
                    )
                    
                    if participantes_seleccionados and st.button("Asignar Seleccionados", type="primary"):
                        exitos = 0
                        for participante_nombre in participantes_seleccionados:
                            participante_id = opciones_participantes[participante_nombre]
                            try:
                                # CORRECCIÓN: Insertar en tabla de relación N:N
                                grupos_service.supabase.table("participantes_grupos").insert({
                                    "grupo_id": grupo_id_limpio,
                                    "participante_id": participante_id,
                                    "fecha_asignacion": datetime.utcnow().isoformat()
                                }).execute()
                                exitos += 1
                            except Exception as e:
                                st.error(f"Error al asignar {participante_nombre}: {e}")
                        
                        if exitos > 0:
                            st.success(f"Se asignaron {exitos} participantes")
                            st.rerun()
                else:
                    st.info("No hay participantes disponibles")
            else:
                st.warning("Primero asigna empresas participantes al grupo")
                
        except Exception as e:
            # ✅ DEBUGGING MEJORADO
            st.error(f"Error cargando participantes disponibles: {e}")
            
            # Solo para debugging - quitar después de solucionar
            with st.expander("🔧 Debug Info", expanded=False):
                st.write("Empresas participantes raw:", empresas_participantes_raw if 'empresas_participantes_raw' in locals() else "No disponible")
                st.write("Empresas válidas:", empresas_participantes if 'empresas_participantes' in locals() else "No disponible") 
                st.write("Participantes asignados raw:", participantes_asignados_raw if 'participantes_asignados_raw' in locals() else "No disponible")
                st.write("Participantes válidos:", participantes_asignados if 'participantes_asignados' in locals() else "No disponible")
        
        # Importación masiva desde Excel
        st.divider()
        st.markdown("##### 📊 Importación Masiva")
        
        tab1, tab2 = st.tabs(["📤 Instrucciones", "📁 Subir Archivo"])
        
        with tab1:
            st.markdown("**📊 Importación masiva desde Excel**")
            with st.container(border=True):
                st.markdown("1. 📁 Sube un archivo Excel con una columna 'dni' o 'nif'")
                st.markdown("2. 🔍 Se buscarán automáticamente en el sistema")
                st.markdown("3. ✅ Solo se asignarán participantes disponibles")
        
        with tab2:
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

def mostrar_seccion_costes_por_empresa_schema_real(grupos_service, grupo_id):
    """
    CORREGIDO: Usando las tablas del schema real con validaciones robustas.
    """
    st.markdown("### 💰 Costes y Bonificaciones por Empresa")
    st.caption("Cada empresa participante gestiona sus propios costes y bonificaciones de forma independiente")
    
    try:
        # Obtener empresas participantes del grupo (VALIDACIÓN ROBUSTA)
        empresas_grupo_res = grupos_service.supabase.table("empresas_grupos").select("""
            id, empresa_id, fecha_asignacion,
            empresa:empresas(id, nombre, cif, tipo_empresa)
        """).eq("grupo_id", grupo_id).execute()
        
        if not empresas_grupo_res.data:
            st.warning("⚠️ No hay empresas participantes. Añade empresas primero en la sección anterior.")
            return
        
        # FILTRAR empresas válidas (con datos no None)
        empresas_validas = []
        for empresa_grupo in empresas_grupo_res.data:
            if (empresa_grupo and 
                isinstance(empresa_grupo, dict) and 
                empresa_grupo.get("empresa") and 
                isinstance(empresa_grupo.get("empresa"), dict)):
                empresas_validas.append(empresa_grupo)
        
        if not empresas_validas:
            st.error("❌ No se encontraron empresas con datos válidos")
            return
        
        # Obtener datos del grupo para cálculos FUNDAE
        grupo_info = grupos_service.supabase.table("grupos").select("""
            modalidad, n_participantes_previstos,
            accion_formativa:acciones_formativas(num_horas)
        """).eq("id", grupo_id).execute()
        
        if not grupo_info.data:
            st.error("❌ No se pudo cargar información del grupo")
            return
            
        datos_grupo = grupo_info.data[0] or {}
        modalidad = datos_grupo.get("modalidad", "PRESENCIAL")
        participantes = datos_grupo.get("n_participantes_previstos", 1) or 1
        
        # VALIDACIÓN ROBUSTA de accion_formativa
        accion_formativa = datos_grupo.get("accion_formativa")
        if accion_formativa and isinstance(accion_formativa, dict):
            horas = accion_formativa.get("num_horas", 0) or 0
        else:
            horas = 0
        
        # Calcular límite FUNDAE con valores por defecto seguros
        try:
            limite_boni_base, tarifa_max = grupos_service.calcular_limite_fundae(modalidad, horas, participantes)
        except Exception as e:
            st.warning(f"⚠️ Error al calcular límites FUNDAE: {e}")
            limite_boni_base, tarifa_max = 0.0, 13.0
        
        # Métricas generales del grupo
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🎯 Modalidad", modalidad)
            with col2:
                st.metric("👥 Participantes", participantes)
            with col3:
                st.metric("⏱️ Horas", horas)
            with col4:
                st.metric("💰 Tarifa Max", f"{tarifa_max:.2f} €/h")
        
        # PESTAÑAS PARA CADA EMPRESA
        empresa_nombres = []
        empresa_data_map = {}
        
        for empresa_grupo in empresas_validas:
            empresa_data = empresa_grupo.get("empresa", {})
            tipo_icon = {"GESTORA": "🏛️", "CLIENTE_GESTOR": "🏢", "CLIENTE_SAAS": "💼"}.get(
                empresa_data.get("tipo_empresa", ""), "🏢"
            )
            nombre_empresa = empresa_data.get("nombre", "Sin nombre")
            nombre_tab = f"{tipo_icon} {nombre_empresa[:20]}..."
            empresa_nombres.append(nombre_tab)
            empresa_data_map[nombre_tab] = empresa_grupo
        
        # Crear tabs dinámicas
        if len(empresa_nombres) == 1:
            procesar_empresa_individual_schema_real(grupos_service, empresa_data_map[empresa_nombres[0]], tarifa_max, horas, participantes)
        else:
            tabs_empresas = st.tabs(empresa_nombres)
            for i, tab in enumerate(tabs_empresas):
                with tab:
                    empresa_data = empresa_data_map[empresa_nombres[i]]
                    procesar_empresa_individual_schema_real(grupos_service, empresa_data, tarifa_max, horas, participantes)
        
    except Exception as e:
        st.error(f"❌ Error en sección de costes por empresa: {e}")
        # Debug detallado
        with st.expander("🔧 Debug Info", expanded=False):
            st.write(f"Grupo ID: {grupo_id}")
            st.write(f"Error completo: {str(e)}")
            import traceback
            st.code(traceback.format_exc())


def procesar_empresa_individual_schema_real(grupos_service, empresa_grupo_data, tarifa_max, horas, participantes):
    """
    CORREGIDO: Procesamiento individual usando campos exactos del schema.
    """
    # VALIDACIONES INICIALES ROBUSTAS
    if not empresa_grupo_data or not isinstance(empresa_grupo_data, dict):
        st.error("❌ Datos de empresa-grupo no válidos")
        return
        
    empresa_grupo_id = empresa_grupo_data.get("id")
    if not empresa_grupo_id:
        st.error("❌ ID de empresa-grupo no encontrado")
        return

    empresa_data = empresa_grupo_data.get("empresa", {})
    if not isinstance(empresa_data, dict):
        st.error("❌ Datos de empresa no válidos")
        return
        
    empresa_nombre = empresa_data.get("nombre", "Sin nombre")
    empresa_tipo = empresa_data.get("tipo_empresa", "N/D")
    empresa_cif = empresa_data.get("cif", "N/A")

    # Header
    st.markdown(f"#### 🏢 {empresa_nombre}")
    st.caption(f"Tipo: {empresa_tipo} | CIF: {empresa_cif}")

    # === COSTES DE ESTA EMPRESA (tabla empresa_grupo_costes) ===
    st.markdown("##### 💳 Costes de Formación")

    try:
        # USAR CAMPOS EXACTOS DEL SCHEMA
        costes_empresa_res = grupos_service.supabase.table("empresa_grupo_costes").select("*").eq("empresa_grupo_id", empresa_grupo_id).execute()
        costes_actuales = (costes_empresa_res.data[0] if costes_empresa_res.data else None) or {}
    except Exception as e:
        st.warning(f"⚠️ Error al cargar costes: {e}")
        costes_actuales = {}

    # DEFINIR VARIABLES FUERA DEL FORMULARIO PARA ACCESO GLOBAL
    costes_directos_inicial = float(costes_actuales.get("costes_directos", 0) or 0)
    costes_indirectos_inicial = float(costes_actuales.get("costes_indirectos", 0) or 0)
    costes_organizacion_inicial = float(costes_actuales.get("costes_organizacion", 0) or 0)
    costes_salariales_inicial = float(costes_actuales.get("costes_salariales", 0) or 0)
    cofinanciacion_privada_inicial = float(costes_actuales.get("cofinanciacion_privada", 0) or 0)
    tarifa_hora_inicial = float(costes_actuales.get("tarifa_hora", tarifa_max) or tarifa_max)
    
    # CALCULAR TOTALES INICIALES
    total_costes_empresa = costes_directos_inicial + costes_indirectos_inicial + costes_organizacion_inicial + costes_salariales_inicial
    limite_calculado_empresa = tarifa_hora_inicial * horas * participantes

    with st.form(f"costes_empresa_{empresa_grupo_id}", clear_on_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            # USAR NOMBRES EXACTOS DEL SCHEMA
            costes_directos = st.number_input(
                "💼 Costes Directos (€)",
                value=costes_directos_inicial,
                min_value=0.0,
                key=f"directos_emp_{empresa_grupo_id}"
            )

            costes_indirectos = st.number_input(
                "📋 Costes Indirectos (€)",
                value=costes_indirectos_inicial,
                min_value=0.0,
                help="Máximo 30% de costes directos",
                key=f"indirectos_emp_{empresa_grupo_id}"
            )

            costes_organizacion = st.number_input(
                "🏢 Costes Organización (€)",
                value=costes_organizacion_inicial,
                min_value=0.0,
                key=f"organizacion_emp_{empresa_grupo_id}"
            )

        with col2:
            costes_salariales = st.number_input(
                "👥 Costes Salariales (€)",
                value=costes_salariales_inicial,
                min_value=0.0,
                key=f"salariales_emp_{empresa_grupo_id}"
            )

            cofinanciacion_privada = st.number_input(
                "🏦 Cofinanciación Privada (€)",
                value=cofinanciacion_privada_inicial,
                min_value=0.0,
                key=f"cofinanciacion_emp_{empresa_grupo_id}"
            )

            tarifa_hora = st.number_input(
                "⏰ Tarifa por Hora (€)",
                value=tarifa_hora_inicial,
                min_value=0.0,
                max_value=tarifa_max,
                help=f"Máximo FUNDAE: {tarifa_max} €/h",
                key=f"tarifa_emp_{empresa_grupo_id}"
            )

        # RECALCULAR TOTALES CON VALORES DEL FORMULARIO
        total_costes_formulario = costes_directos + costes_indirectos + costes_organizacion + costes_salariales
        limite_calculado_formulario = tarifa_hora * horas * participantes

        # Métricas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Total Costes", f"{total_costes_formulario:,.2f} €")
        with col2:
            st.metric("🎯 Límite Calculado", f"{limite_calculado_formulario:,.2f} €")
        with col3:
            diferencia = limite_calculado_formulario - total_costes_formulario
            st.metric("📊 Diferencia", f"{diferencia:,.2f} €")

        # Validaciones
        errores_empresa = []
        if costes_directos > 0:
            pct_indirectos = (costes_indirectos / costes_directos) * 100
            if pct_indirectos > 30:
                errores_empresa.append(f"Costes indirectos ({pct_indirectos:.1f}%) superan el 30% permitido")

        if tarifa_hora > tarifa_max:
            errores_empresa.append(f"Tarifa/hora ({tarifa_hora:.2f}€) supera el máximo ({tarifa_max:.2f}€)")

        if errores_empresa:
            st.error("❌ Errores encontrados:")
            for err in errores_empresa:
                st.error(f"• {err}")

        submit_costes = st.form_submit_button("💾 Guardar Costes", type="primary", disabled=bool(errores_empresa))

        if submit_costes and not errores_empresa:
            # USAR CAMPOS EXACTOS DEL SCHEMA
            datos_costes_empresa = {
                "empresa_grupo_id": empresa_grupo_id,
                "costes_directos": costes_directos,
                "costes_indirectos": costes_indirectos,
                "costes_organizacion": costes_organizacion,
                "costes_salariales": costes_salariales,
                "cofinanciacion_privada": cofinanciacion_privada,
                "tarifa_hora": tarifa_hora,
                "modalidad": modalidad,  # Campo según schema
                "total_costes_formacion": total_costes_formulario,
                "limite_maximo_bonificacion": limite_calculado_formulario,
                "observaciones": None,  # Campo según schema
                "updated_at": "now()"
            }
            
            try:
                if costes_actuales and costes_actuales.get("id"):
                    # ACTUALIZAR EXISTENTE
                    res = grupos_service.supabase.table("empresa_grupo_costes").update(datos_costes_empresa).eq("empresa_grupo_id", empresa_grupo_id).execute()
                else:
                    # CREAR NUEVO - incluir created_at
                    datos_costes_empresa["created_at"] = "now()"
                    res = grupos_service.supabase.table("empresa_grupo_costes").insert(datos_costes_empresa).execute()

                if res.data:
                    st.success(f"✅ Costes de {empresa_nombre} guardados correctamente")
                    # ACTUALIZAR VARIABLES GLOBALES
                    total_costes_empresa = total_costes_formulario
                    limite_calculado_empresa = limite_calculado_formulario
                    st.rerun()
                else:
                    st.error("❌ Error al guardar costes - sin datos devueltos")
            except Exception as e:
                st.error(f"❌ Error al guardar costes: {e}")

    # === BONIFICACIONES MENSUALES (FUERA DEL FORMULARIO) ===
    st.divider()
    st.markdown("##### 📅 Bonificaciones Mensuales")

    try:
        # USAR CAMPOS EXACTOS DEL SCHEMA: mes es INTEGER, no VARCHAR
        bonificaciones_empresa_res = grupos_service.supabase.table("empresa_grupo_bonificaciones").select("*").eq("empresa_grupo_id", empresa_grupo_id).order("mes").execute()
        df_bonif_empresa = pd.DataFrame(bonificaciones_empresa_res.data or [])
    except Exception as e:
        st.warning(f"⚠️ Error al cargar bonificaciones: {e}")
        df_bonif_empresa = pd.DataFrame()

    # Cálculos seguros de bonificaciones
    try:
        if not df_bonif_empresa.empty:
            df_bonif_empresa["importe"] = pd.to_numeric(df_bonif_empresa["importe"], errors="coerce").fillna(0.0)
            df_bonif_empresa["mes"] = pd.to_numeric(df_bonif_empresa["mes"], errors="coerce").fillna(1).astype(int)
            total_bonificado_empresa = df_bonif_empresa["importe"].sum()
        else:
            total_bonificado_empresa = 0.0
    except Exception as e:
        st.warning(f"⚠️ Error al procesar bonificaciones: {e}")
        total_bonificado_empresa = 0.0

    disponible_empresa = total_costes_empresa - total_bonificado_empresa

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 Costes Empresa", f"{total_costes_empresa:,.2f} €")
    with col2:
        st.metric("📊 Ya Bonificado", f"{total_bonificado_empresa:,.2f} €")
    with col3:
        st.metric("💡 Disponible", f"{disponible_empresa:,.2f} €")

    # Mostrar bonificaciones existentes (FUERA DE CUALQUIER FORMULARIO)
    if not df_bonif_empresa.empty:
        st.markdown("###### 📋 Bonificaciones Registradas")
        for _, bonif in df_bonif_empresa.iterrows():
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([2, 2, 3, 1])
                with col1:
                    mes_val = bonif.get("mes", 1)
                    try:
                        mes_num = int(mes_val) if mes_val else 1
                        mes_nombre = ["", "Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio",
                                      "Agosto","Septiembre","Octubre","Noviembre","Diciembre"][mes_num]
                    except (IndexError, ValueError, TypeError):
                        mes_nombre = "N/D"
                    st.write(f"📅 {mes_nombre}")
                    
                with col2:
                    importe_val = bonif.get("importe", 0)
                    try:
                        importe_num = float(importe_val) if importe_val is not None else 0.0
                    except (ValueError, TypeError):
                        importe_num = 0.0
                    st.write(f"💰 {importe_num:.2f} €")
                    
                with col3:
                    observaciones = bonif.get("observaciones") or ""
                    st.caption(f"📝 {str(observaciones)[:30]}...")
                    
                with col4:
                    bonif_id = bonif.get("id")
                    if bonif_id and st.button("❌", key=f"del_bonif_emp_{bonif_id}", help="Eliminar bonificación"):
                        try:
                            grupos_service.supabase.table("empresa_grupo_bonificaciones").delete().eq("id", bonif_id).execute()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")

    # Añadir nueva bonificación (CON SU PROPIO FORMULARIO INDEPENDIENTE)
    with st.expander("➕ Añadir Bonificación Mensual"):
        with st.form(f"nueva_bonif_emp_{empresa_grupo_id}"):
            col1, col2 = st.columns(2)

            with col1:
                # Meses disponibles (que no estén ya usados) - USAR INTEGER
                meses_usados = df_bonif_empresa["mes"].tolist() if not df_bonif_empresa.empty else []
                meses_disponibles = [m for m in range(1, 13) if m not in meses_usados]
                
                if not meses_disponibles:
                    st.warning("⚠️ Ya hay bonificaciones para todos los meses")
                    mes_bonif = 1
                else:
                    mes_bonif = st.selectbox(
                        "📅 Mes",
                        options=meses_disponibles,
                        format_func=lambda x: f"{x:02d} - {['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'][x-1]}",
                        key=f"mes_nueva_bonif_emp_{empresa_grupo_id}"
                    )
                
                importe_bonif = st.number_input(
                    "💰 Importe (€)",
                    min_value=0.01,
                    max_value=disponible_empresa if disponible_empresa > 0 else 999999.0,
                    value=0.01,
                    help=f"Disponible: {disponible_empresa:.2f} €",
                    key=f"importe_nueva_bonif_emp_{empresa_grupo_id}"
                )

            with col2:
                observaciones_bonif = st.text_area(
                    "📝 Observaciones",
                    height=100,
                    key=f"obs_nueva_bonif_emp_{empresa_grupo_id}"
                )

            # USAR st.form_submit_button EN LUGAR DE st.button
            if st.form_submit_button("➕ Añadir Bonificación", type="primary"):
                if importe_bonif <= 0:
                    st.error("❌ El importe debe ser mayor que 0")
                elif importe_bonif > disponible_empresa:
                    st.error(f"❌ El importe ({importe_bonif:.2f} €) supera lo disponible ({disponible_empresa:.2f} €)")
                else:
                    # USAR CAMPOS EXACTOS DEL SCHEMA
                    datos_bonif = {
                        "empresa_grupo_id": empresa_grupo_id,
                        "mes": mes_bonif,  # INTEGER según schema
                        "importe": importe_bonif,
                        "observaciones": observaciones_bonif or None,
                        "created_at": "now()",
                        "updated_at": "now()"
                    }
                    try:
                        res = grupos_service.supabase.table("empresa_grupo_bonificaciones").insert(datos_bonif).execute()
                        if res.data:
                            st.success("✅ Bonificación añadida correctamente")
                            st.rerun()
                        else:
                            st.error("❌ Error al añadir bonificación - sin datos devueltos")
                    except Exception as e:
                        st.error(f"❌ Error al añadir bonificación: {e}")

# =========================
# 2. IMPLEMENTAR FILTROS AVANZADOS STREAMLIT 1.49
# =========================

def mostrar_tabla_grupos_con_filtros_y_export(df_grupos, session_state):
    """
    Tabla con filtros avanzados Y exportación de datos filtrados.
    Retorna el DataFrame filtrado para uso posterior.
    """
    
    st.markdown("### 📊 Listado de Grupos")
    
    if df_grupos.empty:
        st.info("📋 No hay grupos registrados en tu ámbito.")
        return pd.DataFrame()
    
    # Preparar datos
    df_display = df_grupos.copy()
    df_display["Estado"] = df_display.apply(
        lambda row: determinar_estado_grupo(row.to_dict()), axis=1
    )
    
    # === SECCIÓN DE FILTROS ===
    with st.expander("🔍 Filtros Avanzados", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            modalidades = ["Todas"] + sorted(df_display["modalidad"].dropna().unique().tolist())
            modalidad_filtro = st.selectbox("🎯 Modalidad", modalidades)
        
        with col2:
            estados = ["Todos"] + sorted(df_display["Estado"].dropna().unique().tolist())
            estado_filtro = st.selectbox("📊 Estado", estados)
        
        with col3:
            localidades = ["Todas"] + sorted(df_display["localidad"].dropna().unique().tolist())
            localidad_filtro = st.selectbox("🏙️ Localidad", localidades)
        
        with col4:
            if session_state.role == "admin":
                empresas = ["Todas"] + sorted(df_display["empresa_nombre"].dropna().unique().tolist())
                empresa_filtro = st.selectbox("🏢 Empresa", empresas)
            else:
                empresa_filtro = "Todas"
        
        # Filtro de búsqueda
        busqueda = st.text_input(
            "🔍 Buscar en código, acción formativa...",
            placeholder="Escribe para filtrar...",
            key="busqueda_grupos"
        )
        
        # Filtro de fechas
        col_fecha1, col_fecha2 = st.columns(2)
        with col_fecha1:
            fecha_desde = st.date_input("📅 Fecha inicio desde", value=None)
        with col_fecha2:
            fecha_hasta = st.date_input("📅 Fecha inicio hasta", value=None)
    
    # === APLICAR FILTROS ===
    df_filtrado = df_display.copy()
    
    if modalidad_filtro != "Todas":
        df_filtrado = df_filtrado[df_filtrado["modalidad"] == modalidad_filtro]
    
    if estado_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Estado"] == estado_filtro]
        
    if localidad_filtro != "Todas":
        df_filtrado = df_filtrado[df_filtrado["localidad"] == localidad_filtro]
    
    if session_state.role == "admin" and empresa_filtro != "Todas":
        df_filtrado = df_filtrado[df_filtrado["empresa_nombre"] == empresa_filtro]
    
    if fecha_desde:
        df_filtrado = df_filtrado[
            pd.to_datetime(df_filtrado["fecha_inicio"]).dt.date >= fecha_desde
        ]
    
    if fecha_hasta:
        df_filtrado = df_filtrado[
            pd.to_datetime(df_filtrado["fecha_inicio"]).dt.date <= fecha_hasta
        ]
    
    if busqueda:
        mascara_busqueda = (
            df_filtrado["codigo_grupo"].str.contains(busqueda, case=False, na=False) |
            df_filtrado["accion_nombre"].str.contains(busqueda, case=False, na=False)
        )
        if "empresa_nombre" in df_filtrado.columns:
            mascara_busqueda |= df_filtrado["empresa_nombre"].str.contains(busqueda, case=False, na=False)
        
        df_filtrado = df_filtrado[mascara_busqueda]
    
    # === MOSTRAR RESULTADOS DE FILTROS ===
    total_original = len(df_display)
    total_filtrado = len(df_filtrado)
    
    if total_filtrado != total_original:
        st.info(f"📊 Mostrando {total_filtrado} de {total_original} grupos")
    
    # === BOTONES DE ACCIÓN (ANTES DE LA TABLA) ===
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        if st.button("➕ Crear Nuevo Grupo", type="primary", use_container_width=True):
            st.session_state.grupo_seleccionado = {}
            st.rerun()
    
    with col2:
        # ✅ EXPORTAR DATOS FILTRADOS
        if not df_filtrado.empty:
            fecha_str = datetime.now().strftime("%Y%m%d")
            filename = f"grupos_filtrados_{fecha_str}.xlsx"
            
            # Preparar datos para exportación (sin columnas internas)
            columnas_export = [
                "codigo_grupo", "accion_nombre", "modalidad",
                "fecha_inicio", "fecha_fin_prevista", "localidad", "provincia",
                "n_participantes_previstos", "Estado", "responsable", 
                "telefono_contacto", "lugar_imparticion"
            ]
            
            if session_state.role == "admin":
                columnas_export.insert(-1, "empresa_nombre")
            
            # Solo columnas que existen
            columnas_disponibles = [col for col in columnas_export if col in df_filtrado.columns]
            df_export = df_filtrado[columnas_disponibles].copy()
            
            export_excel(
                df_export, 
                filename=filename, 
                label="📥 Exportar Filtrados"
            )
        else:
            st.warning("⚠️ No hay datos para exportar")
    
    with col3:
        # Exportar TODO (original)
        if not df_grupos.empty:
            fecha_str = datetime.now().strftime("%Y%m%d")
            filename_completo = f"grupos_completo_{fecha_str}.xlsx"
            
            export_excel(
                df_grupos, 
                filename=filename_completo, 
                label="📥 Exportar Todo"
            )
    
    with col4:
        if st.button("🔄 Actualizar", use_container_width=True):
            grupos_service.limpiar_cache_grupos()
            st.rerun()
    
    # === MOSTRAR TABLA ===
    if df_filtrado.empty:
        st.warning("⚠️ No se encontraron grupos con los filtros aplicados")
        return df_filtrado
    
    # Columnas para mostrar
    columnas_mostrar = [
        "codigo_grupo", "accion_nombre", "modalidad", 
        "fecha_inicio", "fecha_fin_prevista", "localidad", 
        "n_participantes_previstos", "Estado"
    ]
    
    if session_state.role == "admin":
        columnas_mostrar.insert(-1, "empresa_nombre")
    
    columnas_disponibles = [col for col in columnas_mostrar if col in df_filtrado.columns]
    
    # Configuración de columnas
    column_config = {
        "codigo_grupo": st.column_config.TextColumn("🏷️ Código", width="medium"),
        "accion_nombre": st.column_config.TextColumn("📚 Acción Formativa", width="large"),
        "modalidad": st.column_config.SelectboxColumn(
            "🎯 Modalidad", 
            width="small",
            options=["PRESENCIAL", "TELEFORMACION", "MIXTA"]
        ),
        "fecha_inicio": st.column_config.DateColumn("📅 Inicio", width="small"),
        "fecha_fin_prevista": st.column_config.DateColumn("📅 Fin Previsto", width="small"),
        "localidad": st.column_config.TextColumn("🏙️ Localidad", width="medium"),
        "n_participantes_previstos": st.column_config.NumberColumn(
            "👥 Participantes", 
            width="small", 
            format="%d"
        ),
        "Estado": st.column_config.SelectboxColumn(
            "📊 Estado", 
            width="small",
            options=["ABIERTO", "FINALIZAR", "FINALIZADO"]
        )
    }
    
    if session_state.role == "admin":
        column_config["empresa_nombre"] = st.column_config.TextColumn("🏢 Empresa", width="medium")
    
    # Tabla con selección
    event = st.dataframe(
        df_filtrado[columnas_disponibles],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config=column_config,
        height=400
    )
    
    # Procesar selección
    if event.selection.rows:
        selected_idx = event.selection.rows[0]
        # IMPORTANTE: usar índice del DataFrame original, no filtrado
        grupo_seleccionado = df_grupos[df_grupos.index.isin(df_filtrado.iloc[event.selection.rows].index)].iloc[0].to_dict()
        st.session_state.grupo_seleccionado = grupo_seleccionado
    
    return df_filtrado
# =========================
# FUNCIÓN PRINCIPAL
# =========================

def render(supabase, session_state):
    """Función principal de gestión de grupos con diseño consistente a participantes/empresas."""
    st.title("👥 Gestión de Grupos FUNDAE")
    st.caption("🎯 Creación y administración de grupos formativos con jerarquía empresarial")
    
    if "grupo_seleccionado" not in st.session_state:
        st.session_state.grupo_seleccionado = None
        
    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección")
        return
    
    # Inicializar servicio
    grupos_service = get_grupos_service(supabase, session_state)
    
    # Crear tabs principales siguiendo el patrón de participantes
    tabs = st.tabs(["📋 Listado", "➕ Crear"])
    
    # ========================= 
    # TAB 1: LISTADO (Estilo consistente)
    # =========================
    with tabs[0]:
        try:
            df_grupos = grupos_service.get_grupos_completos()
            
            # Preparar datos con estado automático
            if not df_grupos.empty:
                df_grupos["Estado"] = df_grupos.apply(
                    lambda row: determinar_estado_grupo(row.to_dict()), axis=1
                )
            
            # Mostrar tabla con el estilo de participantes
            resultado = mostrar_tabla_grupos_consistente(df_grupos, session_state, grupos_service)
            if resultado is not None and len(resultado) == 2:
                seleccionado, df_paged = resultado
            else:
                seleccionado, df_paged = None, pd.DataFrame()

            # Exportación e importación en expanders (como participantes)
            st.divider()
            
            with st.expander("📥 Exportar Grupos"):
                exportar_grupos(df_grupos, df_paged, session_state)
            
            with st.expander("🔧 Herramientas Administrativas"):
                # Solo limpiar cache
                if st.button("🔄 Limpiar Cache", use_container_width=True):
                    grupos_service.limpiar_cache_grupos()
                    st.success("✅ Cache limpiado")
                    st.rerun()

            with st.expander("ℹ️ Ayuda sobre Grupos FUNDAE"):
                st.markdown("""
                **Funcionalidades principales:**
                - 🔍 **Filtros**: Usa los campos de búsqueda para encontrar grupos rápidamente
                - ✏️ **Edición**: Haz clic en una fila para editar un grupo
                - 📊 **Estados automáticos**: Los estados se calculan según las fechas
                - 👥 **Gestión completa**: Tutores, empresas, participantes y costes
                
                **Estados de grupos:**
                - 🟢 **ABIERTO**: Grupo en proceso de configuración
                - 🟡 **FINALIZAR**: Fecha prevista superada, requiere finalización
                - ✅ **FINALIZADO**: Completado con todos los datos FUNDAE
                
                **Flujo recomendado:**
                1. Crear grupo con datos básicos
                2. Asignar tutores y centro gestor (si aplica)
                3. Añadir empresas participantes
                4. Inscribir participantes
                5. Configurar costes FUNDAE
                6. Finalizar cuando corresponda
                """)

            # Mostrar formulario de edición si hay selección
            if seleccionado is not None:
                with st.container(border=True):
                    grupo_id = mostrar_formulario_grupo_separado(
                        grupos_service, es_creacion=False, context="_editar"
                    )
                    if grupo_id:
                        st.divider()
                        mostrar_secciones_adicionales(grupos_service, grupo_id)
                        
        except Exception as e:
            st.error(f"❌ Error cargando grupos: {e}")

    # =========================
    # TAB 2: CREAR (Estilo consistente) 
    # =========================
    with tabs[1]:
        with st.container(border=True):
            mostrar_formulario_grupo_separado(
                grupos_service, es_creacion=True, context="_crear"
            )
        
def mostrar_tabla_grupos_consistente(df_grupos, session_state, grupos_service):
    """Tabla de grupos usando las métricas y funcionalidad existente."""
    
    if df_grupos.empty:
        st.info("📋 No hay grupos registrados en tu ámbito.")
        return None, pd.DataFrame()
    
    # Usar tu función de métricas existente en lugar de crear una nueva
    mostrar_metricas_grupos(df_grupos, session_state)
    
    # Avisos de grupos pendientes (mantener tu lógica existente)
    grupos_pendientes = get_grupos_pendientes_finalizacion(df_grupos)
    if grupos_pendientes:
        mostrar_avisos_grupos(grupos_pendientes)
    
    # Filtros compactos (estilo participantes)
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        query = st.text_input("🔍 Buscar por código o acción", key="buscar_grupo")
    
    with col2:
        modalidades = ["Todas"] + sorted(df_grupos["modalidad"].dropna().unique().tolist())
        modalidad_filter = st.selectbox("Modalidad", modalidades, key="filtro_modalidad")
    
    with col3:
        estados_unicos = sorted(df_grupos["Estado"].dropna().unique().tolist()) if "Estado" in df_grupos.columns else []
        estado_filter = st.selectbox("Estado", ["Todos"] + estados_unicos, key="filtro_estado")
    
    with col4:
        if session_state.role == "admin":
            empresas = sorted(df_grupos["empresa_nombre"].dropna().unique().tolist()) if "empresa_nombre" in df_grupos.columns else []
            empresa_filter = st.selectbox("Empresa", ["Todas"] + empresas, key="filtro_empresa")
        else:
            empresa_filter = "Todas"

    # Aplicar filtros
    df_filtrado = aplicar_filtros_grupos(df_grupos, query, modalidad_filter, estado_filter, empresa_filter, session_state)

    # Tabla principal
    st.markdown("### 📊 Listado de Grupos")
    
    if df_filtrado.empty:
        st.info("🔍 No hay grupos que coincidan con los filtros aplicados.")
        return None, df_filtrado
    
    # Seleccionar columnas para mostrar
    columnas_mostrar = [
        "codigo_grupo", "accion_nombre", "modalidad", 
        "fecha_inicio", "fecha_fin_prevista", "localidad", 
        "n_participantes_previstos", "Estado"
    ]
    
    if session_state.role == "admin" and "empresa_nombre" in df_filtrado.columns:
        columnas_mostrar.insert(-1, "empresa_nombre")
    
    columnas_disponibles = [col for col in columnas_mostrar if col in df_filtrado.columns]
    
    # Configuración moderna de columnas
    column_config = {
        "codigo_grupo": st.column_config.TextColumn("🏷️ Código", width="small"),
        "accion_nombre": st.column_config.TextColumn("📚 Acción Formativa", width="large"),
        "modalidad": st.column_config.TextColumn("🎯 Modalidad", width="small"),
        "fecha_inicio": st.column_config.DateColumn("📅 Inicio", width="small"),
        "fecha_fin_prevista": st.column_config.DateColumn("📅 Fin Previsto", width="small"),
        "localidad": st.column_config.TextColumn("🏙️ Localidad", width="medium"),
        "n_participantes_previstos": st.column_config.NumberColumn("👥 Participantes", width="small"),
        "Estado": st.column_config.TextColumn("📊 Estado", width="small"),
        "empresa_nombre": st.column_config.TextColumn("🏢 Empresa", width="medium")
    }
    
    # Mostrar tabla con selección
    event = st.dataframe(
        df_filtrado[columnas_disponibles],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config=column_config
    )

    # Procesar selección
    if event.selection.rows:
        selected_idx = event.selection.rows[0]
        grupo_seleccionado = df_filtrado.iloc[selected_idx]
        st.session_state.grupo_seleccionado = grupo_seleccionado.to_dict()
        return grupo_seleccionado.to_dict(), df_filtrado
    
    return None, df_filtrado

def mostrar_metricas_grupos_compactas(df_grupos, session_state):
    """Métricas compactas estilo participantes."""
    if df_grupos.empty:
        return
    
    # Calcular estados
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

def aplicar_filtros_grupos(df_grupos, query, modalidad_filter, estado_filter, empresa_filter, session_state):
    """Aplica filtros al DataFrame de grupos."""
    df_filtrado = df_grupos.copy()
    
    if query:
        mascara = (
            df_filtrado["codigo_grupo"].str.contains(query, case=False, na=False) |
            df_filtrado["accion_nombre"].str.contains(query, case=False, na=False)
        )
        df_filtrado = df_filtrado[mascara]
    
    if modalidad_filter != "Todas":
        df_filtrado = df_filtrado[df_filtrado["modalidad"] == modalidad_filter]
    
    if estado_filter != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Estado"] == estado_filter]
    
    if session_state.role == "admin" and empresa_filter != "Todas":
        df_filtrado = df_filtrado[df_filtrado["empresa_nombre"] == empresa_filter]
    
    return df_filtrado

def exportar_grupos(df_grupos, df_filtrado, session_state):
    """Sección de exportación estilo participantes."""
    if df_grupos.empty:
        st.warning("⚠️ No hay datos para exportar.")
        return
    
    export_scope = st.radio(
        "¿Qué quieres exportar?",
        ["📄 Solo registros visibles", "🌐 Todos los grupos"],
        horizontal=True
    )
    
    df_export = df_filtrado if export_scope == "📄 Solo registros visibles" else df_grupos
    
    if not df_export.empty:
        fecha_str = datetime.now().strftime("%Y%m%d")
        filename = f"grupos_fundae_{fecha_str}.xlsx"
        
        # Usar tu función de exportación existente
        export_excel(df_export, filename=filename, label="📥 Exportar a Excel")


def mostrar_metricas_grupos_detalladas(df_grupos, session_state, grupos_service):
    """Tab de métricas detalladas."""
    if df_grupos.empty:
        st.info("📋 No hay datos para mostrar métricas.")
        return
    
    # Usar tu función existente pero mejorada
    mostrar_metricas_grupos(df_grupos, session_state)
    
    st.divider()
    st.markdown("### 📊 Análisis Adicional")
    
    # Aquí puedes añadir más métricas en el futuro
    st.info("Métricas adicionales en desarrollo...")

# =========================
# PUNTO DE ENTRADA
# =========================

if __name__ == "__main__":
    # Esta función será llamada desde el sistema principal de navegación
    pass
