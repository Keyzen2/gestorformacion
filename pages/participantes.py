import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
from utils import validar_dni_cif, export_csv, get_ajustes_app
from components.listado_con_ficha import listado_con_ficha
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
    st.caption("Gestión de participantes con soporte para jerarquía de empresas.")

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
            # Usar métodos con jerarquía
            df_participantes = participantes_service.get_participantes_con_jerarquia()
            empresas_dict = participantes_service.get_empresas_para_participantes()
            grupos_dict = grupos_service.get_grupos_dict()
            
        except Exception as e:
            st.error(f"❌ Error al cargar datos: {e}")
            return

    # =========================
    # Métricas con jerarquía
    # =========================
    if not df_participantes.empty:
        estadisticas = participantes_service.get_estadisticas_participantes_jerarquia()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("👨‍🎓 Total Participantes", estadisticas.get("total", 0))
        
        with col2:
            st.metric("👥 Con Grupo", estadisticas.get("con_grupo", 0))
        
        with col3:
            st.metric("📊 Sin Asignar", estadisticas.get("sin_grupo", 0))
        
        with col4:
            # Mostrar empresa más activa
            por_empresa = estadisticas.get("por_empresa", {})
            empresa_top = list(por_empresa.keys())[0] if por_empresa else "N/A"
            st.metric("🏢 Empresa Más Activa", empresa_top)

        # Mostrar estadísticas por tipo de empresa si hay datos
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
    # Filtros de búsqueda con jerarquía
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
    # Funciones CRUD con jerarquía
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
            
            # Convertir grupo_sel a grupo_id
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

    def get_campos_dinamicos_jerarquia(datos):
        """Define campos del formulario según rol y jerarquía."""
        campos = ["email", "nombre", "apellidos", "nif", "telefono", "fecha_nacimiento", "sexo", "tipo_documento", "niss"]
        
        # Empresa siempre necesaria
        campos.append("empresa_sel")
        
        # Grupo opcional
        campos.append("grupo_sel")
        
        return campos

    # =========================
    # Configuración para listado_con_ficha con jerarquía
    # =========================
    campos_select = {
        "sexo": ["", "M", "F"],
        "tipo_documento": ["", "NIF", "NIE", "Pasaporte"],
        "grupo_sel": [""] + sorted(grupos_dict.keys()),
        "empresa_sel": [""] + sorted(empresas_dict.keys())
    }

    campos_obligatorios = ["email", "nombre", "empresa_sel"]
    campos_readonly = ["created_at", "updated_at"]
    
    campos_help = {
        "email": "Email único del participante (obligatorio)",
        "nombre": "Nombre del participante (obligatorio)", 
        "apellidos": "Apellidos del participante",
        "nif": "NIF/DNI válido (opcional)",
        "telefono": "Teléfono de contacto",
        "fecha_nacimiento": "Fecha de nacimiento",
        "sexo": "Sexo del participante (M/F)",
        "tipo_documento": "Tipo de documento de identidad (obligatorio FUNDAE)",
        "niss": "Número de la Seguridad Social (12 dígitos, obligatorio FUNDAE)",
        "empresa_sel": "Empresa del participante (obligatorio)",
        "grupo_sel": "Grupo formativo asignado (opcional)"
    }

    # =========================
    # Tabla principal con jerarquía
    # =========================
    st.markdown("### 📊 Listado de Participantes")
    
    if df_filtered.empty:
        st.info("📋 No hay participantes que coincidan con los filtros aplicados.")
        
        # Mostrar información de contexto según rol
        if session_state.role == "gestor":
            st.info("💡 Como gestor, puedes crear participantes para tu empresa y empresas clientes.")
        
    else:
        # Preparar datos para display con jerarquía
        df_display = df_filtered.copy()
        
        # Convertir relaciones a campos de selección
        if "empresa_display" in df_display.columns:
            df_display["empresa_sel"] = df_display["empresa_display"]
        elif "empresa_nombre" in df_display.columns:
            df_display["empresa_sel"] = df_display["empresa_nombre"]
        else:
            df_display["empresa_sel"] = ""
            
        if "grupo_codigo" in df_display.columns:
            df_display["grupo_sel"] = df_display["grupo_codigo"]
        else:
            df_display["grupo_sel"] = ""

        # Columnas visibles con información jerárquica
        columnas_visibles = ["nombre", "apellidos", "email", "nif", "telefono"]
        
        if "empresa_display" in df_display.columns:
            columnas_visibles.append("empresa_display")
        elif "empresa_nombre" in df_display.columns:
            columnas_visibles.append("empresa_nombre")
            
        if "grupo_codigo" in df_display.columns:
            columnas_visibles.append("grupo_codigo")

        # Mensaje informativo según rol
        if session_state.role == "gestor":
            empresas_count = len(empresas_dict)
            st.info(f"💡 Gestionas {empresas_count} empresa(s). Puedes crear participantes en cualquiera de ellas.")
        else:
            st.info("💡 Los participantes se crean como usuarios con rol 'alumno' y credenciales de acceso.")

        # Usar listado_con_ficha con funciones de jerarquía
        listado_con_ficha(
            df=df_display,
            columnas_visibles=columnas_visibles,
            titulo="Participante",
            on_save=actualizar_participante_jerarquia,
            on_create=crear_participante_jerarquia,
            on_delete=eliminar_participante_jerarquia,
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_dinamicos=get_campos_dinamicos_jerarquia,
            campos_obligatorios=campos_obligatorios,
            allow_creation=True,
            campos_help=campos_help,
            search_columns=["nombre", "apellidos", "email", "nif"]
        )

    st.divider()

    # =========================
    # GESTIÓN DE DIPLOMAS CON JERARQUÍA
    # =========================
    if session_state.role in ["admin", "gestor"]:
        mostrar_seccion_diplomas_con_jerarquia(supabase, session_state, participantes_service)

    # =========================
    # IMPORTACIÓN MASIVA CON JERARQUÍA
    # =========================
    mostrar_importacion_masiva_con_jerarquia(supabase, session_state, participantes_service, empresas_dict, grupos_dict)

    # =========================
    # Exportación con información jerárquica
    # =========================
    if not df_filtered.empty:
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Exportar a CSV"):
                # Preparar datos para exportar con información legible
                df_export = df_filtered.copy()
                if "empresa_display" in df_export.columns:
                    df_export = df_export.drop(columns=["empresa"], errors="ignore")
                    df_export = df_export.rename(columns={"empresa_display": "empresa"})
                
                export_csv(df_export, filename="participantes_jerarquia.csv")
        
        with col2:
            st.metric("📋 Registros mostrados", len(df_filtered))

    st.divider()
    
    # Información contextual según rol
    if session_state.role == "gestor":
        st.caption("💡 Como gestor, gestionas participantes de tu empresa y empresas clientes.")
    else:
        st.caption("💡 Los participantes pueden pertenecer a diferentes tipos de empresas según la jerarquía.")


