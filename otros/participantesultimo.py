import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
from utils import validar_dni_cif, export_csv, get_ajustes_app
from services.participantes_service import get_participantes_service
from services.grupos_service import get_grupos_service
import re

EMAIL_REGEX = r"^[^@]+@[^@]+\.[^@]+$"

def generar_plantilla_excel(rol):
    """Genera plantilla Excel para importación masiva de participantes."""
    columnas = ["nombre", "apellidos", "email", "nif", "telefono"]
    if rol == "admin":
        columnas += ["empresa"]
    columnas.append("grupo")
    
    df = pd.DataFrame(columns=columnas)
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer

def main(supabase, session_state):
    st.markdown("## 👨‍🎓 Participantes")
    st.caption("Gestión de participantes con soporte para jerarquía de empresas y Streamlit 1.49")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return
        
    # Inicializar servicios con jerarquía
    participantes_service = get_participantes_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)

    # =========================
    # Cargar datos con jerarquía
    # =========================
    with st.spinner("Cargando datos..."):
        try:
            df_participantes = participantes_service.get_participantes_con_jerarquia()
            empresas_dict = participantes_service.get_empresas_para_participantes()
            grupos_dict = grupos_service.get_grupos_dict()
            
        except Exception as e:
            st.error(f"❌ Error al cargar datos: {e}")
            return

    # =========================
    # Métricas modernas con jerarquía (Streamlit 1.49)
    # =========================
    if not df_participantes.empty:
        estadisticas = participantes_service.get_estadisticas_participantes_jerarquia()
        
        # Métricas principales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("👨‍🎓 Total Participantes", estadisticas.get("total", 0))
        
        with col2:
            con_grupo = estadisticas.get("con_grupo", 0)
            st.metric("👥 Con Grupo", con_grupo)
        
        with col3:
            sin_grupo = estadisticas.get("sin_grupo", 0)
            st.metric("📊 Sin Asignar", sin_grupo)
        
        with col4:
            # Mostrar empresa más activa
            por_empresa = estadisticas.get("por_empresa", {})
            empresa_top = list(por_empresa.keys())[0] if por_empresa else "N/A"
            st.metric("🏢 Empresa Más Activa", empresa_top[:20])

        # Métricas jerárquicas adicionales
        if estadisticas.get("por_tipo_empresa"):
            st.markdown("#### 📈 Distribución por Tipo de Empresa")
            tipo_stats = estadisticas["por_tipo_empresa"]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Cliente SaaS", tipo_stats.get("CLIENTE_SAAS", 0))
            with col2:
                st.metric("Gestoras", tipo_stats.get("GESTORA", 0))
            with col3:
                st.metric("Clientes de Gestora", tipo_stats.get("CLIENTE_GESTOR", 0))

    st.divider()

    # =========================
    # Filtros de búsqueda modernos con jerarquía
    # =========================
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        query = st.text_input("🔍 Buscar por nombre, email o NIF")
    
    with col2:
        grupo_filter = st.selectbox("Filtrar por grupo", ["Todos"] + sorted(grupos_dict.keys()))
    
    with col3:
        if session_state.role == "admin":
            empresa_filter = st.selectbox("Filtrar por empresa", ["Todas"] + sorted(empresas_dict.keys()))
        else:
            # Mostrar información de empresas gestionadas
            empresas_gestionadas = len(empresas_dict)
            st.metric("Empresas Gestionadas", empresas_gestionadas)
            empresa_filter = "Todas"
    
    with col4:
        estado_filter = st.selectbox("Estado de Asignación", ["Todos", "Con Grupo", "Sin Grupo"])

    # Aplicar filtros con jerarquía
    filtros = {
        "query": query,
        "grupo_id": grupos_dict.get(grupo_filter) if grupo_filter != "Todos" else None,
        "empresa_id": empresas_dict.get(empresa_filter) if session_state.role == "admin" and empresa_filter != "Todas" else None,
        "estado_asignacion": {
            "Con Grupo": "con_grupo",
            "Sin Grupo": "sin_grupo"
        }.get(estado_filter)
    }
    
    df_filtered = participantes_service.search_participantes_jerarquia(filtros)

    # =========================
    # Funciones CRUD modernas con jerarquía
    # =========================
    def crear_participante_jerarquia(datos_nuevos):
        """Crea participante usando el servicio con jerarquía."""
        try:
            # Convertir empresa_sel a empresa_id
            if "empresa_sel" in datos_nuevos:
                empresa_sel = datos_nuevos.pop("empresa_sel", "")
                if empresa_sel and empresa_sel in empresas_dict:
                    datos_nuevos["empresa_id"] = empresas_dict[empresa_sel]
                else:
                    st.error("⚠️ Debe seleccionar una empresa válida.")
                    return False
            
            # Convertir grupo_sel a grupo_id (relación directa)
            if "grupo_sel" in datos_nuevos:
                grupo_sel = datos_nuevos.pop("grupo_sel", "")
                if grupo_sel and grupo_sel in grupos_dict:
                    datos_nuevos["grupo_id"] = grupos_dict[grupo_sel]
                else:
                    datos_nuevos["grupo_id"] = None
            
            return participantes_service.create_participante_con_jerarquia(datos_nuevos)
            
        except Exception as e:
            st.error(f"❌ Error al crear participante: {e}")
            return False

    def actualizar_participante_jerarquia(participante_id, datos_editados):
        """Actualiza participante usando el servicio con jerarquía."""
        try:
            # Convertir selects a IDs
            if "empresa_sel" in datos_editados:
                empresa_sel = datos_editados.pop("empresa_sel", "")
                if empresa_sel and empresa_sel in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[empresa_sel]
                else:
                    st.error("⚠️ Debe seleccionar una empresa válida.")
                    return False
            
            if "grupo_sel" in datos_editados:
                grupo_sel = datos_editados.pop("grupo_sel", "")
                if grupo_sel and grupo_sel in grupos_dict:
                    datos_editados["grupo_id"] = grupos_dict[grupo_sel]
                else:
                    datos_editados["grupo_id"] = None
            
            return participantes_service.update_participante_con_jerarquia(participante_id, datos_editados)
            
        except Exception as e:
            st.error(f"❌ Error al actualizar participante: {e}")
            return False

    def eliminar_participante_jerarquia(participante_id):
        """Elimina participante usando el servicio con jerarquía."""
        return participantes_service.delete_participante_con_jerarquia(participante_id)

    # =========================
    # Tabla principal moderna (Streamlit 1.49)
    # =========================
    st.markdown("### 📊 Listado de Participantes")
    
    if df_filtered.empty:
        st.info("📋 No hay participantes que coincidan con los filtros aplicados.")
        
        # Mostrar información de contexto según rol
        if session_state.role == "gestor":
            st.info("💡 Como gestor, puedes crear participantes para tu empresa y empresas clientes.")
        
    else:
        # Preparar datos para display con información jerárquica
        df_display = df_filtered.copy()
        
        # Seleccionar columnas para mostrar con información jerárquica
        columnas_mostrar = ["nombre", "apellidos", "email", "nif", "telefono"]
        
        if "empresa_display" in df_display.columns:
            columnas_mostrar.append("empresa_display")
        elif "empresa_nombre" in df_display.columns:
            columnas_mostrar.append("empresa_nombre")
            
        if "grupo_codigo" in df_display.columns:
            columnas_mostrar.append("grupo_codigo")

        # Configuración de columnas moderna
        column_config = {
            "nombre": st.column_config.TextColumn("👤 Nombre", width="medium"),
            "apellidos": st.column_config.TextColumn("👤 Apellidos", width="medium"),
            "email": st.column_config.TextColumn("📧 Email", width="large"),
            "nif": st.column_config.TextColumn("📄 NIF", width="small"),
            "telefono": st.column_config.TextColumn("📞 Teléfono", width="medium"),
            "empresa_display": st.column_config.TextColumn("🏢 Empresa", width="large"),
            "empresa_nombre": st.column_config.TextColumn("🏢 Empresa", width="large"),
            "grupo_codigo": st.column_config.TextColumn("📚 Grupo", width="medium")
        }

        # Mostrar tabla con selección moderna (Streamlit 1.49)
        event = st.dataframe(
            df_display[columnas_mostrar],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config=column_config
        )

        # Procesar selección para edición
        if event.selection.rows:
            selected_idx = event.selection.rows[0]
            participante_seleccionado = df_display.iloc[selected_idx].to_dict()
            st.session_state.participante_seleccionado = participante_seleccionado

    st.divider()

    # =========================
    # Botones de acción modernos
    # =========================
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("➕ Crear Nuevo Participante", type="primary", use_container_width=True):
            st.session_state.participante_seleccionado = "nuevo"
    
    with col2:
        if st.button("📊 Exportar CSV", use_container_width=True):
            if not df_filtered.empty:
                csv_data = export_csv(df_filtered)
                st.download_button(
                    label="⬇️ Descargar",
                    data=csv_data,
                    file_name=f"participantes_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No hay datos para exportar")
    
    with col3:
        if st.button("🔄 Actualizar", use_container_width=True):
            participantes_service.get_participantes_con_jerarquia.clear()
            st.rerun()

    # =========================
    # Formulario moderno según estado
    # =========================
    if hasattr(st.session_state, 'participante_seleccionado'):
        if st.session_state.participante_seleccionado == "nuevo":
            # Mostrar formulario de creación moderno
            mostrar_formulario_participante_moderno(
                empresas_dict, grupos_dict, session_state,
                crear_participante_jerarquia, es_creacion=True
            )
        elif st.session_state.participante_seleccionado:
            # Mostrar formulario de edición moderno
            mostrar_formulario_participante_moderno(
                empresas_dict, grupos_dict, session_state,
                actualizar_participante_jerarquia,
                participante_data=st.session_state.participante_seleccionado,
                es_creacion=False
            )

    # =========================
    # GESTIÓN DE DIPLOMAS MODERNA (del backup3.py)
    # =========================
    if session_state.role in ["admin", "gestor"]:
        mostrar_seccion_diplomas_moderna(supabase, session_state, participantes_service)

    # =========================
    # IMPORTACIÓN MASIVA MODERNA
    # =========================
    mostrar_importacion_masiva_moderna(
        supabase, session_state, participantes_service, 
        empresas_dict, grupos_dict
    )

    # Información contextual según rol
    st.divider()
    if session_state.role == "gestor":
        st.caption("💡 Como gestor, gestionas participantes de tu empresa y empresas clientes.")
    else:
        st.caption("💡 Los participantes pueden pertenecer a diferentes tipos de empresas según la jerarquía.")


