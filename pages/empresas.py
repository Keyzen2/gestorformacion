import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import validar_dni_cif, export_csv
from services.empresas_service import get_empresas_service

# Configuración de jerarquía
TIPOS_EMPRESA = {
    "CLIENTE_SAAS": "🏢 Cliente SaaS Directo",
    "GESTORA": "🎯 Gestora de Formación", 
    "CLIENTE_GESTOR": "👥 Cliente de Gestora"
}

@st.cache_data(ttl=3600)
def cargar_provincias(_supabase):
    """Carga lista de provincias."""
    try:
        result = _supabase.table("provincias").select("id, nombre").order("nombre").execute()
        return {prov["nombre"]: prov["id"] for prov in result.data or []}
    except:
        return {}

@st.cache_data(ttl=3600)
def cargar_localidades(_supabase, provincia_id):
    """Carga localidades de una provincia."""
    try:
        result = _supabase.table("localidades").select("id, nombre").eq("provincia_id", provincia_id).order("nombre").execute()
        return {loc["nombre"]: loc["id"] for loc in result.data or []}
    except:
        return {}

@st.cache_data(ttl=3600)
def cargar_sectores(_supabase):
    """Carga sectores empresariales."""
    try:
        result = _supabase.table("sectores_empresariales").select("nombre").order("nombre").execute()
        sectores = [sector["nombre"] for sector in result.data or []]
        return sorted(list(set(sectores)))
    except:
        return ["🏭 Industria", "🏪 Comercio", "⚙️ Servicios", "🏗️ Construcción", "💻 Tecnología"]

@st.cache_data(ttl=3600)
def cargar_cnae(_supabase):
    """Carga códigos CNAE."""
    try:
        result = _supabase.table("codigos_cnae").select("codigo, descripcion").order("codigo").execute()
        return {f"{cnae['codigo']} - {cnae['descripcion']}": cnae['codigo'] for cnae in result.data or []}
    except:
        return {}

def cargar_crm_datos(supabase, empresa_id):
    """Carga datos específicos de CRM con fechas."""
    try:
        result = supabase.table("crm_empresas").select("*").eq("empresa_id", empresa_id).execute()
        if result.data:
            return result.data[0]
        return {"crm_activo": False, "crm_inicio": None, "crm_fin": None}
    except:
        return {"crm_activo": False, "crm_inicio": None, "crm_fin": None}

def mostrar_metricas_empresas(empresas_service, session_state):
    """Muestra métricas con información jerárquica usando Streamlit 1.49."""
    try:
        metricas = empresas_service.get_estadisticas_empresas()
        
        if session_state.role == "admin":
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🏢 Total Empresas", metricas.get("total_empresas", 0), 
                         delta=f"+{metricas.get('nuevas_mes', 0)} este mes")
            with col2:
                st.metric("📅 Nuevas (30 días)", metricas.get("nuevas_mes", 0))
            with col3:
                st.metric("🎓 Con Formación", metricas.get("con_formacion", 0))
            with col4:
                porcentaje = metricas.get("porcentaje_activas", 0)
                st.metric("📊 % Activas", f"{porcentaje}%")
                
            # Distribución jerárquica
            with st.container():
                st.markdown("##### 🌳 Distribución por Tipo")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Cliente SaaS", metricas.get("clientes_saas", 0))
                with col2:
                    st.metric("Gestoras", metricas.get("gestoras", 0))
                with col3:
                    st.metric("Clientes de Gestoras", metricas.get("clientes_gestoras", 0))
        
        elif session_state.role == "gestor":
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("👥 Mis Empresas Clientes", metricas.get("total_clientes", 0))
            with col2:
                st.metric("📅 Nuevos (30 días)", metricas.get("nuevos_clientes_mes", 0))
            with col3:
                st.metric("🎓 Con Formación", metricas.get("clientes_con_formacion", 0))
            with col4:
                with st.container():
                    st.info(f"🎯 Gestora: {metricas.get('empresa_gestora', 'N/A')}")

    except Exception as e:
        st.error(f"❌ Error al cargar métricas: {e}")

