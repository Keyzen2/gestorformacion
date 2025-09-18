import streamlit as st
import pandas as pd
from datetime import datetime, date
from services.grupos_service import get_grupos_service
from utils import validar_dni_cif
import math

# =========================
# CONFIGURACIÓN Y CONSTANTES
# =========================

MODALIDADES_FUNDAE = {
    "PRESENCIAL": "PRESENCIAL",
    "TELEFORMACION": "TELEFORMACION", 
    "MIXTA": "MIXTA"
}

INTERVALOS_TIEMPO = [f"{h:02d}:{m:02d}" for h in range(6, 24) for m in [0, 15, 30, 45]]
DIAS_SEMANA = ["L", "M", "X", "J", "V", "S", "D"]
NOMBRES_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# =========================
# FUNCIONES AUXILIARES MEJORADAS
# =========================

def safe_int_conversion(value, default=0):
    """Convierte un valor a entero de forma segura."""
    if value is None or pd.isna(value):
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

def determinar_estado_grupo(grupo_data):
    """Determina el estado automático del grupo según las fechas."""
    if not grupo_data:
        return "ABIERTO"
    
    fecha_fin_prevista = grupo_data.get("fecha_fin_prevista")
    fecha_fin_real = grupo_data.get("fecha_fin")
    n_finalizados = grupo_data.get("n_participantes_finalizados")
    
    # Si tiene datos de finalización completos
    if fecha_fin_real and n_finalizados is not None:
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
    
    # Participantes entre 1 y 30
    try:
        n_part = int(datos.get("n_participantes_previstos", 0))
        if n_part < 1 or n_part > 30:
            errores.append("Participantes previstos debe estar entre 1 y 30")
    except:
        errores.append("Participantes previstos debe ser un número")
    
    return errores

# =========================
# COMPONENTES UI MODERNOS
# =========================

def mostrar_kpis_grupos(df_grupos):
    """KPIs modernos con métricas mejoradas de Streamlit 1.49."""
    if df_grupos.empty:
        st.info("📋 No hay grupos registrados.")
        return
    
    # Calcular estados
    total = len(df_grupos)
    abiertos = sum(1 for _, g in df_grupos.iterrows() if determinar_estado_grupo(g.to_dict()) == "ABIERTO")
    por_finalizar = sum(1 for _, g in df_grupos.iterrows() if determinar_estado_grupo(g.to_dict()) == "FINALIZAR")
    finalizados = sum(1 for _, g in df_grupos.iterrows() if determinar_estado_grupo(g.to_dict()) == "FINALIZADO")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "📊 Total Grupos", 
            total,
            help="Total de grupos en el sistema"
        )
    
    with col2:
        st.metric(
            "🟢 Abiertos", 
            abiertos,
            delta=f"{(abiertos/total*100):.1f}%" if total > 0 else "0%",
            help="Grupos activos en formación"
        )
    
    with col3:
        if por_finalizar > 0:
            st.metric(
                "🟡 Por Finalizar", 
                por_finalizar,
                delta=f"¡{por_finalizar} pendientes!",
                delta_color="inverse",
                help="Grupos que necesitan finalización"
            )
        else:
            st.metric(
                "🟡 Por Finalizar", 
                por_finalizar,
                delta="Todo al día",
                help="Grupos que necesitan finalización"
            )
    
    with col4:
        st.metric(
            "✅ Finalizados", 
            finalizados,
            delta=f"{(finalizados/total*100):.1f}%" if total > 0 else "0%",
            help="Grupos completados"
        )

