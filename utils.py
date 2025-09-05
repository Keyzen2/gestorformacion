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
    """Lee un archivo Excel y devuelve un DataFrame. Compatible con UploadedFile de Streamlit."""
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
def generar_pdf(nombre_archivo, contenido="Informe ISO 9001"):
    """
    Genera un PDF en memoria con el contenido indicado.
    Devuelve un BytesIO listo para subir a Supabase Storage o descargar.
    """
    try:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Encabezado
        c.setFont("Helvetica-Bold", 14)
        c.drawString(2 * cm, height - 2 * cm, "Informe de Auditoría ISO 9001")
        c.setFont("Helvetica", 10)
        c.drawString(2 * cm, height - 2.7 * cm, f"Generado el {datetime.today().strftime('%d/%m/%Y')}")

        # Contenido
        y = height - 4 * cm
        c.setFont("Helvetica", 10)
        for linea in contenido.split("\n"):
            if y < 2 * cm:
                c.showPage()
                y = height - 2 * cm
                c.setFont("Helvetica", 10)
            c.drawString(2 * cm, y, linea.strip())
            y -= 0.5 * cm

        # Pie de página
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(2 * cm, 1.5 * cm, "Este informe ha sido generado automáticamente por el sistema ISO 9001.")

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
    """Valida un XML contra un esquema XSD. Devuelve True/False."""
    try:
        xml_doc = etree.fromstring(xml_string.encode())
        xsd_doc = etree.fromstring(xsd_string.encode())
        schema = etree.XMLSchema(xsd_doc)
        return schema.validate(xml_doc)
    except Exception as e:
        st.error(f"❌ Error validando XML: {e}")
        return False

# =========================
# Generadores XML FUNDAE
# =========================
def generar_xml_accion_formativa(supabase, accion_id):
    """Genera un XML con datos de la acción formativa desde la BD."""
    try:
        accion = supabase.table("acciones_formativas").select("*").eq("id", accion_id).execute().data
        if not accion:
            return "<error>No se encontró la acción formativa</error>"

        accion = accion[0]
        root = ET.Element("accion_formativa")
        ET.SubElement(root, "id").text = str(accion["id"])
        ET.SubElement(root, "nombre").text = accion["nombre"]
        ET.SubElement(root, "fecha_generacion").text = datetime.today().strftime("%Y-%m-%d")

        return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    except Exception as e:
        return f"<error>Error generando XML: {e}</error>"

def generar_xml_inicio_grupo(supabase, grupo_id):
    """Genera un XML con datos de inicio de grupo."""
    try:
        grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute().data
        if not grupo:
            return "<error>No se encontró el grupo</error>"

        grupo = grupo[0]
        root = ET.Element("inicio_grupo")
        ET.SubElement(root, "id").text = str(grupo["id"])
        ET.SubElement(root, "codigo").text = grupo["codigo_grupo"]
        ET.SubElement(root, "fecha_inicio").text = str(grupo.get("fecha_inicio", ""))

        return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    except Exception as e:
        return f"<error>Error generando XML: {e}</error>"

def generar_xml_finalizacion_grupo(supabase, grupo_id):
    """Genera un XML con datos de finalización de grupo."""
    try:
        grupo = supabase.table("grupos").select("*").eq("id", grupo_id).execute().data
        if not grupo:
            return "<error>No se encontró el grupo</error>"

        grupo = grupo[0]
        root = ET.Element("finalizacion_grupo")
        ET.SubElement(root, "id").text = str(grupo["id"])
        ET.SubElement(root, "codigo").text = grupo["codigo_grupo"]
        ET.SubElement(root, "fecha_fin").text = str(grupo.get("fecha_fin", ""))

        return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    except Exception as e:
        return f"<error>Error generando XML: {e}</error>"

# =========================
# Validación de DNI/NIE/CIF español
# =========================
def validar_dni_cif(valor: str) -> bool:
    """Valida DNI, NIE o CIF español. CIF validado de forma simplificada."""
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
        # Validación simplificada de CIF
        return True

    return False
        
