import xml.etree.ElementTree as ET
from fpdf import FPDF
from io import BytesIO
import pandas as pd
import xmlschema

# -------------------------
# Generación de XML
# -------------------------
def generar_xml_accion_formativa(accion_formativa):
    root = ET.Element("AccionFormativa")
    ET.SubElement(root, "CodigoAccion").text = accion_formativa['id']
    ET.SubElement(root, "Nombre").text = accion_formativa['nombre']
    ET.SubElement(root, "Descripcion").text = accion_formativa['descripcion']
    ET.SubElement(root, "FechaInicio").text = str(accion_formativa['fecha_inicio'])
    ET.SubElement(root, "FechaFin").text = str(accion_formativa['fecha_fin'])
    tree = ET.ElementTree(root)
    xml_bytes = BytesIO()
    tree.write(xml_bytes, encoding="utf-8", xml_declaration=True)
    xml_bytes.seek(0)
    return xml_bytes

def generar_xml_inicio_grupo(grupo, participantes):
    root = ET.Element("InicioGrupoFormativo")
    ET.SubElement(root, "CodigoGrupo").text = grupo['codigo_grupo']
    ET.SubElement(root, "FechaInicio").text = str(grupo['fecha_inicio'])
    ET.SubElement(root, "FechaFin").text = str(grupo['fecha_fin'])
    for p in participantes:
        part = ET.SubElement(root, "Participante")
        ET.SubElement(part, "NIF").text = p['nif']
        ET.SubElement(part, "Nombre").text = p['nombre']
        ET.SubElement(part, "FechaNacimiento").text = str(p['fecha_nacimiento'])
        ET.SubElement(part, "Sexo").text = p['sexo']
    tree = ET.ElementTree(root)
    xml_bytes = BytesIO()
    tree.write(xml_bytes, encoding="utf-8", xml_declaration=True)
    xml_bytes.seek(0)
    return xml_bytes

def generar_xml_finalizacion_grupo(grupo, participantes):
    root = ET.Element("FinalizacionGrupoFormativo")
    ET.SubElement(root, "CodigoGrupo").text = grupo['codigo_grupo']
    ET.SubElement(root, "FechaFin").text = str(grupo['fecha_fin'])
    for p in participantes:
        part = ET.SubElement(root, "Participante")
        ET.SubElement(part, "NIF").text = p['nif']
        ET.SubElement(part, "Nombre").text = p['nombre']
    tree = ET.ElementTree(root)
    xml_bytes = BytesIO()
    tree.write(xml_bytes, encoding="utf-8", xml_declaration=True)
    xml_bytes.seek(0)
    return xml_bytes

# -------------------------
# Validación XML con XSD
# -------------------------
def validar_xml(xml_bytes, xsd_path):
    schema = xmlschema.XMLSchema(xsd_path)
    xml_bytes.seek(0)
    return schema.is_valid(xml_bytes)

# -------------------------
# Generación de PDF
# -------------------------
def generar_pdf(grupo, participantes):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Grupo: {grupo['codigo_grupo']}", ln=True)
    for p in participantes:
        pdf.cell(200, 10, txt=f"{p['nombre']} - {p['nif']}", ln=True)
    pdf_bytes = BytesIO()
    pdf.output(pdf_bytes)
    pdf_bytes.seek(0)
    return pdf_bytes

# -------------------------
# Importación de Excel de participantes
# -------------------------
def importar_participantes_excel(excel_file, grupo_id):
    df = pd.read_excel(excel_file)
    participantes = []
    for _, row in df.iterrows():
        participantes.append({
            "nif": row["NIF"],
            "nombre": row["Nombre"],
            "fecha_nacimiento": row["FechaNacimiento"],
            "sexo": row["Sexo"],
            "grupo_id": grupo_id
        })
    return participantes