def mostrar_alertas_grupos(df_grupos):
    """Alertas modernas con grupos pendientes."""
    grupos_pendientes = []
    for _, grupo in df_grupos.iterrows():
        if determinar_estado_grupo(grupo.to_dict()) == "FINALIZAR":
            grupos_pendientes.append(grupo.to_dict())
    
    if not grupos_pendientes:
        return
    
    st.warning(f"⚠️ **{len(grupos_pendientes)} grupo(s) pendiente(s) de finalización**")
    
    with st.expander("Ver grupos pendientes", expanded=False):
        for grupo in grupos_pendientes[:5]:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{grupo.get('codigo_grupo')}** - Fin previsto: {grupo.get('fecha_fin_prevista')}")
            with col2:
                if st.button("Finalizar", key=f"finalizar_{grupo.get('id')}", type="secondary"):
                    st.session_state.grupo_para_finalizar = grupo
                    st.rerun()

# =========================
# MODAL CREAR GRUPO
# =========================

@st.dialog("Crear Nuevo Grupo", width="large")
def modal_crear_grupo(grupos_service):
    """Modal moderno para crear grupos."""
    
    st.markdown("### ➕ Crear Nuevo Grupo de Formación")
    st.caption("Complete los datos básicos obligatorios para FUNDAE")
    
    # Obtener datos necesarios
    acciones_dict = grupos_service.get_acciones_dict()
    if not acciones_dict:
        st.error("❌ No hay acciones formativas disponibles. Crea una acción formativa primero.")
        return
    
    with st.form("form_crear_grupo", clear_on_submit=False):
        # Datos básicos
        st.markdown("#### 📋 Datos Básicos")
        col1, col2 = st.columns(2)
        
        with col1:
            codigo_grupo = st.text_input(
                "Código del Grupo *",
                max_chars=50,
                help="Código único identificativo del grupo"
            )
            
            accion_formativa = st.selectbox(
                "Acción Formativa *",
                list(acciones_dict.keys()),
                help="Selecciona la acción formativa asociada"
            )
            
            fecha_inicio = st.date_input(
                "Fecha de Inicio *",
                value=date.today(),
                help="Fecha de inicio de la formación"
            )
        
        with col2:
            n_participantes_previstos = st.number_input(
                "Participantes Previstos *",
                min_value=1,
                max_value=30,
                value=8,
                help="Número de participantes previstos (1-30)"
            )
            
            fecha_fin_prevista = st.date_input(
                "Fecha Fin Prevista *",
                help="Fecha prevista de finalización"
            )
            
            localidad = st.text_input(
                "Localidad *",
                help="Localidad de impartición (obligatorio FUNDAE)"
            )
        
        # Datos adicionales
        st.markdown("#### 📍 Información Adicional")
        col3, col4 = st.columns(2)
        
        with col3:
            provincia = st.text_input("Provincia")
            cp = st.text_input("Código Postal")
        
        with col4:
            responsable = st.text_input("Responsable del Grupo")
            telefono_contacto = st.text_input("Teléfono de Contacto")
        
        lugar_imparticion = st.text_area(
            "Lugar de Impartición",
            height=60,
            help="Descripción detallada del lugar"
        )
        
        observaciones = st.text_area(
            "Observaciones",
            height=80,
            help="Información adicional (opcional)"
        )
        
        # Horarios básicos
        st.markdown("#### ⏰ Horarios Básicos")
        col5, col6 = st.columns(2)
        
        with col5:
            hora_inicio = st.selectbox("Hora Inicio", INTERVALOS_TIEMPO, index=12)  # 09:00
        
        with col6:
            hora_fin = st.selectbox("Hora Fin", INTERVALOS_TIEMPO, index=28)  # 13:00
        
        # Días de la semana
        dias_cols = st.columns(5)
        dias_seleccionados = []
        
        for i, (dia_corto, dia_largo) in enumerate(zip(DIAS_SEMANA[:5], NOMBRES_DIAS[:5])):
            with dias_cols[i]:
                if st.checkbox(dia_corto, value=True, key=f"dia_{dia_corto}"):
                    dias_seleccionados.append(dia_corto)
        
        # Botones de acción
        col_submit, col_cancel = st.columns([2, 1])
        
        with col_submit:
            submitted = st.form_submit_button("✅ Crear Grupo", type="primary", use_container_width=True)
        
        with col_cancel:
            cancelled = st.form_submit_button("❌ Cancelar", use_container_width=True)
        
        if cancelled:
            st.rerun()
        
        if submitted:
            # Validaciones
            if not codigo_grupo:
                st.error("⚠️ El código de grupo es obligatorio")
                return
            
            if not localidad:
                st.error("⚠️ La localidad es obligatoria")
                return
            
            # Construir horario básico
            horario = construir_horario_fundae(
                hora_inicio, hora_fin, None, None, dias_seleccionados
            )
            
            # Preparar datos
            accion_id = acciones_dict[accion_formativa]
            modalidad_raw = grupos_service.get_accion_modalidad(accion_id)
            modalidad = grupos_service.normalizar_modalidad_fundae(modalidad_raw)
            
            datos_crear = {
                "codigo_grupo": codigo_grupo,
                "accion_formativa_id": accion_id,
                "modalidad": modalidad,
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
                "horario": horario
            }
            
            # Asignar empresa según rol
            if grupos_service.rol == "gestor":
                datos_crear["empresa_id"] = grupos_service.empresa_id
            
            # Validar
            errores = validar_campos_obligatorios_fundae(datos_crear)
            
            if errores:
                st.error("❌ Errores de validación:")
                for error in errores:
                    st.error(f"• {error}")
            else:
                try:
                    exito, grupo_id = grupos_service.create_grupo_completo(datos_crear)
                    if exito:
                        st.success(f"✅ Grupo '{codigo_grupo}' creado correctamente")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ Error al crear el grupo")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

