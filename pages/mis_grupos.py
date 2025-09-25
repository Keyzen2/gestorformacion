import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import Optional, Dict, List

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
def cargar_cursos_alumno(supabase, email: str):
    """Carga los cursos del alumno desde la base de datos."""
    try:
        # Buscar participante por email
        participante_res = supabase.table("participantes").select("*").eq("email", email).execute()
        
        if not participante_res.data:
            return pd.DataFrame()
        
        participante = participante_res.data[0]
        participante_id = participante["id"]
        
        # Obtener grupos del participante usando relación N:N
        grupos_participante_res = supabase.table("participantes_grupos").select("""
            grupo_id,
            fecha_inscripcion,
            grupo:grupos(
                id, codigo_grupo, fecha_inicio, fecha_fin, fecha_fin_prevista, modalidad,
                accion_formativa_id,
                accion_formativa:acciones_formativas(
                    id, codigo_accion, nombre, horas, modalidad,
                    empresa:empresas(nombre)
                )
            )
        """).eq("participante_id", participante_id).execute()
        
        if not grupos_participante_res.data:
            return pd.DataFrame()
        
        # Procesar datos para el DataFrame
        cursos_data = []
        for relacion in grupos_participante_res.data:
            grupo = relacion.get("grupo", {})
            accion = grupo.get("accion_formativa", {})
            empresa_accion = accion.get("empresa", {})
            
            # Determinar estado del curso
            estado = determinar_estado_curso(grupo)
            
            curso_info = {
                "grupo_id": grupo.get("id"),
                "participante_id": participante_id,
                "codigo_grupo": grupo.get("codigo_grupo", "Sin código"),
                "codigo_accion": accion.get("codigo_accion", "Sin código"),
                "nombre_curso": accion.get("nombre", "Sin nombre"),
                "horas": accion.get("horas", 0),
                "modalidad": accion.get("modalidad", grupo.get("modalidad", "Sin especificar")),
                "empresa_formadora": empresa_accion.get("nombre", "Sin empresa"),
                "fecha_inicio": grupo.get("fecha_inicio"),
                "fecha_fin": grupo.get("fecha_fin") or grupo.get("fecha_fin_prevista"),
                "fecha_inscripcion": relacion.get("fecha_inscripcion"),
                "estado": estado
            }
            
            cursos_data.append(curso_info)
        
        return pd.DataFrame(cursos_data)
        
    except Exception as e:
        st.error(f"Error cargando cursos: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300) 
def cargar_diplomas_alumno(supabase, participante_id: int):
    """Carga los diplomas disponibles para el alumno."""
    try:
        diplomas_res = supabase.table("diplomas").select("*").eq(
            "participante_id", participante_id
        ).execute()
        
        diplomas = {}
        for diploma in diplomas_res.data or []:
            grupo_id = diploma.get("grupo_id")
            if grupo_id:
                diplomas[grupo_id] = {
                    "id": diploma["id"],
                    "url": diploma.get("url"),
                    "archivo_nombre": diploma.get("archivo_nombre", "diploma.pdf"),
                    "fecha_subida": diploma.get("fecha_subida")
                }
        
        return diplomas
        
    except Exception as e:
        st.error(f"Error cargando diplomas: {e}")
        return {}

def determinar_estado_curso(grupo: Dict) -> str:
    """Determina el estado actual de un curso según las fechas."""
    hoy = date.today()
    
    fecha_inicio = grupo.get("fecha_inicio")
    fecha_fin = grupo.get("fecha_fin") or grupo.get("fecha_fin_prevista")
    
    if not fecha_inicio:
        return "Sin fechas definidas"
    
    try:
        fecha_inicio_dt = pd.to_datetime(fecha_inicio).date()
        
        if fecha_inicio_dt > hoy:
            return "Pendiente de inicio"
        
        if fecha_fin:
            fecha_fin_dt = pd.to_datetime(fecha_fin).date()
            if fecha_fin_dt < hoy:
                return "Finalizado"
            elif fecha_inicio_dt <= hoy <= fecha_fin_dt:
                return "En curso"
        
        return "En curso"
        
    except:
        return "Fechas inválidas"

def obtener_color_estado(estado: str) -> str:
    """Devuelve el color apropiado para cada estado."""
    colores = {
        "Pendiente de inicio": "🟡",
        "En curso": "🟢", 
        "Finalizado": "🔵",
        "Sin fechas definidas": "⚪",
        "Fechas inválidas": "🔴"
    }
    return colores.get(estado, "⚪")

def formatear_fecha(fecha_str: Optional[str]) -> str:
    """Formatea una fecha para mostrar al usuario."""
    if not fecha_str:
        return "No definida"
    
    try:
        fecha_dt = pd.to_datetime(fecha_str)
        return fecha_dt.strftime("%d/%m/%Y")
    except:
        return "Fecha inválida"

# =========================
# COMPONENTES DE LA INTERFAZ
# =========================

def mostrar_resumen_alumno(df_cursos: pd.DataFrame, diplomas: Dict):
    """Muestra un resumen general del alumno."""
    if df_cursos.empty:
        return
    
    # Calcular métricas
    total_cursos = len(df_cursos)
    total_horas = df_cursos["horas"].sum()
    cursos_completados = len(df_cursos[df_cursos["estado"] == "Finalizado"])
    diplomas_disponibles = len(diplomas)
    
    st.subheader("📊 Mi Resumen de Formación")
    
    # Mostrar métricas con st.metric
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "📚 Total Cursos",
            total_cursos,
            help="Cursos en los que estás inscrito"
        )
    
    with col2:
        st.metric(
            "⏱️ Total Horas",
            f"{total_horas}h",
            help="Horas totales de formación"
        )
    
    with col3:
        st.metric(
            "✅ Completados",
            cursos_completados,
            delta=f"{(cursos_completados/total_cursos*100):.0f}%" if total_cursos > 0 else "0%",
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
        # Filtro por texto
        filtro_texto = st.text_input(
            "Buscar curso o empresa",
            placeholder="Nombre del curso, código...",
            help="Busca en nombre del curso, código o empresa"
        )
    
    with col2:
        # Filtro por año
        años_disponibles = []
        for fecha in df_cursos["fecha_inicio"].dropna():
            try:
                año = pd.to_datetime(fecha).year
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
        # Filtro por estado
        estados_disponibles = df_cursos["estado"].unique().tolist()
        filtro_estado = st.selectbox(
            "Estado del curso",
            ["Todos"] + estados_disponibles,
            help="Filtrar por estado actual"
        )
    
    # Aplicar filtros
    df_filtrado = df_cursos.copy()
    
    if filtro_texto:
        mascara = (
            df_filtrado["nombre_curso"].str.contains(filtro_texto, case=False, na=False) |
            df_filtrado["codigo_accion"].str.contains(filtro_texto, case=False, na=False) |
            df_filtrado["codigo_grupo"].str.contains(filtro_texto, case=False, na=False) |
            df_filtrado["empresa_formadora"].str.contains(filtro_texto, case=False, na=False)
        )
        df_filtrado = df_filtrado[mascara]
    
    if filtro_año != "Todos":
        try:
            año_int = int(filtro_año)
            mascara_año = df_filtrado["fecha_inicio"].apply(
                lambda x: pd.to_datetime(x, errors='coerce').year == año_int if pd.notna(x) else False
            )
            df_filtrado = df_filtrado[mascara_año]
        except:
            pass
    
    if filtro_estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["estado"] == filtro_estado]
    
    filtros_aplicados = {
        "texto": filtro_texto,
        "año": filtro_año,
        "estado": filtro_estado
    }
    
    return filtros_aplicados, df_filtrado

