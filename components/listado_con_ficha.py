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
    on_delete: Optional[Callable] = None,  # ✅ AÑADIDO: soporte para eliminación
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
        display: none !important; /* ✅ CORREGIDO: Ocultar divs vacíos */
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
    
    /* ✅ AÑADIDO: Ocultar elementos problemáticos */
    div[data-testid="empty-container"] {
        display: none !important;
    }
    
    .empty-div {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

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

def mostrar_formulario_edicion(fila, titulo, on_save, on_delete, id_col, 
                             campos_select, campos_textarea, campos_file, campos_readonly, 
                             campos_dinamicos, campos_password, campos_obligatorios, 
                             campos_help, reactive_fields):
    """Formulario de edición avanzado con todos los campos disponibles."""
    
    st.markdown('<div class="ficha-container">', unsafe_allow_html=True)
    st.markdown(f"### ✏️ Editar {titulo}")
    
    # Mostrar información básica del registro
    if fila.get('nombre'):
        st.caption(f"Editando: {fila.get('nombre')}")
    elif fila.get('nombre_completo'):
        st.caption(f"Editando: {fila.get('nombre_completo')}")
    else:
        st.caption(f"ID: {fila.get(id_col)}")
    
    # Determinar campos a mostrar
    if campos_dinamicos:
        try:
            # ✅ CORREGIDO: Manejo seguro para evitar "Series ambiguous"
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
        campos_a_mostrar = [col for col in fila.keys() if col != id_col and col not in campos_readonly]

    # Filtrar campos que no deben mostrarse
    campos_a_mostrar = [campo for campo in campos_a_mostrar if campo not in ['created_at', 'updated_at']]

    with st.form(f"form_editar_{fila[id_col]}", clear_on_submit=False):
        datos_editados = {}
        
        # Organizar en secciones si hay muchos campos
        if len(campos_a_mostrar) > 8:
            st.markdown("#### 📝 Información básica")
            col1, col2 = st.columns(2)
            columnas = [col1, col2]
        elif len(campos_a_mostrar) > 4:
            col1, col2 = st.columns(2)
            columnas = [col1, col2]
        else:
            columnas = [st.container()]
        
        for i, campo in enumerate(campos_a_mostrar):
            if campo == id_col:
                continue
                
            valor_actual = fila.get(campo, "")
            if pd.isna(valor_actual):
                valor_actual = ""

            # Determinar en qué columna mostrar el campo
            col_actual = columnas[i % len(columnas)] if len(columnas) > 1 else columnas[0]
            
            # Crear contenedor dinámico para campos reactivos
            campo_container = st.container()
            
            with col_actual:
                with campo_container:
                    # Verificar si el campo debe estar visible según reactive_fields
                    campo_visible = True
                    if reactive_fields:
                        for trigger_field, dependent_fields in reactive_fields.items():
                            if campo in dependent_fields:
                                trigger_value = fila.get(trigger_field)
                                # Lógica simple: mostrar campo dependiente solo si trigger no está vacío
                                campo_visible = bool(trigger_value and str(trigger_value).strip())
                    
                    if campo_visible:
                        valor_editado = crear_campo_formulario(
                            campo, valor_actual, campos_select, campos_textarea, campos_file,
                            campos_readonly, [], campos_help, f"edit_{fila[id_col]}",
                            es_obligatorio=(campo in campos_obligatorios)
                        )
                        
                        if valor_editado is not None:
                            datos_editados[campo] = valor_editado

        # Información adicional
        if campos_readonly:
            with st.expander("ℹ️ Información adicional", expanded=False):
                for campo in campos_readonly:
                    if campo in fila:
                        valor = fila[campo]
                        if pd.notna(valor):
                            if 'fecha' in campo.lower() or 'created' in campo.lower() or 'updated' in campo.lower():
                                try:
                                    fecha = pd.to_datetime(valor)
                                    valor_formateado = fecha.strftime("%d/%m/%Y %H:%M")
                                except:
                                    valor_formateado = str(valor)
                            else:
                                valor_formateado = str(valor)
                            
                            st.text(f"{campo.replace('_', ' ').title()}: {valor_formateado}")

        st.divider()

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
                btn_eliminar = st.form_submit_button(
                    "🗑️ Eliminar", 
                    use_container_width=True,
                    help="Eliminar este registro permanentemente"
                )
        else:
            btn_guardar = st.form_submit_button(
                "💾 Guardar Cambios", 
                type="primary", 
                use_container_width=True
            )
            btn_eliminar = False

        # Procesar acciones
        if btn_guardar:
            # Validar campos obligatorios
            campos_faltantes = validar_campos_obligatorios(datos_editados, campos_obligatorios)
            
            if campos_faltantes:
                st.error(f"⚠️ Faltan campos obligatorios: {', '.join(campos_faltantes)}")
            else:
                try:
                    on_save(fila[id_col], datos_editados)
                    st.success("✅ Cambios guardados correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar: {e}")
        
        # ✅ CORREGIDO: Implementación completa de eliminación
        if btn_eliminar and on_delete:
            confirmar_key = f"confirmar_eliminar_{fila[id_col]}"
            
            if not st.session_state.get(confirmar_key, False):
                st.session_state[confirmar_key] = True
                st.warning("⚠️ ¿Estás seguro? Haz clic en Eliminar otra vez para confirmar.")
                st.rerun()
            else:
                try:
                    on_delete(fila[id_col])
                    st.session_state[confirmar_key] = False
                    st.success("✅ Registro eliminado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al eliminar: {e}")
                    st.session_state[confirmar_key] = False

    st.markdown('</div>', unsafe_allow_html=True)


def mostrar_formulario_creacion(titulo, on_create, campos_dinamicos, campos_select, campos_textarea, 
                              campos_file, campos_password, campos_help, campos_obligatorios, reactive_fields):
    """Formulario de creación avanzado con campos específicos."""
    
    st.markdown('<div class="ficha-container">', unsafe_allow_html=True)
    st.markdown(f"### ➕ Crear Nuevo {titulo}")
    st.caption("Completa los campos para crear un nuevo registro.")
    
    # Obtener campos para creación
    if campos_dinamicos:
        try:
            # ✅ CORREGIDO: Manejo seguro para creación
            campos_crear = campos_dinamicos({})  # Pasar dict vacío para creación
        except Exception as e:
            st.error(f"❌ Error al obtener campos de creación: {e}")
            # Fallback: usar todos los campos disponibles
            campos_crear = list(set(list(campos_select.keys()) + list(campos_textarea.keys()) + 
                                  list(campos_file.keys()) + campos_password))
    else:
        # Si no hay función dinámica, usar todos los campos disponibles
        campos_crear = list(set(list(campos_select.keys()) + list(campos_textarea.keys()) + 
                              list(campos_file.keys()) + campos_password))
    
    # Quitar campos que no deben aparecer en creación
    campos_crear = [c for c in campos_crear if c not in ['id', 'created_at', 'updated_at']]
    
    if not campos_crear:
        st.warning("⚠️ No se han definido campos para la creación.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    with st.form("form_crear", clear_on_submit=True):
        datos_nuevos = {}
        
        # Organizar en columnas
        if len(campos_crear) > 6:
            st.markdown("#### 📝 Información del nuevo registro")
            col1, col2 = st.columns(2)
            columnas = [col1, col2]
        elif len(campos_crear) > 3:
            col1, col2 = st.columns(2)
            columnas = [col1, col2]
        else:
            columnas = [st.container()]
        
        # Crear campos reactivos con contenedores
        campo_containers = {}
        for campo in campos_crear:
            campo_containers[campo] = st.container()
        
        for i, campo in enumerate(campos_crear):
            col_actual = columnas[i % len(columnas)] if len(columnas) > 1 else columnas[0]
            
            with col_actual:
                with campo_containers[campo]:
                    valor = crear_campo_formulario(
                        campo, "", campos_select, campos_textarea, campos_file,
                        [], campos_password, campos_help, "create",
                        es_obligatorio=(campo in campos_obligatorios)
                    )
                    
                    if valor is not None and str(valor).strip() != "":
                        datos_nuevos[campo] = valor
        
        # Información sobre campos obligatorios
        if campos_obligatorios:
            st.info(f"📋 Campos obligatorios: {', '.join([c.replace('_', ' ').title() for c in campos_obligatorios])}")

        btn_crear = st.form_submit_button("➕ Crear", type="primary", use_container_width=True)
        
        if btn_crear:
            # Validar campos obligatorios
            campos_faltantes = validar_campos_obligatorios(datos_nuevos, campos_obligatorios)
            
            if campos_faltantes:
                st.error(f"⚠️ Faltan campos obligatorios: {', '.join(campos_faltantes)}")
            else:
                try:
                    on_create(datos_nuevos)
                    st.success("✅ Registro creado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al crear: {e}")

    st.markdown('</div>', unsafe_allow_html=True)


def crear_campo_formulario(campo, valor_actual, campos_select, campos_textarea, campos_file,
                         campos_readonly, campos_password, campos_help, prefix, es_obligatorio=False):
    """Crea un campo de formulario avanzado según el tipo."""
    
    label = campo.replace('_', ' ').title()
    help_text = campos_help.get(campo, "")
    
    # Añadir asterisco si es obligatorio
    if es_obligatorio:
        label = f"{label} *"
        # Aplicar estilo CSS para campos obligatorios
        st.markdown(f'<div class="campo-obligatorio">', unsafe_allow_html=True)
    
    resultado = None
    
    try:
        # Campo readonly
        if campo in campos_readonly:
            resultado = st.text_input(
                label, 
                value=str(valor_actual), 
                disabled=True, 
                help=help_text, 
                key=f"{prefix}_{campo}"
            )
            return valor_actual
        
        # Campo select
        if campo in campos_select:
            opciones = campos_select[campo]
            if not isinstance(opciones, list):
                opciones = list(opciones)
            
            try:
                # Buscar el índice del valor actual
                if valor_actual in opciones:
                    index = opciones.index(valor_actual)
                elif str(valor_actual) in [str(op) for op in opciones]:
                    # Buscar por string conversion
                    index = [str(op) for op in opciones].index(str(valor_actual))
                else:
                    index = 0
            except (ValueError, TypeError):
                index = 0
            
            resultado = st.selectbox(
                label, 
                opciones, 
                index=index, 
                help=help_text, 
                key=f"{prefix}_{campo}"
            )
        
        # Campo textarea
        elif campo in campos_textarea:
            config = campos_textarea[campo]
            resultado = st.text_area(
                config.get("label", label), 
                value=str(valor_actual) if valor_actual else "", 
                height=config.get("height", 100),
                help=help_text,
                key=f"{prefix}_{campo}",
                max_chars=config.get("max_chars", None)
            )
        
        # Campo file
        elif campo in campos_file:
            config = campos_file[campo]
            resultado = st.file_uploader(
                config.get("label", label),
                type=config.get("type", None),
                help=help_text,
                key=f"{prefix}_{campo}",
                accept_multiple_files=config.get("multiple", False)
            )
        
        # Campo password
        elif campo in campos_password:
            resultado = st.text_input(
                label, 
                type="password", 
                help=help_text, 
                key=f"{prefix}_{campo}",
                placeholder="Introduce la contraseña..."
            )
        
        # Campo fecha
        elif 'fecha' in campo.lower() and valor_actual:
            try:
                if isinstance(valor_actual, str) and valor_actual.strip():
                    fecha_val = pd.to_datetime(valor_actual).date()
                elif hasattr(valor_actual, 'date'):
                    fecha_val = valor_actual.date()
                elif hasattr(valor_actual, 'date'):
                    fecha_val = valor_actual
                else:
                    fecha_val = None
                    
                if fecha_val:
                    resultado = st.date_input(
                        label, 
                        value=fecha_val, 
                        help=help_text, 
                        key=f"{prefix}_{campo}"
                    )
                else:
                    resultado = st.date_input(
                        label, 
                        value=None, 
                        help=help_text, 
                        key=f"{prefix}_{campo}"
                    )
            except:
                # Si falla el parsing de fecha, usar input de texto
                resultado = st.text_input(
                    label, 
                    value=str(valor_actual) if valor_actual else "", 
                    help=help_text, 
                    key=f"{prefix}_{campo}",
                    placeholder="dd/mm/yyyy"
                )
        
        # Campo booleano
        elif isinstance(valor_actual, bool):
            resultado = st.checkbox(
                label, 
                value=valor_actual, 
                help=help_text, 
                key=f"{prefix}_{campo}"
            )
        
        # Campo numérico
        elif isinstance(valor_actual, (int, float)) and not isinstance(valor_actual, bool):
            if isinstance(valor_actual, int):
                resultado = st.number_input(
                    label, 
                    value=int(valor_actual), 
                    help=help_text, 
                    key=f"{prefix}_{campo}",
                    step=1
                )
            else:
                resultado = st.number_input(
                    label, 
                    value=float(valor_actual), 
                    help=help_text, 
                    key=f"{prefix}_{campo}",
                    step=0.01,
                    format="%.2f"
                )
        
        # Campo email
        elif 'email' in campo.lower():
            resultado = st.text_input(
                label, 
                value=str(valor_actual) if valor_actual else "", 
                help=help_text, 
                key=f"{prefix}_{campo}",
                placeholder="usuario@ejemplo.com"
            )
        
        # Campo teléfono
        elif 'telefono' in campo.lower() or 'phone' in campo.lower():
            resultado = st.text_input(
                label, 
                value=str(valor_actual) if valor_actual else "", 
                help=help_text, 
                key=f"{prefix}_{campo}",
                placeholder="123456789"
            )
        
        # Campo URL
        elif 'url' in campo.lower() or 'web' in campo.lower():
            resultado = st.text_input(
                label, 
                value=str(valor_actual) if valor_actual else "", 
                help=help_text, 
                key=f"{prefix}_{campo}",
                placeholder="https://ejemplo.com"
            )
        
        # Campo texto por defecto
        else:
            resultado = st.text_input(
                label, 
                value=str(valor_actual) if valor_actual else "", 
                help=help_text, 
                key=f"{prefix}_{campo}"
            )
    
    except Exception as e:
        st.error(f"❌ Error al crear campo {campo}: {e}")
        # Fallback a input de texto simple
        resultado = st.text_input(
            label, 
            value=str(valor_actual) if valor_actual else "", 
            key=f"{prefix}_{campo}_fallback"
        )
    
    finally:
        if es_obligatorio:
            st.markdown('</div>', unsafe_allow_html=True)
    
    return resultado


def validar_campos_obligatorios(datos, campos_obligatorios):
    """Valida que todos los campos obligatorios tengan valor."""
    campos_faltantes = []
    
    for campo in campos_obligatorios:
        valor = datos.get(campo)
        if valor is None or valor == "" or (isinstance(valor, str) and not valor.strip()):
            campos_faltantes.append(campo.replace('_', ' ').title())
    
    return campos_faltantes
