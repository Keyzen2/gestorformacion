import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import validar_dni_cif, export_csv
from services.empresas_service import get_empresas_service

# Configuración de jerarquía
TIPOS_EMPRESA = {
    "CLIENTE_SAAS": "Cliente SaaS Directo",
    "GESTORA": "Gestora de Formación", 
    "CLIENTE_GESTOR": "Cliente de Gestora"
}

@st.cache_data(ttl=3600)  # Cache por 1 hora
def cargar_provincias(supabase):
    """Carga lista de provincias."""
    try:
        result = supabase.table("provincias").select("id, nombre").order("nombre").execute()
        return {prov["nombre"]: prov["id"] for prov in result.data or []}
    except:
        return {}

@st.cache_data(ttl=3600)
def cargar_localidades(supabase, provincia_id):
    """Carga localidades de una provincia."""
    try:
        result = supabase.table("localidades").select("id, nombre").eq("provincia_id", provincia_id).order("nombre").execute()
        return {loc["nombre"]: loc["id"] for loc in result.data or []}
    except:
        return {}

@st.cache_data(ttl=3600)
def cargar_sectores(supabase):
    """Carga sectores empresariales."""
    try:
        result = supabase.table("sectores_empresariales").select("nombre").order("nombre").execute()
        return [sector["nombre"] for sector in result.data or []]
    except:
        return ["Comercio", "Industria", "Servicios", "Construcción", "Tecnología"]

@st.cache_data(ttl=3600)
def cargar_cnae(supabase):
    """Carga códigos CNAE."""
    try:
        result = supabase.table("codigos_cnae").select("codigo, descripcion").order("codigo").execute()
        return {f"{cnae['codigo']} - {cnae['descripcion']}": cnae['codigo'] for cnae in result.data or []}
    except:
        return {}

def mostrar_metricas_empresas(empresas_service, session_state):
    """Muestra métricas con información jerárquica."""
    try:
        metricas = empresas_service.get_estadisticas_empresas()
        
        if session_state.role == "admin":
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Empresas", metricas.get("total_empresas", 0))
            with col2:
                st.metric("Nuevas (30 días)", metricas.get("nuevas_mes", 0))
            with col3:
                st.metric("Con Formación", metricas.get("con_formacion", 0))
            with col4:
                porcentaje = metricas.get("porcentaje_activas", 0)
                st.metric("% Activas", f"{porcentaje}%")
        
        elif session_state.role == "gestor":
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Mis Empresas Clientes", metricas.get("total_clientes", 0))
            with col2:
                st.metric("Nuevos (30 días)", metricas.get("nuevos_clientes_mes", 0))
            with col3:
                st.metric("Con Formación", metricas.get("clientes_con_formacion", 0))
            with col4:
                st.info(f"Gestora: {metricas.get('empresa_gestora', 'N/A')}")

    except Exception as e:
        st.error(f"Error al cargar métricas: {e}")

