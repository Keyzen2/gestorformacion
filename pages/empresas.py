import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils import (
    validar_cif,
    export_csv,
    modulo_formacion,
    modulo_iso,
    modulo_rgpd,
    modulo_crm,
    modulo_docu_avanzada,
    guardar_modulos,
)

def main(supabase, session_state):
    st.title("🏢 Gestión de Empresas")

    # Sólo admin o gestor
    if session_state.role not in {"admin", "gestor"}:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # —————————————————
    # 1) Mostrar lista y métricas
    # —————————————————
    empresas_res = supabase.table("empresas").select("*").execute()
    empresas = empresas_res.data or []
    df_emp = pd.DataFrame(empresas) if empresas else pd.DataFrame()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏢 Total Empresas", len(df_emp))
    col2.metric(
        "🆕 Nuevas este mes",
        len(
            df_emp[
                pd.to_datetime(df_emp.get("fecha_alta"), errors="coerce")
                .dt.month
                == datetime.now().month
            ]
        )
        if not df_emp.empty
        else 0,
    )
    col3.metric(
        "📍 Provincia más frecuente",
        df_emp["provincia"].value_counts().idxmax()
        if "provincia" in df_emp.columns and not df_emp.empty
        else "N/D",
    )
    col4.metric(
        "🌆 Ciudad más frecuente",
        df_emp["ciudad"].value_counts().idxmax()
        if "ciudad" in df_emp.columns and not df_emp.empty
        else "N/D",
    )

    st.divider()

    # —————————————————
    # 2) Buscador y exportación
    # —————————————————
    st.markdown("### 🔍 Buscar y Exportar")
    query = st.text_input("Buscar por nombre o CIF")
    df_fil = df_emp.copy()
    if query:
        df_fil = df_fil[
            df_fil["nombre"].str.contains(query, case=False, na=False)
            | df_fil["cif"].str.contains(query, case=False, na=False)
        ]
    if not df_fil.empty:
        export_csv(df_fil, filename="empresas.csv")
    else:
        st.info("ℹ️ No hay empresas para mostrar.")

    st.divider()

    # —————————————————
    # 3) Formulario edición de datos generales
    # —————————————————
    st.markdown("### ✏️ Empresas Registradas")
    for row in empresas:
        with st.expander(f"{row['nombre']} ({row.get('cif','')})"):
            st.write(f"**Dirección:** {row.get('direccion','')}")
            st.write(f"**Teléfono:** {row.get('telefono','')}")
            st.write(f"**Email:** {row.get('email','')}")
            st.write(
                f"**Representante:** {row.get('representante_nombre','')} "
                f"({row.get('representante_dni','')})"
            )
            st.write(f"**Ciudad:** {row.get('ciudad','')}")
            st.write(f"**Provincia:** {row.get('provincia','')}")
            st.write(f"**Código Postal:** {row.get('codigo_postal','')}")
            st.write(f"**Fecha Alta:** {row.get('fecha_alta','')}")

            with st.form(f"edit_basicos_{row['id']}", clear_on_submit=True):
                nuevo_nombre   = st.text_input("Nombre", value=row.get("nombre",""))
                nuevo_cif      = st.text_input("CIF", value=row.get("cif",""))
                nueva_direccion= st.text_input("Dirección", value=row.get("direccion",""))
                nuevo_tel      = st.text_input("Teléfono", value=row.get("telefono",""))
                nuevo_email    = st.text_input("Email", value=row.get("email",""))
                rep_nombre     = st.text_input(
                    "Nombre representante", value=row.get("representante_nombre","")
                )
                rep_dni        = st.text_input(
                    "DNI representante", value=row.get("representante_dni","")
                )
                nueva_ciudad   = st.text_input("Ciudad", value=row.get("ciudad",""))
                nueva_provin   = st.text_input("Provincia", value=row.get("provincia",""))
                nuevo_cp       = st.text_input(
                    "Código Postal", value=row.get("codigo_postal","")
                )
                guardar_basicos = st.form_submit_button("💾 Guardar cambios")

                if guardar_basicos:
                    if nuevo_cif and not validar_cif(nuevo_cif):
                        st.error("⚠️ CIF inválido.")
                    else:
                        supabase.table("empresas").update({
                            "nombre": nuevo_nombre,
                            "cif": nuevo_cif,
                            "direccion": nueva_direccion,
                            "telefono": nuevo_tel,
                            "email": nuevo_email,
                            "representante_nombre": rep_nombre,
                            "representante_dni": rep_dni,
                            "ciudad": nueva_ciudad,
                            "provincia": nueva_provin,
                            "codigo_postal": nuevo_cp
                        }).eq("id", row["id"]).execute()
                        st.success("✅ Datos generales actualizados.")
                        st.rerun()

    st.divider()

    # —————————————————
    # 4) Formulario creación de empresa (datos básicos)
    # —————————————————
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
            st.error("⚠️ Nombre y CIF obligatorios.")
        elif not validar_cif(cif):
            st.error("⚠️ CIF inválido.")
        else:
            try:
                res = supabase.table("empresas").insert({
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
                empresa_id = res.data[0]["id"]
                # Guardamos el ID en session_state para los módulos
                session_state["last_empresa_id"] = empresa_id
                st.success("✅ Empresa creada. Ahora configura los módulos.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al crear la empresa: {e}")

    # —————————————————
    # 5) Formularios independientes de módulos
    # —————————————————
    empresa_id = session_state.get("last_empresa_id")
    if empresa_id:
        emp_data = supabase.table("empresas").select("*").eq("id", empresa_id).execute().data[0]
        st.markdown("### ⚙️ Configuración de módulos para la empresa recién creada")

        def render_module(key: str, label: str):
            defaults = emp_data
            with st.expander(label, expanded=False):
                activo = st.checkbox(
                    "Activar módulo", value=defaults.get(f"{key}_activo", False), key=f"{key}_activo"
                )
                if activo:
                    inicio = st.date_input(
                        "Fecha inicio",
                        value=defaults.get(f"{key}_inicio", date.today()),
                        key=f"{key}_inicio",
                    )
                    fin = st.date_input(
                        "Fecha fin prevista",
                        value=defaults.get(f"{key}_fin", date.today()),
                        key=f"{key}_fin",
                    )
                else:
                    inicio = fin = None

                if st.button("💾 Guardar configuración", key=f"btn_{key}"):
                    if activo and inicio and fin and inicio > fin:
                        st.error("⚠️ Fecha fin anterior a inicio.")
                    else:
                        payload = {
                            f"{key}_activo": activo,
                            f"{key}_inicio": inicio.isoformat() if inicio else None,
                            f"{key}_fin": fin.isoformat() if fin else None,
                        }
                        supabase.table("empresas").update(payload).eq("id", empresa_id).execute()
                        st.success(f"✅ Módulo '{label}' actualizado.")
                        st.rerun()

        render_module("formacion", "📚 Formación")
        render_module("iso", "✅ ISO 9001")
        render_module("rgpd", "🛡️ RGPD")
        render_module("docu_avanzada", "📁 Documentación Avanzada")

        # CRM (tabla separada)
        crm_res = supabase.table("crm_empresas").select("*").eq("empresa_id", empresa_id).execute()
        crm_defaults = crm_res.data[0] if crm_res.data else {}
        with st.expander("📈 CRM", expanded=False):
            activo = st.checkbox(
                "Activar CRM", value=crm_defaults.get("crm_activo", False), key="crm_activo"
            )
            if activo:
                inicio = st.date_input(
                    "Fecha inicio",
                    value=crm_defaults.get("crm_inicio", date.today()),
                    key="crm_inicio",
                )
                fin = st.date_input(
                    "Fecha fin prevista",
                    value=crm_defaults.get("crm_fin", date.today()),
                    key="crm_fin",
                )
            else:
                inicio = fin = None

            if st.button("💾 Guardar CRM"):
                payload = {
                    "empresa_id": empresa_id,
                    "crm_activo": activo,
                    "crm_inicio": inicio.isoformat() if inicio else None,
                    "crm_fin": fin.isoformat() if fin else None,
                }
                supabase.table("crm_empresas").upsert(payload).execute()
                st.success("✅ CRM actualizado.")
                st.rerun()
