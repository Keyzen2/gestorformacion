import pandas as pd
from io import BytesIO
from lxml import etree
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def generar_xml_accion_formativa(accion):
    # Genera XML según estructura Fundae
    root = etree.Element("AccionFormativa")
    for k, v in accion.items():
        etree.SubElement(root, k).text = str(v)
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

def generar_xml_inicio_grupo(grupo, participantes):
    root = etree.Element("InicioGrupo")
    for k, v in grupo.items():
        etree.SubElement(root, k).text = str(v)
    part_elem = etree.SubElement(root, "Participantes")
    for p in participantes:
        p_elem = etree.SubElement(part_elem, "Participante")
        for k, v in p.items():
            etree.SubElement(p_elem, k).text = str(v)
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

def generar_xml_finalizacion_grupo(grupo, participantes):
    root = etree.Element("FinalizacionGrupo")
    for k, v in grupo.items():
        etree.SubElement(root, k).text = str(v)
    part_elem = etree.SubElement(root, "Participantes")
    for p in participantes:
        p_elem = etree.SubElement(part_elem, "Participante")
        for k, v in p.items():
            etree.SubElement(p_elem, k).text = str(v)
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

def generar_pdf_grupo(grupo, participantes):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(50, 750, f"Grupo: {grupo.get('codigo_grupo')} - {grupo.get('nombre')}")
    y = 720
    for p in participantes:
        c.drawString(50, y, f"{p.get('nombre')} - {p.get('nif')}")
        y -= 20
        if y < 50:
            c.showPage()
            y = 750
    c.save()
    buffer.seek(0)
    return buffer.read()

def importar_participantes_excel(file):
    df = pd.read_excel(file)
    participantes = df.to_dict(orient="records")
    return participantes

def validar_xml(xml_bytes, xsd_path):
    try:
        schema_doc = etree.parse(xsd_path)
        schema = etree.XMLSchema(schema_doc)
        doc = etree.fromstring(xml_bytes)
        return schema.validate(doc)
    except Exception:
        return False

def guardar_documento_en_storage(supabase, bucket, file_bytes, filename, tipo, grupo_id, accion_id, usuario_uid):
    path = f"{tipo}/{filename}"
    supabase.storage.from_(bucket).upload(path, file_bytes, upsert=True)
    supabase.table("documentos").insert([{
        "archivo_path": path,
        "tipo": tipo,
        "grupo_id": grupo_id,
        "accion_id": accion_id,
        "usuario_auth_id": usuario_uid
    }]).execute()
    signed = supabase.storage.from_(bucket).create_signed_url(path, 3600)
    signed_url = signed.get("signedURL") or signed.get("data", {}).get("signedUrl")
    return signed_url, path