def mostrar_seccion_diplomas_con_jerarquia(supabase, session_state, participantes_service):
    """Gestión de diplomas respetando jerarquía de empresas."""
    st.markdown("### 🏅 Gestión de Diplomas")
    st.caption("Subir y gestionar diplomas respetando jerarquía de empresas.")
    
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

        # Obtener participantes de grupos finalizados con filtro jerárquico
        grupos_finalizados_ids = [g["id"] for g in grupos_finalizados]
        
        participantes_res = supabase.table("participantes").select("""
            id, nombre, apellidos, email, grupo_id, nif, empresa_id
        """).in_("grupo_id", grupos_finalizados_ids).in_("empresa_id", empresas_permitidas).execute()
        
        participantes_finalizados = participantes_res.data or []
        
        if not participantes_finalizados:
            st.info("No hay participantes en grupos finalizados de tus empresas.")
            return

        # Métricas básicas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📚 Grupos Finalizados", len(grupos_finalizados))
        with col2:
            st.metric("👥 Participantes", len(participantes_finalizados))
        with col3:
            # Obtener diplomas existentes
            participantes_ids = [p["id"] for p in participantes_finalizados]
            diplomas_res = supabase.table("diplomas").select("participante_id").in_(
                "participante_id", participantes_ids
            ).execute()
            diplomas_count = len(diplomas_res.data or [])
            st.metric("🏅 Diplomas Subidos", diplomas_count)

        st.success(f"Gestión de diplomas disponible para {len(participantes_finalizados)} participantes.")
        st.info("💡 Funcionalidad completa de diplomas disponible - implementación detallada pendiente.")
        
    except Exception as e:
        st.error(f"❌ Error al cargar gestión de diplomas: {e}")


def mostrar_importacion_masiva_con_jerarquia(supabase, session_state, participantes_service, empresas_dict, grupos_dict):
    """Importación masiva respetando jerarquía de empresas."""
    with st.expander("📂 Importación masiva de participantes"):
        st.markdown("Importar participantes respetando la jerarquía de empresas.")
        
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
                    emails_validos = df_import["email"].str.match(r'^[^@]+@[^@]+\.[^@]+, na=False).sum()
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
                        
                        # Limpiar cache
                        participantes_service.get_participantes_con_jerarquia.clear()
                        
            except Exception as e:
                st.error(f"❌ Error al procesar archivo: {e}")


def procesar_importacion_con_jerarquia(supabase, session_state, df_import, participantes_service, empresas_dict, grupos_dict):
    """Procesa importación masiva respetando jerarquía."""
    resultados = {
        "exitosos": 0,
        "errores": 0, 
        "omitidos": 0,
        "detalles_errores": []
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
            else:
                resultados["errores"] += 1
                resultados["detalles_errores"].append(f"Fila {index + 2}: Error al crear participante - {email}")
                
        except Exception as e:
            resultados["errores"] += 1
            resultados["detalles_errores"].append(f"Fila {index + 2}: Error general - {e}")
    
    return resultados
