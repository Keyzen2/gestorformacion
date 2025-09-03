# utils.py
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from lxml import etree

# =======================
# IMPORTACIÓN DE EXCEL
# =======================
def importar_participantes_excel(file) -> pd.DataFrame:
    """
    Importa un archivo Excel y devuelve un DataFrame.
    """
    try:
        df = pd.read_excel(file)
        return df
    except Exception as e:
        raise ValueError(f"Error al leer el archivo Excel: {str(e)}")


# =======================
# GENERACIÓN DE PDF
# =======================
def generar_pdf(nombre_archivo="documento.pdf", contenido="PDF de prueba") -> BytesIO:
    """
    Genera un PDF básico y devuelve un buffer BytesIO.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, contenido)
    c.save()
    buffer.seek(0)
    return buffer


# =======================
# VALIDACIÓN DE XML
# =======================
def validar_xml(xml_string: str, xsd_string: str) -> bool:
    """
    Valida un XML contra un XSD.
    """
    try:
        xml_doc = etree.fromstring(xml_string.encode())
        xsd_doc = etree.fromstring(xsd_string.encode())
        schema = etree.XMLSchema(xsd_doc)
        return schema.validate(xml_doc)
    except Exception as e:
        raise ValueError(f"Error en validación XML: {str(e)}")


# =======================
# GENERACIÓN DE XML
# =======================
def generar_xml_accion_formativa(data: dict) -> str:
    """
    Genera XML para una acción formativa según los datos proporcionados.
    """
    root = etree.Element("AccionFormativa")
    for key, value in data.items():
        elem = etree.SubElement(root, key)
        elem.text = str(value)
    return etree.tostring(root, pretty_print=True, encoding="unicode")


def generar_xml_inicio_grupo(data: dict) -> str:
    """
    Genera XML de inicio de grupo.
    """
    root = etree.Element("InicioGrupo")
    for key, value in data.items():
        elem = etree.SubElement(root, key)
        elem.text = str(value)
    return etree.tostring(root, pretty_print=True, encoding="unicode")


def generar_xml_finalizacion_grupo(data: dict) -> str:
    """
    Genera XML de finalización de grupo.
    """
    root = etree.Element("FinalizacionGrupo")
    for key, value in data.items():
        elem = etree.SubElement(root, key)
        elem.text = str(value)
    return etree.tostring(root, pretty_print=True, encoding="unicode")
