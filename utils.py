import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from lxml import etree

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
