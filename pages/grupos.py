import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from utils import validar_dni_cif, export_csv, export_excel
from services.grupos_service import get_grupos_service
import io


def main(supabase, session_state):
    """Punto de entrada principal de la gestión de grupos."""
    st.title("👥 Gestión de Grupos")
    st.caption("Creación y administración de grupos formativos según estándares FUNDAE.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicio
    grupos_service = get_grupos_service(supabase, session_state)

    # Inicializar session state
    if "mostrar_formulario" not in st.session_state:
        st.session_state.mostrar_formulario = False
    if "grupo_editando" not in st.session_state:
        st.session_state.grupo_editando = None

    # Cargar datos necesarios
    try:
        df_grupos = grupos_service.get_grupos_completos()
        acciones_dict = grupos_service.get_acciones_dict()
        empresas_dict = grupos_service.get_empresas_dict() if session_state.role == "admin" else {}
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # Determinar qué mostrar
    if st.session_state.mostrar_formulario:
        mostrar_formulario_grupo(grupos_service, acciones_dict, empresas_dict, session_state)
    else:
        mostrar_vista_principal(df_grupos, grupos_service, session_state)


def mostrar_avisos_grupos(grupos_service, df_grupos):
    """Muestra avisos inteligentes sobre grupos pendientes y próximos a finalizar."""
    if df_grupos.empty:
        return

    hoy = datetime.today().date()
    avisos_pendientes = []
    avisos_proximos = []

    for _, grupo in df_grupos.iterrows():
        fecha_fin_prevista = grupo.get("fecha_fin_prevista")
        estado = grupo.get("estado", "ABIERTO")
        codigo = grupo.get("codigo_grupo", "")

        if not fecha_fin_prevista:
            continue

        try:
            fecha_fin = datetime.fromisoformat(fecha_fin_prevista).date()

            # Grupos pendientes de finalización
            if fecha_fin <= hoy and estado != "FINALIZADO":
                avisos_pendientes.append(f"**{codigo}** - Finalizado el {fecha_fin.strftime('%d/%m/%Y')}")

            # Grupos próximos a finalizar (próximos 7 días)
            elif fecha_fin > hoy and (fecha_fin - hoy).days <= 7 and estado == "ABIERTO":
                dias_restantes = (fecha_fin - hoy).days
                avisos_proximos.append(f"**{codigo}** - Finaliza en {dias_restantes} día{'s' if dias_restantes != 1 else ''}")
        except:
            continue

    # Mostrar avisos (máximo 3 de cada tipo)
    if avisos_pendientes:
        st.error("⚠️ **Grupos pendientes de finalización:**")
        for aviso in avisos_pendientes[:3]:
            st.error(f"• {aviso}")
        if len(avisos_pendientes) > 3:
            st.error(f"• ... y {len(avisos_pendientes) - 3} más")

    if avisos_proximos:
        st.warning("📅 **Grupos próximos a finalizar:**")
        for aviso in avisos_proximos[:3]:
            st.warning(f"• {aviso}")
        if len(avisos_proximos) > 3:
            st.warning(f"• ... y {len(avisos_proximos) - 3} más")


def mostrar_vista_principal(df_grupos, grupos_service, session_state):
    """Muestra la tabla principal de grupos con selector dropdown."""
    st.markdown("### 📊 Grupos Formativos")

     # Mostrar avisos inteligentes
    mostrar_avisos_grupos(grupos_service, df_grupos)
    
    if df_grupos.empty:
        st.info("ℹ️ No hay grupos registrados.")
        if st.button("➕ Crear Primer Grupo", type="primary"):
            st.session_state.grupo_editando = None
            st.session_state.mostrar_formulario = True
            st.rerun()
        return

    # Selector de grupo
    col1, col2 = st.columns([3, 1])

    with col1:
        # Preparar opciones del selector
        opciones = ["Crear Nuevo Grupo"] + [
            f"{row['codigo_grupo']} - {row.get('accion_nombre', 'Sin acción')}"
            for _, row in df_grupos.iterrows()
        ]

        seleccion = st.selectbox(
            "Seleccionar grupo:",
            opciones,
            index=0,
            help="Selecciona un grupo existente para editarlo o crear uno nuevo"
        )

    with col2:
        if st.button("🔄 Actualizar", help="Recargar datos"):
            st.rerun()

    # Tabla de grupos
    if not df_grupos.empty:
        # Preparar datos para mostrar
        columnas_mostrar = [
            "codigo_grupo", "accion_nombre", "modalidad",
            "fecha_inicio", "fecha_fin_prevista", "n_participantes_previstos",
            "localidad", "empresa_nombre"
        ]

        # Filtrar columnas existentes
        columnas_existentes = [col for col in columnas_mostrar if col in df_grupos.columns]
        df_display = df_grupos[columnas_existentes].copy()

        # Renombrar columnas para mejor visualización
        columnas_nombres = {
            "codigo_grupo": "Código",
            "accion_nombre": "Acción Formativa",
            "modalidad": "Modalidad",
            "fecha_inicio": "Fecha Inicio",
            "fecha_fin_prevista": "Fecha Fin Prevista",
            "n_participantes_previstos": "Participantes",
            "localidad": "Localidad",
            "empresa_nombre": "Empresa"
        }

        df_display = df_display.rename(columns=columnas_nombres)

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True
        )

    # Procesar selección
    if seleccion and seleccion != "Crear Nuevo Grupo":
        # Extraer código del grupo de la selección
        codigo_grupo = seleccion.split(" - ")[0]
        grupo_seleccionado = df_grupos[df_grupos["codigo_grupo"] == codigo_grupo]

        if not grupo_seleccionado.empty:
            st.session_state.grupo_editando = grupo_seleccionado.iloc[0].to_dict()
            st.session_state.mostrar_formulario = True
            st.rerun()
    elif seleccion == "Crear Nuevo Grupo":
        st.session_state.grupo_editando = None
        st.session_state.mostrar_formulario = True
        st.rerun()


