"""
Archivo: views/generar_diplomas.py
Sistema profesional de generación de diplomas PDF con editor interactivo
Autor: Sistema DataFor
Fecha: 2025
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
from typing import Optional, Dict
from services.participantes_service import get_participantes_service
from services.grupos_service import get_grupos_service
from services.empresas_service import get_empresas_service

# Importar reportlab
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# =========================
# SERVICIO DE FIRMAS
# =========================
class FirmasService:
    """Gestión de firmas digitales para diplomas."""
    
    def __init__(self, supabase, session_state):
        self.supabase = supabase
        self.session_state = session_state
    
    def get_firma_empresa(self, empresa_id: str) -> Optional[Dict]:
        """Obtiene la firma digital de una empresa."""
        try:
            result = self.supabase.table("empresas_firmas_diplomas").select("*").eq(
                "empresa_id", empresa_id
            ).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            st.error(f"Error obteniendo firma: {e}")
            return None
    
    def subir_firma(self, empresa_id: str, archivo_firma) -> bool:
        """Sube una nueva firma digital."""
        try:
            if archivo_firma.size > 2 * 1024 * 1024:
                st.error("Archivo muy grande. Máximo 2MB")
                return False
            
            timestamp = int(datetime.now().timestamp())
            file_name = f"firma_{timestamp}.png"
            file_path = f"firmas_diplomas/{empresa_id}/{file_name}"
            
            self.supabase.storage.from_("diplomas").upload(
                file_path,
                archivo_firma.getvalue(),
                {"content-type": "image/png"}
            )
            
            url = self.supabase.storage.from_("diplomas").get_public_url(file_path)
            
            firma_existente = self.get_firma_empresa(empresa_id)
            
            if firma_existente:
                self.supabase.table("empresas_firmas_diplomas").update({
                    "archivo_url": url,
                    "archivo_nombre": file_name,
                    "updated_at": datetime.now().isoformat()
                }).eq("empresa_id", empresa_id).execute()
            else:
                self.supabase.table("empresas_firmas_diplomas").insert({
                    "empresa_id": empresa_id,
                    "archivo_url": url,
                    "archivo_nombre": file_name
                }).execute()
            
            return True
        
        except Exception as e:
            st.error(f"Error subiendo firma: {e}")
            return False
    
    def eliminar_firma(self, empresa_id: str) -> bool:
        """Elimina la firma digital de una empresa."""
        try:
            self.supabase.table("empresas_firmas_diplomas").delete().eq(
                "empresa_id", empresa_id
            ).execute()
            return True
        except Exception as e:
            st.error(f"Error eliminando firma: {e}")
            return False

# =========================
# CANVAS PERSONALIZADO CON BORDE
# =========================
class DiplomaCanvas(canvas.Canvas):
    """Canvas personalizado con borde decorativo."""
    
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []
    
    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()
    
    def save(self):
        page_count = len(self.pages)
        for page_num, page in enumerate(self.pages):
            self.__dict__.update(page)
            if page_num == 0:
                self.draw_border()
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)
    
    def draw_border(self):
        """Dibuja borde decorativo en la primera página."""
        width, height = landscape(A4)
        
        margen = 1.5 * cm
        grosor_principal = 4
        grosor_secundario = 1
        
        # Borde exterior
        self.setStrokeColor(colors.HexColor("#2c3e50"))
        self.setLineWidth(grosor_principal)
        self.rect(margen, margen, width - 2 * margen, height - 2 * margen)
        
        # Borde interior
        self.setStrokeColor(colors.HexColor("#3498db"))
        self.setLineWidth(grosor_secundario)
        margen_interno = margen + 0.3 * cm
        self.rect(margen_interno, margen_interno, width - 2 * margen_interno, height - 2 * margen_interno)

# =========================
# GENERADOR DE PDF
# =========================
def generar_diploma_pdf(participante, grupo, accion, firma_url=None, datos_personalizados=None) -> BytesIO:
    """Genera el PDF del diploma con diseño profesional y borde decorativo."""
    if not REPORTLAB_AVAILABLE:
        st.error("reportlab no está instalado")
        return None
    
    # Aplicar datos personalizados
    if datos_personalizados:
        if 'nombre_completo' in datos_personalizados:
            partes = datos_personalizados['nombre_completo'].split(' ', 1)
            participante['nombre'] = partes[0]
            participante['apellidos'] = partes[1] if len(partes) > 1 else ''
        for key in ['tipo_documento', 'nif']:
            if key in datos_personalizados:
                participante[key] = datos_personalizados[key]
        if 'accion_nombre' in datos_personalizados:
            accion['nombre'] = datos_personalizados['accion_nombre']
        for key in ['horas', 'modalidad']:
            if key in datos_personalizados:
                if key == 'horas':
                    accion['horas'] = datos_personalizados[key]
                else:
                    grupo[key] = datos_personalizados[key]
        for key in ['fecha_inicio', 'fecha_fin']:
            if key in datos_personalizados:
                grupo[key] = datos_personalizados[key]
        if 'contenidos' in datos_personalizados:
            accion['contenidos'] = datos_personalizados['contenidos']
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            leftMargin=3*cm, rightMargin=3*cm,
                            topMargin=3*cm, bottomMargin=3*cm)
    
    elementos = []
    styles = getSampleStyleSheet()
    
    style_titulo = ParagraphStyle('Titulo', parent=styles['Heading1'],
        fontSize=48, textColor=colors.HexColor("#2c3e50"),
        alignment=TA_CENTER, spaceAfter=30, fontName='Helvetica-Bold')
    
    style_accion = ParagraphStyle('Accion', parent=styles['Heading2'],
        fontSize=24, textColor=colors.HexColor("#3498db"),
        alignment=TA_CENTER, spaceAfter=20, fontName='Helvetica-Bold')
    
    style_datos = ParagraphStyle('Datos', parent=styles['Normal'],
        fontSize=14, alignment=TA_CENTER, spaceAfter=12, fontName='Helvetica')
    
    style_contenidos = ParagraphStyle('Contenidos', parent=styles['Normal'],
        fontSize=11, alignment=TA_JUSTIFY, spaceAfter=8, leading=14, fontName='Helvetica')
    
    # CARA A
    elementos.append(Spacer(1, 0.5*cm))
    elementos.append(Paragraph("DIPLOMA", style_titulo))
    elementos.append(Spacer(1, 1*cm))
    
    nombre_completo = f"{participante.get('nombre', '')} {participante.get('apellidos', '')}".strip()
    tipo_doc = participante.get('tipo_documento', 'NIF')
    num_doc = participante.get('nif', 'Sin documento')
    
    elementos.append(Paragraph(f"<b>{nombre_completo}</b>", style_datos))
    elementos.append(Paragraph(f"con {tipo_doc} <b>{num_doc}</b>", style_datos))
    elementos.append(Spacer(1, 0.8*cm))
    elementos.append(Paragraph("ha realizado con aprovechamiento este curso:", style_datos))
    elementos.append(Spacer(1, 0.5*cm))
    
    accion_nombre = accion.get('nombre', 'Curso no especificado')
    elementos.append(Paragraph(accion_nombre, style_accion))
    elementos.append(Spacer(1, 0.8*cm))
    
    horas = accion.get('horas', 0) or accion.get('num_horas', 0)
    modalidad = grupo.get('modalidad', 'PRESENCIAL')
    fecha_inicio = grupo.get('fecha_inicio')
    fecha_fin = grupo.get('fecha_fin') or grupo.get('fecha_fin_prevista')
    
    fecha_inicio_str = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y') if fecha_inicio else "No especificada"
    fecha_fin_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y') if fecha_fin else "No especificada"
    
    texto_detalles = (
        f"con una duración de <b>{horas} horas</b>, "
        f"en modalidad <b>{modalidad}</b>, "
        f"entre el <b>{fecha_inicio_str}</b> y el <b>{fecha_fin_str}</b>."
    )
    elementos.append(Paragraph(texto_detalles, style_datos))
    elementos.append(Spacer(1, 1*cm))
    
    fecha_emision = datetime.now().strftime('%d de %B de %Y')
    elementos.append(Paragraph(f"Firmado a {fecha_emision}", style_datos))
    elementos.append(Spacer(1, 1.5*cm))
    
    if firma_url:
        try:
            from reportlab.platypus import Image as RLImage
            firma_img = RLImage(firma_url, width=5*cm, height=2*cm)
            firma_data = [[firma_img]]
            firma_table = Table(firma_data, colWidths=[landscape(A4)[0] - 6*cm])
            firma_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elementos.append(firma_table)
            elementos.append(Spacer(1, 0.3*cm))
        except:
            pass
    
    elementos.append(Paragraph("_______________________", style_datos))
    elementos.append(Paragraph("Firma del responsable", style_datos))
    
    # CARA B
    elementos.append(PageBreak())
    style_titulo_b = ParagraphStyle('TituloB', parent=styles['Heading1'],
        fontSize=32, textColor=colors.HexColor("#2c3e50"),
        alignment=TA_CENTER, spaceAfter=20, fontName='Helvetica-Bold')
    elementos.append(Paragraph("CONTENIDOS", style_titulo_b))
    elementos.append(Spacer(1, 0.5*cm))
    
    contenidos = accion.get('contenidos', '')
    if contenidos and contenidos.strip():
        contenidos_texto = contenidos.replace('\n\n', '<br/><br/>').replace('\n', '<br/>')
        elementos.append(Paragraph(contenidos_texto, style_contenidos))
    else:
        elementos.append(Paragraph("Los contenidos de este curso no han sido especificados.", style_contenidos))
    
    doc.build(elementos, canvasmaker=DiplomaCanvas)
    buffer.seek(0)
    return buffer

# =========================
# EDITOR INTERACTIVO
# =========================
def mostrar_editor_diploma(participante, grupo, accion):
    st.markdown("### ✏️ Editor de Diploma")
    st.caption("Personaliza los datos antes de generar el diploma")
    
    datos_editados = {}
    
    with st.expander("👤 Datos del Participante", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            nombre_completo = st.text_input("Nombre completo",
                value=f"{participante.get('nombre', '')} {participante.get('apellidos', '')}".strip(),
                key="edit_nombre")
            datos_editados['nombre_completo'] = nombre_completo
        with col2:
            tipo_doc = st.selectbox("Tipo documento",
                ["DNI", "NIE", "PASAPORTE"],
                index=["DNI", "NIE", "PASAPORTE"].index(participante.get('tipo_documento', 'DNI')) if participante.get('tipo_documento') in ["DNI", "NIE", "PASAPORTE"] else 0,
                key="edit_tipo_doc")
            datos_editados['tipo_documento'] = tipo_doc
            num_doc = st.text_input("Número documento",
                value=participante.get('nif', ''), key="edit_nif")
            datos_editados['nif'] = num_doc
    
    with st.expander("📚 Datos del Curso", expanded=True):
        accion_nombre = st.text_area("Nombre del curso", value=accion.get('nombre', ''), height=80, key="edit_accion")
        datos_editados['accion_nombre'] = accion_nombre
        col1, col2 = st.columns(2)
        with col1:
            horas = st.number_input("Horas del curso", min_value=1, max_value=1000,
                value=int(accion.get('horas', 0) or accion.get('num_horas', 0) or 0), key="edit_horas")
            datos_editados['horas'] = horas
        with col2:
            modalidad = st.selectbox("Modalidad", ["PRESENCIAL", "TELEFORMACION", "MIXTA"],
                index=["PRESENCIAL", "TELEFORMACION", "MIXTA"].index(grupo.get('modalidad', 'PRESENCIAL')) if grupo.get('modalidad') in ["PRESENCIAL", "TELEFORMACION", "MIXTA"] else 0,
                key="edit_modalidad")
            datos_editados['modalidad'] = modalidad
    
    with st.expander("📅 Fechas del Curso", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio_val = grupo.get('fecha_inicio')
            fecha_inicio_val = pd.to_datetime(fecha_inicio_val).date() if fecha_inicio_val else date.today()
            fecha_inicio = st.date_input("Fecha inicio", value=fecha_inicio_val, key="edit_fecha_inicio")
            datos_editados['fecha_inicio'] = fecha_inicio
        with col2:
            fecha_fin_val = grupo.get('fecha_fin') or grupo.get('fecha_fin_prevista')
            fecha_fin_val = pd.to_datetime(fecha_fin_val).date() if fecha_fin_val else date.today()
            fecha_fin = st.date_input("Fecha fin", value=fecha_fin_val, key="edit_fecha_fin")
            datos_editados['fecha_fin'] = fecha_fin
    
    with st.expander("📝 Contenidos del Curso", expanded=False):
        contenidos = st.text_area("Contenidos (aparecerán en la cara B del diploma)",
            value=accion.get('contenidos', ''), height=200, key="edit_contenidos")
        datos_editados['contenidos'] = contenidos
    
    return datos_editados

# =========================
# FILTROS
# =========================
def mostrar_filtros(empresas_service, grupos_service, participantes_service, session_state):
    st.markdown("### 🔍 Filtros de Selección")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if session_state.role == "admin":
            df_empresas = empresas_service.get_empresas_con_jerarquia()
            empresas_dict = {row["nombre"]: row["id"] for _, row in df_empresas.iterrows()}
            empresa_sel = st.selectbox("🏢 Empresa", ["Todas"] + list(empresas_dict.keys()))
            empresa_id = empresas_dict.get(empresa_sel) if empresa_sel != "Todas" else None
        else:
            empresa_id = session_state.user.get("empresa_id")
    
    with col2:
        años_disponibles = list(range(datetime.now().year, datetime.now().year - 10, -1))
        año_sel = st.selectbox("📅 Año", ["Todos"] + años_disponibles)
    
    with col3:
        df_grupos = grupos_service.get_grupos_completos()
        if empresa_id:
            df_grupos = df_grupos[df_grupos["empresa_id"] == empresa_id]
        if año_sel != "Todos":
            df_grupos = df_grupos[df_grupos["ano_inicio"] == año_sel]
        grupos_dict = {row["codigo_grupo"]: row["id"] for _, row in df_grupos.iterrows()}
        grupo_sel = st.selectbox("📚 Grupo", ["Todos"] + list(grupos_dict.keys()))
        grupo_id = grupos_dict.get(grupo_sel) if grupo_sel != "Todos" else None
    
    with col4:
        participante_buscar = st.text_input("👤 Buscar participante", placeholder="Nombre o NIF")
    
    return {
        "empresa_id": empresa_id,
        "año": año_sel if año_sel != "Todos" else None,
        "grupo_id": grupo_id,
        "participante_buscar": participante_buscar
    }

# =========================
# GESTIÓN DE FIRMAS
# =========================
def mostrar_gestion_firmas(firmas_service, empresa_id, session_state):
    """Interfaz para gestionar firma digital."""
    st.markdown("### ✍️ Firma Digital para Diplomas")
    
    firma_actual = firmas_service.get_firma_empresa(empresa_id)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if firma_actual and firma_actual.get("archivo_url"):
            st.image(firma_actual["archivo_url"], width=200, caption="Firma actual")
            
            if st.button("🗑️ Eliminar firma", use_container_width=True):
                if firmas_service.eliminar_firma(empresa_id):
                    st.success("✅ Firma eliminada")
                    st.rerun()
        else:
            st.info("📝 Sin firma configurada")
    
    with col2:
        st.markdown("**📤 Subir/Actualizar Firma**")
        archivo_firma = st.file_uploader(
            "Seleccionar imagen PNG",
            type=["png"],
            key=f"firma_{empresa_id}",
            help="Imagen de tu firma. Máximo 2MB. Fondo transparente recomendado."
        )
        if archivo_firma:
            st.image(archivo_firma, width=200, caption="Vista previa")
            if st.button("💾 Guardar firma", type="primary", use_container_width=True):
                if firmas_service.subir_firma(empresa_id, archivo_firma):
                    st.success("✅ Firma guardada correctamente")
                    st.rerun()

# =========================
# MAIN
# =========================
def render(supabase, session_state):
    st.title("📜 Generador de Diplomas Profesional")
    st.caption("Generación de diplomas PDF con editor interactivo y previsualización")
    
    if not REPORTLAB_AVAILABLE:
        st.error("⚠️ reportlab no está instalado. Ejecuta: pip install reportlab")
        return
    
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para generar diplomas")
        return
    
    empresas_service = get_empresas_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)
    participantes_service = get_participantes_service(supabase, session_state)
    firmas_service = FirmasService(supabase, session_state)
    
    tabs = st.tabs(["📜 Generar Diplomas", "✍️ Gestionar Firma"])
    
    # --- TAB 0: GENERAR DIPLOMAS ---
    with tabs[0]:
        filtros = mostrar_filtros(empresas_service, grupos_service, participantes_service, session_state)
        st.divider()
        
        df_participantes = participantes_service.get_participantes_completos()
        
        if filtros["empresa_id"]:
            df_participantes = df_participantes[df_participantes["empresa_id"] == filtros["empresa_id"]]
        if filtros["grupo_id"]:
            participantes_grupo = participantes_service.supabase.table("participantes_grupos").select(
                "participante_id"
            ).eq("grupo_id", filtros["grupo_id"]).execute()
            ids_grupo = [p["participante_id"] for p in (participantes_grupo.data or [])]
            df_participantes = df_participantes[df_participantes["id"].isin(ids_grupo)]
        if filtros["participante_buscar"]:
            buscar = filtros["participante_buscar"].lower()
            df_participantes = df_participantes[
                df_participantes["nombre"].str.lower().str.contains(buscar, na=False) |
                df_participantes["apellidos"].str.lower().str.contains(buscar, na=False) |
                df_participantes["nif"].str.lower().str.contains(buscar, na=False)
            ]
        
        if df_participantes.empty:
            st.info("📋 No se encontraron participantes con los filtros aplicados")
            return
        
        st.success(f"✅ {len(df_participantes)} participante(s) encontrado(s)")
        
        participante_sel = st.selectbox(
            "Seleccionar participante",
            df_participantes.apply(lambda x: f"{x['nombre']} {x['apellidos']} - {x['nif']}", axis=1).tolist()
        )
        participante_idx = df_participantes.apply(
            lambda x: f"{x['nombre']} {x['apellidos']} - {x['nif']}", axis=1
        ).tolist().index(participante_sel)
        participante = df_participantes.iloc[participante_idx].to_dict()
        
        grupos_part = participantes_service.get_grupos_de_participante(participante["id"])
        if grupos_part.empty:
            st.warning("⚠️ Este participante no está asignado a ningún grupo")
            return
        
        grupo_sel = st.selectbox(
            "Seleccionar grupo/curso",
            grupos_part.apply(lambda x: f"{x['codigo_grupo']} - {x['accion_nombre']}", axis=1).tolist()
        )
        grupo_idx = grupos_part.apply(
            lambda x: f"{x['codigo_grupo']} - {x['accion_nombre']}", axis=1
        ).tolist().index(grupo_sel)
        grupo = grupos_part.iloc[grupo_idx].to_dict()
        
        grupo_completo = grupos_service.supabase.table("grupos").select("*").eq(
            "id", grupo["grupo_id"]
        ).execute().data[0]
        accion_completa = grupos_service.supabase.table("acciones_formativas").select("*").eq(
            "id", grupo_completo["accion_formativa_id"]
        ).execute().data[0]
        
        empresa_id = participante.get("empresa_id")
        firma = firmas_service.get_firma_empresa(empresa_id)
        firma_url = firma["archivo_url"] if firma else None
        
        st.divider()
        datos_personalizados = mostrar_editor_diploma(participante, grupo_completo, accion_completa)
        st.divider()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("👁️ Previsualizar", type="secondary", use_container_width=True):
                with st.spinner("Generando previsualización..."):
                    pdf_buffer = generar_diploma_pdf(participante, grupo_completo, accion_completa, firma_url, datos_personalizados)
                    if pdf_buffer:
                        st.success("✅ Previsualización generada")
                        st.download_button("📥 Descargar Previsualización",
                            data=pdf_buffer, file_name=f"preview_{participante['nif']}.pdf",
                            mime="application/pdf", use_container_width=True)
        with col2:
            if st.button("🔄 Restablecer", use_container_width=True):
                for key in list(st.session_state.keys()):
                    if key.startswith('edit_'):
                        del st.session_state[key]
                st.rerun()
        with col3:
            if st.button("📜 Generar Final", type="primary", use_container_width=True):
                with st.spinner("Generando diploma..."):
                    pdf_buffer = generar_diploma_pdf(participante, grupo_completo, accion_completa, firma_url, datos_personalizados)
                    if pdf_buffer:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"diploma_{participante['nif']}_{timestamp}.pdf"
                        st.success("✅ Diploma generado")
                        st.download_button("📥 Descargar Diploma",
                            data=pdf_buffer, file_name=filename,
                            mime="application/pdf", type="primary", use_container_width=True)
    
    # --- TAB 1: GESTIONAR FIRMAS ---
    with tabs[1]:
        if session_state.role == "admin":
            df_empresas = empresas_service.get_empresas_con_jerarquia()
            empresas_dict = {row["nombre"]: row["id"] for _, row in df_empresas.iterrows()}
            empresa_firma_sel = st.selectbox("Seleccionar empresa", list(empresas_dict.keys()))
            empresa_firma_id = empresas_dict[empresa_firma_sel]
        else:
            empresa_firma_id = session_state.user.get("empresa_id")
        
        mostrar_gestion_firmas(firmas_service, empresa_firma_id, session_state)
        
        st.divider()
        with st.expander("💡 Consejos para una buena firma"):
            st.markdown("""
            **Recomendaciones para la imagen de firma:**
            1. **Formato PNG** con fondo transparente
            2. **Resolución**: mínimo 300 DPI
            3. **Tamaño recomendado**: 500x200 píxeles
            4. **Color**: Azul oscuro o negro
            5. **Peso máximo**: 2MB
            """)

