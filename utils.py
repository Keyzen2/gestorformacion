import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from lxml import etree
import xml.etree.ElementTree as ET
import re
from datetime import datetime

# =========================
# Importar participantes desde Excel
# =========================
def importar_participantes_excel(file):
    try:
        if not file:
            st.warning("⚠️ No se ha proporcionado ningún archivo.")
            return pd.DataFrame()
        return pd.read_excel(file)
    except Exception as e:
        st.error(f"❌ Error al leer el Excel: {e}")
        return pd.DataFrame()

# =========================
# Generar PDF profesional
# =========================
def generar_pdf(nombre_archivo, contenido="Documento generado", encabezado=None):
    """
    Genera un PDF en memoria con el contenido indicado.
    Devuelve un BytesIO listo para subir o descargar.
    El encabezado es opcional.
    """
    try:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        y = height - 2 * cm

        # Encabezado opcional
        if encabezado:
            c.setFont("Helvetica-Bold", 14)
            c.drawString(2 * cm, y, encabezado)
            y -= 0.7 * cm
            c.setFont("Helvetica", 10)
            c.drawString(2 * cm, y, f"Generado el {datetime.today().strftime('%d/%m/%Y')}")
            y -= 1.3 * cm

        # Contenido
        c.setFont("Helvetica", 10)
        for linea in contenido.split("\n"):
            if y < 2 * cm:
                c.showPage()
                y = height - 2 * cm
                c.setFont("Helvetica", 10)
            c.drawString(2 * cm, y, linea.strip())
            y -= 0.5 * cm

        c.save()
        buffer.seek(0)
        return buffer
    except Exception as e:
        st.error(f"❌ Error al generar el PDF: {e}")
        return None

# =========================
# Validación de XML con XSD
# =========================
def validar_xml(xml_string, xsd_string):
    try:
        xml_doc = etree.fromstring(xml_string.encode())
        xsd_doc = etree.fromstring(xsd_string.encode())
        schema = etree.XMLSchema(xsd_doc)
        return schema.validate(xml_doc)
    except Exception as e:
        st.error(f"❌ Error validando XML: {e}")
        return False

# =========================
# Generador XML: Acción Formativa
# =========================
def generar_xml_accion_formativa(accion: dict) -> str:
    root = ET.Element("ACCIONES_FORMATIVAS")
    af = ET.SubElement(root, "ACCION_FORMATIVA")

    ET.SubElement(af, "CODIGO_ACCION").text = str(accion.get("codigo_accion", ""))
    ET.SubElement(af, "NOMBRE_ACCION").text = accion.get("nombre", "")
    ET.SubElement(af, "CODIGO_AREA_PROFESIONAL").text = accion.get("cod_area_profesional", "")
    ET.SubElement(af, "SECTOR").text = accion.get("sector") or "No especificado"
    ET.SubElement(af, "OBJETIVOS").text = accion.get("objetivos") or "No especificado"
    ET.SubElement(af, "CONTENIDOS").text = accion.get("contenidos") or "No especificado"
    ET.SubElement(af, "MODALIDAD").text = accion.get("modalidad", "")
    ET.SubElement(af, "NIVEL").text = accion.get("nivel", "")
    ET.SubElement(af, "DURACION").text = str(accion.get("num_horas") or accion.get("duracion_horas") or 0)
    ET.SubElement(af, "CERTIFICADO_PROFESIONALIDAD").text = "S" if accion.get("certificado_profesionalidad") else "N"

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")

# =========================
# Generador XML: Inicio de Grupo
# =========================
def generar_xml_inicio_grupo(grupo: dict) -> str:
    root = ET.Element("INICIO_GRUPO")
    ET.SubElement(root, "CODIGO_GRUPO").text = grupo.get("codigo_grupo", "")
    ET.SubElement(root, "CODIGO_ACCION").text = grupo.get("accion_formativa_id", "")
    ET.SubElement(root, "FECHA_INICIO").text = grupo.get("fecha_inicio", "")
    ET.SubElement(root, "AULA_VIRTUAL").text = "S" if grupo.get("aula_virtual") else "N"
    ET.SubElement(root, "LOCALIDAD").text = grupo.get("localidad") or "No especificado"
    ET.SubElement(root, "PROVINCIA").text = grupo.get("provincia") or "No especificado"
    ET.SubElement(root, "CP").text = grupo.get("cp") or "00000"
    ET.SubElement(root, "N_PARTICIPANTES_PREVISTOS").text = str(grupo.get("n_participantes_previstos") or 0)
    ET.SubElement(root, "OBSERVACIONES").text = grupo.get("observaciones") or ""

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")