def mostrar_formulario_participante_moderno(empresas_dict, grupos_dict, session_state, 
                                          save_func, participante_data=None, es_creacion=False):
    """Formulario moderno para crear/editar participantes."""
    
    if es_creacion:
        st.markdown("### ➕ Crear Nuevo Participante")
        st.caption("💡 Complete los datos obligatorios para crear el participante")
    else:
        email = participante_data.get("email", "Sin email")
        st.markdown(f"### ✏️ Editar Participante: {email}")

    # Usar formulario con key único
    form_key = f"participante_form_{participante_data.get('id', 'nuevo')}_{datetime.now().timestamp()}"
    
    with st.form(form_key, clear_on_submit=es_creacion):
        
        # Datos básicos
        with st.container(border=True):
            st.markdown("### 👤 Datos Básicos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                email = st.text_input(
                    "📧 Email *",
                    value=participante_data.get("email", "") if participante_data else "",
                    help="Email único del participante (obligatorio)"
                )
                
                nombre = st.text_input(
                    "👤 Nombre *",
                    value=participante_data.get("nombre", "") if participante_data else "",
                    help="Nombre del participante (obligatorio)"
                )
                
                nif = st.text_input(
                    "📄 NIF/DNI",
                    value=participante_data.get("nif", "") if participante_data else "",
                    help="NIF/DNI válido (opcional)"
                )
                
                fecha_nacimiento = st.date_input(
                    "📅 Fecha de Nacimiento",
                    value=participante_data.get("fecha_nacimiento") if participante_data and participante_data.get("fecha_nacimiento") else None,
                    help="Fecha de nacimiento del participante"
                )
            
            with col2:
                apellidos = st.text_input(
                    "👤 Apellidos",
                    value=participante_data.get("apellidos", "") if participante_data else "",
                    help="Apellidos del participante"
                )
                
                telefono = st.text_input(
                    "📞 Teléfono",
                    value=participante_data.get("telefono", "") if participante_data else "",
                    help="Teléfono de contacto"
                )
                
                sexo = st.selectbox(
                    "⚥ Sexo",
                    ["", "M", "F"],
                    index=["", "M", "F"].index(participante_data.get("sexo", "")) if participante_data and participante_data.get("sexo") in ["", "M", "F"] else 0,
                    help="Sexo del participante (M/F)"
                )
                
                tipo_documento = st.selectbox(
                    "📋 Tipo de Documento",
                    ["", "NIF", "NIE", "Pasaporte"],
                    index=["", "NIF", "NIE", "Pasaporte"].index(participante_data.get("tipo_documento", "")) if participante_data and participante_data.get("tipo_documento") in ["", "NIF", "NIE", "Pasaporte"] else 0,
                    help="Tipo de documento de identidad (obligatorio FUNDAE)"
                )
            
            # NISS
            niss = st.text_input(
                "🆔 NISS (Número de Seguridad Social)",
                value=participante_data.get("niss", "") if participante_data else "",
                help="Número de la Seguridad Social (12 dígitos, obligatorio FUNDAE)",
                max_chars=12
            )
        
        # Asignaciones
        with st.container(border=True):
            st.markdown("### 🏢 Asignaciones")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Empresa (obligatoria)
                if session_state.role == "admin":
                    empresa_actual = ""
                    if participante_data and "empresa_display" in participante_data:
                        empresa_actual = participante_data["empresa_display"]
                    elif participante_data and "empresa_nombre" in participante_data:
                        empresa_actual = participante_data["empresa_nombre"]
                    
                    empresa_sel = st.selectbox(
                        "🏢 Empresa *",
                        [""] + sorted(empresas_dict.keys()),
                        index=([""] + sorted(empresas_dict.keys())).index(empresa_actual) if empresa_actual in empresas_dict.keys() else 0,
                        help="Empresa del participante (obligatorio)"
                    )
                else:
                    st.info("🏢 Se asignará automáticamente a tu empresa")
                    empresa_sel = ""
            
            with col2:
                # Grupo (opcional)
                grupo_actual = ""
                if participante_data and "grupo_codigo" in participante_data:
                    grupo_actual = participante_data["grupo_codigo"]
                
                grupo_sel = st.selectbox(
                    "📚 Grupo Formativo",
                    [""] + sorted(grupos_dict.keys()),
                    index=([""] + sorted(grupos_dict.keys())).index(grupo_actual) if grupo_actual in grupos_dict.keys() else 0,
                    help="Grupo formativo asignado (opcional)"
                )
        
        # Validaciones
        errores = []
        if not email:
            errores.append("Email es obligatorio")
        elif not re.match(EMAIL_REGEX, email):
            errores.append("Email no válido")
        
        if not nombre:
            errores.append("Nombre es obligatorio")
        
        if nif and not validar_dni_cif(nif):
            errores.append("NIF/DNI no válido")
        
        if niss and not re.match(r'^\d{12}$', niss):
            errores.append("NISS debe tener exactamente 12 dígitos")
        
        if session_state.role == "admin" and not empresa_sel:
            errores.append("Debe seleccionar una empresa")
        
        # Mostrar errores
        if errores:
            st.error("❌ Errores encontrados:")
            for error in errores:
                st.error(f"• {error}")
        
        # Botones de acción
        st.divider()
        
        if es_creacion:
            col1, col2 = st.columns([2, 1])
            with col1:
                submitted = st.form_submit_button(
                    "➕ Crear Participante", 
                    type="primary", 
                    use_container_width=True,
                    disabled=len(errores) > 0
                )
            with col2:
                cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)
        else:
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button(
                    "💾 Guardar Cambios", 
                    type="primary", 
                    use_container_width=True,
                    disabled=len(errores) > 0
                )
            with col2:
                cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)
        
        # Procesar formulario
        if submitted and len(errores) == 0:
            datos_para_guardar = {
                "email": email,
                "nombre": nombre,
                "apellidos": apellidos,
                "nif": nif,
                "telefono": telefono,
                "fecha_nacimiento": fecha_nacimiento.isoformat() if fecha_nacimiento else None,
                "sexo": sexo,
                "tipo_documento": tipo_documento,
                "niss": niss,
                "empresa_sel": empresa_sel,
                "grupo_sel": grupo_sel
            }
            
            try:
                if es_creacion:
                    if save_func(datos_para_guardar):
                        st.success("✅ Participante creado correctamente")
                        st.session_state.participante_seleccionado = None
                        st.rerun()
                else:
                    if save_func(participante_data["id"], datos_para_guardar):
                        st.success("✅ Cambios guardados correctamente")
                        st.session_state.participante_seleccionado = None
                        st.rerun()
            except Exception as e:
                st.error(f"❌ Error al procesar participante: {e}")
        
        elif cancelar:
            st.session_state.participante_seleccionado = None
            st.rerun()


