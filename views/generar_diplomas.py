import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
from typing import Optional, Dict, Any
from services.participantes_service import get_participantes_service
from services.grupos_service import get_grupos_service
from services.empresas_service import get_empresas_service

# Importar reportlab
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="📜 Generador de Diplomas",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
            # Validar tamaño
            if archivo_firma.size > 2 * 1024 * 1024:  # 2MB
                st.error("Archivo muy grande. Máximo 2MB")
                return False
            
            # Construir ruta
            timestamp = int(datetime.now().timestamp())
            file_name = f"firma_{timestamp}.png"
            file_path = f"firmas_diplomas/{empresa_id}/{file_name}"
            
            # Subir a storage
            self.supabase.storage.from_("diplomas").upload(
                file_path,
                archivo_firma.getvalue(),
                {"content-type": "image/png"}
            )
            
            # Obtener URL
            url = self.supabase.storage.from_("diplomas").get_public_url(file_path)
            
            # Guardar/actualizar en BD
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
# GENERADOR DE PDF
# =========================
def generar_diploma_pdf(
    participante: Dict,
    grupo: Dict,
    accion: Dict,
    firma_url: Optional[str] = None
) -> BytesIO:
    """Genera el PDF del diploma con diseño profesional."""
    
    if not REPORTLAB_AVAILABLE:
        st.error("reportlab no está instalado. Ejecuta: pip install reportlab")
        return None
    
    buffer = BytesIO()
    
    # Crear documento A4 apaisado
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    elementos = []
    styles = getSampleStyleSheet()
    
    # ==================
    # ESTILOS PERSONALIZADOS
    # ==================
    style_titulo = ParagraphStyle(
        'Titulo',
        parent=styles['Heading1'],
        fontSize=48,
        textColor=colors.HexColor("#2c3e50"),
        alignment=TA_CENTER,
        spaceAfter=30,
        fontName='Helvetica-Bold'
    )
    
    style_accion = ParagraphStyle(
        'Accion',
        parent=styles['Heading2'],
        fontSize=24,
        textColor=colors.HexColor("#3498db"),
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica-Bold'
    )
    
    style_datos = ParagraphStyle(
        'Datos',
        parent=styles['Normal'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=12,
        fontName='Helvetica'
    )
    
    style_contenidos = ParagraphStyle(
        'Contenidos',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        leading=14,
        fontName='Helvetica'
    )
    
    # ==================
    # CARA A - DIPLOMA
    # ==================
    
    # Logo (si está disponible - usar placeholder)
    # TODO: Usar el logo de datafor que mencionas
    # elementos.append(Image("assets/logo_datafor.png", width=4*cm, height=2*cm))
    # elementos.append(Spacer(1, 1*cm))
    
    # Borde decorativo (simular recuadro corporativo)
    elementos.append(Spacer(1, 0.5*cm))
    
    # DIPLOMA
    elementos.append(Paragraph("DIPLOMA", style_titulo))
    elementos.append(Spacer(1, 1*cm))
    
    # Datos del participante
    nombre_completo = f"{participante.get('nombre', '')} {participante.get('apellidos', '')}".strip()
    tipo_doc = participante.get('tipo_documento', 'NIF')
    num_doc = participante.get('nif', 'Sin documento')
    
    texto_participante = f"<b>{nombre_completo}</b>"
    elementos.append(Paragraph(texto_participante, style_datos))
    
    texto_documento = f"con {tipo_doc} <b>{num_doc}</b>"
    elementos.append(Paragraph(texto_documento, style_datos))
    
    elementos.append(Spacer(1, 0.8*cm))
    
    # Texto introductorio
    texto_intro = "ha realizado con aprovechamiento este curso:"
    elementos.append(Paragraph(texto_intro, style_datos))
    elementos.append(Spacer(1, 0.5*cm))
    
    # Nombre de la acción formativa (destacado)
    accion_nombre = accion.get('nombre', 'Curso no especificado')
    elementos.append(Paragraph(accion_nombre, style_accion))
    elementos.append(Spacer(1, 0.8*cm))
    
    # Detalles del curso
    horas = accion.get('horas', 0) or accion.get('num_horas', 0)
    modalidad = grupo.get('modalidad', 'PRESENCIAL')
    fecha_inicio = grupo.get('fecha_inicio')
    fecha_fin = grupo.get('fecha_fin') or grupo.get('fecha_fin_prevista')
    
    if fecha_inicio:
        fecha_inicio_str = pd.to_datetime(fecha_inicio).strftime('%d/%m/%Y')
    else:
        fecha_inicio_str = "No especificada"
    
    if fecha_fin:
        fecha_fin_str = pd.to_datetime(fecha_fin).strftime('%d/%m/%Y')
    else:
        fecha_fin_str = "No especificada"
    
    texto_detalles = (
        f"con una duración de <b>{horas} horas</b>, "
        f"en modalidad <b>{modalidad}</b>, "
        f"entre el <b>{fecha_inicio_str}</b> y el <b>{fecha_fin_str}</b>."
    )
    elementos.append(Paragraph(texto_detalles, style_datos))
    
    elementos.append(Spacer(1, 1*cm))
    
    # Fecha de emisión
    fecha_emision = datetime.now().strftime('%d de %B de %Y')
    texto_firma = f"Firmado a {fecha_emision}"
    elementos.append(Paragraph(texto_firma, style_datos))
    
    elementos.append(Spacer(1, 1.5*cm))
    
    # Firma digital (si existe)
    if firma_url:
        try:
            # Crear tabla para centrar la firma
            firma_data = [[Image(firma_url, width=5*cm, height=2*cm)]]
            firma_table = Table(firma_data, colWidths=[landscape(A4)[0] - 4*cm])
            firma_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elementos.append(firma_table)
            elementos.append(Spacer(1, 0.3*cm))
            elementos.append(Paragraph("_______________________", style_datos))
            elementos.append(Paragraph("Firma del responsable", style_datos))
        except Exception as e:
            # Si falla cargar la imagen, mostrar línea de firma
            elementos.append(Paragraph("_______________________", style_datos))
            elementos.append(Paragraph("Firma del responsable", style_datos))
    else:
        elementos.append(Paragraph("_______________________", style_datos))
        elementos.append(Paragraph("Firma del responsable", style_datos))
    
    # ==================
    # CARA B - CONTENIDOS
    # ==================
    elementos.append(PageBreak())
    
    # Título de la segunda página
    style_titulo_b = ParagraphStyle(
        'TituloB',
        parent=styles['Heading1'],
        fontSize=32,
        textColor=colors.HexColor("#2c3e50"),
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica-Bold'
    )
    
    elementos.append(Paragraph("CONTENIDOS", style_titulo_b))
    elementos.append(Spacer(1, 0.5*cm))
    
    # Contenidos del curso
    contenidos = accion.get('contenidos', '')
    
    if contenidos and contenidos.strip():
        # Limpiar y formatear contenidos
        contenidos_texto = contenidos.replace('\n\n', '<br/><br/>')
        contenidos_texto = contenidos_texto.replace('\n', '<br/>')
        
        elementos.append(Paragraph(contenidos_texto, style_contenidos))
    else:
        elementos.append(Paragraph(
            "Los contenidos de este curso no han sido especificados.",
            style_contenidos
        ))
    
    # Generar PDF
    doc.build(elementos)
    buffer.seek(0)
    
    return buffer

# =========================
# GESTIÓN DE FIRMAS UI
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
            help="Imagen de tu firma digitalizada. Máximo 2MB"
        )
        
        if archivo_firma:
            st.image(archivo_firma, width=200, caption="Vista previa")
            
            if st.button("💾 Guardar firma", type="primary", use_container_width=True):
                if firmas_service.subir_firma(empresa_id, archivo_firma):
                    st.success("✅ Firma guardada correctamente")
                    st.rerun()