def mostrar_tabla_empresas(df_empresas, session_state):
    """Muestra tabla de empresas."""
    if df_empresas.empty:
        st.info("No hay empresas para mostrar")
        return None
    
    # Preparar datos para mostrar
    df_display = df_empresas.copy()
    
    # Columnas según rol
    if session_state.role == "admin":
        columnas = ["nombre_display", "cif", "tipo_display", "ciudad", "telefono", "email"]
        column_config = {
            "nombre_display": st.column_config.TextColumn("Razón Social", width="large"),
            "cif": st.column_config.TextColumn("CIF", width="small"),
            "tipo_display": st.column_config.TextColumn("Tipo", width="medium"),
            "ciudad": st.column_config.TextColumn("Ciudad", width="medium"),
            "telefono": st.column_config.TextColumn("Teléfono", width="medium"),
            "email": st.column_config.TextColumn("Email", width="large")
        }
    else:
        columnas = ["nombre_display", "cif", "ciudad", "telefono", "email"]
        column_config = {
            "nombre_display": st.column_config.TextColumn("Razón Social", width="large"),
            "cif": st.column_config.TextColumn("CIF", width="small"),
            "ciudad": st.column_config.TextColumn("Ciudad", width="medium"),
            "telefono": st.column_config.TextColumn("Teléfono", width="medium"),
            "email": st.column_config.TextColumn("Email", width="large")
        }
    
    # Tabla con selección
    evento = st.dataframe(
        df_display[columnas],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    # Retornar índice seleccionado
    if evento.selection.rows:
        return df_display.iloc[evento.selection.rows[0]]
    return None

def cargar_cuentas_cotizacion(supabase, empresa_id):
    """Carga cuentas de cotización de una empresa."""
    try:
        result = supabase.table("cuentas_cotizacion").select("*").eq("empresa_id", empresa_id).execute()
        return result.data or []
    except:
        return []

def mostrar_formulario_empresa(empresa_data, empresas_service, session_state, es_creacion=False):
    """Formulario FUNDAE completo para empresas."""
    
    if es_creacion:
        st.subheader("Nueva Empresa Cliente")
        datos = {}
    else:
        st.subheader(f"Editar {empresa_data['nombre']}")
        datos = empresa_data.copy()
    
    # Cargar datos auxiliares
    provincias_dict = cargar_provincias(empresas_service.supabase)
    sectores_list = cargar_sectores(empresas_service.supabase)
    cnae_dict = cargar_cnae(empresas_service.supabase)
    
    form_key = f"form_empresa_{'crear' if es_creacion else 'editar'}_{datos.get('id', 'nuevo')}"
    with st.form(form_key, clear_on_submit=es_creacion):
        
        # =========================
        # BLOQUE IDENTIFICACIÓN
        # =========================
        st.markdown("### Identificación")
        
        # Datos principales
        st.markdown("#### Datos Principales")
        col1, col2 = st.columns(2)
        
        with col1:
            # Para gestores: nombre y CIF readonly en edición
            if session_state.role == "gestor" and not es_creacion:
                st.text_input("Razón Social", value=datos.get("nombre", ""), disabled=True)
                nombre = datos.get("nombre", "")
                st.text_input("CIF", value=datos.get("cif", ""), disabled=True)
                cif = datos.get("cif", "")
            else:
                nombre = st.text_input("Razón Social", value=datos.get("nombre", ""))
                cif = st.text_input("CIF", value=datos.get("cif", ""))
        
        with col2:
            sector = st.selectbox("Sector", options=[""] + sectores_list, 
                                index=sectores_list.index(datos.get("sector", "")) + 1 if datos.get("sector") in sectores_list else 0)
            convenio_referencia = st.text_input("Convenio de Referencia", value=datos.get("convenio_referencia", ""))
        
        # Código CNAE con búsqueda
        if cnae_dict:
            cnae_actual = datos.get("codigo_cnae", "")
            cnae_display = next((k for k, v in cnae_dict.items() if v == cnae_actual), "")
            codigo_cnae_sel = st.selectbox(
                "Código CNAE", 
                options=[""] + list(cnae_dict.keys()),
                index=list(cnae_dict.keys()).index(cnae_display) + 1 if cnae_display else 0,
                help="Busque escribiendo el código o descripción"
            )
            codigo_cnae = cnae_dict.get(codigo_cnae_sel, "") if codigo_cnae_sel else ""
        else:
            codigo_cnae = st.text_input("Código CNAE", value=datos.get("codigo_cnae", ""))
        
        # Domicilio Social
        st.markdown("#### Domicilio Social")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            calle = st.text_input("Calle", value=datos.get("calle", ""))
            numero = st.text_input("Número", value=datos.get("numero", ""))
        
        with col2:
            codigo_postal = st.text_input("Código Postal", value=datos.get("codigo_postal", ""))
            
            # Selector de provincia
            provincia_actual = datos.get("provincia_id")
            if provincia_actual and provincias_dict:
                provincia_nombre = next((k for k, v in provincias_dict.items() if v == provincia_actual), "")
            else:
                provincia_nombre = ""
            
            provincia_sel = st.selectbox(
                "Provincia", 
                options=[""] + list(provincias_dict.keys()),
                index=list(provincias_dict.keys()).index(provincia_nombre) + 1 if provincia_nombre else 0
            )
            provincia_id = provincias_dict.get(provincia_sel) if provincia_sel else None
        
        with col3:
            # Selector de localidad (depende de provincia)
            if provincia_id:
                localidades_dict = cargar_localidades(empresas_service.supabase, provincia_id)
                localidad_actual = datos.get("localidad_id")
                if localidad_actual and localidades_dict:
                    localidad_nombre = next((k for k, v in localidades_dict.items() if v == localidad_actual), "")
                else:
                    localidad_nombre = ""
                
                localidad_sel = st.selectbox(
                    "Población",
                    options=[""] + list(localidades_dict.keys()),
                    index=list(localidades_dict.keys()).index(localidad_nombre) + 1 if localidad_nombre else 0
                )
                localidad_id = localidades_dict.get(localidad_sel) if localidad_sel else None
            else:
                st.selectbox("Población", options=["Seleccione provincia primero"], disabled=True)
                localidad_id = None
            
            telefono = st.text_input("Teléfono", value=datos.get("telefono", ""))
        
        # Representante Legal
        st.markdown("#### Representante Legal")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            representante_tipo_documento = st.selectbox(
                "Tipo Documento", 
                options=["", "NIF", "NIE", "PASAPORTE"],
                index=["", "NIF", "NIE", "PASAPORTE"].index(datos.get("representante_tipo_documento", ""))
            )
        
        with col2:
            representante_numero_documento = st.text_input("Nº Documento", value=datos.get("representante_numero_documento", ""))
        
        with col3:
            representante_nombre_apellidos = st.text_input("Nombre y Apellidos", value=datos.get("representante_nombre_apellidos", ""))
        
        # Notificaciones
        st.markdown("#### Notificaciones")
        email_notificaciones = st.text_input("Email", value=datos.get("email_notificaciones", datos.get("email", "")))
        
        # Contrato de Encomienda
        st.markdown("#### Contrato de Encomienda")
        fecha_contrato_encomienda = st.date_input(
            "Fecha Contrato Encomienda", 
            value=datos.get("fecha_contrato_encomienda") if datos.get("fecha_contrato_encomienda") else date.today()
        )
        
        # =========================
        # BLOQUE CARACTERÍSTICAS
        # =========================
        st.markdown("### Características")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nueva_creacion = st.checkbox("Nueva creación", value=datos.get("nueva_creacion", False))
            representacion_legal_trabajadores = st.checkbox(
                "¿Existe Representación Legal de las Personas Trabajadoras?", 
                value=datos.get("representacion_legal_trabajadores", False)
            )
            plantilla_media_anterior = st.number_input(
                "Plantilla media de la empresa en el año anterior", 
                min_value=0, 
                value=datos.get("plantilla_media_anterior", 0)
            )
        
        with col2:
            es_pyme = st.checkbox("PYME", value=datos.get("es_pyme", True))
            voluntad_acumular_credito = st.checkbox(
                "¿Manifiesta la empresa la voluntad de acumular su crédito de formación con el siguiente o los dos siguientes ejercicios?",
                value=datos.get("voluntad_acumular_credito", False)
            )
            tiene_erte = st.checkbox("ERTE", value=datos.get("tiene_erte", False))
        
        # Cuentas de Cotización
        st.markdown("#### Cuentas de Cotización")
        
        if not es_creacion:
            cuentas_existentes = cargar_cuentas_cotizacion(empresas_service.supabase, datos.get("id"))
            if cuentas_existentes:
                st.write("Cuentas existentes:")
                for cuenta in cuentas_existentes:
                    principal_text = " (Principal)" if cuenta.get("es_principal") else ""
                    st.text(f"• {cuenta['numero_cuenta']}{principal_text}")
        
        cuenta_cotizacion_nueva = st.text_input("Nueva Cuenta de Cotización", placeholder="Opcional: agregar nueva cuenta")
        es_principal_nueva = st.checkbox("Marcar como cuenta principal") if cuenta_cotizacion_nueva else False
        
        # Campos de módulos solo para admin
        if session_state.role == "admin":
            st.markdown("### Configuración de Módulos")
            col1, col2 = st.columns(2)
            
            with col1:
                formacion_activo = st.checkbox("Formación", value=datos.get("formacion_activo", True))
                iso_activo = st.checkbox("ISO 9001", value=datos.get("iso_activo", False))
            
            with col2:
                rgpd_activo = st.checkbox("RGPD", value=datos.get("rgpd_activo", False))
                docu_avanzada_activo = st.checkbox("Doc. Avanzada", value=datos.get("docu_avanzada_activo", False))
        else:
            formacion_activo = datos.get("formacion_activo", True)
            iso_activo = datos.get("iso_activo", False)
            rgpd_activo = datos.get("rgpd_activo", False)
            docu_avanzada_activo = datos.get("docu_avanzada_activo", False)
        
        # Botones de acción
        st.markdown("---")
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        
        with col_btn1:
            submitted = st.form_submit_button("Guardar", type="primary", use_container_width=True)
        
        with col_btn2:
            if not es_creacion and session_state.role == "admin":
                eliminar = st.form_submit_button("Eliminar", type="secondary", use_container_width=True)
            else:
                eliminar = False
        
        # Procesar formulario
        if submitted:
            # Validaciones básicas
            errores = []
            if not nombre or not cif:
                errores.append("Razón Social y CIF son obligatorios")
            
            if not validar_dni_cif(cif):
                errores.append("El CIF no es válido")
            
            if not fecha_contrato_encomienda:
                errores.append("Fecha de Contrato de Encomienda es obligatoria")
            
            if representante_tipo_documento and not representante_numero_documento:
                errores.append("Si especifica tipo de documento del representante, debe indicar el número")
            
            if errores:
                for error in errores:
                    st.error(f"⚠️ {error}")
                return False
            
            # Preparar datos
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
                "representante_tipo_documento": representante_tipo_documento if representante_tipo_documento else None,
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
            
            # DEBUG: Mostrar datos que se van a enviar
            with st.expander("Debug - Datos a enviar", expanded=False):
                st.json(datos_empresa)
            
            try:
                if es_creacion:
                    # Crear nueva empresa
                    success, empresa_id = empresas_service.crear_empresa_con_jerarquia(datos_empresa)
                    if success:
                        st.success(f"✅ Empresa cliente creada correctamente (ID: {empresa_id})")
                        
                        # Agregar cuenta de cotización si se especificó
                        if cuenta_cotizacion_nueva:
                            try:
                                empresas_service.supabase.table("cuentas_cotizacion").insert({
                                    "empresa_id": empresa_id,
                                    "numero_cuenta": cuenta_cotizacion_nueva,
                                    "es_principal": es_principal_nueva
                                }).execute()
                                st.success("Cuenta de cotización agregada")
                            except Exception as e:
                                st.warning(f"Empresa creada pero error al agregar cuenta: {e}")
                        
                        st.rerun()
                    else:
                        st.error("❌ Error al crear la empresa cliente")
                else:
                    # Actualizar empresa existente
                    success = empresas_service.update_empresa_con_jerarquia(datos["id"], datos_empresa)
                    if success:
                        st.success("✅ Empresa actualizada correctamente")
                        
                        # Agregar nueva cuenta de cotización si se especificó
                        if cuenta_cotizacion_nueva:
                            try:
                                empresas_service.supabase.table("cuentas_cotizacion").insert({
                                    "empresa_id": datos["id"],
                                    "numero_cuenta": cuenta_cotizacion_nueva,
                                    "es_principal": es_principal_nueva
                                }).execute()
                                st.success("Nueva cuenta de cotización agregada")
                            except Exception as e:
                                st.warning(f"Empresa actualizada pero error al agregar cuenta: {e}")
                        
                        st.rerun()
                    else:
                        st.error("❌ Error al actualizar la empresa")
                        
            except Exception as e:
                st.error(f"❌ Error procesando empresa: {e}")
                st.exception(e)
                return False
    
    return False

def main(supabase, session_state):
    st.title("Gestión de Empresas FUNDAE")
    
    if session_state.role == "admin":
        st.caption("Administración completa de empresas con datos FUNDAE")
    else:
        st.caption("Gestión de empresas clientes con formulario FUNDAE completo")

    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.warning("No tienes permisos para acceder a esta sección")
        return

    # Inicializar servicio
    empresas_service = get_empresas_service(supabase, session_state)
    
    # Cargar datos con spinner
    with st.spinner("Cargando empresas..."):
        try:
            df_empresas = empresas_service.get_empresas_con_jerarquia()
        except Exception as e:
            st.error(f"Error al cargar empresas: {e}")
            return

    # Métricas
    mostrar_metricas_empresas(empresas_service, session_state)
    st.divider()
    
    # Filtros de búsqueda
    st.markdown("### Buscar y Filtrar")
    col1, col2 = st.columns(2)
    
    with col1:
        query = st.text_input("Buscar por razón social, CIF o ciudad", placeholder="Escribe para buscar...")
    
    with col2:
        if session_state.role == "admin":
            tipo_filter = st.selectbox("Filtrar por tipo", 
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
            label="Exportar CSV",
            data=df_filtered.to_csv(index=False),
            file_name=f"empresas_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    st.divider()
    
    # Tabs principales usando Streamlit 1.49
    tab1, tab2 = st.tabs(["Lista de Empresas", "Nueva Empresa"])
    
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
            st.info("No tienes permisos para crear empresas")
    
    # Vista jerárquica para admin
    if session_state.role == "admin":
        st.divider()
        with st.expander("Vista Jerárquica", expanded=False):
            try:
                arbol = empresas_service.get_arbol_empresas()
                if not arbol.empty:
                    for _, empresa in arbol.iterrows():
                        nivel = empresa.get("nivel_jerarquico", 1)
                        if nivel == 1:
                            st.markdown(f"**{empresa['nombre']}** ({empresa.get('tipo_empresa', 'N/A')})")
                        else:
                            st.markdown(f"  └── {empresa['nombre']} ({empresa.get('tipo_empresa', 'N/A')})")
                else:
                    st.info("No hay estructura jerárquica para mostrar")
            except Exception as e:
                st.error(f"Error cargando vista jerárquica: {e}")
    
    # Información adicional
    st.divider()
    if session_state.role == "admin":
        with st.expander("Información sobre FUNDAE y Jerarquía"):
            st.markdown("""
            **Campos FUNDAE obligatorios:**
            - Datos de identificación completos (CIF, razón social, sector, CNAE)
            - Domicilio social completo con provincia y localidad
            - Representante legal con documentación
            - Características de la empresa (plantilla, PYME, etc.)
            - Al menos una cuenta de cotización
            
            **Jerarquía Multi-Tenant:**
            - **Cliente SaaS**: Empresas que contratan directamente
            - **Gestora**: Clientes que gestionan otras empresas
            - **Cliente Gestor**: Empresas gestionadas por una gestora
            """)
    elif session_state.role == "gestor":
        with st.expander("Información para Gestores"):
            st.markdown("""
            **Formulario FUNDAE completo:**
            - Todos los campos requeridos por FUNDAE para formación bonificada
            - Selector inteligente de provincia → localidad
            - Códigos CNAE con búsqueda
            - Gestión de cuentas de cotización
            
            **Limitaciones para gestores:**
            - Razón Social y CIF solo editables en creación
            - Solo pueden crear empresas "Cliente de Gestora"
            - No pueden modificar configuración de módulos
            """)

if __name__ == "__main__":
    pass