# =========================
# MODAL EDITAR GRUPO
# =========================

@st.dialog("Editar Grupo", width="large")
def modal_editar_grupo(grupos_service, grupo):
    """Modal moderno para editar grupos."""
    
    codigo = grupo.get("codigo_grupo", "Sin código")
    estado = determinar_estado_grupo(grupo)
    
    st.markdown(f"### ✏️ Editar: {codigo}")
    
    # Mostrar estado
    color_estado = {
        "ABIERTO": "🟢",
        "FINALIZAR": "🟡", 
        "FINALIZADO": "✅"
    }
    st.caption(f"Estado: {color_estado.get(estado, '⚪')} {estado}")
    
    # Pestañas para organizar contenido
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Datos Básicos",
        "👥 Participantes", 
        "👨‍🏫 Tutores",
        "💰 Costes"
    ])
    
    with tab1:
        mostrar_tab_datos_basicos(grupos_service, grupo)
    
    with tab2:
        mostrar_tab_participantes(grupos_service, grupo["id"])
    
    with tab3:
        mostrar_tab_tutores(grupos_service, grupo["id"])
    
    with tab4:
        mostrar_tab_costes(grupos_service, grupo["id"])

def mostrar_tab_datos_basicos(grupos_service, grupo):
    """Tab de datos básicos en modal de edición."""
    
    with st.form("form_datos_basicos"):
        st.markdown("#### 📋 Información del Grupo")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Mostrar código (no editable)
            st.text_input(
                "Código del Grupo",
                value=grupo.get("codigo_grupo", ""),
                disabled=True
            )
            
            fecha_inicio = st.date_input(
                "Fecha de Inicio *",
                value=safe_date_conversion(grupo.get("fecha_inicio")) or date.today()
            )
            
            n_participantes = st.number_input(
                "Participantes Previstos *",
                min_value=1,
                max_value=30,
                value=safe_int_conversion(grupo.get("n_participantes_previstos"), 8)
            )
        
        with col2:
            localidad = st.text_input(
                "Localidad *",
                value=grupo.get("localidad", "")
            )
            
            fecha_fin_prevista = st.date_input(
                "Fecha Fin Prevista *",
                value=safe_date_conversion(grupo.get("fecha_fin_prevista"))
            )
            
            provincia = st.text_input(
                "Provincia",
                value=grupo.get("provincia", "")
            )
        
        observaciones = st.text_area(
            "Observaciones",
            value=grupo.get("observaciones", ""),
            height=100
        )
        
        # Sección de finalización si es necesario
        estado = determinar_estado_grupo(grupo)
        if estado in ["FINALIZAR", "FINALIZADO"]:
            st.markdown("#### 🏁 Datos de Finalización")
            
            col3, col4 = st.columns(2)
            
            with col3:
                fecha_fin_real = st.date_input(
                    "Fecha Fin Real *",
                    value=safe_date_conversion(grupo.get("fecha_fin")) or date.today()
                )
                
                n_finalizados = st.number_input(
                    "Participantes Finalizados *",
                    min_value=0,
                    max_value=n_participantes,
                    value=safe_int_conversion(grupo.get("n_participantes_finalizados"), 0)
                )
            
            with col4:
                n_aptos = st.number_input(
                    "Participantes Aptos *",
                    min_value=0,
                    max_value=n_finalizados,
                    value=safe_int_conversion(grupo.get("n_aptos"), 0)
                )
                
                n_no_aptos = st.number_input(
                    "Participantes No Aptos *",
                    min_value=0,
                    max_value=n_finalizados,
                    value=safe_int_conversion(grupo.get("n_no_aptos"), 0)
                )
            
            # Validación en tiempo real
            if n_finalizados > 0 and (n_aptos + n_no_aptos != n_finalizados):
                st.error(f"⚠️ La suma de aptos ({n_aptos}) + no aptos ({n_no_aptos}) debe ser igual a finalizados ({n_finalizados})")
        
        # Botón guardar
        if st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True):
            datos_actualizar = {
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin_prevista": fecha_fin_prevista.isoformat() if fecha_fin_prevista else None,
                "localidad": localidad,
                "provincia": provincia,
                "n_participantes_previstos": n_participantes,
                "observaciones": observaciones
            }
            
            # Añadir datos de finalización si aplica
            if estado in ["FINALIZAR", "FINALIZADO"]:
                datos_actualizar.update({
                    "fecha_fin": fecha_fin_real.isoformat(),
                    "n_participantes_finalizados": n_finalizados,
                    "n_aptos": n_aptos,
                    "n_no_aptos": n_no_aptos
                })
            
            # Validar y guardar
            errores = validar_campos_obligatorios_fundae(datos_actualizar)
            
            if errores:
                st.error("❌ Errores de validación:")
                for error in errores:
                    st.error(f"• {error}")
            else:
                try:
                    if grupos_service.update_grupo(grupo["id"], datos_actualizar):
                        st.success("✅ Cambios guardados correctamente")
                        st.rerun()
                    else:
                        st.error("❌ Error al guardar cambios")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

