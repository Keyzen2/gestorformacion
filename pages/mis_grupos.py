import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import Optional

# =========================
# CONFIG STREAMLIT
# =========================
st.set_page_config(
    page_title="🎓 Mis Cursos",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# FUNCIONES AUXILIARES
# =========================

@st.cache_data(ttl=300)
def cargar_cursos_alumno(_supabase, email: str):
    """Carga los cursos del alumno usando la vista existente."""
    try:
        part_res = _supabase.table("vw_participantes_completo").select("*").eq("email", email).execute()
        df = pd.DataFrame(part_res.data or [])
        
        if df.empty:
            return df
            
        # Limpiar y procesar datos
        df["accion_horas"] = pd.to_numeric(df["accion_horas"], errors='coerce').fillna(0)
        
        # Asegurar que las fechas son del tipo correcto
        df["grupo_fecha_inicio"] = pd.to_datetime(df["grupo_fecha_inicio"], errors='coerce')
        df["grupo_fecha_fin_prevista"] = pd.to_datetime(df["grupo_fecha_fin_prevista"], errors='coerce')
        
        return df
        
    except Exception as e:
        st.error(f"Error cargando cursos: {e}")
        return pd.DataFrame()

def formatear_fecha(fecha) -> str:
    """Formatea una fecha para mostrar al usuario."""
    if pd.isna(fecha):
        return "No definida"
    
    try:
        if isinstance(fecha, str):
            fecha_dt = pd.to_datetime(fecha)
        else:
            fecha_dt = fecha
        return fecha_dt.strftime("%d/%m/%Y")
    except:
        return "Fecha inválida"

def mostrar_diploma_alumno(curso_row):
    """Función para mostrar y gestionar diplomas del alumno."""
    try:
        grupo_id = curso_row.get("grupo_id")
        if not grupo_id:
            st.error("No se puede acceder al diploma: información de grupo no disponible")
            return
        
        # Necesitamos acceder a supabase, pero no está disponible aquí
        # Esta función necesita modificarse para recibir supabase como parámetro
        st.info("🔗 Para acceder al diploma, contacta con tu centro de formación")
        st.markdown("""
        **Información del curso:**
        - Código: {}
        - Curso: {}
        - Estado: Finalizado ✅
        
        Tu diploma está disponible. Si no puedes acceder, contacta con:
        - Tu departamento de formación
        - El centro que impartió el curso
        - Soporte técnico de la plataforma
        """.format(
            curso_row.get("codigo_grupo", "N/A"),
            curso_row.get("accion_nombre", "N/A")
        ))
        
    except Exception as e:
        st.error(f"Error accediendo al diploma: {e}")

def obtener_diploma_real(_supabase, grupo_id, email):
    """Obtiene la URL real del diploma desde la base de datos."""
    try:
        # Primero obtener el participante_id del email
        participante_res = _supabase.table("participantes").select("id").eq("email", email).execute()
        if not participante_res.data:
            return None
            
        participante_id = participante_res.data[0]["id"]
        
        # Buscar diploma
        diploma_res = _supabase.table("diplomas").select("url, archivo_nombre, fecha_subida").eq(
            "grupo_id", grupo_id
        ).eq("participante_id", participante_id).execute()
        
        if diploma_res.data:
            diploma_data = diploma_res.data[0]
            # Limpiar URL (remover ? al final si existe)
            url = diploma_data.get("url", "").rstrip("?")
            return {
                "url": url,
                "archivo_nombre": diploma_data.get("archivo_nombre"),
                "fecha_subida": diploma_data.get("fecha_subida")
            }
        
        return None
        
    except Exception as e:
        st.error(f"Error buscando diploma: {e}")
        return None
    """Devuelve el emoji apropiado para cada estado."""
    colores = {
        "Pendiente de inicio": "🟡",
        "En curso": "🟢", 
        "Curso finalizado": "🔵",
        "Finalizado": "🔵"
    }
    return colores.get(estado, "⚪")

def calcular_dias_restantes(fecha_inicio) -> Optional[int]:
    """Calcula días restantes para que comience un curso."""
    if pd.isna(fecha_inicio):
        return None
        
    try:
        if isinstance(fecha_inicio, str):
            fecha_dt = pd.to_datetime(fecha_inicio).date()
        else:
            fecha_dt = fecha_inicio.date()
            
        hoy = date.today()
        if fecha_dt > hoy:
            return (fecha_dt - hoy).days
    except:
        pass
    
    return None

# =========================
# COMPONENTES DE LA INTERFAZ
# =========================

def mostrar_resumen_alumno(df_cursos: pd.DataFrame):
    """Muestra un resumen general del alumno."""
    if df_cursos.empty:
        return
    
    # Calcular métricas
    total_cursos = len(df_cursos)
    total_horas = df_cursos["accion_horas"].sum()
    cursos_completados = len(df_cursos[df_cursos["estado_formacion"].isin(["Curso finalizado", "Finalizado"])])
    diplomas_disponibles = len(df_cursos[df_cursos["tiene_diploma"] == True])
    
    st.subheader("📊 Mi Resumen de Formación")
    
    # Mostrar métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "📚 Total Cursos",
            total_cursos,
            help="Cursos en los que estás inscrito"
        )
    
    with col2:
        horas_texto = f"{int(total_horas)}h" if total_horas > 0 else "0h"
        st.metric(
            "⏱️ Total Horas",
            horas_texto,
            help="Horas totales de formación"
        )
    
    with col3:
        porcentaje = f"{(cursos_completados/total_cursos*100):.0f}%" if total_cursos > 0 else "0%"
        st.metric(
            "✅ Completados",
            cursos_completados,
            delta=porcentaje,
            help="Cursos finalizados"
        )
    
    with col4:
        st.metric(
            "🏆 Diplomas",
            diplomas_disponibles,
            help="Diplomas disponibles para descarga"
        )

