import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.subheader("👨‍🎓 Participantes")
    st.caption("Gestión de participantes y diplomas asociados.")

    # =========================
    # Listado de participantes
    # =========================
    participantes_res = supabase.table("participantes").select("*").execute().data or []
    if not participantes_res:
        st.info("ℹ️ No hay participantes registrados.")
        return

    df_participantes = pd.DataFrame(participantes_res)
    df_participantes["Fecha Alta"] = pd.to_datetime(df_participantes["fecha_alta"], errors="coerce").dt.date

    st.markdown("### 📋 Participantes registrados")
    st.dataframe(df_participantes[["id", "nombre", "email", "grupo_id", "Fecha Alta"]])

    # Crear un diccionario de nombres de grupo
    grupos_res = supabase.table("grupos").select("*").execute().data or []
    grupos_nombre_por_id = {g["id"]: g.get("codigo_grupo", "—") for g in grupos_res}

    # =========================
    # Subida de diplomas
    # =========================
    for idx, row in df_participantes.iterrows():
        st.divider()
        st.markdown(f"### 🎓 Participante: {row['nombre']} ({row['email']})")

        # Mostrar diplomas existentes
        diplomas_res = (
            supabase.table("diplomas")
            .select("*")
            .eq("participante_id", row["id"])
            .execute()
            .data or []
        )

        if diplomas_res:
            st.markdown("#### 🗂️ Diplomas existentes")
            for d in diplomas_res:
                url = d["url"]["publicUrl"] if d.get("url") else "#"
                fecha = pd.to_datetime(d["fecha_subida"]).date() if d.get("fecha_subida") else "—"
                st.markdown(f"- Grupo: {grupos_nombre_por_id.get(d['grupo_id'], '—')}, Fecha: {fecha} — [Abrir PDF]({url})")

        # Formulario para subir nuevo diploma
        st.markdown("### 📤 Subir nuevo diploma")
        with st.form(f"diploma_upload_form_{row['id']}", clear_on_submit=True):
            grupo_id = row.get("grupo_id")
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
                    # Comprobar si ya existe diploma para este participante y grupo
                    existe = (
                        supabase.table("diplomas")
                        .select("*")
                        .eq("participante_id", row["id"])
                        .eq("grupo_id", grupo_id)
                        .execute()
                    ).data

                    nombre_archivo = f"diploma_{row['id']}_{grupo_id}.pdf"
                    file_bytes = archivo.read()

                    if existe:
                        st.warning("⚠️ Ya existe un diploma para este participante en este grupo.")
                        reemplazar = st.checkbox("Deseo reemplazar el diploma existente")
                        if reemplazar:
                            supabase.storage.from_("documentos").upload(
                                nombre_archivo,
                                file_bytes,
                                {"content-type": "application/pdf"},
                                upsert=True
                            )
                            url_diploma = supabase.storage.from_("documentos").get_public_url(nombre_archivo)
                            supabase.table("diplomas").update({
                                "url": url_diploma,
                                "fecha_subida": fecha_subida.isoformat(),
                                "archivo_nombre": nombre_archivo
                            }).eq("id", existe[0]["id"]).execute()
                            st.success("✅ Diploma reemplazado correctamente.")
                            st.rerun()
                    else:
                        supabase.storage.from_("documentos").upload(
                            nombre_archivo,
                            file_bytes,
                            {"content-type": "application/pdf"},
                            upsert=True
                        )
                        url_diploma = supabase.storage.from_("documentos").get_public_url(nombre_archivo)
                        supabase.table("diplomas").insert({
                            "participante_id": row["id"],
                            "grupo_id": grupo_id,
                            "url": url_diploma,
                            "fecha_subida": fecha_subida.isoformat(),
                            "archivo_nombre": nombre_archivo
                        }).execute()
                        st.success("✅ Diploma subido correctamente.")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al subir el diploma: {e}")

    # =========================
    # Vista consolidada de diplomas (solo admin)
    # =========================
    if session_state.role == "admin":
        st.divider()
        st.markdown("## 📊 Diplomas por grupo")
        try:
            diplomas_all = supabase.table("diplomas").select("*").execute().data or []
            df_diplomas = pd.DataFrame(diplomas_all)

            if not df_diplomas.empty:
                df_diplomas["Grupo"] = df_diplomas["grupo_id"].map(grupos_nombre_por_id)
                df_diplomas["Fecha"] = pd.to_datetime(df_diplomas["fecha_subida"]).dt.date
                df_diplomas["Diploma"] = df_diplomas.apply(
                    lambda x: f"[Abrir PDF]({x['url']['publicUrl']})" if x.get("url") else "—", axis=1
                )

                # Filtrado y descarga CSV
                grupo_filter = st.selectbox("Filtrar por grupo", ["-- Todos --"] + list(grupos_nombre_por_id.values()))
                if grupo_filter != "-- Todos --":
                    df_diplomas = df_diplomas[df_diplomas["Grupo"] == grupo_filter]

                st.download_button(
                    "⬇️ Descargar listado en CSV",
                    data=df_diplomas.to_csv(index=False).encode("utf-8"),
                    file_name="diplomas.csv",
                    mime="text/csv"
                )

                st.dataframe(df_diplomas[["participante_id", "Grupo", "Fecha", "Diploma"]])
            else:
                st.info("ℹ️ No hay diplomas registrados aún.")
        except Exception as e:
            st.error(f"❌ Error al cargar diplomas globales: {e}")
