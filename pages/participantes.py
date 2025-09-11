import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from services.alumnos import alta_alumno
from services.participantes_service import get_participantes_service
from services.data_service import get_data_service  # Para empresas y grupos dict
from utils import is_module_active, validar_dni_cif, export_csv, subir_archivo_supabase, get_ajustes_app
from components.listado_con_ficha import listado_con_ficha

def generar_plantilla_excel(rol):
    """Genera plantilla Excel para importación masiva de participantes."""
    columnas = ["nombre", "email"]
    if rol == "admin":
        columnas += ["grupo", "empresa"]
    columnas += ["apellidos", "dni", "telefono"]
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
    participantes_service = get_participantes_service(supabase, session_state)
    data_service = get_data_service(supabase, session_state)  # Para dict de empresas/grupos
    
    empresa_id = session_state.user.get("empresa_id")

    # =========================
    # Cargar datos con CACHE OPTIMIZADO
    # =========================
    with st.spinner("Cargando datos..."):
        try:
            # Usar servicios especializados
            df_part = participantes_service.get_participantes_completos()
            empresas_dict = data_service.get_empresas_dict()
            grupos_dict = data_service.get_grupos_dict()
            
            # Opciones para selects
            empresas_opciones = [""] + sorted(empresas_dict.keys())
            grupos_opciones = [""] + sorted(grupos_dict.keys())
            
            # Mapeo inverso para grupos (ID -> código)
            grupos_nombre_por_id = {v: k for k, v in grupos_dict.items()}

        except Exception as e:
            st.error(f"❌ Error al cargar datos: {e}")
            return

    # =========================
    # Métricas OPTIMIZADAS usando servicio
    # =========================
    if not df_part.empty:
        stats = participantes_service.get_estadisticas_participantes()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🧑‍🎓 Total Participantes", stats["total"])
        
        with col2:
            st.metric("👥 Con Grupo", stats["con_grupo"])
        
        with col3:
            st.metric("🆕 Nuevos este mes", stats["este_mes"])
        
        with col4:
            st.metric("✅ Datos Completos", stats["datos_completos"])

    st.divider()

    # =========================
    # Filtros de búsqueda
    # =========================
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        query = st.text_input("🔍 Buscar por nombre, email o DNI")
    with col2:
        grupo_filter = st.selectbox("Filtrar por grupo", ["Todos"] + sorted(grupos_dict.keys()))
    with col3:
        if session_state.role == "admin":
            empresa_filter = st.selectbox("Filtrar por empresa", ["Todas"] + sorted(empresas_dict.keys()))

    # Aplicar filtros usando servicio
    filtros = {}
    if query:
        filtros["query"] = query
    if grupo_filter != "Todos":
        filtros["grupo_id"] = grupos_dict.get(grupo_filter)
    if session_state.role == "admin" and 'empresa_filter' in locals() and empresa_filter != "Todas":
        filtros["empresa_id"] = empresas_dict.get(empresa_filter)

    # Usar búsqueda avanzada del servicio
    if filtros:
        df_filtered = participantes_service.search_participantes_avanzado(filtros)
    else:
        df_filtered = df_part.copy()

    # =========================
    # Funciones CRUD OPTIMIZADAS usando servicio
    # =========================
    def guardar_participante(datos):
        """Guarda o actualiza un participante usando participantes_service."""
        try:
            # Validaciones básicas (el servicio también las hace)
            if not datos.get("email"):
                st.error("⚠️ El email es obligatorio.")
                return False
                
            if datos.get("dni") and not validar_dni_cif(datos["dni"]):
                st.error("⚠️ DNI/CIF no válido.")
                return False
            
            # Convertir selects a IDs
            if datos.get("grupo_sel"):
                datos["grupo_id"] = grupos_dict.get(datos["grupo_sel"])
                
            if session_state.role == "admin" and datos.get("empresa_sel"):
                datos["empresa_id"] = empresas_dict.get(datos["empresa_sel"])
            elif session_state.role == "gestor":
                datos["empresa_id"] = empresa_id
            
            # Limpiar campos de select temporales
            datos_limpios = {k: v for k, v in datos.items() 
                           if not k.endswith("_sel") and k != "contraseña"}
            
            # Usar participantes_service
            if datos.get("id"):
                success = participantes_service.update_participante(datos["id"], datos_limpios)
                if success:
                    st.success("✅ Participante actualizado correctamente.")
                    st.rerun()
            else:
                # Para nuevo participante, crear usuario también
                if datos.get("contraseña"):
                    # Crear usuario con contraseña personalizada
                    result = alta_alumno(
                        supabase, 
                        datos["email"], 
                        datos["contraseña"], 
                        datos["nombre"],
                        datos["apellidos"],
                        datos.get("empresa_id")
                    )
                else:
                    # Crear usuario con contraseña automática
                    result = alta_alumno(
                        supabase, 
                        datos["email"], 
                        None,  # Contraseña automática
                        datos["nombre"],
                        datos["apellidos"],
                        datos.get("empresa_id")
                    )
                
                if result.get("success"):
                    # Crear registro de participante usando servicio
                    success = participantes_service.create_participante(datos_limpios)
                    if success:
                        st.success("✅ Participante creado correctamente.")
                        if result.get("password"):
                            st.info(f"🔑 Contraseña generada: {result['password']}")
                        st.rerun()
                else:
                    st.error(f"❌ Error al crear usuario: {result.get('error', 'Error desconocido')}")
            
            return success
            
        except Exception as e:
            st.error(f"❌ Error al guardar participante: {e}")
            return False

    def crear_participante(datos):
        """Crea un nuevo participante."""
        # Asegurar que no tiene ID para creación
        datos.pop("id", None)
        return guardar_participante(datos)

    # =========================
    # Campos dinámicos
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente."""
        campos_base = ["nombre", "apellidos", "email", "dni", "telefono", "grupo_sel"]
        
        # Solo admin puede seleccionar empresa
        if session_state.role == "admin":
            campos_base.insert(-1, "empresa_sel")
            
        # Para formulario de creación, añadir contraseña
        if not datos or not datos.get("id"):
            campos_base.append("contraseña")
            
        return campos_base

    # Configuración de campos
    campos_select = {
        "grupo_sel": grupos_opciones,
        "sexo": ["", "M", "F"]
    }
    
    if session_state.role == "admin":
        campos_select["empresa_sel"] = empresas_opciones

    campos_password = ["contraseña"]
    campos_readonly = ["created_at", "updated_at"]
    campos_obligatorios = ["nombre", "apellidos", "email"]

    campos_help = {
        "email": "Email único del participante (obligatorio)",
        "dni": "DNI, NIE o CIF válido (opcional)",
        "grupo_sel": "Grupo al que pertenece el participante",
        "empresa_sel": "Empresa del participante (solo admin)",
        "contraseña": "Contraseña para acceso (se genera automáticamente si se deja vacío)"
    }

    # =========================
    # Importación masiva
    # =========================
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
                    status_text = st.empty()
                    
                    for i, row in df_import.iterrows():
                        try:
                            progress_bar.progress((i + 1) / len(df_import))
                            status_text.text(f"Procesando {i + 1}/{len(df_import)}: {row.get('nombre', 'Sin nombre')}")
                            
                            # Preparar datos
                            datos_participante = {
                                "nombre": row.get("nombre"),
                                "apellidos": row.get("apellidos"),
                                "email": row.get("email"),
                                "dni": row.get("dni"),
                                "telefono": row.get("telefono")
                            }
                            
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
                            
                            # Crear participante usando servicio
                            if crear_participante(datos_participante):
                                creados += 1
                            else:
                                errores.append(f"Fila {i+1}: {row.get('nombre', 'Sin nombre')}")
                                
                        except Exception as e:
                            errores.append(f"Fila {i+1}: {str(e)}")
                    
                    progress_bar.empty()
                    status_text.empty()
                    
                    if creados > 0:
                        st.success(f"✅ Se crearon {creados} participantes correctamente.")
                    
                    if errores:
                        st.error(f"❌ Errores en {len(errores)} registros:")
                        for error in errores[:5]:  # Mostrar solo los primeros 5
                            st.text(f"  • {error}")
                        if len(errores) > 5:
                            st.text(f"  • ... y {len(errores)-5} errores más")
                            
            except Exception as e:
                st.error(f"❌ Error al procesar archivo: {e}")

    # =========================
    # Mostrar interfaz principal
    # =========================
    puede_crear = (
        session_state.role == "admin" or
        (session_state.role == "gestor" and empresa_id)
    )

    if df_filtered.empty:
        if df_part.empty:
            st.info("ℹ️ No hay participantes registrados.")
        else:
            st.warning(f"🔍 No se encontraron participantes que coincidan con los filtros.")
    else:
        # Preparar datos para mostrar
        df_display = df_filtered.copy()
        
        # Añadir campos para selects
        df_display["grupo_sel"] = df_display["grupo_codigo"]
        if session_state.role == "admin":
            df_display["empresa_sel"] = df_display["empresa_nombre"]

        # Mostrar tabla con componente optimizado
        listado_con_ficha(
            df_display,
            columnas_visibles=[
                "id", "nombre", "apellidos", "email", "dni", 
                "telefono", "grupo_codigo", "empresa_nombre", "created_at"
            ],
            titulo="Participante",
            on_save=guardar_participante,
            on_create=crear_participante if puede_crear else None,
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_dinamicos=get_campos_dinamicos,
            campos_password=campos_password,
            campos_obligatorios=campos_obligatorios,
            allow_creation=puede_crear,
            campos_help=campos_help
        )

    # =========================
    # Exportación
    # =========================
    if not df_filtered.empty:
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Exportar a CSV"):
                csv_data = export_csv(df_filtered[["nombre", "apellidos", "email", "dni", "telefono", "grupo_codigo", "empresa_nombre"]])
                st.download_button(
                    "💾 Descargar CSV",
                    data=csv_data,
                    file_name=f"participantes_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        
        with col2:
            st.metric("📋 Registros mostrados", len(df_filtered))