# =========================
# Generador XML: Finalización de Grupo
# =========================
def generar_xml_finalizacion_grupo(grupo: dict) -> str:
    root = ET.Element("FINALIZACION_GRUPO")
    ET.SubElement(root, "CODIGO_GRUPO").text = grupo.get("codigo_grupo", "")
    ET.SubElement(root, "CODIGO_ACCION").text = grupo.get("accion_formativa_id", "")
    ET.SubElement(root, "FECHA_FIN").text = grupo.get("fecha_fin", "")
    ET.SubElement(root, "N_PARTICIPANTES_FINALIZADOS").text = str(grupo.get("n_participantes_finalizados") or 0)
    ET.SubElement(root, "N_APTOS").text = str(grupo.get("n_aptos") or 0)
    ET.SubElement(root, "N_NO_APTOS").text = str(grupo.get("n_no_aptos") or 0)
    ET.SubElement(root, "OBSERVACIONES").text = grupo.get("observaciones") or ""

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")
# =========================
# Ajustes globales de la app
# =========================
def get_ajustes_app(supabase, campos=None):
    """
    Devuelve los ajustes globales desde la tabla ajustes_app.
    Si se especifican campos, se hace un select parcial.
    """
    try:
        query = supabase.table("ajustes_app")
        if campos:
            query = query.select(",".join(campos))
        else:
            query = query.select("*")
        res = query.eq("id", 1).execute()
        return res.data[0] if res.data else {}
    except Exception as e:
        st.error(f"❌ Error al cargar ajustes de la app: {e}")
        return {}

def update_ajustes_app(supabase, data_dict):
    """
    Actualiza los ajustes globales en la tabla ajustes_app.
    """
    try:
        data_dict["updated_at"] = datetime.utcnow().isoformat()
        supabase.table("ajustes_app").update(data_dict).eq("id", 1).execute()
    except Exception as e:
        st.error(f"❌ Error al guardar ajustes de la app: {e}")

# =========================
# Renderizado seguro de textos
# =========================
def render_texto(texto: str, modo="markdown"):
    """
    Renderiza texto en Streamlit según el modo indicado.
    - markdown: usa st.markdown()
    - html: usa st.markdown(..., unsafe_allow_html=True)
    """
    if not texto:
        return
    try:
        if modo == "html":
            st.markdown(texto, unsafe_allow_html=True)
        else:
            st.markdown(texto)
    except Exception as e:
        st.error(f"❌ Error al renderizar texto: {e}")
        
# =========================
# Validación de DNI/NIE/CIF español
# =========================
def validar_dni_cif(valor: str) -> bool:
    if not valor:
        return False
    valor = valor.upper().strip()

    dni_regex = r'^\d{8}[A-Z]$'
    nie_regex = r'^[XYZ]\d{7}[A-Z]$'
    cif_regex = r'^[ABCDEFGHJKLMNPQRSUVW]\d{7}[0-9A-J]$'

    letras_dni = "TRWAGMYFPDXBNJZSQVHLCKE"

    if re.match(dni_regex, valor):
        numero = int(valor[:-1])
        letra = valor[-1]
        return letras_dni[numero % 23] == letra

    elif re.match(nie_regex, valor):
        mapa = {'X': '0', 'Y': '1', 'Z': '2'}
        numero = int(mapa[valor[0]] + valor[1:-1])
        letra = valor[-1]
        return letras_dni[numero % 23] == letra

    elif re.match(cif_regex, valor):
        return True

    return False
