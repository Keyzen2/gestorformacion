import streamlit as st
import pandas as pd

def main(supabase, session_state):
    st.subheader("Usuarios y Empresas")

    # -----------------------
    # Ver usuarios y empresas
    # -----------------------
    if st.button("Ver Usuarios"):
        usuarios = supabase.table("usuarios").select("*").execute().data
        if usuarios:
            st.dataframe(pd.DataFrame(usuarios))
        else:
            st.info("No hay usuarios registrados")

    if st.button("Ver Empresas"):
        empresas = supabase.table("empresas").select("*").execute().data
        if empresas:
            st.dataframe(pd.DataFrame(empresas))
        else:
            st.info("No hay empresas registradas")

    # -----------------------
    # Crear Usuario
    # -----------------------
    st.markdown("### Crear Usuario")
    with st.form("crear_usuario"):
        email_new = st.text_input("Email")
        nombre_new = st.text_input("Nombre")
        rol_new = st.selectbox("Rol", ["admin", "gestor"])

        empresa_id = None
        if rol_new == "gestor":
            empresas_res = supabase.table("empresas").select("id, nombre").execute()
            empresas_dict = {e["nombre"]: e["id"] for e in empresas_res.data} if empresas_res.data else {}
            empresa_nombre = st.selectbox("Empresa asignada", options=list(empresas_dict.keys()) if empresas_dict else [])
            empresa_id = empresas_dict.get(empresa_nombre)

        submitted_user = st.form_submit_button("Crear Usuario")
        if submitted_user:
            if not email_new or not nombre_new or not rol_new:
                st.error("⚠️ Todos los campos son obligatorios")
            elif rol_new == "gestor" and not empresa_id:
                st.error("⚠️ Debes asignar una empresa al gestor")
            else:
                try:
                    # Aquí hay que poner el UID real del usuario en Supabase Auth
                    auth_id_placeholder = "uid_del_usuario_auth"
                    insert_data = {
                        "auth_id": auth_id_placeholder,
                        "email": email_new,
                        "nombre": nombre_new,
                        "rol": rol_new
                    }
                    if empresa_id:
                        insert_data["empresa_id"] = empresa_id

                    supabase.table("usuarios").insert(insert_data).execute()
                    st.success(f"Usuario '{nombre_new}' creado correctamente")
                except Exception as e:
                    st.error(f"Error al crear el usuario: {e}")

# -----------------------
# Solo ver empresa para gestores
# -----------------------
def empresas_only(supabase, session_state):
    st.subheader("Mi Empresa")
    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.info("No tienes empresa asignada")
        return
    empresa_res = supabase.table("empresas").select("*").eq("id", empresa_id).execute()
    if empresa_res.data:
        st.dataframe(pd.DataFrame(empresa_res.data))
    else:
        st.info("No hay datos de empresa")
