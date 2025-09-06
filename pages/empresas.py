import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    try:
        st.subheader("🏢 Empresas")
        st.caption("Gestión de empresas registradas en el sistema.")

        if session_state.role != "admin":
            st.warning("🔒 Solo los administradores pueden gestionar empresas.")
            st.stop()

        st.divider()
        st.markdown("### 📊 Resumen de Empresas")

        empresas_res = supabase.table("empresas").select("*").execute()
        df_empresas = pd.DataFrame(empresas_res.data) if empresas_res.data else pd.DataFrame()

        total_empresas = len(df_empresas)
        empresas_mes = df_empresas[
            pd.to_datetime(df_empresas.get("fecha_alta", pd.Series()), errors="coerce").dt.month == datetime.now().month
        ]
        total_mes = len(empresas_mes)

        provincia_top = df_empresas["provincia"].value_counts().idxmax() if "provincia" in df_empresas.columns else "N/D"
        ciudad_top = df_empresas["ciudad"].value_counts().idxmax() if "ciudad" in df_empresas.columns else "N/D"

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🏢 Total Empresas", total_empresas)
        col2.metric("🗓️ Nuevas este mes", total_mes)
        col3.metric("📍 Provincia más frecuente", provincia_top)
        col4.metric("🌆 Ciudad más frecuente", ciudad_top)

        st.divider()
        st.markdown("### 🔍 Buscar y Exportar")
        search_query = st.text_input("Buscar por nombre o CIF")
        if search_query:
            df_empresas = df_empresas[
                df_empresas["nombre"].str.contains(search_query, case=False, na=False) |
                df_empresas["cif"].str.contains(search_query, case=False, na=False)
            ]

        if not df_empresas.empty:
            st.download_button(
                "⬇️ Descargar CSV",
                data=df_empresas.to_csv(index=False).encode("utf-8"),
                file_name="empresas.csv",
                mime="text/csv"
            )

            st.divider()
            st.markdown("### 🧾 Empresas Registradas")

            for _, row in df_empresas.iterrows():
                with st.expander(f"{row['nombre']} ({row['cif']})"):
                    st.write(f"**Dirección:** {row.get('direccion', '')}")
                    st.write(f"**Teléfono:** {row.get('telefono', '')}")
                    st.write(f"**Email:** {row.get('email', '')}")
                    st.write(f"**Representante:** {row.get('representante_nombre', '')} ({row.get('representante_dni', '')})")
                    st.write(f"**Ciudad:** {row.get('ciudad', '')}")
                    st.write(f"**Provincia:** {row.get('provincia', '')}")
                    st.write(f"**Código Postal:** {row.get('codigo_postal', '')}")
                    st.write(f"**Fecha Alta:** {row.get('fecha_alta', '')}")
                    st.write(f"**ISO 9001 Activo:** {'✅ Sí' if row.get('iso_activo') else '❌ No'}")
                    st.write(f"**Inicio ISO:** {row.get('iso_inicio', '—')}")
                    st.write(f"**Fin ISO:** {row.get('iso_fin', '—')}")
                    st.write(f"**RGPD Activo:** {'✅ Sí' if row.get('rgpd_activo') else '❌ No'}")
                    st.write(f"**Inicio RGPD:** {row.get('rgpd_inicio', '—')}")
                    st.write(f"**Fin RGPD:** {row.get('rgpd_fin', '—')}")

                    col1, col2 = st.columns(2)

                    # -----------------------
                    # FORMULARIO EDICIÓN
                    # -----------------------
                    with col1:
                        with st.form(f"edit_empresa_{row['id']}", clear_on_submit=True):
                            nuevo_nombre = st.text_input("Nombre", value=row["nombre"])
                            nuevo_cif = st.text_input("CIF", value=row["cif"])
                            nueva_direccion = st.text_input("Dirección", value=row.get("direccion", ""))
                            nuevo_telefono = st.text_input("Teléfono", value=row.get("telefono", ""))
                            nuevo_email = st.text_input("Email", value=row.get("email", ""))
                            nuevo_rep_nombre = st.text_input("Nombre del representante", value=row.get("representante_nombre", ""))
                            nuevo_rep_dni = st.text_input("DNI del representante", value=row.get("representante_dni", ""))
                            nueva_ciudad = st.text_input("Ciudad", value=row.get("ciudad", ""))
                            nueva_provincia = st.text_input("Provincia", value=row.get("provincia", ""))
                            nuevo_cp = st.text_input("Código Postal", value=row.get("codigo_postal", ""))

                            st.markdown("#### ⚙️ Configuración de módulos")
                            iso_activo = st.checkbox("Activar módulo ISO 9001", value=row.get("iso_activo", False))
                            if iso_activo:
                                iso_inicio = st.date_input(
                                    "Fecha de inicio ISO",
                                    value=pd.to_datetime(row.get("iso_inicio"), errors="coerce").date()
                                    if row.get("iso_inicio") else datetime.today().date()
                                )
                                iso_fin = st.date_input(
                                    "Fecha de fin ISO",
                                    value=pd.to_datetime(row.get("iso_fin"), errors="coerce").date()
                                    if row.get("iso_fin") else datetime.today().date()
                                )
                            else:
                                iso_inicio, iso_fin = None, None

                            st.markdown("#### 🛡️ Configuración RGPD")
                            rgpd_inicio = st.date_input(
                                "Fecha de inicio RGPD",
                                value=pd.to_datetime(row.get("rgpd_inicio"), errors="coerce").date()
                                if row.get("rgpd_inicio") else datetime.today().date()
                            )
                            rgpd_fin = st.date_input(
                                "Fecha de fin RGPD (opcional)",
                                value=pd.to_datetime(row.get("rgpd_fin"), errors="coerce").date()
                                if row.get("rgpd_fin") else None
                            )

                            rgpd_activo_valor = row.get("rgpd_activo", False)
                            if rgpd_fin and rgpd_fin <= datetime.today().date():
                                rgpd_activo_valor = False

                            rgpd_activo = st.checkbox("Activar módulo RGPD", value=rgpd_activo_valor)

                            # 📈 Configuración CRM
                            crm_res = supabase.table("crm_empresas").select("*").eq("empresa_id", row["id"]).execute()
                            crm_data = crm_res.data[0] if crm_res.data else {}

                            crm_inicio = st.date_input(
                                "Fecha de inicio CRM",
                                value=pd.to_datetime(crm_data.get("crm_inicio"), errors="coerce").date()
                                if crm_data.get("crm_inicio") else datetime.today().date()
                            )
                            crm_fin = st.date_input(
                                "Fecha de fin CRM (opcional)",
                                value=pd.to_datetime(crm_data.get("crm_fin"), errors="coerce").date()
                                if crm_data.get("crm_fin") else None
                            )

                            crm_activo_valor = crm_data.get("crm_activo", False)
                            if crm_fin and crm_fin <= datetime.today().date():
                                crm_activo_valor = False

                            crm_activo = st.checkbox("Activar módulo CRM", value=crm_activo_valor)

                            if f"empresa_editada_{row['id']}" not in st.session_state:
                                st.session_state[f"empresa_editada_{row['id']}"] = False

                            guardar = st.form_submit_button("Guardar cambios")

                            if guardar and not st.session_state[f"empresa_editada_{row['id']}"]:
                                try:
                                    supabase.table("empresas").update({
                                        "nombre": nuevo_nombre,
                                        "cif": nuevo_cif,
                                        "direccion": nueva_direccion,
                                        "telefono": nuevo_telefono,
                                        "email": nuevo_email,
                                        "representante_nombre": nuevo_rep_nombre,
                                        "representante_dni": nuevo_rep_dni,
                                        "ciudad": nueva_ciudad,
                                        "provincia": nueva_provincia,
                                        "codigo_postal": nuevo_cp,
                                        "iso_activo": iso_activo,
                                        "iso_inicio": iso_inicio.isoformat() if iso_inicio else None,
                                        "iso_fin": iso_fin.isoformat() if iso_fin else None,
                                        "rgpd_activo": rgpd_activo,
                                        "rgpd_inicio": rgpd_inicio.isoformat() if rgpd_inicio else None,
                                                                                "rgpd_fin": rgpd_fin.isoformat() if rgpd_fin else None
                                    }).eq("id", row["id"]).execute()

                                    # Crear registro en rgpd_empresas si activamos RGPD y no existe
                                    if rgpd_activo:
                                        existe_rgpd = supabase.table("rgpd_empresas").select("id").eq("empresa_id", row["id"]).execute()
                                        if not existe_rgpd.data:
import streamlit as st
import pandas as pd

def main(supabase_admin, session_state):
    st.title("🏢 Gestión de Empresas")

    # --- Botón crear nueva empresa ---
    with st.expander("➕ Crear nueva empresa"):
        with st.form("form_nueva_empresa"):
            nombre = st.text_input("Nombre de la empresa")
            cif = st.text_input("CIF")
            telefono = st.text_input("Teléfono")
            email = st.text_input("Email")
            submit = st.form_submit_button("Guardar")

        if submit:
            if not nombre or not cif:
                st.warning("El nombre y CIF son obligatorios.")
            else:
                try:
                    supabase_admin.table("empresas").insert({
                        "nombre": nombre,
                        "cif": cif,
                        "telefono": telefono,
                        "email": email
                    }).execute()
                    st.success("✅ Empresa creada correctamente")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Error al crear empresa: {e}")

    # --- Listado de empresas ---
    try:
        res = supabase_admin.table("empresas").select("*").execute()
        empresas = res.data if res.data else []
    except Exception as e:
        st.error(f"❌ Error cargando empresas: {e}")
        empresas = []

    if not empresas:
        st.info("No hay empresas registradas aún.")
        return

    df = pd.DataFrame(empresas)
    st.dataframe(df, use_container_width=True)

    # --- Selección de empresa para editar ---
    empresa_ids = [e["id"] for e in empresas if "id" in e]
    empresa_sel = st.selectbox("Seleccionar empresa", empresa_ids)

    if empresa_sel:
        empresa = next((e for e in empresas if e["id"] == empresa_sel), None)
        if empresa:
            st.subheader(f"✏️ Editar Empresa: {empresa.get('nombre', '')}")

            with st.form(f"form_edit_empresa_{empresa_sel}"):
                nombre = st.text_input("Nombre", value=empresa.get("nombre", ""))
                cif = st.text_input("CIF", value=empresa.get("cif", ""))
                telefono = st.text_input("Teléfono", value=empresa.get("telefono", ""))
                email = st.text_input("Email", value=empresa.get("email", ""))
                iso_activo = st.checkbox("ISO Activo", value=empresa.get("iso_activo", False))
                rgpd_activo = st.checkbox("RGPD Activo", value=empresa.get("rgpd_activo", False))
                crm_activo = st.checkbox("CRM Activo", value=empresa.get("crm_activo", False))
                guardar = st.form_submit_button("💾 Guardar cambios")

            if guardar:
                try:
                    supabase_admin.table("empresas").update({
                        "nombre": nombre,
                        "cif": cif,
                        "telefono": telefono,
                        "email": email,
                        "iso_activo": iso_activo,
                        "rgpd_activo": rgpd_activo,
                        "crm_activo": crm_activo
                    }).eq("id", empresa_sel).execute()
                    st.success("✅ Empresa actualizada correctamente")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Error actualizando empresa: {e}")