def mostrar_tarjeta_curso(curso: Dict, diploma: Optional[Dict] = None):
    """Muestra una tarjeta individual para cada curso."""
    
    # Determinar el color del estado
    color_estado = obtener_color_estado(curso["estado"])
    
    with st.container():
        # Header de la tarjeta
        col_header1, col_header2 = st.columns([3, 1])
        
        with col_header1:
            st.markdown(f"### 📖 {curso['nombre_curso']}")
            st.caption(f"Código: {curso['codigo_accion']} | Grupo: {curso['codigo_grupo']}")
        
        with col_header2:
            st.markdown(f"**{color_estado} {curso['estado']}**")
            if curso['horas'] > 0:
                st.caption(f"⏱️ {curso['horas']} horas")
        
        # Información del curso
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"**🏢 Empresa formadora:** {curso['empresa_formadora']}")
            st.markdown(f"**📍 Modalidad:** {curso['modalidad']}")
            st.markdown(f"**📅 Inicio:** {formatear_fecha(curso['fecha_inicio'])}")
            st.markdown(f"**🏁 Fin:** {formatear_fecha(curso['fecha_fin'])}")
            
            if curso.get("fecha_inscripcion"):
                st.caption(f"Inscrito el: {formatear_fecha(curso['fecha_inscripcion'])}")
        
        with col2:
            # Acciones disponibles
            st.markdown("**🎯 Acciones:**")
            
            # Botón de diploma si está disponible
            if diploma:
                if st.button(
                    "🏆 Descargar Diploma",
                    key=f"diploma_{curso['grupo_id']}",
                    type="primary",
                    use_container_width=True,
                    help=f"Diploma subido el {formatear_fecha(diploma.get('fecha_subida'))}"
                ):
                    if diploma.get("url"):
                        st.markdown(f"[🔗 Abrir diploma en nueva pestaña]({diploma['url']})")
                        st.balloons()  # Efecto visual de celebración
                    else:
                        st.error("Error al acceder al diploma")
            else:
                if curso["estado"] == "Finalizado":
                    st.info("🕐 Diploma pendiente de subida")
                else:
                    st.info("🎓 Diploma disponible al finalizar")
            
            # Información adicional
            if curso["estado"] == "En curso":
                st.success("✅ Curso activo")
            elif curso["estado"] == "Pendiente de inicio":
                days_to_start = None
                try:
                    fecha_inicio = pd.to_datetime(curso["fecha_inicio"]).date()
                    days_to_start = (fecha_inicio - date.today()).days
                except:
                    pass
                
                if days_to_start and days_to_start > 0:
                    st.info(f"🗓️ Comienza en {days_to_start} días")
        
        st.divider()