def mostrar_tab_participantes(grupos_service, grupo_id):
    """Tab de participantes en modal de edición."""
    
    try:
        df_participantes = grupos_service.get_participantes_grupo(grupo_id)
        
        if not df_participantes.empty:
            st.markdown("##### 👥 Participantes Asignados")
            
            # Mostrar tabla con botones de acción
            for _, row in df_participantes.iterrows():
                col1, col2 = st.columns([4, 1])
                with col1:
                    nombre = f"{row.get('nombre', '')} {row.get('apellidos', '')}"
                    st.write(f"**{nombre}** - {row.get('nif', 'Sin NIF')}")
                    st.caption(f"Email: {row.get('email', 'N/A')}")
                
                with col2:
                    if st.button("🗑️", key=f"remove_part_{row['id']}", help="Desasignar"):
                        if grupos_service.desasignar_participante_de_grupo(row["id"]):
                            st.success("Participante desasignado")
                            st.rerun()
        else:
            st.info("No hay participantes asignados")
        
        # Asignar participantes
        st.markdown("##### ➕ Asignar Participantes")
        
        df_disponibles = grupos_service.get_participantes_disponibles(grupo_id)
        
        if not df_disponibles.empty:
            participante_options = {}
            for _, row in df_disponibles.iterrows():
                nombre = f"{row.get('nombre', '')} {row.get('apellidos', '')}"
                participante_options[f"{row.get('nif', 'Sin NIF')} - {nombre}"] = row["id"]
            
            with st.form("form_asignar_participantes"):
                participantes_sel = st.multiselect(
                    "Seleccionar participantes:",
                    participante_options.keys()
                )
                
                if st.form_submit_button("✅ Asignar Seleccionados", type="primary"):
                    exitos = 0
                    for part_str in participantes_sel:
                        part_id = participante_options[part_str]
                        if grupos_service.asignar_participante_a_grupo(part_id, grupo_id):
                            exitos += 1
                    
                    if exitos > 0:
                        st.success(f"Se asignaron {exitos} participantes")
                        st.rerun()
        else:
            st.info("No hay participantes disponibles")
            
    except Exception as e:
        st.error(f"Error al gestionar participantes: {e}")

