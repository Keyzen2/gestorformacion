import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from services.aulas_service import get_aulas_service
from utils import export_excel
from io import BytesIO

# Verificar disponibilidad de streamlit-calendar
try:
    from streamlit_calendar import calendar
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False

# Verificar reportlab para PDFs
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.shapes import Drawing
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# =========================
# EXPORTACIONES
# =========================

def exportar_cronograma_excel(eventos: list):
    """Exporta cronograma a Excel"""
    try:
        if not eventos:
            st.warning("No hay eventos para exportar")
            return
            
        datos = []
        for ev in eventos:
            props = ev.get("extendedProps", {})
            try:
                inicio = pd.to_datetime(ev.get("start", "")).strftime('%d/%m/%Y %H:%M')
                fin = pd.to_datetime(ev.get("end", "")).strftime('%d/%m/%Y %H:%M')
            except:
                inicio = ev.get("start", "")
                fin = ev.get("end", "")
                
            datos.append({
                "Título": ev.get("title", "").split(": ", 1)[-1] if ": " in ev.get("title", "") else ev.get("title", ""),
                "Aula": props.get("aula_nombre", ""),
                "Inicio": inicio,
                "Fin": fin,
                "Tipo": props.get("tipo_reserva", ""),
                "Estado": props.get("estado", ""),
                "Grupo": props.get("grupo_codigo", "")
            })

        df_export = pd.DataFrame(datos)
        fecha_str = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"cronograma_aulas_{fecha_str}.xlsx"
        
        export_excel(df_export, filename=filename, label="📥 Descargar Excel")

    except Exception as e:
        st.error(f"Error exportando Excel: {e}")


def exportar_cronograma_pdf_semanal(eventos: list, fecha_inicio: date, fecha_fin: date):
    """Exporta cronograma a PDF con vista semanal"""
    if not REPORTLAB_AVAILABLE:
        st.error("reportlab no está instalado. Ejecuta: pip install reportlab")
        return
        
    try:
        if not eventos:
            st.warning("No hay eventos para exportar")
            return
            
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), 
                               leftMargin=1*cm, rightMargin=1*cm,
                               topMargin=1.5*cm, bottomMargin=1.5*cm)
        
        elementos = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor("#2c3e50"),
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        titulo = f"Cronograma de Aulas - {fecha_inicio.strftime('%d/%m/%Y')} a {fecha_fin.strftime('%d/%m/%Y')}"
        elementos.append(Paragraph(titulo, title_style))
        elementos.append(Spacer(1, 12))
        
        # Obtener aulas únicas
        aulas_set = set()
        for ev in eventos:
            aulas_set.add(ev.get("extendedProps", {}).get("aula_nombre", "Sin aula"))
        aulas_list = sorted(list(aulas_set))
        
        if not aulas_list:
            st.warning("No se encontraron aulas en los eventos")
            return
        
        # Generar días
        dias = []
        fecha_actual = fecha_inicio
        while fecha_actual <= fecha_fin:
            dias.append(fecha_actual)
            fecha_actual += timedelta(days=1)
        
        if len(dias) > 7:
            dias = dias[:7]
            st.info(f"Se mostrarán solo los primeros 7 días")
        
        # Crear matriz
        dias_es = {0: 'Lun', 1: 'Mar', 2: 'Mié', 3: 'Jue', 4: 'Vie', 5: 'Sáb', 6: 'Dom'}
        header = ["Aula"] + [f"{dias_es[d.weekday()]}\n{d.strftime('%d/%m')}" for d in dias]
        datos_tabla = [header]
        
        for aula in aulas_list:
            fila = [aula]
            
            for dia in dias:
                eventos_dia = []
                
                for ev in eventos:
                    try:
                        ev_inicio = pd.to_datetime(ev.get("start", "")).date()
                        ev_aula = ev.get("extendedProps", {}).get("aula_nombre", "")
                        
                        if ev_aula == aula and ev_inicio == dia:
                            hora_inicio = pd.to_datetime(ev.get("start", "")).strftime('%H:%M')
                            titulo = ev.get("title", "").split(": ", 1)[-1] if ": " in ev.get("title", "") else ev.get("title", "")
                            eventos_dia.append(f"{hora_inicio}\n{titulo[:15]}..." if len(titulo) > 15 else f"{hora_inicio}\n{titulo}")
                    except:
                        continue
                
                if eventos_dia:
                    fila.append("\n".join(eventos_dia[:3]))
                else:
                    fila.append("-")
            
            datos_tabla.append(fila)
        
        col_widths = [4*cm] + [3.5*cm] * len(dias)
        tabla = Table(datos_tabla, colWidths=col_widths)
        
        estilo_tabla = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#3498db")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor("#ecf0f1")),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (0, -1), 8),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('FONTSIZE', (1, 1), (-1, -1), 7),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#2c3e50")),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]
        
        tabla.setStyle(TableStyle(estilo_tabla))
        elementos.append(tabla)
        
        elementos.append(Spacer(1, 12))
        leyenda_texto = """
        <b>Leyenda:</b> 
        <font color="#28a745">■</font> Formación | 
        <font color="#ffc107">■</font> Mantenimiento | 
        <font color="#17a2b8">■</font> Evento | 
        <font color="#dc3545">■</font> Bloqueada
        """
        elementos.append(Paragraph(leyenda_texto, styles['Normal']))
        
        doc.build(elementos)
        buffer.seek(0)
        
        fecha_str = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"cronograma_semanal_{fecha_str}.pdf"
        
        st.download_button(
            label="📥 Descargar PDF Semanal",
            data=buffer,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True
        )
        
    except Exception as e:
        st.error(f"Error exportando PDF: {e}")


