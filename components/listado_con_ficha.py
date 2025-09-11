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
    on_delete=None,
    campos_select=None,
    campos_textarea=None,
    campos_file=None,
    campos_readonly=None,
    campos_dinamicos=None,
    campos_password=None,
    allow_creation=True,
    campos_help=None,
    reactive_fields=None
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
    campos_select: dict {columna: [opciones]} para selects
    campos_textarea: dict {columna: {"label": str}} para áreas de texto
    campos_file: dict {columna: {"label": str, "type": [extensiones]}} para subida de archivos
    campos_readonly: lista de columnas que no se pueden editar
    campos_dinamicos: función que recibe datos y devuelve lista de campos visibles
    campos_password: lista de campos que son contraseñas (solo para creación)
    allow_creation: bool para mostrar/ocultar formulario de creación
    campos_help: dict {columna: "texto de ayuda"} para mostrar ayuda contextual
    reactive_fields: dict {campo_trigger: [campos_dependientes]} para campos reactivos
    """
    campos_select = campos_select or {}
    campos_textarea = campos_textarea or {}
    campos_file = campos_file or {}
    campos_readonly = campos_readonly or []
    campos_password = campos_password or []
    campos_help = campos_help or {}
    reactive_fields = reactive_fields or {}

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
    
    .form-section {
        margin-bottom: 1.5rem;
        padding: 1rem;
        background-color: #ffffff;
        border-radius: 8px;
        border: 1px solid #e0e4e7;
    }
    
    .metricas-container {
        display: flex;
        gap: 1rem;
        margin-bottom: 1rem;
    }
    
    .metrica-card {
        flex: 1;
        padding: 1rem;
        background: white;
        border-radius: 8px;
        border: 1px solid #e0e4e7;
        text-align: center;
    }
    
    .metrica-valor {
        font-size: 1.5rem;
        font-weight: bold;
        color: #4285f4;
    }
    
    .metrica-label {
        font-size: 0.9rem;
        color: #666;
    }
    
    /* Animaciones para campos reactivos */
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(-10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .campo-aparece {
        animation: slideIn 0.3s ease-out;
    }
    
    /* Mejores botones */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
        border: none;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    .btn-primary {
        background: linear-gradient(45deg, #4285f4, #34a853) !important;
        color: white !important;
    }
    
    .btn-secondary {
        background: linear-gradient(45deg, #6c757d, #5a6268) !important;
        color: white !important;
    }
    
    .btn-danger {
        background: linear-gradient(45deg, #dc3545, #c82333) !important;
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ===============================
    # TABLA DE LISTADO
    # ===============================
    if not df.empty:
        st.markdown(f"### 📋 {titulo}s registrados ({len(df)} total)")
        
        # Configuración de la tabla
        gb = GridOptionsBuilder.from_dataframe(df[columnas_visibles])
        gb.configure_default_column(filter=True, sortable=True, resizable=True)
        gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)
        gb.configure_selection('single', use_checkbox=False)
        gb.configure_grid_options(rowSelection='single')
        grid_options = gb.build()

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
                
                # ✅ CORRECCIÓN: Organizar campos en secciones si hay muchos
                if len(campos_a_mostrar) > 8:
                    st.markdown("#### 📝 Información básica")
                    col1, col2 = st.columns(2)
                    cols = [col1, col2]
                    col_idx = 0
                else:
                    # ✅ CORRECCIÓN: Usar container() en lugar de st directamente
                    cols = [st.container()]
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

                    # ✅ CORRECCIÓN: Usar context manager solo cuando sea válido
                    if len(cols) > 1:
                        with current_col:
                            _render_form_field(col, valor_actual, datos_editados, campos_select, campos_textarea, 
                                             campos_file, campos_readonly, campos_password, campos_help)
                    else:
                        # Para una sola columna, renderizar directamente sin context manager
                        _render_form_field(col, valor_actual, datos_editados, campos_select, campos_textarea, 
                                         campos_file, campos_readonly, campos_password, campos_help)

                # Botones de acción con estilos mejorados
                st.markdown("#### 🔧 Acciones")
                col1, col2, col3 = st.columns([1, 1, 2])
                
                with col1:
                    if st.form_submit_button("💾 Guardar", use_container_width=True, type="primary"):
                        # Filtrar campos que no han cambiado o están vacíos innecesariamente
                        datos_filtrados = {}
                        for key, value in datos_editados.items():
                            if key in campos_file and value is None:
                                continue  # No actualizar archivos si no se subió nada nuevo
                            datos_filtrados[key] = value
                        
                        if datos_filtrados:
                            on_save(fila[id_col], datos_filtrados)
                        else:
                            st.warning("⚠️ No hay cambios para guardar.")
                
                with col2:
                    if on_delete and st.form_submit_button("🗑️ Eliminar", use_container_width=True, type="secondary"):
                        st.session_state[f'confirm_delete_{fila[id_col]}'] = True
                        st.rerun()

            # Confirmación de eliminación
            if on_delete and st.session_state.get(f'confirm_delete_{fila[id_col]}', False):
                st.error("⚠️ ¿Estás seguro de que quieres eliminar este registro?")
                st.caption("Esta acción no se puede deshacer.")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Sí, eliminar", key=f"confirm_yes_{fila[id_col]}", type="primary"):
                        try:
                            on_delete(fila[id_col])
                            del st.session_state[f'confirm_delete_{fila[id_col]}']
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al eliminar: {e}")
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

            # ✅ CORRECCIÓN: Organizar campos en columnas si son muchos
            if len(campos_crear) > 6:
                st.markdown("#### 📝 Información del nuevo registro")
                col1, col2 = st.columns(2)
                cols = [col1, col2]
                col_idx = 0
            else:
                # ✅ CORRECCIÓN: Usar container() en lugar de st directamente
                cols = [st.container()]
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

                # ✅ CORRECCIÓN: Usar context manager solo cuando sea válido
                if len(cols) > 1:
                    with current_col:
                        _render_create_field(col, datos_nuevos, campos_select, campos_textarea, 
                                           campos_file, campos_password, campos_help)
                else:
                    # Para una sola columna, renderizar directamente sin context manager
                    _render_create_field(col, datos_nuevos, campos_select, campos_textarea, 
                                       campos_file, campos_password, campos_help)

            # Botones de creación
            st.markdown("#### 🔧 Crear registro")
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.form_submit_button(f"✅ Crear {titulo}", use_container_width=True, type="primary"):
                    # Filtrar campos vacíos excepto los obligatorios
                    datos_filtrados = {k: v for k, v in datos_nuevos.items() if v or k in campos_password}
                    try:
                        on_create(datos_filtrados)
                    except Exception as e:
                        st.error(f"❌ Error al crear {titulo.lower()}: {e}")
        
        st.markdown('</div>', unsafe_allow_html=True)


def _render_form_field(col, valor_actual, datos_editados, campos_select, campos_textarea, 
                      campos_file, campos_readonly, campos_password, campos_help):
    """Función auxiliar para renderizar campos del formulario de edición."""
    label = col.replace('_', ' ').title()
    help_text = campos_help.get(col, "")
    
    # Campo readonly
    if col in campos_readonly:
        st.text_input(
            label, 
            value=str(valor_actual), 
            disabled=True,
            key=f"readonly_{col}",
            help=help_text
        )
        return

    # Campo select con mejoras visuales
    elif col in campos_select:
        opciones = campos_select[col]
        try:
            idx = opciones.index(valor_actual) if valor_actual in opciones else 0
        except (ValueError, TypeError):
            idx = 0
        
        datos_editados[col] = st.selectbox(
            label, 
            options=opciones, 
            index=idx,
            key=f"select_{col}",
            help=help_text
        )

    # Campo textarea
    elif col in campos_textarea:
        datos_editados[col] = st.text_area(
            campos_textarea[col].get("label", label),
            value=str(valor_actual),
            height=campos_textarea[col].get("height", 100),
            key=f"textarea_{col}",
            help=help_text
        )

    # Campo file con preview
    elif col in campos_file:
        st.markdown(f"**{campos_file[col].get('label', label)}**")
        if valor_actual:
            st.caption(f"📎 Archivo actual: {valor_actual}")
        datos_editados[col] = st.file_uploader(
            "Seleccionar nuevo archivo",
            type=campos_file[col].get("type", None),
            key=f"file_{col}",
            help=help_text
        )

    # Campos específicos por tipo con mejoras
    else:
        if 'fecha' in col.lower():
            try:
                if valor_actual:
                    valor_fecha = pd.to_datetime(valor_actual).date()
                else:
                    valor_fecha = None
            except Exception:
                valor_fecha = None
            datos_editados[col] = st.date_input(
                label, 
                value=valor_fecha,
                key=f"date_{col}",
                help=help_text
            )
        elif col.lower() in ['precio', 'importe', 'valor', 'cantidad', 'numero', 'num', 'horas']:
            try:
                valor_num = float(valor_actual) if valor_actual else 0.0
            except (ValueError, TypeError):
                valor_num = 0.0
            datos_editados[col] = st.number_input(
                label, 
                value=valor_num,
                min_value=0.0, 
                step=0.01 if 'precio' in col.lower() or 'importe' in col.lower() else 1.0,
                key=f"number_{col}",
                help=help_text
            )
        elif 'email' in col.lower():
            datos_editados[col] = st.text_input(
                label, 
                value=str(valor_actual),
                placeholder="usuario@ejemplo.com",
                key=f"email_{col}",
                help=help_text
            )
        elif 'telefono' in col.lower() or 'movil' in col.lower():
            datos_editados[col] = st.text_input(
                label, 
                value=str(valor_actual),
                placeholder="600123456",
                key=f"phone_{col}",
                help=help_text
            )
        elif col in campos_password:
            # Los campos de contraseña no se muestran en edición
            pass
        else:
            datos_editados[col] = st.text_input(
                label, 
                value=str(valor_actual),
                key=f"text_{col}",
                help=help_text
            )
        
        # Mostrar texto de ayuda si existe
        if help_text:
            st.caption(f"💡 {help_text}")


def _render_create_field(col, datos_nuevos, campos_select, campos_textarea, 
                        campos_file, campos_password, campos_help):
    """Función auxiliar para renderizar campos del formulario de creación."""
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
    else:
        if 'fecha' in col.lower():
            datos_nuevos[col] = st.date_input(
                label,
                key=f"create_date_{col}",
                help=help_text
            )
        elif col.lower() in ['precio', 'importe', 'valor', 'cantidad', 'numero', 'num', 'horas']:
            datos_nuevos[col] = st.number_input(
                label,
                min_value=0.0,
                step=0.01 if 'precio' in col.lower() or 'importe' in col.lower() else 1.0,
                key=f"create_number_{col}",
                help=help_text
            )
        elif 'email' in col.lower():
            datos_nuevos[col] = st.text_input(
                label,
                placeholder="usuario@ejemplo.com",
                key=f"create_email_{col}",
                help=help_text
            )
        elif 'telefono' in col.lower() or 'movil' in col.lower():
            datos_nuevos[col] = st.text_input(
                label,
                placeholder="600123456",
                key=f"create_phone_{col}",
                help=help_text
            )
        elif 'cif' in col.lower() or 'dni' in col.lower():
            datos_nuevos[col] = st.text_input(
                label,
                placeholder="12345678A" if 'dni' in col.lower() else "A12345678",
                key=f"create_doc_{col}",
                help=help_text
            )
        else:
            datos_nuevos[col] = st.text_input(
                label,
                key=f"create_input_{col}",
                help=help_text
            )
        
        # Mostrar texto de ayuda
        if help_text:
            st.caption(f"💡 {help_text}")


def _handle_reactive_change(field, reactive_config):
    """Función auxiliar para manejar cambios en campos reactivos."""
    # Esta función se puede expandir para lógica más compleja
    pass