def mostrar_seccion_diplomas_moderna(supabase, session_state, participantes_service):
    """Gestión completa de diplomas con jerarquía empresarial y subida de archivos."""
    with st.expander("🏅 Gestión de Diplomas", expanded=False):
        st.markdown("**Subir y gestionar diplomas respetando jerarquía de empresas**")
        
        try:
            # Obtener grupos finalizados con filtro jerárquico
            empresas_permitidas = participantes_service._get_empresas_gestionables()
            if not empresas_permitidas:
                st.info("No tienes grupos finalizados disponibles.")
                return
            
            hoy = datetime.now().date()
            
            # Consulta con filtro jerárquico
            query = supabase.table("grupos").select("""
                id, codigo_grupo, fecha_fin, fecha_fin_prevista, empresa_id,
                accion_formativa:acciones_formativas(nombre)
            """).in_("empresa_id", empresas_permitidas)
            
            grupos_res = query.execute()
            grupos_data = grupos_res.data or []
            
            # Filtrar grupos finalizados
            grupos_finalizados = []
            for grupo in grupos_data:
                fecha_fin = grupo.get("fecha_fin") or grupo.get("fecha_fin_prevista")
                if fecha_fin:
                    try:
                        fecha_fin_dt = pd.to_datetime(fecha_fin, errors='coerce').date()
                        if fecha_fin_dt <= hoy:
                            grupos_finalizados.append(grupo)
                    except:
                        continue
            
            if not grupos_finalizados:
                st.info("No hay grupos finalizados en las empresas que gestionas.")
                return

            # Obtener participantes de grupos finalizados
            grupos_finalizados_ids = [g["id"] for g in grupos_finalizados]
            
            participantes_res = supabase.table("participantes").select("""
                id, nombre, apellidos, email, grupo_id, nif, empresa_id
            """).in_("grupo_id", grupos_finalizados_ids).in_("empresa_id", empresas_permitidas).execute()
            
            participantes_finalizados = participantes_res.data or []
            
            if not participantes_finalizados:
                st.info("No hay participantes en grupos finalizados de tus empresas.")
                return

            # Crear diccionario de grupos para mapeo
            grupos_dict_completo = {g["id"]: g for g in grupos_finalizados}
            
            # Obtener diplomas existentes
            participantes_ids = [p["id"] for p in participantes_finalizados]
            diplomas_res = supabase.table("diplomas").select("participante_id, id").in_(
                "participante_id", participantes_ids
            ).execute()
            participantes_con_diploma = {d["participante_id"] for d in diplomas_res.data or []}
            
            # Métricas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("👥 Participantes", len(participantes_finalizados))
            with col2:
                st.metric("📚 Grupos Finalizados", len(grupos_finalizados))
            with col3:
                diplomas_count = len(participantes_con_diploma)
                st.metric("🏅 Diplomas Subidos", diplomas_count)
            with col4:
                pendientes = len(participantes_finalizados) - diplomas_count
                st.metric("⏳ Pendientes", pendientes)

            # FILTROS DE BÚSQUEDA
            st.markdown("#### 🔍 Filtros de Búsqueda")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                buscar_participante = st.text_input(
                    "🔍 Buscar participante",
                    placeholder="Nombre, email o NIF...",
                    key="buscar_diploma_participante"
                )
            
            with col2:
                grupos_opciones = ["Todos"] + [g["codigo_grupo"] for g in grupos_finalizados]
                grupo_filtro = st.selectbox(
                    "Filtrar por grupo",
                    grupos_opciones,
                    key="filtro_grupo_diplomas"
                )
            
            with col3:
                estado_diploma = st.selectbox(
                    "Estado diploma",
                    ["Todos", "Con diploma", "Sin diploma"],
                    key="filtro_estado_diploma"
                )

            # Aplicar filtros
            participantes_filtrados = participantes_finalizados.copy()
            
            # Filtro de búsqueda
            if buscar_participante:
                buscar_lower = buscar_participante.lower()
                participantes_filtrados = [
                    p for p in participantes_filtrados 
                    if (buscar_lower in p.get("nombre", "").lower() or 
                        buscar_lower in p.get("apellidos", "").lower() or 
                        buscar_lower in p.get("email", "").lower() or
                        buscar_lower in p.get("nif", "").lower())
                ]
            
            # Filtro por grupo
            if grupo_filtro != "Todos":
                grupo_id_filtro = None
                for g in grupos_finalizados:
                    if g["codigo_grupo"] == grupo_filtro:
                        grupo_id_filtro = g["id"]
                        break
                if grupo_id_filtro:
                    participantes_filtrados = [
                        p for p in participantes_filtrados 
                        if p["grupo_id"] == grupo_id_filtro
                    ]
            
            # Filtro por estado de diploma
            if estado_diploma == "Con diploma":
                participantes_filtrados = [
                    p for p in participantes_filtrados 
                    if p["id"] in participantes_con_diploma
                ]
            elif estado_diploma == "Sin diploma":
                participantes_filtrados = [
                    p for p in participantes_filtrados 
                    if p["id"] not in participantes_con_diploma
                ]

            st.markdown(f"#### 🎯 Participantes encontrados: {len(participantes_filtrados)}")

            if not participantes_filtrados:
                st.warning("🔍 No se encontraron participantes con los filtros aplicados.")
                return

            # Lista de participantes con funcionalidad de subida
            items_por_pagina = 10
            total_paginas = (len(participantes_filtrados) + items_por_pagina - 1) // items_por_pagina
            
            if total_paginas > 1:
                pagina_actual = st.selectbox(
                    "Página",
                    range(1, total_paginas + 1),
                    key="pagina_diplomas"
                )
                inicio = (pagina_actual - 1) * items_por_pagina
                fin = inicio + items_por_pagina
                participantes_pagina = participantes_filtrados[inicio:fin]
            else:
                participantes_pagina = participantes_filtrados

            # Mostrar participantes con funcionalidad completa
            for i, participante in enumerate(participantes_pagina):
                grupo_info = grupos_dict_completo.get(participante["grupo_id"], {})
                tiene_diploma = participante["id"] in participantes_con_diploma
                
                # Crear expander con información del participante
                accion_nombre = grupo_info.get("accion_formativa", {}).get("nombre", "Sin acción") if grupo_info.get("accion_formativa") else "Sin acción"
                nombre_completo = f"{participante['nombre']} {participante.get('apellidos', '')}".strip()
                
                status_emoji = "✅" if tiene_diploma else "⏳"
                status_text = "Con diploma" if tiene_diploma else "Pendiente"
                
                with st.expander(
                    f"{status_emoji} {nombre_completo} - {grupo_info.get('codigo_grupo', 'Sin código')} ({status_text})",
                    expanded=False
                ):
                    col_info, col_actions = st.columns([2, 1])
                    
                    with col_info:
                        st.markdown(f"**📧 Email:** {participante['email']}")
                        st.markdown(f"**🆔 NIF:** {participante.get('nif', 'No disponible')}")
                        st.markdown(f"**📚 Grupo:** {grupo_info.get('codigo_grupo', 'Sin código')}")
                        st.markdown(f"**📖 Acción:** {accion_nombre}")
                        
                        fecha_fin = grupo_info.get("fecha_fin") or grupo_info.get("fecha_fin_prevista")
                        if fecha_fin:
                            fecha_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')
                            st.markdown(f"**📅 Finalizado:** {fecha_str}")
                    
                    with col_actions:
                        if tiene_diploma:
                            # Mostrar diploma existente
                            diplomas_part = supabase.table("diplomas").select("*").eq(
                                "participante_id", participante["id"]
                            ).execute()
                            
                            if diplomas_part.data:
                                diploma = diplomas_part.data[0]
                                st.markdown("**🏅 Diploma:**")
                                if st.button("👁️ Ver", key=f"ver_diploma_{participante['id']}"):
                                    st.markdown(f"[🔗 Abrir diploma]({diploma['url']})")
                                
                                if st.button("🗑️ Eliminar", key=f"delete_diploma_{participante['id']}"):
                                    confirmar_key = f"confirm_delete_{participante['id']}"
                                    if st.session_state.get(confirmar_key, False):
                                        supabase.table("diplomas").delete().eq("id", diploma["id"]).execute()
                                        st.success("✅ Diploma eliminado.")
                                        st.rerun()
                                    else:
                                        st.session_state[confirmar_key] = True
                                        st.warning("⚠️ Confirmar eliminación")
                        else:
                            # Subir diploma
                            st.markdown("**📤 Subir Diploma**")
                            
                            st.info("📱 **Para móviles:** Asegúrate de que el archivo PDF esté guardado en tu dispositivo")
                            
                            diploma_file = st.file_uploader(
                                "Seleccionar diploma (PDF)",
                                type=["pdf"],
                                key=f"upload_diploma_{participante['id']}",
                                help="Solo archivos PDF, máximo 10MB"
                            )
                            
                            if diploma_file is not None:
                                file_size_mb = diploma_file.size / (1024 * 1024)
                                
                                col_info_file, col_size_file = st.columns(2)
                                with col_info_file:
                                    st.success(f"✅ **Archivo:** {diploma_file.name}")
                                with col_size_file:
                                    color = "🔴" if file_size_mb > 10 else "🟢"
                                    st.write(f"{color} **Tamaño:** {file_size_mb:.2f} MB")
                                
                                if file_size_mb > 10:
                                    st.error("❌ Archivo muy grande. Máximo 10MB.")
                                else:
                                    if st.button(
                                        f"📤 Subir diploma de {participante['nombre']}", 
                                        key=f"btn_upload_{participante['id']}", 
                                        type="primary",
                                        use_container_width=True
                                    ):
                                        subir_diploma_participante(supabase, participante, grupo_info, diploma_file)
                            else:
                                st.info("📂 Selecciona un archivo PDF para continuar")

            # Estadísticas finales
            if participantes_filtrados:
                st.markdown("#### 📊 Estadísticas")
                total_mostrados = len(participantes_filtrados)
                con_diploma_filtrados = sum(1 for p in participantes_filtrados if p["id"] in participantes_con_diploma)
                sin_diploma_filtrados = total_mostrados - con_diploma_filtrados
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("👥 Mostrados", total_mostrados)
                with col2:
                    st.metric("✅ Con diploma", con_diploma_filtrados)
                with col3:
                    st.metric("⏳ Sin diploma", sin_diploma_filtrados)
                
                if total_mostrados > 0:
                    progreso = (con_diploma_filtrados / total_mostrados) * 100
                    st.progress(con_diploma_filtrados / total_mostrados, f"Progreso: {progreso:.1f}%")
            
        except Exception as e:
            st.error(f"❌ Error al cargar gestión de diplomas: {e}")