def exportar_informe_estadisticas_pdf(eventos: list, aulas_info: list, fecha_inicio: date, fecha_fin: date):
    """Exporta informe ejecutivo con estadísticas"""
    if not REPORTLAB_AVAILABLE:
        st.error("reportlab no está instalado")
        return
        
    try:
        if not eventos or not aulas_info:
            st.warning("No hay datos suficientes")
            return
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                               leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
        
        elementos = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor("#2c3e50"),
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        elementos.append(Spacer(1, 3*cm))
        elementos.append(Paragraph("Informe de Estadísticas", title_style))
        elementos.append(Paragraph("Gestión de Aulas", title_style))
        elementos.append(Spacer(1, 1*cm))
        
        periodo = f"Período: {fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}"
        elementos.append(Paragraph(periodo, styles['Normal']))
        elementos.append(Spacer(1, 0.5*cm))
        
        fecha_gen = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        elementos.append(Paragraph(fecha_gen, styles['Normal']))
        
        elementos.append(PageBreak())
        
        # Resumen ejecutivo
        elementos.append(Paragraph("<b>Resumen Ejecutivo</b>", styles['Heading1']))
        elementos.append(Spacer(1, 12))
        
        total_aulas = len(aulas_info)
        total_eventos = len(eventos)
        dias_periodo = (fecha_fin - fecha_inicio).days + 1
        promedio_eventos_dia = total_eventos / dias_periodo if dias_periodo > 0 else 0
        
        resumen_data = [
            ["Métrica", "Valor"],
            ["Total de Aulas", str(total_aulas)],
            ["Total de Reservas", str(total_eventos)],
            ["Días Analizados", str(dias_periodo)],
            ["Promedio Reservas/Día", f"{promedio_eventos_dia:.1f}"]
        ]
        
        tabla_resumen = Table(resumen_data, colWidths=[10*cm, 5*cm])
        tabla_resumen.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#3498db")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue)
        ]))
        elementos.append(tabla_resumen)
        elementos.append(Spacer(1, 20))
        
        # Ocupación por aula
        elementos.append(Paragraph("<b>Ocupación por Aula</b>", styles['Heading2']))
        elementos.append(Spacer(1, 12))
        
        ocupacion_por_aula = {}
        for aula in aulas_info:
            aula_nombre = aula.get("nombre", "Sin nombre")
            eventos_aula = [
                ev for ev in eventos 
                if ev.get("extendedProps", {}).get("aula_nombre") == aula_nombre
            ]
            ocupacion_por_aula[aula_nombre] = len(eventos_aula)
        
        datos_ocupacion = [["Aula", "Nº Reservas", "% del Total"]]
        for aula_nombre, num_reservas in sorted(ocupacion_por_aula.items(), key=lambda x: x[1], reverse=True):
            porcentaje = (num_reservas / total_eventos * 100) if total_eventos > 0 else 0
            datos_ocupacion.append([
                aula_nombre,
                str(num_reservas),
                f"{porcentaje:.1f}%"
            ])
        
        tabla_ocupacion = Table(datos_ocupacion, colWidths=[8*cm, 4*cm, 3*cm])
        tabla_ocupacion.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#ecf0f1")),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER')
        ]))
        elementos.append(tabla_ocupacion)
        
        doc.build(elementos)
        buffer.seek(0)
        
        fecha_str = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"estadisticas_aulas_{fecha_str}.pdf"
        
        st.download_button(
            label="📥 Descargar Informe Estadísticas",
            data=buffer,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True
        )
        
    except Exception as e:
        st.error(f"Error exportando informe: {e}")


# =========================
# COMPONENTES UI
# =========================

