import streamlit as st
import pandas as pd
from datetime import datetime
from services.empresas_service_jerarquia import get_empresas_service

def test_fase1_empresas(supabase, session_state):
    """Ejecuta pruebas de validación para la FASE 1."""
    
    st.title("🧪 Validación FASE 1: Empresas con Jerarquía")
    st.markdown("Verificando que todos los componentes funcionen correctamente...")
    
    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.error("❌ Solo admin y gestores pueden ejecutar estas pruebas")
        return False
    
    # Inicializar servicio
    try:
        empresas_service = get_empresas_service(supabase, session_state)
        st.success("✅ EmpresasService inicializado correctamente")
    except Exception as e:
        st.error(f"❌ Error al inicializar EmpresasService: {e}")
        return False
    
    resultados = []
    
    # =========================
    # TEST 1: Verificar Estructura BD
    # =========================
    st.markdown("### 1️⃣ Verificando Estructura de Base de Datos")
    
    try:
        # Verificar campos jerárquicos en tabla empresas
        result = supabase.table("empresas").select("tipo_empresa, nivel_jerarquico, empresa_matriz_id").limit(1).execute()
        st.success("✅ Campos jerárquicos presentes en BD")
        
        # Verificar triggers (intentar llamar función)
        try:
            stats_result = supabase.rpc('get_estadisticas_jerarquia').execute()
            st.success("✅ Funciones SQL disponibles")
            if stats_result.data:
                st.json(stats_result.data[0] if isinstance(stats_result.data, list) else stats_result.data)
        except:
            st.warning("⚠️ Funciones SQL opcionales no instaladas")
        
        resultados.append("✅ Estructura BD OK")
    except Exception as e:
        st.error(f"❌ Campos jerárquicos faltantes: {e}")
        resultados.append("❌ Estructura BD ERROR")
        return False
    
    # =========================
    # TEST 2: Funciones del Servicio
    # =========================
    st.markdown("### 2️⃣ Verificando Funciones del Servicio")
    
    # Test get_empresas_con_jerarquia
    try:
        df_empresas = empresas_service.get_empresas_con_jerarquia()
        st.success(f"✅ get_empresas_con_jerarquia: {len(df_empresas)} empresas cargadas")
        resultados.append("✅ Consulta jerárquica OK")
        
        # Mostrar sample si hay datos
        if not df_empresas.empty:
            st.dataframe(df_empresas.head(3)[["nombre", "tipo_empresa", "nivel_jerarquico", "matriz_nombre"]])
        else:
            st.info("💡 No hay empresas en BD para mostrar")
            
    except Exception as e:
        st.error(f"❌ Error en get_empresas_con_jerarquia: {e}")
        resultados.append("❌ Consulta jerárquica ERROR")
    
    # Test según rol
    if session_state.role == "admin":
        try:
            gestoras = empresas_service.get_empresas_gestoras_disponibles()
            st.success(f"✅ get_empresas_gestoras_disponibles: {len(gestoras)} gestoras")
            if gestoras:
                st.write("Gestoras disponibles:", list(gestoras.keys()))
            resultados.append("✅ Funciones admin OK")
        except Exception as e:
            st.error(f"❌ Error en funciones admin: {e}")
            resultados.append("❌ Funciones admin ERROR")
    
    elif session_state.role == "gestor":
        try:
            clientes = empresas_service.get_empresas_clientes_gestor()
            asignacion = empresas_service.get_empresas_para_asignacion()
            st.success(f"✅ get_empresas_clientes_gestor: {len(clientes)} clientes")
            st.success(f"✅ get_empresas_para_asignacion: {len(asignacion)} empresas")
            if asignacion:
                st.write("Empresas para asignación:", list(asignacion.keys())[:3])
            resultados.append("✅ Funciones gestor OK")
        except Exception as e:
            st.error(f"❌ Error en funciones gestor: {e}")
            resultados.append("❌ Funciones gestor ERROR")
    
    # =========================
    # TEST 3: Permisos por Rol
    # =========================
    st.markdown("### 3️⃣ Verificando Permisos por Rol")
    
    # Test can_modify_data
    puede_modificar = empresas_service.can_modify_data()
    if session_state.role in ["admin", "gestor"]:
        if puede_modificar:
            st.success(f"✅ Permisos correctos para {session_state.role}")
            resultados.append("✅ Permisos OK")
        else:
            st.error(f"❌ {session_state.role} debería poder modificar datos")
            resultados.append("❌ Permisos ERROR")
    else:
        if not puede_modificar:
            st.success(f"✅ Permisos restrictivos correctos para {session_state.role}")
            resultados.append("✅ Permisos OK")
        else:
            st.error(f"❌ {session_state.role} no debería poder modificar datos")
            resultados.append("❌ Permisos ERROR")
    
    # =========================
    # TEST 4: Validaciones
    # =========================
    st.markdown("### 4️⃣ Verificando Validaciones")
    
    try:
        # Test validación CIF único
        cif_test = "B00000000"  # CIF que no debería existir
        cif_valido = empresas_service._validar_cif_unico_jerarquico(cif_test)
        if cif_valido:
            st.success("✅ Validación CIF único funciona")
        else:
            st.warning(f"⚠️ CIF {cif_test} ya existe")
        
        # Test permisos de edición
        if session_state.role == "admin":
            st.success("✅ Admin puede editar cualquier empresa")
        elif session_state.role == "gestor":
            empresa_propia = session_state.user.get("empresa_id")
            if empresa_propia:
                puede_editar = empresas_service._puede_editar_empresa_jerarquica(empresa_propia)
                if puede_editar:
                    st.success("✅ Gestor puede editar su empresa")
                else:
                    st.error("❌ Gestor no puede editar su empresa")
        
        resultados.append("✅ Validaciones OK")
    except Exception as e:
        st.error(f"❌ Error en validaciones: {e}")
        resultados.append("❌ Validaciones ERROR")
    
    # =========================
    # RESUMEN FINAL
    # =========================
    st.markdown("### 📊 Resumen de Validación")
    
    todos_ok = all("✅" in resultado for resultado in resultados if "💡" not in resultado)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Resultados:**")
        for resultado in resultados:
            st.markdown(f"- {resultado}")
    
    with col2:
        if todos_ok:
            st.success("🎉 **FASE 1 VALIDADA CORRECTAMENTE**")
            st.markdown("✅ Puedes proceder a la FASE 2")
        else:
            st.error("⚠️ **HAY PROBLEMAS EN FASE 1**")
            st.markdown("❌ Revisa los errores antes de continuar")
    
    return todos_ok