def mostrar_formulario_grupo(grupos_service, acciones_dict, empresas_dict, session_state):
    """Muestra el formulario unificado con secciones colapsables."""
    es_creacion = st.session_state.grupo_editando is None
    datos_actual = st.session_state.grupo_editando or {}

    # Botón volver
    if st.button("← Volver a la lista"):
        st.session_state.mostrar_formulario = False
        st.session_state.grupo_editando = None

    # Título del formulario
    if es_creacion:
        st.header("➕ Crear Nuevo Grupo")
    else:
        codigo = datos_actual.get("codigo_grupo", "")
        st.header(f"✏️ Editar Grupo: {codigo}")

    # Estado del grupo
    estado = determinar_estado_grupo(datos_actual, es_creacion)
    if estado != "ABIERTO":
        if estado == "FINALIZAR":
            st.warning("⚠️ Este grupo necesita datos de finalización")
        elif estado == "FINALIZADO":
            st.success("✅ Grupo finalizado correctamente")

    # Formulario principal
    with st.form("form_grupo"):
        grupo_id = None if es_creacion else datos_actual.get("id")

        # Sección 1: Datos Básicos FUNDAE (siempre expandida)
        with st.expander("📋 **Datos Básicos FUNDAE**", expanded=True):
            datos_basicos = mostrar_seccion_datos_basicos(datos_actual, acciones_dict, empresas_dict, session_state, es_creacion)

        # Sección 2: Horarios de Impartición (expandida por defecto)
        with st.expander("🕒 **Horarios de Impartición**", expanded=True):
            datos_horarios = mostrar_seccion_horarios(datos_actual)

        # Sección 3: Datos de Finalización (condicional)
        mostrar_finalizacion = (not es_creacion and
                               (datos_actual.get("fecha_fin_prevista") and
                                datetime.fromisoformat(datos_actual["fecha_fin_prevista"]).date() <= datetime.today().date()) or
                               estado in ["FINALIZAR", "FINALIZADO"])

        datos_finalizacion = {}
        if mostrar_finalizacion:
            with st.expander("🏁 **Datos de Finalización**", expanded=estado == "FINALIZAR"):
                datos_finalizacion = mostrar_seccion_finalizacion(datos_actual)

        # Botón guardar
        submitted = st.form_submit_button("💾 Guardar Grupo", type="primary", use_container_width=True)

        if submitted:
            procesar_formulario_grupo(grupos_service, datos_basicos, datos_horarios, datos_finalizacion,
                                    acciones_dict, empresas_dict, es_creacion, grupo_id, session_state)

    # Secciones adicionales (solo después de crear el grupo)
    if not es_creacion and grupo_id:
        st.divider()

        # Sección 4: Tutores asignados
        with st.expander("👨‍🏫 **Tutores Asignados**"):
            mostrar_seccion_tutores(grupos_service, grupo_id)

        # Sección 5: Empresas participantes
        with st.expander("🏢 **Empresas Participantes**"):
            mostrar_seccion_empresas(grupos_service, grupo_id)

        # Sección 6: Participantes del grupo
        with st.expander("👥 **Participantes del Grupo**"):
            mostrar_seccion_participantes(grupos_service, grupo_id)

        # Sección 7: Costes y bonificaciones FUNDAE
        with st.expander("💰 **Costes y Bonificaciones FUNDAE**"):
            mostrar_seccion_costes(grupos_service, grupo_id)