def mostrar_tab_tutores(grupos_service, grupo_id):
    """Tab de tutores en modal de edición."""
    
    try:
        df_tutores = grupos_service.get_tutores_grupo(grupo_id)
        
        if not df_tutores.empty:
            st.markdown("##### 👨‍🏫 Tutores Asignados")
            
            for _, row in df_tutores.iterrows():
                tutor = row.get("tutor", {})
                if not tutor:
                    continue
                
                col1, col2 = st.columns([4, 1])
                with col1:
                    nombre = f"{tutor.get('nombre', '')} {tutor.get('apellidos', '')}"
                    st.write(f"**{nombre}**")
                    st.caption(f"Email: {tutor.get('email', 'N/A')} | Especialidad: {tutor.get('especialidad', 'N/A')}")
                
                with col2:
                    if st.button("🗑️", key=f"remove_tutor_{row['id']}", help="Quitar tutor"):
                        if grupos_service.delete_tutor_grupo(row["id"]):
                            st.success("Tutor eliminado")
                            st.rerun()
        else:
            st.info("No hay tutores asignados")
        
        # Asignar tutores
        st.markdown("##### ➕ Asignar Tutores")
        
        df_tutores_disponibles = grupos_service.get_tutores_completos()
        
        if not df_tutores_disponibles.empty:
            # Filtrar ya asignados
            tutores_asignados = set()
            for _, row in df_tutores.iterrows():
                tutor = row.get("tutor", {})
                if tutor and tutor.get("id"):
                    tutores_asignados.add(tutor.get("id"))
            
            df_disponibles = df_tutores_disponibles[
                ~df_tutores_disponibles["id"].isin(tutores_asignados)
            ]
            
            if not df_disponibles.empty:
                tutor_options = {}
                for _, row in df_disponibles.iterrows():
                    nombre = f"{row.get('nombre', '')} {row.get('apellidos', '')}"
                    especialidad = row.get('especialidad', 'Sin especialidad')
                    tutor_options[f"{nombre} - {especialidad}"] = row["id"]
                
                with st.form("form_asignar_tutores"):
                    tutores_sel = st.multiselect(
                        "Seleccionar tutores:",
                        tutor_options.keys()
                    )
                    
                    if st.form_submit_button("✅ Asignar Seleccionados", type="primary"):
                        exitos = 0
                        for tutor_str in tutores_sel:
                            tutor_id = tutor_options[tutor_str]
                            if grupos_service.create_tutor_grupo(grupo_id, tutor_id):
                                exitos += 1
                        
                        if exitos > 0:
                            st.success(f"Se asignaron {exitos} tutores")
                            st.rerun()
            else:
                st.info("Todos los tutores disponibles ya están asignados")
        else:
            st.info("No hay tutores disponibles")
            
    except Exception as e:
        st.error(f"Error al gestionar tutores: {e}")

