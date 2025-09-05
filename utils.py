import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from lxml import etree
import re
from datetime import datetime

# =========================
# Importar participantes desde Excel
# =========================
def importar_participantes_excel(file):
    return pd.read_excel(file)

# =========================
# Generar PDF profesional
# =========================
def generar_pdf(nombre_archivo, contenido="Informe ISO 9001"):
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

# =========================
# Validación de XML con XSD
# =========================
def validar_xml(xml_string, xsd_string):
    xml_doc = etree.fromstring(xml_string.encode())
    xsd_doc = etree.fromstring(xsd_string.encode())
    schema = etree.XMLSchema(xsd_doc)
    return schema.validate(xml_doc)

# =========================
# Generadores XML FUNDAE
# =========================
def generar_xml_accion_formativa(accion_id):
    return f"<accion id='{accion_id}'/>"

def generar_xml_inicio_grupo(accion_id):
    return f"<inicio_grupo accion_id='{accion_id}'/>"

def generar_xml_finalizacion_grupo(accion_id):
    return f"<finalizacion_grupo accion_id='{accion_id}'/>"

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
        # Validación simplificada de CIF
        return True

    return False
    