def mostrar_seccion_datos_basicos(datos_actual, acciones_dict, empresas_dict, session_state, es_creacion):
    """Sección 1: Datos Básicos FUNDAE."""
    col1, col2 = st.columns(2)

    with col1:
        codigo_grupo = st.text_input(
            "Código del Grupo *",
            value=datos_actual.get("codigo_grupo", ""),
            max_chars=50,
            disabled=not es_creacion,
            help="Máximo 50 caracteres. Solo editable en creación."
        )

        accion_opciones = [""] + list(acciones_dict.keys())
        accion_actual = None
        if datos_actual.get("accion_formativa"):
            for nombre, id_accion in acciones_dict.items():
                if id_accion == datos_actual["accion_formativa"].get("id"):
                    accion_actual = nombre
                    break

        accion_formativa = st.selectbox(
            "Acción Formativa *",
            accion_opciones,
            index=accion_opciones.index(accion_actual) if accion_actual in accion_opciones else 0
        )

        modalidad = st.selectbox(
            "Modalidad *",
            ["PRESENCIAL", "TELEFORMACION", "MIXTA"],
            index=["PRESENCIAL", "TELEFORMACION", "MIXTA"].index(datos_actual.get("modalidad", "PRESENCIAL"))
        )

        localidad = st.text_input(
            "Localidad *",
            value=datos_actual.get("localidad", ""),
            help="Obligatorio para FUNDAE"
        )

        fecha_inicio = st.date_input(
            "Fecha Inicio *",
            value=datetime.fromisoformat(datos_actual["fecha_inicio"]).date() if datos_actual.get("fecha_inicio") else None
        )

    with col2:
        lugar_imparticion = st.text_area(
            "Lugar de Impartición *",
            value=datos_actual.get("lugar_imparticion", ""),
            height=100
        )

        provincia = st.text_input(
            "Provincia",
            value=datos_actual.get("provincia", ""),
            help="Opcional"
        )

        cp = st.text_input(
            "Código Postal",
            value=datos_actual.get("cp", ""),
            help="Opcional"
        )

        fecha_fin_prevista = st.date_input(
            "Fecha Fin Prevista *",
            value=datetime.fromisoformat(datos_actual["fecha_fin_prevista"]).date() if datos_actual.get("fecha_fin_prevista") else None
        )

        n_participantes_previstos = st.number_input(
            "Participantes Previstos *",
            min_value=1,
            max_value=30,
            value=int(datos_actual.get("n_participantes_previstos", 1))
        )

    observaciones = st.text_area(
        "Observaciones",
        value=datos_actual.get("observaciones", ""),
        help="Información adicional"
    )

    # Empresa propietaria (solo visible para admin)
    empresa_id = None
    if session_state.role == "admin" and empresas_dict:
        empresa_actual = None
        if datos_actual.get("empresa"):
            empresa_actual = datos_actual["empresa"].get("nombre")
        elif datos_actual.get("empresa_id"):
            for nombre, id_emp in empresas_dict.items():
                if id_emp == datos_actual["empresa_id"]:
                    empresa_actual = nombre
                    break

        empresa_opciones = [""] + list(empresas_dict.keys())
        empresa_seleccionada = st.selectbox(
            "Empresa Propietaria",
            empresa_opciones,
            index=empresa_opciones.index(empresa_actual) if empresa_actual in empresa_opciones else 0
        )
        empresa_id = empresas_dict.get(empresa_seleccionada) if empresa_seleccionada else None

    return {
        "codigo_grupo": codigo_grupo,
        "accion_formativa": accion_formativa,
        "modalidad": modalidad,
        "lugar_imparticion": lugar_imparticion,
        "localidad": localidad,
        "provincia": provincia,
        "cp": cp,
        "fecha_inicio": fecha_inicio,
        "fecha_fin_prevista": fecha_fin_prevista,
        "n_participantes_previstos": n_participantes_previstos,
        "observaciones": observaciones,
        "empresa_id": empresa_id
    }