def mostrar_tabla_aulas(df_aulas, session_state, aulas_service):
    """Tabla de aulas siguiendo patrón Streamlit 1.49"""
    if df_aulas.empty:
        st.info("No hay aulas para mostrar")
        return None

    st.markdown("### Aulas Registradas")

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_nombre = st.text_input("Nombre contiene", key="filtro_aula_nombre")
    with col2:
        filtro_ubicacion = st.text_input("Ubicación contiene", key="filtro_aula_ubicacion")
    with col3:
        filtro_activa = st.selectbox("Estado", ["Todas", "Activas", "Inactivas"], key="filtro_aula_estado")

    df_filtrado = df_aulas.copy()
    
    if filtro_nombre:
        df_filtrado = df_filtrado[df_filtrado["nombre"].str.contains(filtro_nombre, case=False, na=False)]
    if filtro_ubicacion:
        df_filtrado = df_filtrado[df_filtrado["ubicacion"].str.contains(filtro_ubicacion, case=False, na=False)]
    if filtro_activa != "Todas":
        activa_bool = filtro_activa == "Activas"
        df_filtrado = df_filtrado[df_filtrado["activa"] == activa_bool]

    if df_filtrado.empty:
        st.warning("No se encontraron aulas con los filtros aplicados")
        return None

    df_display = df_filtrado.copy()
    df_display["Estado"] = df_display["activa"].apply(lambda x: "Activa" if x else "Inactiva")
    df_display["Capacidad"] = df_display["capacidad_maxima"]
    
    columnas = ["nombre", "ubicacion", "Capacidad", "Estado"]
    if session_state.role == "admin":
        columnas.insert(2, "empresa_nombre")

    evento = st.dataframe(
        df_display[columnas],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "nombre": "Nombre del Aula",
            "ubicacion": "Ubicación",
            "empresa_nombre": "Empresa"
        }
    )

    col_exp, col_imp = st.columns([1, 1])
    with col_exp:
        if not df_filtrado.empty:
            fecha_str = datetime.now().strftime("%Y%m%d")
            filename = f"aulas_{fecha_str}.xlsx"
            export_excel(df_filtrado, filename=filename, label="Exportar Excel")
    with col_imp:
        if st.button("Actualizar", use_container_width=True, key="btn_actualizar_aulas"):
            aulas_service.limpiar_cache_aulas()
            st.rerun()

    if evento.selection.rows:
        return df_filtrado.iloc[evento.selection.rows[0]]
    return None


def mostrar_formulario_aula(aula_data, aulas_service, session_state, es_creacion=False):
    """Formulario de aula"""
    if es_creacion:
        st.subheader("Nueva Aula")
        datos = {}
    else:
        st.subheader(f"Editar {aula_data['nombre']}")
        datos = aula_data.copy()

    form_id = f"aula_{datos.get('id', 'nueva')}_{'crear' if es_creacion else 'editar'}"

    with st.form(form_id, clear_on_submit=es_creacion):
        st.markdown("### Información Básica")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nombre = st.text_input(
                "Nombre del Aula *", 
                value=datos.get("nombre", ""), 
                key=f"{form_id}_nombre"
            )
            capacidad_maxima = st.number_input(
                "Capacidad Máxima *", 
                min_value=1, 
                max_value=200, 
                value=int(datos.get("capacidad_maxima", 20)),
                key=f"{form_id}_capacidad"
            )
        
        with col2:
            ubicacion = st.text_input(
                "Ubicación", 
                value=datos.get("ubicacion", ""), 
                key=f"{form_id}_ubicacion"
            )
            activa = st.checkbox(
                "Aula Activa", 
                value=datos.get("activa", True),
                key=f"{form_id}_activa"
            )

        st.markdown("### Equipamiento")
        opciones_equipamiento = [
            "PROYECTOR", "PIZARRA_DIGITAL", "ORDENADORES", "AUDIO", 
            "AIRE_ACONDICIONADO", "CALEFACCION", "WIFI", "TELEVISION",
            "FLIPCHART", "IMPRESORA", "ESCANER"
        ]
        
        equipamiento_actual = datos.get("equipamiento", [])
        equipamiento = st.multiselect(
            "Seleccionar equipamiento",
            options=opciones_equipamiento,
            default=equipamiento_actual,
            key=f"{form_id}_equipamiento"
        )

        st.markdown("### Configuración Visual")
        col1, col2 = st.columns(2)
        
        with col1:
            color_cronograma = st.color_picker(
                "Color en Cronograma",
                value=datos.get("color_cronograma", "#3498db"),
                key=f"{form_id}_color"
            )
        
        with col2:
            st.write("**Vista previa:**")
            st.markdown(
                f'<div style="background-color: {color_cronograma}; height: 30px; border-radius: 5px; border: 1px solid #ddd; margin-top: 8px;"></div>',
                unsafe_allow_html=True
            )

        observaciones = st.text_area(
            "Observaciones",
            value=datos.get("observaciones", ""),
            key=f"{form_id}_observaciones"
        )

        errores = []
        if not nombre:
            errores.append("Nombre obligatorio")
        if capacidad_maxima < 1:
            errores.append("Capacidad debe ser mayor a 0")
        
        if errores:
            st.error(f"Errores: {', '.join(errores)}")

        st.markdown("---")
        if es_creacion:
            submitted = st.form_submit_button("Crear Aula", type="primary", use_container_width=True)
            eliminar = False
        else:
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button("Guardar Cambios", type="primary", use_container_width=True)
            with col_btn2:
                eliminar = st.form_submit_button("Eliminar", type="secondary", use_container_width=True) if session_state.role == "admin" else False

        if submitted and not errores:
            try:
                datos_aula = {
                    "nombre": nombre,
                    "descripcion": datos.get("descripcion", ""),
                    "capacidad_maxima": capacidad_maxima,
                    "equipamiento": equipamiento,
                    "ubicacion": ubicacion,
                    "activa": activa,
                    "color_cronograma": color_cronograma,
                    "observaciones": observaciones,
                    "updated_at": datetime.utcnow().isoformat()
                }

                if es_creacion:
                    datos_aula["empresa_id"] = session_state.user.get("empresa_id")
                    datos_aula["created_at"] = datetime.utcnow().isoformat()
                    
                    success, aula_id = aulas_service.crear_aula(datos_aula)
                    if success:
                        st.success("Aula creada correctamente")
                        if "crear_nueva_aula" in st.session_state:
                            del st.session_state["crear_nueva_aula"]
                        st.rerun()
                    else:
                        st.error(f"Error al crear: {aula_id if isinstance(aula_id, str) else 'Error desconocido'}")
                else:
                    success = aulas_service.actualizar_aula(datos["id"], datos_aula)
                    if success:
                        st.success("Aula actualizada")
                        st.rerun()
                    else:
                        st.error("Error al actualizar")
                        
            except Exception as e:
                st.error(f"Error: {e}")

        if eliminar:
            if st.session_state.get("confirmar_eliminar_aula"):
                try:
                    success = aulas_service.eliminar_aula(datos["id"])
                    if success:
                        st.success("Aula eliminada")
                        del st.session_state["confirmar_eliminar_aula"]
                        st.rerun()
                    else:
                        st.error("No se puede eliminar (tiene reservas futuras)")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.session_state["confirmar_eliminar_aula"] = True
                st.warning("Presiona 'Eliminar' nuevamente para confirmar")

