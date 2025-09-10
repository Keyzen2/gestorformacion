import streamlit as st
import pandas as pd
from utils import export_csv
from components.listado_crud import listado_crud
import uuid
from datetime import datetime

def main(supabase, session_state):
    st.subheader("🛡️ Encargados del Tratamiento")
    st.caption("Gestión de encargados RGPD vinculados a empresas.")
    st.divider()

    # Permisos
    if session_state.role not in {"admin", "gestor"}:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # =========================
    # Cargar encargados
    # =========================
    try:
        base_select = (
            "id, nombre, email, telefono, empresa:empresas(nombre)"
        )

        if session_state.role == "gestor":
            query = supabase.table("rgpd_encargados").select(base_select).eq(
                "empresa_id", session_state.user.get("empresa_id")
            )
        else:  # admin
            query = supabase.table("rgpd_encargados").select(base_select)

        encargados_res = query.execute().data
        df = pd.DataFrame(encargados_res) if encargados_res else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error al cargar encargados: {e}")
        return

    if df.empty:
        st.info("ℹ️ No hay encargados registrados.")

    # =========================
    # Exportar CSV
    # =========================
    if not df.empty:
        export_csv(df, filename="encargados_filtrados.csv")
        st.divider()

    # =========================
    # Funciones CRUD
    # =========================
    def guardar_encargado(encargado_id, datos):
        try:
            if session_state.role == "gestor":
                datos["empresa_id"] = session_state.user.get("empresa_id")
            else:
                if "empresa_id" in datos and datos["empresa_id"]:
                    datos["empresa_id"] = empresas_dict[datos["empresa_id"]]

            supabase.table("rgpd_encargados").update(datos).eq("id", encargado_id).execute()
            st.success("✅ Cambios guardados correctamente.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar encargado: {e}")

    def crear_encargado(datos):
        try:
            encargado_id = str(uuid.uuid4())

            if session_state.role == "gestor":
                datos["empresa_id"] = session_state.user.get("empresa_id")
            else:
                if "empresa_id" in datos and datos["empresa_id"]:
                    datos["empresa_id"] = empresas_dict[datos["empresa_id"]]

            datos["id"] = encargado_id
            datos["created_at"] = datetime.utcnow().isoformat()

            supabase.table("rgpd_encargados").insert(datos).execute()
            st.success("✅ Encargado creado correctamente.")

            # Limpiar campos para evitar reenvío
            for key in list(datos.keys()):
                if key in st.session_state:
                    del st.session_state[key]

            st.experimental_rerun()
        except Exception as e:
            st.error(f"❌ Error al crear encargado: {e}")

    # =========================
    # Campos select según rol
    # =========================
    campos_select = {}
    if session_state.role == "admin":
        empresas_res = supabase.table("empresas").select("id, nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data}
        campos_select["empresa_id"] = list(empresas_dict.keys())

    # =========================
    # Llamada al CRUD
    # =========================
    listado_crud(
        df,
        columnas_visibles=[
            "id", "nombre", "email", "telefono", "empresa"
        ],
        titulo="Encargado",
        on_save=guardar_encargado,
        on_create=crear_encargado,
        id_col="id",
        campos_select=campos_select
    )
    
