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

                    col1, col2 = st.columns(2)

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
                            iso_inicio = st.date_input(
                                "Fecha de inicio ISO",
                                value=pd.to_datetime(row.get("iso_inicio"), errors="coerce").date()
                                if row.get("iso_inicio") else datetime.today().date()
                            )
                            iso_fin = st.date_input(
                                "Fecha de fin ISO",
                                value=pd.to_datetime(row.get("iso_fin"), errors="coerce").date()
                                if row.get("iso_fin") else None
                            )

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
                                        "iso_fin": iso_fin.isoformat() if iso_fin else None
                                    }).eq("id", row["id"]).execute()
                                    st.session_state[f"empresa_editada_{row['id']}"] = True
                                    st.success("✅ Cambios guardados correctamente.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error al actualizar: {str(e)}")

                    with col2:
                        with st.form(f"delete_empresa_{row['id']}"):
                            st.warning("⚠️ Esta acción eliminará la empresa permanentemente.")
                            confirmar = st.checkbox("Confirmo la eliminación")
                            eliminar = st.form_submit_button("🗑️ Eliminar empresa")
                            if eliminar and confirmar:
                                try:
                                    supabase.table("empresas").delete().eq("id", row["id"]).execute()
                                    st.success("✅ Empresa eliminada.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error al eliminar: {str(e)}")
        else:
            st.info("ℹ️ No hay empresas registradas.")

        st.divider()
        st.markdown("### ➕ Crear Empresa")
        if "empresa_creada" not in st.session_state:
            st.session_state.empresa_creada = False

        with st.form("crear_empresa", clear_on_submit=True):
            nombre = st.text_input("Nombre *")
            cif = st.text_input("CIF *")
            direccion = st.text_input("Dirección")
            telefono = st.text_input("Teléfono")
            email = st.text_input("Email")
            representante_nombre = st.text_input("Nombre del representante")
            representante_dni = st.text_input("DNI del representante")
            ciudad = st.text_input("Ciudad")
            provincia = st.text_input("Provincia")
            codigo_postal = st.text_input("Código Postal")

            st.markdown("#### ⚙️ Configuración de módulos")
            iso_activo = st.checkbox("Activar módulo ISO 9001", value=False)
            iso_inicio = st.date_input("Fecha de inicio ISO", value=datetime.today())
            iso_fin = st.date_input("Fecha de fin ISO", value=None)

            submitted = st.form_submit_button("Crear Empresa")
            if submitted and not st.session_state.empresa_creada:
                if not nombre or not cif:
                    st.error("⚠️ Los campos 'Nombre' y 'CIF' son obligatorios.")
                else:
                    try:
                        existe = supabase.table("empresas").select("id").eq("cif", cif).execute()
                        if existe.data:
                            st.error(f"⚠️ Ya existe una empresa con el CIF '{cif}'.")
                        else:
                            supabase.table("empresas").insert({
                                "nombre": nombre,
                                "cif": cif,
                                "direccion": direccion,
                                "telefono": telefono,
                                "email": email,
                                "representante_nombre": representante_nombre,
                                "representante_dni": representante_dni,
                                "ciudad": ciudad,
                                "provincia": provincia,
                                "codigo_postal": codigo_postal,
                                "fecha_alta": datetime.utcnow().isoformat(),
                                "iso_activo": iso_activo,
                                "iso_inicio": iso_inicio.isoformat() if iso_inicio else None,
                                "iso_fin": iso_fin.isoformat() if iso_fin else None
                            }).execute()

                            st.session_state.empresa_creada = True
                            st.success(f"✅ Empresa '{nombre}' creada correctamente.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al crear la empresa: {str(e)}")

    except Exception as e:
        st.error(f"❌ Error al cargar el módulo de empresas: {e}")
