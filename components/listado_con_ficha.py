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
                        # Aquí iría la función de eliminación si estuviera implementada
                        st.success("✅ Funcionalidad de eliminación pendiente de implementar.")
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
                        cfg = campos_textarea[col        # FICHA DE EDICIÓN CON MEJORAS VISUALES
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
                        # Crear contenedor dinámico para campos reactivos
                        campo_container = st.container()
                        
                        with campo_container:
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
                                continue

                            # Campo select con mejoras visuales
                            elif col in campos_select:
                                opciones = campos_select[col]
                                try:
                                    idx = opciones.index(valor_actual) if valor_actual in opciones else 0
                                except (ValueError, TypeError):
                                    idx = 0
                                
                                # Campo select reactivo
                                datos_editados[col] = st.selectbox(
                                    label, 
                                    options=opciones, 
                                    index=idx,
                                    key=f"select_{col}",
                                    help=help_text,
                                    on_change=lambda: _handle_reactive_change(col, reactive_fields) if col in reactive_fields else None
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
                                st.markdown(fimport streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

def listado_con_ficha(
    df,
    columnas_visibles,
    titulo,
    on_save,
    id_col="id",
    on_create=None,
    campos_select=None,
    campos_textarea=None,
    campos_file=None,
    campos_readonly=None,
    campos_dinamicos=None,
    campos_password=None,
    allow_creation=True
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
    """
    campos_select = campos_select or {}
    campos_textarea = campos_textarea or {}
    campos_file = campos_file or {}
    campos_readonly = campos_readonly or []
    campos_password = campos_password or []

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
        # FICHA DE EDICIÓN
        # ===============================
        if grid_response["selected_rows"]:
            fila = grid_response["selected_rows"][0]
            st.divider()
            st.subheader(f"✏️ Editar {titulo}")
            st.caption(f"Modificando: {fila.get('nombre', fila.get('nombre_completo', fila[columnas_visibles[0]]))}")

            # Determinar campos visibles dinámicamente
            campos_a_mostrar = columnas_visibles.copy()
            if campos_dinamicos:
                try:
                    campos_a_mostrar = campos_dinamicos(fila)
                    # Asegurar que no se pierda el ID
                    if id_col not in campos_a_mostrar:
                        campos_a_mostrar.insert(0, id_col)
                except Exception as e:
                    st.error(f"❌ Error en campos dinámicos: {e}")

            with st.form("form_editar", clear_on_submit=False):
                datos_editados = {}
                
                for col in campos_a_mostrar:
                    if col == id_col:
                        continue

                    valor_actual = fila.get(col, "")
                    if valor_actual is None:
                        valor_actual = ""

                    # Campo readonly
                    if col in campos_readonly:
                        st.text_input(
                            col.replace('_', ' ').title(), 
                            value=str(valor_actual), 
                            disabled=True,
                            key=f"readonly_{col}"
                        )
                        continue

                    # Campo select
                    elif col in campos_select:
                        opciones = campos_select[col]
                        try:
                            idx = opciones.index(valor_actual) if valor_actual in opciones else 0
                        except (ValueError, TypeError):
                            idx = 0
                        datos_editados[col] = st.selectbox(
                            col.replace('_', ' ').title(), 
                            options=opciones, 
                            index=idx,
                            key=f"select_{col}"
                        )

                    # Campo textarea
                    elif col in campos_textarea:
                        datos_editados[col] = st.text_area(
                            campos_textarea[col].get("label", col.replace('_', ' ').title()),
                            value=str(valor_actual),
                            height=100,
                            key=f"textarea_{col}"
                        )

                    # Campo file
                    elif col in campos_file:
                        st.markdown(f"**{campos_file[col].get('label', col.replace('_', ' ').title())}**")
                        if valor_actual:
                            st.caption(f"Archivo actual: {valor_actual}")
                        datos_editados[col] = st.file_uploader(
                            "Seleccionar nuevo archivo",
                            type=campos_file[col].get("type", None),
                            key=f"file_{col}"
                        )

                    # Campo de texto normal
                    else:
                        datos_editados[col] = st.text_input(
                            col.replace('_', ' ').title(), 
                            value=str(valor_actual),
                            key=f"input_{col}"
                        )

                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.form_submit_button("💾 Guardar cambios", use_container_width=True):
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

    else:
        st.info(f"ℹ️ No hay {titulo.lower()}s registrados en el sistema.")

    # ===============================
    # FORMULARIO DE CREACIÓN
    # ===============================
    if on_create and allow_creation:
        st.divider()
        st.subheader(f"➕ Crear nuevo {titulo}")
        
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

            for col in campos_crear:
                if col == id_col:
                    continue

                # Campo select
                if col in campos_select:
                    datos_nuevos[col] = st.selectbox(
                        col.replace('_', ' ').title(),
                        options=campos_select[col],
                        key=f"create_select_{col}"
                    )

                # Campo textarea
                elif col in campos_textarea:
                    datos_nuevos[col] = st.text_area(
                        campos_textarea[col].get("label", col.replace('_', ' ').title()),
                        height=100,
                        key=f"create_textarea_{col}"
                    )

                # Campo file
                elif col in campos_file:
                    datos_nuevos[col] = st.file_uploader(
                        campos_file[col].get("label", col.replace('_', ' ').title()),
                        type=campos_file[col].get("type", None),
                        key=f"create_file_{col}"
                    )

                # Campo password
                elif col in campos_password:
                    datos_nuevos[col] = st.text_input(
                        col.replace('_', ' ').title(),
                        type="password",
                        key=f"create_password_{col}",
                        help="Se generará automáticamente si se deja vacío"
                    )

                # Campo de texto normal
                else:
                    datos_nuevos[col] = st.text_input(
                        col.replace('_', ' ').title(),
                        key=f"create_input_{col}"
                    )

            col1, col2 = st.columns([1, 3])
            with col1:
                if st.form_submit_button(f"✅ Crear {titulo}", use_container_width=True):
                    # Filtrar campos vacíos excepto los obligatorios
                    datos_filtrados = {k: v for k, v in datos_nuevos.items() if v or k in campos_password}
                    on_create(datos_filtrados)
                
