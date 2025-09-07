import streamlit as st
from datetime import datetime
from utils import get_ajustes_app, update_ajustes_app

def main(supabase, session_state):
    st.title("⚙️ Ajustes de la Aplicación")
    st.caption("Configura los textos, apariencia y comportamiento global de la plataforma.")

    # Solo admin puede acceder
    if session_state.role != "admin":
        st.warning("🔒 Solo el administrador global puede acceder a esta sección.")
        return

    # Obtener ajustes actuales
    ajustes = get_ajustes_app(supabase)

    # =========================
    # Branding y apariencia
    # =========================
    with st.form("branding_form"):
        st.subheader("🎨 Branding y apariencia")
        nombre_app = st.text_input("Nombre visible de la app", value=ajustes.get("nombre_app", "Gestor de Formación"))
        logo_url = st.text_input("URL del logo", value=ajustes.get("logo_url", ""))
        color_primario = st.color_picker("Color primario", value=ajustes.get("color_primario", "#4285F4"))
        color_secundario = st.color_picker("Color secundario", value=ajustes.get("color_secundario", "#5f6368"))
        guardar_branding = st.form_submit_button("💾 Guardar branding")
        if guardar_branding:
            update_ajustes_app(supabase, {
                "nombre_app": nombre_app,
                "logo_url": logo_url,
                "color_primario": color_primario,
                "color_secundario": color_secundario
            })
            st.success("✅ Branding actualizado correctamente.")
            st.rerun()

    # =========================
    # Textos de bienvenida por rol
    # =========================
    with st.form("textos_bienvenida"):
        st.subheader("📋 Textos de bienvenida por rol")
        bienvenida_admin = st.text_area("Bienvenida para admin", value=ajustes.get("bienvenida_admin", "Panel de Administración SaaS"))
        bienvenida_gestor = st.text_area("Bienvenida para gestor", value=ajustes.get("bienvenida_gestor", "Panel del Gestor"))
        bienvenida_alumno = st.text_area("Bienvenida para alumno", value=ajustes.get("bienvenida_alumno", "Área del Alumno"))
        bienvenida_comercial = st.text_area("Bienvenida para comercial", value=ajustes.get("bienvenida_comercial", "Área Comercial - CRM"))
        guardar_textos = st.form_submit_button("💾 Guardar textos")
        if guardar_textos:
            update_ajustes_app(supabase, {
                "bienvenida_admin": bienvenida_admin,
                "bienvenida_gestor": bienvenida_gestor,
                "bienvenida_alumno": bienvenida_alumno,
                "bienvenida_comercial": bienvenida_comercial
            })
            st.success("✅ Textos de bienvenida actualizados.")
            st.rerun()

    # =========================
    # Mensaje de login y footer
    # =========================
    with st.form("textos_generales"):
        st.subheader("📝 Textos generales")
        mensaje_login = st.text_area("Mensaje en pantalla de login", value=ajustes.get("mensaje_login", "Accede al gestor con tus credenciales."))
        mensaje_footer = st.text_area("Texto del pie de página", value=ajustes.get("mensaje_footer", "© 2025 Gestor de Formación · Streamlit + Supabase"))
        guardar_generales = st.form_submit_button("💾 Guardar textos generales")
        if guardar_generales:
            update_ajustes_app(supabase, {
                "mensaje_login": mensaje_login,
                "mensaje_footer": mensaje_footer
            })
            st.success("✅ Textos generales actualizados.")
            st.rerun()
          
