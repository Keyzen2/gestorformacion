import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
from utils import validar_dni_cif, export_csv, get_ajustes_app
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha
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

    # Inicializar servicio de datos
    data_service = get_data_service(supabase, session_state)
    empresa_id = session_state.user.get("empresa_id")

    # =========================
    # Cargar datos
    # =========================
    with st.spinner("Cargando datos..."):
        try:
            # Usar el método corregido del DataService
            df_participantes = data_service.get_participantes_completos()
            
            # Obtener diccionarios de empresas y grupos
            empresas_dict = data_service.get_empresas_dict()
            grupos_dict = data_service.get_grupos_dict()
            
            # Opciones para selects
            empresas_opciones = [""] + sorted(empresas_dict.keys())
            grupos_opciones = [""] + sorted(grupos_dict.keys())
            
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
            # Nuevos este mes
            este_mes = len(df_participantes[
                pd.to_datetime(df_participantes["created_at"], errors="coerce").dt.month == datetime.now().month
            ])
            st.metric("🆕 Nuevos este mes", este_mes)
        
        with col4:
            # Con datos completos
            completos = len(df_participantes[
                (df_participantes["email"].notna()) & 
                (df_participantes["nombre"].notna()) & 
                (df_participantes["apellidos"].notna())
            ])
            st.metric("✅ Datos Completos", completos)

    st.divider()

    # =========================
    # Filtros de búsqueda - CORREGIDO: usar 'nif' en lugar de 'dni'
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

    # Aplicar filtros - CORREGIDO: usar 'nif'
    df_filtered = df_participantes.copy()
    
    if query and not df_filtered.empty:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["apellidos"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["email"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["nif"].fillna("").str.lower().str.contains(q_lower, na=False)  # ✅ nif
        ]
    
    if grupo_filter != "Todos" and not df_filtered.empty:
        grupo_id = grupos_dict.get(grupo_filter)
        df_filtered = df_filtered[df_filtered["grupo_id"] == grupo_id]
    
    if session_state.role == "admin" and 'empresa_filter' in locals() and empresa_filter != "Todas" and not df_filtered.empty:
        empresa_id_filter = empresas_dict.get(empresa_filter)
        df_filtered = df_filtered[df_filtered["empresa_id"] == empresa_id_filter]

    # =========================
    # Funciones CRUD CORREGIDAS CON LIMPIEZA DE CACHE
    # =========================
    def guardar_participante(participante_id, datos_editados):
        """Guarda cambios en un participante - CORREGIDO CON CACHE."""
        try:
            # Validaciones básicas
            if not datos_editados.get("email"):
                st.error("⚠️ El email es obligatorio.")
                return
                
            if datos_editados.get("nif") and not validar_dni_cif(datos_editados["nif"]):
                st.error("⚠️ NIF no válido.")
                return
            
            # Convertir selects a IDs
            if "grupo_sel" in datos_editados:
                grupo_sel = datos_editados.pop("grupo_sel")
                if grupo_sel and grupo_sel in grupos_dict:
                    datos_editados["grupo_id"] = grupos_dict[grupo_sel]
                else:
                    datos_editados["grupo_id"] = None
                    
            # Solo para admin: convertir empresa_sel
            if "empresa_sel" in datos_editados:
                empresa_sel = datos_editados.pop("empresa_sel")
                if session_state.role == "admin" and empresa_sel and empresa_sel in empresas_dict:
                    datos_editados["empresa_id"] = empresas_dict[empresa_sel]
            
            # Para gestores, asegurar que mantienen su empresa
            if session_state.role == "gestor":
                datos_editados["empresa_id"] = empresa_id
            
            # CORRECCIÓN JSON: Convertir fecha a string ISO si es date object
            if "fecha_nacimiento" in datos_editados:
                fecha = datos_editados["fecha_nacimiento"]
                if hasattr(fecha, 'isoformat'):
                    datos_editados["fecha_nacimiento"] = fecha.isoformat()
                elif fecha:
                    datos_editados["fecha_nacimiento"] = str(fecha)
            
            # CORRECCIÓN JSON: Limpiar valores None y vacíos problemáticos
            datos_limpios = {}
            for key, value in datos_editados.items():
                if value is not None and value != "":
                    # Convertir datetime objects a string
                    if hasattr(value, 'isoformat'):
                        datos_limpios[key] = value.isoformat()
                    else:
                        datos_limpios[key] = value
            
            # Actualizar timestamp
            datos_limpios["updated_at"] = datetime.utcnow().isoformat()
            
            # Actualizar en base de datos
            supabase.table("participantes").update(datos_limpios).eq("id", participante_id).execute()
            
            # ✅ AÑADIDO: Limpiar cache para forzar recarga
            data_service.get_participantes_completos.clear()
            
            st.success("✅ Participante actualizado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al guardar participante: {e}")

    def crear_participante(datos_nuevos):
        """Crea un nuevo participante - CORREGIDO CON CACHE.""" 
        try:
            # Validaciones
            if not datos_nuevos.get("email") or not datos_nuevos.get("nombre") or not datos_nuevos.get("apellidos"):
                st.error("⚠️ Nombre, apellidos y email son obligatorios.")
                return
                
            if datos_nuevos.get("nif") and not validar_dni_cif(datos_nuevos["nif"]):
                st.error("⚠️ NIF no válido.")
                return

            # Verificar email único
            email_existe = supabase.table("participantes").select("id").eq("email", datos_nuevos["email"]).execute()
            if email_existe.data:
                st.error("⚠️ Ya existe un participante con ese email.")
                return

            # Convertir selects a IDs
            if "grupo_sel" in datos_nuevos:
                grupo_sel = datos_nuevos.pop("grupo_sel")
                if grupo_sel and grupo_sel in grupos_dict:
                    datos_nuevos["grupo_id"] = grupos_dict[grupo_sel]
                    
            # Solo para admin: convertir empresa_sel
            if "empresa_sel" in datos_nuevos:
                empresa_sel = datos_nuevos.pop("empresa_sel")
                if session_state.role == "admin" and empresa_sel and empresa_sel in empresas_dict:
                    datos_nuevos["empresa_id"] = empresas_dict[empresa_sel]
            
            # Para gestores, siempre asignar su empresa
            if session_state.role == "gestor":
                datos_nuevos["empresa_id"] = empresa_id

            # CORRECCIÓN JSON: Procesar fecha de nacimiento
            if "fecha_nacimiento" in datos_nuevos:
                fecha = datos_nuevos["fecha_nacimiento"]
                if hasattr(fecha, 'isoformat'):
                    datos_nuevos["fecha_nacimiento"] = fecha.isoformat()
                elif fecha:
                    datos_nuevos["fecha_nacimiento"] = str(fecha)

            # CORRECCIÓN JSON: Limpiar campos temporales y procesar valores
            datos_limpios = {}
            for key, value in datos_nuevos.items():
                # Saltar campos temporales
                if key.endswith("_sel") or key == "contraseña":
                    continue
                # Solo incluir valores no vacíos
                if value is not None and value != "":
                    # Convertir datetime objects a string
                    if hasattr(value, 'isoformat'):
                        datos_limpios[key] = value.isoformat()
                    else:
                        datos_limpios[key] = value
            
            # Añadir timestamps
            datos_limpios["created_at"] = datetime.utcnow().isoformat()
            datos_limpios["updated_at"] = datetime.utcnow().isoformat()

            # Crear participante
            result = supabase.table("participantes").insert(datos_limpios).execute()
            
            if result.data:
                # ✅ AÑADIDO: Limpiar cache para forzar recarga
                data_service.get_participantes_completos.clear()
                
                st.success("✅ Participante creado correctamente.")
                st.rerun()
            else:
                st.error("❌ Error al crear el participante.")
                
        except Exception as e:
            st.error(f"❌ Error al crear participante: {e}")

    def eliminar_participante(participante_id):
        """Elimina un participante - CON LIMPIEZA DE CACHE.""" 
        try:
            # Eliminar participante
            supabase.table("participantes").delete().eq("id", participante_id).execute()
            
            # ✅ AÑADIDO: Limpiar cache para forzar recarga
            data_service.get_participantes_completos.clear()
            
            st.success("✅ Participante eliminado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al eliminar participante: {e}")

    # =========================
    # Configuración de campos para formulario
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente - ORDEN CORRECTO."""
        # Validar que datos es un diccionario
        if not isinstance(datos, dict):
            datos = {}
            
        # ORDEN SECUENCIAL CORRECTO: Nombre → Apellidos → Email → etc.
        campos_base = [
            "nombre", 
            "apellidos",
            "email", 
            "nif", 
            "telefono",
            "fecha_nacimiento",
            "sexo",
            "grupo_sel"
        ]
    
        # SOLUCIÓN SIMPLE: Solo admin ve empresa
        if session_state.role == "admin":
            campos_base.append("empresa_sel")
            
        return campos_base

    # Configuración de selects
    campos_select = {
        "grupo_sel": grupos_opciones,
        "sexo": ["", "M", "F"]
    }

    # Solo admin puede seleccionar empresa
    if session_state.role == "admin":
        campos_select["empresa_sel"] = empresas_opciones

    # Campos textarea (vacío pero debe ser diccionario)
    campos_textarea = {}
    
    # Campos file (vacío pero debe ser diccionario)
    campos_file = {}

    # Campos readonly - SIN problemas de empresa
    campos_readonly = ["id", "created_at", "updated_at"]

    # Campos password (debe ser lista)
    campos_password = []

    # Campos de ayuda CORREGIDOS
    campos_help = {
        "nombre": "Nombre del participante (obligatorio)",
        "apellidos": "Apellidos del participante (obligatorio)",
        "email": "Email único del participante (obligatorio)",
        "nif": "NIF/DNI del participante (opcional)",
        "telefono": "Número de teléfono de contacto",
        "fecha_nacimiento": "Fecha de nacimiento (mayores de 18 años)",  # ✅ Actualizado
        "sexo": "Sexo del participante (M/F)",
        "grupo_sel": "Grupo al que pertenece el participante"
    }

    # Solo añadir help de empresa para admin
    if session_state.role == "admin":
        campos_help["empresa_sel"] = "Empresa del participante"

    # Campos obligatorios
    campos_obligatorios = ["nombre", "apellidos", "email"]

    # Campos reactivos
    reactive_fields = {
        "grupo_sel": []
    }

    # =========================
    # Mostrar interfaz principal
    # =========================
    puede_crear = (
        session_state.role == "admin" or
        (session_state.role == "gestor" and empresa_id)
    )

    # Preparar df_display CORREGIDO
    if not df_filtered.empty:
        df_display = df_filtered.copy()
        
        # Convertir valores problemáticos
        for col in df_display.columns:
            if df_display[col].dtype == 'object':
                df_display[col] = df_display[col].fillna("")
        
        # Campos de selección
        if "grupo_codigo" in df_display.columns:
            df_display["grupo_sel"] = df_display["grupo_codigo"].fillna("")
        else:
            df_display["grupo_sel"] = ""
            
        # Solo admin necesita empresa_sel
        if session_state.role == "admin":
            if "empresa_nombre" in df_display.columns:
                df_display["empresa_sel"] = df_display["empresa_nombre"].fillna("")
            else:
                df_display["empresa_sel"] = ""
    else:
        df_display = pd.DataFrame(columns=[
            "id", "nombre", "apellidos", "email", "nif", "telefono", "grupo_codigo",
            "empresa_nombre"
        ])

    # Columnas visibles según rol
    columnas_base = ["nombre", "apellidos", "email", "nif", "telefono"]
    
    # Añadir columnas adicionales si existen en el dataframe
    if not df_display.empty:
        if "grupo_codigo" in df_display.columns:
            columnas_base.append("grupo_codigo")
        if session_state.role == "admin" and "empresa_nombre" in df_display.columns:
            columnas_base.append("empresa_nombre")
    
    columnas_visibles = [col for col in columnas_base if col in df_display.columns]

    # Llamada con parámetros validados y manejo de errores
    try:
        listado_con_ficha(
            df=df_display,
            columnas_visibles=columnas_visibles,
            titulo="Participante",
            on_save=guardar_participante,
            on_create=crear_participante if puede_crear else None,
            on_delete=eliminar_participante if session_state.role == "admin" else None,
            id_col="id",
            campos_select=campos_select,
            campos_textarea=campos_textarea,
            campos_file=campos_file,
            campos_readonly=campos_readonly,
            campos_dinamicos=get_campos_dinamicos,
            campos_password=campos_password,
            allow_creation=puede_crear,
            campos_help=campos_help,
            campos_obligatorios=campos_obligatorios,
            reactive_fields=reactive_fields,
            search_columns=["nombre", "apellidos", "email", "nif"]  # ✅ nif en search
        )
    except Exception as e:
        st.error(f"❌ Error al mostrar listado: {e}")

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
    # AÑADIR AL FINAL DEL ARCHIVO participantes.py, DESPUÉS DE LA SECCIÓN DE IMPORTACIÓN MASIVA

    # =========================
    # GESTIÓN DE DIPLOMAS
    # =========================
    if session_state.role in ["admin", "gestor"]:
        st.divider()
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
                        if fecha_fin_dt < hoy:
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

    st.divider()
    st.caption("💡 Los participantes son usuarios que pertenecen a grupos formativos y pueden obtener diplomas al completar los cursos.")
    
    # =========================
    # Importación masiva - CORREGIDA PARA NIF
    # =========================
    if puede_crear:
        st.divider()
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
                try:
                    df_import = pd.read_excel(archivo_subido)
                    
                    if df_import.empty:
                        st.warning("⚠️ El archivo está vacío.")
                    else:
                        creados = 0
                        errores = []
                        
                        progress_bar = st.progress(0)
                        
                        for i, row in df_import.iterrows():
                            try:
                                progress_bar.progress((i + 1) / len(df_import))
                                
                                # Preparar datos con conversión de fecha
                                datos_participante = {
                                    "nombre": row.get("nombre"),
                                    "apellidos": row.get("apellidos"),
                                    "email": row.get("email"),
                                    "nif": row.get("nif"),  # ✅ nif
                                    "telefono": row.get("telefono"),
                                    "created_at": datetime.utcnow().isoformat(),
                                    "updated_at": datetime.utcnow().isoformat()
                                }
                                
                                # Procesar fecha de nacimiento si existe
                                if row.get("fecha_nacimiento"):
                                    try:
                                        if isinstance(row["fecha_nacimiento"], str):
                                            fecha_obj = pd.to_datetime(row["fecha_nacimiento"]).date()
                                        else:
                                            fecha_obj = row["fecha_nacimiento"]
                                        datos_participante["fecha_nacimiento"] = fecha_obj.isoformat() if hasattr(fecha_obj, 'isoformat') else str(fecha_obj)
                                    except:
                                        pass
                                
                                # Asignar empresa y grupo
                                if session_state.role == "admin":
                                    if row.get("empresa"):
                                        datos_participante["empresa_id"] = empresas_dict.get(row["empresa"])
                                    if row.get("grupo"):
                                        datos_participante["grupo_id"] = grupos_dict.get(row["grupo"])
                                else:
                                    datos_participante["empresa_id"] = empresa_id
                                    if row.get("grupo"):
                                        datos_participante["grupo_id"] = grupos_dict.get(row["grupo"])
                                
                                # Validar datos básicos
                                if not datos_participante.get("nombre") or not datos_participante.get("email"):
                                    errores.append(f"Fila {i+1}: Faltan nombre o email")
                                    continue
                                
                                # Crear participante
                                result = supabase.table("participantes").insert(datos_participante).execute()
                                if result.data:
                                    creados += 1
                                else:
                                    errores.append(f"Fila {i+1}: Error al crear")
                                    
                            except Exception as e:
                                errores.append(f"Fila {i+1}: {str(e)}")
                        
                        progress_bar.empty()
                        
                        if creados > 0:
                            # ✅ AÑADIDO: Limpiar cache después de importación masiva
                            data_service.get_participantes_completos.clear()
                            
                            st.success(f"✅ Se crearon {creados} participantes correctamente.")
                            st.rerun()
                        
                        if errores:
                            st.error(f"❌ Errores en {len(errores)} registros:")
                            for error in errores[:5]:
                                st.text(f"  • {error}")
                            if len(errores) > 5:
                                st.text(f"  • ... y {len(errores)-5} errores más")
                                
                except Exception as e:
                    st.error(f"❌ Error al procesar archivo: {e}")

    st.divider()
    st.caption("Los participantes son los alumnos que realizan la formacion en los grupos.")
