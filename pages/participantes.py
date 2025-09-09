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
        empresas_res = (
            supabase.table("empresas")
            .select("id,nombre")
            .eq("id", empresa_id)
            .execute()
            if session_state.role == "gestor"
            else supabase.table("empresas").select("id,nombre").execute()
        )
        empresas_dict = {e["nombre"]: e["id"] for e in (empresas_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las empresas: {e}")
        empresas_dict = {}

    try:
        grupos_res = (
            supabase.table("grupos")
            .select("id,codigo_grupo")
            .eq("empresa_id", empresa_id)
            .execute()
            if session_state.role == "gestor"
            else supabase.table("grupos").select("id,codigo_grupo").execute()
        )
        grupos_dict = {g["codigo_grupo"]: g["id"] for g in (grupos_res.data or [])}
        grupos_nombre_por_id = {g["id"]: g["codigo_grupo"] for g in (grupos_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los grupos: {e}")
        grupos_dict = {}
        grupos_nombre_por_id = {}

    # Cargar participantes existentes
    try:
        part_res = (
            supabase.table("participantes")
            .select("*")
            .eq("empresa_id", empresa_id)
            .execute()
            if session_state.role == "gestor"
            else supabase.table("participantes").select("*").execute()
        )
        df_part = pd.DataFrame(part_res.data or [])
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar los participantes: {e}")
        df_part = pd.DataFrame()

    # Alta individual
    puede_crear = (
        session_state.role == "admin" or
        (session_state.role == "gestor" and empresa_id)
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
                empresas_filtradas = (
                    [n for n in empresas_dict if empresa_busqueda.lower() in n.lower()]
                    if empresa_busqueda
                    else list(empresas_dict.keys())
                )
                empresa_sel = (
                    st.selectbox("Empresa", sorted(empresas_filtradas))
                    if empresas_filtradas
                    else None
                )
                empresa_id_new = empresas_dict.get(empresa_sel) if empresa_sel else None

                grupo_sel = (
                    st.selectbox("Grupo", sorted(grupos_dict.keys()))
                    if grupos_dict
                    else None
                )
                grupo_id_new = grupos_dict.get(grupo_sel) if grupo_sel else None
            else:
                empresa_id_new = empresa_id
                if grupos_dict:
                    grupo_sel = st.selectbox("Grupo", sorted(grupos_dict.keys()))
                    grupo_id_new = grupos_dict.get(grupo_sel)
                else:
                    st.warning("⚠️ No hay grupos disponibles en tu empresa.")
                    grupo_id_new = None

            submitted = st.form_submit_button("➕ Añadir Participante")

        if submitted:
            if not nombre or not email:
                st.error("⚠️ Nombre y email son obligatorios.")
            elif not empresa_id_new:
                st.error("⚠️ Debes seleccionar una empresa.")
            elif not grupo_id_new:
                st.error("⚠️ Debes seleccionar un grupo.")
            else:
                try:
                    alta_alumno(
                        supabase,
                        email=email,
                        nombre=nombre,
                        dni=dni,
                        apellidos=apellidos,
                        telefono=telefono,
                        empresa_id=empresa_id_new,
                        grupo_id=grupo_id_new
                    )
                    st.success("✅ Participante creado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al crear participante: {e}")

    # Vista de participantes
    if not df_part.empty:
        st.markdown("### 📋 Participantes registrados")
        columnas_a_mostrar = [
            c for c in
            ["nombre", "apellidos", "email", "dni", "telefono", "grupo_id", "empresa_id"]
            if c in df_part.columns
        ]
        st.dataframe(df_part[columnas_a_mostrar])
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

                if session_state.role == "admin":
                    with st.form(f"edit_part_{row['id']}", clear_on_submit=True):
                        nuevo_nombre = st.text_input("Nombre", value=row.get("nombre", ""))
                        nuevos_apellidos = st.text_input(
                            "Apellidos", value=row.get("apellidos", "")
                        )
                        nuevo_email = st.text_input("Email", value=row.get("email", ""))
                        guardar = st.form_submit_button("💾 Guardar cambios")

                    if guardar:
                        try:
                            if nuevo_email != row.get("email", ""):
                                usuario_res = (
                                    supabase.table("usuarios")
                                    .select("auth_id")
                                    .eq("email", row.get("email", ""))
                                    .execute()
                                )
                                if usuario_res.data:
                                    auth_id = usuario_res.data[0]["auth_id"]
                                    supabase.auth.admin.update_user_by_id(
                                        auth_id, {"email": nuevo_email}
                                    )
                                    supabase.table("usuarios").update(
                                        {"email": nuevo_email}
                                    ).eq("auth_id", auth_id).execute()

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
                        diplomas_res = (
                            supabase.table("diplomas")
                            .select("*")
                            .eq("participante_id", row["id"])
                            .execute()
                        )
                        diplomas = diplomas_res.data or []
                        if diplomas:
                            for d in diplomas:
                                grupo_nombre = grupos_nombre_por_id.get(
                                    d["grupo_id"], "Grupo desconocido"
                                )
                                st.markdown(
                                    f"- 📄 [Diploma]({d['url']}) ({grupo_nombre}, {d['fecha_subida']})"
                                )
                        else:
                            st.info("Este participante no tiene diplomas registrados.")
                    except Exception as e:
                        st.error(f"❌ Error al cargar diplomas: {e}")
                        