def mostrar_filtros_cursos(df_cursos: pd.DataFrame):
    """Muestra filtros para los cursos del alumno."""
    if df_cursos.empty:
        return {}, df_cursos
    
    st.subheader("🔍 Filtros")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filtro_texto = st.text_input(
            "Buscar curso o empresa",
            placeholder="Nombre del curso, empresa...",
            help="Busca en nombre del curso o empresa"
        )
    
    with col2:
        # Obtener años únicos de las fechas
        años_disponibles = []
        for fecha in df_cursos["grupo_fecha_inicio"].dropna():
            try:
                if isinstance(fecha, str):
                    año = pd.to_datetime(fecha).year
                else:
                    año = fecha.year
                años_disponibles.append(año)
            except:
                continue
        
        años_únicos = sorted(set(años_disponibles), reverse=True)
        filtro_año = st.selectbox(
            "Año del curso",
            ["Todos"] + [str(año) for año in años_únicos],
            help="Filtrar por año de inicio"
        )
    
    with col3:
        estados_disponibles = df_cursos["estado_formacion"].dropna().unique().tolist()
        filtro_estado = st.selectbox(
            "Estado del curso", 
            ["Todos"] + estados_disponibles,
            help="Filtrar por estado actual"
        )
    
    # Aplicar filtros
    df_filtrado = df_cursos.copy()
    
    if filtro_texto:
        mascara = (
            df_filtrado["accion_nombre"].str.contains(filtro_texto, case=False, na=False) |
            df_filtrado["empresa_nombre"].str.contains(filtro_texto, case=False, na=False) |
            df_filtrado["codigo_grupo"].str.contains(filtro_texto, case=False, na=False)
        )
        df_filtrado = df_filtrado[mascara]
    
    if filtro_año != "Todos":
        try:
            año_int = int(filtro_año)
            mascara_año = df_filtrado["grupo_fecha_inicio"].dt.year == año_int
            df_filtrado = df_filtrado[mascara_año]
        except:
            pass
    
    if filtro_estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["estado_formacion"] == filtro_estado]
    
    return {"texto": filtro_texto, "año": filtro_año, "estado": filtro_estado}, df_filtrado

