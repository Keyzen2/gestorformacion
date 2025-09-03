# app.py
import streamlit as st
import pandas as pd
from supabase import create_client, Client
from io import BytesIO
import datetime
import os

# ---------------- Supabase config ----------------
SUPABASE_URL = "TU_SUPABASE_URL"
SUPABASE_KEY = "TU_SUPABASE_ANON_KEY"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- Utils básicos ----------------
def generar_pdf(nombre_archivo, contenido):
    from reportlab.pdfgen import canvas
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, contenido)
    c.save()
    buffer.seek(0)
    return buffer

def generar_xml(nombre_archivo, contenido):
    xml = f"<?xml version='1.0'?><document><contenido>{contenido}</contenido></document>"
    return BytesIO(xml.encode('utf-8'))

# ---------------- Autenticación ----------------
def login_usuario():
    st.session_state['user'] = None
    st.title("Login")
    usuario = st.text_input("Usuario (email/CIF)")
    contraseña = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        data = supabase.table("usuarios").select("*").eq("email", usuario).eq("contraseña", contraseña).execute()
        if data.data:
            st.session_state['user'] = data.data[0]
            st.success(f"Bienvenido {st.session_state['user']['nombre']}")
        else:
            st.error("Usuario o contraseña incorrectos")

# ---------------- Panel Admin ----------------
def panel_admin():
    st.header("Panel Admin")
    menu = st.sidebar.selectbox("Menú", ["Usuarios", "Empresas", "Acciones Formativas", "Grupos", "Histórico Documentos"])

    if menu == "Usuarios":
        st.subheader("Alta de Usuario")
        nombre = st.text_input("Nombre")
        email = st.text_input("Email / CIF")
        rol = st.selectbox("Rol", ["admin", "empresa"])
        if st.button("Crear usuario"):
            supabase.table("usuarios").insert({"nombre": nombre, "email": email, "rol": rol}).execute()
            st.success("Usuario creado")
        st.subheader("Listado de usuarios")
        df = pd.DataFrame(supabase.table("usuarios").select("*").execute().data)
        st.dataframe(df)

    elif menu == "Empresas":
        st.subheader("Alta de Empresa")
        cif = st.text_input("CIF/NIF")
        razon = st.text_input("Razón Social")
        if st.button("Crear empresa"):
            supabase.table("empresas").insert({"CIF": cif, "razon_social": razon}).execute()
            st.success("Empresa creada")
        st.subheader("Listado de empresas")
        df = pd.DataFrame(supabase.table("empresas").select("*").execute().data)
        st.dataframe(df)

    elif menu == "Acciones Formativas":
        st.subheader("Alta de Acción Formativa")
        codigo = st.text_input("Código")
        denominacion = st.text_input("Denominación")
        modalidad = st.selectbox("Modalidad", ["presencial", "teleformación"])
        if st.button("Crear acción"):
            supabase.table("acciones_formativas").insert({
                "codigo": codigo,
                "denominacion": denominacion,
                "modalidad": modalidad,
                "empresa_id": None
            }).execute()
            st.success("Acción formativa creada")
        st.subheader("Listado de acciones")
        df = pd.DataFrame(supabase.table("acciones_formativas").select("*").execute().data)
        st.dataframe(df)

    elif menu == "Grupos":
        st.subheader("Alta de Grupo")
        codigo_grupo = st.text_input("Código Grupo")
        accion_id = st.text_input("ID Acción Formativa")
        if st.button("Crear grupo"):
            supabase.table("grupos").insert({"codigo_grupo": codigo_grupo, "accion_formativa_id": accion_id}).execute()
            st.success("Grupo creado")
        st.subheader("Listado de grupos")
        df = pd.DataFrame(supabase.table("grupos").select("*").execute().data)
        st.dataframe(df)

    elif menu == "Histórico Documentos":
        st.subheader("Documentos Generados")
        docs = pd.DataFrame(supabase.table("documentos").select("*").execute().data)
        st.dataframe(docs)
        for idx, row in docs.iterrows():
            url = supabase.storage.from_("documentos").get_public_url(row["archivo_path"]).data
            st.markdown(f"[Descargar {row['tipo']}]({url})")

# ---------------- Panel Empresa ----------------
def panel_empresa():
    st.header("Panel Empresa")
    st.write(f"Bienvenido {st.session_state['user']['nombre']}")
    acciones = pd.DataFrame(supabase.table("acciones_formativas").select("*").eq("empresa_id", st.session_state['user']['empresa_id']).execute().data)
    st.subheader("Mis Acciones Formativas")
    st.dataframe(acciones)

    grupos = pd.DataFrame(supabase.table("grupos").select("*").execute().data)
    st.subheader("Mis Grupos")
    st.dataframe(grupos)

# ---------------- Main ----------------
def main():
    if "user" not in st.session_state:
        st.session_state['user'] = None

    if st.session_state['user'] is None:
        login_usuario()
    else:
        rol = st.session_state['user']['rol']
        if rol == "admin":
            panel_admin()
        else:
            panel_empresa()

if __name__ == "__main__":
    main()