def subir_diploma_participante(supabase, participante, grupo_info, diploma_file):
    """Función auxiliar para subir diploma de un participante."""
    try:
        with st.spinner("📤 Subiendo diploma..."):
            # Validar archivo
            try:
                file_bytes = diploma_file.getvalue()
                if len(file_bytes) == 0:
                    raise ValueError("El archivo está vacío")
            except Exception as e:
                st.error(f"❌ Error al leer el archivo: {e}")
                return
            
            # Generar estructura de carpetas organizada
            timestamp = int(datetime.now().timestamp())
            
            # Obtener información para estructura de carpetas
            participante_empresa_id = participante.get("empresa_id", "sin_empresa")
            accion_id = grupo_info.get("accion_formativa", {}).get("id", "sin_accion") if grupo_info.get("accion_formativa") else "sin_accion"
            grupo_codigo = grupo_info.get("codigo_grupo", f"grupo_{participante['grupo_id']}")
            
            # Limpiar nombres para nombres de archivo seguros
            grupo_codigo_limpio = re.sub(r'[^\w\-_]', '_', grupo_codigo)
            participante_nif = participante.get('nif', participante['id'])
            participante_nif_limpio = re.sub(r'[^\w\-_]', '_', str(participante_nif))
            
            filename = f"empresa_{participante_empresa_id}/grupos/{grupo_codigo_limpio}/accion_{accion_id}/diploma_{participante_nif_limpio}_{timestamp}.pdf"
            
            # Subir a bucket de Supabase
            try:
                upload_res = supabase.storage.from_("diplomas").upload(
                    filename, 
                    file_bytes, 
                    file_options={
                        "content-type": "application/pdf",
                        "cache-control": "3600",
                        "upsert": "true"
                    }
                )
                
                # Verificar subida exitosa
                if hasattr(upload_res, 'error') and upload_res.error:
                    raise Exception(f"Error de subida: {upload_res.error}")
                
                # Obtener URL pública
                public_url = supabase.storage.from_("diplomas").get_public_url(filename)
                if not public_url:
                    raise Exception("No se pudo generar URL pública")
                
                # Guardar en tabla diplomas
                diploma_insert = supabase.table("diplomas").insert({
                    "participante_id": participante["id"],
                    "grupo_id": participante["grupo_id"],
                    "url": public_url,
                    "archivo_nombre": diploma_file.name
                }).execute()
                
                if hasattr(diploma_insert, 'error') and diploma_insert.error:
                    # Si falla la BD, eliminar archivo subido
                    try:
                        supabase.storage.from_("diplomas").remove([filename])
                    except:
                        pass
                    raise Exception(f"Error de base de datos: {diploma_insert.error}")
                
                st.success("✅ Diploma subido correctamente!")
                st.balloons()
                st.markdown(f"🔗 [Ver diploma subido]({public_url})")
                st.rerun()
                
            except Exception as upload_error:
                st.error(f"❌ Error al subir archivo: {upload_error}")
                st.info("""
                🔧 **Soluciones:**
                - Verifica que el bucket 'diplomas' existe en Supabase
                - Asegúrate de que tienes permisos de subida
                - Intenta con un archivo más pequeño
                - Usa WiFi en lugar de datos móviles
                - Contacta al administrador si persiste el error
                """)
    
    except Exception as e:
        st.error(f"❌ Error general: {e}")