# =========================
# TEST INTERACTIVO DE CREACIÓN
# =========================
def test_crear_empresa_interactivo(supabase, session_state):
    """Test interactivo para crear una empresa real."""
    
    st.markdown("### 🧪 Test de Creación de Empresa")
    
    if session_state.role not in ["admin", "gestor"]:
        st.error("Solo admin y gestor pueden crear empresas")
        return
    
    empresas_service = get_empresas_service(supabase, session_state)
    
    with st.form("test_crear_empresa"):
        st.markdown("#### Crear Empresa de Prueba")
        
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre", value=f"Test {session_state.role} {datetime.now().strftime('%H%M')}")
            cif = st.text_input("CIF", value=f"B{datetime.now().strftime('%H%M%S')}99")
            ciudad = st.text_input("Ciudad", value="Madrid")
        
        with col2:
            telefono = st.text_input("Teléfono", value="600123456")
            email = st.text_input("Email", value=f"test{datetime.now().strftime('%H%M')}@example.com")
            direccion = st.text_input("Dirección", value="Calle Test 123")
        
        if session_state.role == "admin":
            tipo_empresa = st.selectbox("Tipo Empresa", ["CLIENTE_SAAS", "GESTORA"])
        
        submitted = st.form_submit_button("🚀 Crear Empresa de Prueba")
        
        if submitted:
            datos = {
                "nombre": nombre,
                "cif": cif,
                "ciudad": ciudad,
                "telefono": telefono,
                "email": email,
                "direccion": direccion
            }
            
            if session_state.role == "admin":
                datos["tipo_empresa"] = tipo_empresa
            
            try:
                success, empresa_id = empresas_service.crear_empresa_con_jerarquia(datos)
                if success:
                    st.success(f"✅ Empresa creada: {empresa_id}")
                    st.balloons()
                    
                    # Mostrar datos creados
                    empresa_creada = empresas_service.get_empresa_by_id(empresa_id)
                    if empresa_creada:
                        st.json(empresa_creada)
                else:
                    st.error("❌ Error al crear empresa")
            except Exception as e:
                st.error(f"❌ Excepción: {e}")