def mostrar_tarjeta_curso_funcional(curso_row, _supabase, email):
    """Muestra una tarjeta individual para cada curso con descarga funcional de diploma."""
    
    # Obtener datos de la fila
    nombre_curso = curso_row.get("accion_nombre", "Sin nombre")
    codigo_grupo = curso_row.get("codigo_grupo", "Sin código")
    horas = int(curso_row.get("accion_horas", 0)) if pd.notna(curso_row.get("accion_horas")) else 0
    modalidad = curso_row.get("accion_modalidad", "Sin especificar")
    empresa = curso_row.get("empresa_nombre", "Sin empresa")
    estado = curso_row.get("estado_formacion", "Sin estado")
    fecha_inicio = curso_row.get("grupo_fecha_inicio")
    fecha_fin = curso_row.get("grupo_fecha_fin_prevista")
    tiene_diploma = curso_row.get("tiene_diploma", False)
    grupo_id = curso_row.get("grupo_id")
    
    # Color del estado
    color_estado = obtener_color_estado(estado)
    
    with st.container():
        # Header de la tarjeta
        col_header1, col_header2 = st.columns([3, 1])
        
        with col_header1:
            st.markdown(f"### 📖 {nombre_curso}")
            st.caption(f"Grupo: {codigo_grupo}")
        
        with col_header2:
            st.markdown(f"**{color_estado} {estado}**")
            if horas > 0:
                st.caption(f"⏱️ {horas} horas")
        
        # Información del curso
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"**🏢 Empresa:** {empresa}")
            st.markdown(f"**📍 Modalidad:** {modalidad}")
            st.markdown(f"**📅 Inicio:** {formatear_fecha(fecha_inicio)}")
            st.markdown(f"**🏁 Fin:** {formatear_fecha(fecha_fin)}")
        
        with col2:
            # Acciones disponibles
            st.markdown("**🎯 Acciones:**")
            
            # Botón de diploma si está disponible
            if tiene_diploma and grupo_id:
                if st.button(
                    "🏆 Ver Diploma",
                    key=f"diploma_{grupo_id}",
                    type="primary",
                    use_container_width=True
                ):
                    diploma_info = obtener_diploma_real(_supabase, grupo_id, email)
                    if diploma_info and diploma_info.get("url"):
                        st.success("✅ Diploma encontrado!")
                        st.markdown(f"**📄 Archivo:** {diploma_info.get('archivo_nombre', 'diploma.pdf')}")
                        if diploma_info.get("fecha_subida"):
                            fecha_subida_fmt = formatear_fecha(diploma_info["fecha_subida"])
                            st.caption(f"Subido el: {fecha_subida_fmt}")
                        
                        # Botón para abrir el diploma
                        st.link_button(
                            "🔗 Abrir diploma", 
                            diploma_info["url"],
                            use_container_width=True
                        )
                        st.balloons()
                    else:
                        st.warning("⚠️ Diploma no encontrado o en proceso")
                        st.info("Contacta con tu centro de formación si el problema persiste")
            else:
                if estado in ["Curso finalizado", "Finalizado"]:
                    st.info("🕐 Diploma pendiente")
                else:
                    st.info("🎓 Disponible al finalizar")
            
            # Información adicional según estado
            if estado == "En curso":
                st.success("✅ Curso activo")
            elif estado == "Pendiente de inicio":
                dias_restantes = calcular_dias_restantes(fecha_inicio)
                if dias_restantes and dias_restantes > 0:
                    st.info(f"🗓️ Comienza en {dias_restantes} días")
        
        st.divider()

def mostrar_sin_cursos():
    """Muestra mensaje cuando el alumno no tiene cursos."""
    st.info("📚 Aún no tienes cursos asignados")
    
    st.markdown("""
    ### ¿Qué puedes hacer?
    
    - **Contacta con tu empresa** para solicitar formación
    - **Consulta el catálogo** de cursos disponibles 
    - **Revisa tu email** por si hay comunicaciones
    
    ### ¿Necesitas ayuda?
    
    Si crees que deberías tener cursos asignados:
    - Contacta con Recursos Humanos
    - Habla con tu gestor de formación
    - Usa el soporte técnico de la empresa
    """)

