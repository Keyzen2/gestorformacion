import streamlit as st
import pandas as pd
from datetime import datetime
from services.data_service import get_data_service
from services.grupos_service import get_grupos_service


def main(supabase, session_state):
    st.markdown("## 📊 Panel del Gestor")
    st.caption("Visión general de la plataforma para gestores y administradores.")

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        return

    # =========================
    # Inicializar servicios
    # =========================
    data_service = get_data_service(supabase, session_state)
    grupos_service = get_grupos_service(supabase, session_state)

    # =========================
    # Cargar datos de grupos
    # =========================
    with st.spinner("Cargando información..."):
        try:
            df_grupos = grupos_service.get_grupos_completos()
            total_grupos = len(df_grupos)
        except Exception as e:
            st.warning(f"⚠️ Error al cargar grupos: {e}")
            df_grupos = pd.DataFrame()
            total_grupos = 0

    # =========================
    # Métricas principales
    # =========================
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Total Grupos", total_grupos)

    with col2:
        abiertos = len(df_grupos[df_grupos["fecha_fin"].isna()]) if not df_grupos.empty else 0
        st.metric("🟢 Abiertos", abiertos)

    with col3:
        finalizados = len(df_grupos[df_grupos["fecha_fin"].notna()]) if not df_grupos.empty else 0
        st.metric("✅ Finalizados", finalizados)

    with col4:
        pendientes = len(df_grupos[df_grupos["fecha_fin_prevista"].notna() & df_grupos["fecha_fin"].isna()]) if not df_grupos.empty else 0
        st.metric("🟡 Por Finalizar", pendientes)

    st.divider()

    # =========================
    # Listado de grupos recientes
    # =========================
    st.subheader("📋 Últimos Grupos")
    if not df_grupos.empty:
        df_display = df_grupos.copy()
        columnas = [
            "codigo_grupo",
            "accion_nombre",
            "fecha_inicio",
            "fecha_fin_prevista",
            "empresa_nombre",
            "accion_modalidad",
        ]

        df_display = df_display[columnas].sort_values("fecha_inicio", ascending=False).head(10)

        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("No hay grupos registrados todavía.")

    # =========================
    # Sección: Participantes
    # =========================
    st.divider()
    st.subheader("🧑‍🎓 Participantes")
    try:
        df_participantes = data_service.get_participantes_completos()
        total_participantes = len(df_participantes)
        st.metric("👥 Total Participantes", total_participantes)

        if not df_participantes.empty:
            df_part_display = df_participantes[
                ["nif", "nombre", "apellidos", "email", "empresa_nombre", "grupo_codigo"]
            ].head(10)
            st.dataframe(df_part_display, use_container_width=True, hide_index=True)
        else:
            st.info("No hay participantes registrados.")
    except Exception as e:
        st.warning(f"⚠️ Error al cargar participantes: {e}")

    # =========================
    # Sección: Tutores
    # =========================
    st.divider()
    st.subheader("👨‍🏫 Tutores")
    try:
        df_tutores = data_service.get_tutores_completos()
        total_tutores = len(df_tutores)
        st.metric("📘 Total Tutores", total_tutores)

        if not df_tutores.empty:
            df_tutores_display = df_tutores[
                ["nif", "nombre", "apellidos", "email", "especialidad", "empresa_nombre"]
            ].head(10)
            st.dataframe(df_tutores_display, use_container_width=True, hide_index=True)
        else:
            st.info("No hay tutores registrados.")
    except Exception as e:
        st.warning(f"⚠️ Error al cargar tutores: {e}")

    # =========================
    # Sección: Empresas
    # =========================
    st.divider()
    st.subheader("🏢 Empresas")
    try:
        df_empresas = data_service.get_empresas_completas()
        total_empresas = len(df_empresas)
        st.metric("🏭 Total Empresas", total_empresas)

        if not df_empresas.empty:
            df_empresas_display = df_empresas[
                ["cif", "nombre", "telefono", "email", "direccion", "localidad", "provincia"]
            ].head(10)
            st.dataframe(df_empresas_display, use_container_width=True, hide_index=True)
        else:
            st.info("No hay empresas registradas.")
    except Exception as e:
        st.warning(f"⚠️ Error al cargar empresas: {e}")

    # =========================
    # DOCUMENTACIÓN FUNDAE
    # =========================
    with st.expander("📂 Documentación y Modelos FUNDAE", expanded=False):
        st.markdown("Enlaces oficiales a modelos y documentos publicados por FUNDAE:")
    
        st.subheader("📑 Contratación entidad organizadora")
        st.markdown("- [Contrato de encomienda](https://www.fundae.es/DocumentosModelos/Contrato%20de%20encomienda.pdf)")
        st.markdown("- [Desistimiento del contrato](https://www.fundae.es/DocumentosModelos/Desistimiento%20contrato%20encomienda.pdf)")
    
        st.subheader("👥 Representación Legal de los Trabajadores (RLT)")
        st.markdown("- [Información a la RLT](https://www.fundae.es/DocumentosModelos/Informacion%20RLT.pdf)")
        st.markdown("- [Acta de discrepancias](https://www.fundae.es/DocumentosModelos/Acta%20de%20discrepancias.pdf)")
        st.markdown("- [Solicitud de información de la RLT](https://www.fundae.es/DocumentosModelos/Solicitud%20informacion%20RLT.pdf)")
    
        st.subheader("🏫 Impartición")
        st.markdown("- [Control de asistencia](https://www.fundae.es/DocumentosModelos/Control%20de%20asistencia.pdf)")
        st.markdown("- [Diploma](https://www.fundae.es/DocumentosModelos/Diploma.pdf)")
        st.markdown("- [Certificado de asistencia](https://www.fundae.es/DocumentosModelos/Certificado%20asistencia.pdf)")
        st.markdown("- [Declaración uso aula virtual 2024](https://www.fundae.es/DocumentosModelos/Declaracion%20aula%20virtual%202024.pdf)")
        st.markdown("- [Declaración uso aula virtual 2025](https://www.fundae.es/DocumentosModelos/Declaracion%20aula%20virtual%202025.pdf)")
    
        st.subheader("📝 Evaluación")
        st.markdown("- [Manual de ayuda evaluación de calidad](https://www.fundae.es/DocumentosModelos/Manual%20evaluacion%20calidad.pdf)")
        st.markdown("- [Instrucciones envío cuestionarios 2024](https://www.fundae.es/DocumentosModelos/Instrucciones%20cuestionarios%202024.pdf)")
    
        st.subheader("💶 Costes")
        st.markdown("- [B1. Resumen de costes](https://www.fundae.es/DocumentosModelos/B1%20Resumen%20costes.pdf)")
        st.markdown("- [Anexos de costes](https://www.fundae.es/DocumentosModelos/Anexos%20costes.pdf)")
        st.markdown("- [B2. Permisos individuales de formación](https://www.fundae.es/DocumentosModelos/B2%20Permisos%20individuales.pdf)")
        st.markdown("- [Guía de orientación de costes](https://www.fundae.es/DocumentosModelos/Guia%20costes.pdf)")
    
        st.subheader("📜 Permiso Individual de Formación")
        st.markdown("- [Solicitud de PIF a la empresa](https://www.fundae.es/DocumentosModelos/Solicitud%20PIF.pdf)")
