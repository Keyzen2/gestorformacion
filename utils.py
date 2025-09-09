import re
import io
from datetime import date, datetime
import requests
from lxml import etree
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from supabase import Client

# —————————————
# Roles y validaciones
# —————————————

ROLES = {"admin", "gestor", "alumno"}

def validar_cif(cif: str) -> bool:
    """Valida formato y dígito de control de un CIF español."""
    cif = (cif or "").strip().upper()
    if not re.match(r"^[A-HJNP-SUVW]\d{7}[0-9A-J]$", cif):
        return False
    # Suma pares
    even_sum = sum(int(cif[i]) for i in range(2, 8, 2))
    # Suma impares (cada dígito * 2, luego descomponer)
    odd_sum = 0
    for i in range(1, 8, 2):
        v = 2 * int(cif[i])
        odd_sum += (v // 10) + (v % 10)
    total = even_sum + odd_sum
    control = (10 - (total % 10)) % 10
    control_char = cif[-1]
    letters = "JABCDEFGHI"
    if control_char.isdigit():
        return str(control) == control_char
    return letters[control] == control_char

def validar_nif(nif: str) -> bool:
    """Valida NIF español (8 dígitos + letra)."""
    nif = (nif or "").strip().upper()
    if not re.match(r"^\d{8}[TRWAGMYFPDXBNJZSQVHLCKE]$", nif):
        return False
    letters = "TRWAGMYFPDXBNJZSQVHLCKE"
    number = int(nif[:8])
    return letters[number % 23] == nif[-1]

# —————————————
# Ajustes de la aplicación
# —————————————

def get_ajustes_app(supabase: Client) -> dict:
    """
    Recupera la configuración global (mensajes, branding, tarjetas) de la tabla ajustes_app.
    """
    res = supabase.table("ajustes_app").select("*").eq("id", 1).execute()
    return res.data[0] if res.data else {}

def update_ajustes_app(supabase: Client, nuevos: dict) -> None:
    """
    Actualiza los ajustes de la aplicación.
    """
    supabase.table("ajustes_app").update(nuevos).eq("id", 1).execute()

# —————————————
# Generación de PDF
# —————————————

def generar_pdf(buffer: io.BytesIO, text_lines: list[str]) -> io.BytesIO:
    """
    Genera un PDF con líneas de texto. Devuelve BytesIO listo para descarga.
    """
    c = canvas.Canvas(buffer, pagesize=A4)
    ancho, alto = A4
    y = alto - 50
    for line in text_lines:
        c.drawString(50, y, line)
        y -= 15
        if y < 50:
            c.showPage()
            y = alto - 50
    c.save()
    buffer.seek(0)
    return buffer

# —————————————
# Generación de XML y validación
# —————————————

def generar_xml_accion_formativa(accion: dict) -> bytes:
    """
    Crea un XML para exportar una acción formativa a Fundae.
    """
    root = etree.Element("AccionFormativa")
    for key, val in accion.items():
        child = etree.SubElement(root, key)
        child.text = str(val)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")

def generar_xml_inicio_grupo(grupo: dict, participantes: list[dict]) -> bytes:
    """
    XML de inicio de grupo incluyendo lista de participantes.
    """
    root = etree.Element("GrupoInicio")
    meta = etree.SubElement(root, "Grupo")
    for k in ["codigo_grupo", "fecha_inicio"]:
        sub = etree.SubElement(meta, k)
        sub.text = str(grupo.get(k, ""))
    lista = etree.SubElement(root, "Participantes")
    for p in participantes:
        p_el = etree.SubElement(lista, "Participante")
        etree.SubElement(p_el, "id").text = p.get("id")
        etree.SubElement(p_el, "nombre").text = p.get("nombre")
        etree.SubElement(p_el, "email").text = p.get("email")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")

def generar_xml_finalizacion_grupo(grupo: dict, resultado: dict) -> bytes:
    """
    XML de finalización de grupo con datos de aptos/no aptos.
    """
    root = etree.Element("GrupoFin")
    for key in ["codigo_grupo", "fecha_fin"]:
        el = etree.SubElement(root, key)
        el.text = str(grupo.get(key, ""))
    for key, val in resultado.items():
        el = etree.SubElement(root, key)
        el.text = str(val)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")

def validar_xml(xml_bytes: bytes, xsd_url: str) -> None:
    """
    Valida un XML contra un XSD remoto.
    Lanza excepción si no cumple.
    """
    # Cargar esquema
    r = requests.get(xsd_url)
    schema_doc = etree.XML(r.content)
    schema = etree.XMLSchema(schema_doc)
    doc = etree.fromstring(xml_bytes)
    if not schema.validate(doc):
        errs = "\n".join(str(e) for e in schema.error_log)
        raise ValueError(f"XML no válido:\n{errs}")

# —————————————
# Subida a Storage de Supabase
# —————————————

def upload_to_storage(supabase: Client,
                      bucket: str,
                      path: str,
                      file_bytes: bytes,
                      content_type: str) -> str:
    """
    Sube bytes a Supabase Storage y devuelve la URL pública.
    """
    supabase.storage.from_(bucket).upload(path, file_bytes, {"content-type": content_type})
    url_res = supabase.storage.from_(bucket).get_public_url(path)
    return url_res.data.get("publicURL", "")

# —————————————
# Módulos activos
# —————————————

def is_module_active(empresa_data: dict,
                     empresa_crm: dict,
                     module: str,
                     today: date,
                     role: str) -> bool:
    """
    Comprueba en el dict de empresa (y crm_data si CRM) si un módulo está activo y vigente.
    module in {"formacion","iso","rgpd","crm","docu_avanzada"}
    """
    if role not in ROLES:
        return False
    key_act = f"{module}_activo"
    key_i = f"{module}_inicio"
    key_f = f"{module}_fin"
    activo = empresa_data.get(key_act, False)
    inicio = empresa_data.get(key_i)
    fin = empresa_data.get(key_f)
    if not activo or not inicio:
        return False
    inicio = datetime.fromisoformat(inicio).date() if isinstance(inicio, str) else inicio
    fin = datetime.fromisoformat(fin).date() if isinstance(fin, str) else fin
    if module == "crm":
        inicio = empresa_crm.get("crm_inicio") or inicio
        fin = empresa_crm.get("crm_fin") or fin
    if not isinstance(inicio, date):
        return False
    if fin and today > fin:
        return False
    return today >= inicio

# —————————————
# Export CSV helper
# —————————————

def export_csv(df, filename="data.csv"):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("💾 Descargar CSV", data=csv, file_name=filename, mime="text/csv")
