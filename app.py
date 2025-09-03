# app.py
import streamlit as st
import pandas as pd
from supabase import create_client, Client
from io import BytesIO
from datetime import datetime
from reportlab.pdfgen import canvas
from lxml import etree

# -----------------------------
# Configuración Supabase
# -----------------------------
SUPABASE_URL = "TU_SUPABASE_URL"
SUPABASE_KEY = "TU_SUPABASE_KEY"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# Autenticación básica
# -----------------------------
st.title("Gestor de Formación")

def login():
    st.session_state['logged_in'] = False
    role = None
    email = st.text_input("Usuario (email o CIF)")
    password = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        # Supabase Auth
        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if "user" in user and user['user']:
            st.session_state['logged_in'] = True
            # Obtener rol
            result = supabase.table("usuarios").select("rol").eq("email", email).single().execute()
            role = result.data['rol'] if result.data else None
            st.session_state['role'] = role
        else:
            st.error("Usuario o contraseña incorrectos")

if 'logged_in' not in st.session_state:
    login()

# -----------------------------
# Panel principal según rol
# -----------------------------
if st.session_state.get('logged_in'):
    role = st.session_state.get('role')
    if role == "admin":
        st.subheader("Panel Admin")
        menu = st.sidebar.selectbox("Menú", ["Usuarios", "Empresas", "Acciones Formativas", "Grupos", "Participantes", "Documentos"])
        
        if menu == "Usuarios":
            st.write("Gestión de usuarios")
            usuarios = supabase.table("usuarios").select("*").execute().data
            st.dataframe(pd.DataFrame(usuarios))
        
        if menu == "Empresas":
            st.write("Gestión de empresas")
            empresas = supabase.table("empresas").select("*").execute().data
            st.dataframe(pd.DataFrame(empresas))
        
        if menu == "Acciones Formativas":
            st.write("Alta de acciones formativas")
            codigo = st.text_input("Código")
            denominacion = st.text_input("Denominación")
            if st.button("Crear acción"):
                supabase.table("acciones_formativas").insert({
                    "codigo": codigo,
                    "denominacion": denominacion
                }).execute()
                st.success("Acción creada")
        
        if menu == "Grupos":
            st.write("Alta de grupos")
        
        if menu == "Participantes":
            st.write("Importar participantes desde Excel")
            file = st.file_uploader("Sube archivo Excel", type=["xlsx"])
            if file:
                df = pd.read_excel(file)
                st.dataframe(df)
                if st.button("Guardar participantes"):
                    for _, row in df.iterrows():
                        supabase.table("participantes").insert({
                            "grupo_id": 1,  # reemplazar según tu lógica
                            "nombre": row["nombre"],
                            "nif": row["nif"]
                        }).execute()
                    st.success("Participantes guardados")
        
        if menu == "Documentos":
            st.write("Documentos generados")
            documentos = supabase.table("documentos").select("*").execute().data
            st.dataframe(pd.DataFrame(documentos))
    
    elif role == "empresa":
        st.subheader("Panel Empresa")
        menu = st.sidebar.selectbox("Menú", ["Mis Acciones", "Mis Grupos", "Mis Participantes", "Mis Documentos"])
        st.write(f"Bienvenido, empresa: {menu}")

# -----------------------------
# Funciones auxiliares
# -----------------------------
def generar_pdf(nombre_archivo="documento.pdf", texto="Ejemplo PDF"):
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, texto)
    c.save()
    buffer.seek(0)
    return buffer

def generar_xml(nombre="documento.xml"):
    root = etree.Element("root")
    child = etree.SubElement(root, "child")
    child.text = "Ejemplo XML"
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")
