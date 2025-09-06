import streamlit as st
import pandas as pd
from datetime import datetime

# -----------------------
# FUNCIONES AUXILIARES
# -----------------------
def modulo_iso(row=None):
    iso_activo = st.checkbox("Activar módulo ISO 9001", value=row.get("iso_activo", False) if row else False)
    iso_inicio = iso_fin = None
    if iso_activo:
        iso_inicio = st.date_input(
            "Fecha de inicio ISO",
            value=pd.to_datetime(row.get("iso_inicio"), errors="coerce").date() if row and row.get("iso_inicio") else datetime.today().date()
        )
        iso_fin = st.date_input(
            "Fecha de fin ISO",
            value=pd.to_datetime(row.get("iso_fin"), errors="coerce").date() if row and row.get("iso_fin") else datetime.today().date()
        )
    return iso_activo, iso_inicio, iso_fin

def modulo_rgpd(row=None):
    rgpd_inicio_val = pd.to_datetime(row.get("rgpd_inicio"), errors="coerce").date() if row and row.get("rgpd_inicio") else datetime.today().date()
    rgpd_fin_val = pd.to_datetime(row.get("rgpd_fin"), errors="coerce").date() if row and row.get("rgpd_fin") else None
    rgpd_activo_val = row.get("rgpd_activo", False) if row else False
    if rgpd_fin_val and rgpd_fin_val <= datetime.today().date():
        rgpd_activo_val = False

    st.markdown("#### 🛡️ Configuración RGPD")
    rgpd_activo = st.checkbox("Activar módulo RGPD", value=rgpd_activo_val)
    rgpd_inicio = st.date_input("Fecha de inicio RGPD", value=rgpd_inicio_val)
    rgpd_fin = st.date_input("Fecha de fin RGPD (opcional)", value=rgpd_fin_val)
    return rgpd_activo, rgpd_inicio, rgpd_fin

def modulo_crm(supabase, empresa_id):
    if not empresa_id:
        return False, None, None
    crm_res = supabase.table("crm_empresas").select("*").eq("empresa_id", empresa_id).execute()
    crm_data = crm_res.data[0] if crm_res.data else {}
    crm_activo = crm_data.get("crm_activo", False)
    crm_inicio = pd.to_datetime(crm_data.get("crm_inicio"), errors="coerce").date() if crm_data.get("crm_inicio") else datetime.today().date()
    crm_fin = pd.to_datetime(crm_data.get("crm_fin"), errors="coerce").date() if crm_data.get("crm_fin") else None
    if crm_fin and crm_fin <= datetime.today().date():
        crm_activo = False

    st.markdown("#### 📈 Configuración CRM")
    crm_activo = st.checkbox("Activar módulo CRM", value=crm_activo)
    crm_inicio = st.date_input("Fecha de inicio CRM", value=crm_inicio)
    crm_fin = st.date_input("Fecha de fin CRM (opcional)", value=crm_fin)
    return crm_activo, crm_inicio, crm_fin