# =========================
# FILTROS Y SELECCIÓN
# =========================
def mostrar_filtros(
    empresas_service,
    grupos_service,
    participantes_service,
    session_state
):
    """Filtros para seleccionar participantes y grupos."""
    st.markdown("### 🔍 Filtros de Selección")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Filtro empresa
    with col1:
        if session_state.role == "admin":
            df_empresas = empresas_service.get_empresas_con_jerarquia()
            empresas_dict = {row["nombre"]: row["id"] for _, row in df_empresas.iterrows()}
            empresas_opciones = ["Todas"] + list(empresas_dict.keys())
            
            empresa_sel = st.selectbox("🏢 Empresa", empresas_opciones)
            empresa_id = empresas_dict.get(empresa_sel) if empresa_sel != "Todas" else None
        else:
            empresa_id = session_state.user.get("empresa_id")
            empresa_sel = None
    
    # Filtro año
    with col2:
        años_disponibles = list(range(datetime.now().year, datetime.now().year - 10, -1))
        año_sel = st.selectbox("📅 Año", ["Todos"] + años_disponibles)
    
    # Filtro grupo
    with col3:
        df_grupos = grupos_service.get_grupos_completos()
        
        if empresa_id:
            df_grupos = df_grupos[df_grupos["empresa_id"] == empresa_id]
        
        if año_sel != "Todos":
            df_grupos = df_grupos[df_grupos["ano_inicio"] == año_sel]
        
        grupos_dict = {row["codigo_grupo"]: row["id"] for _, row in df_grupos.iterrows()}
        grupos_opciones = ["Todos"] + list(grupos_dict.keys())
        
        grupo_sel = st.selectbox("📚 Grupo", grupos_opciones)
        grupo_id = grupos_dict.get(grupo_sel) if grupo_sel != "Todos" else None
    
    # Filtro participante
    with col4:
        participante_buscar = st.text_input("👤 Buscar participante", placeholder="Nombre o NIF")
    
    return {
        "empresa_id": empresa_id,
        "año": año_sel if año_sel != "Todos" else None,
        "grupo_id": grupo_id,
        "participante_buscar": participante_buscar
    }

