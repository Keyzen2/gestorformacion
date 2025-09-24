import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime, date
from utils import (
    generar_pdf,
    generar_xml_accion_formativa,
    generar_xml_inicio_grupo,
    generar_xml_finalizacion_grupo,
    validar_xml,
    export_csv,
    export_excel,
    # Usar las funciones mejoradas que YA EXISTEN en utils.py
    generar_xml_accion_formativa_mejorado,
    generar_xml_inicio_grupo_con_validaciones,
    generar_xml_finalizacion_grupo_mejorado,
    preparar_datos_xml_inicio_simple,
    validar_datos_grupo_fundae_completo,
    get_empresa_responsable_fundae
)
from services.data_service import get_data_service
from services.grupos_service import get_grupos_service

# =========================
# CONFIGURACIÓN DE PÁGINA MODERNA
# =========================

def apply_modern_styles():
    """Aplica estilos modernos usando las capacidades de Streamlit 1.49."""
    st.markdown("""
    <style>
    /* Estilos modernos para documentos FUNDAE */
    .main-header {
        background: linear-gradient(90deg, #2E7D32 0%, #388E3C 100%);
        padding: 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(46, 125, 50, 0.3);
    }
    
    .fundae-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #2E7D32;
        margin-bottom: 1rem;
        transition: transform 0.2s ease;
    }
    
    .fundae-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    }
    
    .validation-success {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        box-shadow: 0 4px 8px rgba(76, 175, 80, 0.3);
    }
    
    .validation-error {
        background: linear-gradient(135deg, #f44336 0%, #e53935 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        box-shadow: 0 4px 8px rgba(244, 67, 54, 0.3);
    }
    
    .validation-warning {
        background: linear-gradient(135deg, #FF9800 0%, #F57C00 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        box-shadow: 0 4px 8px rgba(255, 152, 0, 0.3);
    }
    </style>
    """, unsafe_allow_html=True)

# =========================
# FUNCIONES AUXILIARES
# =========================

def verificar_esquemas_fundae():
    """Verifica que los esquemas XSD FUNDAE estén configurados correctamente."""
    
    try:
        # Acceso a secrets
        fundae_config = st.secrets.get("FUNDAE", {})
        
        xsd_urls = {
            'accion_formativa': fundae_config.get("xsd_accion_formativa"),
            'inicio_grupo': fundae_config.get("xsd_inicio_grupo"), 
            'finalizacion_grupo': fundae_config.get("xsd_finalizacion_grupo")
        }
        
        urls_faltantes = [k for k, v in xsd_urls.items() if not v]
        
        if urls_faltantes:
            st.error("❌ **Configuración FUNDAE incompleta**")
            st.error(f"Faltan esquemas XSD: {', '.join(urls_faltantes)}")
            
            with st.expander("🔧 Cómo corregir la configuración", expanded=True):
                st.markdown("""
                **Agrega estos valores a tu `secrets.toml`:**
                
                ```toml
                [FUNDAE]
                xsd_accion_formativa = "https://empresas.fundae.es/Lanzadera/Content/schemas/2025/AAFF_Inicio.xsd"
                xsd_inicio_grupo = "https://empresas.fundae.es/Lanzadera/Content/schemas/2025/InicioGrupos_Organizadora.xsd"
                xsd_finalizacion_grupo = "https://empresas.fundae.es/Lanzadera/Content/schemas/2025/FinalizacionGrupo_Organizadora.xsd"
                ```
                """)
            
            return None
        
        st.success("✅ Esquemas FUNDAE 2025 configurados correctamente")
        return xsd_urls
        
    except Exception as e:
        st.error(f"❌ Error al verificar configuración FUNDAE: {e}")
        return None

def mostrar_metricas_sistema(df_acciones, df_grupos, user_role):
    """Muestra métricas del sistema según rol."""
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📚 Acciones Formativas", len(df_acciones) if not df_acciones.empty else 0)
    
    with col2:
        st.metric("👥 Grupos", len(df_grupos) if not df_grupos.empty else 0)
    
    with col3:
        if not df_grupos.empty:
            # Grupos activos (sin fecha de fin o fecha futura)
            hoy = date.today()
            grupos_activos = 0
            
            for _, grupo in df_grupos.iterrows():
                fecha_fin = grupo.get('fecha_fin')
                if not fecha_fin:
                    grupos_activos += 1
                else:
                    try:
                        if isinstance(fecha_fin, str):
                            fecha_fin_dt = datetime.fromisoformat(fecha_fin.replace('Z', '+00:00')).date()
                        else:
                            fecha_fin_dt = fecha_fin
                        
                        if fecha_fin_dt > hoy:
                            grupos_activos += 1
                    except:
                        grupos_activos += 1
            
            st.metric("✅ Grupos Activos", grupos_activos)
        else:
            st.metric("✅ Grupos Activos", 0)
    
    with col4:
        if user_role == "gestor" and not df_grupos.empty:
            # Contar empresas participantes
            empresas_participantes = set()
            for _, grupo in df_grupos.iterrows():
                if "empresa_nombre" in grupo and grupo["empresa_nombre"]:
                    empresas_participantes.add(grupo["empresa_nombre"])
            st.metric("🏢 Empresas Gestionadas", len(empresas_participantes))
        else:
            st.metric("📊 Documentos XML", 3)

