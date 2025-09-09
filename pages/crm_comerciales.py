import streamlit as st
import pandas as pd
import re
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

    # --- Selector de empresa para admin ---
    if rol == "admin":
        try:
            empresas_res = supabase.table("empresas").select("id,nombre").execute().data or []
            empresas_dict = {e["nombre"]: e["id"] for e in empresas_res}
            empresa_sel = st.selectbox("Empresa", list(empresas_dict.keys()))
            empresa_id_sel = empresas_dict[empresa_sel]
        except Exception as e:
            st.error(f"❌ Error al cargar empresas: {e}")
            return
    else:
        empresa_id_sel = empresa_id

    # --- Cargar comerciales ---
    try:
        comerciales_res = supabase.table("comerciales")\
                                   .select("*")\
                                   .eq("empresa_id", empresa_id_sel)\
                                   .execute()
        comerciales = comerciales_res.data or []
        if comerciales:
            df = pd.DataFrame(comerciales)
            st.markdown("### 📋 Comerciales registrados")
            columnas = ["nombre", "email", "telefono", "activo", "fecha_alta"]
            if rol == "admin":
                columnas.insert(0, "empresa_id")
            st.dataframe(df[columnas])
        else:
            st.info("No hay comerciales registrados para esta empresa.")
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
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            st.error("⚠️ El email no tiene un formato válido.")
        else:
            # Evitar duplicados por empresa
            existe = supabase.table("comerciales")\
                             .select("id")\
                             .eq("empresa_id", empresa_id_sel)\
                             .eq("email", email)\
                             .execute().data
            if existe:
                st.error("⚠️ Ya existe un comercial con este email en esta empresa.")
            else:
                try:
                    usuario_id = None
                    if crear_usuario:
                        usuario_res = supabase.table("usuarios").insert({
                            "email": email,
                            "nombre": nombre,
                            "rol": "comercial",
                            "empresa_id": empresa_id_sel
                        }).execute()
                        if usuario_res.data:
                            usuario_id = usuario_res.data[0]["id"]

                    supabase.table("comerciales").insert({
                        "empresa_id": empresa_id_sel,
                        "usuario_id": usuario_id,
                        "nombre": nombre,
                        "email": email,
                        "telefono": telefono,
                        "fecha_alta": datetime.utcnow(),
                        "activo": True
                    }).execute()
                    st.success("✅ Comercial registrado correctamente.")
                    st.rerun()
                except Exception as e:
                    # Captura de error por violación de UNIQUE en base de datos
                    if "duplicate key value violates unique constraint" in str(e):
                        st.error("⚠️ Ya existe un comercial con este email en esta empresa.")
                    else:
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
                