# =========================
# MAIN
# =========================
def render(supabase, session_state):
    st.title("📜 Generador de Diplomas")
    st.caption("Generación profesional de diplomas PDF con previsualización")
    
    if not REPORTLAB_AVAILABLE:
        st.error("⚠️ reportlab no está instalado. Ejecuta: `pip install reportlab`")
        return
    
    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para generar diplomas")
        return
    
    # Inicializar servicios
    empresas_service = get_empresas_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)
    participantes_service = get_participantes_service(supabase, session_state)
    firmas_service = FirmasService(supabase, session_state)
    
    # Tabs principales
    tabs = st.tabs(["📜 Generar Diplomas", "✍️ Gestionar Firma"])
    
    # ==================
    # TAB 1: GENERAR
    # ==================
    with tabs[0]:
        # Filtros
        filtros = mostrar_filtros(
            empresas_service,
            grupos_service,
            participantes_service,
            session_state
        )
        
        st.divider()
        
        # Obtener participantes según filtros
        df_participantes = participantes_service.get_participantes_completos()
        
        # Aplicar filtros
        if filtros["empresa_id"]:
            df_participantes = df_participantes[df_participantes["empresa_id"] == filtros["empresa_id"]]
        
        if filtros["grupo_id"]:
            # Obtener participantes del grupo
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
        
        # Selección de participante
        participante_sel = st.selectbox(
            "Seleccionar participante",
            df_participantes.apply(
                lambda x: f"{x['nombre']} {x['apellidos']} - {x['nif']}", axis=1
            ).tolist()
        )
        
        participante_idx = df_participantes.apply(
            lambda x: f"{x['nombre']} {x['apellidos']} - {x['nif']}", axis=1
        ).tolist().index(participante_sel)
        
        participante = df_participantes.iloc[participante_idx].to_dict()
        
        # Obtener grupos del participante
        grupos_part = participantes_service.get_grupos_de_participante(participante["id"])
        
        if grupos_part.empty:
            st.warning("⚠️ Este participante no está asignado a ningún grupo")
            return
        
        # Selección de grupo
        grupo_sel = st.selectbox(
            "Seleccionar grupo/curso",
            grupos_part.apply(
                lambda x: f"{x['codigo_grupo']} - {x['accion_nombre']}", axis=1
            ).tolist()
        )
        
        grupo_idx = grupos_part.apply(
            lambda x: f"{x['codigo_grupo']} - {x['accion_nombre']}", axis=1
        ).tolist().index(grupo_sel)
        
        grupo = grupos_part.iloc[grupo_idx].to_dict()
        
        # Obtener datos completos del grupo y acción
        grupo_completo = grupos_service.supabase.table("grupos").select("*").eq(
            "id", grupo["grupo_id"]
        ).execute().data[0]
        
        accion_completa = grupos_service.supabase.table("acciones_formativas").select("*").eq(
            "id", grupo_completo["accion_formativa_id"]
        ).execute().data[0]
        
        # Obtener firma
        empresa_id = participante.get("empresa_id")
        firma = firmas_service.get_firma_empresa(empresa_id)
        firma_url = firma["archivo_url"] if firma else None
        
        st.divider()
        
        # Botones de acción
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("👁️ Previsualizar Diploma", type="secondary", use_container_width=True):
                with st.spinner("Generando previsualización..."):
                    pdf_buffer = generar_diploma_pdf(
                        participante,
                        grupo_completo,
                        accion_completa,
                        firma_url
                    )
                    
                    if pdf_buffer:
                        st.success("✅ Previsualización generada")
                        st.download_button(
                            "📥 Descargar Previsualización",
                            data=pdf_buffer,
                            file_name=f"preview_diploma_{participante['nif']}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
        
        with col2:
            if st.button("📜 Generar Diploma Final", type="primary", use_container_width=True):
                with st.spinner("Generando diploma final..."):
                    pdf_buffer = generar_diploma_pdf(
                        participante,
                        grupo_completo,
                        accion_completa,
                        firma_url
                    )
                    
                    if pdf_buffer:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"diploma_{participante['nif']}_{timestamp}.pdf"
                        
                        st.success("✅ Diploma generado correctamente")
                        st.download_button(
                            "📥 Descargar Diploma",
                            data=pdf_buffer,
                            file_name=filename,
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )
    
    # ==================
    # TAB 2: FIRMAS
    # ==================
    with tabs[1]:
        if session_state.role == "admin":
            # Admin puede gestionar firma de cualquier empresa
            df_empresas = empresas_service.get_empresas_con_jerarquia()
            empresas_dict = {row["nombre"]: row["id"] for _, row in df_empresas.iterrows()}
            
            empresa_firma_sel = st.selectbox("Seleccionar empresa", list(empresas_dict.keys()))
            empresa_firma_id = empresas_dict[empresa_firma_sel]
        else:
            # Gestor solo su empresa
            empresa_firma_id = session_state.user.get("empresa_id")
        
        mostrar_gestion_firmas(firmas_service, empresa_firma_id, session_state)