# =========================
# FUNCIÓN PRINCIPAL
# =========================

def main(supabase, session_state):
    """Función principal con diseño moderno y esquemas FUNDAE reales."""
    
    # Aplicar estilos modernos
    apply_modern_styles()
    
    # Header principal
    st.markdown("""
    <div class="main-header">
        <h1>📄 Sistema de Documentos FUNDAE</h1>
        <p>Generación y validación de XMLs oficiales - Esquemas FUNDAE 2025</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Verificar permisos
    user_role = session_state.role
    empresa_id = session_state.user.get("empresa_id")
    
    if user_role not in ["admin", "gestor"]:
        st.error("🔒 Acceso restringido a administradores y gestores")
        return
    
    # Información contextual por rol
    if user_role == "gestor":
        st.info("💡 Como gestor, puedes generar documentos para tu empresa y empresas clientes")
    elif user_role == "admin":
        st.info("💡 Como admin, puedes generar documentos para cualquier empresa del sistema")
    
    # Verificar configuración FUNDAE
    xsd_urls = verificar_esquemas_fundae()
    if not xsd_urls:
        return
    
    # Inicializar servicios
    try:
        data_service = get_data_service(supabase, session_state)
        grupos_service = get_grupos_service(supabase, session_state)
    except Exception as e:
        st.error(f"❌ Error al inicializar servicios: {e}")
        return
    
    # Cargar datos del sistema
    with st.spinner("Cargando datos con validaciones FUNDAE..."):
        try:
            df_acciones = data_service.get_acciones_formativas()
            df_grupos = grupos_service.get_grupos_completos()
        except Exception as e:
            st.error(f"❌ Error al cargar datos: {e}")
            df_acciones = pd.DataFrame()
            df_grupos = pd.DataFrame()
    
    # Mostrar métricas del sistema
    mostrar_metricas_sistema(df_acciones, df_grupos, user_role)
    
    st.divider()
    
    # =========================
    # SELECTOR DE TIPO DE DOCUMENTO
    # =========================
    
    tipo_documento = st.selectbox(
        "🎯 Selecciona el tipo de documento a generar:",
        ["Seleccionar...", "XML Acción Formativa", "XML Inicio de Grupo", "XML Finalización de Grupo"],
        key="tipo_documento_fundae",
        help="Documentos con validaciones FUNDAE y jerarquía empresarial"
    )
    
    if tipo_documento == "Seleccionar...":
        mostrar_informacion_tipos_xml()
        
    elif tipo_documento == "XML Acción Formativa":
        procesar_xml_accion_formativa(df_acciones, supabase, session_state, xsd_urls)
        
    elif tipo_documento == "XML Inicio de Grupo":
        procesar_xml_inicio_grupo(df_grupos, supabase, session_state, xsd_urls)
        
    elif tipo_documento == "XML Finalización de Grupo":
        procesar_xml_finalizacion_grupo(df_grupos, supabase, session_state, xsd_urls)
    
    # Footer informativo
    mostrar_footer_informativo()

# =========================
# PROCESAMIENTO XML ACCIÓN FORMATIVA
# =========================

def procesar_xml_accion_formativa(df_acciones, supabase, session_state, xsd_urls):
    """Procesa XML de Acción Formativa usando funciones de utils.py"""
    
    st.markdown("### 📚 XML Acción Formativa FUNDAE")
    st.caption("Esquema: AAFF_Inicio.xsd - Declaración oficial de acciones formativas")
    
    if df_acciones.empty:
        st.warning("⚠️ No hay acciones formativas disponibles")
        st.info("💡 Crea acciones formativas desde la página correspondiente")
        return
    
    # Crear diccionario de acciones
    acciones_dict = {}
    for _, accion in df_acciones.iterrows():
        codigo = accion.get('codigo_accion', 'Sin código')
        nombre = accion.get('nombre', 'Sin nombre')
        ano = "?"
        
        if accion.get('fecha_inicio'):
            try:
                ano = datetime.fromisoformat(str(accion['fecha_inicio']).replace('Z', '+00:00')).year
            except:
                pass
        
        nombre_mostrar = f"{codigo} - {nombre} ({ano})"
        acciones_dict[nombre_mostrar] = accion.to_dict()
    
    accion_seleccionada = st.selectbox(
        "Selecciona una acción formativa:",
        ["Seleccionar..."] + list(acciones_dict.keys()),
        key="accion_xml_fundae"
    )
    
    if accion_seleccionada != "Seleccionar...":
        accion_data = acciones_dict[accion_seleccionada]
        
        # Mostrar datos de la acción
        mostrar_datos_accion(accion_data)
        
        # Botones de acción
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📄 Generar XML FUNDAE", type="primary", use_container_width=True):
                generar_y_mostrar_xml_accion(accion_data, supabase, session_state)
        
        with col2:
            if st.button("✅ Validar contra XSD", use_container_width=True):
                if xsd_urls.get('accion_formativa'):
                    validar_xml_accion_xsd(accion_data, xsd_urls['accion_formativa'], supabase, session_state)

def mostrar_datos_accion(accion_data):
    """Muestra datos de la acción formativa."""
    
    datos_fundae = [
        ["Código FUNDAE", accion_data.get('codigo_accion', 'N/A')],
        ["Denominación", accion_data.get('nombre', 'N/A')],
        ["Modalidad", accion_data.get('modalidad', 'N/A')],
        ["Duración (horas)", accion_data.get('num_horas', 0)],
        ["Área Profesional", accion_data.get('area_profesional', 'N/A')],
        ["Fecha Inicio", accion_data.get('fecha_inicio', 'N/A')],
        ["Fecha Fin", accion_data.get('fecha_fin', 'N/A')],
        ["Certificado Profesionalidad", "Sí" if accion_data.get('certificado_profesionalidad') else "No"]
    ]
    
    df_datos = pd.DataFrame(datos_fundae, columns=["Campo FUNDAE", "Valor"])
    
    st.dataframe(
        df_datos,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Campo FUNDAE": st.column_config.TextColumn("Campo FUNDAE", width="medium"),
            "Valor": st.column_config.TextColumn("Valor", width="large")
        }
    )

def generar_y_mostrar_xml_accion(accion_data, supabase, session_state):
    """Genera y muestra XML de acción usando función mejorada de utils.py"""
    
    with st.spinner("Generando XML según esquemas FUNDAE 2025..."):
        try:
            # USAR FUNCIÓN MEJORADA de utils.py
            xml_content = generar_xml_accion_formativa_mejorado(accion_data)
            
            if xml_content:
                st.success("✅ XML FUNDAE generado correctamente")
                
                # Preview del XML
                st.text_area(
                    "XML Generado (Preview):", 
                    xml_content[:1200] + "..." if len(xml_content) > 1200 else xml_content, 
                    height=200
                )
                
                # Botón de descarga
                codigo = accion_data.get('codigo_accion', 'sin_codigo')
                ano = datetime.now().year
                fecha_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"FUNDAE_AAFF_{codigo}_{ano}_{fecha_str}.xml"
                
                st.download_button(
                    label="💾 Descargar XML FUNDAE",
                    data=xml_content,
                    file_name=filename,
                    mime="application/xml",
                    use_container_width=True,
                    type="primary"
                )
            else:
                st.error("❌ Error al generar XML FUNDAE")
                
        except Exception as e:
            st.error(f"❌ Error en generación XML: {e}")

def validar_xml_accion_xsd(accion_data, xsd_url, supabase, session_state):
    """Valida XML de acción contra esquema XSD."""
    
    with st.spinner("Validando contra esquema FUNDAE oficial..."):
        try:
            # Generar XML usando función mejorada
            xml_content = generar_xml_accion_formativa_mejorado(accion_data)
            
            if xml_content:
                es_valido, errores = validar_xml(xml_content, xsd_url)
                
                if es_valido:
                    st.markdown("""
                    <div class="validation-success">
                        🎉 <strong>XML válido según esquema FUNDAE</strong><br>
                        Cumple con AAFF_Inicio.xsd oficial
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div class="validation-error">
                        ❌ <strong>XML no válido según esquema XSD</strong><br>
                        Requiere correcciones antes de enviar a FUNDAE
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander("🔍 Ver errores de validación XSD", expanded=True):
                        for i, error in enumerate(errores[:8], 1):
                            st.error(f"**Error {i}:** {error}")
                        
                        if len(errores) > 8:
                            st.warning(f"... y {len(errores) - 8} errores adicionales")
            else:
                st.error("❌ No se pudo generar XML para validación")
                
        except Exception as e:
            st.error(f"❌ Error en validación XSD: {e}")

# =========================
# PROCESAMIENTO XML INICIO GRUPO  
# =========================

def procesar_xml_inicio_grupo(df_grupos, supabase, session_state, xsd_urls):
    """Procesa XML de Inicio de Grupo usando funciones de utils.py"""
    
    st.markdown("### 🚀 XML Inicio de Grupo FUNDAE")
    st.caption("Esquema: InicioGrupos_Organizadora.xsd - Comunicación oficial de inicio")
    
    if df_grupos.empty:
        st.warning("⚠️ No hay grupos disponibles")
        st.info("💡 Crea grupos desde la página correspondiente")
        return
    
    # Crear diccionario de grupos con estado
    grupos_dict = {}
    for _, grupo in df_grupos.iterrows():
        codigo = grupo.get('codigo_grupo', 'Sin código')
        accion_nombre = grupo.get('accion_nombre', 'Sin acción')
        empresa_nombre = grupo.get('empresa_nombre', 'Sin empresa')
        
        # Determinar estado visual
        estado = determinar_estado_grupo(grupo.to_dict())
        icono_estado = {
            "ABIERTO": "🟢",
            "FINALIZAR": "🟡", 
            "FINALIZADO": "✅",
            "INCOMPLETO": "🔴"
        }.get(estado, "⚪")
        
        # Año del grupo
        ano = "?"
        if grupo.get('fecha_inicio'):
            try:
                ano = datetime.fromisoformat(str(grupo['fecha_inicio']).replace('Z', '+00:00')).year
            except:
                pass
        
        nombre_display = f"{icono_estado} {codigo} - {accion_nombre} ({empresa_nombre} - {ano})"
        grupos_dict[nombre_display] = grupo.to_dict()
    
    grupo_seleccionado = st.selectbox(
        "Selecciona el grupo formativo:",
        options=["Seleccionar..."] + list(grupos_dict.keys()),
        help="Solo grupos con datos completos para FUNDAE"
    )
    
    if grupo_seleccionado != "Seleccionar...":
        grupo_data = grupos_dict[grupo_seleccionado]
        grupo_id = grupo_data.get('id')
        
        # Validar y preparar datos usando función mejorada de utils.py
        with st.spinner("Validando datos FUNDAE del grupo..."):
            try:
                # USAR FUNCIÓN MEJORADA de utils.py
                datos_xml, errores = preparar_datos_xml_inicio_simple(grupo_id, supabase, session_state)
                
                if errores:
                    mostrar_errores_grupo(errores, grupo_data)
                    return
                
                # Mostrar información del grupo válido
                mostrar_informacion_grupo_valido(datos_xml)
                
                # Botones de acción
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("📄 Generar XML Inicio", type="primary", use_container_width=True):
                        generar_y_mostrar_xml_inicio_grupo(datos_xml)
                
                with col2:
                    if st.button("✅ Validar XML", use_container_width=True):
                        if xsd_urls.get('inicio_grupo'):
                            validar_xml_inicio_grupo_xsd(datos_xml, xsd_urls['inicio_grupo'])
                
            except Exception as e:
                st.error(f"❌ Error al procesar grupo FUNDAE: {e}")

def determinar_estado_grupo(grupo_data):
    """Determina estado del grupo para FUNDAE."""
    
    campos_requeridos = [
        'codigo_grupo', 'fecha_inicio', 'fecha_fin_prevista',
        'localidad', 'responsable', 'telefono_contacto'
    ]
    
    # Verificar campos básicos
    for campo in campos_requeridos:
        if not grupo_data.get(campo):
            return "INCOMPLETO"
    
    # Verificar fechas
    fecha_fin_prevista = grupo_data.get("fecha_fin_prevista")
    fecha_fin_real = grupo_data.get("fecha_fin")
    
    if fecha_fin_real:
        return "FINALIZADO"
    
    if fecha_fin_prevista:
        try:
            fecha_prevista_dt = datetime.fromisoformat(str(fecha_fin_prevista).replace('Z', '+00:00')).date()
            if fecha_prevista_dt <= date.today():
                return "FINALIZAR"
        except:
            pass
    
    return "ABIERTO"

def mostrar_errores_grupo(errores, grupo_data):
    """Muestra errores de validación FUNDAE."""
    
    st.markdown("""
    <div class="validation-error">
        ❌ <strong>Grupo no cumple los requisitos FUNDAE</strong><br>
        Completa los datos faltantes antes de generar XML
    </div>
    """, unsafe_allow_html=True)
    
    for error in errores:
        st.error(f"• {error}")
    
    st.info("💡 Ve a la página de Grupos para completar los datos faltantes")
    
    with st.expander("🔍 Ver datos actuales del grupo"):
        st.json(grupo_data)

def mostrar_informacion_grupo_valido(datos_xml):
    """Muestra información del grupo válido para FUNDAE."""
    
    st.success("✅ Grupo válido para XML FUNDAE con jerarquía empresarial")
    
    # Mostrar empresa responsable
    empresa_responsable = datos_xml.get("empresa_responsable", {})
    if empresa_responsable:
        st.info(f"🏢 Empresa responsable ante FUNDAE: **{empresa_responsable.get('nombre')}** (CIF: {empresa_responsable.get('cif')})")
    
    # Información del grupo
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("👥 Tutores", len(datos_xml.get("tutores", [])))
    with col2:
        st.metric("🏢 Empresas", len(datos_xml.get("empresas", [])))
    with col3:
        st.metric("🎓 Participantes", len(datos_xml.get("participantes", [])))
    
    # Vista previa de datos
    with st.expander("👀 Vista previa de datos FUNDAE", expanded=False):
        tab1, tab2, tab3 = st.tabs(["Grupo", "Empresa Responsable", "Tutores"])
        
        with tab1:
            grupo_info = datos_xml.get("grupo", {})
            st.json({
                "codigo_grupo": grupo_info.get("codigo_grupo"),
                "responsable": grupo_info.get("responsable"),
                "telefono_contacto": grupo_info.get("telefono_contacto"),
                "modalidad": grupo_info.get("modalidad"),
                "fecha_inicio": grupo_info.get("fecha_inicio")
            })
        
        with tab2:
            st.json(empresa_responsable)
        
        with tab3:
            for i, tutor in enumerate(datos_xml.get("tutores", [])):
                st.write(f"**Tutor {i+1}:**")
                st.json({
                    "nombre": tutor.get("nombre"),
                    "apellidos": tutor.get("apellidos"),
                    "nif": tutor.get("nif")
                })

def generar_y_mostrar_xml_inicio_grupo(datos_xml):
    """Genera y muestra XML de inicio de grupo usando función mejorada de utils.py"""
    
    with st.spinner("Generando XML de inicio con validaciones de jerarquía..."):
        try:
            # USAR FUNCIÓN MEJORADA de utils.py
            xml_content = generar_xml_inicio_grupo_con_validaciones(datos_xml)
            
            if xml_content:
                st.success("✅ XML de inicio generado correctamente con validaciones FUNDAE")
                
                # Mostrar XML generado (preview)
                st.text_area("XML Generado:", xml_content[:1000] + "...", height=150)
                
                # Botón de descarga
                codigo_grupo = datos_xml.get("grupo", {}).get("codigo_grupo", "sin_codigo")
                empresa_resp = datos_xml.get("empresa_responsable", {}).get("nombre", "sin_empresa").replace(" ", "_")
                ano = datetime.now().year
                
                filename = f"inicio_grupo_{codigo_grupo}_{empresa_resp}_{ano}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
                
                st.download_button(
                    label="💾 Descargar XML",
                    data=xml_content,
                    file_name=filename,
                    mime="application/xml",
                    use_container_width=True,
                    type="primary"
                )
            else:
                st.error("❌ Error al generar el XML")
                
        except Exception as e:
            st.error(f"❌ Error en generación XML: {e}")

def validar_xml_inicio_grupo_xsd(datos_xml, xsd_url):
    """Valida XML de inicio de grupo contra esquema XSD."""
    
    with st.spinner("Validando XML contra esquema FUNDAE..."):
        try:
            # Generar XML usando función mejorada
            xml_content = generar_xml_inicio_grupo_con_validaciones(datos_xml)
            
            if xml_content:
                es_valido, errores_xsd = validar_xml(xml_content, xsd_url)
                
                if es_valido:
                    st.markdown("""
                    <div class="validation-success">
                        ✅ <strong>XML válido según esquema FUNDAE</strong><br>
                        Cumple con InicioGrupos_Organizadora.xsd oficial
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div class="validation-error">
                        ❌ <strong>XML no válido según esquema XSD</strong><br>
                        Requiere correcciones antes de enviar a FUNDAE
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander("🔍 Ver errores de validación XSD", expanded=True):
                        for i, error in enumerate(errores_xsd[:5], 1):
                            st.error(f"**Error {i}:** {error}")
                        if len(errores_xsd) > 5:
                            st.info(f"... y {len(errores_xsd) - 5} errores más")
            else:
                st.error("❌ No se pudo generar XML para validación")
                
        except Exception as e:
            st.error(f"❌ Error en validación XSD: {e}")

# =========================
# PROCESAMIENTO XML FINALIZACIÓN
# =========================

def procesar_xml_finalizacion_grupo(df_grupos, supabase, session_state, xsd_urls):
    """Procesa XML de Finalización de Grupo usando funciones de utils.py"""
    
    st.markdown("### 🏁 XML Finalización de Grupo FUNDAE")
    st.caption("Esquema: FinalizacionGrupo_Organizadora.xsd - Comunicación oficial de finalización")
    
    if df_grupos.empty:
        st.warning("⚠️ No hay grupos disponibles")
        st.info("💡 Crea grupos desde la página correspondiente")
        return
    
    # Filtrar grupos finalizables
    grupos_finalizables = []
    hoy = date.today()
    
    for _, grupo in df_grupos.iterrows():
        fecha_fin_prevista = grupo.get('fecha_fin_prevista')
        fecha_fin_real = grupo.get('fecha_fin')
        estado_grupo = grupo.get('estado', 'abierto')
        
        puede_finalizar = False
        
        if fecha_fin_real:
            puede_finalizar = True
        elif fecha_fin_prevista:
            try:
                fecha_prevista_dt = datetime.fromisoformat(str(fecha_fin_prevista).replace('Z', '+00:00')).date()
                if fecha_prevista_dt <= hoy:
                    puede_finalizar = True
            except:
                pass
        elif estado_grupo in ['finalizar', 'finalizado']:
            puede_finalizar = True
        
        if puede_finalizar:
            grupos_finalizables.append(grupo.to_dict())
    
    if not grupos_finalizables:
        st.warning("⚠️ No hay grupos disponibles para finalización")
        st.info("💡 Los grupos deben haber superado su fecha prevista o estar marcados como finalizados")
        return
    
    # Crear diccionario de grupos finalizables
    grupos_dict = {}
    for grupo in grupos_finalizables:
        codigo = grupo.get('codigo_grupo', 'Sin código')
        accion_nombre = grupo.get('accion_nombre', 'Sin acción')
        fecha_fin = grupo.get('fecha_fin', grupo.get('fecha_fin_prevista', 'Sin fecha'))
        empresa_nombre = grupo.get('empresa_nombre', 'Sin empresa')
        
        # Determinar estado visual
        if grupo.get('fecha_fin'):
            estado_visual = "FINALIZADO"
        elif grupo.get('estado') == 'finalizar':
            estado_visual = "PENDIENTE"
        else:
            estado_visual = "DISPONIBLE"
        
        nombre_mostrar = f"{codigo} - {accion_nombre} ({empresa_nombre} - {estado_visual})"
        grupos_dict[nombre_mostrar] = grupo
    
    grupo_seleccionado = st.selectbox(
        "Selecciona un grupo para finalizar:",
        ["Seleccionar..."] + list(grupos_dict.keys()),
        key="grupo_fin_xml",
        help="Solo se muestran grupos que han superado su fecha prevista o están marcados para finalizar"
    )
    
    if grupo_seleccionado != "Seleccionar...":
        grupo_data = grupos_dict[grupo_seleccionado]
        grupo_id = grupo_data.get('id')
        
        # Validar empresa responsable
        with st.spinner("Validando permisos y datos para finalización..."):
            try:
                empresa_responsable, error_empresa = get_empresa_responsable_fundae(supabase, grupo_id)
                
                if error_empresa:
                    st.error(f"❌ Error al determinar empresa responsable: {error_empresa}")
                    return
                
                st.info(f"🏢 Empresa responsable ante FUNDAE: **{empresa_responsable.get('nombre')}** (CIF: {empresa_responsable.get('cif')})")
                
            except Exception as e:
                st.error(f"❌ Error al validar empresa responsable: {e}")
                return
        
        # Obtener participantes del grupo
        with st.spinner("Cargando participantes del grupo..."):
            try:
                # Buscar participantes usando la relación N:N
                participantes_res = supabase.table("participantes_grupos").select("""
                    participante:participantes(*)
                """).eq("grupo_id", grupo_id).execute()
                
                participantes_data = []
                if participantes_res.data:
                    participantes_data = [rel["participante"] for rel in participantes_res.data if rel.get("participante")]
                
                if not participantes_data:
                    st.warning(f"⚠️ No hay participantes en el grupo {grupo_data.get('codigo_grupo', 'seleccionado')}")
                    st.info("💡 Asigna participantes al grupo antes de generar el XML de finalización")
                    return
                
                st.success(f"✅ Encontrados {len(participantes_data)} participantes en el grupo")
                
                # Información de finalización
                mostrar_formulario_finalizacion(grupo_data, participantes_data, empresa_responsable, xsd_urls)
                
            except Exception as e:
                st.error(f"❌ Error al cargar participantes: {e}")

def mostrar_formulario_finalizacion(grupo_data, participantes_data, empresa_responsable, xsd_urls):
    """Muestra formulario de finalización con validaciones."""
    
    st.markdown("#### 📝 Información de Finalización")
    
    col1, col2, col3 = st.columns(3)
    
    # Valores actuales del grupo
    n_finalizados_actual = grupo_data.get('n_participantes_finalizados', len(participantes_data))
    n_aptos_actual = grupo_data.get('n_aptos', len(participantes_data))
    n_no_aptos_actual = grupo_data.get('n_no_aptos', 0)
    
    with col1:
        n_finalizados = st.number_input(
            "👥 Participantes Finalizados:",
            min_value=0,
            max_value=len(participantes_data),
            value=min(n_finalizados_actual, len(participantes_data)),
            help="Número total de participantes que completaron la formación"
        )
    
    with col2:
        n_aptos = st.number_input(
            "✅ Participantes APTOS:",
            min_value=0,
            max_value=n_finalizados,
            value=min(n_aptos_actual, n_finalizados),
            help="Participantes que superaron la formación"
        )
    
    with col3:
        n_no_aptos = st.number_input(
            "❌ Participantes NO APTOS:",
            min_value=0,
            max_value=n_finalizados,
            value=min(n_no_aptos_actual, n_finalizados - n_aptos),
            help="Participantes que no superaron la formación"
        )
    
    # Validación en tiempo real
    if n_finalizados > 0:
        total_resultado = n_aptos + n_no_aptos
        if total_resultado != n_finalizados:
            st.error(f"❌ Error: Aptos ({n_aptos}) + No Aptos ({n_no_aptos}) = {total_resultado}, debe ser igual a Finalizados ({n_finalizados})")
            return
        else:
            st.success(f"✅ Coherencia validada: {n_aptos} aptos + {n_no_aptos} no aptos = {n_finalizados} finalizados")
    
    # Fecha de finalización
    fecha_fin_actual = grupo_data.get('fecha_fin')
    if fecha_fin_actual:
        try:
            fecha_fin_default = datetime.fromisoformat(str(fecha_fin_actual).replace('Z', '+00:00')).date()
        except:
            fecha_fin_default = date.today()
    else:
        fecha_fin_default = date.today()
    
    fecha_fin_real = st.date_input(
        "📅 Fecha Real de Finalización:",
        value=fecha_fin_default,
        help="Fecha en que realmente finalizó el grupo"
    )
    
    # Actualizar datos del grupo para XML
    grupo_data_final = grupo_data.copy()
    grupo_data_final.update({
        'n_participantes_finalizados': n_finalizados,
        'n_aptos': n_aptos,
        'n_no_aptos': n_no_aptos,
        'fecha_fin': fecha_fin_real.isoformat(),
        'empresa_responsable': empresa_responsable
    })
    
    # Vista previa de datos
    with st.expander("👀 Vista previa de datos de finalización", expanded=False):
        tab1, tab2, tab3 = st.tabs(["Datos Grupo", "Participantes", "Empresa Responsable"])
        
        with tab1:
            st.json({
                "codigo_grupo": grupo_data_final.get('codigo_grupo'),
                "fecha_fin_real": fecha_fin_real.isoformat(),
                "participantes_finalizados": n_finalizados,
                "participantes_aptos": n_aptos,
                "participantes_no_aptos": n_no_aptos
            })
        
        with tab2:
            # Mostrar muestra de participantes
            participantes_preview = participantes_data[:3]
            for i, p in enumerate(participantes_preview):
                st.write(f"**Participante {i+1}:**")
                st.json({
                    "nombre": p.get('nombre', ''),
                    "apellidos": p.get('apellidos', ''),
                    "nif": p.get('nif', ''),
                    "email": p.get('email', '')
                })
            if len(participantes_data) > 3:
                st.caption(f"... y {len(participantes_data) - 3} participantes más")
        
        with tab3:
            st.json(empresa_responsable)
    
    # Botones de acción
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📄 Generar XML Finalización", type="primary", use_container_width=True):
            generar_y_mostrar_xml_finalizacion(grupo_data_final, participantes_data)
    
    with col2:
        if st.button("✅ Validar XML", use_container_width=True):
            if xsd_urls.get('finalizacion_grupo'):
                validar_xml_finalizacion_xsd(grupo_data_final, participantes_data, xsd_urls['finalizacion_grupo'])

def generar_y_mostrar_xml_finalizacion(grupo_data_final, participantes_data):
    """Genera y muestra XML de finalización usando función mejorada de utils.py"""
    
    with st.spinner("Generando XML de finalización con validaciones..."):
        try:
            # USAR FUNCIÓN MEJORADA de utils.py
            xml_content = generar_xml_finalizacion_grupo_mejorado(grupo_data_final, participantes_data)
            
            if xml_content:
                st.success("✅ XML de finalización generado correctamente")
                
                # Mostrar preview del XML
                st.text_area("XML Generado:", xml_content[:1000] + "...", height=150)
                
                # Botón de descarga con nombre descriptivo
                codigo_grupo = grupo_data_final.get('codigo_grupo', 'sin_codigo')
                empresa_nombre = grupo_data_final.get('empresa_responsable', {}).get('nombre', 'sin_empresa').replace(' ', '_')
                ano = datetime.fromisoformat(grupo_data_final.get('fecha_fin')).year if grupo_data_final.get('fecha_fin') else datetime.now().year
                
                filename = f"fin_grupo_{codigo_grupo}_{empresa_nombre}_{ano}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
                
                st.download_button(
                    label="💾 Descargar XML Finalización",
                    data=xml_content,
                    file_name=filename,
                    mime="application/xml",
                    use_container_width=True,
                    type="primary"
                )
            else:
                st.error("❌ Error al generar el XML")
                
        except Exception as e:
            st.error(f"❌ Error en generación XML: {e}")

def validar_xml_finalizacion_xsd(grupo_data_final, participantes_data, xsd_url):
    """Valida XML de finalización contra esquema XSD."""
    
    with st.spinner("Validando XML contra esquema FUNDAE..."):
        try:
            # Generar XML usando función mejorada
            xml_content = generar_xml_finalizacion_grupo_mejorado(grupo_data_final, participantes_data)
            
            if xml_content:
                es_valido, errores = validar_xml(xml_content, xsd_url)
                
                if es_valido:
                    st.markdown("""
                    <div class="validation-success">
                        ✅ <strong>XML de finalización válido según esquema FUNDAE</strong><br>
                        Cumple con FinalizacionGrupo_Organizadora.xsd oficial
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div class="validation-error">
                        ❌ <strong>XML no válido según esquema XSD</strong><br>
                        Requiere correcciones antes de enviar a FUNDAE
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander("🔍 Ver errores de validación XSD", expanded=True):
                        for i, error in enumerate(errores[:5], 1):
                            st.error(f"**Error {i}:** {error}")
                        if len(errores) > 5:
                            st.info(f"... y {len(errores) - 5} errores más")
            else:
                st.error("❌ No se pudo generar XML para validación")
                
        except Exception as e:
            st.error(f"❌ Error en validación XSD: {e}")

# =========================
# FUNCIONES DE INFORMACIÓN
# =========================

def mostrar_informacion_tipos_xml():
    """Muestra información sobre los tipos de XML disponibles."""
    
    st.info("👆 Selecciona un tipo de documento para comenzar")
    
    with st.expander("ℹ️ Validaciones FUNDAE aplicadas", expanded=False):
        st.markdown("""
        ### 🔍 Validaciones de Códigos FUNDAE:
        
        **Códigos de Acción Formativa:**
        - Únicos por empresa gestora y año
        - No pueden repetirse en el mismo periodo
        - Reutilizables en años diferentes
        
        **Códigos de Grupo:**
        - Únicos por acción formativa, empresa gestora y año
        - Secuenciales recomendados (Grupo 1, Grupo 2, etc.)
        - Reinicio de numeración cada año
        
        **Jerarquía Empresarial:**
        - Gestoras: Responsables ante FUNDAE
        - Clientes: Los XMLs se generan bajo la gestora
        - Validación automática de permisos
        """)

def mostrar_footer_informativo():
    """Muestra footer con información del sistema."""
    
    st.divider()
    
    with st.expander("ℹ️ Información sobre documentos FUNDAE", expanded=False):
        st.markdown("""
        ### 📋 Tipos de documentos FUNDAE con validaciones:
        
        **XML Acción Formativa:**
        - Códigos únicos por empresa gestora y año
        - Empresa responsable ante FUNDAE claramente identificada
        - Validación automática de duplicados
        
        **XML Inicio de Grupo:**
        - Códigos únicos por acción, empresa gestora y año
        - Jerarquía empresarial respetada (gestora > clientes)
        - Validación de permisos según rol
        
        **XML Finalización de Grupo:**
        - Coherencia de participantes (finalizados = aptos + no aptos)
        - Empresa responsable consistente con el inicio
        - Validación temporal de fechas
        
        ### 🔍 Validaciones FUNDAE aplicadas:
        - **Códigos únicos**: Por empresa gestora y año calendario
        - **Jerarquía empresarial**: Gestoras responsables de sus clientes
        - **Coherencia temporal**: Años consistentes entre documentos
        - **Integridad de datos**: Participantes y empresas validados
        
        ### ⚠️ Notas importantes:
        - Los XMLs incluyen metadatos de validación
        - La empresa responsable ante FUNDAE es siempre la gestora
        - Los códigos se reutilizan cada año calendario
        - Validación automática contra esquemas XSD oficiales
        """)
    
    st.caption("💡 Sistema con validaciones de jerarquía empresarial y códigos únicos FUNDAE")