def mostrar_sin_cursos():
    """Muestra mensaje cuando el alumno no tiene cursos."""
    st.info("📚 Aún no tienes cursos asignados")
    
    st.markdown("""
    ### ¿Qué puedes hacer?
    
    - **Contacta con tu empresa** para solicitar formación
    - **Consulta el catálogo** de cursos disponibles con tu gestor
    - **Revisa tu email** por si hay comunicaciones pendientes
    
    ### ¿Necesitas ayuda?
    
    Si crees que deberías tener cursos asignados, contacta con:
    - Tu departamento de Recursos Humanos
    - El gestor de formación de tu empresa  
    - Soporte técnico de la plataforma
    """)

def mostrar_historial_completo(df_cursos: pd.DataFrame, diplomas: Dict):
    """Muestra un historial completo en formato tabla."""
    if df_cursos.empty:
        return
    
    st.subheader("📋 Historial Completo")
    
    # Preparar datos para la tabla
    df_tabla = df_cursos.copy()
    df_tabla["fecha_inicio_fmt"] = df_tabla["fecha_inicio"].apply(formatear_fecha)
    df_tabla["fecha_fin_fmt"] = df_tabla["fecha_fin"].apply(formatear_fecha)
    df_tabla["tiene_diploma"] = df_tabla["grupo_id"].apply(lambda x: "Sí" if x in diplomas else "No")
    
    # Configurar columnas para mostrar
    columnas_mostrar = [
        "codigo_accion", "nombre_curso", "horas", "modalidad", 
        "fecha_inicio_fmt", "fecha_fin_fmt", "estado", "tiene_diploma"
    ]
    
    # Configuración de columnas
    column_config = {
        "codigo_accion": st.column_config.TextColumn("Código", width="small"),
        "nombre_curso": st.column_config.TextColumn("Curso", width="large"),
        "horas": st.column_config.NumberColumn("Horas", width="small"),
        "modalidad": st.column_config.TextColumn("Modalidad", width="medium"),
        "fecha_inicio_fmt": st.column_config.TextColumn("Inicio", width="small"),
        "fecha_fin_fmt": st.column_config.TextColumn("Fin", width="small"), 
        "estado": st.column_config.TextColumn("Estado", width="medium"),
        "tiene_diploma": st.column_config.TextColumn("Diploma", width="small")
    }
    
    # Mostrar tabla
    st.dataframe(
        df_tabla[columnas_mostrar],
        column_config=column_config,
        use_container_width=True,
        hide_index=True
    )

