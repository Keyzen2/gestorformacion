import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from services.alumnos import alta_alumno

def generar_plantilla_excel(rol: str) -> BytesIO:
    """
    Devuelve un BytesIO con una plantilla de columnas vacías
    según el rol (admin puede asignar empresa y grupo).
    """
    columnas = ["nombre", "email"]
    if rol == "admin":
        columnas += ["empresa", "grupo"]
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

    # Descargar plantilla de importación
    plantilla = generar_plantilla_excel(session_state.role)
    st.download_button(
        "📥 Descargar plantilla de importación",
        data=plantilla,
        file_name="plantilla_participantes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.divider()

    # Permisos: solo admin y gestor pueden ver/crear participantes
    if session_state.role not in {"admin", "gestor"}:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    empresa_id = session_state.user.get("empresa_id")

    # Cargar empresas para el select (admin puede elegir cualquiera)
    try:
        q = supabase.table("empresas").select("id,nombre")
        if session_state.role == "gestor":
            q = q.eq("id", empresa_id)
        empresas_res = q.execute()
        empresas_dict = {e["nombre"]: e["id"] for e in (empresas_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ Error al cargar empresas: {e}")
        empresas_dict = {}

    # Cargar grupos para el select
    try:
        q = supabase.table("grupos").select("id,codigo_grupo")
        if session_state.role == "gestor":
            q = q.eq("empresa_id", empresa_id)
        grupos_res = q.execute()
        grupos_dict = {g["codigo_grupo"]: g["id"] for g in (grupos_res.data or [])}
    except Exception as e:
        st.error(f"⚠️ Error al cargar grupos: {e}")
        grupos_dict = {}

    # Cargar participantes existentes
    try:
        q = supabase.table("participantes").select("*")
        if session_state.role == "gestor":
            q = q.eq("empresa_id", empresa_id)
        part_res = q.execute()
        df_part = pd.DataFrame(part_res.data or [])
    except Exception as e:
        st.error(f"⚠️ Error al cargar participantes: {e}")
        df_part = pd.DataFrame()

    # ➕ Alta individual de participante
    puede_crear = (
        session_state.role == "admin" or
        (session_state.role == "gestor" and empresa_id)
    )
    if puede_crear:
        st.markdown("### ➕ Añadir Participante")
        with st.form("form_crear_participante", clear_on_submit=True):
            nombre    = st.text_input("Nombre *")
            apellidos = st.text_input("Apellidos")
            dni       = st.text_input("DNI/NIF")
            email     = st.text_input("Email *")
            telefono  = st.text_input("Teléfono")

            if session_state.role == "admin":
                empresa_sel = st.selectbox(
                    "Empresa *",
                    sorted(empresas_dict.keys())
                )
                empresa_new = empresas_dict.get(empresa_sel)
                grupo_sel = st.selectbox(
                    "Grupo *",
                    sorted(grupos_dict.keys())
                )
                grupo_new = grupos_dict.get(grupo_sel)
            else:
                empresa_new = empresa_id
                if grupos_dict:
                    grupo_sel = st.selectbox(
                        "Grupo *",
                        sorted(grupos_dict.keys())
                    )
                    grupo_new = grupos_dict.get(grupo_sel)
                else:
                    st.warning("⚠️ No hay grupos disponibles.")
                    grupo_new = None

            submitted = st.form_submit_button("➕ Añadir Participante")

        if submitted:
            if not nombre or not email:
                st.error("⚠️ Nombre y email son obligatorios.")
            elif not empresa_new or not grupo_new:
                st.error("⚠️ Debes seleccionar empresa y grupo.")
            else:
                try:
                    alta_alumno(
                        supabase,
                        email=email,
                        nombre=nombre,
                        apellidos=apellidos,
                        dni=dni,
                        telefono=telefono,
                        empresa_id=empresa_new,
                        grupo_id=grupo_new
                    )
                    st.success("✅ Participante creado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al crear participante: {e}")

    # 📋 Tabla de participantes
    if not df_part.empty:
        st.markdown("### 📋 Participantes registrados")
        mostrar = [c for c in ["nombre","apellidos","email","dni","telefono","grupo_id","empresa_id"] if c in df_part.columns]
        st.dataframe(df_part[mostrar])

        st.download_button(
            "⬇️ Descargar CSV",
            data=df_part.to_csv(index=False).encode("utf-8"),
            file_name="participantes.csv",
            mime="text/csv"
        )

        # Detalles y edición individual
        st.markdown("### 🔍 Detalles individuales")
        grupos_nombre = {v:k for k,v in grupos_dict.items()}

        for _, row in df_part.iterrows():
            label = f"{row.get('nombre','')} {row.get('apellidos','')}"
            with st.expander(label):
                st.write(f"**Email:** {row.get('email','')}")
                st.write(f"**Teléfono:** {row.get('telefono','')}")
                st.write(f"**DNI/NIF:** {row.get('dni','')}")
                st.write(f"**Empresa ID:** {row.get('empresa_id','')}")
                grp_code = grupos_nombre.get(row.get("grupo_id"), row.get("grupo_id"))
                st.write(f"**Grupo:** {grp_code}")
                st.write(f"**Fecha alta:** {row.get('created_at','')}")

                if session_state.role in {"admin", "gestor"}:
                    with st.form(f"form_edit_part_{row['id']}", clear_on_submit=True):
                        n_nombre    = st.text_input("Nombre", value=row.get("nombre",""))
                        n_apellidos = st.text_input("Apellidos", value=row.get("apellidos",""))
                        n_email     = st.text_input("Email", value=row.get("email",""))
                        guardar = st.form_submit_button("💾 Guardar cambios")

                    if guardar:
                        try:
                            # Actualizar datos básicos del participante
                            supabase.table("participantes").update({
                                "nombre":    n_nombre,
                                "apellidos": n_apellidos,
                                "email":     n_email
                            }).eq("id", row["id"]).execute()
                            st.success("✅ Participante actualizado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al actualizar participante: {e}")

                # Diplomas del participante
                st.markdown("#### 🏅 Diplomas registrados")
                try:
                    dip_res = supabase.table("diplomas")\
                                     .select("*")\
                                     .eq("participante_id", row["id"])\
                                     .execute()
                    diplomas = dip_res.data or []
                    if diplomas:
                        for d in diplomas:
                            fecha = d.get("fecha_subida","")
                            url   = d.get("url","")
                            grp   = grupos_nombre.get(d.get("grupo_id"), d.get("grupo_id"))
                            st.markdown(f"- 📄 [Diploma]({url}) — Grupo {grp} — {fecha}")
                    else:
                        st.info("Este participante no tiene diplomas.")
                except Exception as e:
                    st.error(f"❌ Error al cargar diplomas: {e}")
    else:
        st.info("ℹ️ No hay participantes registrados.")
                        
