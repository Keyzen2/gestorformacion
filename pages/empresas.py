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
        return sorted(list(set(sectores)))  # Eliminar duplicados
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
        st.error(f"Error al cargar métricas: {e}")

def mostrar_tabla_empresas(df_empresas, session_state):
    """Muestra tabla de empresas con funcionalidades de Streamlit 1.49."""
    if df_empresas.empty:
        st.info("📋 No hay empresas para mostrar")
        return None
    
    # Preparar datos para mostrar
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
    
    # Retornar empresa seleccionada
    if evento.selection.rows:
        return df_display.iloc[evento.selection.rows[0]]
    return None

def mostrar_formulario_empresa(empresa_data, empresas_service, session_state, es_creacion=False):
    """Formulario FUNDAE completo con funcionalidades de Streamlit 1.49."""
    
    if es_creacion:
        st.subheader("➕ Nueva Empresa Cliente")
        datos = {}
    else:
        st.subheader(f"✏️ Editar {empresa_data['nombre']}")
        datos = empresa_data.copy()
    
    # Cargar datos auxiliares
    provincias_dict = cargar_provincias(empresas_service.supabase)
    sectores_list = cargar_sectores(empresas_service.supabase)
    cnae_dict = cargar_cnae(empresas_service.supabase)
    
    # ID único para el formulario
    form_id = f"empresa_{datos.get('id', 'nueva')}_{'crear' if es_creacion else 'editar'}"
    
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
    
    with st.form(f"form_{form_id}", clear_on_submit=es_creacion):
        
        # =========================
        # BLOQUE IDENTIFICACIÓN
        # =========================
        st.markdown("### 🆔 Identificación")
        
        # Datos principales
        st.markdown("#### 📋 Datos Principales")
        col1, col2 = st.columns(2)
        
        with col1:
            # Para gestores: nombre y CIF readonly en edición
            if session_state.role == "gestor" and not es_creacion:
                st.text_input("🏢 Razón Social", value=datos.get("nombre", ""), disabled=True)
                nombre = datos.get("nombre", "")
                st.text_input("📄 CIF", value=datos.get("cif", ""), disabled=True)
                cif = datos.get("cif", "")
                cif_valido = True
            else:
                nombre = st.text_input("🏢 Razón Social", value=datos.get("nombre", ""))
                cif = st.text_input("📄 CIF", value=datos.get("cif", ""))
                cif_valido = validar_dni_cif(cif) if cif else True
        
        with col2:
            sector = st.selectbox("🏭 Sector", options=[""] + sectores_list, 
                                index=sectores_list.index(datos.get("sector", "")) + 1 if datos.get("sector") in sectores_list else 0)
            convenio_referencia = st.text_input("📋 Convenio de Referencia", value=datos.get("convenio_referencia", ""))
        
        # Código CNAE
        if cnae_dict:
            cnae_actual = datos.get("codigo_cnae", "")
            cnae_display = next((k for k, v in cnae_dict.items() if v == cnae_actual), "")
            codigo_cnae_sel = st.selectbox(
                "🔢 Código CNAE", 
                options=[""] + list(cnae_dict.keys()),
                index=list(cnae_dict.keys()).index(cnae_display) + 1 if cnae_display else 0,
                help="Busque escribiendo el código o descripción"
            )
            codigo_cnae = cnae_dict.get(codigo_cnae_sel, "") if codigo_cnae_sel else ""
        else:
            codigo_cnae = st.text_input("🔢 Código CNAE", value=datos.get("codigo_cnae", ""))
        
        # Domicilio Social
        st.markdown("#### 🏠 Domicilio Social")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            calle = st.text_input("🛣️ Calle", value=datos.get("calle", ""))
            numero = st.text_input("🏠 Número", value=datos.get("numero", ""))
        
        with col2:
            codigo_postal = st.text_input("📮 Código Postal", value=datos.get("codigo_postal", ""))
            
            # Selector de provincia
            provincia_actual = datos.get("provincia_id")
            if provincia_actual and provincias_dict:
                provincia_nombre = next((k for k, v in provincias_dict.items() if v == provincia_actual), "")
            else:
                provincia_nombre = ""
            
            provincia_sel = st.selectbox(
                "🗺️ Provincia", 
                options=[""] + list(provincias_dict.keys()),
                index=list(provincias_dict.keys()).index(provincia_nombre) + 1 if provincia_nombre else 0
            )
            provincia_id = provincias_dict.get(provincia_sel) if provincia_sel else None
        
        with col3:
            # Selector de localidad
            if provincia_id:
                localidades_dict = cargar_localidades(empresas_service.supabase, provincia_id)
                if localidades_dict:
                    localidad_actual = datos.get("localidad_id")
                    localidad_nombre = next((k for k, v in localidades_dict.items() if v == localidad_actual), "") if localidad_actual else ""
                    
                    localidad_sel = st.selectbox(
                        "🏘️ Población",
                        options=[""] + list(localidades_dict.keys()),
                        index=list(localidades_dict.keys()).index(localidad_nombre) + 1 if localidad_nombre else 0
                    )
                    localidad_id = localidades_dict.get(localidad_sel) if localidad_sel else None
                else:
                    st.selectbox("🏘️ Población", options=["Sin localidades"], disabled=True)
                    localidad_id = None
                    localidad_sel = ""
            else:
                st.selectbox("🏘️ Población", options=["Seleccione provincia"], disabled=True)
                localidad_id = None
                localidad_sel = ""
            
            telefono = st.text_input("📞 Teléfono", value=datos.get("telefono", ""))
        
        # Representante Legal
        st.markdown("#### 👤 Representante Legal")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            representante_tipo_documento = st.selectbox(
                "📄 Tipo Documento", 
                options=["", "NIF", "NIE", "PASAPORTE"],
                index=["", "NIF", "NIE", "PASAPORTE"].index(datos.get("representante_tipo_documento", "")) if datos.get("representante_tipo_documento") in ["", "NIF", "NIE", "PASAPORTE"] else 0
            )
        
        with col2:
            representante_numero_documento = st.text_input("🆔 Nº Documento", value=datos.get("representante_numero_documento", ""))
        
        with col3:
            representante_nombre_apellidos = st.text_input("👤 Nombre y Apellidos", value=datos.get("representante_nombre_apellidos", ""))
        
        # Notificaciones
        st.markdown("#### 📧 Notificaciones")
        email_notificaciones = st.text_input("📧 Email", value=datos.get("email_notificaciones", datos.get("email", "")))
        
        # Contrato de Encomienda
        st.markdown("#### 📋 Contrato de Encomienda")
        fecha_contrato_encomienda = st.date_input(
            "📅 Fecha Contrato Encomienda", 
            value=datos.get("fecha_contrato_encomienda") if datos.get("fecha_contrato_encomienda") else date.today()
        )
        
        # =========================
        # BLOQUE CARACTERÍSTICAS
        # =========================
        st.markdown("### ⚙️ Características")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nueva_creacion = st.checkbox("🆕 Nueva creación", value=datos.get("nueva_creacion", False))
            representacion_legal_trabajadores = st.checkbox(
                "👥 ¿Existe Representación Legal de las Personas Trabajadoras?", 
                value=datos.get("representacion_legal_trabajadores", False)
            )
            plantilla_media_anterior = st.number_input(
                "👥 Plantilla media del año anterior", 
                min_value=0, 
                value=datos.get("plantilla_media_anterior", 0)
            )
        
        with col2:
            es_pyme = st.checkbox("🏢 PYME", value=datos.get("es_pyme", True))
            voluntad_acumular_credito = st.checkbox(
                "💰 ¿Voluntad de acumular crédito de formación?",
                value=datos.get("voluntad_acumular_credito", False)
            )
            tiene_erte = st.checkbox("⚠️ ERTE", value=datos.get("tiene_erte", False))
        
        # Campos de módulos solo para admin
        if session_state.role == "admin":
            st.markdown("### 🔧 Configuración de Módulos")
            col1, col2 = st.columns(2)
            
            with col1:
                formacion_activo = st.checkbox("📚 Formación", value=datos.get("formacion_activo", True))
                iso_activo = st.checkbox("📋 ISO 9001", value=datos.get("iso_activo", False))
            
            with col2:
                rgpd_activo = st.checkbox("🛡️ RGPD", value=datos.get("rgpd_activo", False))
                docu_avanzada_activo = st.checkbox("📁 Doc. Avanzada", value=datos.get("docu_avanzada_activo", False))
        else:
            formacion_activo = datos.get("formacion_activo", True)
            iso_activo = datos.get("iso_activo", False)
            rgpd_activo = datos.get("rgpd_activo", False)
            docu_avanzada_activo = datos.get("docu_avanzada_activo", False)
        
        # Validaciones
        errores = []
        if not nombre:
            errores.append("Razón Social requerida")
        if not cif or not cif_valido:
            errores.append("CIF válido requerido")
        if not fecha_contrato_encomienda:
            errores.append("Fecha contrato requerida")
        if len(st.session_state[cuentas_key]) == 0:
            errores.append("Al menos una cuenta de cotización")
        
        # Mostrar errores
        if errores:
            st.error(f"⚠️ Faltan campos: {', '.join(errores)}")
        
        # Botones de acción
        st.markdown("---")
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        
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
                rgpd_activo, docu_avanzada_activo, st.session_state[cuentas_key],
                provincia_sel, localidad_sel, empresas_service, session_state, es_creacion
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
    
    # Gestión de cuentas de cotización FUERA del formulario
    st.markdown("#### 🏦 Cuentas de Cotización")
    mostrar_gestion_cuentas(cuentas_key)

