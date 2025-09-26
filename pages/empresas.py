import streamlit as st
import pandas as pd
import uuid
from datetime import datetime, date
from utils import validar_dni_cif, export_csv
from services.empresas_service import get_empresas_service

# Configuración de jerarquía
TIPOS_EMPRESA = {
    "CLIENTE_SAAS": "🏢 Cliente SaaS Directo",
    "GESTORA": "🎯 Gestora de Formación", 
    "CLIENTE_GESTOR": "👥 Cliente de Gestora"
}

@st.cache_data(ttl=300)
def cargar_provincias(_supabase):
    """Carga lista de provincias."""
    try:
        result = _supabase.table("provincias").select("id, nombre").order("nombre").execute()
        return {prov["nombre"]: prov["id"] for prov in result.data or []}
    except:
        return {}

@st.cache_data(ttl=300)
def cargar_localidades(_supabase, provincia_id):
    """Carga localidades de una provincia."""
    try:
        result = _supabase.table("localidades").select("id, nombre").eq("provincia_id", provincia_id).order("nombre").execute()
        return {loc["nombre"]: loc["id"] for loc in result.data or []}
    except:
        return {}

@st.cache_data(ttl=300)
def cargar_sectores(_supabase):
    """Carga sectores empresariales."""
    try:
        result = _supabase.table("sectores_empresariales").select("nombre").order("nombre").execute()
        sectores = [sector["nombre"] for sector in result.data or []]
        return sorted(list(set(sectores)))
    except:
        return ["🏭 Industria", "🏪 Comercio", "⚙️ Servicios", "🏗️ Construcción", "💻 Tecnología"]

@st.cache_data(ttl=300)
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
        
