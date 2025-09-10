import streamlit as st
import pandas as pd
from datetime import datetime
from utils import validar_dni_cif, export_csv
from components.listado_con_ficha import listado_con_ficha

def main(supabase, session_state):
    st.title("🏢 Gestión de Empresas")

    if session_state.role != "admin":
        st.warning("🔒 Solo los administradores pueden acceder a esta sección.")
        st.stop()

    # 1) Cargar empresas
    empresas_res = supabase.table("empresas").select("*").execute()
    df_emp = pd.DataFrame(empresas_res.data or [])

    # 2) Cargar CRM empresas
    crm_res = supabase.table("crm_empresas").select("*").execute()
    df_crm = pd.DataFrame(crm_res.data or [])

    # 3) Unir CRM a empresas
    if not df_crm.empty:
        df_emp = df_emp.merge(
            df_crm[["empresa_id", "crm_activo", "crm_inicio", "crm_fin"]],
            left_on="id", right_on="empresa_id", how="left"
        )
    else:
        df_emp["crm_activo"] = False
        df_emp["crm_inicio"] = None
        df_emp["crm_fin"] = None

    # 4) Métricas
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏢 Total Empresas", len(df_emp))

    # Nuevas este mes
    if "fecha_alta" in df_emp.columns and not df_emp.empty:
        fecha_alta_mes = pd.to_datetime(df_emp["fecha_alta"], errors="coerce").dt.month
        nuevas_mes = (fecha_alta_mes == datetime.now().month).sum()
    else:
        nuevas_mes = 0
    col2.metric("🆕 Nuevas este mes", nuevas_mes)

    # Provincia más frecuente
    if "provincia" in df_emp.columns and not df_emp.empty and df_emp["provincia"].notna().any():
        provincia_frec = df_emp["provincia"].value_counts().idxmax()
    else:
        provincia_frec = "N/D"
    col3.metric("📍 Provincia más frecuente", provincia_frec)

    # Ciudad más frecuente
    if "ciudad" in df_emp.columns and not df_emp.empty and df_emp["ciudad"].notna().any():
        ciudad_frec = df_emp["ciudad"].value_counts().idxmax()
    else:
        ciudad_frec = "N/D"
    col4.metric("🌆 Ciudad más frecuente", ciudad_frec)

    st.divider()

    # 5) Filtro de búsqueda
    st.markdown("### 🔍 Buscar y Exportar")
    query = st.text_input("Buscar por nombre, CIF, email, provincia o ciudad")
    df_fil = df_emp.copy()
    if query:
        q = query.lower()
        df_fil = df_fil[
            df_fil["nombre"].str.lower().str.contains(q, na=False) |
            df_fil["cif"].str.lower().str.contains(q, na=False) |
            df_fil["email"].str.lower().str.contains(q, na=False) |
            df_fil["provincia"].str.lower().str.contains(q, na=False) |
            df_fil["ciudad"].str.lower().str.contains(q, na=False)
        ]

    # 6) Export CSV (solo si hay datos)
    if not df_fil.empty:
        export_csv(df_fil, filename="empresas.csv")
    
    st.divider()

    # 7) Mostrar mensaje si no hay empresas en la base de datos
    if df_emp.empty:
        st.info("ℹ️ No hay empresas registradas en el sistema. Crea la primera empresa usando el formulario de abajo.")
    # 8) Mostrar mensaje si la búsqueda no encuentra resultados
    elif df_fil.empty and query:
        st.warning(f"🔍 No se encontraron empresas que coincidan con '{query}'. Prueba con otros términos de búsqueda.")
    # 9) Mostrar listado con ficha si hay datos
    else:
        # Guardar cambios desde ficha
        def guardar_empresa(empresa_id, datos):
            try:
                # Separar datos de CRM
                crm_data = {k: datos.pop(k) for k in ["crm_activo", "crm_inicio", "crm_fin"] if k in datos}

                # Actualizar empresa
                supabase.table("empresas").update(datos).eq("id", empresa_id).execute()

                # Actualizar/crear CRM
                if crm_data:
                    crm_data["empresa_id"] = empresa_id
                    supabase.table("crm_empresas").upsert(crm_data).execute()

                st.success("✅ Cambios guardados correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al actualizar empresa: {e}")

        # Campos editables
        campos_select = {
            "formacion_activo": [True, False],
            "iso_activo": [True, False],
            "rgpd_activo": [True, False],
            "docu_avanzada_activo": [True, False],
            "crm_activo": [True, False]
        }

        campos_readonly = ["fecha_alta"]

        listado_con_ficha(
            df_fil,
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
            id_col="id",
            campos_select=campos_select,
            campos_readonly=campos_readonly
        )

    st.divider()

    # 10) Creación de empresa
    st.subheader("➕ Crear nueva empresa")
    with st.form("crear_empresa", clear_on_submit=True):
        nombre        = st.text_input("Nombre *")
        cif           = st.text_input("CIF *")
        direccion     = st.text_input("Dirección")
        telefono      = st.text_input("Teléfono")
        email         = st.text_input("Email")
        rep_nombre    = st.text_input("Nombre representante")
        rep_dni       = st.text_input("DNI representante")
        ciudad        = st.text_input("Ciudad")
        provincia     = st.text_input("Provincia")
        codigo_postal = st.text_input("Código Postal")
        crear_empresa = st.form_submit_button("✅ Crear empresa")

    if crear_empresa:
        if not nombre or not cif:
            st.error("⚠️ Nombre y CIF son obligatorios.")
        elif not validar_dni_cif(cif):
            st.error("⚠️ CIF inválido.")
        else:
            try:
                supabase.table("empresas").insert({
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
                    "fecha_alta": datetime.utcnow().isoformat()
                }).execute()
                st.success("✅ Empresa creada.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al crear la empresa: {e}")
                