def mostrar_tab_costes(grupos_service, grupo_id):
    """Tab de costes en modal de edición."""
    
    st.markdown("##### 💰 Gestión de Costes FUNDAE")
    
    try:
        costes_actuales = grupos_service.get_grupo_costes(grupo_id)
        
        with st.form("form_costes"):
            col1, col2 = st.columns(2)
            
            with col1:
                costes_directos = st.number_input(
                    "Costes Directos (€)",
                    value=float(costes_actuales.get("costes_directos", 0)),
                    min_value=0.0
                )
                
                costes_indirectos = st.number_input(
                    "Costes Indirectos (€)",
                    value=float(costes_actuales.get("costes_indirectos", 0)),
                    min_value=0.0,
                    help="Máximo 30% de costes directos"
                )
            
            with col2:
                tarifa_hora = st.number_input(
                    "Tarifa por Hora (€)",
                    value=float(costes_actuales.get("tarifa_hora", 13.0)),
                    min_value=0.0,
                    max_value=13.0,
                    help="Máximo FUNDAE: 13 €/h"
                )
                
                cofinanciacion = st.number_input(
                    "Cofinanciación Privada (€)",
                    value=float(costes_actuales.get("cofinanciacion_privada", 0)),
                    min_value=0.0
                )
            
            # Validaciones
            total_costes = costes_directos + costes_indirectos
            
            if costes_directos > 0:
                pct_indirectos = (costes_indirectos / costes_directos) * 100
                if pct_indirectos > 30:
                    st.error(f"Costes indirectos ({pct_indirectos:.1f}%) superan el 30% permitido")
                else:
                    st.success(f"Costes indirectos dentro del límite ({pct_indirectos:.1f}%)")
            
            st.metric("Total Costes", f"{total_costes:,.2f} €")
            
            if st.form_submit_button("💾 Guardar Costes", type="primary"):
                datos_costes = {
                    "grupo_id": grupo_id,
                    "costes_directos": costes_directos,
                    "costes_indirectos": costes_indirectos,
                    "tarifa_hora": tarifa_hora,
                    "cofinanciacion_privada": cofinanciacion
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
                    
    except Exception as e:
        st.error(f"Error al cargar costes: {e}")

# =========================
# FUNCIÓN PRINCIPAL CON TABLA CLICABLE
# =========================

def main(supabase, session_state):
    """Función principal de gestión de grupos con sistema modal."""
    
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
    
    # Mostrar alertas
    mostrar_alertas_grupos(df_grupos)
    
    st.divider()
    
    # Botón para crear nuevo grupo
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("➕ Crear Nuevo Grupo", type="primary", use_container_width=True):
            modal_crear_grupo(grupos_service)
    
    # Tabla principal de grupos (CLICABLE)
    st.markdown("### 📊 Listado de Grupos")
    
    if df_grupos.empty:
        st.info("📋 No hay grupos registrados. Crea tu primer grupo.")
    else:
        # Preparar datos para mostrar
        df_display = df_grupos.copy()
        
        # Añadir columna de estado
        df_display["Estado"] = df_display.apply(
            lambda row: determinar_estado_grupo(row.to_dict()), axis=1
        )
        
        # Seleccionar columnas para mostrar
        columnas_mostrar = [
            "codigo_grupo", 
            "accion_nombre", 
            "modalidad", 
            "fecha_inicio", 
            "fecha_fin_prevista", 
            "localidad", 
            "n_participantes_previstos", 
            "Estado"
        ]
        columnas_disponibles = [col for col in columnas_mostrar if col in df_display.columns]
        
        # Configurar selección de tabla
        selection = st.dataframe(
            df_display[columnas_disponibles],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Procesar selección de fila
        if selection.selection.rows:
            selected_idx = selection.selection.rows[0]
            grupo_seleccionado = df_grupos.iloc[selected_idx].to_dict()
            
            # Abrir modal de edición automáticamente
            modal_editar_grupo(grupos_service, grupo_seleccionado)
    
    # Manejo de grupos para finalizar (desde alertas)
    if hasattr(st.session_state, 'grupo_para_finalizar'):
        grupo = st.session_state.grupo_para_finalizar
        del st.session_state.grupo_para_finalizar
        modal_editar_grupo(grupos_service, grupo)
