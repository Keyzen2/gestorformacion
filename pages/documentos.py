import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import (
    export_csv, 
    subir_archivo_supabase, 
    format_date,
    safe_date_parse,
    get_ajustes_app
)
from components.listado_con_ficha import listado_con_ficha
from services.data_service import get_data_service

def main(supabase, session_state):
    st.title("📄 Gestión de Documentos")
    st.caption("Administración de documentos y archivos del sistema de formación.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicio de datos
    data_service = get_data_service(supabase, session_state)

    # =========================
    # CARGAR DATOS PRINCIPALES
    # =========================
    try:
        df_documentos = data_service.get_documentos()
    except Exception as e:
        st.error(f"❌ Error al cargar documentos: {e}")
        return

    # Cargar empresas para los selects
    try:
        if session_state.role == "admin":
            empresas_res = supabase.table("empresas").select("id,nombre").execute()
        else:
            empresa_id = session_state.user.get("empresa_id")
            empresas_res = supabase.table("empresas").select("id,nombre").eq("id", empresa_id).execute()
        
        empresas_dict = {e["nombre"]: e["id"] for e in (empresas_res.data or [])}
        empresas_opciones = [""] + sorted(empresas_dict.keys())
    except Exception as e:
        st.error(f"❌ Error al cargar empresas: {e}")
        empresas_dict = {}
        empresas_opciones = [""]

    # =========================
    # MÉTRICAS PRINCIPALES
    # =========================
    if not df_documentos.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📄 Total Documentos", len(df_documentos))
        with col2:
            # Documentos por tipo
            tipos = df_documentos["tipo"].value_counts()
            tipo_principal = tipos.index[0] if not tipos.empty else "N/A"
            st.metric("📋 Tipo Principal", tipo_principal)
        with col3:
            # Documentos recientes (últimos 30 días)
            if "created_at" in df_documentos.columns:
                try:
                    df_documentos['created_at_safe'] = df_documentos['created_at'].apply(safe_date_parse)
                    fecha_limite = datetime.now() - pd.Timedelta(days=30)
                    recientes = len(df_documentos[df_documentos['created_at_safe'] >= fecha_limite])
                    st.metric("🆕 Recientes (30 días)", recientes)
                except Exception:
                    st.metric("🆕 Recientes (30 días)", 0)
            else:
                st.metric("🆕 Recientes (30 días)", 0)
        with col4:
            # Documentos con URL
            con_url = len(df_documentos[df_documentos["url"].notna()])
            st.metric("🔗 Con Archivo", con_url)

    # =========================
    # FILTROS DE BÚSQUEDA
    # =========================
    st.divider()
    st.markdown("### 🔍 Buscar y Filtrar Documentos")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        query = st.text_input("🔍 Buscar por título o descripción")
    with col2:
        # Obtener tipos únicos de documentos
        tipos_unicos = ["Todos"] + sorted(df_documentos["tipo"].fillna("Sin tipo").unique().tolist())
        tipo_filter = st.selectbox("Filtrar por tipo", tipos_unicos)
    with col3:
        # Filtro por fecha
        fecha_filter = st.selectbox(
            "Filtrar por fecha",
            ["Todos", "Últimos 7 días", "Últimos 30 días", "Últimos 90 días"]
        )

    # Aplicar filtros
    df_filtered = df_documentos.copy()
    
    if query:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["titulo"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["descripcion"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]
    
    if tipo_filter != "Todos":
        if tipo_filter == "Sin tipo":
            df_filtered = df_filtered[df_filtered["tipo"].isna()]
        else:
            df_filtered = df_filtered[df_filtered["tipo"] == tipo_filter]
    
    if fecha_filter != "Todos" and "created_at" in df_filtered.columns:
        try:
            df_filtered['created_at_safe'] = df_filtered['created_at'].apply(safe_date_parse)
            days_map = {
                "Últimos 7 días": 7,
                "Últimos 30 días": 30,
                "Últimos 90 días": 90
            }
            days = days_map.get(fecha_filter, 30)
            fecha_limite = datetime.now() - pd.Timedelta(days=days)
            df_filtered = df_filtered[df_filtered['created_at_safe'] >= fecha_limite]
        except Exception:
            pass  # Si falla el filtro por fecha, mostrar todos

    # Botón de exportación
    if not df_filtered.empty:
        export_csv(df_filtered, filename="documentos.csv")

    st.divider()

    # =========================
    # DEFINIR CAMPOS PARA FORMULARIOS
    # =========================
    def get_campos_dinamicos(datos):
        """Define campos visibles según el contexto."""
        campos_base = [
            "id", "titulo", "descripcion", "tipo", "fecha_documento"
        ]
        
        # Solo admin puede asignar empresa
        if session_state.role == "admin":
            campos_base.append("empresa_nombre")
        
        # Campos adicionales
        campos_base.extend(["observaciones", "url"])
        
        return campos_base

    # Tipos de documento predefinidos
    tipos_documento = [
        "Certificado",
        "Diploma", 
        "Manual",
        "Evaluación",
        "Acta",
        "Informe",
        "Normativa",
        "Plantilla",
        "Comunicación",
        "Otro"
    ]

    # Campos para select
    campos_select = {
        "tipo": tipos_documento
    }
    
    if session_state.role == "admin":
        campos_select["empresa_nombre"] = empresas_opciones

    # Campos de texto área
    campos_textarea = {
        "descripcion": {"label": "Descripción del documento", "height": 100},
        "observaciones": {"label": "Observaciones adicionales", "height": 80}
    }

    # Campos de archivo
    campos_file = {
        "url": {"label": "Subir archivo", "type": ["pdf", "doc", "docx", "xlsx", "xls", "ppt", "pptx", "jpg", "png"]}
    }

    # Campos de ayuda
    campos_help = {
        "titulo": "Título descriptivo del documento (obligatorio)",
        "descripcion": "Descripción detallada del contenido",
        "tipo": "Categoría del documento",
        "fecha_documento": "Fecha del documento (no de subida)",
        "empresa_nombre": "Empresa a la que pertenece (solo para admin)",
        "observaciones": "Notas adicionales o comentarios",
        "url": "Archivo digital del documento"
    }

    # Campos obligatorios
    campos_obligatorios = ["titulo", "tipo"]

    # Columnas visibles en la tabla
    columnas_visibles = ["titulo", "tipo", "fecha_documento", "descripcion"]
    if session_state.role == "admin":
        columnas_visibles.append("empresa_nombre")

    # =========================
    # FUNCIONES CRUD
    # =========================
    def guardar_documento(documento_id, datos_editados):
        """Función para guardar cambios en un documento."""
        try:
            # Validaciones básicas
            if not datos_editados.get("titulo") or not datos_editados.get("tipo"):
                st.error("⚠️ Título y tipo son obligatorios.")
                return

            # Manejar subida de archivo
            if "url" in datos_editados and datos_editados["url"]:
                archivo = datos_editados["url"]
                if archivo:
                    archivo_url = subir_archivo_supabase(supabase, archivo.read(), archivo.name, "documentos")
                    if archivo_url:
                        datos_editados["url"] = archivo_url
                    else:
                        st.error("⚠️ Error al subir el archivo.")
                        return
                else:
                    # Mantener URL existente si no se subió nuevo archivo
                    del datos_editados["url"]

            # Convertir empresa_nombre a empresa_id si es necesario
            if "empresa_nombre" in datos_editados and datos_editados["empresa_nombre"]:
                empresa_id_new = empresas_dict.get(datos_editados["empresa_nombre"])
                datos_editados["empresa_id"] = empresa_id_new
                del datos_editados["empresa_nombre"]
            elif "empresa_nombre" in datos_editados:
                datos_editados["empresa_id"] = None
                del datos_editados["empresa_nombre"]

            # Convertir fecha si es necesario
            if "fecha_documento" in datos_editados and isinstance(datos_editados["fecha_documento"], date):
                datos_editados["fecha_documento"] = datos_editados["fecha_documento"].isoformat()

            # Actualizar documento
            supabase.table("documentos").update(datos_editados).eq("id", documento_id).execute()
            
            st.success("✅ Documento actualizado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al actualizar documento: {e}")

    def crear_documento(datos_nuevos):
        """Función para crear un nuevo documento."""
        try:
            # Validaciones básicas
            if not datos_nuevos.get("titulo") or not datos_nuevos.get("tipo"):
                st.error("⚠️ Título y tipo son obligatorios.")
                return

            # Asignar empresa según rol
            if session_state.role == "gestor":
                datos_nuevos["empresa_id"] = session_state.user.get("empresa_id")
            elif "empresa_nombre" in datos_nuevos and datos_nuevos["empresa_nombre"]:
                empresa_id_new = empresas_dict.get(datos_nuevos["empresa_nombre"])
                datos_nuevos["empresa_id"] = empresa_id_new
                del datos_nuevos["empresa_nombre"]

            # Manejar subida de archivo
            if "url" in datos_nuevos and datos_nuevos["url"]:
                archivo = datos_nuevos["url"]
                if archivo:
                    archivo_url = subir_archivo_supabase(supabase, archivo.read(), archivo.name, "documentos")
                    if archivo_url:
                        datos_nuevos["url"] = archivo_url
                    else:
                        st.error("⚠️ Error al subir el archivo.")
                        return
                else:
                    del datos_nuevos["url"]

            # Convertir fecha si es necesario
            if "fecha_documento" in datos_nuevos and isinstance(datos_nuevos["fecha_documento"], date):
                datos_nuevos["fecha_documento"] = datos_nuevos["fecha_documento"].isoformat()

            # Crear documento
            supabase.table("documentos").insert(datos_nuevos).execute()
            
            st.success("✅ Documento creado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al crear documento: {e}")

    def eliminar_documento(documento_id):
        """Función para eliminar un documento."""
        try:
            # Verificar permisos
            if session_state.role != "admin":
                st.error("⚠️ Solo los administradores pueden eliminar documentos.")
                return
            
            # Eliminar documento
            supabase.table("documentos").delete().eq("id", documento_id).execute()
            
            st.success("✅ Documento eliminado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al eliminar documento: {e}")

    # =========================
    # RENDERIZAR COMPONENTE PRINCIPAL
    # =========================
    if df_filtered.empty and query:
        st.warning(f"🔍 No se encontraron documentos que coincidan con '{query}'.")
    elif df_filtered.empty:
        st.info("ℹ️ No hay documentos registrados. Crea el primer documento usando el formulario de abajo.")
    else:
        # Formatear fechas para mostrar
        if "fecha_documento" in df_filtered.columns:
            df_filtered["fecha_documento"] = df_filtered["fecha_documento"].apply(
                lambda x: format_date(x) if pd.notna(x) else ""
            )
        
        # Usar el componente listado_con_ficha corregido
        listado_con_ficha(
            df=df_filtered,
            columnas_visibles=columnas_visibles,
            titulo="Documento",
            on_save=guardar_documento,
            on_create=crear_documento if data_service.can_modify_data() else None,
            on_delete=eliminar_documento if session_state.role == "admin" else None,
            id_col="id",
            campos_select=campos_select,
            campos_textarea=campos_textarea,
            campos_file=campos_file,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=data_service.can_modify_data(),
            campos_help=campos_help,
            campos_obligatorios=campos_obligatorios,
            search_columns=["titulo", "descripcion", "tipo"]
        )

    # =========================
    # GESTIÓN MASIVA DE DOCUMENTOS
    # =========================
    st.divider()
    st.markdown("### 📤 Gestión Masiva de Documentos")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### 📁 Subida Múltiple")
        archivos_multiples = st.file_uploader(
            "Seleccionar múltiples archivos",
            type=["pdf", "doc", "docx", "xlsx", "xls", "ppt", "pptx", "jpg", "png"],
            accept_multiple_files=True,
            help="Puedes subir varios archivos a la vez. Se crearán documentos automáticamente."
        )
        
        if archivos_multiples:
            col_config1, col_config2 = st.columns(2)
            with col_config1:
                tipo_masivo = st.selectbox("Tipo para todos los archivos", tipos_documento, key="tipo_masivo")
            with col_config2:
                if session_state.role == "admin":
                    empresa_masiva = st.selectbox("Empresa (opcional)", empresas_opciones, key="empresa_masiva")
                else:
                    empresa_masiva = None
            
            if st.button("📥 Subir Todos los Archivos"):
                subir_archivos_masivo(supabase, session_state, archivos_multiples, tipo_masivo, empresa_masiva, empresas_dict)

    with col2:
        st.markdown("#### 📊 Estadísticas por Tipo")
        if not df_documentos.empty:
            tipos_stats = df_documentos["tipo"].value_counts()
            for tipo, cantidad in tipos_stats.head(5).items():
                st.metric(f"📋 {tipo}", cantidad)

    # =========================
    # PLANTILLAS Y HERRAMIENTAS
    # =========================
    st.divider()
    st.markdown("### 🛠️ Herramientas Adicionales")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### 📋 Plantillas")
        if st.button("📄 Crear Acta de Reunión"):
            crear_plantilla_acta(supabase, session_state)
        if st.button("📋 Crear Informe de Evaluación"):
            crear_plantilla_evaluacion(supabase, session_state)
    
    with col2:
        st.markdown("#### 🔍 Búsqueda Avanzada")
        if st.button("🔎 Buscar por Contenido"):
            st.info("Funcionalidad en desarrollo - Búsqueda full-text en documentos")
        if st.button("📅 Documentos Próximos a Vencer"):
            mostrar_documentos_vencimiento(df_documentos)
    
    with col3:
        st.markdown("#### 📊 Reportes")
        if st.button("📈 Generar Reporte de Documentos"):
            generar_reporte_documentos(df_documentos)
        if st.button("🗂️ Exportar Todo a ZIP"):
            st.info("Funcionalidad en desarrollo - Exportación masiva")

    st.divider()
    st.caption("💡 Los documentos son elementos clave para la trazabilidad y gestión de la formación. Mantén organizados los archivos por tipo y empresa.")

    # =========================
    # INFORMACIÓN ADICIONAL
    # =========================
    with st.expander("ℹ️ Información sobre Gestión de Documentos"):
        st.markdown("""
        **Tipos de documentos soportados:**
        
        **📄 Documentos de texto:**
        - PDF, DOC, DOCX para manuales, certificados, informes
        
        **📊 Hojas de cálculo:**
        - XLSX, XLS para listas, evaluaciones, métricas
        
        **📽️ Presentaciones:**
        - PPT, PPTX para materiales formativos
        
        **🖼️ Imágenes:**
        - JPG, PNG para capturas, diagramas, logos
        
        **🔒 Seguridad:**
        - Los archivos se almacenan de forma segura en Supabase Storage
        - Control de acceso basado en roles de usuario
        - URLs únicas y no predecibles
        
        **💡 Consejos:**
        - Usa nombres descriptivos para los títulos
        - Especifica siempre el tipo de documento
        - Añade observaciones para facilitar la búsqueda
        - Revisa periódicamente documentos obsoletos
        """)

def subir_archivos_masivo(supabase, session_state, archivos, tipo, empresa_nombre, empresas_dict):
    """Función para subir múltiples archivos de una vez."""
    try:
        exitosos = 0
        errores = []
        
        # Determinar empresa_id
        empresa_id = None
        if session_state.role == "gestor":
            empresa_id = session_state.user.get("empresa_id")
        elif empresa_nombre and empresa_nombre in empresas_dict:
            empresa_id = empresas_dict[empresa_nombre]
        
        progress_bar = st.progress(0)
        total_archivos = len(archivos)
        
        for i, archivo in enumerate(archivos):
            try:
                # Subir archivo
                archivo_url = subir_archivo_supabase(supabase, archivo.read(), archivo.name, "documentos")
                
                if archivo_url:
                    # Crear documento
                    datos_documento = {
                        "titulo": archivo.name,
                        "tipo": tipo,
                        "url": archivo_url,
                        "descripcion": f"Documento subido masivamente: {archivo.name}",
                        "empresa_id": empresa_id
                    }
                    
                    supabase.table("documentos").insert(datos_documento).execute()
                    exitosos += 1
                else:
                    errores.append(f"Error al subir {archivo.name}")
                
                # Actualizar barra de progreso
                progress_bar.progress((i + 1) / total_archivos)
                
            except Exception as e:
                errores.append(f"Error con {archivo.name}: {str(e)}")
        
        # Mostrar resultados
        if exitosos > 0:
            st.success(f"✅ Se subieron {exitosos} archivos correctamente.")
        
        if errores:
            st.error("❌ Errores encontrados:")
            for error in errores[:5]:  # Mostrar solo los primeros 5
                st.caption(f"• {error}")
            if len(errores) > 5:
                st.caption(f"... y {len(errores) - 5} errores más")
        
        if exitosos > 0:
            st.rerun()
            
    except Exception as e:
        st.error(f"❌ Error en subida masiva: {e}")

def crear_plantilla_acta(supabase, session_state):
    """Crea una plantilla de acta de reunión."""
    try:
        plantilla_acta = """
        ACTA DE REUNIÓN
        
        Fecha: ________________
        Hora: _________________
        Lugar: ________________
        
        ASISTENTES:
        - 
        - 
        - 
        
        ORDEN DEL DÍA:
        1. 
        2. 
        3. 
        
        DESARROLLO:
        
        
        ACUERDOS:
        
        
        ACCIONES PENDIENTES:
        
        
        Firma: ________________
        """
        
        # Crear documento plantilla
        datos_plantilla = {
            "titulo": f"Plantilla Acta de Reunión - {datetime.now().strftime('%Y%m%d')}",
            "tipo": "Plantilla",
            "descripcion": plantilla_acta,
            "empresa_id": session_state.user.get("empresa_id") if session_state.role == "gestor" else None
        }
        
        supabase.table("documentos").insert(datos_plantilla).execute()
        st.success("✅ Plantilla de acta creada correctamente.")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error al crear plantilla: {e}")

def crear_plantilla_evaluacion(supabase, session_state):
    """Crea una plantilla de informe de evaluación."""
    try:
        plantilla_evaluacion = """
        INFORME DE EVALUACIÓN
        
        Participante: ________________
        Curso: _______________________
        Tutor: _______________________
        Fecha: _______________________
        
        EVALUACIÓN TEÓRICA:
        - Puntuación: ___/100
        - Observaciones:
        
        
        EVALUACIÓN PRÁCTICA:
        - Puntuación: ___/100
        - Observaciones:
        
        
        COMPETENCIAS DESARROLLADAS:
        [ ] Competencia 1
        [ ] Competencia 2
        [ ] Competencia 3
        
        RECOMENDACIONES:
        
        
        RESULTADO FINAL: APTO / NO APTO
        
        Firma Tutor: ________________
        """
        
        # Crear documento plantilla
        datos_plantilla = {
            "titulo": f"Plantilla Evaluación - {datetime.now().strftime('%Y%m%d')}",
            "tipo": "Plantilla",
            "descripcion": plantilla_evaluacion,
            "empresa_id": session_state.user.get("empresa_id") if session_state.role == "gestor" else None
        }
        
        supabase.table("documentos").insert(datos_plantilla).execute()
        st.success("✅ Plantilla de evaluación creada correctamente.")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error al crear plantilla: {e}")

def mostrar_documentos_vencimiento(df_documentos):
    """Muestra documentos próximos a vencer (ejemplo)."""
    st.info("📅 Funcionalidad en desarrollo: Análisis de documentos con fechas de vencimiento")
    
    # Aquí podrías implementar lógica para documentos con fecha de caducidad
    if not df_documentos.empty:
        st.write("Próximamente: alertas automáticas para documentos próximos a vencer")

def generar_reporte_documentos(df_documentos):
    """Genera un reporte estadístico de documentos."""
    if df_documentos.empty:
        st.warning("No hay documentos para generar reporte.")
        return
    
    st.markdown("### 📊 Reporte de Documentos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Distribución por Tipo")
        tipos_count = df_documentos["tipo"].value_counts()
        st.bar_chart(tipos_count)
    
    with col2:
        st.markdown("#### Documentos por Mes")
        if "created_at" in df_documentos.columns:
            try:
                df_documentos['created_at_safe'] = df_documentos['created_at'].apply(safe_date_parse)
                df_documentos['mes'] = df_documentos['created_at_safe'].dt.to_period('M')
                por_mes = df_documentos['mes'].value_counts().sort_index()
                st.line_chart(por_mes)
            except Exception:
                st.info("No se pueden mostrar estadísticas por fecha")
    
    # Tabla resumen
    st.markdown("#### 📋 Resumen Estadístico")
    resumen = {
        "Total documentos": len(df_documentos),
        "Tipos únicos": df_documentos["tipo"].nunique(),
        "Con archivo adjunto": len(df_documentos[df_documentos["url"].notna()]),
        "Sin archivo": len(df_documentos[df_documentos["url"].isna()])
    }
    
    for metrica, valor in resumen.items():
        st.metric(metrica, valor)