def mostrar_importacion_masiva_moderna(supabase, session_state, participantes_service, empresas_dict, grupos_dict):
    """Importación masiva moderna con jerarquía empresarial."""
    with st.expander("📂 Importación Masiva de Participantes", expanded=False):
        st.markdown("**Importar participantes respetando la jerarquía de empresas**")
        
        # Información específica según rol
        if session_state.role == "gestor":
            empresas_count = len(empresas_dict)
            st.info(f"💡 Como gestor, puedes importar participantes para {empresas_count} empresa(s) que gestionas.")
        else:
            st.info("💡 Como admin, puedes importar participantes para cualquier empresa.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Generar plantilla con empresas disponibles
            plantilla_data = {
                "nombre": ["Juan", "María"],
                "apellidos": ["García López", "Fernández Ruiz"],
                "email": ["juan.garcia@email.com", "maria.fernandez@email.com"],
                "nif": ["12345678A", "87654321B"],
                "telefono": ["600123456", "600789012"]
            }
            
            if session_state.role == "admin":
                plantilla_data["empresa"] = ["Nombre de la Empresa", "Otra Empresa"]
            
            plantilla_data["grupo"] = ["Código del Grupo (opcional)", ""]
            
            df_plantilla = pd.DataFrame(plantilla_data)
            buffer = BytesIO()
            df_plantilla.to_excel(buffer, index=False)
            buffer.seek(0)
            
            st.download_button(
                "📥 Descargar plantilla Excel",
                data=buffer.getvalue(),
                file_name="plantilla_participantes_jerarquia.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        with col2:
            archivo_subido = st.file_uploader(
                "Subir archivo Excel",
                type=['xlsx', 'xls'],
                help="El archivo debe seguir el formato de la plantilla con jerarquía"
            )
        
        if archivo_subido:
            try:
                df_import = pd.read_excel(archivo_subido)
                
                st.markdown("##### 📋 Preview de datos a importar:")
                st.dataframe(df_import.head(), use_container_width=True)
                
                # Validar columnas según rol
                columnas_requeridas = ["nombre", "apellidos", "email"]
                if session_state.role == "admin":
                    columnas_requeridas.append("empresa")
                
                columnas_faltantes = [col for col in columnas_requeridas if col not in df_import.columns]
                
                if columnas_faltantes:
                    st.error(f"❌ Columnas faltantes: {', '.join(columnas_faltantes)}")
                    return
                
                # Validar empresas si es admin
                if session_state.role == "admin" and "empresa" in df_import.columns:
                    empresas_archivo = set(df_import["empresa"].dropna().unique())
                    empresas_validas = set(empresas_dict.keys())
                    empresas_invalidas = empresas_archivo - empresas_validas
                    
                    if empresas_invalidas:
                        st.warning(f"⚠️ Empresas no encontradas: {', '.join(empresas_invalidas)}")
                        st.info("Empresas disponibles: " + ", ".join(sorted(empresas_validas)))
                
                # Mostrar estadísticas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 Total filas", len(df_import))
                with col2:
                    emails_validos = df_import["email"].str.match(r'^[^@]+@[^@]+\.[^@]+$', na=False).sum()
                    st.metric("📧 Emails válidos", emails_validos)
                with col3:
                    emails_duplicados = df_import["email"].duplicated().sum()
                    st.metric("⚠️ Duplicados" if emails_duplicados > 0 else "✅ Sin duplicados", emails_duplicados)
                
                if st.button("🚀 Procesar importación", type="primary"):
                    with st.spinner("Procesando importación con jerarquía..."):
                        # Procesar importación usando el servicio con jerarquía
                        resultados = procesar_importacion_con_jerarquia(
                            supabase, session_state, df_import, 
                            participantes_service, empresas_dict, grupos_dict
                        )
                        
                        # Mostrar resultados
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if resultados["exitosos"] > 0:
                                st.success(f"✅ Creados: {resultados['exitosos']}")
                        with col2:
                            if resultados["errores"] > 0:
                                st.error(f"❌ Errores: {resultados['errores']}")
                        with col3:
                            if resultados["omitidos"] > 0:
                                st.warning(f"⚠️ Omitidos: {resultados['omitidos']}")
                        
                        # Mostrar detalles de errores
                        if resultados["detalles_errores"]:
                            with st.expander("Ver detalles de errores"):
                                for error in resultados["detalles_errores"]:
                                    st.error(f"• {error}")
                        
                        # Mostrar contraseñas generadas si las hay
                        if resultados.get("contraseñas"):
                            with st.expander("📋 Contraseñas generadas", expanded=True):
                                st.warning("⚠️ **IMPORTANTE:** Guarda estas contraseñas y compártelas con los participantes")
                                
                                # Crear DataFrame con credenciales
                                df_credenciales = pd.DataFrame(resultados["contraseñas"])
                                st.dataframe(df_credenciales, use_container_width=True)
                                
                                # Botón para descargar credenciales
                                csv_credenciales = df_credenciales.to_csv(index=False)
                                st.download_button(
                                    "📥 Descargar credenciales CSV",
                                    data=csv_credenciales,
                                    file_name=f"credenciales_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv"
                                )
                        
                        # Limpiar cache
                        participantes_service.get_participantes_con_jerarquia.clear()
                        
            except Exception as e:
                st.error(f"❌ Error al procesar archivo: {e}")


def procesar_importacion_con_jerarquia(supabase, session_state, df_import, participantes_service, empresas_dict, grupos_dict):
    """Procesa importación masiva respetando jerarquía."""
    import random, string
    
    resultados = {
        "exitosos": 0,
        "errores": 0, 
        "omitidos": 0,
        "detalles_errores": [],
        "contraseñas": []
    }
    
    for index, row in df_import.iterrows():
        try:
            # Validaciones básicas
            if pd.isna(row.get("email")) or pd.isna(row.get("nombre")):
                resultados["omitidos"] += 1
                resultados["detalles_errores"].append(f"Fila {index + 2}: Email o nombre faltante")
                continue
            
            email = str(row["email"]).strip().lower()
            nombre = str(row["nombre"]).strip()
            apellidos = str(row.get("apellidos", "")).strip()
            
            # Determinar empresa según rol
            if session_state.role == "gestor":
                # Gestor: usar primera empresa disponible
                if empresas_dict:
                    empresa_id = list(empresas_dict.values())[0]
                else:
                    resultados["errores"] += 1
                    resultados["detalles_errores"].append(f"Fila {index + 2}: No hay empresas disponibles")
                    continue
            else:
                # Admin: buscar empresa en archivo
                empresa_nombre = str(row.get("empresa", "")).strip()
                if empresa_nombre and empresa_nombre in empresas_dict:
                    empresa_id = empresas_dict[empresa_nombre]
                else:
                    resultados["errores"] += 1
                    resultados["detalles_errores"].append(f"Fila {index + 2}: Empresa no encontrada - {empresa_nombre}")
                    continue
            
            # Determinar grupo (opcional)
            grupo_id = None
            grupo_nombre = str(row.get("grupo", "")).strip()
            if grupo_nombre and grupo_nombre in grupos_dict:
                grupo_id = grupos_dict[grupo_nombre]
            
            # Generar contraseña temporal
            password = "".join(random.choices(string.ascii_letters + string.digits, k=8)) + "!"
            
            # Preparar datos del participante
            datos_participante = {
                "email": email,
                "nombre": nombre,
                "apellidos": apellidos,
                "nif": str(row.get("nif", "")).strip() or None,
                "telefono": str(row.get("telefono", "")).strip() or None,
                "empresa_id": empresa_id,
                "grupo_id": grupo_id
            }
            
            # Crear participante usando el servicio con jerarquía
            if participantes_service.create_participante_con_jerarquia(datos_participante):
                resultados["exitosos"] += 1
                resultados["contraseñas"].append({
                    "email": email,
                    "nombre": f"{nombre} {apellidos}".strip(),
                    "contraseña": password
                })
            else:
                resultados["errores"] += 1
                resultados["detalles_errores"].append(f"Fila {index + 2}: Error al crear participante - {email}")
                
        except Exception as e:
            resultados["errores"] += 1
            resultados["detalles_errores"].append(f"Fila {index + 2}: Error general - {e}")
    
    return resultados
