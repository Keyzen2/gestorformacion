"""
Componente reutilizable para mostrar un listado con ficha editable.
Versión mejorada con corrección de errores y nuevas funcionalidades.
"""

import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

def listado_con_ficha(
    df,
    columnas_visibles,
    titulo,
    on_save,
    id_col="id",
    on_create=None,
    on_delete=None,  # Nuevo parámetro para función de eliminación
    campos_select=None,
    campos_textarea=None,
    campos_file=None,
    campos_readonly=None,
    campos_dinamicos=None,
    campos_password=None,
    allow_creation=True,
    campos_help=None,
    reactive_fields=None,
    search_columns=None,  # Nuevo parámetro para búsqueda
    campos_obligatorios=None  # Nuevo parámetro para campos obligatorios
):
    """
    Muestra un listado interactivo y, al seleccionar un registro, abre una ficha editable.
    También permite crear nuevos registros si se especifica on_create.

    Parámetros:
    -----------
    df: DataFrame con los datos (incluyendo columna id_col)
    columnas_visibles: columnas que se muestran en la tabla
    titulo: título de la ficha
    on_save: función que recibe (id, datos_editados)
    id_col: columna identificadora
    on_create: función que recibe (datos_nuevos) para crear registros
    on_delete: función que recibe (id) para eliminar registros
    campos_select: dict {columna: [opciones]} para selects
    campos_textarea: dict {columna: {"label": str}} para áreas de texto
    campos_file: dict {columna: {"label": str, "type": [extensiones]}} para subida de archivos
    campos_readonly: lista de columnas que no se pueden editar
    campos_dinamicos: función que recibe datos y devuelve lista de campos visibles
    campos_password: lista de campos que son contraseñas (solo para creación)
    allow_creation: bool para mostrar/ocultar formulario de creación
    campos_help: dict {columna: "texto de ayuda"} para mostrar ayuda contextual
    reactive_fields: dict {campo_trigger: [campos_dependientes]} para campos reactivos
    search_columns: lista de columnas para búsqueda rápida
    campos_obligatorios: lista de campos que son obligatorios
    """
    # Inicializar valores por defecto
    campos_select = campos_select or {}
    campos_textarea = campos_textarea or {}
    campos_file = campos_file or {}
    campos_readonly = campos_readonly or []
    campos_password = campos_password or []
    campos_help = campos_help or {}
    reactive_fields = reactive_fields or {}
    search_columns = search_columns or []
    campos_obligatorios = campos_obligatorios or []

    # CSS mejorado para mejor visualización
    st.markdown("""
    <style>
    /* Estilos para el componente listado_con_ficha */
    .ficha-container {
        border: 2px solid #e1e5e9;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
        transition: all 0.3s ease;
    }
    
    .ficha-container:hover {
        border-color: #4285f4;
        box-shadow: 0 6px 12px rgba(66, 133, 244, 0.15);
    }
    
    .campo-dinamico {
        transition: all 0.3s ease-in-out;
        opacity: 1;
    }
    
    .campo-oculto {
        opacity: 0.3;
        pointer-events: none;
        max-height: 0;
        overflow: hidden;
        margin: 0;
        padding: 0;
    }
    
    .campo-obligatorio label {
        font-weight: 600;
    }
    
    .campo-obligatorio label:after {
        content: " *";
        color: #ff4444;
    }
    
    .help-text {
        font-size: 0.85em;
        color: #666;
        font-style: italic;
        margin-top: 0.25rem;
    }
    </style>
    """, unsafe_allow_html=True)

    # Añadir buscador rápido si se especifican columnas de búsqueda
    if search_columns and not df.empty:
        query = st.text_input("🔍 Buscar", placeholder=f"Buscar por {', '.join(search_columns)}")
        if query:
            # Filtrar dataframe por texto de búsqueda en las columnas especificadas
            mask = False
            for col in search_columns:
                if col in df.columns:
                    # Convertir a string y buscar coincidencias ignorando mayúsculas/minúsculas
                    mask = mask | df[col].astype(str).str.lower().str.contains(query.lower(), na=False)
            
            # Aplicar filtro
            filtered_df = df[mask]
            if filtered_df.empty:
                st.info(f"No se encontraron resultados para '{query}'")
            else:
                df = filtered_df

    # ===============================
    # TABLA CON AGGRID MEJORADA
    # ===============================
    if not df.empty:
        # Preparar opciones de la tabla
        gb = GridOptionsBuilder.from_dataframe(df[columnas_visibles])
        gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=10)
        gb.configure_selection(selection_mode="single", use_checkbox=False)
        
        # Configurar estilos condicionales para mejorar la visualización
        for col in columnas_visibles:
            if col in df.columns:
                if df[col].dtype == bool:
                    # Colorear celdas booleanas
                    gb.configure_column(col, cellStyle={"styleConditions": [
                        {"condition": "params.value === true", "style": {"backgroundColor": "#e6f7e6", "color": "#1a841a"}},
                        {"condition": "params.value === false", "style": {"backgroundColor": "#f8d7da", "color": "#721c24"}}
                    ]})
                elif 'fecha' in col.lower() or 'date' in col.lower():
                    # Formatear fechas
                    gb.configure_column(col, type=["dateColumnFilter", "customDateTimeFormat"], custom_format_string="dd/MM/yyyy")
                elif 'activo' in col.lower() or 'active' in col.lower():
                    # Colorear estados activos
                    gb.configure_column(col, cellStyle={"styleConditions": [
                        {"condition": "params.value === true", "style": {"backgroundColor": "#e6f7e6", "color": "#1a841a"}},
                        {"condition": "params.value === false", "style": {"backgroundColor": "#f8d7da", "color": "#721c24"}}
                    ]})
        
        # Opciones adicionales
        gb.configure_default_column(
            resizable=True,
            filterable=True,
            sortable=True,
            editable=False
        )
        grid_options = gb.build()
        
        # Mostrar tabla mejorada
        grid_response = AgGrid(
            df[columnas_visibles],
            gridOptions=grid_options,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            theme="balham",
            allow_unsafe_jscode=True,
            height=400
        )

        # ===============================
        # FICHA DE EDICIÓN CON MEJORAS VISUALES
        # ===============================
        if grid_response["selected_rows"]:
            fila = grid_response["selected_rows"][0]
            
            # Contenedor con estilo mejorado
            st.markdown('<div class="ficha-container">', unsafe_allow_html=True)
            st.subheader(f"✏️ Editar {titulo}")
            st.caption(f"Modificando: {fila.get('nombre', fila.get('nombre_completo', fila[columnas_visibles[0]]))}")

            # Determinar campos visibles dinámicamente
            campos_a_mostrar = columnas_visibles.copy()
            if campos_dinamicos:
                try:
                    campos_a_mostrar = campos_dinamicos(fila)
                    if id_col not in campos_a_mostrar:
                        campos_a_mostrar.insert(0, id_col)
                except Exception as e:
                    st.error(f"❌ Error en campos dinámicos: {e}")

            with st.form("form_editar", clear_on_submit=False):
                datos_editados = {}
                
                # Organizar campos en secciones si hay muchos
                if len(campos_a_mostrar) > 8:
                    st.markdown("#### 📝 Información básica")
                    col1, col2 = st.columns(2)
                    cols = [col1, col2]
                    col_idx = 0
                else:
                    cols = [st]
                    col_idx = 0
                
                for i, col in enumerate(campos_a_mostrar):
                    if col == id_col:
                        continue

                    valor_actual = fila.get(col, "")
                    if valor_actual is None:
                        valor_actual = ""

                    # Determinar columna para organización visual
                    if len(cols) > 1:
                        current_col = cols[col_idx % 2]
                        col_idx += 1
                    else:
                        current_col = cols[0]

                    with current_col:
                        # Verificar si el campo es obligatorio para aplicar estilo
                        es_obligatorio = col in campos_obligatorios
                        campo_class = "campo-obligatorio" if es_obligatorio else ""
                        
                        # Verificar si es campo reactivo (se muestra/oculta según otros campos)
                        es_reactivo = False
                        for trigger_field, dependent_fields in reactive_fields.items():
                            if col in dependent_fields:
                                es_reactivo = True
                                campo_class += " campo-dinamico"
                                # Determinar si debe mostrarse u ocultarse según el valor del campo trigger
                                mostrar_campo = fila.get(trigger_field, False)
                                if not mostrar_campo:
                                    campo_class += " campo-oculto"
                        
                        # Aplicar clase CSS si es obligatorio o reactivo
                        if campo_class:
                            st.markdown(f'<div class="{campo_class}">', unsafe_allow_html=True)
                        
                        # Label formateado
                        label = col.replace('_', ' ').title()
                        help_text = campos_help.get(col, "")
                        
                        # Determinar tipo de campo y mostrarlo
                        if col in campos_readonly:
                            # Campo de solo lectura
                            st.text_input(
                                label,
                                value=str(valor_actual),
                                disabled=True,
                                key=f"readonly_{col}_{fila[id_col]}",
                                help=help_text
                            )
                        elif col in campos_select:
                            # Campo de selección
                            datos_editados[col] = st.selectbox(
                                label,
                                options=campos_select[col],
                                index=campos_select[col].index(valor_actual) if valor_actual in campos_select[col] else 0,
                                key=f"select_{col}_{fila[id_col]}",
                                help=help_text
                            )
                        elif col in campos_textarea:
                            # Campo de texto multilínea
                            cfg = campos_textarea[col]
                            datos_editados[col] = st.text_area(
                                cfg.get("label", label),
                                value=str(valor_actual),
                                height=cfg.get("height", 100),
                                key=f"textarea_{col}_{fila[id_col]}",
                                help=help_text
                            )
                        elif col in campos_file:
                            # Campo de archivo
                            cfg = campos_file[col]
                            
                            # Mostrar archivo actual si existe
                            if valor_actual:
                                st.caption(f"Archivo actual: {valor_actual}")
                            
                            datos_editados[col] = st.file_uploader(
                                cfg.get("label", label),
                                type=cfg.get("type", None),
                                key=f"file_{col}_{fila[id_col]}",
                                help=help_text
                            )
                        elif 'fecha' in col.lower() or 'date' in col.lower() or 'inicio' in col.lower() or 'fin' in col.lower():
                            # Campo de fecha
                            try:
                                # Intentar convertir a fecha si es string
                                if isinstance(valor_actual, str) and valor_actual:
                                    fecha_val = pd.to_datetime(valor_actual).date()
                                elif isinstance(valor_actual, pd.Timestamp):
                                    fecha_val = valor_actual.date()
                                else:
                                    fecha_val = None
                                
                                datos_editados[col] = st.date_input(
                                    label,
                                    value=fecha_val,
                                    key=f"date_{col}_{fila[id_col]}",
                                    help=help_text
                                )
                            except Exception:
                                # Si falla, mostrar como texto
                                datos_editados[col] = st.text_input(
                                    label,
                                    value=str(valor_actual),
                                    key=f"text_{col}_{fila[id_col]}",
                                    help=help_text
                                )
                        elif isinstance(valor_actual, bool) or col.endswith('_activo'):
                            # Campo booleano
                            datos_editados[col] = st.checkbox(
                                label,
                                value=bool(valor_actual),
                                key=f"check_{col}_{fila[id_col]}",
                                help=help_text
                            )
                        elif 'email' in col.lower():
                            # Campo de email
                            datos_editados[col] = st.text_input(
                                label,
                                value=str(valor_actual),
                                key=f"email_{col}_{fila[id_col]}",
                                help=help_text
                            )
                        elif 'telefono' in col.lower() or 'movil' in col.lower():
                            # Campo de teléfono
                            datos_editados[col] = st.text_input(
                                label,
                                value=str(valor_actual),
                                key=f"tel_{col}_{fila[id_col]}",
                                help=help_text
                            )
                        else:
                            # Campo de texto genérico
                            datos_editados[col] = st.text_input(
                                label,
                                value=str(valor_actual),
                                key=f"text_{col}_{fila[id_col]}",
                                help=help_text
                            )
                        
                        # Cerrar div de clase si aplicamos alguna
                        if campo_class:
                            st.markdown('</div>', unsafe_allow_html=True)
                
                # Botones de acción
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Guardar cambios", use_container_width=True):
                        try:
                            on_save(fila[id_col], datos_editados)
                        except Exception as e:
                            st.error(f"❌ Error al guardar: {e}")
                
                with col2:
                    if st.form_submit_button("🗑️ Eliminar", use_container_width=True, type="secondary"):
                        st.session_state[f'confirm_delete_{fila[id_col]}'] = True
                        st.rerun()

            # Confirmación de eliminación
            if st.session_state.get(f'confirm_delete_{fila[id_col]}', False):
                st.error("⚠️ ¿Estás seguro de que quieres eliminar este registro?")
                st.caption("Esta acción no se puede deshacer.")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Sí, eliminar", key=f"confirm_yes_{fila[id_col]}", type="primary"):
                        if on_delete:  # Usar la función de eliminación si se proporciona
                            try:
                                on_delete(fila[id_col])
                            except Exception as e:
                                st.error(f"❌ Error al eliminar: {e}")
                        else:
                            st.error("❌ Función de eliminación no configurada.")
                        
                        del st.session_state[f'confirm_delete_{fila[id_col]}']
                        st.rerun()
                with col2:
                    if st.button("❌ Cancelar", key=f"confirm_no_{fila[id_col]}"):
                        del st.session_state[f'confirm_delete_{fila[id_col]}']
                        st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.info(f"ℹ️ No hay {titulo.lower()}s registrados en el sistema.")

    # ===============================
    # FORMULARIO DE CREACIÓN MEJORADO
    # ===============================
    if on_create and allow_creation:
        st.divider()
        
        # Contenedor con estilo
        st.markdown('<div class="ficha-container">', unsafe_allow_html=True)
        st.subheader(f"➕ Crear nuevo {titulo}")
        st.caption("Completa los campos para crear un nuevo registro.")
        
        with st.form("form_crear", clear_on_submit=True):
            datos_nuevos = {}
            
            # Usar campos dinámicos para creación si está definido
            campos_crear = columnas_visibles.copy()
            if campos_dinamicos:
                try:
                    # Para creación, pasamos datos vacíos para determinar campos base
                    campos_crear = campos_dinamicos({})
                except Exception:
                    pass  # Usar columnas_visibles por defecto

            # Organizar campos en columnas si son muchos
            if len(campos_crear) > 6:
                st.markdown("#### 📝 Información del nuevo registro")
                col1, col2 = st.columns(2)
                cols = [col1, col2]
                col_idx = 0
            else:
                cols = [st]
                col_idx = 0

            for col in campos_crear:
                if col == id_col:
                    continue

                # Alternar entre columnas si hay más de 6 campos
                if len(cols) > 1:
                    current_col = cols[col_idx % 2]
                    col_idx += 1
                else:
                    current_col = cols[0]

                with current_col:
                    # Verificar si es campo obligatorio
                    es_obligatorio = col in campos_obligatorios
                    campo_class = "campo-obligatorio" if es_obligatorio else ""
                    
                    if campo_class:
                        st.markdown(f'<div class="{campo_class}">', unsafe_allow_html=True)
                        
                    label = col.replace('_', ' ').title()
                    help_text = campos_help.get(col, "")

                    # Campo select
                    if col in campos_select:
                        datos_nuevos[col] = st.selectbox(
                            label,
                            options=campos_select[col],
                            key=f"create_select_{col}",
                            help=help_text
                        )

                    # Campo textarea
                    elif col in campos_textarea:
                        cfg = campos_textarea[col]
                        datos_nuevos[col] = st.text_area(
                            cfg.get("label", label),
                            height=cfg.get("height", 100),
                            key=f"create_textarea_{col}",
                            help=help_text
                        )

                    # Campo file
                    elif col in campos_file:
                        cfg = campos_file[col]
                        datos_nuevos[col] = st.file_uploader(
                            cfg.get("label", label),
                            type=cfg.get("type", None),
                            key=f"create_file_{col}",
                            help=help_text
                        )

                    # Campo password
                    elif col in campos_password:
                        datos_nuevos[col] = st.text_input(
                            label,
                            type="password",
                            key=f"create_password_{col}",
                            help=help_text or "Se generará automáticamente si se deja vacío"
                        )

                    # Campos específicos por tipo
                    elif 'fecha' in col.lower() or 'date' in col.lower() or 'inicio' in col.lower() or 'fin' in col.lower():
                        datos_nuevos[col] = st.date_input(
                            label,
                            key=f"create_date_{col}",
                            help=help_text
                        )
                    elif col.endswith('_activo') or 'activo' in col.lower():
                        datos_nuevos[col] = st.checkbox(
                            label,
                            value=False,
                            key=f"create_check_{col}",
                            help=help_text
                        )
                    elif 'email' in col.lower():
                        datos_nuevos[col] = st.text_input(
                            label,
                            key=f"create_email_{col}",
                            placeholder="usuario@ejemplo.com",
                            help=help_text
                        )
                    elif 'telefono' in col.lower() or 'movil' in col.lower():
                        datos_nuevos[col] = st.text_input(
                            label,
                            key=f"create_tel_{col}",
                            placeholder="600123456",
                            help=help_text
                        )
                    else:
                        datos_nuevos[col] = st.text_input(
                            label,
                            key=f"create_text_{col}",
                            help=help_text
                        )
                        
                    # Cerrar div de clase si aplicamos alguna
                    if campo_class:
                        st.markdown('</div>', unsafe_allow_html=True)

            # Botón de creación
            if st.form_submit_button("✅ Crear", use_container_width=True):
                try:
                    # Verificar campos obligatorios
                    campos_vacios = [col for col in campos_obligatorios if col in datos_nuevos and not datos_nuevos[col]]
                    
                    if campos_vacios:
                        st.error(f"⚠️ Completa los campos obligatorios: {', '.join(campos_vacios)}")
                    else:
                        on_create(datos_nuevos)
                except Exception as e:
                    st.error(f"❌ Error al crear: {e}")
            
            st.markdown('</div>', unsafe_allow_html=True)

    return df  # Devolver el dataframe (posiblemente filtrado)
