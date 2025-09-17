import streamlit as st
from utils.fundae_helpers import actualizar_tipo_documento_tutores, migrar_horarios_existentes

def main(supabase, session_state):
    st.title("🔧 Migración FUNDAE")
    st.caption("Ejecutar UNA sola vez para migrar datos existentes")
    
    # Solo admin puede acceder
    if session_state.role != "admin":
        st.error("Solo administradores pueden ejecutar migraciones")
        return
    
    st.warning("⚠️ IMPORTANTE: Esta migración solo debe ejecutarse UNA vez")
    
    if st.checkbox("Entiendo que esto es una migración única"):
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("1. Migrar Tipos de Documento", type="primary"):
                try:
                    with st.spinner("Migrando tipos de documento..."):
                        if actualizar_tipo_documento_tutores(supabase):
                            st.success("✅ Tipos de documento actualizados")
                        else:
                            st.error("❌ Error al actualizar tipos de documento")
                except Exception as e:
                    st.error(f"Error: {e}")
        
        with col2:
            if st.button("2. Migrar Horarios", type="primary"):
                try:
                    with st.spinner("Migrando horarios..."):
                        migrados, errores = migrar_horarios_existentes(supabase)
                        st.success(f"✅ Horarios migrados: {migrados}")
                        if errores > 0:
                            st.warning(f"⚠️ Errores: {errores}")
                except Exception as e:
                    st.error(f"Error: {e}")
        
        st.divider()
        st.info("Una vez ejecutada la migración, puedes borrar este archivo")