# =========================
# GESTIÓN DE RESERVAS
# =========================

def mostrar_lista_reservas(aulas_service, session_state):
    """Lista de reservas con filtros"""
    st.markdown("### Reservas Existentes")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        fecha_desde = st.date_input(
            "Desde",
            value=datetime.now().date() - timedelta(days=7),
            key="lista_fecha_desde"
        )
    
    with col2:
        fecha_hasta = st.date_input(
            "Hasta",
            value=datetime.now().date() + timedelta(days=14),
            key="lista_fecha_hasta"
        )
    
    with col3:
        filtro_tipo = st.selectbox(
            "Tipo",
            ["Todos", "GRUPO", "EVENTO", "MANTENIMIENTO", "BLOQUEADA"],
            key="lista_filtro_tipo"
        )
    
    try:
        df_reservas = aulas_service.get_reservas_periodo(
            fecha_desde.isoformat() + "T00:00:00Z",
            fecha_hasta.isoformat() + "T23:59:59Z"
        )
        
        if not df_reservas.empty:
            if filtro_tipo != "Todos":
                df_reservas = df_reservas[df_reservas['tipo_reserva'] == filtro_tipo]
            
            df_display = df_reservas.copy()
            df_display['Fecha'] = pd.to_datetime(df_display['fecha_inicio']).dt.strftime('%d/%m/%Y')
            df_display['Horario'] = (
                pd.to_datetime(df_display['fecha_inicio']).dt.strftime('%H:%M') + 
                " - " + 
                pd.to_datetime(df_display['fecha_fin']).dt.strftime('%H:%M')
            )
            df_display['Estado'] = df_display['estado'].apply(
                lambda x: "Confirmada" if x == "CONFIRMADA" else "Pendiente"
            )
            
            columnas_mostrar = ['Fecha', 'Horario', 'aula_nombre', 'titulo', 'tipo_reserva', 'Estado']
            
            evento = st.dataframe(
                df_display[columnas_mostrar],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    'aula_nombre': 'Aula',
                    'titulo': 'Título',
                    'tipo_reserva': 'Tipo'
                }
            )
            
            if evento.selection.rows and session_state.role in ["admin", "gestor"]:
                reserva_seleccionada = df_reservas.iloc[evento.selection.rows[0]]
                
                st.markdown("---")
                st.markdown("### Acciones para Reserva Seleccionada")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("Editar Reserva", key="editar_reserva_btn"):
                        st.session_state["editar_reserva_id"] = reserva_seleccionada['id']
                        st.rerun()
                
                with col2:
                    if reserva_seleccionada['estado'] == 'PENDIENTE':
                        if st.button("Confirmar", key="confirmar_reserva_btn"):
                            try:
                                success = aulas_service.actualizar_estado_reserva(
                                    reserva_seleccionada['id'], 
                                    'CONFIRMADA'
                                )
                                if success:
                                    st.success("Reserva confirmada")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                
                with col3:
                    if st.button("Eliminar", key="eliminar_reserva_btn"):
                        if st.session_state.get("confirmar_eliminar_reserva"):
                            try:
                                success = aulas_service.eliminar_reserva(reserva_seleccionada['id'])
                                if success:
                                    st.success("Reserva eliminada")
                                    del st.session_state["confirmar_eliminar_reserva"]
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                        else:
                            st.session_state["confirmar_eliminar_reserva"] = True
                            st.warning("Presiona nuevamente para confirmar")
        
        else:
            st.info("No hay reservas en el período")
            
    except Exception as e:
        st.error(f"Error cargando reservas: {e}")