def mostrar_historial_tabla(df_cursos: pd.DataFrame):
    """Muestra historial en formato tabla."""
    if df_cursos.empty:
        return
    
    st.subheader("📋 Historial Completo")
    
    # Preparar datos para mostrar
    df_mostrar = df_cursos.copy()
    df_mostrar["fecha_inicio_fmt"] = df_mostrar["grupo_fecha_inicio"].apply(formatear_fecha)
    df_mostrar["fecha_fin_fmt"] = df_mostrar["grupo_fecha_fin_prevista"].apply(formatear_fecha)
    df_mostrar["horas_fmt"] = df_mostrar["accion_horas"].apply(lambda x: f"{int(x)}" if pd.notna(x) and x > 0 else "0")
    df_mostrar["diploma_txt"] = df_mostrar["tiene_diploma"].apply(lambda x: "✅ Sí" if x else "❌ No")
    
    # Columnas a mostrar
    columnas_tabla = [
        "codigo_grupo", "accion_nombre", "horas_fmt", "accion_modalidad",
        "fecha_inicio_fmt", "fecha_fin_fmt", "estado_formacion", "diploma_txt"
    ]
    
    # Configuración de columnas
    column_config = {
        "codigo_grupo": st.column_config.TextColumn("Grupo", width="small"),
        "accion_nombre": st.column_config.TextColumn("Curso", width="large"),
        "horas_fmt": st.column_config.TextColumn("Horas", width="small"),
        "accion_modalidad": st.column_config.TextColumn("Modalidad", width="medium"),
        "fecha_inicio_fmt": st.column_config.TextColumn("Inicio", width="small"),
        "fecha_fin_fmt": st.column_config.TextColumn("Fin", width="small"),
        "estado_formacion": st.column_config.TextColumn("Estado", width="medium"),
        "diploma_txt": st.column_config.TextColumn("Diploma", width="small")
    }
    
    st.dataframe(
        df_mostrar[columnas_tabla],
        column_config=column_config,
        use_container_width=True,
        hide_index=True
    )

# =========================
# FUNCIÓN PRINCIPAL
# =========================

def main(supabase, session_state):
    """Función principal del portal del alumno."""
    
    # CSS mínimo nativo
    st.markdown("""
    <style>
    .stMetric { 
        background-color: #f8f9fa; 
        padding: 1rem; 
        border-radius: 0.5rem; 
        border: 1px solid #dee2e6;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("🎓 Mis Cursos")
    st.markdown("*Portal del alumno - Mi formación personal*")
    
    # Verificar usuario
    email = session_state.user.get("email")
    if not email:
        st.error("No se pudo identificar al usuario logueado.")
        return
    
    # Cargar datos usando la vista existente
    with st.spinner("Cargando tus cursos..."):
        df_cursos = cargar_cursos_alumno(supabase, email)
    
    # Si no hay cursos
    if df_cursos.empty:
        mostrar_sin_cursos()
        return
    
    # Mostrar resumen
    mostrar_resumen_alumno(df_cursos)
    st.markdown("---")
    
    # Aplicar filtros
    filtros, df_filtrado = mostrar_filtros_cursos(df_cursos)
    
    # Verificar resultados filtrados
    if df_filtrado.empty:
        st.warning("No se encontraron cursos con los filtros aplicados.")
        st.info("Modifica los criterios de búsqueda.")
        return
    
    # Mostrar información de filtros activos
    filtros_activos = []
    if filtros.get("texto"):
        filtros_activos.append(f"Texto: {filtros['texto']}")
    if filtros.get("año") and filtros.get("año") != "Todos":
        filtros_activos.append(f"Año: {filtros['año']}")
    if filtros.get("estado") and filtros.get("estado") != "Todos":
        filtros_activos.append(f"Estado: {filtros['estado']}")
    
    if filtros_activos:
        st.info(f"🔍 Filtros aplicados: {' | '.join(filtros_activos)}")
    
    st.markdown(f"### 📚 Mis Cursos ({len(df_filtrado)} encontrados)")
    
    # Tabs para diferentes vistas
    tab1, tab2 = st.tabs(["👀 Vista Detalle", "📊 Vista Tabla"])
    
    with tab1:
        # Vista en tarjetas detalladas
        for _, curso in df_filtrado.iterrows():
            mostrar_tarjeta_curso_funcional(curso.to_dict(), supabase, email)
    
    with tab2:
        # Vista en tabla compacta
        mostrar_historial_tabla(df_filtrado)
    
    # Información adicional
    with st.expander("ℹ️ Ayuda del portal"):
        st.markdown("""
        **Funcionalidades principales:**
        
        - **Resumen**: Métricas de tu progreso formativo
        - **Filtros**: Busca cursos por texto, año o estado  
        - **Vista Detalle**: Información completa de cada curso
        - **Vista Tabla**: Resumen compacto para exportar
        - **Diplomas**: Descarga cuando estén disponibles
        
        **Estados de cursos:**
        - 🟡 **Pendiente de inicio**: Aún no comenzado
        - 🟢 **En curso**: Actualmente activo
        - 🔵 **Finalizado**: Completado, diploma disponible
        
        **¿Falta información?**
        - Contacta con tu departamento de formación
        - Verifica que tu email esté actualizado
        - Revisa las comunicaciones de la empresa
        """)

if __name__ == "__main__":
    st.error("Este módulo debe ejecutarse desde la aplicación principal.")
