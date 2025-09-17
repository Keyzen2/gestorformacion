import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
from utils import validar_dni_cif, export_csv, get_ajustes_app
from services.data_service import get_data_service
from services.grupos_service import get_grupos_service

def generar_plantilla_excel(rol):
    """Genera plantilla Excel para importación masiva de participantes."""
    columnas = ["nombre", "apellidos", "email", "nif", "telefono"]
    if rol == "admin":
        columnas += ["grupo", "empresa"]
    
    df = pd.DataFrame(columns=columnas)
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer

def main(supabase, session_state):
    st.markdown("## 🧑‍🎓 Participantes")
    st.caption("Gestión de participantes y vinculación con empresas y grupos.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return
        
    # Inicializar servicios
    data_service = get_data_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)
    empresa_id = session_state.user.get("empresa_id")

    # =========================
    # Cargar datos
    # =========================
    with st.spinner("Cargando datos..."):
        try:
            df_participantes = data_service.get_participantes_completos()
            empresas_dict = data_service.get_empresas_dict()
            grupos_dict = grupos_service.get_grupos_dict()
            
        except Exception as e:
            st.error(f"❌ Error al cargar datos: {e}")
            return

    # =========================
    # Métricas básicas
    # =========================
    if not df_participantes.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🧑‍🎓 Total Participantes", len(df_participantes))
        
        with col2:
            con_grupo = len(df_participantes[df_participantes["grupo_id"].notna()])
            st.metric("👥 Con Grupo", con_grupo)
        
        with col3:
            este_mes = len(df_participantes[
                pd.to_datetime(df_participantes["created_at"], errors="coerce").dt.month == datetime.now().month
            ])
            st.metric("🆕 Nuevos este mes", este_mes)
        
        with col4:
            completos = len(df_participantes[
                (df_participantes["email"].notna()) & 
                (df_participantes["nombre"].notna()) & 
                (df_participantes["apellidos"].notna())
            ])
            st.metric("✅ Datos Completos", completos)

    st.divider()

    # =========================
    # FORMULARIO DE EDICIÓN/CREACIÓN
    # =========================
    if "participante_seleccionado" in st.session_state:
        participante_id = st.session_state.participante_seleccionado
        mostrar_formulario_participante(
            supabase, session_state, data_service, grupos_service,
            participante_id, empresas_dict, grupos_dict, empresa_id
        )
        
    # =========================
    # Filtros de búsqueda
    # =========================
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        query = st.text_input("🔍 Buscar por nombre, email o NIF")
    with col2:
        grupo_filter = st.selectbox("Filtrar por grupo", ["Todos"] + sorted(grupos_dict.keys()))
    with col3:
        if session_state.role == "admin":
            empresa_filter = st.selectbox("Filtrar por empresa", ["Todas"] + sorted(empresas_dict.keys()))

    # Aplicar filtros
    df_filtered = df_participantes.copy()
    
    if query and not df_filtered.empty:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["apellidos"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["email"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["nif"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]
    
    if grupo_filter != "Todos" and not df_filtered.empty:
        grupo_id = grupos_dict.get(grupo_filter)
        df_filtered = df_filtered[df_filtered["grupo_id"] == grupo_id]
    
    if session_state.role == "admin" and 'empresa_filter' in locals() and empresa_filter != "Todas" and not df_filtered.empty:
        empresa_id_filter = empresas_dict.get(empresa_filter)
        df_filtered = df_filtered[df_filtered["empresa_id"] == empresa_id_filter]
        
    # =========================
    # Botón crear participante
    # =========================
    puede_crear = (
        session_state.role == "admin" or
        (session_state.role == "gestor" and empresa_id)
    )
    
    if puede_crear:
        if st.button("➕ Crear Nuevo Participante", type="primary"):
            st.session_state.participante_seleccionado = "nuevo"
            st.rerun()

    # =========================
    # TABLA EDITABLE ESTILO GRUPOS
    # =========================
    st.markdown("### 📊 Listado de Participantes")
    
    if df_filtered.empty:
        st.info("📋 No hay participantes registrados o que coincidan con los filtros.")
    else:
        # Preparar datos para mostrar
        df_display = df_filtered.copy()
        
        # Columnas visibles según rol
        columnas_base = ["nif", "nombre", "apellidos", "email", "telefono"]
        
        if not df_display.empty:
            if "grupo_codigo" in df_display.columns:
                columnas_base.append("grupo_codigo")
            if session_state.role == "admin" and "empresa_nombre" in df_display.columns:
                columnas_base.append("empresa_nombre")
        
        columnas_visibles = [col for col in columnas_base if col in df_display.columns]

        # Tabla con selección
        event = st.dataframe(
            df_display[columnas_visibles],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Procesar selección
        if event.selection.rows:
            selected_idx = event.selection.rows[0]
            participante_seleccionado = df_filtered.iloc[selected_idx]
            st.session_state.participante_seleccionado = participante_seleccionado["id"]
            st.rerun())

    st.divider()

    # =========================
    # GESTIÓN DE DIPLOMAS (mantener sección existente)
    # =========================
    if session_state.role in ["admin", "gestor"]:
        st.divider()
        mostrar_seccion_diplomas(supabase, session_state, empresa_id)

    # =========================
    # IMPORTACIÓN MASIVA (mantener sección existente)
    # =========================
    if puede_crear:
        st.divider()
        mostrar_importacion_masiva(supabase, session_state, data_service, empresas_dict, grupos_dict, empresa_id)

    # =========================
    # Exportación
    # =========================
    if not df_filtered.empty:
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Exportar a CSV"):
                export_csv(df_filtered[columnas_visibles], filename="participantes.csv")
        
        with col2:
            st.metric("📋 Registros mostrados", len(df_filtered))

    st.divider()
    st.caption("💡 Los participantes son usuarios que pertenecen a grupos formativos y pueden obtener diplomas al completar los cursos.")


def mostrar_formulario_participante(supabase, session_state, data_service, grupos_service, 
                                   participante_id, empresas_dict, grupos_dict, empresa_id):
    """Formulario unificado para crear/editar participantes estilo grupos.py"""

    es_creacion = participante_id == "nuevo"

    if es_creacion:
        st.markdown("### ➕ Crear Nuevo Participante")
        participante_data = {}
    else:
        st.markdown("### ✏️ Editar Participante")
        try:
            result = supabase.table("participantes").select("*").eq("id", participante_id).limit(1).execute()
            participante_data = result.data[0] if result.data else {}
            if not participante_data:
                st.error("Participante no encontrado")
                if "participante_seleccionado" in st.session_state:
                    del st.session_state.participante_seleccionado
                return
        except Exception as e:
            st.error(f"Error al cargar participante: {e}")
            if "participante_seleccionado" in st.session_state:
                del st.session_state.participante_seleccionado
            return

    # =========================
    # SECCIÓN 1: DATOS BÁSICOS
    # =========================
    with st.expander("📋 1. Datos Básicos", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            nombre = st.text_input(
                "Nombre *",
                value=participante_data.get("nombre", ""),
                key="part_nombre"
            )
            
            apellidos = st.text_input(
                "Apellidos *",
                value=participante_data.get("apellidos", ""),
                key="part_apellidos"
            )
            
            email = st.text_input(
                "Email *",
                value=participante_data.get("email", ""),
                key="part_email"
            )
        
        with col2:
            nif = st.text_input(
                "NIF/DNI",
                value=participante_data.get("nif", ""),
                help="NIF/DNI del participante (opcional)",
                key="part_nif"
            )
            
            telefono = st.text_input(
                "Teléfono",
                value=participante_data.get("telefono", ""),
                key="part_telefono"
            )
            
            # Fecha de nacimiento
            fecha_nac_actual = participante_data.get("fecha_nacimiento")
            if fecha_nac_actual:
                try:
                    if isinstance(fecha_nac_actual, str):
                        fecha_nac_value = datetime.fromisoformat(fecha_nac_actual.replace('Z', '+00:00')).date()
                    else:
                        fecha_nac_value = fecha_nac_actual
                except:
                    fecha_nac_value = None
            else:
                fecha_nac_value = None
                
            fecha_nacimiento = st.date_input(
                "Fecha de Nacimiento",
                value=fecha_nac_value,
                key="part_fecha_nac"
            )
            
            sexo = st.selectbox(
                "Sexo",
                ["", "M", "F"],
                index=["", "M", "F"].index(participante_data.get("sexo", "")) if participante_data.get("sexo") in ["", "M", "F"] else 0,
                key="part_sexo"
            )

    # =========================
    # SECCIÓN 2: EMPRESA Y GRUPO (LÓGICA MEJORADA)
    # =========================
    with st.expander("🏢 2. Empresa y Grupo", expanded=True):
        
        if session_state.role == "gestor":
            # GESTOR: Solo su empresa y sus grupos
            try:
                empresa_nombre = None
                for nombre, id_emp in empresas_dict.items():
                    if id_emp == empresa_id:
                        empresa_nombre = nombre
                        break
                
                if empresa_nombre:
                    st.text_input("Empresa", empresa_nombre, disabled=True)
                    empresa_seleccionada_id = empresa_id
                else:
                    st.error("No se encontró información de tu empresa")
                    return
                
                # Grupos solo de su empresa
                grupos_empresa = grupos_service.get_grupos_dict_por_empresa(empresa_id)
                
                if grupos_empresa:
                    grupo_actual = participante_data.get("grupo_id")
                    grupo_nombre_actual = None
                    for nombre, id_grupo in grupos_empresa.items():
                        if id_grupo == grupo_actual:
                            grupo_nombre_actual = nombre
                            break
                    
                    grupo_opciones = [""] + list(grupos_empresa.keys())
                    grupo_index = 0
                    if grupo_nombre_actual and grupo_nombre_actual in grupo_opciones:
                        grupo_index = grupo_opciones.index(grupo_nombre_actual)
                    
                    grupo_seleccionado = st.selectbox(
                        "Grupo",
                        grupo_opciones,
                        index=grupo_index,
                        key="part_grupo"
                    )
                    
                    grupo_seleccionado_id = grupos_empresa.get(grupo_seleccionado) if grupo_seleccionado else None
                else:
                    st.info("No hay grupos disponibles para tu empresa")
                    grupo_seleccionado_id = None
                    
            except Exception as e:
                st.error(f"Error al cargar datos del gestor: {e}")
                return
        
        else:
            # ADMIN: Puede elegir cualquier empresa, grupos se filtran por empresa
            col1, col2 = st.columns(2)
            
            with col1:
                # Selector de empresa
                empresa_actual = participante_data.get("empresa_id")
                empresa_nombre_actual = None
                for nombre, id_emp in empresas_dict.items():
                    if id_emp == empresa_actual:
                        empresa_nombre_actual = nombre
                        break
                
                empresa_opciones = list(empresas_dict.keys())
                empresa_index = 0
                if empresa_nombre_actual and empresa_nombre_actual in empresa_opciones:
                    empresa_index = empresa_opciones.index(empresa_nombre_actual)
                
                empresa_seleccionada = st.selectbox(
                    "Empresa *",
                    empresa_opciones,
                    index=empresa_index,
                    key="part_empresa"
                )
                
                empresa_seleccionada_id = empresas_dict[empresa_seleccionada]
            
            with col2:
                # Grupos filtrados por empresa seleccionada
                try:
                    grupos_empresa = grupos_service.get_grupos_dict_por_empresa(empresa_seleccionada_id)
                    
                    if grupos_empresa:
                        grupo_actual = participante_data.get("grupo_id")
                        grupo_nombre_actual = None
                        for nombre, id_grupo in grupos_empresa.items():
                            if id_grupo == grupo_actual:
                                grupo_nombre_actual = nombre
                                break
                        
                        grupo_opciones = [""] + list(grupos_empresa.keys())
                        grupo_index = 0
                        if grupo_nombre_actual and grupo_nombre_actual in grupo_opciones:
                            grupo_index = grupo_opciones.index(grupo_nombre_actual)
                        
                        grupo_seleccionado = st.selectbox(
                            "Grupo",
                            grupo_opciones,
                            index=grupo_index,
                            key="part_grupo"
                        )
                        
                        grupo_seleccionado_id = grupos_empresa.get(grupo_seleccionado) if grupo_seleccionado else None
                    else:
                        st.info(f"No hay grupos disponibles para {empresa_seleccionada}")
                        grupo_seleccionado_id = None
                        
                except Exception as e:
                    st.error(f"Error al cargar grupos: {e}")
                    grupo_seleccionado_id = None

    # =========================
    # BOTONES DE ACCIÓN
    # =========================
    st.divider()
    
    if es_creacion:
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("➕ Crear Participante", type="primary", use_container_width=True):
                crear_participante(
                    supabase, session_state, data_service,
                    nombre, apellidos, email, nif, telefono, fecha_nacimiento, sexo,
                    empresa_seleccionada_id, grupo_seleccionado_id
                )
        
        with col2:
            if st.button("❌ Cancelar", use_container_width=True):
                del st.session_state.participante_editando
                st.rerun()
    
    else:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("💾 Guardar Cambios", type="primary", use_container_width=True):
                actualizar_participante(
                    supabase, session_state, data_service, participante_id,
                    nombre, apellidos, email, nif, telefono, fecha_nacimiento, sexo,
                    empresa_seleccionada_id, grupo_seleccionado_id
                )
        
        with col2:
            if st.button("🔄 Recargar", use_container_width=True):
                st.rerun()
        
        with col3:
            if st.button("❌ Cancelar", use_container_width=True):
                del st.session_state.participante_editando
                st.rerun()


def crear_participante(supabase, session_state, data_service, nombre, apellidos, email, nif, 
                      telefono, fecha_nacimiento, sexo, empresa_id, grupo_id):
    """Crea un nuevo participante con validaciones."""
    try:
        # Validaciones básicas
        if not nombre or not apellidos or not email:
            st.error("⚠️ Nombre, apellidos y email son obligatorios.")
            return
            
        if nif and not validar_dni_cif(nif):
            st.error("⚠️ NIF no válido.")
            return

        # Verificar email único
        email_existe = supabase.table("participantes").select("id").eq("email", email).execute()
        if email_existe.data:
            st.error("⚠️ Ya existe un participante con ese email.")
            return

        # Preparar datos
        datos_participante = {
            "nombre": nombre,
            "apellidos": apellidos,
            "email": email,
            "empresa_id": empresa_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # Campos opcionales
        if nif:
            datos_participante["nif"] = nif
        if telefono:
            datos_participante["telefono"] = telefono
        if fecha_nacimiento:
            datos_participante["fecha_nacimiento"] = fecha_nacimiento.isoformat()
        if sexo:
            datos_participante["sexo"] = sexo
        if grupo_id:
            datos_participante["grupo_id"] = grupo_id

        # Crear participante
        result = supabase.table("participantes").insert(datos_participante).execute()
        
        if result.data:
            # Limpiar cache
            data_service.get_participantes_completos.clear()
            
            st.success("✅ Participante creado correctamente.")
            del st.session_state.participante_editando
            st.rerun()
        else:
            st.error("❌ Error al crear el participante.")
            
    except Exception as e:
        st.error(f"❌ Error al crear participante: {e}")


def actualizar_participante(supabase, session_state, data_service, participante_id, nombre, apellidos, 
                           email, nif, telefono, fecha_nacimiento, sexo, empresa_id, grupo_id):
    """Actualiza un participante existente."""
    try:
        # Validaciones básicas
        if not nombre or not apellidos or not email:
            st.error("⚠️ Nombre, apellidos y email son obligatorios.")
            return
            
        if nif and not validar_dni_cif(nif):
            st.error("⚠️ NIF no válido.")
            return

        # Preparar datos de actualización
        datos_actualizacion = {
            "nombre": nombre,
            "apellidos": apellidos,
            "email": email,
            "empresa_id": empresa_id,
            "updated_at": datetime.utcnow().isoformat()
        }

        # Campos opcionales
        if nif:
            datos_actualizacion["nif"] = nif
        else:
            datos_actualizacion["nif"] = None
            
        if telefono:
            datos_actualizacion["telefono"] = telefono
        else:
            datos_actualizacion["telefono"] = None
            
        if fecha_nacimiento:
            datos_actualizacion["fecha_nacimiento"] = fecha_nacimiento.isoformat()
        else:
            datos_actualizacion["fecha_nacimiento"] = None
            
        if sexo:
            datos_actualizacion["sexo"] = sexo
        else:
            datos_actualizacion["sexo"] = None
            
        if grupo_id:
            datos_actualizacion["grupo_id"] = grupo_id
        else:
            datos_actualizacion["grupo_id"] = None

        # Actualizar participante
        supabase.table("participantes").update(datos_actualizacion).eq("id", participante_id).execute()
        
        # Limpiar cache
        data_service.get_participantes_completos.clear()
        
        st.success("✅ Participante actualizado correctamente.")
        del st.session_state.participante_editando
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error al actualizar participante: {e}")


def mostrar_seccion_diplomas(supabase, session_state, empresa_id):
    """Sección de gestión de diplomas - FUNCIONAL COMPLETA."""
    st.markdown("### 🏅 Gestión de Diplomas")
    st.caption("Subir y gestionar diplomas para participantes de grupos finalizados.")
    
    try:
        # Obtener grupos finalizados
        hoy = datetime.now().date()
        
        # Consulta para obtener grupos con sus participantes
        query_grupos = supabase.table("grupos").select("""
            id, codigo_grupo, fecha_fin, fecha_fin_prevista, empresa_id,
            accion_formativa:acciones_formativas(nombre)
        """)
        
        if session_state.role == "gestor" and empresa_id:
            query_grupos = query_grupos.eq("empresa_id", empresa_id)
        
        grupos_res = query_grupos.execute()
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
            st.info("ℹ️ No hay grupos finalizados disponibles para gestionar diplomas.")
        else:
            # Obtener participantes de grupos finalizados
            grupos_finalizados_ids = [g["id"] for g in grupos_finalizados]
            
            query_participantes = supabase.table("participantes").select("""
                id, nombre, apellidos, email, grupo_id
            """).in_("grupo_id", grupos_finalizados_ids)
            
            if session_state.role == "gestor" and empresa_id:
                query_participantes = query_participantes.eq("empresa_id", empresa_id)
            
            participantes_res = query_participantes.execute()
            participantes_finalizados = participantes_res.data or []
            
            if not participantes_finalizados:
                st.info("ℹ️ No hay participantes en grupos finalizados.")
            else:
                # Crear diccionario de grupos para mapeo
                grupos_dict_completo = {g["id"]: g for g in grupos_finalizados}
                
                # Mostrar métricas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("👥 Participantes", len(participantes_finalizados))
                with col2:
                    st.metric("📚 Grupos Finalizados", len(grupos_finalizados))
                with col3:
                    # Calcular diplomas existentes
                    diplomas_res = supabase.table("diplomas").select("participante_id").in_(
                        "participante_id", [p["id"] for p in participantes_finalizados]
                    ).execute()
                    diplomas_count = len(diplomas_res.data or [])
                    st.metric("🏅 Diplomas Subidos", diplomas_count)
                
                st.markdown("#### 🎯 Seleccionar Participante")
                
                # Crear opciones mejoradas para el selector
                opciones_participantes = []
                for p in participantes_finalizados:
                    grupo_info = grupos_dict_completo.get(p["grupo_id"], {})
                    grupo_codigo = grupo_info.get("codigo_grupo", "Sin código")
                    accion_nombre = grupo_info.get("accion_formativa", {}).get("nombre", "Sin acción") if grupo_info.get("accion_formativa") else "Sin acción"
                    
                    nombre_completo = f"{p['nombre']} {p.get('apellidos', '')}".strip()
                    opcion = f"{nombre_completo} - {grupo_codigo} ({accion_nombre})"
                    opciones_participantes.append((opcion, p))
                
                if opciones_participantes:
                    participante_seleccionado = st.selectbox(
                        "Seleccionar participante para gestionar diploma:",
                        options=[None] + [op[0] for op in opciones_participantes],
                        format_func=lambda x: "Seleccionar..." if x is None else x,
                        key="diploma_participante_selector"
                    )
                    
                    if participante_seleccionado:
                        # Encontrar datos del participante seleccionado
                        participante_data = None
                        for opcion, data in opciones_participantes:
                            if opcion == participante_seleccionado:
                                participante_data = data
                                break
                        
                        if participante_data:
                            grupo_info = grupos_dict_completo.get(participante_data["grupo_id"], {})
                            
                            with st.container():
                                st.markdown("#### 📋 Información del Participante")
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.markdown(f"**👤 Nombre:** {participante_data['nombre']} {participante_data.get('apellidos', '')}")
                                    st.markdown(f"**📧 Email:** {participante_data['email']}")
                                
                                with col2:
                                    st.markdown(f"**📚 Grupo:** {grupo_info.get('codigo_grupo', 'Sin código')}")
                                    fecha_fin = grupo_info.get("fecha_fin") or grupo_info.get("fecha_fin_prevista")
                                    if fecha_fin:
                                        fecha_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')
                                        st.markdown(f"**📅 Finalizado:** {fecha_str}")
                                
                                # Gestión de diplomas existentes
                                st.markdown("#### 🏅 Diplomas Registrados")
                                
                                try:
                                    diplomas_existentes = supabase.table("diplomas").select("*").eq(
                                        "participante_id", participante_data["id"]
                                    ).execute()
                                    diplomas = diplomas_existentes.data or []
                                    
                                    if diplomas:
                                        for i, diploma in enumerate(diplomas):
                                            with st.expander(f"📄 Diploma {i+1} - {diploma.get('archivo_nombre', 'Sin nombre')}"):
                                                col_info, col_actions = st.columns([3, 1])
                                                
                                                with col_info:
                                                    fecha_subida = diploma.get('fecha_subida')
                                                    if fecha_subida:
                                                        fecha_str = pd.to_datetime(fecha_subida).strftime('%d/%m/%Y %H:%M')
                                                        st.markdown(f"**📅 Subido:** {fecha_str}")
                                                    st.markdown(f"**🔗 URL:** [Ver diploma]({diploma['url']})")
                                                
                                                with col_actions:
                                                    if st.button("🗑️ Eliminar", key=f"delete_diploma_{diploma['id']}"):
                                                        confirm_key = f"confirm_delete_diploma_{diploma['id']}"
                                                        if st.session_state.get(confirm_key, False):
                                                            supabase.table("diplomas").delete().eq("id", diploma["id"]).execute()
                                                            st.success("✅ Diploma eliminado.")
                                                            st.rerun()
                                                        else:
                                                            st.session_state[confirm_key] = True
                                                            st.warning("⚠️ Haz clic de nuevo para confirmar")
                                    else:
                                        st.info("ℹ️ Este participante no tiene diplomas registrados.")
                                
                                except Exception as e:
                                    st.error(f"❌ Error al cargar diplomas: {e}")
                                
                                # Subir nuevo diploma
                                st.markdown("#### 📤 Subir Nuevo Diploma")
                                
                                if diplomas:
                                    st.warning("⚠️ **Atención:** Ya existe un diploma para este participante. El nuevo archivo lo reemplazará.")
                                
                                diploma_file = st.file_uploader(
                                    "📄 Seleccionar archivo de diploma (PDF)",
                                    type=["pdf"],
                                    key=f"diploma_uploader_{participante_data['id']}",
                                    help="Solo se permiten archivos PDF. Máximo 10MB."
                                )
                                
                                if diploma_file:
                                    # Validar tamaño
                                    file_size_mb = diploma_file.size / (1024 * 1024)
                                    st.info(f"📁 **Archivo:** {diploma_file.name} ({file_size_mb:.2f} MB)")
                                    
                                    if file_size_mb > 10:
                                        st.error("❌ El archivo es demasiado grande. Máximo 10MB.")
                                    else:
                                        col_upload, col_cancel = st.columns([2, 1])
                                        
                                        with col_upload:
                                            if st.button("📤 Subir Diploma", type="primary", key=f"upload_btn_{participante_data['id']}"):
                                                try:
                                                    with st.spinner("📤 Subiendo diploma..."):
                                                        # Usar función de utils.py
                                                        from utils import subir_archivo_supabase
                                                        
                                                        url = subir_archivo_supabase(
                                                            supabase,
                                                            diploma_file,
                                                            empresa_id=session_state.user.get("empresa_id"),
                                                            bucket="diplomas"
                                                        )
                                                        
                                                        if url:
                                                            # Eliminar diplomas existentes si los hay
                                                            if diplomas:
                                                                for d in diplomas:
                                                                    supabase.table("diplomas").delete().eq("id", d["id"]).execute()
                                                            
                                                            # Insertar nuevo diploma (usando estructura exacta de tu tabla)
                                                            supabase.table("diplomas").insert({
                                                                "participante_id": participante_data["id"],
                                                                "grupo_id": participante_data["grupo_id"],
                                                                "url": url,
                                                                "archivo_nombre": diploma_file.name
                                                                # fecha_subida se añade automáticamente con DEFAULT NOW()
                                                            }).execute()
                                                            
                                                            st.success("✅ Diploma subido correctamente.")
                                                            st.balloons()
                                                            st.rerun()
                                                        else:
                                                            st.error("❌ Error al obtener la URL del diploma.")
                                                
                                                except ImportError:
                                                    st.error("❌ Error: No se pudo importar la función de subida de archivos.")
                                                except Exception as e:
                                                    st.error(f"❌ Error al subir diploma: {e}")
                                        
                                        with col_cancel:
                                            if st.button("❌ Cancelar", key=f"cancel_btn_{participante_data['id']}"):
                                                st.rerun()
    
    except Exception as e:
        st.error(f"❌ Error al cargar datos para gestión de diplomas: {e}")

    # =========================
    # ESTADÍSTICAS DE DIPLOMAS
    # =========================
    with st.expander("📊 Estadísticas de Diplomas"):
        try:
            # Obtener estadísticas generales
            if session_state.role == "admin":
                # Estadísticas globales para admin
                total_grupos_query = supabase.table("grupos").select("id, fecha_fin, fecha_fin_prevista")
                total_diplomas_query = supabase.table("diplomas").select("id")
            else:
                # Estadísticas por empresa para gestor
                total_grupos_query = supabase.table("grupos").select("id, fecha_fin, fecha_fin_prevista").eq("empresa_id", empresa_id)
                # Para diplomas, necesitamos un join o filtrar por participantes de la empresa
                participantes_empresa = supabase.table("participantes").select("id").eq("empresa_id", empresa_id).execute()
                participantes_ids = [p["id"] for p in participantes_empresa.data or []]
                
                if participantes_ids:
                    total_diplomas_query = supabase.table("diplomas").select("id").in_("participante_id", participantes_ids)
                else:
                    total_diplomas_query = None
            
            total_grupos_res = total_grupos_query.execute()
            if total_diplomas_query:
                total_diplomas_res = total_diplomas_query.execute()
                total_diplomas = len(total_diplomas_res.data or [])
            else:
                total_diplomas = 0
            
            # Calcular grupos finalizados
            total_finalizados = 0
            hoy = datetime.now().date()
            for grupo in total_grupos_res.data or []:
                fecha_fin = grupo.get("fecha_fin") or grupo.get("fecha_fin_prevista")
                if fecha_fin:
                    try:
                        if pd.to_datetime(fecha_fin, errors='coerce').date() < hoy:
                            total_finalizados += 1
                    except:
                        continue
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("📚 Grupos Finalizados", total_finalizados)
            
            with col2:
                st.metric("🏅 Total Diplomas", total_diplomas)
            
            with col3:
                pendientes = max(0, total_finalizados - total_diplomas)
                st.metric("⏳ Pendientes", pendientes)
            
            with col4:
                if total_finalizados > 0:
                    progreso = (total_diplomas / total_finalizados) * 100
                    st.metric("📈 Progreso", f"{progreso:.1f}%")
                else:
                    st.metric("📈 Progreso", "0%")
            
            # Barra de progreso
            if total_finalizados > 0:
                progreso_decimal = total_diplomas / total_finalizados
                st.progress(progreso_decimal, text=f"Diplomas completados: {progreso_decimal:.1%}")
            
        except Exception as e:
            st.error(f"❌ Error al cargar estadísticas: {e}")


def mostrar_importacion_masiva(supabase, session_state, data_service, empresas_dict, grupos_dict, empresa_id):
    """Sección de importación masiva (mantener código existente mejorado)."""
    with st.expander("📂 Importación masiva de participantes"):
        st.markdown("Sube un archivo Excel con participantes para crear múltiples registros de una vez.")
        
        col1, col2 = st.columns(2)
        with col1:
            plantilla = generar_plantilla_excel(session_state.role)
            st.download_button(
                "📥 Descargar plantilla Excel",
                data=plantilla.getvalue(),
                file_name="plantilla_participantes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        with col2:
            archivo_subido = st.file_uploader(
                "Subir archivo Excel",
                type=['xlsx', 'xls'],
                help="El archivo debe seguir el formato de la plantilla"
            )
        
        if archivo_subido and st.button("🚀 Procesar importación"):
            # TODO: Mantener la lógica de importación masiva del archivo original
            st.info("Procesamiento de importación masiva - mantener lógica existente")
