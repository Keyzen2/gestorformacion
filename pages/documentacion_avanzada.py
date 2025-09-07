import streamlit as st
import pandas as pd
from datetime import datetime
from utils import subir_archivo_supabase, eliminar_archivo_supabase

BUCKET_NAME = "documentos"  # Tu bucket actual

def main(supabase, session_state):
    st.title("📁 Gestión Documental Avanzada")
    st.caption("Repositorio centralizado de documentos por empresa, grupo, módulo o usuario.")

    rol = session_state.role
    empresa_id = session_state.user.get("empresa_id")

    if rol not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # =========================
    # Filtros
    # =========================
    st.markdown("### 🔍 Filtros de búsqueda")
    modulo_filter = st.selectbox("Filtrar por módulo", ["-- Todos --", "formacion", "iso", "rgpd", "crm"])
    categoria_filter = st.text_input("Filtrar por categoría")
    nombre_filter = st.text_input("Buscar por nombre o descripción")

    # =========================
    # Cargar documentos
    # =========================
    docs_res = supabase.table("documentos_avanzados").select("*").eq("empresa_id", empresa_id).execute()
    documentos = docs_res.data if docs_res.data else []

    # Aplicar filtros
    if modulo_filter != "-- Todos --":
        documentos = [d for d in documentos if d.get("modulo") == modulo_filter]
    if categoria_filter:
        documentos = [d for d in documentos if categoria_filter.lower() in d.get("categoria", "").lower()]
    if nombre_filter:
        documentos = [d for d in documentos if nombre_filter.lower() in d.get("nombre", "").lower() or nombre_filter.lower() in d.get("descripcion", "").lower()]

    # =========================
    # Subida de documento
    # =========================
    st.markdown("### 📤 Subir nuevo documento")
    with st.form("upload_doc"):
        nombre = st.text_input("Nombre del documento *")
        descripcion = st.text_area("Descripción")
        categoria = st.text_input("Categoría (ej. contrato, informe, evidencia)")
        modulo = st.selectbox("Módulo asociado", ["formacion", "iso", "rgpd", "crm"])
        entidad = st.selectbox("Entidad asociada", ["Empresa", "Grupo", "Usuario"])
        entidad_id = st.text_input("ID de la entidad asociada")
        visibilidad = st.multiselect("Visible para", ["admin", "gestor", "alumno", "comercial"], default=["admin", "gestor"])
        archivo = st.file_uploader("Archivo", type=["pdf", "docx", "xlsx", "jpg", "png"])

        subir = st.form_submit_button("💾 Subir documento")
        if subir:
            if not nombre or not archivo:
                st.error("⚠️ El nombre y el archivo son obligatorios.")
            else:
                url = subir_archivo_supabase(supabase, archivo, empresa_id, bucket=BUCKET_NAME)
                if url:
                    supabase.table("documentos_avanzados").insert({
                        "nombre": nombre,
                        "descripcion": descripcion,
                        "categoria": categoria,
                        "modulo": modulo,
                        "entidad": entidad,
                        "entidad_id": entidad_id,
                        "visible_para": visibilidad,
                        "url": url,
                        "version": 1,
                        "empresa_id": empresa_id,
                        "created_by": session_state.user.get("id"),
                        "created_at": datetime.utcnow().isoformat()
                    }).execute()
                    st.success("✅ Documento subido correctamente.")
                    st.rerun()

    # =========================
    # Mostrar documentos
    # =========================
    st.markdown("### 📚 Documentos disponibles")
    if documentos:
        for doc in documentos:
            if rol not in doc.get("visible_para", []):
                continue
            with st.expander(f"{doc['nombre']} ({doc.get('categoria','')})"):
                st.write(f"📄 Descripción: {doc.get('descripcion','')}")
                st.write(f"🔗 URL: {doc.get('url','')}")
                st.write(f"📌 Módulo: {doc.get('modulo','')}")
                st.write(f"🏷️ Categoría: {doc.get('categoria','')}")
                st.write(f"📅 Subido el: {doc.get('created_at','')}")
                st.write(f"👤 Subido por: {doc.get('created_by','')}")
                st.write(f"🔢 Versión: {doc.get('version',1)}")
                st.write(f"👁️ Visibilidad: {', '.join(doc.get('visible_para', []))}")

                # Eliminación segura
                eliminar = st.button(f"🗑️ Eliminar documento", key=f"del_{doc['id']}")
                if eliminar:
                    eliminado = eliminar_archivo_supabase(supabase, doc.get("url"), bucket=BUCKET_NAME)
                    supabase.table("documentos_avanzados").delete().eq("id", doc["id"]).execute()
                    if eliminado:
                        st.success("✅ Documento y archivo eliminados correctamente.")
                    else:
                        st.warning("⚠️ Documento eliminado, pero el archivo no se pudo borrar.")
                    st.rerun()
    else:
        st.info("ℹ️ No hay documentos disponibles.")
              