# =========================
# FUNCIÓN PRINCIPAL
# =========================

def main(supabase, session_state):
    """Función principal del portal del alumno."""
    
    # CSS mínimo para mejorar la apariencia
    st.markdown("""
    <style>
    .stMetric { background-color: #f8f9fa; padding: 1rem; border-radius: 0.5rem; }
    .curso-finalizado { border-left: 4px solid #28a745; }
    .curso-en-curso { border-left: 4px solid #17a2b8; }
    .curso-pendiente { border-left: 4px solid #ffc107; }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("🎓 Mis Cursos")
    st.markdown("*Portal del alumno - Gestión de formación personal*")
    
    # Verificar usuario
    email = session_state.user.get("email")
    if not email:
        st.error("No se pudo identificar al usuario.")
        return
    
    # Cargar datos
    with st.spinner("Cargando tus cursos..."):
        df_cursos = cargar_cursos_alumno(supabase, email)
    
    # Si no hay cursos, mostrar mensaje
    if df_cursos.empty:
        mostrar_sin_cursos()
        return
    
    # Cargar diplomas
    participante_id = df_cursos["participante_id"].iloc[0] if not df_cursos.empty else None
    diplomas = cargar_diplomas_alumno(supabase, participante_id) if participante_id else {}
    
    # Mostrar resumen
    mostrar_resumen_alumno(df_cursos, diplomas)
    
    st.markdown("---")
    
    # Aplicar filtros
    filtros, df_filtrado = mostrar_filtros_cursos(df_cursos)
    
    # Mostrar resultados filtrados
    if df_filtrado.empty:
        st.warning("No se encontraron cursos con los filtros aplicados.")
        st.info("Intenta modificar los criterios de búsqueda.")
        return
    
    # Mostrar información de filtros aplicados
    if any(filtros.values()):
        filtros_activos = [f"{k}: {v}" for k, v in filtros.items() if v and v != "Todos"]
        if filtros_activos:
            st.info(f"🔍 Filtros aplicados: {' | '.join(filtros_activos)}")
    
    st.markdown(f"### 📚 Mis Cursos ({len(df_filtrado)} encontrados)")
    
    # Tabs para diferentes vistas
    tab1, tab2 = st.tabs(["👀 Vista Tarjetas", "📊 Vista Tabla"])
    
    with tab1:
        # Vista en tarjetas (por defecto)
        for _, curso in df_filtrado.iterrows():
            diploma = diplomas.get(curso["grupo_id"])
            mostrar_tarjeta_curso(curso.to_dict(), diploma)
    
    with tab2:
        # Vista en tabla
        mostrar_historial_completo(df_filtrado, diplomas)
    
    # Información adicional en expander
    with st.expander("ℹ️ Información sobre el portal"):
        st.markdown("""
        **¿Cómo usar este portal?**
        
        - **Vista Tarjetas**: Información detallada de cada curso con acciones rápidas
        - **Vista Tabla**: Resumen completo en formato tabla para exportar o imprimir
        - **Filtros**: Busca cursos específicos por texto, año o estado
        - **Diplomas**: Descarga automática cuando estén disponibles
        
        **Estados de los cursos:**
        - 🟡 **Pendiente de inicio**: El curso aún no ha comenzado
        - 🟢 **En curso**: Curso actualmente activo
        - 🔵 **Finalizado**: Curso completado, diploma disponible próximamente
        
        **¿Problemas?**
        - Si no ves un curso esperado, contacta con tu gestor de formación
        - Si falta un diploma, puede estar en proceso de generación
        - Para soporte técnico, usa los canales habituales de tu empresa
        """)

if __name__ == "__main__":
    # Esta sección solo se ejecuta si el archivo se ejecuta directamente
    st.error("Este archivo debe ejecutarse como parte de la aplicación principal.")
