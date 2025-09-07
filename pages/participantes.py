import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from services.alumnos import alta_alumno
from utils import is_module_active

def generar_plantilla_excel(rol):
    columnas = ["nombre", "email"]
    if rol == "admin":
        columnas += ["grupo", "empresa"]
    columnas += ["apellidos", "dni", "telefono"]
    df = pd.DataFrame(columns=columnas)
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer

def main(supabase, session_state):
    st.markdown("## 🧑‍🎓 Participantes")
    st.caption("Gestión de participantes y vinculación con empresas y grupos.")
    st.divider()

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    empresa_id = session_state.user.get("empresa_id")

    # Cargar empresas y grupos
    try:
        empresas_res = supabase.table("empresas").select("id,nombre").eq("id", empresa_id).execute() if session_state.role == "gestor" else supabase.table("empresas").select("id,nombre").execute()
        empresas_dict = {e["nombre"]: e["id"] for e in (empresas_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las empresas: {e}")
        empresas_dict = {}

    try:
        grupos_res = supabase.table("grupos").select("id,codigo_grupo").eq("empresa_id", empresa_id).execute() if session_state.role == "gestor" else supabase.table("grupos").select("id,codigo_grupo").execute()
        grupos_dict = {g["codigo_grupo"]: g["id"] for g in (grupos_res.data or [])}
        grupos_nombre_por_id = {g["id"]: g["codigo_grupo"] for g in (grupos_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los grupos: {e}")
        grupos_dict = {}
        grupos_nombre_por_id = {}

    # Cargar participantes
    try:
        part_res = supabase.table("participantes").select("*").eq("empresa_id", empresa_id).execute() if session_state.role == "gestor" else supabase.table("participantes").select("*").execute()
        df_part = pd.DataFrame(part_res.data or [])
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los participantes: {e}")
        df_part = pd.DataFrame()

    # Alta individual
    puede_crear = (
        session_state.role == "admin" or
        (session_state.role == "gestor" and empresa_id and is_module_active(session_state.user.get("empresa", {}), session_state.user.get("empresa_crm", {}), "formacion", datetime.today().date(), "gestor"))
    )

    if puede_crear:
        st.markdown("### ➕ Añadir Participante")
        with st.form("crear_participante", clear_on_submit=True):
            nombre = st.text_input("Nombre *")
            apellidos = st.text_input("Apellidos")
            dni = st.text_input("DNI/NIF")
            email = st.text_input("Email *")
            telefono = st.text_input("Teléfono")

            if session_state.role == "admin":
                empresa_busqueda = st.text_input("🔍 Buscar empresa por nombre")
                empresas_filtradas = [nombre for nombre in empresas_dict if empresa_busqueda.lower() in nombre.lower()] if empresa_busqueda else list(empresas_dict.keys())
                empresa_sel = st.selectbox("Empresa", sorted(empresas_filtradas)) if empresas_filtradas else None
                empresa_id_new = empresas_dict.get(empresa_sel) if empresa_sel else None

                grupo_sel = st.selectbox("Grupo", sorted(grupos_dict.keys()))
                grupo_id_new = grupos_dict.get(grupo_sel)
            else:
                empresa_id_new = empresa_id
                grupo_id_new = None  # Se asigna después en grupos.py

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
                    empresa_id=empresa_id_new,
                    grupo_id=grupo_id_new
                )
                if creado:
                    st.success("✅ Participante creado correctamente.")
                    st.rerun()

    # Importación masiva
    if puede_crear:
        st.markdown("### 📥 Importar participantes desde Excel")
        st.info("""
**Instrucciones:**
- Formato `.xlsx`
- Campos obligatorios: `nombre`, `email`
- Opcionales: `apellidos`, `dni`, `telefono`
- Solo administradores pueden incluir `grupo` y `empresa`
""")
        plantilla = generar_plantilla_excel(session_state.role)
        st.download_button("⬇️ Descargar plantilla Excel", data=plantilla, file_name="plantilla_participantes.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        archivo_excel = st.file_uploader("Selecciona archivo Excel", type=["xlsx"])
        importar = st.button("📤 Importar participantes")

        if importar and archivo_excel:
            try:
                df_import = pd.read_excel(archivo_excel)
                if not {"nombre", "email"}.issubset(df_import.columns):
                    st.error("❌ El archivo debe contener al menos 'nombre' y 'email'.")
                else:
                    total = len(df_import)
                    creados = 0
                    errores = []

                    for _, fila in df_import.iterrows():
                        nombre = str(fila.get("nombre", "")).strip()
                        email = str(fila.get("email", "")).strip()
                        apellidos = str(fila.get("apellidos", "")).strip()
                        dni = str(fila.get("dni", "")).strip()
                        telefono = str(fila.get("telefono", "")).strip()

                        if not nombre or not email:
                            errores.append(f"Fila incompleta: {nombre} ({email})")
                            continue

                        if session_state.role == "admin":
                            grupo_nombre = str(fila.get("grupo", "")).strip()
                            grupo_id = grupos_dict.get(grupo_nombre)
                            empresa_nombre = str(fila.get("empresa", "")).strip()
                            empresa_id_import = empresas_dict.get(empresa_nombre)
                        else:
                            grupo_id = None
                            empresa_id_import = empresa_id

                        creado = alta_alumno(
                            supabase,
                            email=email,
                            password=None,
                            nombre=nombre,
                            dni=dni,
                            apellidos=apellidos,
                            telefono=telefono,
                            empresa_id=empresa_id_import,
                            grupo_id=grupo_id
                        )
                        if creado:
                            creados += 1
                        else:
                            errores.append(f"{nombre} ({email}) - Error al crear")

                    st.success(f"✅ Se han creado {creados} de {total} participantes.")
                    if errores:
                        st.warning("⚠️ Errores:")
                        for err in errores:
                            st.write(f"- {err}")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error al procesar el archivo: {e}")

    # Filtros
    st.divider()
    st.markdown("### 🔍 Filtros")
    col1, col2 = st.columns(2)
    filtro_nombre = col1.text_input("Filtrar por nombre")
    filtro_email = col2.text_input("Filtrar por email")

    if filtro_nombre:
        df_part = df_part[df_part["nombre"].str.contains(filtro_nombre, case=False, na=False)]
    if filtro_email:
        df_part = df_part[df_part["email"].str.contains(filtro_email, case=False, na=False)]

    # Vista de participantes
    if not df_part.empty:
        st.markdown("### 📋 Participantes registrados")
        st.dataframe(df_part[["nombre", "apellidos", "email", "dni", "telefono", "grupo_id", "empresa_id"]])
        st.download_button("⬇️ Descargar CSV", data=df_part.to_csv(index=False).encode("utf-8"), file_name="participantes.csv", mime="text/csv")

        st.markdown("### 🔍 Detalles individuales")
        for _, row in df_part.iterrows():
            with st.expander(f"{row.get('nombre','')} {row.get('apellidos','')}"):
                st.write(f"**Email:** {row.get('email','')}")
                st.write(f"**Teléfono:** {row.get('telefono','')}")
                st.write(f"**DNI/NIF:** {row.get('dni','')}")
                st.write(f"**Empresa ID:** {row.get('empresa_id','')}")
                st.write(f"**Grupo ID:** {row.get('grupo_id','')}")
                st.write(f"**Fecha Alta:** {row.get('fecha_alta','')}")

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
                    existe = supabase.table("diplomas").select("id,archivo_nombre").eq("participante_id", row["id"]).eq("grupo_id", grupo_id).execute()
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
                                empresa_id = row.get("empresa_id")
                                nombre_archivo = f"diploma_{row['id']}_{grupo_id}_{fecha_subida.isoformat()}.pdf"
                                ruta_archivo = f"{empresa_id}/diplomas/{nombre_archivo}"
                                file_bytes = archivo.read()

                                if existe.data:
                                    anterior = existe.data[0]
                                    supabase.storage.from_("documentos").remove([anterior["archivo_nombre"]])
                                    supabase.table("diplomas").delete().eq("id", anterior["id"]).execute()

                                supabase.storage.from_("documentos").upload(ruta_archivo, file_bytes, {"content-type": "application/pdf"})
                                url = supabase.storage.from_("documentos").get_public_url(ruta_archivo)

                                supabase.table("diplomas").insert({
                                    "participante_id": row["id"],
                                    "grupo_id": grupo_id,
                                    "empresa_id": empresa_id,
                                    "url": url,
                                    "fecha_subida": fecha_subida.isoformat(),
                                    "archivo_nombre": ruta_archivo
                                }).execute()

                                st.success("✅ Diploma subido y registrado correctamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al subir el diploma: {e}")
