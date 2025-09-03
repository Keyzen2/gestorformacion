import pandas as pd
from io import BytesIO
from lxml import etree
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ------------------------
# IMPORTAR PARTICIPANTES DESDE EXCEL CON BATCHING
# ------------------------
def importar_participantes_excel(file, batch_size=None):
    df = pd.read_excel(file)
    participantes = df.to_dict(orient="records")
    if batch_size:
        # devuelve listas por lotes
        for i in range(0, len(participantes), batch_size):
            yield participantes[i:i+batch_size]
    else:
        yield participantes

# ------------------------
# VALIDAR XML SEGÚN XSD
# ------------------------
def validar_xml(xml_bytes, xsd_path):
    try:
        xml_doc = etree.fromstring(xml_bytes)
        with open(xsd_path, 'rb') as f:
            xsd_doc = etree.XML(f.read())
        xmlschema = etree.XMLSchema(xsd_doc)
        return xmlschema.validate(xml_doc)
    except Exception as e:
        print("Error validando XML:", e)
        return False

# ------------------------
# GENERAR DOCUMENTOS PDF
# ------------------------
def generar_pdf_grupo(grupo, participantes):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(50, 800, f"Grupo: {grupo.get('codigo_grupo')}")
    y = 780
    for p in participantes:
        c.drawString(50, y, f"{p.get('nombre')} — {p.get('nif')}")
        y -= 20
        if y < 50:
            c.showPage()
            y = 800
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

# ------------------------
# GENERAR XML
# ------------------------
def generar_xml_accion_formativa(accion):
    root = etree.Element("AccionFormativa")
    for key, value in accion.items():
        etree.SubElement(root, key).text = str(value)
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

def generar_xml_inicio_grupo(grupo, participantes):
    root = etree.Element("InicioGrupo")
    g = etree.SubElement(root, "Grupo")
    for key, value in grupo.items():
        etree.SubElement(g, key).text = str(value)
    ps = etree.SubElement(root, "Participantes")
    for p in participantes:
        part = etree.SubElement(ps, "Participante")
        for key, value in p.items():
            etree.SubElement(part, key).text = str(value)
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

def generar_xml_finalizacion_grupo(grupo, participantes):
    root = etree.Element("FinalizacionGrupo")
    g = etree.SubElement(root, "Grupo")
    for key, value in grupo.items():
        etree.SubElement(g, key).text = str(value)
    ps = etree.SubElement(root, "Participantes")
    for p in participantes:
        part = etree.SubElement(ps, "Participante")
        for key, value in p.items():
            etree.SubElement(part, key).text = str(value)
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

# ------------------------
# GUARDAR DOCUMENTO EN SUPABASE STORAGE
# ------------------------
def guardar_documento_en_storage(supabase, bucket, contenido_bytes, nombre_archivo, tipo, grupo_id, accion_id, usuario_id):
    try:
        path = f"{tipo}/{nombre_archivo}"
        supabase.storage.from_(bucket).upload(path, contenido_bytes, overwrite=True)
        doc_data = {
            "archivo_path": path,
            "tipo": tipo,
            "grupo_id": grupo_id,
            "accion_id": accion_id,
            "usuario_auth_id": usuario_id
        }
        supabase.table("documentos").insert(doc_data).execute()
        # Crear signed URL 1h
        signed = supabase.storage.from_(bucket).create_signed_url(path, 3600)
        url = signed.get("signed_url") or (signed.get("data") and signed["data"].get("signed_url"))
        return url, path
    except Exception as e:
        print("Error guardando documento:", e)
        return None, None