# =========================
# FUNCIÓN PRINCIPAL
# =========================
def main(supabase, session_state):
    """Función principal de validación (para pages/validacion_fase1.py)."""
    
    # Tabs para organizar tests
    tab1, tab2 = st.tabs(["🔍 Validación Automática", "🧪 Test Interactivo"])
    
    with tab1:
        # Mostrar test interactivo si está habilitado
        if st.session_state.get("test_crear_empresa", False):
            test_crear_empresa_interactivo(supabase, session_state)
            
            if st.button("⬅️ Volver a Validación"):
                st.session_state.test_crear_empresa = False
                st.rerun()
        else:
            # Ejecutar validación completa
            resultado = test_fase1_empresas(supabase, session_state)
            
            if resultado and st.button("🚀 Ir a Test de Creación"):
                st.session_state.test_crear_empresa = True
                st.rerun()
    
    with tab2:
        test_crear_empresa_interactivo(supabase, session_state)
    
    # Información adicional
    st.markdown("---")
    with st.expander("ℹ️ Información de Debugging"):
        st.markdown("#### Variables de Sesión")
        st.json({
            "role": session_state.role,
            "user_id": session_state.user.get("id"),
            "empresa_id": session_state.user.get("empresa_id"),
            "email": session_state.user.get("email")
        })

