import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils import validar_dni_cif, export_csv
from services.data_service import get_data_service
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.title("🏢 Gestión de Empresas")
    st.caption("Administración de empresas y configuración de módulos activos.")

    # Verificar permisos
    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        return

    # Inicializar servicio de datos
    data_service = get_data_service(supabase, session_state)

    # =========================
    # Cargar datos con DataService
    # =========================
    with st.spinner("Cargando datos de empresas..."):
        df_empresas = data_service.get_empresas_con_modulos()
        if df_empresas.empty:
            st.info("ℹ️ No hay empresas registradas.")
            st.stop()

    # =========================
    # Métricas mejoradas
    # =========================
    try:
        # Calcular métricas básicas
        total_empresas = len(df_empresas)
        empresas_este_mes = len(df_empresas[
            pd.to_datetime(df_empresas['created_at'], errors='coerce').dt.date >= 
            datetime.now().replace(day=1).date()
        ]) if 'created_at' in df_empresas.columns else 0
        
        provincia_top = df_empresas['provincia'].mode().iloc[0] if 'provincia' in df_empresas.columns and not df_empresas['provincia'].isna().all() else "N/D"
        
        # Contar módulos activos
        modulos_cols = [col for col in df_empresas.columns if col.endswith('_activo')]
        modulos_activos = df_empresas[modulos_cols].sum().sum() if modulos_cols else 0

        # Mostrar métricas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🏢 Total Empresas", total_empresas)
        
        with col2:
            st.metric("🆕 Nuevas este mes", empresas_este_mes)
        
        with col3:
            st.metric("🌍 Provincia principal", provincia_top)
        
        with col4:
            st.metric("📊 Módulos activos", modulos_activos)

    except Exception as e:
        st.error(f"⚠️ Error al calcular métricas: {e}")

    st.divider()

    # =========================
    # Filtros de búsqueda
    # =========================
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2 = st.columns(2)
    
    with col1:
        query = st.text_input("🔍 Buscar por nombre, CIF, email, provincia o ciudad")
    
    with col2:
        modulo_filter = st.selectbox(
            "Filtrar por módulo activo", 
            ["Todos", "Formación", "ISO 9001", "RGPD", "CRM", "Doc. Avanzada"]
        )

    # Aplicar filtros
    df_filtered = df_empresas.copy()
    
    # Filtro de búsqueda
    if query:
        q = query.lower()
        mask = (
            df_filtered['nombre'].fillna("").str.lower().str.contains(q, na=False) |
            df_filtered['cif'].fillna("").str.lower().str.contains(q, na=False) |
            df_filtered['email'].fillna("").str.lower().str.contains(q, na=False) |
            df_filtered['provincia'].fillna("").str.lower().str.contains(q, na=False) |
            df_filtered['ciudad'].fillna("").str.lower().str.contains(q, na=False)
        )
        df_filtered = df_filtered[mask]

    # Filtro de módulos
    if modulo_filter != "Todos":
        modulo_map = {
            "Formación": "formacion_activo",
            "ISO 9001": "iso_activo", 
            "RGPD": "rgpd_activo",
            "CRM": "crm_activo",
            "Doc. Avanzada": "docu_avanzada_activo"
        }
        col_filtro = modulo_map.get(modulo_filter)
        if col_filtro and col_filtro in df_filtered.columns:
            df_filtered = df_filtered[df_filtered[col_filtro] == True]

    # Mensaje si no hay resultados
    if df_filtered.empty and query:
        st.warning(f"🔍 No se encontraron empresas que coincidan con '{query}'.")
        return

    # Exportar CSV
    if not df_filtered.empty:
        export_csv(df_filtered, filename="empresas.csv")
    
    st.divider()

    # =========================
    # Funciones CRUD optimizadas
    # =========================
    def guardar_empresa(empresa_id, datos_editados):
        """Función para guardar cambios en una empresa."""
        try:
            # Validaciones básicas
            if not datos_editados.get("nombre"):
                st.error("⚠️ El nombre de la empresa es obligatorio.")
                return
                
            if datos_editados.get("cif") and not validar_dni_cif(datos_editados["cif"]):
                st.error("⚠️ El CIF no tiene un formato válido.")
                return

            # Actualizar en base de datos
            update_data = {k: v for k, v in datos_editados.items() if v is not None}
            if update_data:
                supabase.table("empresas").update(update_data).eq("id", empresa_id).execute()
                
                # Limpiar cache
                if hasattr(data_service.get_empresas_con_modulos, 'clear'):
                    data_service.get_empresas_con_modulos.clear()
                
                st.success("✅ Empresa actualizada correctamente.")
                st.rerun()
            else:
                st.warning("⚠️ No se detectaron cambios para guardar.")
                
        except Exception as e:
            st.error(f"⌛ Error al actualizar empresa: {e}")

    def crear_empresa(datos_nuevos):
        """Función para crear una nueva empresa."""
        try:
            # Validaciones obligatorias
            if not datos_nuevos.get("nombre"):
                st.error("⚠️ El nombre de la empresa es obligatorio.")
                return
                
            if not datos_nuevos.get("cif"):
                st.error("⚠️ El CIF es obligatorio.")
                return
                
            if not validar_dni_cif(datos_nuevos["cif"]):
                st.error("⚠️ El CIF no tiene un formato válido.")
                return

            # Verificar si ya existe empresa con mismo CIF
            existing = supabase.table("empresas").select("id").eq("cif", datos_nuevos["cif"]).execute()
            if existing.data:
                st.error("⚠️ Ya existe una empresa con este CIF.")
                return

            # Crear empresa
            create_data = {k: v for k, v in datos_nuevos.items() if v is not None and v != ""}
            create_data["created_at"] = datetime.now().isoformat()
            
            supabase.table("empresas").insert(create_data).execute()
            
            # Limpiar cache
            if hasattr(data_service.get_empresas_con_modulos, 'clear'):
                data_service.get_empresas_con_modulos.clear()
            
            st.success("✅ Empresa creada correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"⌛ Error al crear empresa: {e}")

    def eliminar_empresa(empresa_id):
        """Función para eliminar una empresa."""
        try:
            # Verificar si tiene datos relacionados
            usuarios = supabase.table("usuarios").select("id").eq("empresa_id", empresa_id).execute()
            if usuarios.data:
                st.error("⚠️ No se puede eliminar: la empresa tiene usuarios asignados.")
                return

            grupos = supabase.table("grupos").select("id").eq("empresa_id", empresa_id).execute()
            if grupos.data:
                st.error("⚠️ No se puede eliminar: la empresa tiene grupos formativos.")
                return

            # Eliminar empresa
            supabase.table("empresas").delete().eq("id", empresa_id).execute()
            
            # Limpiar cache
            if hasattr(data_service.get_empresas_con_modulos, 'clear'):
                data_service.get_empresas_con_modulos.clear()
            
            st.success("✅ Empresa eliminada correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"⌛ Error al eliminar empresa: {e}")

    # =========================
    # Configuración de campos para listado_con_ficha
    # =========================
    def get_campos_dinamicos(datos):
        """Determina campos a mostrar dinámicamente."""
        campos_base = [
            "nombre", "cif", "email", "telefono", "direccion", 
            "ciudad", "provincia", "codigo_postal", "pais"
        ]
        
        # Campos de módulos
        campos_modulos = [
            "formacion_activo", "formacion_inicio", "formacion_fin",
            "iso_activo", "iso_inicio", "iso_fin",
            "rgpd_activo", "rgpd_inicio", "rgpd_fin",
            "docu_avanzada_activo", "docu_avanzada_inicio", "docu_avanzada_fin"
        ]
        
        return campos_base + campos_modulos

    # Configuración de campos especiales
    campos_select = {
        "formacion_activo": [True, False],
        "iso_activo": [True, False],
        "rgpd_activo": [True, False],
        "docu_avanzada_activo": [True, False],
        "pais": ["España", "Portugal", "Francia", "Italia", "Otro"]
    }

    campos_readonly = ["id", "created_at"]
    
    campos_help = {
        "nombre": "Nombre completo de la empresa",
        "cif": "CIF/NIF de la empresa (obligatorio)",
        "email": "Email de contacto principal",
        "formacion_activo": "¿Está activo el módulo de formación?",
        "iso_activo": "¿Está activo el módulo ISO 9001?",
        "rgpd_activo": "¿Está activo el módulo RGPD?",
        "docu_avanzada_activo": "¿Está activo el módulo de documentación avanzada?"
    }

    # Columnas visibles en la tabla
    columnas_visibles = [
        "nombre", "cif", "email", "ciudad", "provincia", 
        "formacion_activo", "iso_activo", "rgpd_activo"
    ]

    # =========================
    # Mostrar interfaz principal
    # =========================
    if df_filtered.empty:
        if df_empresas.empty:
            st.info("ℹ️ No hay empresas registradas.")
        else:
            st.warning(f"🔍 No hay empresas que coincidan con los filtros aplicados.")
    else:
        # Usar el componente listado_con_ficha optimizado
        listado_con_ficha(
            df=df_filtered,
            columnas_visibles=columnas_visibles,
            titulo="Empresa",
            on_save=guardar_empresa,
            id_col="id",
            on_create=crear_empresa,
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            campos_dinamicos=get_campos_dinamicos,
            allow_creation=True,
            campos_help=campos_help
        )

    # =========================
    # Información adicional
    # =========================
    st.divider()
    with st.expander("ℹ️ Información sobre módulos"):
        st.markdown("""
        **Módulos disponibles:**
        - **📚 Formación**: Gestión de acciones formativas, grupos y participantes
        - **📋 ISO 9001**: Sistema de gestión de calidad
        - **🔒 RGPD**: Gestión de protección de datos
        - **📁 Doc. Avanzada**: Sistema documental transversal
        - **📊 CRM**: Gestión de relaciones comerciales (configuración independiente)
        
        Los módulos se activan mediante las fechas de inicio y fin correspondientes.
        """)