def guardar_modulos(supabase, empresa_id, iso, rgpd, crm):
    iso_activo, iso_inicio, iso_fin = iso
    rgpd_activo, rgpd_inicio, rgpd_fin = rgpd
    crm_activo, crm_inicio, crm_fin = crm

    # Actualizar ISO y RGPD en tabla empresas
    supabase.table("empresas").update({
        "iso_activo": iso_activo,
        "iso_inicio": iso_inicio.isoformat() if iso_inicio else None,
        "iso_fin": iso_fin.isoformat() if iso_fin else None,
        "rgpd_activo": rgpd_activo,
        "rgpd_inicio": rgpd_inicio.isoformat() if rgpd_inicio else None,
        "rgpd_fin": rgpd_fin.isoformat() if rgpd_fin else None
    }).eq("id", empresa_id).execute()

    # RGPD tabla separada
    if rgpd_activo:
        existe = supabase.table("rgpd_empresas").select("id").eq("empresa_id", empresa_id).execute()
        if not existe.data:
            supabase.table("rgpd_empresas").insert({
                "empresa_id": empresa_id,
                "rgpd_activo": True,
                "rgpd_inicio": rgpd_inicio.isoformat(),
                "rgpd_fin": rgpd_fin.isoformat() if rgpd_fin else None,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

    # CRM tabla separada
    crm_res = supabase.table("crm_empresas").select("id").eq("empresa_id", empresa_id).execute()
    if crm_res.data:
        supabase.table("crm_empresas").update({
            "crm_activo": crm_activo,
            "crm_inicio": crm_inicio.isoformat() if crm_inicio else None,
            "crm_fin": crm_fin.isoformat() if crm_fin else None
        }).eq("empresa_id", empresa_id).execute()
    elif crm_activo:
        supabase.table("crm_empresas").insert({
            "empresa_id": empresa_id,
            "crm_activo": crm_activo,
            "crm_inicio": crm_inicio.isoformat() if crm_inicio else None,
            "crm_fin": crm_fin.isoformat() if crm_fin else None,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

def export_csv(df, filename="empresas.csv"):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("💾 Descargar CSV", data=csv, file_name=filename, mime="text/csv")

# -----------------------
# MAIN
# -----------------------
def main(supabase, session_state):
    st.title("🏢 Gestión de Empresas")

    # -----------------------
    # RESUMEN
    # -----------------------
    empresas_res = supabase.table("empresas").select("*").execute()
    empresas = empresas_res.data if empresas_res.data else []
    df_empresas = pd.DataFrame(empresas) if empresas else pd.DataFrame()

    total_empresas = len(df_empresas)
    empresas_mes = df_empresas[pd.to_datetime(df_empresas.get("fecha_alta", pd.Series()), errors="coerce").dt.month == datetime.now().month] if not df_empresas.empty else pd.DataFrame()
    total_mes = len(empresas_mes)

    provincia_top = df_empresas["provincia"].value_counts().idxmax() if "provincia" in df_empresas.columns and not df_empresas.empty else "N/D"
    ciudad_top = df_empresas["ciudad"].value_counts().idxmax() if "ciudad" in df_empresas.columns and not df_empresas.empty else "N/D"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏢 Total Empresas", total_empresas)
    col2.metric("🆕 Nuevas este mes", total_mes)
    col3.metric("📍 Provincia más frecuente", provincia_top)
    col4.metric("🌆 Ciudad más frecuente", ciudad_top)

    st.divider()
    st.markdown("### 🔍 Buscar y Exportar")
    search_query = st.text_input("Buscar por nombre o CIF")
    if search_query and not df_empresas.empty:
        df_empresas = df_empresas[
            df_empresas["nombre"].str.contains(search_query, case=False, na=False) |
            df_empresas["cif"].str.contains(search_query, case=False, na=False)
        ]
    if not df_empresas.empty:
        export_csv(df_empresas)

    st.divider()
    st.markdown("### ✏️ Empresas Registradas")
    if empresas:
        for row in empresas:
            with st.expander(f"{row['nombre']} ({row.get('cif', '')})"):
                st.write(f"**Dirección:** {row.get('direccion','')}")
                st.write(f"**Teléfono:** {row.get('telefono','')}")
                st.write(f"**Email:** {row.get('email','')}")
                st.write(f"**Representante:** {row.get('representante_nombre','')} ({row.get('representante_dni','')})")
                st.write(f"**Ciudad:** {row.get('ciudad','')}")
                st.write(f"**Provincia:** {row.get('provincia','')}")
                st.write(f"**Código Postal:** {row.get('codigo_postal','')}")
                st.write(f"**Fecha Alta:** {row.get('fecha_alta','')}")

                # Formulario edición
                with st.form(f"editar_{row['id']}"):
                    nuevo_nombre = st.text_input("Nombre", value=row.get("nombre",""))
                    nuevo_cif = st.text_input("CIF", value=row.get("cif",""))
                    nuevo_direccion = st.text_input("Dirección", value=row.get("direccion",""))
                    nuevo_telefono = st.text_input("Teléfono", value=row.get("telefono",""))
                    nuevo_email = st.text_input("Email", value=row.get("email",""))
                    nuevo_rep_nombre = st.text_input("Nombre representante", value=row.get("representante_nombre",""))
                    nuevo_rep_dni = st.text_input("DNI representante", value=row.get("representante_dni",""))
                    nueva_ciudad = st.text_input("Ciudad", value=row.get("ciudad",""))
                    nueva_provincia = st.text_input("Provincia", value=row.get("provincia",""))
                    nuevo_cp = st.text_input("Código Postal", value=row.get("codigo_postal",""))

                    iso = modulo_iso(row)
                    rgpd = modulo_rgpd(row)
                    crm = modulo_crm(supabase, row["id"])

                    guardar = st.form_submit_button("Guardar cambios")
                    if guardar:
                        supabase.table("empresas").update({
                            "nombre": nuevo_nombre,
                            "cif": nuevo_cif,
                            "direccion": nuevo_direccion,
                            "telefono": nuevo_telefono,
                            "email": nuevo_email,
                            "representante_nombre": nuevo_rep_nombre,
                            "representante_dni": nuevo_rep_dni,
                            "ciudad": nueva_ciudad,
                            "provincia": nueva_provincia,
                            "codigo_postal": nuevo_cp
                        }).eq("id", row["id"]).execute()
                        guardar_modulos(supabase, row["id"], iso, rgpd, crm)
                        st.success("Empresa actualizada ✅")
                        st.rerun()

                # Formulario eliminar
                with st.form(f"eliminar_{row['id']}"):
                    confirmar = st.checkbox("Confirmar eliminación")
                    eliminar = st.form_submit_button("Eliminar empresa")
                    if eliminar and confirmar:
                        supabase.table("empresas").delete().eq("id", row["id"]).execute()
                        st.success("Empresa eliminada ✅")
                        st.rerun()

    # -----------------------
    # CREAR NUEVA EMPRESA
    # -----------------------
    st.divider()
    st.subheader("➕ Crear nueva empresa")
    with st.form("crear_empresa"):
        nombre = st.text_input("Nombre *")
        cif = st.text_input("CIF *")
        direccion = st.text_input("Dirección")
        telefono = st.text_input("Teléfono")
        email = st.text_input("Email")
        representante_nombre = st.text_input("Nombre representante")
        representante_dni = st.text_input("DNI representante")
        ciudad = st.text_input("Ciudad")
        provincia = st.text_input("Provincia")
        codigo_postal = st.text_input("Código Postal")
        iso = modulo_iso()
        rgpd = modulo_rgpd()
        crm = (False, None, None)

        guardar = st.form_submit_button("Crear empresa")
        if guardar:
            if not nombre or not cif:
                st.error("Los campos 'Nombre' y 'CIF' son obligatorios.")
            else:
                res = supabase.table("empresas").insert({
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
                    "iso_activo": iso[0],
                    "iso_inicio": iso[1].isoformat() if iso[1] else None,
                    "iso_fin": iso[2].isoformat() if iso[2] else None,
                    "rgpd_activo": rgpd[0],
                    "rgpd_inicio": rgpd[1].isoformat() if rgpd[1] else None,
                    "rgpd_fin": rgpd[2].isoformat() if rgpd[2] else None
                }).execute()
                empresa_id = res.data[0]["id"]
                guardar_modulos(supabase, empresa_id, iso, rgpd, crm)
                st.success("Empresa creada ✅")
                st.rerun()
