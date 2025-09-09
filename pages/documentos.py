import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from utils import (
    generar_pdf,
    generar_xml_accion_formativa,
    generar_xml_inicio_grupo,
    generar_xml_finalizacion_grupo,
    validar_xml,
)

def main(supabase, session_state):
    st.subheader("📄 Documentos")
    st.caption("Generación de documentos PDF y XML para acciones formativas y grupos.")
    st.divider()

    if session_state.role not in ["admin", "gestor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección.")
        st.stop()

    # Leer URLs XSD desde secrets
    FUNDAE = st.secrets["FUNDAE"]
    xsd_accion = FUNDAE["xsd_accion_formativa"]
    xsd_inicio = FUNDAE["xsd_inicio_grupo"]
    xsd_finalizacion = FUNDAE["xsd_finalizacion_grupo"]

    # 1) Selección de acción formativa
    try:
        if session_state.role == "gestor":
            empresa_id = session_state.user.get("empresa_id")
            grp = supabase.table("grupos")\
                          .select("accion_formativa_id")\
                          .eq("empresa_id", empresa_id)\
                          .execute().data or []
            ids_acc = list({g["accion_formativa_id"] for g in grp})
            acciones_res = supabase.table("acciones_formativas")\
                                    .select("*")\
                                    .in_("id", ids_acc)\
                                    .execute()
        else:
            acciones_res = supabase.table("acciones_formativas").select("*").execute()
    except Exception as e:
        st.error(f"⚠️ No se pudieron cargar las acciones formativas: {e}")
        acciones_res = {"data": []}

    acciones_dict = {a["nombre"]: a["id"] for a in (acciones_res.data or [])}
    accion_nombre = st.selectbox(
        "Selecciona Acción Formativa",
        options=list(acciones_dict.keys()) or ["No hay acciones"]
    )
    accion_id = acciones_dict.get(accion_nombre)
    accion = next((a for a in (acciones_res.data or []) if a["id"] == accion_id), None)

    # 2) Selección de grupo
    grupos_dict = {}
    grupo = None
    if accion:
        try:
            if session_state.role == "gestor":
                empresa_id = session_state.user.get("empresa_id")
                grupos_res = supabase.table("grupos")\
                                      .select("*")\
                                      .eq("empresa_id", empresa_id)\
                                      .eq("accion_formativa_id", accion_id)\
                                      .execute()
            else:
                grupos_res = supabase.table("grupos")\
                                      .select("*")\
                                      .eq("accion_formativa_id", accion_id)\
                                      .execute()
            grupos_dict = {g["codigo_grupo"]: g["id"] for g in (grupos_res.data or [])}
        except Exception as e:
            st.error(f"⚠️ No se pudieron cargar los grupos: {e}")
            grupos_res = {"data": []}

        grupo_nombre = st.selectbox(
            "Selecciona Grupo",
            options=list(grupos_dict.keys()) or ["No hay grupos"]
        )
        grupo_id = grupos_dict.get(grupo_nombre)
        grupo = next((g for g in (grupos_res.data or []) if g["id"] == grupo_id), None)

    st.divider()
    st.markdown("### 🧾 Generar Documentos")

    # 3) Generar PDF de Acción Formativa
    if accion and st.button("📄 Generar PDF"):
        lines = [
            f"Acción Formativa: {accion['nombre']}",
            f"Código: {accion['codigo_accion']}",
            f"Modalidad: {accion.get('modalidad','No especificada')}",
            f"Nivel: {accion.get('nivel','No especificado')}",
            f"Duración: {accion.get('num_horas','0')} horas",
            f"Fecha de generación: {datetime.today().strftime('%d/%m/%Y')}"
        ]
        buffer = BytesIO()
        pdf_bytes = generar_pdf(buffer, lines)
        st.download_button(
            "⬇️ Descargar PDF",
            data=pdf_bytes.getvalue(),
            file_name=f"{accion['codigo_accion']}_accion_formativa_{datetime.today().strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )

    # 4) Generar XML de Acción Formativa
    if accion and st.button("📤 Generar XML de Acción Formativa"):
        try:
            xml_bytes = generar_xml_accion_formativa(accion)
            validar_xml(xml_bytes, xsd_accion)
            st.download_button(
                "⬇️ Descargar XML Acción Formativa",
                data=xml_bytes,
                file_name=f"{accion['codigo_accion']}_accion_formativa_{datetime.today().strftime('%Y%m%d')}.xml",
                mime="application/xml"
            )
        except Exception as e:
            st.error(f"❌ Error al generar o validar XML de acción formativa: {e}")

    # 5) Generar XML de Inicio de Grupo
    if grupo and st.button("📤 Generar XML de Inicio de Grupo"):
        if not grupo.get("fecha_inicio") or not grupo.get("fecha_fin_prevista"):
            st.error("⚠️ El grupo debe tener fechas de inicio y fin previstas.")
        else:
            try:
                pg = supabase.table("participantes_grupos")\
                             .select("participante_id")\
                             .eq("grupo_id", grupo["id"])\
                             .execute().data or []
                ids = [p["participante_id"] for p in pg]
                if not ids:
                    st.error("⚠️ No hay participantes asignados a este grupo.")
                else:
                    participantes = supabase.table("participantes")\
                                             .select("id,nombre,email")\
                                             .in_("id", ids)\
                                             .execute().data or []
                    xml_bytes = generar_xml_inicio_grupo(grupo, participantes)
                    validar_xml(xml_bytes, xsd_inicio)
                    st.download_button(
                        "⬇️ Descargar XML Inicio Grupo",
                        data=xml_bytes,
                        file_name=f"{grupo['codigo_grupo']}_inicio_grupo_{datetime.today().strftime('%Y%m%d')}.xml",
                        mime="application/xml"
                    )
            except Exception as e:
                st.error(f"❌ Error al generar o validar XML de inicio de grupo: {e}")

    # 6) Generar XML de Finalización de Grupo
    if grupo and st.button("📤 Generar XML de Finalización de Grupo"):
        if grupo.get("estado") != "cerrado":
            st.error("⚠️ El grupo debe estar cerrado antes de generar el XML de finalización.")
        else:
            try:
                grupo_detalle = supabase.table("grupos")\
                                        .select("*")\
                                        .eq("id", grupo["id"])\
                                        .execute().data[0]
                # Si el XSD requiere participantes, cargarlos
                pg = supabase.table("participantes_grupos")\
                             .select("participante_id")\
                             .eq("grupo_id", grupo["id"])\
                             .execute().data or []
                ids = [p["participante_id"] for p in pg]
                participantes = []
                if ids:
                    participantes = supabase.table("participantes")\
                                             .select("id,nombre,email")\
                                             .in_("id", ids)\
                                             .execute().data or []
                xml_bytes = generar_xml_finalizacion_grupo(grupo_detalle, participantes)
                validar_xml(xml_bytes, xsd_finalizacion)
                st.download_button(
                    "⬇️ Descargar XML Finalización Grupo",
                    data=xml_bytes,
                    file_name=f"{grupo['codigo_grupo']}_finalizacion_grupo_{datetime.today().strftime('%Y%m%d')}.xml",
                    mime="application/xml"
                )
            except Exception as e:
                st.error(f"❌ Error al generar o validar XML de finalización de grupo: {e}")
    