def mostrar_seccion_horarios(datos_actual):
    """Sección 2: Horarios de Impartición."""
    st.markdown("**Configuración de Horarios**")

    # Parsear horario existente si existe
    horario_actual = datos_actual.get("horario", "")
    m_inicio, m_fin, t_inicio, t_fin, dias_actuales = None, None, None, None, []

    if horario_actual:
        try:
            # Parsear horario existente (implementar según formato actual)
            # Por ahora, usar valores por defecto
            pass
        except:
            pass

    # Radio buttons para tipo de horario
    tipo_horario = st.radio(
        "Tipo de Horario:",
        ["Solo Mañana", "Solo Tarde", "Mañana y Tarde"],
        horizontal=True
    )

    col1, col2 = st.columns(2)

    with col1:
        if tipo_horario in ["Solo Mañana", "Mañana y Tarde"]:
            st.markdown("**Horario de Mañana**")
            m_inicio = st.time_input("Inicio Mañana", value=time(9, 0), step=900)  # 15 min intervals
            m_fin = st.time_input("Fin Mañana", value=time(13, 0), step=900)
        else:
            m_inicio = m_fin = None

    with col2:
        if tipo_horario in ["Solo Tarde", "Mañana y Tarde"]:
            st.markdown("**Horario de Tarde**")
            t_inicio = st.time_input("Inicio Tarde", value=time(15, 0), step=900)
            t_fin = st.time_input("Fin Tarde", value=time(19, 0), step=900)
        else:
            t_inicio = t_fin = None

    # Días de la semana
    st.markdown("**Días de Impartición**")
    dias_semana = ["L", "M", "X", "J", "V", "S", "D"]
    dias_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    cols = st.columns(7)
    dias_seleccionados = []

    for i, (dia, nombre) in enumerate(zip(dias_semana, dias_nombres)):
        with cols[i]:
            # L-V seleccionados por defecto
            default_value = dia in (dias_actuales if dias_actuales else ["L", "M", "X", "J", "V"])
            if st.checkbox(dia, value=default_value, help=nombre):
                dias_seleccionados.append(dia)

    return {
        "m_inicio": m_inicio,
        "m_fin": m_fin,
        "t_inicio": t_inicio,
        "t_fin": t_fin,
        "dias": dias_seleccionados
    }


def mostrar_seccion_finalizacion(datos_actual):
    """Sección 3: Datos de Finalización."""
    st.info("ℹ️ Complete los datos de finalización para cumplir con FUNDAE")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        fecha_fin = st.date_input(
            "Fecha Fin Real *",
            value=datetime.fromisoformat(datos_actual["fecha_fin"]).date() if datos_actual.get("fecha_fin") else None
        )

    with col2:
        n_finalizados = st.number_input(
            "Participantes Finalizados *",
            min_value=0,
            value=int(datos_actual.get("n_participantes_finalizados", 0))
        )

    with col3:
        n_aptos = st.number_input(
            "Número de Aptos *",
            min_value=0,
            value=int(datos_actual.get("n_aptos", 0))
        )

    with col4:
        n_no_aptos = st.number_input(
            "Número de No Aptos *",
            min_value=0,
            value=int(datos_actual.get("n_no_aptos", 0))
        )

    # Validación en tiempo real
    if n_aptos + n_no_aptos != n_finalizados and n_finalizados > 0:
        st.error("⚠️ La suma de Aptos y No Aptos debe coincidir con Finalizados")

    return {
        "fecha_fin": fecha_fin,
        "n_participantes_finalizados": n_finalizados,
        "n_aptos": n_aptos,
        "n_no_aptos": n_no_aptos
    }