def mostrar_formulario_reserva_manual(aulas_service, session_state):
    """Formulario para crear reservas manuales"""
    
    st.markdown("### Nueva Reserva Manual")
    
    try:
        df_aulas = aulas_service.get_aulas_con_empresa()
        if df_aulas.empty:
            st.warning("No hay aulas disponibles")
            return
        
        aulas_opciones = {}
        for _, row in df_aulas.iterrows():
            if row.get('ubicacion') and str(row['ubicacion']).strip():
                nombre_display = f"{row['nombre']} ({row['ubicacion']})"
            else:
                nombre_display = row['nombre']
            aulas_opciones[nombre_display] = row['id']
        
    except Exception as e:
        st.error(f"Error cargando aulas: {e}")
        return

    with st.form("nueva_reserva_manual"):
        col1, col2 = st.columns(2)
        
        with col1:
            aula_seleccionada = st.selectbox(
                "Seleccionar Aula",
                options=list(aulas_opciones.keys()),
                key="reserva_aula"
            )
            
            tipo_reserva = st.selectbox(
                "Tipo de Reserva",
                ["GRUPO", "EVENTO", "MANTENIMIENTO", "BLOQUEADA"],
                key="reserva_tipo"
            )
            
            titulo = st.text_input(
                "Título de la Reserva",
                key="reserva_titulo",
                help="Descripción breve"
            )
        
        with col2:
            fecha_reserva = st.date_input(
                "Fecha",
                value=datetime.now().date(),
                key="reserva_fecha"
            )
            
            col_hora1, col_hora2 = st.columns(2)
            with col_hora1:
                hora_inicio = st.time_input(
                    "Hora Inicio",
                    value=datetime.now().time(),
                    key="reserva_hora_inicio"
                )
            with col_hora2:
                hora_fin = st.time_input(
                    "Hora Fin",
                    value=(datetime.now() + timedelta(hours=2)).time(),
                    key="reserva_hora_fin"
                )
        
        descripcion = st.text_area(
            "Descripción Adicional",
            key="reserva_descripcion",
            help="Información adicional (opcional)"
        )
        
        errores = []
        if not titulo:
            errores.append("El título es obligatorio")
        if hora_inicio >= hora_fin:
            errores.append("La hora de fin debe ser posterior a la de inicio")
        
        if errores:
            for error in errores:
                st.error(f"⚠️ {error}")
        
        submitted = st.form_submit_button(
            "Crear Reserva", 
            type="primary", 
            use_container_width=True,
            disabled=bool(errores)
        )
        
        if submitted and not errores:
            try:
                fecha_inicio_completa = datetime.combine(fecha_reserva, hora_inicio)
                fecha_fin_completa = datetime.combine(fecha_reserva, hora_fin)
                
                aula_id = aulas_opciones[aula_seleccionada]
                
                conflictos = aulas_service.verificar_conflictos_reserva(
                    aula_id,
                    fecha_inicio_completa.isoformat(),
                    fecha_fin_completa.isoformat()
                )
                
                if conflictos:
                    st.error("Ya existe una reserva en este horario")
                    return
                
                datos_reserva = {
                    "aula_id": aula_id,
                    "titulo": titulo,
                    "descripcion": descripcion,
                    "tipo_reserva": tipo_reserva,
                    "fecha_inicio": fecha_inicio_completa.isoformat(),
                    "fecha_fin": fecha_fin_completa.isoformat(),
                    "estado": "CONFIRMADA",
                    "created_by": session_state.user.get("id"),
                    "created_at": datetime.utcnow().isoformat()
                }
                
                success, reserva_id = aulas_service.crear_reserva(datos_reserva)
                
                if success:
                    st.success("Reserva creada correctamente")
                    st.rerun()
                else:
                    st.error("Error al crear la reserva")
                    
            except Exception as e:
                st.error(f"Error procesando reserva: {e}")


def mostrar_gestion_reservas(aulas_service, session_state):
    """Gestión completa de reservas con subtabs"""
    
    st.markdown("### Gestión de Reservas")
    
    sub_tabs = st.tabs(["Lista de Reservas", "Nueva Reserva"])
    
    with sub_tabs[0]:
        mostrar_lista_reservas(aulas_service, session_state)
    
    with sub_tabs[1]:
        mostrar_formulario_reserva_manual(aulas_service, session_state)


