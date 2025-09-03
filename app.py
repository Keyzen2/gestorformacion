import streamlit as st
from supabase import create_client
from utils import generar_xml_accion_formativa, generar_xml_inicio_grupo, generar_xml_finalizacion_grupo, validar_xml, importar_participantes_excel, generar_pdf

# -------------------------
# Configuración de Supabase
# -------------------------
SUPABASE_URL = st.secrets["SUPABASE"]["url"]
SUPABASE_KEY = st.secrets["SUPABASE"]["anon_key"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------
# Autenticación y sesión
# -------------------------
if "rol" not in st.session_state:
    st.session_state["rol"] = "empresa"  # Por defecto, empresa; en producción usar auth real

st.title("Soy tu gestor de formación")

# -------------------------
# Panel de Administración
# -------------------------
if st.session_state["rol"] == "admin":
    st.subheader("Panel de Administración de Usuarios")
    usuarios = supabase.table("usuarios").select("*").execute().data
    st.write("Usuarios registrados:")
    for u in usuarios:
        st.write(f"{u['nombre']} ({u['email']}) - Rol: {u['rol']}")
    
    email_cambiar = st.text_input("Email del usuario a cambiar de rol")
    nuevo_rol = st.selectbox("Nuevo rol", ["empresa", "admin"])
    if st.button("Actualizar rol"):
        if email_cambiar:
            supabase.table("usuarios").update({"rol": nuevo_rol}).eq("email", email_cambiar).execute()
            st.success(f"Rol de {email_cambiar} actualizado a {nuevo_rol}")

# -------------------------
# Selección de Acción Formativa y Grupo
# -------------------------
acciones_formativas = supabase.table("acciones_formativas").select("*").execute().data
accion_formativa_id = st.selectbox("Selecciona una acción formativa", [a['id'] for a in acciones_formativas])

grupos = supabase.table("grupos").select("*").eq("accion_formativa_id", accion_formativa_id).execute().data
grupo_id = st.selectbox("Selecciona un grupo", [g['id'] for g in grupos])

# -------------------------
# Importación Masiva de Participantes
# -------------------------
archivo_excel = st.file_uploader("Sube un archivo Excel con los participantes", type=["xlsx"])
if archivo_excel:
    participantes_data = importar_participantes_excel(archivo_excel)
    for p in participantes_data:
        p["grupo_id"] = grupo_id
        supabase.table("participantes").insert(p).execute()
    st.success("Participantes importados correctamente.")

# -------------------------
# Filtrado y Paginación de Participantes
# -------------------------
pagina_actual = st.session_state.get("pagina_participantes", 0)
pagina_size = 50

filtro = st.text_input("Buscar participante por nombre o NIF")

query = supabase.table("participantes").select("*").eq("grupo_id", grupo_id)
if filtro:
    query = query.ilike("nombre", f"%{filtro}%")  # También se puede filtrar por NIF si se desea

participantes = query.range(pagina_actual*pagina_size, (pagina_actual+1)*pagina_size - 1).execute().data

st.write(f"Mostrando participantes {pagina_actual*pagina_size + 1} a {(pagina_actual+1)*pagina_size}")
for p in participantes:
    st.write(f"{p['nombre']} - {p['nif']}")

col1, col2 = st.columns(2)
if col1.button("Página anterior") and pagina_actual > 0:
    st.session_state["pagina_participantes"] = pagina_actual - 1
    st.experimental_rerun()
if col2.button("Página siguiente") and len(participantes) == pagina_size:
    st.session_state["pagina_participantes"] = pagina_actual + 1
    st.experimental_rerun()

# -------------------------
# Generación de XML y PDF
# -------------------------
if st.button("Generar XML de Acción Formativa"):
    datos_accion_formativa = supabase.table("acciones_formativas").select("*").eq("id", accion_formativa_id).execute().data[0]
    xml_bytes = generar_xml_accion_formativa(datos_accion_formativa)
    if validar_xml(xml_bytes, st.secrets["FUNDAE"]["xsd_accion_formativa"]):
        st.download_button("Descargar XML Acción Formativa", xml_bytes, "accion_formativa.xml", "application/xml")
    else:
        st.error("El XML no es válido según FUNDAE")

if st.button("Generar XML de Inicio de Grupo"):
    datos_grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute().data[0]
    xml_bytes = generar_xml_inicio_grupo(datos_grupo)
    if validar_xml(xml_bytes, st.secrets["FUNDAE"]["xsd_inicio_grupo"]):
        st.download_button("Descargar XML Inicio Grupo", xml_bytes, "inicio_grupo.xml", "application/xml")
    else:
        st.error("El XML no es válido según FUNDAE")

if st.button("Generar XML de Finalización de Grupo"):
    datos_grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute().data[0]
    xml_bytes = generar_xml_finalizacion_grupo(datos_grupo)
    if validar_xml(xml_bytes, st.secrets["FUNDAE"]["xsd_finalizacion_grupo"]):
        st.download_button("Descargar XML Finalización Grupo", xml_bytes, "finalizacion_grupo.xml", "application/xml")
    else:
        st.error("El XML no es válido según FUNDAE")

if st.button("Generar PDF del Grupo"):
    datos_grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute().data[0]
    pdf_bytes = generar_pdf(datos_grupo, participantes)
    st.download_button("Descargar PDF del Grupo", pdf_bytes, "grupo.pdf", "application/pdf")