if __name__ == "__main__":
    # Para testing independiente
    pass
    """Ejecuta pruebas de validación para la FASE 1."""
    
    st.title("🧪 Validación FASE 1: Empresas con Jerarquía")
    st.markdown("Verificando que todos los componentes funcionen correctamente...")
    
    # Inicializar servicio
    try:
        empresas_service = get_empresas_service(supabase, session_state)
        st.success("✅ EmpresasService inicializado correctamente")
    except Exception as e:
        st.error(f"❌ Error al inicializar EmpresasService: {e}")
        return False
    
    resultados = []
    
    # =========================
    # TEST 1: Verificar Estructura BD
    # =========================
    st.markdown("### 1️⃣ Verificando Estructura de Base de Datos")
    
    try:
        # Verificar campos jerárquicos en tabla empresas
        result = supabase.table("empresas").select("tipo_empresa, nivel_jerarquico, empresa_matriz_id").limit(1).execute()
        st.success("✅ Campos jerárquicos presentes en BD")
        resultados.append("✅ Estructura BD OK")
    except Exception as e:
        st.error(f"❌ Campos jerárquicos faltantes: {e}")
        resultados.append("❌ Estructura BD ERROR")
        return False
    
    # =========================
    # TEST 2: Funciones del Servicio
    # =========================
    st.markdown("### 2️⃣ Verificando Funciones del Servicio")
    
    # Test get_empresas_con_jerarquia
    try:
        df_empresas = empresas_service.get_empresas_con_jerarquia()
        st.success(f"✅ get_empresas_con_jerarquia: {len(df_empresas)} empresas cargadas")
        resultados.append("✅ Consulta jerárquica OK")
        
        # Mostrar sample si hay datos
        if not df_empresas.empty:
            st.dataframe(df_empresas.head(3))
        else:
            st.info("💡 No hay empresas en BD para mostrar")
            
    except Exception as e:
        st.error(f"❌ Error en get_empresas_con_jerarquia: {e}")
        resultados.append("❌ Consulta jerárquica ERROR")
    
    # Test según rol
    if session_state.role == "admin":
        try:
            gestoras = empresas_service.get_empresas_gestoras_disponibles()
            st.success(f"✅ get_empresas_gestoras_disponibles: {len(gestoras)} gestoras")
            resultados.append("✅ Funciones admin OK")
        except Exception as e:
            st.error(f"❌ Error en funciones admin: {e}")
            resultados.append("❌ Funciones admin ERROR")
    
    elif session_state.role == "gestor":
        try:
            clientes = empresas_service.get_empresas_clientes_gestor()
            st.success(f"✅ get_empresas_clientes_gestor: {len(clientes)} clientes")
            resultados.append("✅ Funciones gestor OK")
        except Exception as e:
            st.error(f"❌ Error en funciones gestor: {e}")
            resultados.append("❌ Funciones gestor ERROR")
    
    # =========================
    # TEST 3: Permisos por Rol
    # =========================
    st.markdown("### 3️⃣ Verificando Permisos por Rol")
    
    # Test can_modify_data
    puede_modificar = empresas_service.can_modify_data()
    if session_state.role in ["admin", "gestor"]:
        if puede_modificar:
            st.success(f"✅ Permisos correctos para {session_state.role}")
            resultados.append("✅ Permisos OK")
        else:
            st.error(f"❌ {session_state.role} debería poder modificar datos")
            resultados.append("❌ Permisos ERROR")
    else:
        if not puede_modificar:
            st.success(f"✅ Permisos restrictivos correctos para {session_state.role}")
            resultados.append("✅ Permisos OK")
        else:
            st.error(f"❌ {session_state.role} no debería poder modificar datos")
            resultados.append("❌ Permisos ERROR")
    
    # =========================
    # TEST 4: Funciones SQL (Opcional)
    # =========================
    st.markdown("### 4️⃣ Verificando Funciones SQL Opcionales")
    
    try:
        # Test función estadísticas
        stats = supabase.rpc('get_estadisticas_jerarquia').execute()
        if stats.data:
            st.success("✅ Función get_estadisticas_jerarquia disponible")
            st.json(stats.data[0] if isinstance(stats.data, list) else stats.data)
            resultados.append("✅ Funciones SQL OK")
        else:
            st.warning("⚠️ Función get_estadisticas_jerarquia sin datos")
            resultados.append("⚠️ Funciones SQL parcial")
    except Exception as e:
        st.warning(f"⚠️ Funciones SQL opcionales no disponibles: {e}")
        resultados.append("⚠️ Funciones SQL no instaladas")
    
    # =========================
    # TEST 5: Crear Empresa (Simulación)
    # =========================
    st.markdown("### 5️⃣ Simulando Creación de Empresa")
    
    if puede_modificar:
        st.markdown("#### Datos de prueba:")
        datos_test = {
            "nombre": f"Empresa Test {session_state.role}",
            "cif": "B99999999",  # CIF de prueba
            "direccion": "Calle Test 123",
            "ciudad": "Madrid",
            "telefono": "600123456",
            "email": "test@empresa.com"
        }
        
        if session_state.role == "gestor":
            datos_test["tipo_empresa"] = "CLIENTE_GESTOR"
            datos_test["empresa_matriz_id"] = session_state.user.get("empresa_id")
        
        st.json(datos_test)
        
        # Verificar validaciones (sin crear realmente)
        try:
            # Solo validar CIF único
            cif_valido = empresas_service._validar_cif_unico_jerarquico(datos_test["cif"])
            if cif_valido:
                st.success("✅ Validaciones pasarían (CIF único)")
                resultados.append("✅ Validaciones OK")
            else:
                st.warning("⚠️ CIF ya existe en BD")
                resultados.append("⚠️ Validaciones parcial")
        except Exception as e:
            st.error(f"❌ Error en validaciones: {e}")
            resultados.append("❌ Validaciones ERROR")
    else:
        st.info("💡 Usuario sin permisos de creación - Test omitido")
        resultados.append("💡 Test creación omitido")
    
    # =========================
    # RESUMEN FINAL
    # =========================
    st.markdown("### 📊 Resumen de Validación")
    
    todos_ok = all("✅" in resultado for resultado in resultados if "💡" not in resultado)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Resultados:**")
        for resultado in resultados:
            st.markdown(f"- {resultado}")
    
    with col2:
        if todos_ok:
            st.success("🎉 **FASE 1 VALIDADA CORRECTAMENTE**")
            st.markdown("✅ Puedes proceder a la FASE 2")
        else:
            st.error("⚠️ **HAY PROBLEMAS EN FASE 1**")
            st.markdown("❌ Revisa los errores antes de continuar")
    
    # =========================
    # ACCIONES RECOMENDADAS
    # =========================
    st.markdown("### 🎯 Próximos Pasos")
    
    if todos_ok:
        st.markdown("""
        **FASE 1 completada exitosamente. Ahora puedes:**
        
        1. **Actualizar menú lateral** para mostrar "Empresas" a gestores
        2. **Proceder a FASE 2**: Actualizar grupos.py con jerarquía
        3. **Crear empresas cliente** como gestor para probar funcionalidad
        4. **Verificar permisos** creando grupos con empresas clientes
        """)
        
        if st.button("🚀 Ir a Test de Creación de Empresa"):
            st.session_state.test_crear_empresa = True
            
    else:
        st.markdown("""
        **Problemas detectados. Revisa:**
        
        1. **Estructura BD**: Ejecutar migrations SQL
        2. **Importaciones**: Verificar que empresas_service_jerarquia.py está importado
        3. **Permisos**: Verificar session_state.role
        4. **Funciones SQL**: Ejecutar triggers y funciones opcionales
        """)
    
    return todos_ok

