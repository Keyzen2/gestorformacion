import streamlit as st
import pandas as pd
from datetime import datetime
from utils import validar_dni_cif, export_csv, subir_archivo_supabase
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.title("👨‍🏫 Gestión de Tutores")
    st.caption("Administración de tutores de empresa y especialistas.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # Inicializar servicio de datos
    data_service = get_data_service(supabase, session_state)

    # =========================
    # CARGAR DATOS PRINCIPALES
    # =========================
    try:
        # ✅ CORRECCIÓN: Usar la función correcta sin parámetros extra
        df_tutores = data_service.get_tutores()
    except Exception as e:
        st.error(f"❌ Error al cargar tutores: {e}")
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
    if not df_tutores.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👨‍🏫 Total Tutores", len(df_tutores))
        with col2:
            tutores_empresa = len(df_tutores[df_tutores["tipo_tutor"] == "empresa"])
            st.metric("🏢 Tutores Empresa", tutores_empresa)
        with col3:
            tutores_especialista = len(df_tutores[df_tutores["tipo_tutor"] == "especialista"])
            st.metric("🎯 Especialistas", tutores_especialista)
        with col4:
            con_cv = len(df_tutores[df_tutores["cv_url"].notna()])
            st.metric("📄 Con CV", con_cv)

    # =========================
    # FILTROS DE BÚSQUEDA
    # =========================
    st.divider()
    st.markdown("### 🔍 Buscar y Filtrar Tutores")
    
    col1, col2 = st.columns(2)
    with col1:
        query = st.text_input("🔍 Buscar por nombre, email o especialidad")
    with col2:
        tipo_filter = st.selectbox(
            "Filtrar por tipo",
            ["Todos", "Tutor de empresa", "Tutor especialista"]
        )

    # Aplicar filtros
    df_filtered = df_tutores.copy()
    
    if query:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["apellidos"].fillna("").str.lower().str.contains(q_lower, na=False) |
            df_filtered["email"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["especialidad"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]
    
    if tipo_filter != "Todos":
        tipo_mapping = {
            "Tutor de empresa": "empresa",
            "Tutor especialista": "especialista"
        }
        tipo_valor = tipo_mapping.get(tipo_filter)
        if tipo_valor:
            df_filtered = df_filtered[df_filtered["tipo_tutor"] == tipo_valor]

    # Botón de exportación
    if not df_filtered.empty:
        export_csv(df_filtered, filename="tutores.csv")

    st.divider()

    # =========================
    # DEFINIR CAMPOS PARA FORMULARIOS
    # =========================
    def get_campos_dinamicos(datos):
        """Define campos visibles según el contexto."""
        campos_base = [
            "id", "nombre", "apellidos", "email", "telefono", "nif", 
            "tipo_tutor", "especialidad", "direccion", "ciudad", 
            "provincia", "codigo_postal"
        ]
        
        # Solo admin puede asignar empresa
        if session_state.role == "admin":
            campos_base.append("empresa_nombre")
        
        # Campo CV al final
        campos_base.append("cv_url")
        
        return campos_base

    # Campos para select
    campos_select = {
        "tipo_tutor": ["empresa", "especialista"]
    }
    
    if session_state.role == "admin":
        campos_select["empresa_nombre"] = empresas_opciones

    # Campos de texto área
    campos_textarea = {
        "especialidad": {"label": "Especialidad y experiencia", "height": 100},
        "direccion": {"label": "Dirección completa", "height": 80}
    }

    # Campos de archivo
    campos_file = {
        "cv_url": {"label": "Subir CV (PDF)", "type": ["pdf"]}
    }

    # Campos de ayuda
    campos_help = {
        "nombre": "Nombre del tutor (obligatorio)",
        "apellidos": "Apellidos del tutor (obligatorio)",
        "email": "Email de contacto del tutor (obligatorio)",
        "telefono": "Teléfono de contacto",
        "nif": "NIF/NIE del tutor",
        "tipo_tutor": "Tipo de tutor: empresa (interno) o especialista (externo)",
        "especialidad": "Área de especialización y experiencia profesional",
        "empresa_nombre": "Empresa a la que pertenece (solo para admin)",
        "cv_url": "Curriculum vitae en formato PDF",
        "direccion": "Dirección completa del tutor",
        "ciudad": "Ciudad de residencia",
        "provincia": "Provincia",
        "codigo_postal": "Código postal"
    }

    # Campos obligatorios
    campos_obligatorios = ["nombre", "apellidos", "email", "tipo_tutor"]

    # Columnas visibles en la tabla
    columnas_visibles = ["nombre", "apellidos", "email", "tipo_tutor", "especialidad"]
    if session_state.role == "admin":
        columnas_visibles.append("empresa_nombre")

    # =========================
    # FUNCIONES CRUD
    # =========================
    def guardar_tutor(tutor_id, datos_editados):
        """Función para guardar cambios en un tutor."""
        try:
            # Validaciones básicas
            if not datos_editados.get("nombre") or not datos_editados.get("apellidos") or not datos_editados.get("email"):
                st.error("⚠️ Nombre, apellidos y email son obligatorios.")
                return
                
            if datos_editados.get("nif") and not validar_dni_cif(datos_editados["nif"]):
                st.error("⚠️ El NIF/NIE no es válido.")
                return

            # Verificar email único
            existing_email = supabase.table("tutores").select("id").eq("email", datos_editados["email"]).neq("id", tutor_id).execute()
            if existing_email.data:
                st.error("⚠️ Ya existe otro tutor con ese email.")
                return

            # Manejar subida de CV
            if "cv_url" in datos_editados and datos_editados["cv_url"]:
                cv_file = datos_editados["cv_url"]
                if cv_file:
                    cv_url = subir_archivo_supabase(supabase, cv_file.read(), cv_file.name, "documentos")
                    if cv_url:
                        datos_editados["cv_url"] = cv_url
                    else:
                        st.error("⚠️ Error al subir el CV.")
                        return
                else:
                    # Mantener URL existente si no se subió nuevo archivo
                    del datos_editados["cv_url"]

            # Convertir empresa_nombre a empresa_id si es necesario
            if "empresa_nombre" in datos_editados and datos_editados["empresa_nombre"]:
                empresa_id_new = empresas_dict.get(datos_editados["empresa_nombre"])
                datos_editados["empresa_id"] = empresa_id_new
                del datos_editados["empresa_nombre"]
            elif "empresa_nombre" in datos_editados:
                datos_editados["empresa_id"] = None
                del datos_editados["empresa_nombre"]

            # Actualizar tutor
            supabase.table("tutores").update(datos_editados).eq("id", tutor_id).execute()
            
            st.success("✅ Tutor actualizado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al actualizar tutor: {e}")

    def crear_tutor(datos_nuevos):
        """Función para crear un nuevo tutor."""
        try:
            # Validaciones básicas
            if not datos_nuevos.get("nombre") or not datos_nuevos.get("apellidos") or not datos_nuevos.get("email"):
                st.error("⚠️ Nombre, apellidos y email son obligatorios.")
                return
                
            if datos_nuevos.get("nif") and not validar_dni_cif(datos_nuevos["nif"]):
                st.error("⚠️ El NIF/NIE no es válido.")
                return

            # Verificar email único
            existing_email = supabase.table("tutores").select("id").eq("email", datos_nuevos["email"]).execute()
            if existing_email.data:
                st.error("⚠️ Ya existe un tutor con ese email.")
                return

            # Asignar empresa según rol
            if session_state.role == "gestor":
                datos_nuevos["empresa_id"] = session_state.user.get("empresa_id")
            elif "empresa_nombre" in datos_nuevos and datos_nuevos["empresa_nombre"]:
                empresa_id_new = empresas_dict.get(datos_nuevos["empresa_nombre"])
                datos_nuevos["empresa_id"] = empresa_id_new
                del datos_nuevos["empresa_nombre"]

            # Manejar subida de CV
            if "cv_url" in datos_nuevos and datos_nuevos["cv_url"]:
                cv_file = datos_nuevos["cv_url"]
                if cv_file:
                    cv_url = subir_archivo_supabase(supabase, cv_file.read(), cv_file.name, "documentos")
                    if cv_url:
                        datos_nuevos["cv_url"] = cv_url
                    else:
                        st.error("⚠️ Error al subir el CV.")
                        return
                else:
                    del datos_nuevos["cv_url"]

            # Crear tutor
            supabase.table("tutores").insert(datos_nuevos).execute()
            
            st.success("✅ Tutor creado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al crear tutor: {e}")

    def eliminar_tutor(tutor_id):
        """Función para eliminar un tutor."""
        try:
            # Verificar dependencias (grupos asignados, etc.)
            # Aquí puedes añadir verificaciones según tu modelo de datos
            
            # Eliminar tutor
            supabase.table("tutores").delete().eq("id", tutor_id).execute()
            
            st.success("✅ Tutor eliminado correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al eliminar tutor: {e}")

    # =========================
    # RENDERIZAR COMPONENTE PRINCIPAL
    # =========================
    if df_filtered.empty and query:
        st.warning(f"🔍 No se encontraron tutores que coincidan con '{query}'.")
    elif df_filtered.empty:
        st.info("ℹ️ No hay tutores registrados. Crea el primer tutor usando el formulario de abajo.")
    else:
        # Usar el componente listado_con_ficha corregido
        listado_con_ficha(
            df=df_filtered,
            columnas_visibles=columnas_visibles,
            titulo="Tutor",
            on_save=guardar_tutor,
            on_create=crear_tutor if data_service.can_modify_data() else None,
            on_delete=eliminar_tutor if session_state.role == "admin" else None,
            id_col="id",
            campos_select=campos_select,
            campos_textarea=campos_textarea,
            campos_file=campos_file,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=data_service.can_modify_data(),
            campos_help=campos_help,
            campos_obligatorios=campos_obligatorios,
            search_columns=["nombre", "apellidos", "email", "especialidad"]
        )

    st.divider()
    st.caption("💡 Los tutores son profesionales responsables del seguimiento y evaluación de los participantes en las acciones formativas.")

    # =========================
    # INFORMACIÓN ADICIONAL
    # =========================
    with st.expander("ℹ️ Información sobre Tipos de Tutores"):
        st.markdown("""
        **Tipos de tutores disponibles:**
        
        **🏢 Tutor de empresa:**
        - Personal interno de la empresa cliente
        - Responsable del seguimiento en el puesto de trabajo
        - Conoce el contexto específico de la empresa
        
        **🎯 Tutor especialista:**
        - Profesional externo especializado en la materia
        - Aporta conocimiento técnico específico
        - Puede trabajar con múltiples empresas
        
        **📄 Gestión de CV:**
        - Los CV se almacenan de forma segura en Supabase Storage
        - Formatos aceptados: PDF
        - Acceso controlado según permisos de usuario
        """)

    # Estadísticas adicionales para admin
    if session_state.role == "admin" and not df_tutores.empty:
        st.markdown("### 📊 Estadísticas Detalladas")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Tutores por empresa
            if "empresa_nombre" in df_tutores.columns:
                tutores_por_empresa = df_tutores["empresa_nombre"].value_counts()
                if not tutores_por_empresa.empty:
                    st.metric("🏆 Empresa con más tutores", tutores_por_empresa.index[0])
        
        with col2:
            # Especialidades más comunes
            especialidades = df_tutores["especialidad"].fillna("Sin especificar").value_counts()
            if not especialidades.empty:
                st.metric("📚 Especialidad más común", especialidades.index[0])
        
        with col3:
            # Porcentaje con CV
            con_cv = len(df_tutores[df_tutores["cv_url"].notna()])
            porcentaje_cv = (con_cv / len(df_tutores) * 100) if len(df_tutores) > 0 else 0
            st.metric("📄 % con CV subido", f"{porcentaje_cv:.1f}%")
