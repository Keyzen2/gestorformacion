import streamlit as st
import pandas as pd
from typing import Dict, List, Callable, Any, Optional

def listado_con_ficha(
    df: pd.DataFrame,
    columnas_visibles: List[str],
    titulo: str,
    on_save: Callable,
    id_col: str = "id",
    on_create: Optional[Callable] = None,
    on_delete: Optional[Callable] = None,
    campos_select: Optional[Dict[str, List]] = None,
    campos_textarea: Optional[Dict[str, Dict]] = None,
    campos_file: Optional[Dict[str, Dict]] = None,
    campos_readonly: Optional[List[str]] = None,
    campos_dinamicos: Optional[Callable] = None,
    campos_password: Optional[List[str]] = None,
    campos_obligatorios: Optional[List[str]] = None,
    allow_creation: bool = True,
    campos_help: Optional[Dict[str, str]] = None,
    reactive_fields: Optional[Dict[str, List[str]]] = None,
    search_columns: Optional[List[str]] = None
):
    """
    Componente mejorado que muestra una tabla interactiva con Streamlit
    y formularios para editar/crear registros.
    
    Args:
        df: DataFrame con los datos
        columnas_visibles: Lista de columnas a mostrar en la tabla
        titulo: Título para el formulario
        on_save: Función para guardar cambios (id, datos_editados)
        id_col: Nombre de la columna ID
        on_create: Función para crear nuevos registros (datos_nuevos)
        on_delete: Función para eliminar registros (id)
        campos_select: Dict con opciones para campos select
        campos_textarea: Dict para campos de texto largo
        campos_file: Dict para campos de archivo
        campos_readonly: Lista de campos de solo lectura
        campos_dinamicos: Función que devuelve campos según contexto
        campos_password: Lista de campos tipo password
        campos_obligatorios: Lista de campos obligatorios
        allow_creation: Si permitir crear nuevos registros
        campos_help: Dict con textos de ayuda
        reactive_fields: Dict con campos que dependen de otros
        search_columns: Columnas donde buscar
    """
    
    # Inicializar valores por defecto
    campos_select = campos_select or {}
    campos_textarea = campos_textarea or {}
    campos_file = campos_file or {}
    campos_readonly = campos_readonly or []
    campos_password = campos_password or []
    campos_obligatorios = campos_obligatorios or []
    campos_help = campos_help or {}
    reactive_fields = reactive_fields or {}
    search_columns = search_columns or []

    # CSS mejorado para mejor apariencia
    st.markdown("""
    <style>
    .tabla-container {
        border: 1px solid #e1e5e9;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        background: #f8f9fa;
    }
    
    .ficha-container {
        border: 2px solid #2196f3;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        background: linear-gradient(135deg, #f0f8ff 0%, #ffffff 100%);
        box-shadow: 0 4px 12px rgba(33, 150, 243, 0.15);
    }
    
    .crear-container {
        border: 2px solid #4caf50;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        background: linear-gradient(135deg, #f1f8e9 0%, #ffffff 100%);
        box-shadow: 0 4px 12px rgba(76, 175, 80, 0.15);
    }
    
    .registro-activo {
        background-color: #e3f2fd !important;
        border-left: 4px solid #2196f3;
        padding: 12px;
        margin: 4px 0;
        border-radius: 6px;
    }
    
    .campo-obligatorio label {
        font-weight: 600;
        color: #1976d2;
    }
    
    .campo-obligatorio label:after {
        content: " *";
        color: #f44336;
        font-weight: bold;
    }
    
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #e1e5e9;
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 1.2rem;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

    if df is None or df.empty:
        st.info(f"📋 No hay {titulo.lower()}s para mostrar.")
        
        # Mostrar formulario de creación si está permitido
        if allow_creation and on_create:
            mostrar_formulario_creacion(
                titulo, on_create, campos_select, campos_textarea, 
                campos_file, campos_password, campos_obligatorios, 
                campos_help, reactive_fields
            )
        return

    # =========================
    # BÚSQUEDA INTEGRADA
    # =========================
    if search_columns:
        st.markdown("### 🔍 Búsqueda rápida")
        search_term = st.text_input(
            "Buscar...", 
            placeholder=f"Buscar en: {', '.join(search_columns)}",
            key=f"search_{titulo.lower()}"
        )
        
        if search_term:
            search_mask = pd.Series([False] * len(df))
            for col in search_columns:
                if col in df.columns:
                    search_mask = search_mask | df[col].astype(str).str.contains(
                        search_term, case=False, na=False
                    )
            df = df[search_mask]
            
            if df.empty:
                st.warning(f"🔍 No se encontraron resultados para '{search_term}'")
                return

    # =========================
    # TABLA PRINCIPAL MEJORADA
    # =========================
    st.markdown(f"### 📊 Lista de {titulo}s")
    
    # Métricas rápidas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📋 Total registros", len(df))
    with col2:
        if search_columns and 'search_term' in locals() and search_term:
            st.metric("🔍 Encontrados", len(df))
        else:
            st.metric("📁 Columnas", len(columnas_visibles))
    with col3:
        if allow_creation:
            st.metric("➕ Crear nuevo", "Disponible")

    # Verificar columnas disponibles
    columnas_disponibles = [col for col in columnas_visibles if col in df.columns]
    if not columnas_disponibles:
        st.error("❌ Las columnas especificadas no existen en los datos.")
        return

    if id_col not in df.columns:
        st.error(f"❌ La columna ID '{id_col}' no existe en los datos.")
        return

    # =========================
    # TABLA INTERACTIVA MEJORADA
    # =========================
    st.markdown('<div class="tabla-container">', unsafe_allow_html=True)
    
    # Preparar datos para mostrar
    df_display = df[columnas_disponibles + [id_col]].copy()
    
    # Formatear datos para mejor visualización
    for col in df_display.columns:
        if col == id_col:
            continue
            
        if df_display[col].dtype == 'bool':
            df_display[col] = df_display[col].map({
                True: '✅ Sí', 
                False: '❌ No', 
                None: '⚪ N/A'
            })
        elif pd.api.types.is_datetime64_any_dtype(df_display[col]):
            df_display[col] = pd.to_datetime(df_display[col], errors='coerce').dt.strftime('%d/%m/%Y')
        elif col.endswith('_url') and not df_display[col].isna().all():
            # Para URLs, mostrar si existe o no
            df_display[col] = df_display[col].apply(
                lambda x: '🔗 Disponible' if pd.notna(x) and x != '' else '⚫ No disponible'
            )

    # Paginación mejorada
    items_per_page = st.selectbox(
        "Registros por página:", 
        [10, 25, 50, 100], 
        index=0,
        key=f"pagination_{titulo.lower()}"
    )
    
    total_pages = (len(df_display) - 1) // items_per_page + 1
    
    if total_pages > 1:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            page = st.selectbox(
                f"Página (de {total_pages}):", 
                range(1, total_pages + 1),
                key=f"page_{titulo.lower()}"
            )
    else:
        page = 1

    # Calcular índices para paginación
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(df_display))
    df_page = df_display.iloc[start_idx:end_idx]

    # Mostrar tabla con selección
    st.markdown("#### 👀 Datos")
    
    # Usar dataframe interactivo de Streamlit
    event = st.dataframe(
        df_page,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"table_{titulo.lower()}_{page}"
    )
    
    st.markdown('</div>', unsafe_allow_html=True)

    # =========================
    # MANEJO DE SELECCIÓN
    # =========================
    selected_row = None
    if event.selection and event.selection.get("rows"):
        # Obtener la fila seleccionada
        selected_idx = event.selection["rows"][0]
        actual_idx = start_idx + selected_idx
        
        if actual_idx < len(df):
            selected_row = df.iloc[actual_idx]
            
            # Mostrar formulario de edición
            mostrar_formulario_edicion(
                selected_row, titulo, on_save, on_delete, id_col,
                campos_select, campos_textarea, campos_file, campos_readonly,
                campos_dinamicos, campos_password, campos_obligatorios, 
                campos_help, reactive_fields
            )

    # =========================
    # FORMULARIO DE CREACIÓN
    # =========================
    if allow_creation and on_create:
        st.divider()
        mostrar_formulario_creacion(
            titulo, on_create, campos_select, campos_textarea,
            campos_file, campos_password, campos_obligatorios,
            campos_help, reactive_fields
        )


def mostrar_formulario_edicion(fila, titulo, on_save, on_delete, id_col, campos_select,
                             campos_textarea, campos_file, campos_readonly, campos_dinamicos,
                             campos_password, campos_obligatorios, campos_help, reactive_fields):
    """Muestra el formulario de edición para un registro."""
    
    st.markdown('<div class="ficha-container">', unsafe_allow_html=True)
    st.markdown(f"### ✏️ Editar {titulo}")
    st.markdown(f"**ID:** `{fila[id_col]}`")
    
    # Determinar campos a mostrar
    if campos_dinamicos:
        try:
            campos_a_mostrar = campos_dinamicos(fila)
        except Exception as e:
            st.error(f"❌ Error en campos dinámicos: {e}")
            campos_a_mostrar = [col for col in fila.index if col != id_col]
    else:
        campos_a_mostrar = [col for col in fila.index if col != id_col]

    with st.form(f"form_editar_{fila[id_col]}", clear_on_submit=False):
        datos_editados = {}
        
        # Organizar en columnas si hay muchos campos
        if len(campos_a_mostrar) > 8:
            col1, col2 = st.columns(2)
            columnas = [col1, col2]
        else:
            columnas = [st]
        
        for i, campo in enumerate(campos_a_mostrar):
            if campo == id_col:
                continue
                
            valor_actual = fila.get(campo, "")
            if pd.isna(valor_actual):
                valor_actual = ""

            # Determinar en qué columna mostrar el campo
            col_actual = columnas[i % len(columnas)] if len(columnas) > 1 else columnas[0]
            
            with col_actual:
                valor_editado = crear_campo_formulario(
                    campo, valor_actual, campos_select, campos_textarea, campos_file,
                    campos_readonly, campos_password, campos_obligatorios, 
                    campos_help, f"edit_{fila[id_col]}"
                )
                
                if valor_editado is not None:
                    datos_editados[campo] = valor_editado

        # Botones de acción mejorados
        col_save, col_delete, col_cancel = st.columns(3)
        
        with col_save:
            btn_guardar = st.form_submit_button(
                "💾 Guardar Cambios", 
                type="primary", 
                use_container_width=True
            )
        
        with col_delete:
            if on_delete:
                btn_eliminar = st.form_submit_button(
                    "🗑️ Eliminar", 
                    use_container_width=True
                )
            else:
                btn_eliminar = False

        with col_cancel:
            btn_cancelar = st.form_submit_button(
                "❌ Cancelar", 
                use_container_width=True
            )

        # Procesar acciones
        if btn_guardar:
            try:
                # Añadir ID para identificar el registro
                datos_editados[id_col] = fila[id_col]
                on_save(fila[id_col], datos_editados)
            except Exception as e:
                st.error(f"❌ Error al guardar: {e}")
        
        if btn_eliminar and on_delete:
            confirmar_key = f"confirmar_eliminar_{fila[id_col]}"
            if st.session_state.get(confirmar_key, False):
                try:
                    on_delete(fila[id_col])
                    st.session_state[confirmar_key] = False
                except Exception as e:
                    st.error(f"❌ Error al eliminar: {e}")
            else:
                st.session_state[confirmar_key] = True
                st.warning("⚠️ Haz clic en Eliminar otra vez para confirmar.")
                st.rerun()

        if btn_cancelar:
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def mostrar_formulario_creacion(titulo, on_create, campos_select, campos_textarea,
                              campos_file, campos_password, campos_obligatorios,
                              campos_help, reactive_fields):
    """Muestra el formulario para crear un nuevo registro."""
    
    st.markdown('<div class="crear-container">', unsafe_allow_html=True)
    st.markdown(f"### ➕ Crear Nuevo {titulo}")
    
    with st.form("form_crear", clear_on_submit=True):
        datos_nuevos = {}
        
        # Obtener todos los campos posibles
        todos_campos = set()
        todos_campos.update(campos_select.keys())
        todos_campos.update(campos_textarea.keys())
        todos_campos.update(campos_file.keys())
        todos_campos.update(campos_password)
        
        # Añadir campos básicos si no hay campos definidos
        if not todos_campos:
            todos_campos.update(['nombre', 'email'])
        
        # Añadir campos obligatorios
        todos_campos.update(campos_obligatorios)
        
        # Organizar en columnas
        campos_lista = sorted(list(todos_campos))
        if len(campos_lista) > 6:
            col1, col2 = st.columns(2)
            columnas = [col1, col2]
        else:
            columnas = [st]
        
        for i, campo in enumerate(campos_lista):
            col_actual = columnas[i % len(columnas)] if len(columnas) > 1 else columnas[0]
            
            with col_actual:
                valor = crear_campo_formulario(
                    campo, "", campos_select, campos_textarea, campos_file,
                    [], campos_password, campos_obligatorios, campos_help, "create"
                )
                
                if valor is not None and valor != "":
                    datos_nuevos[campo] = valor

        btn_crear = st.form_submit_button(
            f"➕ Crear {titulo}", 
            type="primary", 
            use_container_width=True
        )
        
        if btn_crear:
            # Validar campos obligatorios
            campos_faltantes = []
            for campo in campos_obligatorios:
                if campo not in datos_nuevos or not datos_nuevos[campo]:
                    campos_faltantes.append(campo)
            
            if campos_faltantes:
                st.error(f"⚠️ Campos obligatorios faltantes: {', '.join(campos_faltantes)}")
            else:
                try:
                    on_create(datos_nuevos)
                except Exception as e:
                    st.error(f"❌ Error al crear: {e}")

    st.markdown('</div>', unsafe_allow_html=True)


def crear_campo_formulario(campo, valor_actual, campos_select, campos_textarea, campos_file,
                         campos_readonly, campos_password, campos_obligatorios, campos_help, prefix):
    """Crea un campo de formulario según el tipo."""
    
    # Texto de ayuda
    help_text = campos_help.get(campo, None)
    
    # Determinar si es obligatorio
    es_obligatorio = campo in campos_obligatorios
    
    # Crear contenedor con clase CSS para campos obligatorios
    if es_obligatorio:
        st.markdown(f'<div class="campo-obligatorio">', unsafe_allow_html=True)
    
    # Campo de solo lectura
    if campo in campos_readonly:
        valor = st.text_input(
            f"{campo.replace('_', ' ').title()}", 
            value=str(valor_actual), 
            disabled=True, 
            help=help_text,
            key=f"{prefix}_{campo}"
        )
        if es_obligatorio:
            st.markdown('</div>', unsafe_allow_html=True)
        return valor_actual
    
    # Campo de contraseña
    if campo in campos_password:
        valor = st.text_input(
            f"{campo.replace('_', ' ').title()}", 
            value="", 
            type="password", 
            help=help_text,
            key=f"{prefix}_{campo}"
        )
        if es_obligatorio:
            st.markdown('</div>', unsafe_allow_html=True)
        return valor
    
    # Campo select
    if campo in campos_select:
        opciones = campos_select[campo]
        try:
            index = opciones.index(valor_actual) if valor_actual in opciones else 0
        except (ValueError, TypeError):
            index = 0
        
        valor = st.selectbox(
            f"{campo.replace('_', ' ').title()}", 
            opciones, 
            index=index, 
            help=help_text,
            key=f"{prefix}_{campo}"
        )
        if es_obligatorio:
            st.markdown('</div>', unsafe_allow_html=True)
        return valor
    
    # Campo textarea
    if campo in campos_textarea:
        valor = st.text_area(
            f"{campo.replace('_', ' ').title()}", 
            value=str(valor_actual), 
            help=help_text,
            key=f"{prefix}_{campo}"
        )
        if es_obligatorio:
            st.markdown('</div>', unsafe_allow_html=True)
        return valor
    
    # Campo file
    if campo in campos_file:
        config = campos_file[campo]
        valor = st.file_uploader(
            config.get("label", f"{campo.replace('_', ' ').title()}"), 
            type=config.get("type", None), 
            help=help_text or config.get("help", None),
            key=f"{prefix}_{campo}"
        )
        if es_obligatorio:
            st.markdown('</div>', unsafe_allow_html=True)
        return valor
    
    # Campo booleano
    if isinstance(valor_actual, bool) or str(valor_actual).lower() in ['true', 'false', 'sí', 'no', '✅', '❌']:
        valor_bool = valor_actual if isinstance(valor_actual, bool) else str(valor_actual).lower() in ['true', 'sí', '✅']
        valor = st.checkbox(
            f"{campo.replace('_', ' ').title()}", 
            value=valor_bool, 
            help=help_text,
            key=f"{prefix}_{campo}"
        )
        if es_obligatorio:
            st.markdown('</div>', unsafe_allow_html=True)
        return valor
    
    # Campo de texto por defecto
    valor = st.text_input(
        f"{campo.replace('_', ' ').title()}", 
        value=str(valor_actual), 
        help=help_text,
        key=f"{prefix}_{campo}"
    )
    
    if es_obligatorio:
        st.markdown('</div>', unsafe_allow_html=True)
    
    return valor
