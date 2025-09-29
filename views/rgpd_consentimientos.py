import streamlit as st
import pandas as pd
from datetime import datetime
from components.listado_con_ficha import listado_con_ficha
import uuid

def render(supabase, session_state):
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
        base_select = "id, tipo, ubicacion, version, fecha, enlace, texto, empresa:empresas(nombre)"
        if session_state.role == "gestor":
            query = supabase.table("rgpd_clausulas").select(base_select).eq("empresa_id", empresa_id)
        else:
            query = supabase.table("rgpd_clausulas").select(base_select)

        res = query.execute().data
        df = pd.DataFrame(res) if res else pd.DataFrame()

        # Aplanar empresa
        if "empresa" in df.columns:
            df["empresa"] = df["empresa"].apply(lambda x: x.get("nombre") if isinstance(x, dict) else x)

        # Mostrar enlace como botón de descarga si existe
        if "enlace" in df.columns:
            df["enlace"] = df["enlace"].apply(
                lambda url: f"[📥 Descargar PDF]({url})" if url else ""
            )

    except Exception as e:
        st.error(f"❌ Error al cargar cláusulas: {e}")
        return

    if df.empty:
        st.info("ℹ️ No hay cláusulas registradas.")
        return

    # =========================
    # Selects y permisos
    # =========================
    campos_select = {
        "tipo": ["Formulario web", "Contrato", "Aviso legal", "Otro"]
    }
    campos_readonly = ["fecha"]
    if session_state.role == "gestor":
        campos_readonly.append("empresa")

    if session_state.role == "admin":
        empresas_res = supabase.table("empresas").select("id, nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data}
        campos_select["empresa_id"] = list(empresas_dict.keys())

    campos_textarea = {
        "texto": {"label": "Texto legal completo"}
    }

    campos_file = {
        "pdf_file": {"label": "📄 Subir/Actualizar PDF de la cláusula", "type": ["pdf"]}
    }

    # =========================
    # Guardar cambios desde ficha
    # =========================
    def guardar_clausula(clausula_id, datos):
        try:
            # Mapear empresa_id según rol
            if session_state.role == "gestor":
                datos["empresa_id"] = empresa_id
            else:
                if "empresa_id" in datos and datos["empresa_id"]:
                    datos["empresa_id"] = empresas_dict[datos["empresa_id"]]
                else:
                    datos["empresa_id"] = None

            # Subida de PDF si se adjunta
            if "pdf_file" in datos and datos["pdf_file"] is not None and datos["empresa_id"]:
                file_path = f"{datos['empresa_id']}/{clausula_id}.pdf"
                supabase.storage.from_("rgpd_clausulas").upload(
                    file_path,
                    datos["pdf_file"].getvalue(),
                    {"upsert": True}
                )
                public_url = supabase.storage.from_("rgpd_clausulas").get_public_url(file_path)
                datos["enlace"] = public_url
                del datos["pdf_file"]

            supabase.table("rgpd_clausulas").update(datos).eq("id", clausula_id).execute()
            st.success("✅ Cambios guardados correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al actualizar cláusula: {e}")

    # =========================
    # Llamada a listado_con_ficha
    # =========================
    listado_con_ficha(
        df,
        columnas_visibles=["id", "tipo", "ubicacion", "version", "fecha", "enlace", "empresa", "texto"],
        titulo="Cláusula",
        on_save=guardar_clausula,
        id_col="id",
        campos_select=campos_select,
        campos_textarea=campos_textarea,
        campos_file=campos_file,
        campos_readonly=campos_readonly
    )
    
