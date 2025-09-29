import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils import validar_dni_cif, export_csv
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.title("🏢 Gestión de Empresas")
    st.caption("Administración de empresas y configuración de módulos activos.")

    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        return

    # =========================
    # Cargar datos
    # =========================
    try:
        # Cargar empresas
        empresas_res = supabase.table("empresas").select("*").execute()
        df_emp = pd.DataFrame(empresas_res.data or [])

        # Cargar CRM empresas
        crm_res = supabase.table("crm_empresas").select("*").execute()
        df_crm = pd.DataFrame(crm_res.data or [])

        # Unir CRM a empresas
        if not df_crm.empty and not df_emp.empty:
            df_emp = df_emp.merge(
                df_crm[["empresa_id", "crm_activo", "crm_inicio", "crm_fin"]],
                left_on="id", right_on="empresa_id", how="left"
            )
            # Limpiar columna duplicada
            if "empresa_id" in df_emp.columns:
                df_emp = df_emp.drop("empresa_id", axis=1)
        else:
            # Añadir columnas CRM vacías si no hay datos
            df_emp["crm_activo"] = False
            df_emp["crm_inicio"] = None
            df_emp["crm_fin"] = None

    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    # =========================
    # Métricas mejoradas
    # =========================
    if not df_emp.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🏢 Total Empresas", len(df_emp))
        
        with col2:
            # Empresas nuevas este mes
            if "fecha_alta" in df_emp.columns:
                este_mes = df_emp[
                    pd.to_datetime(df_emp["fecha_alta"], errors="coerce").dt.month == datetime.now().month
                ]
                st.metric("🆕 Nuevas este mes", len(este_mes))
            else:
                st.metric("🆕 Nuevas este mes", 0)
        
        with col3:
            # Provincia más frecuente
            if "provincia" in df_emp.columns and not df_emp["provincia"].isna().all():
                provincia_top = df_emp["provincia"].value_counts().idxmax()
                st.metric("📍 Provincia principal", provincia_top)
            else:
                st.metric("📍 Provincia principal", "N/D")
        
        with col4:
            # Empresas con módulos activos
            modulos_activos = 0
            for col in ["formacion_activo", "iso_activo", "rgpd_activo", "crm_activo"]:
                if col in df_emp.columns:
                    modulos_activos += df_emp[col].fillna(False).sum()
            st.metric("📊 Módulos activos", int(modulos_activos))

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
            ["Todos", "Formación", "ISO 9001", "RGPD", "CRM"]
        )

    # Aplicar filtros
    df_filtered = df_emp.copy()
    
    if query:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["cif"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["email"].fillna("").str.lower().str.contains(q_lower, na=False) |
            df_filtered["provincia"].fillna("").str.lower().str.contains(q_lower, na=False) |
            df_filtered["ciudad"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]
    
    if modulo_filter != "Todos":
        modulo_map = {
            "Formación": "formacion_activo",
            "ISO 9001": "iso_activo", 
            "RGPD": "rgpd_activo",
            "CRM": "crm_activo"
        }
        col_filtro = modulo_map.get(modulo_filter)
        if col_filtro and col_filtro in df_filtered.columns:
            df_filtered = df_filtered[df_filtered[col_filtro] == True]

    # Exportar CSV
    if not df_filtered.empty:
        export_csv(df_filtered, filename="empresas.csv")
    
    st.divider()

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_empresa(empresa_id, datos_editados):
        """Función para guardar cambios en una empresa."""
        try:
            # Validaciones
            if not datos_editados.get("nombre") or not datos_editados.get("cif"):
                st.error("⚠️ Nombre y CIF son obligatorios.")
                return
                
            if not validar_dni_cif(datos_editados["cif"]):
                st.error("⚠️ CIF inválido.")
                return

            # Separar datos de CRM
            crm_data = {}
            empresa_data = {}
            
            for key, value in datos_editados.items():
                if key.startswith("crm_"):
                    crm_data[key] = value
                else:
                    empresa_data[key] = value

            # Actualizar empresa
            supabase.table("empresas").update(empresa_data).eq("id", empresa_id).execute()

            # Actualizar/crear CRM si hay datos
            if crm_data:
                crm_data["empresa_id"] = empresa_id
                # Intentar actualizar, si no existe lo crea (upsert)
                supabase.table("crm_empresas").upsert(crm_data, on_conflict="empresa_id").execute()

            st.success("✅ Empresa actualizada correctamente.")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al actualizar empresa: {e}")

    def crear_empresa(datos_nuevos):
        """Función para crear una nueva empresa."""
        try:
            # Validaciones
            if not datos_nuevos.get("nombre") or not datos_nuevos.get("cif"):
                st.error("⚠️ Nombre y CIF son obligatorios.")
                return
                
            if not validar_dni_cif(datos_nuevos["cif"]):
                st.error("⚠️ CIF inválido.")
                return

            # Separar datos de CRM
            crm_data = {}
            empresa_data = {}
            
            for key, value in datos_nuevos.items():
                if key.startswith("crm_"):
                    crm_data[key] = value
                else:
                    empresa_data[key] = value

            # Añadir fecha de alta
            empresa_data["fecha_alta"] = datetime.utcnow().isoformat()

            # Crear empresa
            result = supabase.table("empresas").insert(empresa_data).execute()
            
            if result.data:
                empresa_id = result.data[0]["id"]
                
                # Crear registro CRM si hay datos
                if crm_data and any(crm_data.values()):
                    crm_data["empresa_id"] = empresa_id
                    supabase.table("crm_empresas").insert(crm_data).execute()

                st.success("✅ Empresa creada correctamente.")
                st.rerun()
            else:
                st.error("❌ Error al crear la empresa.")
                
        except Exception as e:
            st.error(f"❌ Error al crear empresa: {e}")

    # =========================
    # Configuración de campos
    # =========================
    campos_select = {
        "formacion_activo": [True, False],
        "iso_activo": [True, False],
        "rgpd_activo": [True, False],
        "docu_avanzada_activo": [True, False],
        "crm_activo": [True, False]
    }

    campos_readonly = ["fecha_alta"]

    campos_help = {
        "cif": "CIF válido de la empresa (obligatorio)",
        "formacion_activo": "Activar módulo de gestión de formación",
        "iso_activo": "Activar módulo de gestión ISO 9001",
        "rgpd_activo": "Activar módulo de gestión RGPD",
        "crm_activo": "Activar módulo de CRM comercial",
        "docu_avanzada_activo": "Activar módulo de documentación avanzada"
    }

    # =========================
    # Mostrar interfaz principal
    # =========================
    if df_filtered.empty:
        if df_emp.empty:
            st.info("ℹ️ No hay empresas registradas en el sistema.")
            st.markdown("### ➕ Crear primera empresa")
        else:
            st.warning(f"🔍 No se encontraron empresas que coincidan con los filtros aplicados.")
        
        # Mostrar formulario de creación incluso si no hay datos
        if st.button("➕ Crear nueva empresa"):
            st.session_state["mostrar_formulario_empresa"] = True
    else:
        # Preparar datos para mostrar
        df_display = df_filtered.copy()
        
        # Asegurar que tenemos todas las columnas necesarias
        columnas_obligatorias = [
            "formacion_activo", "formacion_inicio", "formacion_fin",
            "iso_activo", "iso_inicio", "iso_fin",
            "rgpd_activo", "rgpd_inicio", "rgpd_fin",
            "docu_avanzada_activo", "docu_avanzada_inicio", "docu_avanzada_fin",
            "crm_activo", "crm_inicio", "crm_fin"
        ]
        
        for col in columnas_obligatorias:
            if col not in df_display.columns:
                if col.endswith("_activo"):
                    df_display[col] = False
                else:
                    df_display[col] = None

        # Mostrar tabla interactiva
        listado_con_ficha(
            df_display,
            columnas_visibles=[
                "id", "nombre", "cif", "direccion", "telefono", "email",
                "representante_nombre", "representante_dni", "ciudad", "provincia",
                "codigo_postal", "fecha_alta",
                "formacion_activo", "formacion_inicio", "formacion_fin",
                "iso_activo", "iso_inicio", "iso_fin",
                "rgpd_activo", "rgpd_inicio", "rgpd_fin",
                "docu_avanzada_activo", "docu_avanzada_inicio", "docu_avanzada_fin",
                "crm_activo", "crm_inicio", "crm_fin"
            ],
            titulo="Empresa",
            on_save=guardar_empresa,
            on_create=crear_empresa,
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly,
            allow_creation=True,
            campos_help=campos_help
        )

    # =========================
    # Formulario de creación rápida (alternativo)
    # =========================
    if st.session_state.get("mostrar_formulario_empresa", False) or df_emp.empty:
        st.divider()
        st.subheader("➕ Crear nueva empresa")
        
        with st.form("crear_empresa_rapida", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🏢 Datos básicos")
                nombre = st.text_input("Nombre *", help="Nombre completo de la empresa")
                cif = st.text_input("CIF *", help="CIF válido de la empresa")
                email = st.text_input("Email", help="Email de contacto")
                telefono = st.text_input("Teléfono", help="Teléfono de contacto")
                
            with col2:
                st.markdown("#### 📍 Ubicación")
                direccion = st.text_input("Dirección")
                ciudad = st.text_input("Ciudad")
                provincia = st.text_input("Provincia")
                codigo_postal = st.text_input("Código Postal")

            st.markdown("#### 👤 Representante legal")
            col3, col4 = st.columns(2)
            with col3:
                rep_nombre = st.text_input("Nombre representante")
            with col4:
                rep_dni = st.text_input("DNI representante")

            st.markdown("#### 📋 Módulos a activar")
            col5, col6, col7, col8 = st.columns(4)
            
            with col5:
                formacion_activo = st.checkbox("🎓 Formación", value=True)
            with col6:
                iso_activo = st.checkbox("📋 ISO 9001")
            with col7:
                rgpd_activo = st.checkbox("🔐 RGPD")
            with col8:
                crm_activo = st.checkbox("📈 CRM")

            col_submit1, col_submit2 = st.columns([1, 3])
            with col_submit1:
                crear_empresa_btn = st.form_submit_button("✅ Crear empresa", use_container_width=True)
            with col_submit2:
                if st.form_submit_button("❌ Cancelar", use_container_width=True):
                    st.session_state["mostrar_formulario_empresa"] = False
                    st.rerun()

        if crear_empresa_btn:
            if not nombre or not cif:
                st.error("⚠️ Nombre y CIF son obligatorios.")
            elif not validar_dni_cif(cif):
                st.error("⚠️ CIF inválido.")
            else:
                try:
                    # Crear empresa
                    empresa_data = {
                        "nombre": nombre,
                        "cif": cif,
                        "direccion": direccion,
                        "telefono": telefono,
                        "email": email,
                        "representante_nombre": rep_nombre,
                        "representante_dni": rep_dni,
                        "ciudad": ciudad,
                        "provincia": provincia,
                        "codigo_postal": codigo_postal,
                        "fecha_alta": datetime.utcnow().isoformat(),
                        "formacion_activo": formacion_activo,
                        "iso_activo": iso_activo,
                        "rgpd_activo": rgpd_activo,
                        "docu_avanzada_activo": False  # Por defecto desactivado
                    }
                    
                    result = supabase.table("empresas").insert(empresa_data).execute()
                    
                    if result.data:
                        empresa_id = result.data[0]["id"]
                        
                        # Crear registro CRM si está activado
                        if crm_activo:
                            supabase.table("crm_empresas").insert({
                                "empresa_id": empresa_id,
                                "crm_activo": True,
                                "crm_inicio": date.today().isoformat()
                            }).execute()

                        st.success("✅ Empresa creada exitosamente.")
                        st.session_state["mostrar_formulario_empresa"] = False
                        st.rerun()
                    else:
                        st.error("❌ Error al crear la empresa.")
                        
                except Exception as e:
                    st.error(f"❌ Error al crear la empresa: {e}")

    st.divider()
    st.caption("💡 Las empresas son la unidad organizativa principal. Cada empresa puede tener múltiples módulos activos.")
                