# =========================
# CRONOGRAMA
# =========================

def mostrar_cronograma_simple(aulas_service, session_state):
    """Cronograma simplificado sin dependencias externas"""
    
    st.markdown("### Cronograma de Aulas")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        fecha_inicio = st.date_input(
            "Desde", 
            value=datetime.now().date() - timedelta(days=7),
            key="crono_fecha_inicio"
        )
    
    with col2:
        fecha_fin = st.date_input(
            "Hasta", 
            value=datetime.now().date() + timedelta(days=14),
            key="crono_fecha_fin"
        )
    
    with col3:
        if st.button("Actualizar", key="crono_refresh"):
            st.rerun()

    try:
        df_aulas = aulas_service.get_aulas_con_empresa()
        if not df_aulas.empty:
            aulas_disponibles = ["Todas"] + df_aulas['nombre'].tolist()
            aulas_seleccionadas = st.multiselect(
                "Filtrar por aulas",
                aulas_disponibles,
                default=["Todas"],
                key="crono_filtro_aulas"
            )
            
            if "Todas" in aulas_seleccionadas or not aulas_seleccionadas:
                aulas_ids = df_aulas['id'].tolist()
            else:
                aulas_ids = df_aulas[df_aulas['nombre'].isin(aulas_seleccionadas)]['id'].tolist()
        else:
            st.warning("No hay aulas disponibles")
            return
    except Exception as e:
        st.error(f"Error cargando aulas: {e}")
        return

    try:
        eventos = aulas_service.get_eventos_cronograma(
            fecha_inicio.isoformat() + "T00:00:00Z",
            fecha_fin.isoformat() + "T23:59:59Z",
            aulas_ids
        )
        
        if not eventos:
            st.info("No hay eventos en el período seleccionado")
            return
        
        mostrar_cronograma_alternativo(aulas_service, session_state)
        
        st.markdown("---")
        st.markdown("### Exportar")
        col1, col2 = st.columns(2)
        
        with col1:
            exportar_cronograma_excel(eventos)
        with col2:
            exportar_cronograma_pdf_semanal(eventos, fecha_inicio, fecha_fin)
            
    except Exception as e:
        st.error(f"Error obteniendo eventos: {e}")


def mostrar_cronograma_alternativo(aulas_service, session_state):
    """Vista alternativa si falla el calendario"""
    
    st.markdown("### Vista de Cronograma")
    
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Desde", value=datetime.now().date(), key="alt_fecha_inicio")
    with col2:
        fecha_fin = st.date_input("Hasta", value=datetime.now().date() + timedelta(days=7), key="alt_fecha_fin")
    
    try:
        df_reservas = aulas_service.get_reservas_periodo(
            fecha_inicio.isoformat() + "T00:00:00Z",
            fecha_fin.isoformat() + "T23:59:59Z"
        )
        
        if df_reservas.empty:
            st.info("No hay reservas en el período")
            return
        
        df_reservas['fecha'] = pd.to_datetime(df_reservas['fecha_inicio']).dt.date
        fechas_unicas = sorted(df_reservas['fecha'].unique())
        
        for fecha in fechas_unicas:
            eventos_dia = df_reservas[df_reservas['fecha'] == fecha].sort_values('fecha_inicio')
            
            st.markdown(f"#### {fecha.strftime('%A, %d de %B %Y')}")
            
            for _, evento in eventos_dia.iterrows():
                inicio = pd.to_datetime(evento['fecha_inicio'])
                fin = pd.to_datetime(evento['fecha_fin'])
                
                color_map = {'GRUPO': '🟢', 'EVENTO': '🔵', 'MANTENIMIENTO': '🟡', 'BLOQUEADA': '🔴'}
                emoji = color_map.get(evento['tipo_reserva'], '⚪')
                
                col1, col2, col3 = st.columns([1, 2, 1])
                
                with col1:
                    st.markdown(f"**{inicio.strftime('%H:%M')} - {fin.strftime('%H:%M')}**")
                with col2:
                    st.markdown(f"{emoji} **{evento['aula_nombre']}**: {evento['titulo']}")
                with col3:
                    estado_emoji = "✅" if evento['estado'] == 'CONFIRMADA' else "⏳"
                    st.markdown(f"{estado_emoji}")
            
            st.divider()
        
    except Exception as e:
        st.error(f"Error: {e}")


# =========================
# WIDGETS SIDEBAR
# =========================