def mostrar_gestion_cuentas(cuentas_key):
    """Gestión de cuentas de cotización usando st.popover."""
    
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
    
    # Botón para añadir nueva cuenta usando popover
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
                             rgpd_activo, docu_avanzada_activo, cuentas_cotizacion,
                             provincia_sel, localidad_sel, empresas_service, session_state, es_creacion):
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
                guardar_cuentas_cotizacion(empresas_service.supabase, empresa_id, cuentas_cotizacion)
                st.rerun()
            else:
                st.error("❌ Error al crear la empresa cliente")
        else:
            success = empresas_service.update_empresa_con_jerarquia(datos["id"], datos_empresa)
            if success:
                st.success("✅ Empresa actualizada correctamente")
                # Actualizar cuentas
                actualizar_cuentas_cotizacion(empresas_service.supabase, datos["id"], cuentas_cotizacion)
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
    
    # Tabs principales usando Streamlit 1.49
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
            """)
    elif session_state.role == "gestor":
        with st.expander("ℹ️ Información para Gestores"):
            st.markdown("""
            **📋 Formulario FUNDAE completo:**
            - ✅ Todos los campos requeridos por FUNDAE para formación bonificada
            - 🔄 Selector automático provincia → localidad (se actualiza al cambiar)
            - 🔢 Códigos CNAE con búsqueda integrada
            - 🏦 Gestión interactiva de cuentas (usar botón "➕ Añadir Cuenta")
            - ⚡ Validación CIF en tiempo real
            
            **⚠️ Limitaciones para gestores:**
            - 🔒 Razón Social y CIF solo editables en creación
            - 👥 Solo pueden crear empresas "Cliente de Gestora"  
            - 🚫 No pueden modificar configuración de módulos
            """)

if __name__ == "__main__":
    pass