def mostrar_tabla_empresas(df_empresas, session_state, titulo_tabla="📋 Lista de Empresas"):
    """Muestra tabla de empresas con funcionalidades de Streamlit 1.49."""
    if df_empresas.empty:
        st.info("📋 No hay empresas para mostrar")
        return None
    
    st.markdown(f"### {titulo_tabla}")
    
    df_display = df_empresas.copy()
    
    # Columnas según rol
    if session_state.role == "admin":
        columnas = ["nombre_display", "cif", "tipo_display", "ciudad", "telefono", "email"]
        column_config = {
            "nombre_display": st.column_config.TextColumn("🏢 Razón Social", width="large"),
            "cif": st.column_config.TextColumn("📄 CIF", width="small"),
            "tipo_display": st.column_config.TextColumn("🏷️ Tipo", width="medium"),
            "ciudad": st.column_config.TextColumn("📍 Ciudad", width="medium"),
            "telefono": st.column_config.TextColumn("📞 Teléfono", width="medium"),
            "email": st.column_config.TextColumn("📧 Email", width="large")
        }
    else:
        columnas = ["nombre_display", "cif", "ciudad", "telefono", "email"]
        column_config = {
            "nombre_display": st.column_config.TextColumn("🏢 Razón Social", width="large"),
            "cif": st.column_config.TextColumn("📄 CIF", width="small"),
            "ciudad": st.column_config.TextColumn("📍 Ciudad", width="medium"),
            "telefono": st.column_config.TextColumn("📞 Teléfono", width="medium"),
            "email": st.column_config.TextColumn("📧 Email", width="large")
        }
    
    # Tabla con selección usando Streamlit 1.49
    evento = st.dataframe(
        df_display[columnas],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    if evento.selection.rows:
        return df_display.iloc[evento.selection.rows[0]]
    return None

def mostrar_mi_empresa(empresas_service, session_state):
    """Muestra los datos de la empresa del gestor con posibilidad de edición."""
    st.markdown("### 🏢 Mi Empresa")
    
    try:
        # Cargar datos de la empresa del gestor desde la jerarquía
        df_empresas = empresas_service.get_empresas_con_jerarquia()
        mi_empresa = df_empresas[df_empresas['id'] == session_state.user.get("empresa_id")]
        
        if mi_empresa.empty:
            st.error("❌ No se encontraron datos de tu empresa")
            return
        
        empresa_info = mi_empresa.iloc[0].to_dict()
        
        # Mostrar información en container con border
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.info(f"**🏢 Razón Social**\n{empresa_info.get('nombre', 'N/A')}")
                st.info(f"**📄 CIF**\n{empresa_info.get('cif', 'N/A')}")
            
            with col2:
                st.info(f"**📍 Ciudad**\n{empresa_info.get('ciudad', 'N/A')}")
                st.info(f"**📞 Teléfono**\n{empresa_info.get('telefono', 'N/A')}")
            
            with col3:
                st.info(f"**📧 Email**\n{empresa_info.get('email', 'N/A')}")
                st.info(f"**🎯 Tipo**\n{TIPOS_EMPRESA.get(empresa_info.get('tipo_empresa'), 'N/A')}")
            
            # Mostrar módulos activos
            st.markdown("#### 🔧 Módulos Activos")
            modulos_activos = []
            if empresa_info.get("formacion_activo"):
                modulos_activos.append("📚 Formación")
            if empresa_info.get("iso_activo"):
                modulos_activos.append("📋 ISO 9001")
            if empresa_info.get("rgpd_activo"):
                modulos_activos.append("🛡️ RGPD")
            if empresa_info.get("docu_avanzada_activo"):
                modulos_activos.append("📁 Doc. Avanzada")
            if empresa_info.get("crm_activo"):
                modulos_activos.append("📈 CRM")
            
            if modulos_activos:
                st.success(" • ".join(modulos_activos))
            else:
                st.warning("⚠️ No hay módulos activos")
            
            # Botón para editar (solo datos básicos, no módulos)
            if st.button("✏️ Editar Información", use_container_width=True):
                st.session_state["editando_mi_empresa"] = True
                st.rerun()
        
        # Mostrar formulario de edición si está activado
        if st.session_state.get("editando_mi_empresa"):
            with st.container(border=True):
                st.markdown("#### ✏️ Editando Mi Empresa")
                mostrar_formulario_empresa(empresa_info, empresas_service, session_state, es_creacion=False, key_suffix="_mi_empresa", solo_datos_basicos=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Guardar Cambios", type="primary"):
                        st.session_state["editando_mi_empresa"] = False
                        st.rerun()
                with col2:
                    if st.button("❌ Cancelar"):
                        st.session_state["editando_mi_empresa"] = False
                        st.rerun()
            
    except Exception as e:
        st.error(f"❌ Error cargando información de tu empresa: {e}")

def mostrar_formulario_empresa(empresa_data, empresas_service, session_state, es_creacion=False, key_suffix="", solo_datos_basicos=False):
    """Formulario FUNDAE completo con funcionalidades de Streamlit 1.49."""
    
    if es_creacion:
        st.subheader("➕ Nueva Empresa Cliente")
        datos = {}
    else:
        if not key_suffix:
            st.subheader(f"✏️ Editar {empresa_data['nombre']}")
        datos = empresa_data.copy()
    
    # Cargar datos auxiliares
    provincias_dict = cargar_provincias(empresas_service.supabase)
    sectores_list = cargar_sectores(empresas_service.supabase)
    cnae_dict = cargar_cnae(empresas_service.supabase)
    
    # Cargar datos CRM si es necesario (solo admin y no solo datos básicos)
    crm_data = {}
    if not es_creacion and datos.get("id") and not solo_datos_basicos:
        crm_data = cargar_crm_datos(empresas_service.supabase, datos["id"])
    
    # ID único para el formulario
    form_id = f"empresa_{datos.get('id', 'nueva')}_{'crear' if es_creacion else 'editar'}{key_suffix}"
    
    # Inicializar cuentas de cotización en session_state
    cuentas_key = f"cuentas_{form_id}"
    if cuentas_key not in st.session_state:
        if not es_creacion and datos.get("id"):
            try:
                result = empresas_service.supabase.table("cuentas_cotizacion").select("*").eq("empresa_id", datos["id"]).execute()
                st.session_state[cuentas_key] = result.data or []
            except:
                st.session_state[cuentas_key] = []
        else:
            st.session_state[cuentas_key] = []
    
    with st.form(form_id, clear_on_submit=es_creacion):
        
        # =========================
        # BLOQUE IDENTIFICACIÓN
        # =========================
        st.markdown("### 🆔 Identificación")
        
        # Datos principales
        st.markdown("#### 📋 Datos Principales")
        col1, col2 = st.columns(2)
        
        with col1:
            # Para gestores: nombre y CIF readonly en edición (excepto en "Mi Empresa")
            if session_state.role == "gestor" and not es_creacion and not solo_datos_basicos:
                st.text_input("🏢 Razón Social", value=datos.get("nombre", ""), disabled=True, key=f"{form_id}_nombre_readonly")
                nombre = datos.get("nombre", "")
                st.text_input("📄 CIF", value=datos.get("cif", ""), disabled=True, key=f"{form_id}_cif_readonly")
                cif = datos.get("cif", "")
            else:
                nombre = st.text_input("🏢 Razón Social", value=datos.get("nombre", ""), key=f"{form_id}_nombre")
                cif = st.text_input("📄 CIF", value=datos.get("cif", ""), key=f"{form_id}_cif")
        
        with col2:
            sector = st.selectbox("🏭 Sector", options=[""] + sectores_list, 
                                index=sectores_list.index(datos.get("sector", "")) + 1 if datos.get("sector") in sectores_list else 0,
                                key=f"{form_id}_sector")
            convenio_referencia = st.text_input("📋 Convenio de Referencia", value=datos.get("convenio_referencia", ""), key=f"{form_id}_convenio")
        
        # Código CNAE
        if cnae_dict:
            cnae_actual = datos.get("codigo_cnae", "")
            cnae_display = next((k for k, v in cnae_dict.items() if v == cnae_actual), "")
            codigo_cnae_sel = st.selectbox(
                "🔢 Código CNAE", 
                options=[""] + list(cnae_dict.keys()),
                index=list(cnae_dict.keys()).index(cnae_display) + 1 if cnae_display else 0,
                help="Busque escribiendo el código o descripción",
                key=f"{form_id}_cnae"
            )
            codigo_cnae = cnae_dict.get(codigo_cnae_sel, "") if codigo_cnae_sel else ""
        else:
            codigo_cnae = st.text_input("🔢 Código CNAE", value=datos.get("codigo_cnae", ""), key=f"{form_id}_cnae_input")
        
        # Domicilio Social
        st.markdown("#### 🏠 Domicilio Social")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            calle = st.text_input("🛣️ Calle", value=datos.get("calle", ""), key=f"{form_id}_calle")
            numero = st.text_input("🏠 Número", value=datos.get("numero", ""), key=f"{form_id}_numero")
        
        with col2:
            codigo_postal = st.text_input("📮 Código Postal", value=datos.get("codigo_postal", ""), key=f"{form_id}_cp")
            
            # Selector de provincia
            provincia_actual = datos.get("provincia_id")
            if provincia_actual and provincias_dict:
                provincia_nombre = next((k for k, v in provincias_dict.items() if v == provincia_actual), "")
            else:
                provincia_nombre = ""
            
            provincia_sel = st.selectbox(
                "🗺️ Provincia", 
                options=[""] + list(provincias_dict.keys()),
                index=list(provincias_dict.keys()).index(provincia_nombre) + 1 if provincia_nombre else 0,
                key=f"{form_id}_provincia"
            )
            provincia_id = provincias_dict.get(provincia_sel) if provincia_sel else None
        
        with col3:
            # Selector de localidad que se actualiza automáticamente
            if provincia_id:
                localidades_dict = cargar_localidades(empresas_service.supabase, provincia_id)
                if localidades_dict:
                    localidad_actual = datos.get("localidad_id")
                    localidad_nombre = next((k for k, v in localidades_dict.items() if v == localidad_actual), "") if localidad_actual else ""
                    
                    localidad_sel = st.selectbox(
                        "🏘️ Población",
                        options=[""] + list(localidades_dict.keys()),
                        index=list(localidades_dict.keys()).index(localidad_nombre) + 1 if localidad_nombre else 0,
                        key=f"{form_id}_localidad"
                    )
                    localidad_id = localidades_dict.get(localidad_sel) if localidad_sel else None
                else:
                    st.selectbox("🏘️ Población", options=["Sin localidades"], disabled=True, key=f"{form_id}_localidad_empty")
                    localidad_id = None
                    localidad_sel = ""
            else:
                st.selectbox("🏘️ Población", options=["Seleccione provincia"], disabled=True, key=f"{form_id}_localidad_disabled")
                localidad_id = None
                localidad_sel = ""
            
            telefono = st.text_input("📞 Teléfono", value=datos.get("telefono", ""), key=f"{form_id}_telefono")
        
        # Solo mostrar más campos si NO es solo_datos_basicos
        if not solo_datos_basicos:
            # Representante Legal
            st.markdown("#### 👤 Representante Legal")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                representante_tipo_documento = st.selectbox(
                    "📄 Tipo Documento", 
                    options=["", "NIF", "NIE", "PASAPORTE"],
                    index=["", "NIF", "NIE", "PASAPORTE"].index(datos.get("representante_tipo_documento", "")) if datos.get("representante_tipo_documento") in ["", "NIF", "NIE", "PASAPORTE"] else 0,
                    key=f"{form_id}_tipo_doc"
                )
            
            with col2:
                representante_numero_documento = st.text_input("🆔 Nº Documento", value=datos.get("representante_numero_documento", ""), key=f"{form_id}_num_doc")
            
            with col3:
                representante_nombre_apellidos = st.text_input("👤 Nombre y Apellidos", value=datos.get("representante_nombre_apellidos", ""), key=f"{form_id}_nombre_apellidos")
            
            # Notificaciones
            st.markdown("#### 📧 Notificaciones")
            email_notificaciones = st.text_input("📧 Email", value=datos.get("email_notificaciones", datos.get("email", "")), key=f"{form_id}_email")
            
            # Contrato de Encomienda
            st.markdown("#### 📋 Contrato de Encomienda")
            fecha_contrato_encomienda = st.date_input(
                "📅 Fecha Contrato Encomienda", 
                value=datos.get("fecha_contrato_encomienda") if datos.get("fecha_contrato_encomienda") else date.today(),
                key=f"{form_id}_fecha_contrato"
            )
            
            # =========================
            # BLOQUE CARACTERÍSTICAS
            # =========================
            st.markdown("### ⚙️ Características")
            
            col1, col2 = st.columns(2)
            
            with col1:
                nueva_creacion = st.checkbox("🆕 Nueva creación", value=datos.get("nueva_creacion", False), key=f"{form_id}_nueva_creacion")
                representacion_legal_trabajadores = st.checkbox(
                    "👥 ¿Existe Representación Legal de las Personas Trabajadoras?", 
                    value=datos.get("representacion_legal_trabajadores", False), key=f"{form_id}_repr_legal"
                )
                plantilla_media_anterior = st.number_input(
                    "👥 Plantilla media del año anterior", 
                    min_value=0, 
                    value=datos.get("plantilla_media_anterior", 0), key=f"{form_id}_plantilla"
                )
            
            with col2:
                es_pyme = st.checkbox("🏢 PYME", value=datos.get("es_pyme", True), key=f"{form_id}_pyme")
                voluntad_acumular_credito = st.checkbox(
                    "💰 ¿Voluntad de acumular crédito de formación?",
                    value=datos.get("voluntad_acumular_credito", False), key=f"{form_id}_acumular_credito"
                )
                tiene_erte = st.checkbox("⚠️ ERTE", value=datos.get("tiene_erte", False), key=f"{form_id}_erte")
        
        else:
            # Valores por defecto para solo_datos_basicos
            representante_tipo_documento = datos.get("representante_tipo_documento")
            representante_numero_documento = datos.get("representante_numero_documento", "")
            representante_nombre_apellidos = datos.get("representante_nombre_apellidos", "")
            email_notificaciones = datos.get("email_notificaciones", datos.get("email", ""))
            fecha_contrato_encomienda = datos.get("fecha_contrato_encomienda", date.today())
            nueva_creacion = datos.get("nueva_creacion", False)
            representacion_legal_trabajadores = datos.get("representacion_legal_trabajadores", False)
            plantilla_media_anterior = datos.get("plantilla_media_anterior", 0)
            es_pyme = datos.get("es_pyme", True)
            voluntad_acumular_credito = datos.get("voluntad_acumular_credito", False)
            tiene_erte = datos.get("tiene_erte", False)
        
        # Campos de módulos solo para admin y NO solo_datos_basicos
        if session_state.role == "admin" and not solo_datos_basicos:
            st.markdown("### 🔧 Configuración de Módulos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                formacion_activo = st.checkbox("📚 Formación", value=datos.get("formacion_activo", True), key=f"{form_id}_formacion")
                iso_activo = st.checkbox("📋 ISO 9001", value=datos.get("iso_activo", False), key=f"{form_id}_iso")
                rgpd_activo = st.checkbox("🛡️ RGPD", value=datos.get("rgpd_activo", False), key=f"{form_id}_rgpd")
            
            with col2:
                docu_avanzada_activo = st.checkbox("📁 Doc. Avanzada", value=datos.get("docu_avanzada_activo", False), key=f"{form_id}_docu")
                
                # CRM con fechas
                crm_activo = st.checkbox("📈 CRM", value=crm_data.get("crm_activo", False), key=f"{form_id}_crm")
                
                if crm_activo:
                    crm_inicio = st.date_input("📅 CRM Inicio", value=crm_data.get("crm_inicio", date.today()), key=f"{form_id}_crm_inicio")
                    crm_fin = st.date_input("📅 CRM Fin", value=crm_data.get("crm_fin"), key=f"{form_id}_crm_fin", help="Dejar vacío si no tiene fecha fin")
                else:
                    crm_inicio = None
                    crm_fin = None
        else:
            # Mantener valores existentes
            formacion_activo = datos.get("formacion_activo", True)
            iso_activo = datos.get("iso_activo", False)
            rgpd_activo = datos.get("rgpd_activo", False)
            docu_avanzada_activo = datos.get("docu_avanzada_activo", False)
            crm_activo = crm_data.get("crm_activo", False)
            crm_inicio = None
            crm_fin = None
        
        # Validaciones
        errores = []
        if not nombre:
            errores.append("Razón Social requerida")
        if not cif or not validar_dni_cif(cif):
            errores.append("CIF válido requerido")
        if not solo_datos_basicos:
            if not fecha_contrato_encomienda:
                errores.append("Fecha contrato requerida")
            if len(st.session_state[cuentas_key]) == 0:
                errores.append("Al menos una cuenta de cotización")
        
        # Mostrar errores
        if errores:
            st.error(f"⚠️ Faltan campos: {', '.join(errores)}")
        
        # Botones de acción
        st.markdown("---")
        if solo_datos_basicos:
            # Solo botón guardar para "Mi Empresa"
            submitted = st.form_submit_button("💾 Actualizar", type="primary", use_container_width=True, disabled=len(errores) > 0)
            eliminar = False
        else:
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                submitted = st.form_submit_button("💾 Guardar", type="primary", use_container_width=True, disabled=len(errores) > 0)
            
            with col_btn2:
                if not es_creacion and session_state.role == "admin":
                    eliminar = st.form_submit_button("🗑️ Eliminar", type="secondary", use_container_width=True)
                else:
                    eliminar = False
        
        # Procesar formulario
        if submitted:
            procesar_guardado_empresa(
                datos, nombre, cif, sector, convenio_referencia, codigo_cnae,
                calle, numero, codigo_postal, provincia_id, localidad_id, telefono,
                representante_tipo_documento, representante_numero_documento, representante_nombre_apellidos,
                email_notificaciones, fecha_contrato_encomienda, nueva_creacion,
                representacion_legal_trabajadores, plantilla_media_anterior, es_pyme,
                voluntad_acumular_credito, tiene_erte, formacion_activo, iso_activo,
                rgpd_activo, docu_avanzada_activo, crm_activo, crm_inicio, crm_fin,
                st.session_state[cuentas_key], provincia_sel, localidad_sel, 
                empresas_service, session_state, es_creacion, solo_datos_basicos
            )
        
        if eliminar:
            if st.session_state.get("confirmar_eliminar"):
                try:
                    success = empresas_service.delete_empresa_con_jerarquia(datos["id"])
                    if success:
                        st.success("✅ Empresa eliminada correctamente")
                        del st.session_state["confirmar_eliminar"]
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error eliminando empresa: {e}")
            else:
                st.session_state["confirmar_eliminar"] = True
                st.warning("⚠️ Presiona 'Eliminar' nuevamente para confirmar")
    
    # Gestión de cuentas de cotización FUERA del formulario (solo si no es popover ni solo_datos_basicos)
    if not key_suffix and not solo_datos_basicos:
        st.markdown("#### 🏦 Cuentas de Cotización")
        mostrar_gestion_cuentas(cuentas_key)

def mostrar_gestion_cuentas(cuentas_key):
    """Gestión de cuentas de cotización."""
    
    cuentas = st.session_state[cuentas_key]
    
    # Mostrar cuentas existentes
    if cuentas:
        st.write("**Cuentas configuradas:**")
        for i, cuenta in enumerate(cuentas):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                principal = " 🌟" if cuenta.get("es_principal") else ""
                st.text(f"• {cuenta['numero_cuenta']}{principal}")
            with col2:
                if st.button("🌟 Principal", key=f"principal_{cuentas_key}_{i}", 
                           disabled=cuenta.get("es_principal", False)):
                    for j, c in enumerate(cuentas):
                        c["es_principal"] = (j == i)
                    st.rerun()
            with col3:
                if st.button("🗑️", key=f"eliminar_{cuentas_key}_{i}"):
                    cuentas.pop(i)
                    st.rerun()
    else:
        st.info("📝 No hay cuentas de cotización configuradas")
    
    # Añadir nueva cuenta usando popover
    with st.popover("➕ Añadir Cuenta"):
        nueva_cuenta = st.text_input("Número de cuenta", placeholder="Ej: 281234567890")
        es_principal = st.checkbox("Marcar como principal")
        
        if st.button("✅ Añadir"):
            if nueva_cuenta:
                # Si se marca como principal, quitar de otras
                if es_principal:
                    for cuenta in cuentas:
                        cuenta["es_principal"] = False
                
                # Añadir nueva cuenta
                cuentas.append({
                    "numero_cuenta": nueva_cuenta,
                    "es_principal": es_principal
                })
                st.success("✅ Cuenta añadida")
                st.rerun()
            else:
                st.error("⚠️ Introduce un número de cuenta")

def procesar_guardado_empresa(datos, nombre, cif, sector, convenio_referencia, codigo_cnae,
                             calle, numero, codigo_postal, provincia_id, localidad_id, telefono,
                             representante_tipo_documento, representante_numero_documento, representante_nombre_apellidos,
                             email_notificaciones, fecha_contrato_encomienda, nueva_creacion,
                             representacion_legal_trabajadores, plantilla_media_anterior, es_pyme,
                             voluntad_acumular_credito, tiene_erte, formacion_activo, iso_activo,
                             rgpd_activo, docu_avanzada_activo, crm_activo, crm_inicio, crm_fin,
                             cuentas_cotizacion, provincia_sel, localidad_sel, 
                             empresas_service, session_state, es_creacion, solo_datos_basicos=False):
    """Procesa el guardado de la empresa."""
    
    datos_empresa = {
        "nombre": nombre,
        "cif": cif,
        "sector": sector,
        "convenio_referencia": convenio_referencia,
        "codigo_cnae": codigo_cnae,
        "calle": calle,
        "numero": numero,
        "codigo_postal": codigo_postal,
        "provincia_id": provincia_id,
        "localidad_id": localidad_id,
        "telefono": telefono,
        "representante_tipo_documento": representante_tipo_documento or None,
        "representante_numero_documento": representante_numero_documento,
        "representante_nombre_apellidos": representante_nombre_apellidos,
        "email_notificaciones": email_notificaciones,
        "fecha_contrato_encomienda": fecha_contrato_encomienda.isoformat() if fecha_contrato_encomienda else None,
        "nueva_creacion": nueva_creacion,
        "representacion_legal_trabajadores": representacion_legal_trabajadores,
        "plantilla_media_anterior": plantilla_media_anterior,
        "es_pyme": es_pyme,
        "voluntad_acumular_credito": voluntad_acumular_credito,
        "tiene_erte": tiene_erte,
        "formacion_activo": formacion_activo,
        "iso_activo": iso_activo,
        "rgpd_activo": rgpd_activo,
        "docu_avanzada_activo": docu_avanzada_activo,
        # Campos de compatibilidad
        "email": email_notificaciones,
        "direccion": f"{calle} {numero}" if calle else "",
        "ciudad": localidad_sel if localidad_sel else "",
        "provincia": provincia_sel if provincia_sel else ""
    }
    
    try:
        if es_creacion:
            success, empresa_id = empresas_service.crear_empresa_con_jerarquia(datos_empresa)
            if success:
                st.success("✅ Empresa cliente creada correctamente")
                # Guardar cuentas
                if not solo_datos_basicos:
                    guardar_cuentas_cotizacion(empresas_service.supabase, empresa_id, cuentas_cotizacion)
                # Guardar datos CRM si corresponde
                if session_state.role == "admin" and crm_activo:
                    guardar_crm_datos(empresas_service.supabase, empresa_id, crm_activo, crm_inicio, crm_fin)
                st.rerun()
            else:
                st.error("❌ Error al crear la empresa cliente")
        else:
            success = empresas_service.update_empresa_con_jerarquia(datos["id"], datos_empresa)
            if success:
                st.success("✅ Empresa actualizada correctamente")
                # Actualizar cuentas solo si no es solo_datos_basicos
                if not solo_datos_basicos:
                    actualizar_cuentas_cotizacion(empresas_service.supabase, datos["id"], cuentas_cotizacion)
                # Actualizar datos CRM si corresponde
                if session_state.role == "admin" and not solo_datos_basicos:
                    actualizar_crm_datos(empresas_service.supabase, datos["id"], crm_activo, crm_inicio, crm_fin)
                st.rerun()
            else:
                st.error("❌ Error al actualizar la empresa")
    except Exception as e:
        st.error(f"❌ Error procesando empresa: {e}")

def guardar_cuentas_cotizacion(supabase, empresa_id, cuentas):
    """Guarda las cuentas de cotización."""
    try:
        for cuenta in cuentas:
            supabase.table("cuentas_cotizacion").insert({
                "empresa_id": empresa_id,
                "numero_cuenta": cuenta["numero_cuenta"],
                "es_principal": cuenta.get("es_principal", False)
            }).execute()
    except Exception as e:
        st.warning(f"Error guardando cuentas: {e}")

def actualizar_cuentas_cotizacion(supabase, empresa_id, cuentas):
    """Actualiza las cuentas de cotización."""
    try:
        # Eliminar y recrear (simplificado)
        supabase.table("cuentas_cotizacion").delete().eq("empresa_id", empresa_id).execute()
        guardar_cuentas_cotizacion(supabase, empresa_id, cuentas)
    except Exception as e:
        st.warning(f"Error actualizando cuentas: {e}")

def guardar_crm_datos(supabase, empresa_id, crm_activo, crm_inicio, crm_fin):
    """Guarda datos específicos de CRM."""
    try:
        datos_crm = {
            "empresa_id": empresa_id,
            "crm_activo": crm_activo,
            "crm_inicio": crm_inicio.isoformat() if crm_inicio else None,
            "crm_fin": crm_fin.isoformat() if crm_fin else None
        }
        supabase.table("crm_empresas").insert(datos_crm).execute()
    except Exception as e:
        st.warning(f"Error guardando datos CRM: {e}")

def actualizar_crm_datos(supabase, empresa_id, crm_activo, crm_inicio, crm_fin):
    """Actualiza datos específicos de CRM."""
    try:
        datos_crm = {
            "crm_activo": crm_activo,
            "crm_inicio": crm_inicio.isoformat() if crm_inicio else None,
            "crm_fin": crm_fin.isoformat() if crm_fin else None
        }
        
        # Verificar si ya existe
        existing = supabase.table("crm_empresas").select("id").eq("empresa_id", empresa_id).execute()
        
        if existing.data:
            # Actualizar
            supabase.table("crm_empresas").update(datos_crm).eq("empresa_id", empresa_id).execute()
        else:
            # Crear nuevo
            datos_crm["empresa_id"] = empresa_id
            supabase.table("crm_empresas").insert(datos_crm).execute()
    except Exception as e:
        st.warning(f"Error actualizando datos CRM: {e}")

def main(supabase, session_state):
    st.title("🏢 Gestión de Empresas FUNDAE")
    
    if session_state.role == "admin":
        st.caption("📊 Administración completa de empresas con datos FUNDAE")
    else:
        st.caption("👥 Gestión de empresas clientes con formulario FUNDAE completo")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("⚠️ No tienes permisos para acceder a esta sección")
        return

    empresas_service = get_empresas_service(supabase, session_state)
    
    with st.spinner("⏳ Cargando empresas..."):
        try:
            df_empresas = empresas_service.get_empresas_con_jerarquia()
        except Exception as e:
            st.error(f"❌ Error al cargar empresas: {e}")
            return

    # Métricas
    mostrar_metricas_empresas(empresas_service, session_state)
    st.divider()
    
    # Filtros de búsqueda
    st.markdown("### 🔍 Buscar y Filtrar")
    col1, col2 = st.columns(2)
    
    with col1:
        query = st.text_input("🔍 Buscar por razón social, CIF o ciudad", placeholder="Escribe para buscar...")
    
    with col2:
        if session_state.role == "admin":
            tipo_filter = st.selectbox("📂 Filtrar por tipo", 
                                     ["Todos", "CLIENTE_SAAS", "GESTORA", "CLIENTE_GESTOR"])
        else:
            tipo_filter = "Todos"
    
    # Aplicar filtros
    df_filtered = df_empresas.copy()
    if query:
        q_lower = query.lower()
        df_filtered = df_filtered[
            df_filtered["nombre"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["cif"].str.lower().str.contains(q_lower, na=False) |
            df_filtered["ciudad"].fillna("").str.lower().str.contains(q_lower, na=False)
        ]
    
    if tipo_filter != "Todos":
        df_filtered = df_filtered[df_filtered["tipo_empresa"] == tipo_filter]
    
    # Exportar datos
    if not df_filtered.empty:
        st.download_button(
            label="📥 Exportar CSV",
            data=df_filtered.to_csv(index=False),
            file_name=f"empresas_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    st.divider()
    
    # DIFERENCIACIÓN POR ROL: Admin vs Gestor
    if session_state.role == "admin":
        # Tabs para admin (vista tradicional)
        tab1, tab2 = st.tabs(["📋 Lista de Empresas", "➕ Nueva Empresa"])
        
        with tab1:
            # Mostrar tabla y manejar selección
            empresa_seleccionada = mostrar_tabla_empresas(df_filtered, session_state)
            
            # Si hay una empresa seleccionada, mostrar formulario de edición
            if empresa_seleccionada is not None:
                with st.container(border=True):
                    mostrar_formulario_empresa(empresa_seleccionada, empresas_service, session_state, es_creacion=False)
        
        with tab2:
            # Formulario de creación
            if empresas_service.can_modify_data():
                with st.container(border=True):
                    mostrar_formulario_empresa({}, empresas_service, session_state, es_creacion=True)
            else:
                st.info("ℹ️ No tienes permisos para crear empresas")
    
    elif session_state.role == "gestor":
        # Vista separada para gestores
        tab1, tab2, tab3 = st.tabs(["🏢 Mi Empresa", "👥 Empresas Clientes", "➕ Nueva Empresa Cliente"])
        
        with tab1:
            mostrar_mi_empresa(empresas_service, session_state)
        
        with tab2:
            # Filtrar solo empresas clientes (excluir la propia empresa del gestor)
            df_clientes = df_filtered[df_filtered["empresa_matriz_id"] == session_state.user.get("empresa_id")]
            
            empresa_seleccionada = mostrar_tabla_empresas(df_clientes, session_state, "👥 Mis Empresas Clientes")
            
            # Si hay una empresa cliente seleccionada, mostrar formulario de edición
            if empresa_seleccionada is not None:
                with st.container(border=True):
                    mostrar_formulario_empresa(empresa_seleccionada, empresas_service, session_state, es_creacion=False)
        
        with tab3:
            # Formulario de creación de empresa cliente
            if empresas_service.can_modify_data():
                with st.container(border=True):
                    st.info("📋 Las empresas clientes se crearán automáticamente como 'Cliente de Gestora' bajo tu empresa")
                    mostrar_formulario_empresa({}, empresas_service, session_state, es_creacion=True)
            else:
                st.info("ℹ️ No tienes permisos para crear empresas")
    
    # Vista jerárquica para admin
    if session_state.role == "admin":
        st.divider()
        with st.expander("🌳 Vista Jerárquica", expanded=False):
            try:
                arbol = empresas_service.get_arbol_empresas()
                if not arbol.empty:
                    for _, empresa in arbol.iterrows():
                        nivel = empresa.get("nivel_jerarquico", 1)
                        if nivel == 1:
                            st.markdown(f"🏢 **{empresa['nombre']}** ({empresa.get('tipo_empresa', 'N/A')})")
                        else:
                            st.markdown(f"  └── 👥 {empresa['nombre']} ({empresa.get('tipo_empresa', 'N/A')})")
                else:
                    st.info("📋 No hay estructura jerárquica para mostrar")
            except Exception as e:
                st.error(f"❌ Error cargando vista jerárquica: {e}")
    
    # Información adicional
    st.divider()
    if session_state.role == "admin":
        with st.expander("ℹ️ Información sobre FUNDAE y Jerarquía"):
            st.markdown("""
            **📋 Campos FUNDAE obligatorios:**
            - 🆔 Datos de identificación completos (CIF, razón social, sector, CNAE)
            - 🏠 Domicilio social completo con provincia y localidad
            - 👤 Representante legal con documentación
            - ⚙️ Características de la empresa (plantilla, PYME, etc.)
            - 🏦 Al menos una cuenta de cotización
            
            **🌳 Jerarquía Multi-Tenant:**
            - 🏢 **Cliente SaaS**: Empresas que contratan directamente
            - 🎯 **Gestora**: Clientes que gestionan otras empresas
            - 👥 **Cliente Gestor**: Empresas gestionadas por una gestora
            
            **🔧 Módulos disponibles:**
            - 📚 **Formación**: Gestión de cursos y grupos FUNDAE
            - 📋 **ISO 9001**: Sistema de gestión de calidad
            - 🛡️ **RGPD**: Gestión de protección de datos
            - 📁 **Doc. Avanzada**: Gestión documental avanzada
            - 📈 **CRM**: Gestión comercial (solo con fechas)
            """)
    elif session_state.role == "gestor":
        with st.expander("ℹ️ Información para Gestores"):
            st.markdown("""
            **🏢 Mi Empresa:**
            - ✏️ Puedes editar la información básica de tu empresa
            - 🔒 Los módulos solo los puede activar/desactivar el administrador
            - 📊 Ves un resumen de los módulos activos
            
            **👥 Empresas Clientes:**
            - ➕ Puedes crear nuevas empresas como "Cliente de Gestora"
            - ✏️ Puedes editar toda la información FUNDAE de tus clientes
            - 🔒 Razón Social y CIF son de solo lectura tras la creación
            - 🏦 Gestión completa de cuentas de cotización
            
            **📋 Formulario FUNDAE completo:**
            - ✅ Todos los campos requeridos por FUNDAE para formación bonificada
            - 🔄 Selector automático provincia → localidad
            - 🔢 Códigos CNAE con búsqueda integrada
            - 🏦 Gestión interactiva de cuentas (usar "➕ Añadir Cuenta")
            - ⚡ Validación CIF en tiempo real
            """)

if __name__ == "__main__":
    pass