def mostrar_metricas_sidebar(aulas_service, session_state):
    """Métricas rápidas en sidebar"""
    try:
        stats = aulas_service.get_estadisticas_rapidas()
        
        st.sidebar.markdown("### Resumen de Aulas")
        
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            st.metric("Aulas", stats.get('total_aulas', 0))
            st.metric("Hoy", stats.get('reservas_hoy', 0))
        
        with col2:
            st.metric("Activas", stats.get('aulas_activas', 0))
            ocupacion = stats.get('ocupacion_actual', 0)
            st.metric("Ocupación", f"{ocupacion:.0f}%")
        
        if session_state.role == "admin":
            st.sidebar.metric("Capacidad Total", stats.get('capacidad_total', 0))
        
        proximas = aulas_service.get_proximas_reservas(limite=3)
        if proximas:
            st.sidebar.markdown("#### Próximas Reservas")
            for reserva in proximas:
                fecha_hora = pd.to_datetime(reserva['fecha_inicio']).strftime('%d/%m %H:%M')
                st.sidebar.info(f"**{fecha_hora}**\n{reserva['aula_nombre']}: {reserva['titulo'][:20]}...")
        
        disponibles = aulas_service.get_aulas_disponibles_ahora()
        if disponibles:
            st.sidebar.success(f"🟢 {len(disponibles)} aulas disponibles ahora")
        else:
            st.sidebar.warning("Todas las aulas ocupadas")
            
    except Exception as e:
        st.sidebar.error(f"Error en estadísticas: {e}")


def mostrar_alertas_aulas(aulas_service, session_state):
    """Sistema de notificaciones y alertas"""
    
    if session_state.role not in ["admin", "gestor"]:
        return
    
    try:
        notificaciones = aulas_service.get_notificaciones_pendientes()
        
        if notificaciones:
            st.sidebar.markdown("### Notificaciones")
            
            for notif in notificaciones[:5]:
                tipo = notif['tipo']
                mensaje = notif['mensaje']
                
                if tipo == 'MANTENIMIENTO':
                    st.sidebar.warning(f"🔧 {mensaje}")
                elif tipo == 'RECORDATORIO':
                    st.sidebar.info(f"📋 {mensaje}")
                else:
                    st.sidebar.info(f"ℹ️ {mensaje}")
                
    except Exception as e:
        st.sidebar.error(f"Error en notificaciones: {e}")

# =========================
# DASHBOARD ADMIN
# =========================

def mostrar_dashboard_admin(aulas_service, session_state):
    """Dashboard de métricas solo para admin"""
    
    if session_state.role != "admin":
        return
    
    with st.expander("📊 Métricas de Ocupación", expanded=True):
        try:
            stats = aulas_service.get_estadisticas_rapidas()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Aulas", stats.get("total_aulas", 0))
            
            with col2:
                st.metric("Reservas Hoy", stats.get("reservas_hoy", 0))
            
            with col3:
                ocupacion = stats.get("ocupacion_actual", 0)
                st.metric("% Ocupación", f"{ocupacion:.1f}%")
            
            with col4:
                st.metric("Capacidad Total", stats.get("capacidad_total", 0))
            
            # Alertas
            alertas = aulas_service.get_alertas_aulas()
            if alertas:
                st.markdown("#### ⚠️ Alertas")
                for alerta in alertas:
                    if alerta['tipo'] == 'WARNING':
                        st.warning(alerta['mensaje'])
                    else:
                        st.info(alerta['mensaje'])
                        
        except Exception as e:
            st.error(f"Error cargando métricas: {e}")


# =========================
# FUNCIÓN PRINCIPAL
# =========================

