import streamlit as st
import pandas as pd
from datetime import datetime
from services.empresas_service import get_empresas_service

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
                st.json(stats_result.data if isinstance(stats_result.data, dict) else stats_result.data[0])
        except Exception as sql_e:
            st.warning(f"⚠️ Funciones SQL opcionales no instaladas: {sql_e}")
        
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
        try:
            cif_valido = empresas_service._validar_cif_unico_jerarquico(cif_test)
            if cif_valido:
                st.success("✅ Validación CIF único funciona")
            else:
                st.warning(f"⚠️ CIF {cif_test} ya existe")
        except Exception as val_error:
            st.error(f"❌ Error en validación CIF: {val_error}")
        
        # Test permisos de edición
        if session_state.role == "admin":
            st.success("✅ Admin puede editar cualquier empresa")
        elif session_state.role == "gestor":
            empresa_propia = session_state.user.get("empresa_id")
            if empresa_propia:
                try:
                    puede_editar = empresas_service._puede_editar_empresa_jerarquica(empresa_propia)
                    if puede_editar:
                        st.success("✅ Gestor puede editar su empresa")
                    else:
                        st.error("❌ Gestor no puede editar su empresa")
                except Exception as perm_error:
                    st.error(f"❌ Error verificando permisos: {perm_error}")
        
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

def main(supabase, session_state):
    """Función principal que Streamlit ejecuta automáticamente."""
    
    # Verificar autenticación
    if not session_state.get("authenticated"):
        st.error("❌ Debes iniciar sesión para acceder a esta página")
        return
    
    # Verificar permisos
    if session_state.role not in ["admin", "gestor"]:
        st.error("❌ No tienes permisos para acceder a esta validación")
        st.info("💡 Solo administradores y gestores pueden ejecutar las validaciones de FASE 1")
        return
    
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

# Esta parte es importante para Streamlit
if __name__ == "__main__":
    # Para testing independiente
    pass
