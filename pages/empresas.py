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

def modulo_crm(supabase, empresa_id, row=None):
    crm_res = supabase.table("crm_empresas").select("*").eq("empresa_id", empresa_id).execute()
    crm_data = crm_res.data[0] if crm_res.data else {}
    crm_inicio_val = pd.to_datetime(crm_data.get("crm_inicio"), errors="coerce").date() if crm_data.get("crm_inicio") else datetime.today().date()
    crm_fin_val = pd.to_datetime(crm_data.get("crm_fin"), errors="coerce").date() if crm_data.get("crm_fin") else None
    crm_activo_val = crm_data.get("crm_activo", False)
    if crm_fin_val and crm_fin_val <= datetime.today().date():
        crm_activo_val = False

    st.markdown("#### 📈 Configuración CRM")
    crm_activo = st.checkbox("Activar módulo CRM", value=crm_activo_val)
    crm_inicio = st.date_input("Fecha de inicio CRM", value=crm_inicio_val)
    crm_fin = st.date_input("Fecha de fin CRM (opcional)", value=crm_fin_val)
    return crm_activo, crm_inicio, crm_fin

def guardar_empresa(supabase, empresa_id, datos, rgpd_data, crm_data):
    # Actualizar empresa
    supabase.table("empresas").update(datos).eq("id", empresa_id).execute()

    # RGPD
    if rgpd_data["activo"]:
        existe_rgpd = supabase.table("rgpd_empresas").select("id").eq("empresa_id", empresa_id).execute()
        if not existe_rgpd.data:
            supabase.table("rgpd_empresas").insert({
                "empresa_id": empresa_id,
                "rgpd_activo": True,
                "rgpd_inicio": rgpd_data["inicio"].isoformat(),
                "rgpd_fin": rgpd_data["fin"].isoformat() if rgpd_data["fin"] else None,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

    # CRM
    if crm_data["activo"]:
        crm_res = supabase.table("crm_empresas").select("id").eq("empresa_id", empresa_id).execute()
        if crm_res.data:
            supabase.table("crm_empresas").update({
                "crm_activo": crm_data["activo"],
                "crm_inicio": crm_data["inicio"].isoformat() if crm_data["inicio"] else None,
                "crm_fin": crm_data["fin"].isoformat() if crm_data["fin"] else None
            }).eq("empresa_id", empresa_id).execute()
        else:
            supabase.table("crm_empresas").insert({
                "empresa_id": empresa_id,
                "crm_activo": crm_data["activo"],
                "crm_inicio": crm_data["inicio"].isoformat() if crm_data["inicio"] else None,
                "crm_fin": crm_data["fin"].isoformat() if crm_data["fin"] else None,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

# -----------------------
# PÁGINA PRINCIPAL
# -----------------------
def gestionar_empresas(supabase):
    st.title("🏢 Gestión de Empresas")

    # Obtener empresas
    empresas_res = supabase.table("empresas").select("*").execute()
    empresas = empresas_res.data if empresas_res.data else []

    # Mostrar listado
    if empresas:
        df_empresas = pd.DataFrame(empresas)
        st.dataframe(df_empresas[["nombre", "cif", "email", "telefono"]])
    else:
        st.info("No hay empresas registradas.")

    # Crear nueva empresa
    st.subheader("➕ Crear nueva empresa")
    with st.form("crear_empresa"):
        nombre = st.text_input("Nombre de la empresa")
        cif = st.text_input("CIF")
        email = st.text_input("Email")
        telefono = st.text_input("Teléfono")

        iso_activo, iso_inicio, iso_fin = modulo_iso()
        rgpd_activo, rgpd_inicio, rgpd_fin = modulo_rgpd()
        crm_activo, crm_inicio, crm_fin = modulo_crm(supabase, empresa_id="")  # al crear no hay id aún

        if st.form_submit_button("Crear"):
            nueva_empresa = {
                "nombre": nombre,
                "cif": cif,
                "email": email,
                "telefono": telefono,
                "iso_activo": iso_activo,
                "iso_inicio": iso_inicio.isoformat() if iso_inicio else None,
                "iso_fin": iso_fin.isoformat() if iso_fin else None,
                "rgpd_activo": rgpd_activo,
                "rgpd_inicio": rgpd_inicio.isoformat(),
                "rgpd_fin": rgpd_fin.isoformat() if rgpd_fin else None,
            }
            res = supabase.table("empresas").insert(nueva_empresa).execute()
            if res.data:
                empresa_id = res.data[0]["id"]
                guardar_empresa(supabase, empresa_id, nueva_empresa,
                                {"activo": rgpd_activo, "inicio": rgpd_inicio, "fin": rgpd_fin},
                                {"activo": crm_activo, "inicio": crm_inicio, "fin": crm_fin})
                st.success("Empresa creada correctamente ✅")
                st.rerun()

    # Editar empresa existente
    st.subheader("✏️ Editar empresa")
    empresa_sel = st.selectbox("Selecciona empresa", [e["nombre"] for e in empresas]) if empresas else None
    if empresa_sel:
        empresa = next((e for e in empresas if e["nombre"] == empresa_sel), None)
        if empresa:
            with st.form("editar_empresa"):
                nombre = st.text_input("Nombre", empresa.get("nombre", ""))
                cif = st.text_input("CIF", empresa.get("cif", ""))
                email = st.text_input("Email", empresa.get("email", ""))
                telefono = st.text_input("Teléfono", empresa.get("telefono", ""))

                iso_activo, iso_inicio, iso_fin = modulo_iso(empresa)
                rgpd_activo, rgpd_inicio, rgpd_fin = modulo_rgpd(empresa)
                crm_activo, crm_inicio, crm_fin = modulo_crm(supabase, empresa["id"], empresa)

                if st.form_submit_button("Guardar cambios"):
                    datos = {
                        "nombre": nombre,
                        "cif": cif,
                        "email": email,
                        "telefono": telefono,
                        "iso_activo": iso_activo,
                        "iso_inicio": iso_inicio.isoformat() if iso_inicio else None,
                        "iso_fin": iso_fin.isoformat() if iso_fin else None,
                        "rgpd_activo": rgpd_activo,
                        "rgpd_inicio": rgpd_inicio.isoformat(),
                        "rgpd_fin": rgpd_fin.isoformat() if rgpd_fin else None,
                    }
                    guardar_empresa(supabase, empresa["id"], datos,
                                    {"activo": rgpd_activo, "inicio": rgpd_inicio, "fin": rgpd_fin},
                                    {"activo": crm_activo, "inicio": crm_inicio, "fin": crm_fin})
                    st.success("Empresa actualizada ✅")
                    st.rerun()

# =========================
# Punto de entrada para app.py
# =========================
def main(supabase, session_state):
    gestionar_empresas(supabase)