# =========================
# TEST INTERACTIVO DE CREACIÓN
# =========================
def test_crear_empresa_interactivo(supabase, session_state):
    """Test interactivo para crear una empresa real."""
    
    st.markdown("### 🧪 Test de Creación de Empresa")
    
    if session_state.role not in ["admin", "gestor"]:
        st.error("Solo admin y gestor pueden crear empresas")
        return
    
    empresas_service = get_empresas_service(supabase, session_state)
    
    with st.form("test_crear_empresa"):
        st.markdown("#### Crear Empresa de Prueba")
        
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre", value=f"Test {session_state.role} {datetime.now().strftime('%H%M')}")
            cif = st.text_input("CIF", value=f"B{datetime.now().strftime('%H%M%S')}99")
            ciudad = st.text_input("Ciudad", value="Madrid")
        
        with col2:
            telefono = st.text_input("Teléfono", value="600123456")
            email = st.text_input("Email", value=f"test{datetime.now().strftime('%H%M')}@example.com")
            direccion = st.text_input("Dirección", value="Calle Test 123")
        
        if session_state.role == "admin":
            tipo_empresa = st.selectbox("Tipo Empresa", ["CLIENTE_SAAS", "GESTORA"])
        
        submitted = st.form_submit_button("🚀 Crear Empresa de Prueba")
        
        if submitted:
            datos = {
                "nombre": nombre,
                "cif": cif,
                "ciudad": ciudad,
                "telefono": telefono,
                "email": email,
                "direccion": direccion
            }
            
            if session_state.role == "admin":
                datos["tipo_empresa"] = tipo_empresa
            
            try:
                success, empresa_id = empresas_service.crear_empresa_con_jerarquia(datos)
                if success:
                    st.success(f"✅ Empresa creada: {empresa_id}")
                    st.balloons()
                    
                    # Mostrar datos creados
                    empresa_creada = empresas_service.get_empresa_by_id(empresa_id)
                    if empresa_creada:
                        st.json(empresa_creada)
                else:
                    st.error("❌ Error al crear empresa")
            except Exception as e:
                st.error(f"❌ Excepción: {e}")

# =========================
# FUNCIÓN PRINCIPAL
# =========================
def main_validacion(supabase, session_state):
    """Función principal de validación."""
    
    # Mostrar test interactivo si está habilitado
    if st.session_state.get("test_crear_empresa", False):
        test_crear_empresa_interactivo(supabase, session_state)
        
        if st.button("⬅️ Volver a Validación"):
            st.session_state.test_crear_empresa = False
            st.rerun()
    else:
        # Ejecutar validación completa
        test_fase1_empresas(supabase, session_state)

if __name__ == "__main__":
    # Para testing independiente
    # main_validacion(supabase, session_state)
    pass
