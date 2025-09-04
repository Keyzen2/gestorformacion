import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from lxml import etree
import re  # añadido para la validación de DNI/NIE/CIF

def importar_participantes_excel(file):
    return pd.read_excel(file)

def generar_pdf(nombre_archivo, contenido="PDF de prueba"):
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, contenido)
    c.save()
    buffer.seek(0)
    return buffer

def validar_xml(xml_string, xsd_string):
    xml_doc = etree.fromstring(xml_string.encode())
    xsd_doc = etree.fromstring(xsd_string.encode())
    schema = etree.XMLSchema(xsd_doc)
    return schema.validate(xml_doc)

def generar_xml_accion_formativa(accion_id):
    return f"<accion id='{accion_id}'/>"

def generar_xml_inicio_grupo(accion_id):
    return f"<inicio_grupo accion_id='{accion_id}'/>"

def generar_xml_finalizacion_grupo(accion_id):
    return f"<finalizacion_grupo accion_id='{accion_id}'/>"

# -------------------------------
# NUEVA FUNCIÓN: Validador DNI/NIE/CIF
# -------------------------------
def validar_dni_cif(valor: str) -> bool:
    """
    Valida DNI, NIE o CIF español.
    - DNI: 8 dígitos + letra
    - NIE: X/Y/Z + 7 dígitos + letra
    - CIF: letra + 7 dígitos + letra/dígito
    """
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

