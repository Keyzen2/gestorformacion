import streamlit as st
import pandas as pd
from datetime import datetime
from components.listado_crud import listado_crud
import uuid

def main(supabase, session_state):
    st.markdown("## 📄 Cláusulas y Consentimientos")
    st.caption("Gestiona tus textos legales y asegúrate de que estén actualizados.")
    st.divider()

    if session_state.role not in {"admin", "gestor"}:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    empresa_id = session_state.user.get("empresa_id")

    # =========================
    # Cargar cláusulas
    # =========================
    try:
        base_select = "id, tipo, ubicacion, version, fecha, enlace, empresa:empresas(nombre)"
        if session_state.role == "gestor":
            query = supabase.table("rgpd_clausulas").select(base_select).eq("empresa_id", empresa_id)
        else:
            query = supabase.table("rgpd_clausulas").select(base_select)

        clausulas_res = query.execute().data
        df = pd.DataFrame(clausulas_res) if clausulas_res else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error al cargar cláusulas: {e}")
        return

    if df.empty:
        st.info("ℹ️ No hay cláusulas registradas.")

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_clausula(clausula_id, datos):
        try:
            if session_state.role == "gestor":
                datos["empresa_id"] = empresa_id
            else:
                if "empresa_id" in datos and datos["empresa_id"]:
                    datos["empresa_id"] = empresas_dict[datos["empresa_id"]]

            supabase.table("rgpd_clausulas").update(datos).eq("id", clausula_id).execute()
            st.success("✅ Cambios guardados correctamente.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar cláusula: {e}")

    def crear_clausula(datos):
        try:
            clausula_id = str(uuid.uuid4())

            if session_state.role == "gestor":
                datos["empresa_id"] = empresa_id
            else:
                if "empresa_id" in datos and datos["empresa_id"]:
                    datos["empresa_id"] = empresas_dict[datos["empresa_id"]]

            datos["id"] = clausula_id
            datos["fecha"] = datetime.utcnow().isoformat()

            supabase.table("rgpd_clausulas").insert(datos).execute()
            st.success("✅ Cláusula creada correctamente.")

            for key in list(datos.keys()):
                if key in st.session_state:
                    del st.session_state[key]

            st.experimental_rerun()
        except Exception as e:
            st.error(f"❌ Error al crear cláusula: {e}")

    # =========================
    # Campos select
    # =========================
    campos_select = {
        "tipo": ["Formulario web", "Contrato", "Aviso legal", "Otro"]
    }
    if session_state.role == "admin":
        empresas_res = supabase.table("empresas").select("id, nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data}
        campos_select["empresa_id"] = list(empresas_dict.keys())

    # =========================
    # Llamada al CRUD
    # =========================
    listado_crud(
        df,
        columnas_visibles=["id", "tipo", "ubicacion", "version", "fecha", "enlace", "empresa"],
        titulo="Cláusula",
        on_save=guardar_clausula,
        on_create=crear_clausula,
        id_col="id",
        campos_select=campos_select,
        campos_textarea={"texto": {"label": "Texto legal completo"}}
    )
