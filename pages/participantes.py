import streamlit as st
import pandas as pd
from datetime import datetime
from services.alumnos import alta_alumno  # si necesitas alta de participantes

def main(supabase, session_state):
    st.subheader("👥 Gestión de Participantes")
    st.caption("Consulta de participantes y subida de diplomas.")

    try:
        participantes_res = supabase.table("participantes").select("*").execute()
        participantes = participantes_res.data or []

        if participantes:
            df_participantes = pd.DataFrame(participantes)
            df_participantes["Fecha Alta"] = pd.to_datetime(
                df_participantes.get("fecha_alta", pd.Series([None]*len(df_participantes))),
                errors="coerce"
            ).dt.date

            st.markdown("### 📋 Participantes")
            for _, row in df_participantes.iterrows():
                with st.expander(f"{row.get('nombre', 'Sin nombre')} ({row.get('dni', '')})"):
                    st.write(f"**Email:** {row.get('email', '')}")
                    st.write(f"**Teléfono:** {row.get('telefono', '')}")
                    st.write(f"**Fecha Alta:** {row.get('Fecha Alta', '—')}")

                    # -----------------------
                    # Subida de diploma
                    # -----------------------
                    st.markdown("### 📤 Subir nuevo diploma")
                    with st.form(f"diploma_upload_form_{row['id']}", clear_on_submit=True):
                        grupo_id = row.get("grupo_id")
                        grupos_res = supabase.table("grupos").select("id, codigo_grupo").execute().data or []
                        grupos_nombre_por_id = {g["id"]: g["codigo_grupo"] for g in grupos_res}
                        grupo_nombre = grupos_nombre_por_id.get(grupo_id, "Grupo asignado")
                        st.text(f"Grupo: {grupo_nombre}")

                        archivo = st.file_uploader("Selecciona el diploma (PDF)", type=["pdf"])
                        fecha_subida = st.date_input("Fecha de subida", value=datetime.today())
                        subir = st.form_submit_button("Subir diploma")

                        if subir:
                            if not archivo:
                                st.warning("⚠️ Debes seleccionar un archivo PDF.")
                            else:
                                try:
                                    # Validación: evitar duplicados por participante y grupo
                                    existe = (
                                        supabase.table("diplomas")
                                        .select("id")
                                        .eq("participante_id", row["id"])
                                        .eq("grupo_id", grupo_id)
                                        .execute()
                                    )
                                    if existe.data:
                                        st.warning(
                                            "⚠️ Ya existe un diploma para este participante en este grupo."
                                        )
                                    else:
                                        # Generar nombre único
                                        nombre_archivo = f"diploma_{row['id']}_{grupo_id}_{fecha_subida.isoformat()}.pdf"

                                        # Leer contenido del archivo subido
                                        file_bytes = archivo.read()

                                        # Subir al bucket 'documentos'
                                        try:
                                            supabase.storage.from_("documentos").upload(
                                                nombre_archivo,
                                                file_bytes,
                                                {"content-type": "application/pdf"},
                                            )
                                        except Exception as e:
                                            st.error(f"❌ Error al subir al bucket: {e}")
                                            st.stop()

                                        # Obtener URL pública
                                        url_diploma = supabase.storage.from_(
                                            "documentos"
                                        ).get_public_url(nombre_archivo)

                                        # Registrar en tabla diplomas
                                        supabase.table("diplomas").insert(
                                            {
                                                "participante_id": row["id"],
                                                "grupo_id": grupo_id,
                                                "url": url_diploma,
                                                "fecha_subida": fecha_subida.isoformat(),
                                                "archivo_nombre": nombre_archivo,
                                            }
                                        ).execute()

                                        st.success("✅ Diploma subido correctamente.")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error al subir el diploma: {e}")

        else:
            st.info("ℹ️ No hay participantes registrados.")

        # -----------------------
        # Vista consolidada de diplomas por grupo (solo admin)
        # -----------------------
        if session_state.role == "admin":
            st.markdown("## 📊 Diplomas por grupo")
            try:
                diplomas_all = supabase.table("diplomas").select("*").execute().data or []
                df_diplomas = pd.DataFrame(diplomas_all)
                if not df_diplomas.empty:
                    grupos_res = supabase.table("grupos").select("id, codigo_grupo").execute().data or []
                    grupos_nombre_por_id = {g["id"]: g["codigo_grupo"] for g in grupos_res}
                    df_diplomas["Grupo"] = df_diplomas["grupo_id"].map(grupos_nombre_por_id)
                    df_diplomas["Fecha"] = pd.to_datetime(
                        df_diplomas.get("fecha_subida", pd.Series([None]*len(df_diplomas))),
                        errors="coerce"
                    ).dt.date
                    st.dataframe(df_diplomas[["participante_id", "Grupo", "Fecha", "url"]])
                else:
                    st.info("ℹ️ No hay diplomas registrados aún.")
            except Exception as e:
                st.error(f"❌ Error al cargar diplomas globales: {e}")

    except Exception as e:
        st.error(f"❌ Error al cargar la página 'participantes': {e}")
