import streamlit as st
import pandas as pd
from utils import export_csv, validar_dni_cif, get_ajustes_app
from utils import get_ajustes_app
from services.data_service import get_data_service
import uuid
from datetime import datetime

def main(supabase, session_state):
    st.subheader("👨‍🏫 Tutores")
    st.caption("Gestión de tutores internos y externos vinculados a grupos formativos.")

    if session_state.role not in {"admin", "gestor"}:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # ✅ CAMBIO PRINCIPAL: Usar DataService
    data_service = get_data_service(supabase, session_state)

    # =========================
    # Cargar datos con CACHE OPTIMIZADO
    # =========================
    with st.spinner("Cargando datos..."):
        try:
            # ✅ Usar métodos con cache del DataService
            df = data_service.get_tutores_completos()  # Ya tiene cache y filtros por empresa
            empresas_dict = data_service.get_empresas_dict()
            
            # Opciones para selects
            empresas_opciones = [""] + sorted(empresas_dict.keys()) if empresas_dict else [""]

        except Exception as e:
            st.error(f"❌ Error al cargar datos: {e}")
            return

    # =========================
    # Métricas OPTIMIZADAS
    # =========================
    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("👨‍🏫 Total Tutores", len(df))
        
        with col2:
            internos = len(df[df["tipo_tutor"] == "interno"])
            st.metric("🏢 Internos", internos)
        
        with col3:
            externos = len(df[df["tipo_tutor"] == "externo"])
            st.metric("🌐 Externos", externos)
        
        with col4:
            # Tutores con CV subido
            con_cv = len(df[df["cv_url"].notna() & (df["cv_url"] != "")])
            st.metric("📄 Con CV", con_cv)

    st.divider()

    # =========================
    # Filtros de búsqueda
    # =========================
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        query = st.text_input("🔍 Buscar por nombre, email o especialidad")
    with col2:
        tipo_filter = st.selectbox("Filtrar por tipo", ["Todos", "interno", "externo"])
    with col3:
        if session_state.role == "admin":
            empresa_filter = st.selectbox("Filtrar por empresa", ["Todas"] + sorted(empresas_dict.keys()))

    # Aplicar filtros
    df_filtered = df.copy()
    
    if query:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["apellidos"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["email"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["especialidad"].str.lower().str.contains(q_lower, na=False)
        ]
    
    if tipo_filter != "Todos":
        df_filtered = df_filtered[df_filtered["tipo_tutor"] == tipo_filter]
    
    if session_state.role == "admin" and 'empresa_filter' in locals() and empresa_filter != "Todas":
        empresa_filter_id = empresas_dict.get(empresa_filter)
        df_filtered = df_filtered[df_filtered["empresa_id"] == empresa_filter_id]

    # =========================
    # Funciones CRUD OPTIMIZADAS
    # =========================
    def guardar_tutor(datos):
        """Guarda o actualiza un tutor usando DataService."""
        try:
            # Validaciones
            if not datos.get("nombre") or not datos.get("apellidos"):
                st.error("⚠️ Nombre y apellidos son obligatorios.")
                return False
                
            if datos.get("email") and "@" not in datos.get("email", ""):
                st.error("⚠️ Email no válido.")
                return False
                
            if datos.get("nif") and not validar_dni_cif(datos["nif"]):
                st.error("⚠️ NIF/DNI no válido.")
                return False
            
            # Convertir selects a IDs
            if session_state.role == "admin" and datos.get("empresa_sel"):
                datos["empresa_id"] = empresas_dict.get(datos["empresa_sel"])
            elif session_state.role == "gestor":
                datos["empresa_id"] = session_state.user.get("empresa_id")
            
            # Limpiar campos de select temporales
            datos_limpios = {k: v for k, v in datos.items() if not k.endswith("_sel")}
            
            # ✅ Usar DataService para guardar
            if datos.get("id"):
                success = data_service.update_tutor(datos["id"], datos_limpios)
                if success:
                    st.success("✅ Tutor actualizado correctamente.")
                    st.rerun()
            else:
                success = data_service.create_tutor(datos_limpios)
                if success:
                    st.success("✅ Tutor creado correctamente.")
                    st.rerun()
            
            return success
            
        except Exception as e:
            st.error(f"❌ Error al guardar tutor: {e}")
            return False

    def crear_tutor(datos):
        """Crea un nuevo tutor."""
        # Asegurar que no tiene ID para creación
        datos.pop("id", None)
        return guardar_tutor(datos)

    # =========================
    # Configuración de campos para listado_con_ficha
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente."""
        campos_base = [
            "nombre", "apellidos", "email", "telefono", "nif", 
            "tipo_tutor", "especialidad", "direccion", "ciudad", 
            "provincia", "codigo_postal"
        ]
        
        # Solo admin puede seleccionar empresa
        if session_state.role == "admin":
            campos_base.append("empresa_sel")
            
        # CV siempre al final
        campos_base.append("cv_url")
            
        return campos_base

    campos_select = {
        "tipo_tutor": ["", "interno", "externo"]
    }
    
    if session_state.role == "admin":
        campos_select["empresa_sel"] = empresas_opciones

    campos_readonly = ["id", "created_at"]
    campos_file = ["cv_url"]
    campos_obligatorios = ["nombre", "apellidos", "tipo_tutor"]  # ✅ Marcar campos obligatorios

    campos_help = {
        "nombre": "Nombre del tutor (obligatorio)",
        "apellidos": "Apellidos del tutor (obligatorio)", 
        "email": "Email de contacto del tutor",
        "telefono": "Teléfono de contacto",
        "nif": "NIF/DNI del tutor (opcional)",
        "tipo_tutor": "Tipo: interno (empresa) o externo (obligatorio)",
        "especialidad": "Área de especialización del tutor",
        "empresa_sel": "Empresa a la que pertenece (solo admin)",
        "cv_url": "Subir CV del tutor (PDF recomendado)",
        "direccion": "Dirección completa",
        "ciudad": "Ciudad de residencia",
        "provincia": "Provincia",
        "codigo_postal": "Código postal"
    }

    # =========================
    # Mostrar interfaz principal
    # =========================
    if df_filtered.empty:
        if df.empty:
            st.info("ℹ️ No hay tutores registrados.")
        else:
            st.warning(f"🔍 No hay tutores que coincidan con los filtros aplicados.")
    else:
        # Preparar datos para mostrar
        df_display = df_filtered.copy()
        
        # Añadir campos para selects
        if session_state.role == "admin":
            df_display["empresa_sel"] = df_display["empresa_nombre"]

        # ✅ Mostrar tabla con componente optimizado
        listado_con_ficha(
            df_display,
            columnas_visibles=[
                "id", "nombre", "apellidos", "email", "telefono",
                "nif", "tipo_tutor", "especialidad", "cv_url", "empresa_nombre"
            ],
            titulo="Tutor",
            on_save=guardar_tutor,
            on_create=crear_tutor,
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_file=campos_file,
            campos_dinamicos=get_campos_dinamicos,
            campos_obligatorios=campos_obligatorios,  # ✅ Campos obligatorios
            allow_creation=True,
            campos_help=campos_help,
            search_columns=["nombre", "apellidos", "email", "especialidad"]  # ✅ Búsqueda optimizada
        )

    st.divider()

    # =========================
    # FUNCIONALIDADES ADICIONALES OPTIMIZADAS
    # =========================
    
    # Asignación de tutores a grupos
    if not df.empty:
        st.markdown("### 👥 Asignación de Tutores a Grupos")
        
        # ✅ Cargar grupos usando DataService
        try:
            df_grupos = data_service.get_grupos_completos()
            
            if not df_grupos.empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Selector de tutor
                    tutor_options = df.apply(
                        lambda t: f"{t['nombre']} {t['apellidos']} ({t['tipo_tutor']})", axis=1
                    ).tolist()
                    
                    if tutor_options:
                        tutor_sel = st.selectbox("Seleccionar tutor", tutor_options)
                        tutor_idx = tutor_options.index(tutor_sel)
                        tutor_data = df.iloc[tutor_idx]
                
                with col2:
                    # Selector de grupo
                    grupo_options = df_grupos.apply(
                        lambda g: f"{g['codigo_grupo']} - {g.get('accion_nombre', 'Sin acción')}", axis=1
                    ).tolist()
                    
                    if grupo_options:
                        grupo_sel = st.selectbox("Seleccionar grupo", grupo_options)
                        grupo_idx = grupo_options.index(grupo_sel)
                        grupo_data = df_grupos.iloc[grupo_idx]

                # Botón de asignación
                if st.button("✅ Asignar tutor al grupo"):
                    try:
                        # ✅ Usar DataService para asignaciones
                        success = data_service.assign_tutor_to_grupo(tutor_data["id"], grupo_data["id"])
                        if success:
                            st.success("✅ Tutor asignado al grupo correctamente.")
                            st.rerun()
                        else:
                            st.warning("⚠️ Este tutor ya está asignado a este grupo.")
                            
                    except Exception as e:
                        st.error(f"❌ Error al asignar tutor: {e}")
            else:
                st.info("ℹ️ No hay grupos disponibles para asignar.")

        except Exception as e:
            st.error(f"❌ Error al cargar grupos: {e}")

    # ✅ Vista de asignaciones existentes optimizada
    if not df.empty:
        st.markdown("### 📋 Asignaciones Actuales")
        
        try:
            # ✅ Usar DataService para asignaciones
            df_asignaciones = data_service.get_tutor_group_assignments()
            
            if not df_asignaciones.empty:
                for _, asig in df_asignaciones.iterrows():
                    with st.expander(f"👨‍🏫 {asig.get('tutor_nombre', '')} → 📚 {asig.get('grupo_codigo', '')}"):
                        col1, col2, col3 = st.columns([2, 2, 1])
                        
                        with col1:
                            st.write(f"**Tutor:** {asig.get('tutor_nombre', '')} {asig.get('tutor_apellidos', '')}")
                            st.write(f"**Tipo:** {asig.get('tutor_tipo', '')}")
                        
                        with col2:
                            st.write(f"**Grupo:** {asig.get('grupo_codigo', '')}")
                            st.write(f"**Acción:** {asig.get('accion_nombre', 'No especificada')}")
                        
                        with col3:
                            if st.button("🗑️ Eliminar", key=f"remove_asig_{asig['id']}"):
                                try:
                                    success = data_service.remove_tutor_from_grupo(asig["id"])
                                    if success:
                                        st.success("✅ Asignación eliminada.")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error al eliminar: {e}")
            else:
                st.info("ℹ️ No hay asignaciones de tutores a grupos.")
                
        except Exception as e:
            st.error(f"❌ Error al cargar asignaciones: {e}")

    # =========================
    # Exportación
    # =========================
    if not df_filtered.empty:
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Exportar a CSV"):
                csv_data = export_csv(df_filtered[[
                    "nombre", "apellidos", "email", "telefono", "nif", 
                    "tipo_tutor", "especialidad", "empresa_nombre"
                ]])
                st.download_button(
                    "💾 Descargar CSV",
                    data=csv_data,
                    file_name=f"tutores_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        
        with col2:
            st.metric("📋 Registros mostrados", len(df_filtered))
