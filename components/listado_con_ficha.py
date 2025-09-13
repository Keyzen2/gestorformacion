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
    on_delete: Optional[Callable] = None,  # ✅ Soporte para eliminación
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
    """
    # Inicializar valores por defecto de forma segura
    campos_select = campos_select or {}
    campos_textarea = campos_textarea or {}
    campos_file = campos_file or {}
    campos_readonly = campos_readonly or []
    campos_password = campos_password or []
    campos_obligatorios = campos_obligatorios or []
    campos_help = campos_help or {}
    reactive_fields = reactive_fields or {}
    search_columns = search_columns or []

    # CSS mejorado y optimizado
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
    
    /* ✅ CORREGIDO: Mejor manejo de elementos vacíos */
    .elemento-oculto {
        display: none !important;
    }
    
    /* ✅ AÑADIDO: Estilos para confirmación de eliminación */
    .confirmar-eliminar {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { border-color: #ffeaa7; }
        50% { border-color: #fdcb6e; }
        100% { border-color: #ffeaa7; }
    }
    </style>
    """, unsafe_allow_html=True)

    # Verificar si hay datos
    if df is None or df.empty:
        st.info(f"📋 No hay {titulo.lower()}s para mostrar.")
        
        # Mostrar formulario de creación si está permitido
        if allow_creation and on_create:
            mostrar_formulario_creacion(
                titulo, on_create, campos_dinamicos, campos_select, campos_textarea, 
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
            st.metric("🔍 Columnas", len(columnas_visibles))
    with col3:
        if allow_creation:
            st.metric("➕ Crear nuevo", "Disponible")

    # Validaciones de columnas
    if not validar_columnas_disponibles(df, columnas_visibles, id_col):
        return

    # =========================
    # TABLA INTERACTIVA MEJORADA
    # =========================
    st.markdown('<div class="tabla-container">', unsafe_allow_html=True)
    
    # Preparar datos para mostrar
    df_display = preparar_datos_tabla(df, columnas_visibles, id_col)
    
    # Paginación mejorada
    items_per_page = st.selectbox(
        "Registros por página:", 
        [10, 25, 50, 100], 
        index=0,
        key=f"pagination_{titulo.lower()}"
    )
    
    # Cálculos de paginación
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
    
    # ✅ CORREGIDO: Manejo más robusto de selección
    try:
        event = st.dataframe(
            df_page,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key=f"table_{titulo.lower()}_{page}"
        )
    except Exception as e:
        st.error(f"❌ Error al mostrar tabla: {e}")
        return
    
    st.markdown('</div>', unsafe_allow_html=True)

    # =========================
    # MANEJO DE SELECCIÓN MEJORADO
    # =========================
    selected_row = None
    if event and hasattr(event, 'selection') and event.selection.get("rows"):
        try:
            selected_idx = event.selection["rows"][0]
            actual_idx = start_idx + selected_idx
            if actual_idx < len(df):
                selected_row = df.iloc[actual_idx]
                mostrar_formulario_edicion(
                    selected_row, titulo, on_save, on_delete, id_col,
                    campos_select, campos_textarea, campos_file, campos_readonly,
                    campos_dinamicos, campos_password, campos_obligatorios, 
                    campos_help, reactive_fields
                )
        except Exception as e:
            st.error(f"❌ Error al procesar selección: {e}")

    # =========================
    # FORMULARIO DE CREACIÓN
    # =========================
    if allow_creation and on_create:
        st.divider()
        mostrar_formulario_creacion(
            titulo=titulo,
            on_create=on_create,
            campos_dinamicos=campos_dinamicos,
            campos_select=campos_select,
            campos_textarea=campos_textarea,
            campos_file=campos_file,
            campos_password=campos_password,
            campos_help=campos_help,
            campos_obligatorios=campos_obligatorios,
            reactive_fields=reactive_fields
        )


def validar_columnas_disponibles(df, columnas_visibles, id_col):
    """Valida que las columnas necesarias estén disponibles."""
    columnas_disponibles = [col for col in columnas_visibles if col in df.columns]
    if not columnas_disponibles:
        st.error("❌ Las columnas especificadas no existen en los datos.")
        return False

    if id_col not in df.columns:
        st.error(f"❌ La columna ID '{id_col}' no existe en los datos.")
        return False
    
    return True


def preparar_datos_tabla(df, columnas_visibles, id_col):
    """Prepara y formatea los datos para mostrar en la tabla."""
    columnas_disponibles = [col for col in columnas_visibles if col in df.columns]
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
            df_display[col] = df_display[col].apply(
                lambda x: '🔗 Disponible' if pd.notna(x) and x != '' else '⚫ No disponible'
            )
    
    return df_display


def mostrar_formulario_edicion(fila, titulo, on_save, on_delete, id_col, 
                             campos_select, campos_textarea, campos_file, campos_readonly, 
                             campos_dinamicos, campos_password, campos_obligatorios, 
                             campos_help, reactive_fields):
    """✅ CORREGIDO: Formulario de edición con manejo mejorado de submit y confirmaciones."""
    
    st.markdown('<div class="ficha-container">', unsafe_allow_html=True)
    st.markdown(f"### ✏️ Editar {titulo}")
    
    # Mostrar información básica del registro
    mostrar_info_registro(fila, id_col)
    
    # Determinar campos a mostrar
    campos_a_mostrar = obtener_campos_a_mostrar(fila, campos_dinamicos, id_col, campos_readonly)

    # ✅ CORREGIDO: Clave única para evitar conflictos de formulario
    form_key = f"form_editar_{titulo}_{fila[id_col]}_{hash(str(fila))}"
    
    with st.form(form_key, clear_on_submit=False):
        datos_editados = {}
        
        # Organizar campos en columnas
        columnas = organizar_en_columnas(len(campos_a_mostrar))
        
        # Crear campos del formulario
        for i, campo in enumerate(campos_a_mostrar):
            if campo == id_col:
                continue
                
            valor_actual = obtener_valor_campo(fila, campo)
            col_actual = columnas[i % len(columnas)] if len(columnas) > 1 else columnas[0]
            
            with col_actual:
                # ✅ CORREGIDO: Campos reactivos funcionando
                if es_campo_visible(campo, fila, reactive_fields):
                    valor_editado = crear_campo_formulario(
                        campo, valor_actual, campos_select, campos_textarea, campos_file,
                        campos_readonly, campos_password, campos_help, f"edit_{fila[id_col]}",
                        es_obligatorio=(campo in campos_obligatorios)
                    )
                    
                    if valor_editado is not None:
                        datos_editados[campo] = valor_editado

        # Mostrar información adicional solo lectura
        if campos_readonly:
            mostrar_info_readonly(fila, campos_readonly)

        st.divider()

        # ✅ CORREGIDO: Botones de acción mejorados
        procesar_botones_accion_edicion(
            fila, id_col, datos_editados, on_save, on_delete, 
            campos_obligatorios, titulo
        )

    st.markdown('</div>', unsafe_allow_html=True)


def mostrar_info_registro(fila, id_col):
    """Muestra información básica del registro que se está editando."""
    if 'nombre' in fila:
        st.caption(f"Editando: {fila.get('nombre')}")
    elif 'nombre_completo' in fila:
        st.caption(f"Editando: {fila.get('nombre_completo')}")
    elif 'titulo' in fila:
        st.caption(f"Editando: {fila.get('titulo')}")
    else:
        st.caption(f"ID: {fila.get(id_col)}")


def obtener_campos_a_mostrar(fila, campos_dinamicos, id_col, campos_readonly):
    """Obtiene la lista de campos que se deben mostrar en el formulario."""
    if campos_dinamicos:
        try:
            # Convertir Series a dict de forma segura
            if isinstance(fila, pd.Series):
                datos_dict = fila.to_dict()
            else:
                datos_dict = fila
            campos_a_mostrar = campos_dinamicos(datos_dict)
        except Exception as e:
            st.error(f"❌ Error en campos dinámicos: {e}")
            # Usar todas las columnas disponibles como fallback
            campos_a_mostrar = [col for col in fila.keys() if col != id_col]
    else:
        campos_a_mostrar = [col for col in fila.keys() if col != id_col]

    # Filtrar campos que no deben mostrarse en edición
    campos_a_mostrar = [
        campo for campo in campos_a_mostrar 
        if campo not in ['created_at', 'updated_at'] and campo not in campos_readonly
    ]
    
    return campos_a_mostrar


def obtener_valor_campo(fila, campo):
    """Obtiene el valor actual de un campo de forma segura."""
    valor_actual = fila.get(campo, "")
    if pd.isna(valor_actual):
        valor_actual = ""
    return valor_actual


def organizar_en_columnas(num_campos):
    """Organiza los campos en columnas según su cantidad."""
    if num_campos > 8:
        st.markdown("#### 📝 Información básica")
        col1, col2 = st.columns(2)
        columnas = [col1, col2]
    elif num_campos > 4:
        col1, col2 = st.columns(2)
        columnas = [col1, col2]
    else:
        columnas = [st.container()]
    
    return columnas


def es_campo_visible(campo, fila, reactive_fields):
    """✅ CORREGIDO: Verifica si un campo debe ser visible según campos reactivos."""
    if not reactive_fields:
        return True
    
    # Verificar si el campo es dependiente de algún otro campo
    for trigger_field, dependent_fields in reactive_fields.items():
        if campo in dependent_fields:
            trigger_value = fila.get(trigger_field)
            # Lógica: mostrar campo dependiente solo si trigger no está vacío
            return bool(trigger_value and str(trigger_value).strip())
    
    # Si no es un campo dependiente, siempre visible
    return True


def mostrar_info_readonly(fila, campos_readonly):
    """Muestra información adicional de solo lectura."""
    with st.expander("ℹ️ Información adicional", expanded=False):
        for campo in campos_readonly:
            if campo in fila:
                valor = fila[campo]
                if pd.notna(valor):
                    valor_formateado = formatear_valor_readonly(campo, valor)
                    st.text(f"{campo.replace('_', ' ').title()}: {valor_formateado}")


def formatear_valor_readonly(campo, valor):
    """Formatea valores para campos de solo lectura."""
    if 'fecha' in campo.lower() or 'created' in campo.lower() or 'updated' in campo.lower():
        try:
            fecha = pd.to_datetime(valor)
            return fecha.strftime("%d/%m/%Y %H:%M")
        except:
            return str(valor)
    else:
        return str(valor)


def procesar_botones_accion_edicion(fila, id_col, datos_editados, on_save, on_delete, 
                                   campos_obligatorios, titulo):
    """✅ CORREGIDO: Procesamiento mejorado de botones de acción."""
    
    # Configurar estado de confirmación
    confirm_key = f"confirmar_eliminar_{titulo}_{fila[id_col]}"
    
    # Mostrar advertencia de confirmación si está activa
    if st.session_state.get(confirm_key, False):
        st.markdown('<div class="confirmar-eliminar">', unsafe_allow_html=True)
        st.warning("⚠️ **¿Confirmas la eliminación?** Esta acción no se puede deshacer.")
        st.caption(f"Se eliminará el registro: {fila.get('nombre', fila.get(id_col))}")
        st.markdown('</div>', unsafe_allow_html=True)

    # Botones de acción
    if on_delete:
        col_save, col_delete = st.columns(2)
        with col_save:
            btn_guardar = st.form_submit_button(
                "💾 Guardar Cambios", 
                type="primary", 
                use_container_width=True
            )
        with col_delete:
            texto_eliminar = "⚠️ ¡CONFIRMAR ELIMINAR!" if st.session_state.get(confirm_key, False) else "🗑️ Eliminar"
            btn_eliminar = st.form_submit_button(
                texto_eliminar, 
                use_container_width=True,
                help="Eliminar este registro permanentemente",
                type="secondary" if not st.session_state.get(confirm_key, False) else "primary"
            )
    else:
        btn_guardar = st.form_submit_button(
            "💾 Guardar Cambios", 
            type="primary", 
            use_container_width=True
        )
        btn_eliminar = False

    # ✅ CORREGIDO: Procesamiento de acciones mejorado
    if btn_guardar:
        procesar_guardado(fila[id_col], datos_editados, on_save, campos_obligatorios, confirm_key)
    
    if btn_eliminar and on_delete:
        procesar_eliminacion(fila[id_col], on_delete, confirm_key)


def procesar_guardado(record_id, datos_editados, on_save, campos_obligatorios, confirm_key):
    """Procesa el guardado de cambios con validaciones."""
    # Limpiar confirmación de eliminación si existía
    if confirm_key in st.session_state:
        st.session_state[confirm_key] = False
    
    # Validar campos obligatorios
    campos_faltantes = validar_campos_obligatorios(datos_editados, campos_obligatorios)
    
    if campos_faltantes:
        st.error(f"⚠️ Faltan campos obligatorios: {', '.join(campos_faltantes)}")
    else:
        try:
            on_save(record_id, datos_editados)
            st.success("✅ Cambios guardados correctamente.")
            # ✅ CORREGIDO: Rerun seguro
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")


def procesar_eliminacion(record_id, on_delete, confirm_key):
    """✅ CORREGIDO: Procesamiento de eliminación con confirmación robusta."""
    if not st.session_state.get(confirm_key, False):
        # Primera vez: solicitar confirmación
        st.session_state[confirm_key] = True
        st.rerun()
    else:
        # Segunda vez: ejecutar eliminación
        try:
            on_delete(record_id)
            st.session_state[confirm_key] = False
            st.success("✅ Registro eliminado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al eliminar: {e}")
            st.session_state[confirm_key] = False


def mostrar_formulario_creacion(titulo, on_create, campos_dinamicos, campos_select, campos_textarea, 
                              campos_file, campos_password, campos_help, campos_obligatorios, reactive_fields):
    """✅ CORREGIDO: Formulario de creación con mejor manejo."""
    campos_help = campos_help or {}
                                  
    st.markdown('<div class="crear-container">', unsafe_allow_html=True)
    st.markdown(f"### ➕ Crear Nuevo {titulo}")
    st.caption("Completa los campos para crear un nuevo registro.")
    
    # Obtener campos para creación
    campos_crear = obtener_campos_creacion(
        campos_dinamicos, campos_select, campos_textarea, campos_file, campos_password