# =========================
# GUARDAR MÓDULOS
# =========================
def guardar_modulos(empresas_service, empresa_id,
                    formacion_activo, iso_activo, rgpd_activo, docu_avanzada_activo,
                    crm_activo, crm_inicio, crm_fin):
    """Actualiza los módulos básicos (tabla empresas) y CRM (tabla crm_empresas)."""
    try:
        # Normalizar fechas CRM (a ISO o None)
        crm_inicio_iso = crm_inicio.isoformat() if isinstance(crm_inicio, date) else (crm_inicio or None)
        crm_fin_iso = crm_fin.isoformat() if isinstance(crm_fin, date) else (crm_fin or None)

        # 1. Actualizar tabla empresas (booleans)
        empresas_service.supabase.table("empresas").update({
            "formacion_activo": formacion_activo,
            "iso_activo": iso_activo,
            "rgpd_activo": rgpd_activo,
            "docu_avanzada_activo": docu_avanzada_activo,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", empresa_id).execute()

        # 2. Actualizar / insertar en crm_empresas
        if crm_activo:
            registro = empresas_service.supabase.table("crm_empresas").select("id").eq("empresa_id", empresa_id).execute()
            if registro.data:
                # update
                empresas_service.supabase.table("crm_empresas").update({
                    "crm_activo": True,
                    "crm_inicio": crm_inicio_iso,
                    "crm_fin": crm_fin_iso,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("empresa_id", empresa_id).execute()
            else:
                # insert
                empresas_service.supabase.table("crm_empresas").insert({
                    "empresa_id": empresa_id,
                    "crm_activo": True,
                    "crm_inicio": crm_inicio_iso,
                    "crm_fin": crm_fin_iso,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
        else:
            # si lo desactiva → update a false (mantiene el registro)
            empresas_service.supabase.table("crm_empresas").update({
                "crm_activo": False,
                "crm_inicio": None,
                "crm_fin": None,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("empresa_id", empresa_id).execute()

        return True
    except Exception as e:
        st.error(f"❌ Error guardando módulos: {e}")
        return False
        
def exportar_empresas(empresas_service, session_state):
    """Exporta empresas visibles a CSV."""
    try:
        df = empresas_service.get_empresas_con_jerarquia()
        if session_state.role == "gestor":
            empresa_id = session_state.user.get("empresa_id")
            df = df[(df["id"] == empresa_id) | (df["empresa_matriz_id"] == empresa_id)]
        
        if df.empty:
            st.warning("⚠️ No hay empresas para exportar")
            return

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Exportar CSV",
            data=csv,
            file_name=f"empresas_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    except Exception as e:
        st.error(f"❌ Error exportando empresas: {e}")
        
def mostrar_acciones_empresa(empresa_sel, empresas_service, session_state):
    """Muestra acciones disponibles para la empresa seleccionada."""
    if empresa_sel is None or empresa_sel.empty or session_state.role != "admin":
        return
    
    st.markdown("#### ⚙️ Acciones Rápidas")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Botón para convertir a GESTORA
        if empresas_service.puede_convertir_a_gestora(empresa_sel["id"]):
            if st.button(
                "🔄 Convertir a GESTORA", 
                key=f"convertir_{empresa_sel['id']}", 
                help="Convierte esta empresa CLIENTE_SAAS en GESTORA para que pueda gestionar otras empresas"
            ):
                if st.session_state.get("confirmar_conversion"):
                    if empresas_service.convertir_a_gestora(empresa_sel["id"]):
                        del st.session_state["confirmar_conversion"]
                        st.rerun()
                else:
                    st.session_state["confirmar_conversion"] = True
                    st.warning("⚠️ Presiona nuevamente para confirmar la conversión")
        else:
            tipo_actual = empresa_sel.get("tipo_empresa", "")
            if tipo_actual == "GESTORA":
                st.success("✅ Ya es GESTORA")
            elif tipo_actual == "CLIENTE_GESTOR":
                st.info("ℹ️ Es cliente de gestora")
            else:
                st.info("ℹ️ No se puede convertir")
    
    with col2:
        # Información del tipo actual
        tipo_display = TIPOS_EMPRESA.get(empresa_sel.get("tipo_empresa", ""), "Desconocido")
        st.info(f"**Tipo Actual:** {tipo_display}")
    
    with col3:
        # Mostrar empresas cliente si es gestora
        if empresa_sel.get("tipo_empresa") == "GESTORA":
            clientes = empresas_service.get_empresas_clientes_gestor(empresa_sel["id"])
            st.metric("Empresas Cliente", len(clientes))
            
def importar_empresas(empresas_service, session_state):
    """Importa empresas desde un archivo CSV/XLSX con plantilla descargable."""
    uploaded = st.file_uploader("📤 Subir archivo CSV/XLSX", type=["csv", "xlsx"], accept_multiple_files=False)
    
    # 📑 Botón para descargar plantilla de ejemplo
    ejemplo_df = pd.DataFrame([{
        "nombre": "Ejemplo S.L.",
        "cif": "B12345678",
        "telefono": "950123456",
        "email": "ejemplo@empresa.com",
        "direccion": "Calle Mayor 1",
        "ciudad": "Almería",
        "provincia": "Almería",
        "codigo_postal": "04001",
        "sector": "Servicios",
        "convenio_referencia": "Convenio Oficinas",
        "codigo_cnae": "6201",
        "empresa_matriz_id": "",
        "tipo_empresa": "CLIENTE_SAAS",
        "nivel_jerarquico": 1
    }])

    st.download_button(
        "📑 Descargar plantilla XLSX",
        data=ejemplo_df.to_excel(index=False, engine="openpyxl"),
        file_name="plantilla_empresas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    if not uploaded:
        return
    
    try:
        if uploaded.name.endswith(".csv"):
            df = pd.read_csv(uploaded, dtype=str)
        else:
            df = pd.read_excel(uploaded, dtype=str)

        st.success(f"✅ {len(df)} filas cargadas desde {uploaded.name}")
        st.dataframe(df.head(10), use_container_width=True)

        if st.button("🚀 Importar empresas", type="primary", use_container_width=True):
            errores = []
            for _, fila in df.iterrows():
                try:
                    datos = {
                        "nombre": fila.get("nombre"),
                        "cif": fila.get("cif"),
                        "telefono": fila.get("telefono"),
                        "email": fila.get("email"),
                        "direccion": fila.get("direccion"),
                        "ciudad": fila.get("ciudad"),
                        "provincia": fila.get("provincia"),
                        "codigo_postal": fila.get("codigo_postal"),
                        "sector": fila.get("sector"),
                        "convenio_referencia": fila.get("convenio_referencia"),
                        "codigo_cnae": fila.get("codigo_cnae"),
                        "empresa_matriz_id": fila.get("empresa_matriz_id") or None,
                        "tipo_empresa": fila.get("tipo_empresa") or "CLIENTE_SAAS",
                        "nivel_jerarquico": int(fila.get("nivel_jerarquico") or 1),
                        "created_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat()
                    }
                    empresas_service.crear_empresa_con_jerarquia(datos)
                except Exception as ex:
                    errores.append(str(ex))

            if errores:
                st.error(f"⚠️ Errores al importar:\n{errores}")
            else:
                st.success("✅ Importación completada")
                st.rerun()
    except Exception as e:
        st.error(f"❌ Error importando empresas: {e}")

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

def mostrar_tabla_empresas(df_empresas, session_state, titulo_tabla="📋 Lista de Empresas", empresas_service=None):
    """Muestra tabla de empresas con filtros fijos, paginación y exportación."""
    if df_empresas.empty:
        st.info("📋 No hay empresas para mostrar")
        return None

    st.markdown(f"### {titulo_tabla}")

    # 🔎 Filtros fijos arriba de la tabla
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_nombre = st.text_input("🏢 Nombre contiene")
    with col2:
        filtro_cif = st.text_input("📄 CIF contiene")
    with col3:
        filtro_ciudad = st.text_input("📍 Ciudad contiene")

    if filtro_nombre:
        df_empresas = df_empresas[df_empresas["nombre"].str.contains(filtro_nombre, case=False, na=False)]
    if filtro_cif:
        df_empresas = df_empresas[df_empresas["cif"].str.contains(filtro_cif, case=False, na=False)]
    if filtro_ciudad:
        df_empresas = df_empresas[df_empresas["ciudad"].str.contains(filtro_ciudad, case=False, na=False)]

    df_empresas = df_empresas.copy()

    for campo, label in [
        ("formacion_activo", "📚 Formación"),
        ("iso_activo", "📋 ISO"),
        ("rgpd_activo", "🛡️ RGPD"),
        ("docu_avanzada_activo", "📁 Doc. Avanzada"),
        ("crm_activo", "📈 CRM"),
    ]:
        if campo in df_empresas.columns:
            df_empresas[label] = df_empresas[campo].apply(lambda x: "✅" if x else "❌")

    # 📊 Mostrar tabla con selección
    columnas = ["nombre", "cif", "ciudad", "telefono", "email"]
    if session_state.role == "admin":
        columnas.insert(2, "tipo_empresa")

    evento = st.dataframe(
        df_empresas[columnas],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    # 🔢 Controles de paginación y registros por página (debajo de la tabla)
    st.markdown("### 📑 Navegación")
    col_pag1, col_pag2 = st.columns([1, 3])
    with col_pag1:
        page_size = st.selectbox("Registros por página", [10, 20, 50, 100], index=1)
    with col_pag2:
        total_rows = len(df_empresas)
        total_pages = (total_rows // page_size) + (1 if total_rows % page_size else 0)
        page_number = st.number_input("Página", min_value=1, max_value=max(total_pages, 1), step=1, value=1)

    start_idx = (page_number - 1) * page_size
    end_idx = start_idx + page_size
    df_paged = df_empresas.iloc[start_idx:end_idx]

    # ✅ Botones export/import
    if empresas_service is not None:
        col_exp, col_imp = st.columns([1, 1])
        with col_exp:
            exportar_empresas(empresas_service, session_state)
        with col_imp:
            importar_empresas(empresas_service, session_state)

    if evento.selection.rows:
        return df_paged.iloc[evento.selection.rows[0]]
    return None

def mostrar_mi_empresa(empresas_service, session_state):
    """CORREGIDO: Muestra los datos de la empresa del gestor con posibilidad de edición real."""
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
        
        # CORREGIDO: Mostrar formulario de edición real
        if st.session_state.get("editando_mi_empresa"):
            with st.container(border=True):
                st.markdown("#### ✏️ Editando Mi Empresa")
                
                # Formulario específico para "Mi Empresa"
                with st.form("editar_mi_empresa", clear_on_submit=False):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        telefono = st.text_input("📞 Teléfono", value=empresa_info.get("telefono", ""))
                        email = st.text_input("📧 Email", value=empresa_info.get("email", ""))
                        direccion = st.text_input("🏠 Dirección", value=empresa_info.get("direccion", ""))
                    
                    with col2:
                        ciudad = st.text_input("📍 Ciudad", value=empresa_info.get("ciudad", ""))
                        provincia = st.text_input("🗺️ Provincia", value=empresa_info.get("provincia", ""))
                        codigo_postal = st.text_input("📮 Código Postal", value=empresa_info.get("codigo_postal", ""))
                    
                    # Datos del representante (readonly para gestor)
                    st.markdown("#### 👤 Representante Legal (Solo lectura)")
                    col3, col4 = st.columns(2)
                    with col3:
                        st.text_input("Nombre y Apellidos", value=empresa_info.get("representante_nombre_apellidos", ""), disabled=True)
                    with col4:
                        st.text_input("Documento", value=empresa_info.get("representante_numero_documento", ""), disabled=True)
                    
                    # Botones
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        submitted = st.form_submit_button("💾 Guardar Cambios", type="primary")
                    with col_btn2:
                        cancelled = st.form_submit_button("❌ Cancelar")
                    
                    # CORREGIDO: Procesar guardado real
                    if submitted:
                        try:
                            datos_actualizados = {
                                "telefono": telefono,
                                "email": email,
                                "direccion": direccion,
                                "ciudad": ciudad,
                                "provincia": provincia,
                                "codigo_postal": codigo_postal,
                                "email_notificaciones": email,  # Compatibilidad
                                "updated_at": datetime.utcnow().isoformat()
                            }
                            
                            # Actualizar en base de datos
                            result = empresas_service.supabase.table("empresas").update(
                                datos_actualizados
                            ).eq("id", empresa_info["id"]).execute()
                            
                            if result.data:
                                st.success("✅ Información actualizada correctamente")
                                st.session_state["editando_mi_empresa"] = False
                                # Limpiar cache
                                empresas_service.get_empresas_con_jerarquia.clear()
                                cargar_provincias.clear()
                                cargar_localidades.clear()
                                st.rerun()
                            else:
                                st.error("❌ Error al actualizar la información")
                        except Exception as e:
                            st.error(f"❌ Error guardando cambios: {e}")
                    
                    if cancelled:
                        st.session_state["editando_mi_empresa"] = False
                        st.rerun()
            
    except Exception as e:
        st.error(f"❌ Error cargando información de tu empresa: {e}")

def mostrar_campos_conectados_provincia_localidad(empresas_service, datos, key_suffix="", disabled=False):
    """
    Campos conectados provincia-localidad usando IDs reales,
    pero manteniendo provincia/ciudad como texto para compatibilidad.
    """
    # Cargar provincias
    provincias_dict = cargar_provincias(empresas_service.supabase)  # {nombre: id}
    provincias_inv = {v: k for k, v in provincias_dict.items()}     # {id: nombre}

    # Provincia inicial (preferir provincia_id si existe)
    provincia_id = datos.get("provincia_id")
    provincia_sel = provincias_inv.get(provincia_id, datos.get("provincia", ""))

    provincia_sel = st.selectbox(
        "🗺️ Provincia",
        options=[""] + list(provincias_dict.keys()),
        index=list(provincias_dict.keys()).index(provincia_sel) + 1 if provincia_sel in provincias_dict else 0,
        key=f"prov_select_{key_suffix}",
        disabled=disabled
    )

    provincia_id = provincias_dict.get(provincia_sel) if provincia_sel else None

    # Localidades según provincia
    localidad_sel, localidad_id = "", None
    if provincia_id:
        localidades_dict = cargar_localidades(empresas_service.supabase, provincia_id)  # {nombre: id}
        localidades_inv = {v: k for k, v in localidades_dict.items()}

        localidad_id = datos.get("localidad_id")
        localidad_sel = localidades_inv.get(localidad_id, datos.get("ciudad", ""))

        localidad_sel = st.selectbox(
            "🏘️ Población",
            options=[""] + list(localidades_dict.keys()),
            index=list(localidades_dict.keys()).index(localidad_sel) + 1 if localidad_sel in localidades_dict else 0,
            key=f"loc_select_{key_suffix}",
            disabled=disabled
        )
        localidad_id = localidades_dict.get(localidad_sel) if localidad_sel else None
    else:
        st.selectbox("🏘️ Población", options=["Seleccione provincia"], disabled=True, key=f"loc_disabled_{key_suffix}")

    return provincia_sel, localidad_sel, provincia_id, localidad_id

def inicializar_cuentas_cotizacion(form_id, empresas_service, empresa_id=None):
    """NUEVA: Inicializar cuentas en session_state"""
    cuentas_key = f"cuentas_{form_id}"
    if cuentas_key not in st.session_state:
        if empresa_id:
            try:
                result = empresas_service.supabase.table("cuentas_cotizacion").select("*").eq("empresa_id", empresa_id).execute()
                st.session_state[cuentas_key] = result.data or []
            except:
                st.session_state[cuentas_key] = []
        else:
            st.session_state[cuentas_key] = []
    return cuentas_key

def mostrar_gestion_cuentas_en_formulario(cuentas_key):
    """CORREGIDO: Gestión de cuentas que NO resetea el formulario y usa st.rerun() en Streamlit 1.49"""
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
                if st.button("🌟", key=f"principal_{cuentas_key}_{i}", 
                           disabled=cuenta.get("es_principal", False),
                           help="Marcar como principal"):
                    for j, c in enumerate(cuentas):
                        c["es_principal"] = (j == i)
                    st.rerun()
            with col3:
                if st.button("🗑️", key=f"eliminar_{cuentas_key}_{i}",
                           help="Eliminar cuenta"):
                    cuentas.pop(i)
                    st.rerun()
                    break
    else:
        st.info("📝 No hay cuentas de cotización configuradas")
    
    # Campos para añadir nueva cuenta (dentro del formulario)
    st.markdown("**Añadir nueva cuenta:**")
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        nueva_cuenta = st.text_input("Número de cuenta", placeholder="Ej: 281234567890", key=f"nueva_cuenta_{cuentas_key}")
    
    with col2:
        es_principal = st.checkbox("Principal", key=f"es_principal_{cuentas_key}")
    
    with col3:
        if st.button("➕ Añadir", key=f"añadir_{cuentas_key}"):
            if nueva_cuenta.strip():
                if es_principal:
                    for cuenta in cuentas:
                        cuenta["es_principal"] = False
                
                cuentas.append({
                    "numero_cuenta": nueva_cuenta.strip(),
                    "es_principal": es_principal
                })
                
                st.success("✅ Cuenta añadida correctamente")
                st.rerun()
            else:
                st.error("⚠️ Introduce un número de cuenta")

def mostrar_formulario_empresa(empresa_data, empresas_service, session_state, es_creacion=False, key_suffix="", solo_datos_basicos=False):
    """CORREGIDO: Formulario FUNDAE completo con validaciones que no bloquean el botón."""

    if es_creacion:
        st.subheader("➕ Nueva Empresa Cliente")
        datos = {}
    else:
        if not key_suffix:
            st.subheader(f"✏️ Editar {empresa_data['nombre']}")
        datos = empresa_data.copy()

    # ID único para el formulario
    form_id = f"empresa_{datos.get('id', 'nueva')}_{'crear' if es_creacion else 'editar'}{key_suffix}"

    # CAMPOS CONECTADOS FUERA DEL FORMULARIO (solo si no es solo_datos_basicos)
    if not solo_datos_basicos:
        st.markdown("#### 🏠 Domicilio Social (Seleccione provincia y localidad)")
        provincia_sel, localidad_sel, provincia_id, localidad_id = mostrar_campos_conectados_provincia_localidad(
            empresas_service, datos, key_suffix=form_id
        )
        st.divider()
    else:
        provincia_sel, localidad_sel, provincia_id, localidad_id = None, None, None, None

    # Cargar datos auxiliares
    sectores_list = cargar_sectores(empresas_service.supabase)
    cnae_dict = cargar_cnae(empresas_service.supabase)

    # Cargar datos CRM si es necesario
    crm_data = {}
    if not es_creacion and datos.get("id") and not solo_datos_basicos:
        crm_data = cargar_crm_datos(empresas_service.supabase, datos["id"])

    # CORREGIDO: Inicializar cuentas sin resetear formulario
    if not solo_datos_basicos:
        cuentas_key = inicializar_cuentas_cotizacion(
            form_id,
            empresas_service,
            datos.get("id") if not es_creacion else None
        )

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
                st.text_input("🏢 Razón Social", value=datos.get("nombre") or "", disabled=True, key=f"{form_id}_nombre_readonly")
                nombre = datos.get("nombre") or ""
                st.text_input("📄 CIF", value=datos.get("cif") or "", disabled=True, key=f"{form_id}_cif_readonly")
                cif = datos.get("cif") or ""
            else:
                nombre = st.text_input("🏢 Razón Social", value=datos.get("nombre") or "", key=f"{form_id}_nombre")
                cif = st.text_input("📄 CIF", value=datos.get("cif") or "", key=f"{form_id}_cif")
        
        with col2:
            sector_val = (datos.get("sector") or "").strip()
            sector_idx = sectores_list.index(sector_val) + 1 if sector_val in sectores_list else 0
            sector = st.selectbox(
                "🏭 Sector",
                options=[""] + sectores_list,
                index=sector_idx,
                key=f"{form_id}_sector"
            )
            convenio_referencia = st.text_input(
                "📋 Convenio de Referencia",
                value=datos.get("convenio_referencia") or "",
                key=f"{form_id}_convenio"
            )
        # =========================
        # TIPO DE EMPRESA (Solo Admin en Creación)
        # =========================
        if session_state.role == "admin" and es_creacion:
            st.markdown("#### 🎯 Tipo de Empresa")
            
            tipo_empresa = st.selectbox(
                "Tipo de Empresa",
                options=["CLIENTE_SAAS", "GESTORA"],
                index=0,
                key=f"{form_id}_tipo_empresa",
                help="""
                - **CLIENTE_SAAS**: Empresa cliente final que usa directamente el sistema
                - **GESTORA**: Empresa que gestiona formación para otras empresas cliente
                """
            )
            
            if tipo_empresa == "GESTORA":
                st.info("💡 Las empresas GESTORA pueden crear y gestionar empresas cliente")
            else:
                st.info("💡 Las empresas CLIENTE_SAAS pueden usar todos los módulos del sistema")
                
        else:
            # Valores por defecto según el contexto
            if session_state.role == "admin" and not es_creacion:
                # En edición, mantener el tipo actual
                tipo_empresa = datos.get("tipo_empresa", "CLIENTE_SAAS")
            elif session_state.role == "gestor":
                # Gestores solo pueden crear CLIENTE_GESTOR
                tipo_empresa = "CLIENTE_GESTOR"
            else:
                tipo_empresa = "CLIENTE_SAAS"
        # Código CNAE
        if cnae_dict:
            cnae_actual = datos.get("codigo_cnae") or ""
            # Buscar la entrada completa que comience con el código actual
            cnae_display = ""
            if cnae_actual:
                cnae_display = next((k for k in cnae_dict.keys() if k.startswith(cnae_actual)), "")
            
            opciones_cnae = list(cnae_dict.keys())
            cnae_idx = opciones_cnae.index(cnae_display) + 1 if cnae_display in opciones_cnae else 0
            codigo_cnae_sel = st.selectbox(
                "🔢 Código CNAE",
                options=[""] + opciones_cnae,
                index=cnae_idx,
                key=f"{form_id}_cnae"
            )
            codigo_cnae = codigo_cnae_sel.split(" - ")[0] if codigo_cnae_sel else ""
        else:
            codigo_cnae = st.text_input("🔢 Código CNAE", value=datos.get("codigo_cnae") or "", key=f"{form_id}_cnae_input")
        
        # RESTO DE CAMPOS DEL DOMICILIO (no provincia/localidad que ya están fuera)
        st.markdown("#### 🏠 Resto del Domicilio")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            calle = st.text_input("🛣️ Calle", value=datos.get("calle") or "", key=f"{form_id}_calle")
            numero = st.text_input("🏠 Número", value=datos.get("numero") or "", key=f"{form_id}_numero")
        
        with col2:
            codigo_postal = st.text_input("📮 Código Postal", value=datos.get("codigo_postal") or "", key=f"{form_id}_cp")
            telefono = st.text_input("📞 Teléfono", value=datos.get("telefono") or "", key=f"{form_id}_telefono")
        
        with col3:
            st.info(f"**Provincia:** {provincia_sel if not solo_datos_basicos else datos.get('provincia', 'N/A')}")
            st.info(f"**Localidad:** {localidad_sel if not solo_datos_basicos else datos.get('ciudad', 'N/A')}")
        
        # Solo mostrar más campos si NO es solo_datos_basicos
        if not solo_datos_basicos:
            # Representante Legal
            st.markdown("#### 👤 Representante Legal")
            col1, col2, col3 = st.columns(3)
        
            with col1:
                tipo_doc_val = datos.get("representante_tipo_documento") or ""
                opciones_doc = ["", "NIF", "NIE", "PASAPORTE"]
                tipo_doc_idx = opciones_doc.index(tipo_doc_val) if tipo_doc_val in opciones_doc else 0
                representante_tipo_documento = st.selectbox(
                    "📄 Tipo Documento",
                    options=opciones_doc,
                    index=tipo_doc_idx,
                    key=f"{form_id}_tipo_doc"
                )
        
            with col2:
                representante_numero_documento = st.text_input(
                    "🆔 Nº Documento",
                    value=datos.get("representante_numero_documento") or "",
                    key=f"{form_id}_num_doc"
                )
        
            with col3:
                representante_nombre_apellidos = st.text_input(
                    "👤 Nombre y Apellidos",
                    value=datos.get("representante_nombre_apellidos") or "",
                    key=f"{form_id}_nombre_apellidos"
                )
        
            # Notificaciones
            st.markdown("#### 📧 Notificaciones")
            email_notificaciones = st.text_input(
                "📧 Email",
                value=datos.get("email_notificaciones") or datos.get("email") or "",
                key=f"{form_id}_email_notif"
            )
        
            # Contrato de Encomienda
            st.markdown("#### 📋 Contrato de Encomienda")
            fecha_contrato = datos.get("fecha_contrato_encomienda")
            fecha_contrato_encomienda = st.date_input(
                "📅 Fecha Contrato Encomienda",
                value=fecha_contrato if fecha_contrato else date.today(),
                key=f"{form_id}_fecha_contrato"
            )
        
            # =========================
            # BLOQUE CARACTERÍSTICAS
            # =========================
            st.markdown("### ⚙️ Características")
        
            col1, col2 = st.columns(2)
        
            with col1:
                nueva_creacion = st.checkbox(
                    "🆕 Nueva creación",
                    value=datos.get("nueva_creacion", False),
                    key=f"{form_id}_nueva_creacion"
                )
                representacion_legal_trabajadores = st.checkbox(
                    "👥 ¿Existe Representación Legal de las Personas Trabajadoras?",
                    value=datos.get("representacion_legal_trabajadores", False),
                    key=f"{form_id}_repr_legal"
                )
                plantilla_media_anterior = st.number_input(
                    "👥 Plantilla media del año anterior",
                    min_value=0,
                    value=int(datos.get("plantilla_media_anterior") or 0),
                    key=f"{form_id}_plantilla"
                )
        
            with col2:
                es_pyme = st.checkbox(
                    "🏢 PYME",
                    value=datos.get("es_pyme", True),
                    key=f"{form_id}_pyme"
                )
                voluntad_acumular_credito = st.checkbox(
                    "💰 ¿Voluntad de acumular crédito de formación?",
                    value=datos.get("voluntad_acumular_credito", False),
                    key=f"{form_id}_acumular_credito"
                )
                tiene_erte = st.checkbox(
                    "⚠️ ERTE",
                    value=datos.get("tiene_erte", False),
                    key=f"{form_id}_erte"
                )
        else:
            # Valores por defecto si es solo_datos_basicos (ej: Mi Empresa)
            representante_tipo_documento = datos.get("representante_tipo_documento") or ""
            representante_numero_documento = datos.get("representante_numero_documento") or ""
            representante_nombre_apellidos = datos.get("representante_nombre_apellidos") or ""
            email_notificaciones = datos.get("email_notificaciones") or datos.get("email") or ""
            fecha_contrato_encomienda = datos.get("fecha_contrato_encomienda") or date.today()
            nueva_creacion = datos.get("nueva_creacion", False)
            representacion_legal_trabajadores = datos.get("representacion_legal_trabajadores", False)
            plantilla_media_anterior = int(datos.get("plantilla_media_anterior") or 0)
            es_pyme = datos.get("es_pyme", True)
            voluntad_acumular_credito = datos.get("voluntad_acumular_credito", False)
            tiene_erte = datos.get("tiene_erte", False)
            es_centro_gestor = datos.get("es_centro_gestor", False)
            provincia_sel = datos.get("provincia") or ""
            localidad_sel = datos.get("ciudad") or ""
            provincia_id = None
            localidad_id = None

        
        # =========================
        # BLOQUE MÓDULOS
        # =========================
        if session_state.role == "admin" and not solo_datos_basicos:
            st.markdown("### 🔧 Configuración de Módulos")
        
            col1, col2 = st.columns(2)
        
            with col1:
                formacion_activo = st.checkbox(
                    "📚 Formación",
                    value=datos.get("formacion_activo", True),
                    key=f"{form_id}_formacion"
                )
                iso_activo = st.checkbox(
                    "📋 ISO 9001",
                    value=datos.get("iso_activo", False),
                    key=f"{form_id}_iso"
                )
                rgpd_activo = st.checkbox(
                    "🛡️ RGPD",
                    value=datos.get("rgpd_activo", False),
                    key=f"{form_id}_rgpd"
                )
        
            with col2:
                docu_avanzada_activo = st.checkbox(
                    "📁 Doc. Avanzada",
                    value=datos.get("docu_avanzada_activo", False),
                    key=f"{form_id}_docu"
                )
        
                # CRM: solo carga fechas si ya existe en BD
                crm_data = empresas_service.get_crm_empresa(datos.get("id")) if not es_creacion else {}
                crm_activo = st.checkbox(
                    "📈 CRM",
                    value=crm_data.get("crm_activo", False),
                    key=f"{form_id}_crm"
                )
        
                if crm_activo:
                    crm_inicio = st.date_input(
                        "📅 CRM Inicio",
                        value=crm_data.get("crm_inicio") or date.today(),
                        key=f"{form_id}_crm_inicio"
                    )
                    crm_fin = st.date_input(
                        "📅 CRM Fin",
                        value=crm_data.get("crm_fin"),
                        key=f"{form_id}_crm_fin",
                        help="Dejar vacío si no tiene fecha fin"
                    )
                else:
                    crm_inicio, crm_fin = None, None
        
        else:
            formacion_activo = datos.get("formacion_activo", True)
            iso_activo = datos.get("iso_activo", False)
            rgpd_activo = datos.get("rgpd_activo", False)
            docu_avanzada_activo = datos.get("docu_avanzada_activo", False)
            
            es_centro_gestor = datos.get("es_centro_gestor", False)
            
            crm_data = empresas_service.get_crm_empresa(datos.get("id")) if not es_creacion else {}
            crm_activo = crm_data.get("crm_activo", False)
            crm_inicio, crm_fin = crm_data.get("crm_inicio"), crm_data.get("crm_fin")

        if not solo_datos_basicos:
            st.markdown("### 🏢 Funcionalidades Adicionales")
            
            es_centro_gestor = st.checkbox(
                "📍 Puede actuar como Centro Gestor",
                value=datos.get("es_centro_gestor", False),
                key=f"{form_id}_centro_gestor",
                help="Para grupos de Teleformación/Mixta según normativa FUNDAE"
            )
        # =========================
        # VALIDACIONES
        # =========================
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
        
        if errores:
            st.error(f"⚠️ Faltan campos: {', '.join(errores)}")
        
        # =========================
        # BOTONES
        # =========================
        st.markdown("---")
        if es_creacion:
            submitted = st.form_submit_button("➕ Crear Empresa", type="primary", use_container_width=True)
            eliminar = False
        else:
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
            with col_btn2:
                if not es_creacion and session_state.role == "admin":
                    eliminar = st.form_submit_button("🗑️ Eliminar", type="secondary", use_container_width=True)
                else:
                    eliminar = False
        
        # =========================
        # PROCESAMIENTO
        # =========================
        if submitted:
            if errores:
                st.error(f"⚠️ Corrige los errores antes de continuar: {', '.join(errores)}")
            else:
                procesar_guardado_empresa(
                    datos, nombre, cif, sector, convenio_referencia, codigo_cnae,
                    calle, numero, codigo_postal, provincia_id, localidad_id, telefono,
                    representante_tipo_documento, representante_numero_documento, representante_nombre_apellidos,
                    email_notificaciones, fecha_contrato_encomienda, nueva_creacion,
                    representacion_legal_trabajadores, plantilla_media_anterior, es_pyme,
                    voluntad_acumular_credito, tiene_erte, formacion_activo, iso_activo,
                    rgpd_activo, docu_avanzada_activo, crm_activo, crm_inicio, crm_fin,
                    st.session_state[cuentas_key] if not solo_datos_basicos else [],
                    provincia_sel if provincia_sel else None, localidad_sel if localidad_sel else None, 
                    empresas_service, session_state, es_creacion, tipo_empresa, solo_datos_basicos
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
    
    # Gestión de cuentas de cotización fuera del form (solo admin/gestor en edición completa)
    if not key_suffix and not solo_datos_basicos:
        st.markdown("#### 🏦 Cuentas de Cotización")
        mostrar_gestion_cuentas_en_formulario(cuentas_key)
        
# ==================================================
# GUARDADO DE EMPRESA Y CUENTAS
# ==================================================
def limpiar_session_state_empresa(form_id):
    """Limpia session_state específico del formulario de empresa."""
    keys_to_remove = []
    
    # Buscar todas las claves relacionadas con este formulario
    for key in st.session_state.keys():
        if form_id in key or key.startswith("cuentas_"):
            keys_to_remove.append(key)
    
    # Remover las claves encontradas
    for key in keys_to_remove:
        try:
            del st.session_state[key]
        except KeyError:
            pass

def procesar_guardado_empresa(
    datos, nombre, cif, sector, convenio_referencia, codigo_cnae,
    calle, numero, codigo_postal, provincia_id, localidad_id, telefono,
    representante_tipo_documento, representante_numero_documento, representante_nombre_apellidos,
    email_notificaciones, fecha_contrato_encomienda, nueva_creacion,
    representacion_legal_trabajadores, plantilla_media_anterior, es_pyme,
    voluntad_acumular_credito, tiene_erte, formacion_activo, iso_activo,
    rgpd_activo, docu_avanzada_activo, crm_activo, crm_inicio, crm_fin,
    cuentas_cotizacion, provincia_sel, localidad_sel, 
    empresas_service, session_state, es_creacion, tipo_empresa, solo_datos_basicos=False,
    es_centro_gestor=False
):
    """Procesa creación/actualización de empresa con jerarquía, cuentas y CRM."""
    try:
        # Validaciones
        if not validar_dni_cif(cif):
            st.error("❌ CIF inválido")
            return
        if representante_numero_documento and not validar_dni_cif(representante_numero_documento):
            st.error("❌ Documento de representante inválido")
            return

        # Datos base de empresa
        datos_empresa = {
            "nombre": nombre,
            "cif": cif,
            "sector": sector,
            "convenio_referencia": convenio_referencia,
            "codigo_cnae": codigo_cnae,
            "calle": calle,
            "numero": numero,
            "codigo_postal": codigo_postal,
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
            "email": email_notificaciones,
            "direccion": f"{calle} {numero}".strip() if calle or numero else "",
            "es_centro_gestor": es_centro_gestor,
            "updated_at": datetime.utcnow().isoformat(),
            "provincia_id": provincia_id,
            "localidad_id": localidad_id,
            "provincia": provincia_sel if provincia_sel else None,
            "ciudad": localidad_sel if localidad_sel else None
        }
        # Solo añadir es_centro_gestor si está disponible (admin y no solo_datos_basicos)
        if 'es_centro_gestor' in locals():
            datos_empresa["es_centro_gestor"] = es_centro_gestor
            
        # AGREGAR tipo_empresa solo en creación si es admin
        if es_creacion and session_state.role == "admin":
            datos_empresa["tipo_empresa"] = tipo_empresa

        if es_creacion:
            ok, empresa_id = empresas_service.crear_empresa_con_jerarquia(datos_empresa)
            if ok and empresa_id:
                st.success("✅ Empresa creada correctamente")

                # Guardar cuentas de cotización
                if cuentas_cotizacion:
                    guardar_cuentas_cotizacion(empresas_service.supabase, empresa_id, cuentas_cotizacion)

                # Guardar CRM si está activo
                if crm_activo:
                    empresas_service.supabase.table("crm_empresas").insert({
                        "empresa_id": empresa_id,
                        "crm_activo": True,
                        "crm_inicio": crm_inicio,
                        "crm_fin": crm_fin,
                        "created_at": datetime.utcnow().isoformat()
                    }).execute()

                # Limpiar session_state tras creación (CORREGIDO)
                form_id_base = f"empresa_nueva_crear"
                limpiar_session_state_empresa(form_id_base)
                
                st.rerun()

        else:
            ok = empresas_service.update_empresa_con_jerarquia(datos["id"], datos_empresa)
            if ok:
                st.success("✅ Empresa actualizada correctamente")

                # Actualizar cuentas
                if cuentas_cotizacion:
                    guardar_cuentas_cotizacion(empresas_service.supabase, datos["id"], cuentas_cotizacion)

                # Actualizar CRM en su tabla
                crm_table = empresas_service.supabase.table("crm_empresas")
                existing = crm_table.select("id").eq("empresa_id", datos["id"]).execute()

                if crm_activo:
                    payload_crm = {
                        "empresa_id": datos["id"],
                        "crm_activo": True,
                        "crm_inicio": crm_inicio,
                        "crm_fin": crm_fin,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                    if existing.data:
                        crm_table.update(payload_crm).eq("empresa_id", datos["id"]).execute()
                    else:
                        payload_crm["created_at"] = datetime.utcnow().isoformat()
                        crm_table.insert(payload_crm).execute()
                else:
                    # Si desmarcan CRM → desactivar
                    if existing.data:
                        crm_table.update({"crm_activo": False, "updated_at": datetime.utcnow().isoformat()}).eq("empresa_id", datos["id"]).execute()
                        
                # Limpiar session_state tras actualización (CORREGIDO)
                form_id_edicion = f"empresa_{datos['id']}_editar"
                limpiar_session_state_empresa(form_id_edicion)
                
                st.rerun()

    except Exception as e:
        st.error(f"❌ Error procesando empresa: {e}")
        
def guardar_cuentas_cotizacion(supabase, empresa_id: str, cuentas: list):
    """Guarda cuentas de cotización en Supabase, reemplazando las existentes."""
    try:
        supabase.table("cuentas_cotizacion").delete().eq("empresa_id", empresa_id).execute()
        if cuentas:
            cuentas_insert = [
                {
                    "empresa_id": empresa_id,
                    "numero_cuenta": c.get("numero_cuenta"),
                    "es_principal": c.get("es_principal", False),
                    "created_at": datetime.utcnow().isoformat()
                }
                for c in cuentas if c.get("numero_cuenta")
            ]
            if cuentas_insert:
                supabase.table("cuentas_cotizacion").insert(cuentas_insert).execute()
    except Exception as e:
        st.error(f"❌ Error guardando cuentas de cotización: {e}")


# ==================================================
# CRM - GUARDADO
# ==================================================
def guardar_crm_datos(supabase, empresa_id: str, crm_activo: bool, crm_inicio: date = None, crm_fin: date = None):
    """Guarda configuración de CRM para una empresa."""
    try:
        supabase.table("crm_empresas").delete().eq("empresa_id", empresa_id).execute()
        supabase.table("crm_empresas").insert({
            "empresa_id": empresa_id,
            "crm_activo": crm_activo,
            "crm_inicio": crm_inicio.isoformat() if crm_inicio else None,
            "crm_fin": crm_fin.isoformat() if crm_fin else None,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        st.error(f"❌ Error guardando datos CRM: {e}")


# ==================================================
# MAIN
# ==================================================
def main(supabase, session_state):
    """Vista principal de Empresas con tabs jerárquicas."""
    empresas_service = get_empresas_service(supabase, session_state)
    
    st.title("🏢 Gestión de Empresas")
    
    if session_state.role == "admin":
        tab1, tab2, tab3 = st.tabs(["🏢 Empresas", "📊 Métricas", "➕ Nueva Empresa"])
    else:
        tab1, tab2, tab3 = st.tabs(["📊 Mi Empresa", "👥 Empresas Cliente", "➕ Nueva Empresa"])
    
    if session_state.role == "admin":
        with tab1:
            df_empresas = empresas_service.get_empresas_con_jerarquia()
            empresa_sel = mostrar_tabla_empresas(df_empresas, session_state)
            if empresa_sel is not None:
                mostrar_acciones_empresa(empresa_sel, empresas_service, session_state)
                st.divider()
                # 🔄 Limpiar session_state para evitar arrastrar cuentas/CRM de otra empresa
                st.session_state.pop(f"cuentas_empresa_{empresa_sel['id']}", None)
                st.session_state.pop(f"crm_empresa_{empresa_sel['id']}", None)
                mostrar_formulario_empresa(
                    empresa_sel, empresas_service, session_state, es_creacion=False
                )
        with tab2:
            mostrar_metricas_empresas(empresas_service, session_state)
        with tab3:
            # 🔄 Limpiar session_state para nueva empresa
            st.session_state.pop("cuentas_empresa_nueva", None)
            st.session_state.pop("crm_empresa_nueva", None)
            mostrar_formulario_empresa(
                {}, empresas_service, session_state, es_creacion=True
            )
    
    elif session_state.role == "gestor":
        with tab1:
            mostrar_mi_empresa(empresas_service, session_state)
        with tab2:
            df_empresas = empresas_service.get_empresas_con_jerarquia()
            df_empresas = df_empresas[df_empresas["id"] != session_state.user.get("empresa_id")]  # excluir su propia empresa
            empresa_sel = mostrar_tabla_empresas(df_empresas, session_state, "👥 Mis Clientes")
            if empresa_sel is not None:
                mostrar_acciones_empresa(empresa_sel, empresas_service, session_state)
                st.divider()
                # 🔄 Limpiar session_state para evitar arrastrar cuentas/CRM de otra empresa
                st.session_state.pop(f"cuentas_empresa_{empresa_sel['id']}", None)
                st.session_state.pop(f"crm_empresa_{empresa_sel['id']}", None)
                mostrar_formulario_empresa(
                    empresa_sel, empresas_service, session_state, es_creacion=False
                )
        with tab3:
            # 🔄 Limpiar session_state para nueva empresa
            st.session_state.pop("cuentas_empresa_nueva", None)
            st.session_state.pop("crm_empresa_nueva", None)
            mostrar_formulario_empresa(
                {}, empresas_service, session_state, es_creacion=True
            )
    
    with st.expander("ℹ️ Ayuda sobre FUNDAE y Jerarquía"):
        st.markdown("""
        - **FUNDAE**: Los campos corresponden a la información necesaria para bonificar formación.
        - **Jerarquía**:
            - Cliente SaaS Directo → empresa final con acceso al sistema.
            - Gestora → gestiona varias empresas clientes.
            - Cliente de Gestora → empresa asociada a una gestora.
        """)

if __name__ == "__main__":
    main()
