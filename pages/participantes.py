import streamlit as st
import pandas as pd
from datetime import datetime
from utils import validar_dni_cif

def main(supabase, session_state):
    st.subheader("🧾 Participantes")

    # =========================
    # Cargar grupos
    # =========================
    grupos_res = supabase.table("grupos").select("id, codigo_grupo, empresa_id").execute()
    grupos_dict = {g["codigo_grupo"]: g["id"] for g in grupos_res.data} if grupos_res.data else {}

    # Filtrar grupos para gestor
    if session_state.role == "gestor":
        empresa_id_usuario = session_state.user.get("empresa_id")
        grupos_dict = {codigo: gid for codigo, gid in grupos_dict.items()
                       if any(g["empresa_id"] == empresa_id_usuario and g["id"] == gid for g in grupos_res.data)}

    if not grupos_dict:
        st.warning("No hay grupos disponibles.")
        st.stop()

    # =========================
    # Cargar participantes
    # =========================
    participantes_res = supabase.table("participantes").select("*").execute()
    df_participantes = pd.DataFrame(participantes_res.data) if participantes_res.data else pd.DataFrame()

    # Filtrar participantes para gestor
    if session_state.role == "gestor":
        ids_grupos_permitidos = list(grupos_dict.values())
        df_participantes = df_participantes[df_participantes["grupo_id"].isin(ids_grupos_permitidos)]

    # =========================
    # Mostrar listado
    # =========================
    if not df_participantes.empty:
        grupo_filter = st.selectbox("Filtrar por grupo", ["Todos"] + list(grupos_dict.keys()))
        search_query = st.text_input("🔍 Buscar por nombre o DNI")

        if grupo_filter != "Todos":
            df_participantes = df_participantes[df_participantes["grupo_id"] == grupos_dict[grupo_filter]]
        if search_query:
            df_participantes = df_participantes[
                df_participantes["nombre"].str.contains(search_query, case=False, na=False) |
                df_participantes["dni"].str.contains(search_query, case=False, na=False)
            ]

        # Vista expandida por participante
        for _, row in df_participantes.iterrows():
            with st.expander(f"{row['nombre']} ({row['dni']})"):
                st.write(f"**Email:** {row.get('email', '')}")
                st.write(f"**Grupo ID:** {row.get('grupo_id', '')}")
                st.write(f"**Fecha de alta:** {row.get('created_at', '')}")

                # 🔗 Vincular con usuario
                st.markdown("#### 🔗 Vincular con usuario")
                email_usuario = st.text_input("Email del usuario", value=row.get("email", ""), key=f"email_{row['id']}")
                vincular = st.button("Vincular como alumno", key=f"vincular_{row['id']}")
                if vincular:
                    try:
                        existe = supabase.table("usuarios").select("id").eq("email", email_usuario).execute()
                        if not existe.data:
                            supabase.table("usuarios").insert({
                                "email": email_usuario,
                                "nombre": row["nombre"],
                                "rol": "alumno",
                                "dni": row["dni"]
                            }).execute()
                            st.success("✅ Usuario creado y vinculado como alumno.")
                        else:
                            st.info("ℹ️ El usuario ya existe.")
                    except Exception as e:
                        st.error(f"❌ Error al vincular: {str(e)}")

                # 📤 Subir diploma
                st.markdown("#### 📤 Subir diploma")
                grupo_id = row["grupo_id"]
                archivo = st.file_uploader("Selecciona el diploma PDF", type=["pdf"], key=f"diploma_{row['id']}")
                subir = st.button("Subir diploma", key=f"subir_{row['id']}")
                if subir and archivo:
                    try:
                        nombre_archivo = f"diplomas/{row['id']}_{grupo_id}.pdf"
                        # Simulación de URL (debes integrar con Supabase Storage si lo usas)
                        url = f"https://tudominio.supabase.co/storage/v1/object/public/{nombre_archivo}"

                        supabase.table("diplomas").insert({
                            "participante_id": row["id"],
                            "grupo_id": grupo_id,
                            "url": url,
                            "fecha_subida": datetime.utcnow().isoformat()
                        }).execute()
                        st.success("✅ Diploma subido correctamente.")
                    except Exception as e:
                        st.error(f"❌ Error al subir diploma: {str(e)}")

                # 📁 Ver diplomas existentes
                diplomas = supabase.table("diplomas").select("*").eq("participante_id", row["id"]).execute().data
                if diplomas:
                    st.markdown("#### 📁 Diplomas disponibles")
                    for d in diplomas:
                        st.markdown(f"📥 [Descargar diploma del grupo {d['grupo_id']}]({d['url']})")
                else:
                    st.info("ℹ️ No hay diplomas registrados para este participante.")

    # =========================
    # Crear nuevo participante (solo admin)
    # =========================
    if session_state.role == "admin":
        st.markdown("### ➕ Crear Participante")

        if "participante_creado" not in st.session_state:
            st.session_state.participante_creado = False

        with st.form("crear_participante", clear_on_submit=True):
            nombre = st.text_input("Nombre *")
            dni = st.text_input("DNI/NIE *")
            grupo_nombre = st.selectbox("Grupo", list(grupos_dict.keys()))
            submitted = st.form_submit_button("Crear Participante")

            if submitted and not st.session_state.participante_creado:
                if not nombre or not dni or not grupo_nombre:
                    st.error("⚠️ Todos los campos son obligatorios.")
                elif not validar_dni_cif(dni):
                    st.error("⚠️ El DNI/NIE no es válido.")
                else:
                    try:
                        existe = supabase.table("participantes") \
                            .select("id") \
                            .eq("nif", dni) \
                            .eq("grupo_id", grupos_dict[grupo_nombre]) \
                            .execute()

                        if existe.data:
                            st.error(f"⚠️ Ya existe un participante con el DNI/NIF '{dni}' en este grupo.")
                        else:
                            supabase.table("participantes").insert({
                                "nombre": nombre,
                                "nif": dni,
                                "dni": dni,
                                "grupo_id": grupos_dict[grupo_nombre]
                            }).execute()

                            st.session_state.participante_creado = True
                            st.success(f"✅ Participante '{nombre}' creado correctamente.")

                            participantes_res = supabase.table("participantes").select("*").execute()
                            df_participantes = pd.DataFrame(participantes_res.data) if participantes_res.data else pd.DataFrame()
                            st.dataframe(df_participantes)

                    except Exception as e:
                        st.error(f"❌ Error al crear el participante: {str(e)}")
    else:
        st.info("🔒 Solo los administradores pueden dar de alta participantes.")
        
