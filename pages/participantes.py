import streamlit as st
import pandas as pd
from datetime import datetime
from services.alumnos import alta_alumno

def main(supabase, session_state):
    st.markdown("## 🧑‍🎓 Participantes")
    st.caption("Gestión de participantes/alumnos y vinculación con empresas y grupos.")
    st.divider()

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # Cargar empresas y grupos
    try:
        empresa_id = session_state.user.get("empresa_id")
        if session_state.role == "gestor":
            empresas_res = supabase.table("empresas").select("id,nombre").eq("id", empresa_id).execute()
        else:
            empresas_res = supabase.table("empresas").select("id,nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in (empresas_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las empresas: {e}")
        empresas_dict = {}

    try:
        if session_state.role == "gestor":
            grupos_res = supabase.table("grupos").select("id,codigo_grupo").eq("empresa_id", empresa_id).execute()
        else:
            grupos_res = supabase.table("grupos").select("id,codigo_grupo").execute()
        grupos_dict = {g["codigo_grupo"]: g["id"] for g in (grupos_res.data or [])}
        grupos_nombre_por_id = {g["id"]: g["codigo_grupo"] for g in (grupos_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los grupos: {e}")
        grupos_dict = {}
        grupos_nombre_por_id = {}

    # Cargar participantes
    try:
        if session_state.role == "gestor":
            part_res = supabase.table("participantes").select("*").eq("empresa_id", empresa_id).execute()
        else:
            part_res = supabase.table("participantes").select("*").execute()
        df_part = pd.DataFrame(part_res.data or [])
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los participantes: {e}")
        df_part = pd.DataFrame()

    # Alta de participantes
    if session_state.role == "admin":
        st.markdown("### ➕ Añadir Participante")
        with st.form("crear_participante", clear_on_submit=True):
            nombre = st.text_input("Nombre *")
            apellidos = st.text_input("Apellidos")
            dni = st.text_input("DNI/NIF")
            email = st.text_input("Email *")
            telefono = st.text_input("Teléfono")
            empresa_sel = st.selectbox("Empresa", sorted(empresas_dict.keys()))
            grupo_sel = st.selectbox("Grupo", sorted(grupos_dict.keys()))
            submitted = st.form_submit_button("➕ Añadir Participante")

        if submitted:
            if not nombre or not email:
                st.error("⚠️ Nombre y email son obligatorios.")
            else:
                creado = alta_alumno(
                    supabase,
                    email=email,
                    password=None,
                    nombre=nombre,
                    dni=dni,
                    apellidos=apellidos,
                    telefono=telefono,
                    empresa_id=empresas_dict.get(empresa_sel),
                    grupo_id=grupos_dict.get(grupo_sel)
                )
                if creado:
                    st.success("✅ Participante creado correctamente.")
                    st.rerun()

    st.divider()
    st.markdown("### 🔍 Filtros")
    col1, col2 = st.columns(2)
    filtro_nombre = col1.text_input("Filtrar por nombre")
    filtro_email = col2.text_input("Filtrar por email")

    if filtro_nombre:
        df_part = df_part[df_part["nombre"].str.contains(filtro_nombre, case=False, na=False)]
    if filtro_email:
        df_part = df_part[df_part["email"].str.contains(filtro_email, case=False, na=False)]

    if not df_part.empty:
        st.markdown("### 📋 Participantes registrados")
        st.dataframe(df_part[["nombre", "apellidos", "email", "dni", "telefono", "grupo_id", "empresa_id"]])
        st.download_button(
            "⬇️ Descargar CSV",
            data=df_part.to_csv(index=False).encode("utf-8"),
            file_name="participantes.csv",
            mime="text/csv"
        )

        st.markdown("### 🔍 Detalles individuales")
        for _, row in df_part.iterrows():
            with st.expander(f"{row.get('nombre','')} {row.get('apellidos','')}"):
                st.write(f"**Email:** {row.get('email','')}")
                st.write(f"**Teléfono:** {row.get('telefono','')}")
                st.write(f"**DNI/NIF:** {row.get('dni','')}")
                st.write(f"**Empresa ID:** {row.get('empresa_id','')}")
                st.write(f"**Grupo ID:** {row.get('grupo_id','')}")
                st.write(f"**Fecha Alta:** {row.get('fecha_alta','')}")

                # Edición básica
                if session_state.role == "admin":
                    with st.form(f"edit_part_{row['id']}", clear_on_submit=True):
                        nuevo_nombre = st.text_input("Nombre", value=row.get("nombre", ""))
                        nuevos_apellidos = st.text_input("Apellidos", value=row.get("apellidos", ""))
                        nuevo_email = st.text_input("Email", value=row.get("email", ""))
                        guardar = st.form_submit_button("💾 Guardar cambios")
                    if guardar:
                        try:
                            if nuevo_email != row.get("email", ""):
                                usuario_res = supabase.table("usuarios").select("auth_id").eq("email", row.get("email", "")).execute()
                                if usuario_res.data:
                                    auth_id = usuario_res.data[0]["auth_id"]
                                    supabase.auth.admin.update_user_by_id(auth_id, {"email": nuevo_email})
                                    supabase.table("usuarios").update({"email": nuevo_email}).eq("auth_id", auth_id).execute()

                            supabase.table("participantes").update({
                                "nombre": nuevo_nombre,
                                "apellidos": nuevos_apellidos,
                                "email": nuevo_email
                            }).eq("id", row["id"]).execute()
                            st.success("✅ Cambios guardados.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al actualizar: {e}")

                # Diplomas del participante
                if session_state.role in ["admin", "gestor"]:
                    st.markdown("### 🏅 Diplomas del participante")
                    try:
                        diplomas_res = supabase.table("diplomas").select("*").eq("participante_id", row["id"]).execute()
                        diplomas = diplomas_res.data or []
                        if diplomas:
                            for d in diplomas:
                                grupo_nombre = grupos_nombre_por_id.get(d["grupo_id"], "Grupo desconocido")
                                st.markdown(f"- 📄 [Diploma]({d['url']}) ({grupo_nombre}, {d['fecha_subida']})")
                        else:
                            st.info("Este participante no tiene diplomas registrados.")
                    except Exception as e:
                        st.error(f"❌ Error al cargar diplomas: {e}")

                    st.markdown("### 📤 Subir nuevo diploma")
                    grupo_id = row.get("grupo_id")
                    existe = supabase.table("diplomas").select("id").eq("participante_id", row["id"]).eq("grupo_id", grupo_id).execute()
                    if existe.data:
                        st.warning("⚠️ Ya existe un diploma para este participante en este grupo. Puedes sustituirlo.")

                    with st.form(f"diploma_upload_form_{row['id']}", clear_on_submit=True):
                        archivo = st.file_uploader("Selecciona el diploma (PDF)", type=["pdf"])
                        fecha_subida = st.date_input("Fecha de subida", value=datetime.today())
                        subir = st.form_submit_button("Subir diploma")

                    if subir:
                        if not archivo:
                            st.warning("⚠️ Debes seleccionar un archivo PDF.")
                        else:
                            try:
                                nombre_archivo = f"diploma_{row['id']}_{grupo_id}_{fecha_subida.isoformat()}.pdf"
                                file_bytes = archivo.read()

                                # Eliminar anterior si existe
                                if existe.data:
                                    anterior = existe.data[0]
                                    supabase.storage.from_("diplomas").remove([anterior["archivo_nombre"]])
                                    supabase.table("diplomas").delete().eq("id", anterior["id"]).execute()

                                # Subir nuevo
                                supabase.storage.from_("diplomas").upload(nombre_archivo, file_bytes, {"content-type": "application/pdf"})
                                url = supabase.storage.from_("diplomas").get_public_url(nombre_archivo)

                                # Registrar en tabla diplomas
                                supabase.table("diplomas").insert({
                                    "participante_id": row["id"],
                                    "grupo_id": grupo_id,
                                    "url": url,
                                    "fecha_subida": fecha_subida.isoformat(),
                                    "archivo_nombre": nombre_archivo
                                }).execute()

                                st.success("✅ Diploma subido y registrado correctamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al subir el diploma: {e}")
    else:
        st.info("ℹ️ No hay participantes registrados.")