def mostrar_seccion_tutores(grupos_service, grupo_id):
    """Sección 4: Tutores asignados."""
    try:
        df_tutores = grupos_service.get_tutores_grupo(grupo_id)

        if not df_tutores.empty:
            st.markdown("**Tutores Actuales:**")
            tutores_display = []
            for _, row in df_tutores.iterrows():
                tutor = row.get("tutor", {}) or {}
                tutores_display.append({
                    "Nombre": f"{tutor.get('nombre', '')} {tutor.get('apellidos', '')}".strip(),
                    "Email": tutor.get("email", ""),
                    "Especialidad": tutor.get("especialidad", "")
                })

            st.dataframe(pd.DataFrame(tutores_display), use_container_width=True, hide_index=True)
        else:
            st.info("No hay tutores asignados")

        # Formulario para añadir tutores
        with st.form("add_tutores"):
            df_disponibles = grupos_service.get_tutores_completos()
            if not df_disponibles.empty:
                asignados_ids = {(row.get("tutor") or {}).get("id") for _, row in df_tutores.iterrows()}
                df_disponibles = df_disponibles[~df_disponibles["id"].isin(asignados_ids)]

                if not df_disponibles.empty:
                    opciones = {row["nombre_completo"]: row["id"] for _, row in df_disponibles.iterrows()}
                    seleccion = st.multiselect("Seleccionar tutores:", opciones.keys())

                    if st.form_submit_button("Asignar Tutores"):
                        for nombre in seleccion:
                            grupos_service.create_tutor_grupo(grupo_id, opciones[nombre])
                        st.success(f"✅ {len(seleccion)} tutores asignados")
                        st.rerun()
                else:
                    st.info("Todos los tutores están asignados")
            else:
                st.info("No hay tutores disponibles")

    except Exception as e:
        st.error(f"Error al cargar tutores: {e}")


def mostrar_seccion_empresas(grupos_service, grupo_id):
    """Sección 5: Empresas participantes."""
    try:
        df_empresas = grupos_service.get_empresas_grupo(grupo_id)

        if not df_empresas.empty:
            st.markdown("**Empresas Participantes:**")
            empresas_display = []
            for _, row in df_empresas.iterrows():
                emp = row.get("empresa", {}) or {}
                empresas_display.append({
                    "Nombre": emp.get("nombre", ""),
                    "CIF": emp.get("cif", ""),
                    "Fecha Asignación": row.get("fecha_asignacion", "")
                })

            st.dataframe(pd.DataFrame(empresas_display), use_container_width=True, hide_index=True)
        else:
            st.info("No hay empresas participantes")

        # Solo admin puede gestionar empresas
        if st.session_state.get("role") == "admin":
            with st.form("add_empresas"):
                empresas_dict = grupos_service.get_empresas_dict()
                asignadas = {(row.get("empresa") or {}).get("nombre") for _, row in df_empresas.iterrows()}
                disponibles = {nombre: id_emp for nombre, id_emp in empresas_dict.items() if nombre not in asignadas}

                if disponibles:
                    seleccion = st.multiselect("Seleccionar empresas:", disponibles.keys())

                    if st.form_submit_button("Asignar Empresas"):
                        for nombre in seleccion:
                            grupos_service.create_empresa_grupo(grupo_id, disponibles[nombre])
                        st.success(f"✅ {len(seleccion)} empresas asignadas")
                        st.rerun()
                else:
                    st.info("Todas las empresas están asignadas")

    except Exception as e:
        st.error(f"Error al cargar empresas: {e}")


