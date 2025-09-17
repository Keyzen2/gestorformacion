import streamlit as st

def main(supabase, session_state):
    st.title("🔧 Migración FUNDAE")
    st.caption("Ejecutar UNA sola vez para migrar datos existentes")
    
    # Solo admin puede acceder
    if session_state.role != "admin":
        st.error("Solo administradores pueden ejecutar migraciones")
        return
    
    st.warning("⚠️ IMPORTANTE: Esta migración solo debe ejecutarse UNA vez")
    
    if st.checkbox("Entiendo que esto es una migración única"):
        
        # MIGRACIÓN 1: Tipos de documento
        if st.button("1. Migrar Tipos de Documento", type="primary"):
            try:
                with st.spinner("Migrando tipos de documento..."):
                    import re
                    
                    # Obtener todos los tutores
                    tutores = supabase.table("tutores").select("id, nif").execute()
                    
                    actualizados = 0
                    for tutor in tutores.data or []:
                        if not tutor.get("nif"):
                            continue
                            
                        nif = tutor["nif"].upper().strip()
                        tipo_documento = None
                        
                        # Detectar tipo según formato
                        if re.match(r'^[0-9]{8}[A-Z]$', nif):
                            tipo_documento = 10  # NIF
                        elif re.match(r'^[XYZ][0-9]{7}[A-Z]$', nif):
                            tipo_documento = 60  # NIE
                        elif len(nif) >= 6:
                            tipo_documento = 20  # Pasaporte
                        
                        if tipo_documento:
                            supabase.table("tutores").update({
                                "tipo_documento": tipo_documento
                            }).eq("id", tutor["id"]).execute()
                            actualizados += 1
                    
                    st.success(f"✅ {actualizados} tutores actualizados")
                    
            except Exception as e:
                st.error(f"Error: {e}")
        
        st.divider()
        
        # MIGRACIÓN 2: Horarios
        if st.button("2. Migrar Horarios", type="primary"):
            try:
                with st.spinner("Migrando horarios..."):
                    
                    # Obtener grupos con horarios
                    grupos = supabase.table("grupos").select("""
                        id, horario, 
                        accion_formativa:acciones_formativas(num_horas)
                    """).not_.is_("horario", "null").execute()
                    
                    migrados = 0
                    errores = 0
                    
                    for grupo in grupos.data or []:
                        horario_str = grupo.get("horario")
                        if not horario_str:
                            continue
                            
                        try:
                            horas_accion = 0
                            if grupo.get("accion_formativa"):
                                horas_accion = grupo["accion_formativa"].get("num_horas", 0)
                            
                            # Parsear horario básico
                            partes = horario_str.split(" | ")
                            m_ini = m_fin = t_ini = t_fin = None
                            dias = ""
                            
                            for parte in partes:
                                if parte.startswith("Mañana:"):
                                    horas = parte.replace("Mañana: ", "").split(" - ")
                                    if len(horas) == 2:
                                        m_ini, m_fin = horas[0].strip(), horas[1].strip()
                                elif parte.startswith("Tarde:"):
                                    horas = parte.replace("Tarde: ", "").split(" - ")
                                    if len(horas) == 2:
                                        t_ini, t_fin = horas[0].strip(), horas[1].strip()
                                elif parte.startswith("Días:"):
                                    dias = parte.replace("Días: ", "").replace("-", "")
                            
                            # Datos para insertar
                            datos_horario = {
                                "grupo_id": grupo["id"],
                                "horas_totales": float(horas_accion) if horas_accion else 0.0,
                                "hora_inicio_tramo1": m_ini,
                                "hora_fin_tramo1": m_fin,
                                "hora_inicio_tramo2": t_ini,
                                "hora_fin_tramo2": t_fin,
                                "dias": dias
                            }
                            
                            # Eliminar horario anterior si existe
                            supabase.table("grupos_horarios").delete().eq("grupo_id", grupo["id"]).execute()
                            
                            # Insertar nuevo horario
                            result = supabase.table("grupos_horarios").insert(datos_horario).execute()
                            if result.data:
                                migrados += 1
                            else:
                                errores += 1
                                
                        except Exception as e:
                            st.error(f"Error en grupo {grupo['id']}: {e}")
                            errores += 1
                    
                    st.success(f"✅ {migrados} horarios migrados")
                    if errores > 0:
                        st.warning(f"⚠️ {errores} errores")
                    
            except Exception as e:
                st.error(f"Error: {e}")
