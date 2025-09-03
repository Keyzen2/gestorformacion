# utils.py
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from lxml import etree

# =======================
# IMPORTAR PARTICIPANTES DESDE EXCEL
# =======================
def importar_participantes_excel(uploaded_file):
    df = pd.read_excel(uploaded_file)
    required_columns = ["nif", "nombre", "fecha_nacimiento", "sexo", "grupo_id"]
    if not all(col in df.columns for col in required_columns):
        raise ValueError(f"El Excel debe contener las columnas: {required_columns}")
    return df.to_dict(orient="records")

# =======================
# GENERAR PDF
# =======================
def generar_pdf_grupo(nombre_archivo, contenido="PDF de prueba"):
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, contenido)
    c.save()
    buffer.seek(0)
    return buffer

# =======================
# VALIDAR XML
# =======================
def validar_xml(xml_string, xsd_string):
    xml_doc = etree.fromstring(xml_string.encode())
    xsd_doc = etree.fromstring(xsd_string.encode())
    schema = etree.XMLSchema(xsd_doc)
    return schema.validate(xml_doc)

# =======================
# GENERAR XML ACCIÓN FORMATIVA
# =======================
def generar_xml_accion_formativa(accion):
    root = etree.Element("AccionFormativa")
    etree.SubElement(root, "id").text = str(accion["id"])
    etree.SubElement(root, "nombre").text = accion.get("nombre", "")
    etree.SubElement(root, "descripcion").text = accion.get("descripcion", "")
    etree.SubElement(root, "fecha_inicio").text = str(accion.get("fecha_inicio", ""))
    etree.SubElement(root, "fecha_fin").text = str(accion.get("fecha_fin", ""))
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

# =======================
# GENERAR XML INICIO GRUPO
# =======================
def generar_xml_inicio_grupo(accion, participantes):
    root = etree.Element("InicioGrupo")
    etree.SubElement(root, "accion_formativa_id").text = str(accion["id"])
    for p in participantes:
        part_elem = etree.SubElement(root, "Participante")
        etree.SubElement(part_elem, "nif").text = p["nif"]
        etree.SubElement(part_elem, "nombre").text = p["nombre"]
        etree.SubElement(part_elem, "fecha_nacimiento").text = str(p.get("fecha_nacimiento", ""))
        etree.SubElement(part_elem, "sexo").text = p.get("sexo", "")
    return BytesIO(etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8"))

# =======================
# GENERAR XML FINALIZACIÓN GRUPO
# =======================
def generar_xml_finalizacion_grupo(accion, participantes):
    root = etree.Element("FinalizacionGrupo")
    etree.SubElement(root, "accion_formativa_id").text = str(accion["id"])
    for p in participantes:
        part_elem = etree.SubElement(root, "Participante")
        etree.SubElement(part_elem, "nif").text = p["nif"]
        etree.SubElement(part_elem, "nombre").text = p["nombre"]
        etree.SubElement(part_elem, "fecha_nacimiento").text = str(p.get("fecha_nacimiento", ""))
        etree.SubElement(part_elem, "sexo").text = p.get("sexo", "")
    return BytesIO(etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8"))