def mostrar_seccion_participantes(grupos_service, grupo_id):
    """Sección 6: Participantes del grupo."""
    try:
        df_participantes = grupos_service.get_participantes_grupo(grupo_id)

        if not df_participantes.empty:
            st.markdown("**Participantes Actuales:**")
            columnas_mostrar = ["nif", "nombre", "apellidos", "email", "telefono"]
            columnas_existentes = [c for c in columnas_mostrar if c in df_participantes.columns]

            st.dataframe(
                df_participantes[columnas_existentes],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No hay participantes asignados")

        # Tabs para gestión
        tab1, tab2 = st.tabs(["📋 Asignación Individual", "📊 Importación Excel"])

        with tab1:
            with st.form("add_participantes"):
                df_disponibles = grupos_service.get_participantes_disponibles(grupo_id)
                if not df_disponibles.empty:
                    opciones = {
                        f"{row['nif']} - {row['nombre']} {row['apellidos']}": row["id"]
                        for _, row in df_disponibles.iterrows()
                    }
                    seleccion = st.multiselect("Seleccionar participantes:", opciones.keys())

                    if st.form_submit_button("Asignar Participantes"):
                        for sel in seleccion:
                            grupos_service.asignar_participante_a_grupo(opciones[sel], grupo_id)
                        st.success(f"✅ {len(seleccion)} participantes asignados")
                        st.rerun()
                else:
                    st.info("No hay participantes disponibles")

        with tab2:
            procesar_excel_participantes(grupos_service, grupo_id)

    except Exception as e:
        st.error(f"Error al cargar participantes: {e}")


def mostrar_seccion_costes(grupos_service, grupo_id):
    """Sección 7: Costes y bonificaciones FUNDAE."""
    try:
        # Obtener datos del grupo para cálculos
        grupo_info = grupos_service.supabase.table("grupos").select("""
            modalidad, n_participantes_previstos,
            accion_formativa:acciones_formativas(num_horas)
        """).eq("id", grupo_id).execute()

        if not grupo_info.data:
            st.error("No se pudo cargar información del grupo")
            return

        datos = grupo_info.data[0]
        modalidad = datos.get("modalidad", "PRESENCIAL")
        participantes = int(datos.get("n_participantes_previstos", 0))
        horas = int((datos.get("accion_formativa") or {}).get("num_horas", 0))

        # Calcular límite FUNDAE
        limite_boni, tarifa_max = grupos_service.calcular_limite_fundae(modalidad, horas, participantes)

        st.markdown("**Información de Cálculo:**")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Modalidad", modalidad)
        col2.metric("Participantes", participantes)
        col3.metric("Horas", horas)
        col4.metric("Límite Bonificación", f"{limite_boni:,.2f} €")

        # Formulario de costes
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
                costes_salariales = st.number_input(
                    "Costes Salariales (€)",
                    value=float(costes_actuales.get("costes_salariales", 0)),
                    min_value=0.0
                )
                tarifa_hora = st.number_input(
                    "Tarifa por Hora (€)",
                    value=float(costes_actuales.get("tarifa_hora", tarifa_max)),
                    min_value=0.0,
                    max_value=tarifa_max,
                    help=f"Máximo: {tarifa_max} €/h para {modalidad}"
                )

            observaciones = st.text_area(
                "Observaciones",
                value=costes_actuales.get("observaciones", "")
            )

            if st.form_submit_button("💾 Guardar Costes"):
                datos_costes = {
                    "grupo_id": grupo_id,
                    "costes_directos": costes_directos,
                    "costes_indirectos": costes_indirectos,
                    "costes_salariales": costes_salariales,
                    "tarifa_hora": tarifa_hora,
                    "observaciones": observaciones,
                    "updated_at": datetime.utcnow().isoformat()
                }

                if costes_actuales:
                    grupos_service.update_grupo_coste(grupo_id, datos_costes)
                else:
                    grupos_service.create_grupo_coste(datos_costes)

                st.success("✅ Costes guardados")
                st.rerun()

    except Exception as e:
        st.error(f"Error al cargar costes: {e}")


def procesar_excel_participantes(grupos_service, grupo_id):
    """Procesa importación masiva de participantes desde Excel."""
    st.markdown("**Importación desde Excel:**")
    st.markdown("1. Sube un archivo Excel con columna 'dni' o 'nif'")
    st.markdown("2. Se buscarán participantes existentes por NIF")
    st.markdown("3. Solo se asignarán los disponibles")

    uploaded_file = st.file_uploader("Subir Excel", type=["xlsx"])

    if uploaded_file:
        try:
            df_import = pd.read_excel(uploaded_file)

            # Detectar columna de NIF
            col_nif = None
            for col in ["dni", "nif", "DNI", "NIF"]:
                if col in df_import.columns:
                    col_nif = col
                    break

            if not col_nif:
                st.error("El archivo debe contener una columna 'dni' o 'nif'")
                return

            st.dataframe(df_import.head(), use_container_width=True)

            if st.button("🚀 Procesar Importación"):
                nifs = [str(d).strip() for d in df_import[col_nif] if pd.notna(d)]
                nifs_validos = [d for d in nifs if validar_dni_cif(d)]

                df_disponibles = grupos_service.get_participantes_disponibles(grupo_id)
                disponibles = {p["nif"]: p["id"] for _, p in df_disponibles.iterrows()}

                asignados = 0
                errores = []

                for nif in nifs_validos:
                    part_id = disponibles.get(nif)
                    if not part_id:
                        errores.append(f"NIF {nif} no encontrado")
                        continue

                    try:
                        grupos_service.asignar_participante_a_grupo(part_id, grupo_id)
                        asignados += 1
                    except Exception as e:
                        errores.append(f"NIF {nif}: {str(e)}")

                if asignados > 0:
                    st.success(f"✅ {asignados} participantes asignados")
                if errores:
                    for error in errores[:5]:
                        st.warning(f"⚠️ {error}")

                if asignados > 0:
                    st.rerun()

        except Exception as e:
            st.error(f"Error al procesar archivo: {e}")


def procesar_formulario_grupo(grupos_service, datos_basicos, datos_horarios, datos_finalizacion,
                             acciones_dict, empresas_dict, es_creacion, grupo_id, session_state):
    """Procesa y guarda el formulario del grupo."""
    # Validar datos básicos
    errores = validar_datos_grupo(datos_basicos, acciones_dict, es_creacion)

    if errores:
        for error in errores:
            st.error(f"❌ {error}")
        return

    # Construir horario
    horario = build_horario_string(
        datos_horarios["m_inicio"], datos_horarios["m_fin"],
        datos_horarios["t_inicio"], datos_horarios["t_fin"],
        datos_horarios["dias"]
    )

    # Preparar datos para guardar
    datos_grupo = preparar_datos_grupo(datos_basicos, acciones_dict, empresas_dict, horario, session_state)

    # Añadir datos de finalización si corresponde
    if datos_finalizacion:
        for key, value in datos_finalizacion.items():
            if key == "fecha_fin" and value:
                datos_grupo[key] = value.isoformat()
            elif value is not None:
                datos_grupo[key] = value

    # Validación FUNDAE
    tipo_xml = "finalizacion" if datos_finalizacion else "inicio"
    es_valido, errores_fundae = grupos_service.validar_grupo_fundae(datos_grupo, tipo_xml)

    if not es_valido:
        st.error("❌ Errores de validación FUNDAE:")
        for error in errores_fundae:
            st.error(f"• {error}")
        return

    # Guardar grupo
    try:
        if es_creacion:
            if grupos_service.create_grupo_completo(datos_grupo):
                st.success("✅ Grupo creado correctamente")
                st.session_state.mostrar_formulario = False
                st.session_state.grupo_editando = None
                st.rerun()
        else:
            if grupos_service.update_grupo(grupo_id, datos_grupo):
                st.success("✅ Grupo actualizado correctamente")
                st.session_state.mostrar_formulario = False
                st.session_state.grupo_editando = None
                st.rerun()
    except Exception as e:
        st.error(f"❌ Error al guardar: {e}")


def validar_datos_grupo(datos, acciones_dict, es_creacion):
    """Valida los datos del grupo antes de guardar."""
    errores = []

    # Validaciones básicas
    if not datos.get("codigo_grupo"):
        errores.append("Código del grupo es obligatorio")

    if not datos.get("accion_formativa") or datos["accion_formativa"] not in acciones_dict:
        errores.append("Debe seleccionar una acción formativa válida")

    if not datos.get("localidad"):
        errores.append("Localidad es obligatoria")

    if not datos.get("lugar_imparticion"):
        errores.append("Lugar de impartición es obligatorio")

    if not datos.get("fecha_inicio"):
        errores.append("Fecha de inicio es obligatoria")

    if not datos.get("fecha_fin_prevista"):
        errores.append("Fecha fin prevista es obligatoria")

    # Validar fechas
    if datos.get("fecha_inicio") and datos.get("fecha_fin_prevista"):
        if datos["fecha_fin_prevista"] <= datos["fecha_inicio"]:
            errores.append("Fecha fin prevista debe ser posterior a fecha de inicio")

    # Validar participantes
    participantes = datos.get("n_participantes_previstos", 0)
    if participantes < 1 or participantes > 30:
        errores.append("Participantes previstos debe estar entre 1 y 30")

    return errores


def preparar_datos_grupo(datos_formulario, acciones_dict, empresas_dict, horario, session_state):
    """Prepara los datos del grupo para guardar en la base de datos."""
    datos_grupo = {
        "codigo_grupo": datos_formulario["codigo_grupo"],
        "accion_formativa_id": acciones_dict[datos_formulario["accion_formativa"]],
        "modalidad": datos_formulario["modalidad"],
        "lugar_imparticion": datos_formulario["lugar_imparticion"],
        "localidad": datos_formulario["localidad"],
        "provincia": datos_formulario.get("provincia") or None,
        "cp": datos_formulario.get("cp") or None,
        "fecha_inicio": datos_formulario["fecha_inicio"].isoformat(),
        "fecha_fin_prevista": datos_formulario["fecha_fin_prevista"].isoformat(),
        "n_participantes_previstos": datos_formulario["n_participantes_previstos"],
        "horario": horario,
        "observaciones": datos_formulario.get("observaciones") or None,
        "updated_at": datetime.utcnow().isoformat()
    }

    # Asignar empresa según rol
    if session_state.role == "gestor":
        datos_grupo["empresa_id"] = session_state.user.get("empresa_id")
    elif datos_formulario.get("empresa_id"):
        datos_grupo["empresa_id"] = datos_formulario["empresa_id"]

    return datos_grupo


def build_horario_string(m_inicio, m_fin, t_inicio, t_fin, dias):
    """Construye string de horario en formato FUNDAE."""
    partes = []

    if m_inicio and m_fin:
        partes.append(f"Mañana: {m_inicio.strftime('%H:%M')} - {m_fin.strftime('%H:%M')}")

    if t_inicio and t_fin:
        partes.append(f"Tarde: {t_inicio.strftime('%H:%M')} - {t_fin.strftime('%H:%M')}")

    if dias:
        partes.append(f"Días: {'-'.join(dias)}")

    return " | ".join(partes)


def determinar_estado_grupo(datos_grupo, es_creacion):
    """Determina el estado automático del grupo."""
    if es_creacion:
        return "ABIERTO"

    # Verificar si tiene datos de finalización completos
    if (datos_grupo.get("fecha_fin") and
        datos_grupo.get("n_participantes_finalizados") is not None and
        datos_grupo.get("n_aptos") is not None and
        datos_grupo.get("n_no_aptos") is not None):
        return "FINALIZADO"

    # Verificar si la fecha fin prevista ya pasó
    fecha_fin_prevista = datos_grupo.get("fecha_fin_prevista")
    if fecha_fin_prevista:
        try:
            fecha_fin = datetime.fromisoformat(fecha_fin_prevista).date()
            if fecha_fin <= datetime.today().date():
                return "FINALIZAR"
        except:
            pass

    return "ABIERTO"


def get_grupos_service(supabase, session_state):
    """Factory function para obtener el servicio de grupos."""
    from services.grupos_service import GruposService
    return GruposService(supabase, session_state)
