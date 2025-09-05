import streamlit as st
import pandas as pd
from datetime import datetime

def main(supabase, session_state):
    st.markdown("## 🧑‍💼 Comerciales")
    st.caption("Gestión de comerciales asociados a la empresa.")
    st.divider()

    rol = session_state.role
    empresa_id = session_state.user.get("empresa_id")

    if rol not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # --- Cargar comerciales ---
    try:
        if rol == "gestor":
            comerciales_res = supabase.table("comerciales").select("*").eq("empresa_id", empresa_id).execute()
        else:  # admin ve todos
            comerciales_res = supabase.table("comerciales").select("*").execute()

        comerciales = comerciales_res.data or []
        if comerciales:
            df = pd.DataFrame(comerciales)
            st.markdown("### 📋 Comerciales registrados")
            st.dataframe(df[["nombre", "email", "telefono", "activo", "fecha_alta"]])
        else:
            st.info("No hay comerciales registrados.")
    except Exception as e:
        st.error(f"❌ Error al cargar comerciales: {e}")
        comerciales = []

    st.divider()

    # --- Alta de comercial ---
    st.markdown("### ➕ Añadir nuevo comercial")
    with st.form("nuevo_comercial", clear_on_submit=True):
        nombre = st.text_input("Nombre completo *")
        email = st.text_input("Email *")
        telefono = st.text_input("Teléfono")
        crear_usuario = st.checkbox("Crear usuario con rol 'comercial' para acceso al CRM", value=False)
        enviar = st.form_submit_button("Guardar")

    if enviar:
        if not nombre or not email:
            st.warning("⚠️ Nombre y email son obligatorios.")
        else:
            try:
                usuario_id = None
                if crear_usuario:
                    # Crear usuario en tabla usuarios con rol 'comercial'
                    # Nota: Aquí asumimos que la contraseña se gestiona aparte o se envía invitación
                    usuario_res = supabase.table("usuarios").insert({
                        "email": email,
                        "nombre": nombre,
                        "rol": "comercial",
                        "empresa_id": empresa_id if rol == "gestor" else None
                    }).execute()
                    if usuario_res.data:
                        usuario_id = usuario_res.data[0]["id"]

                supabase.table("comerciales").insert({
                    "empresa_id": empresa_id if rol == "gestor" else None,
                    "usuario_id": usuario_id,
                    "nombre": nombre,
                    "email": email,
                    "telefono": telefono,
                    "fecha_alta": datetime.utcnow().isoformat(),
                    "activo": True
                }).execute()
                st.success("✅ Comercial registrado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al registrar comercial: {e}")

    st.divider()

    # --- Gestión de estado ---
    st.markdown("### ⚙️ Activar/Desactivar comercial")
    for c in comerciales:
        col1, col2, col3 = st.columns([3, 2, 2])
        col1.write(f"{c['nombre']} ({c['email']})")
        col2.write("Activo" if c["activo"] else "Inactivo")
        if col3.button("🔄 Cambiar estado", key=f"toggle_{c['id']}"):
            try:
                supabase.table("comerciales").update({
                    "activo": not c["activo"]
                }).eq("id", c["id"]).execute()
                st.success("✅ Estado actualizado.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al actualizar estado: {e}")
              