def main(supabase, session_state):
    """Función principal del módulo de aulas - VERSIÓN COMPLETA"""
    
    # Verificar permisos
    if session_state.role not in ["admin", "gestor", "tutor"]:
        st.warning("🔒 No tienes permisos para acceder a esta sección")
        return
    
    # Inicializar servicio
    try:
        aulas_service = get_aulas_service(supabase, session_state)
    except Exception as e:
        st.error(f"❌ Error inicializando servicio: {e}")
        return
    
    # Widgets sidebar
    with st.sidebar:
        mostrar_metricas_sidebar(aulas_service, session_state)
        mostrar_alertas_aulas(aulas_service, session_state)
    
    # Título
    st.title("🏢 Gestión de Aulas")
    st.caption("Sistema completo de gestión de aulas y reservas para formación")
    
    # Dashboard admin (solo para admin)
    if session_state.role == "admin":
        mostrar_dashboard_admin(aulas_service, session_state)
    
    # Verificar si hay edición de reserva pendiente
    if st.session_state.get("editar_reserva_id"):
        st.warning("Funcionalidad de edición de reserva en desarrollo")
        if st.button("❌ Cancelar edición"):
            del st.session_state["editar_reserva_id"]
            st.rerun()
        return
    
    # Tabs principales
    if session_state.role in ["admin", "gestor"]:
        tabs = st.tabs(["🏢 Aulas", "📅 Cronograma", "📋 Reservas"])
    else:
        tabs = st.tabs(["🏢 Aulas", "📅 Cronograma"])
    
    # TAB 1: Gestión de Aulas
    with tabs[0]:
        try:
            df_aulas = aulas_service.get_aulas_con_empresa()
            
            # Layout: Tabla | Formulario
            col_tabla, col_form = st.columns([2, 1])
            
            with col_tabla:
                aula_seleccionada = mostrar_tabla_aulas(df_aulas, session_state, aulas_service)
            
            with col_form:
                # Botón crear nueva
                if session_state.role in ["admin", "gestor"]:
                    if st.button("➕ Nueva Aula", use_container_width=True, type="primary"):
                        st.session_state["crear_nueva_aula"] = True
                        st.rerun()
                
                # Mostrar formulario según estado
                if st.session_state.get("crear_nueva_aula"):
                    mostrar_formulario_aula(None, aulas_service, session_state, es_creacion=True)
                    
                    if st.button("❌ Cancelar", key="cancelar_nueva_aula"):
                        del st.session_state["crear_nueva_aula"]
                        st.rerun()
                
                elif aula_seleccionada is not None:
                    if session_state.role in ["admin", "gestor"]:
                        mostrar_formulario_aula(aula_seleccionada, aulas_service, session_state)
                    else:
                        st.info("👁️ Modo solo lectura")
                        with st.expander("📋 Detalles del Aula"):
                            st.write(f"**Nombre:** {aula_seleccionada['nombre']}")
                            st.write(f"**Capacidad:** {aula_seleccionada['capacidad_maxima']}")
                            st.write(f"**Ubicación:** {aula_seleccionada.get('ubicacion', 'N/A')}")
                            st.write(f"**Estado:** {'✅ Activa' if aula_seleccionada.get('activa') else '❌ Inactiva'}")
                
                else:
                    st.info("👆 Selecciona un aula de la tabla para ver sus detalles")
                    
                    # Widget aulas disponibles
                    disponibles_ahora = aulas_service.get_aulas_disponibles_ahora()
                    if disponibles_ahora:
                        st.success(f"🟢 {len(disponibles_ahora)} aulas disponibles ahora")
                        with st.expander("Ver aulas disponibles"):
                            for aula in disponibles_ahora:
                                st.write(f"• {aula['nombre']} (Cap: {aula['capacidad_maxima']})")
                    
        except Exception as e:
            st.error(f"❌ Error en gestión de aulas: {e}")
            st.exception(e)
    
    # TAB 2: Cronograma
    with tabs[1]:
        try:
            mostrar_cronograma_simple(aulas_service, session_state)
        except Exception as e:
            st.error(f"❌ Error en cronograma: {e}")
            mostrar_cronograma_alternativo(aulas_service, session_state)
    
    # TAB 3: Reservas (Solo admin/gestor)
    if len(tabs) > 2:
        with tabs[2]:
            try:
                mostrar_gestion_reservas(aulas_service, session_state)
            except Exception as e:
                st.error(f"❌ Error en gestión de reservas: {e}")


# =========================
# PUNTO DE ENTRADA
# =========================

if __name__ == "__main__":
    st.set_page_config(
        page_title="Gestión de Aulas",
        page_icon="🏢",
        layout="wide"
    )
    
    st.info("🧪 Módulo en modo de prueba - Requiere integración con la aplicación principal")
    st.markdown("""
    ### Funcionalidades Implementadas
    
    ✅ **Gestión de Aulas**
    - CRUD completo con validaciones
    - Filtros dinámicos
    - Selección interactiva con formulario
    - Exportación a Excel
    
    ✅ **Cronograma Visual**
    - Calendario interactivo (si streamlit-calendar está instalado)
    - Vista alternativa robusta
    - Filtros por aula y período
    - Exportación Excel y PDF
    
    ✅ **Gestión de Reservas**
    - Lista con filtros
    - Crear reservas manuales
    - Validación de conflictos
    - Confirmación y cancelación
    
    ✅ **Dashboard y Métricas**
    - Estadísticas rápidas en sidebar
    - Métricas admin expandidas
    - Notificaciones y alertas
    - Aulas disponibles en tiempo real
    
    ✅ **Exportaciones Avanzadas**
    - Excel con datos formateados
    - PDF semanal tipo calendario
    - PDF con estadísticas ejecutivas
    
    ✅ **Integración con Grupos**
    - Asignación automática de aula a grupo
    - Reservas vinculadas a grupos formativos
    
    ### Dependencias
    
    **Obligatorias:**
    - streamlit >= 1.49
    - pandas
    - reportlab (para PDFs)
    
    **Opcionales:**
    - streamlit-calendar (para calendario interactivo)
    
    ### Instalación
    
    ```bash
    pip install reportlab
    pip install streamlit-calendar  # Opcional
    ```
    
    ### Base de Datos Requerida
    
    **Tablas:**
    - `aulas` (id, nombre, capacidad_maxima, ubicacion, activa, color_cronograma, equipamiento, empresa_id, ...)
    - `aula_reservas` (id, aula_id, grupo_id, titulo, fecha_inicio, fecha_fin, tipo_reserva, estado, ...)
    - `empresas` (id, nombre, cif, ...)
    - `grupos` (id, codigo_grupo, ...)
    """)
