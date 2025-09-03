# utils.py
import xml.etree.ElementTree as ET
from io import BytesIO
from fpdf import FPDF
import pandas as pd
from datetime import datetime
import xmlschema

# GENERADORES XML/PDF (simplificados — adapta etiquetas según XSD de FUNDAE)
def generar_xml_accion_formativa(accion):
    root = ET.Element("AccionFormativa")
    ET.SubElement(root, "Id").text = str(accion.get("id"))
    ET.SubElement(root, "Nombre").text = accion.get("nombre", "")
    ET.SubElement(root, "Descripcion").text = accion.get("descripcion", "")
    ET.SubElement(root, "FechaInicio").text = str(accion.get("fecha_inicio") or "")
    ET.SubElement(root, "FechaFin").text = str(accion.get("fecha_fin") or "")
    xml_bytes = BytesIO()
    tree = ET.ElementTree(root)
    tree.write(xml_bytes, encoding="utf-8", xml_declaration=True)
    xml_bytes.seek(0)
    return xml_bytes

def generar_xml_inicio_grupo(grupo, participantes):
    root = ET.Element("InicioGrupoFormativo")
    ET.SubElement(root, "CodigoGrupo").text = grupo.get("codigo_grupo", "")
    ET.SubElement(root, "FechaInicio").text = str(grupo.get("fecha_inicio") or "")
    ET.SubElement(root, "FechaFin").text = str(grupo.get("fecha_fin") or "")
    for p in participantes:
        pe = ET.SubElement(root, "Participante")
        ET.SubElement(pe, "NIF").text = p.get("nif", "")
        ET.SubElement(pe, "Nombre").text = p.get("nombre", "")
        ET.SubElement(pe, "FechaNacimiento").text = str(p.get("fecha_nacimiento") or "")
        ET.SubElement(pe, "Sexo").text = p.get("sexo", "")
    xml_bytes = BytesIO()
    ET.ElementTree(root).write(xml_bytes, encoding="utf-8", xml_declaration=True)
    xml_bytes.seek(0)
    return xml_bytes

def generar_xml_finalizacion_grupo(grupo, participantes):
    root = ET.Element("FinalizacionGrupoFormativo")
    ET.SubElement(root, "CodigoGrupo").text = grupo.get("codigo_grupo", "")
    ET.SubElement(root, "FechaFin").text = str(grupo.get("fecha_fin") or "")
    for p in participantes:
        pe = ET.SubElement(root, "Participante")
        ET.SubElement(pe, "NIF").text = p.get("nif", "")
        ET.SubElement(pe, "Nombre").text = p.get("nombre", "")
    xml_bytes = BytesIO()
    ET.ElementTree(root).write(xml_bytes, encoding="utf-8", xml_declaration=True)
    xml_bytes.seek(0)
    return xml_bytes

def generar_pdf_grupo(grupo, participantes):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, f"Grupo: {grupo.get('codigo_grupo','')}", ln=True)
    for p in participantes:
        pdf.cell(0, 8, f"{p.get('nombre','')} - {p.get('nif','')}", ln=True)
    out = BytesIO()
    pdf.output(out)
    out.seek(0)
    return out

# Validar xml con XSD (xsd_path puede ser URL o archivo local)
def validar_xml(xml_bytes, xsd_path):
    xml_bytes.seek(0)
    schema = xmlschema.XMLSchema(xsd_path)
    return schema.is_valid(xml_bytes)

# Importar participantes desde excel
def importar_participantes_excel(file_like):
    df = pd.read_excel(file_like)
    # mapa simple: espera columnas NIF, Nombre, FechaNacimiento, Sexo
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "nif": str(r.get("NIF","")).strip(),
            "nombre": str(r.get("Nombre","")).strip(),
            "fecha_nacimiento": r.get("FechaNacimiento", None),
            "sexo": str(r.get("Sexo","") or "").strip()
        })
    return rows

# Guardar documento en Supabase Storage y registrar path (usa supabase client que se pasa)
def guardar_documento_en_storage(supabase_client, bucket_name, file_bytes_io, filename, tipo, grupo_id, accion_formativa_id, usuario_auth_id):
    """
    - file_bytes_io: BytesIO
    - returns: signed_url (temporal) y path
    """
    path = f"{usuario_auth_id}/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
    # subir: supabase.storage.from_(bucket).upload(path, file)
    # upload requiere bytes-like
    file_bytes_io.seek(0)
    data = file_bytes_io.read()
    supabase_client.storage.from_(bucket_name).upload(path, data)

    # crear signed url temporal (ej. 1 hora = 3600s)
    signed = supabase_client.storage.from_(bucket_name).create_signed_url(path, 3600)
    # El retorno depende de la versión, adaptamos
    signed_url = None
    if signed and isinstance(signed, dict):
        # versiones pueden devolver {'signedURL':...} o {'data': {'signedUrl':...}}
        if "signedURL" in signed:
            signed_url = signed["signedURL"]
        elif "data" in signed and isinstance(signed["data"], dict) and "signedUrl" in signed["data"]:
            signed_url = signed["data"]["signedUrl"]
        elif "data" in signed and isinstance(signed["data"], dict) and "signedURL" in signed["data"]:
            signed_url = signed["data"]["signedURL"]

    # registrar en tabla documentos
    supabase_client.table("documentos").insert({
        "tipo": tipo,
        "grupo_id": grupo_id,
        "accion_formativa_id": accion_formativa_id,
        "usuario_auth_id": usuario_auth_id,
        "archivo_path": path
    }).execute()

    return signed_url, path
