import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from typing import Dict, List, Callable, Optional, Any

def listado_con_ficha(
    df: pd.DataFrame,
    columnas_visibles: List[str],
    titulo: str,
    on_save: Callable[[str, Dict[str, Any]], None],
    id_col: str = "id",
    on_create: Optional[Callable[[Dict[str, Any]], None]] = None,
    campos_select: Optional[Dict[str, List]] = None,
    campos_textarea: Optional[Dict[str, Dict[str, Any]]] = None,
    campos_file: Optional[Dict[str, Dict[str, Any]]] = None,
    campos_readonly: Optional[List[str]] = None,
    campos_dinamicos: Optional[Callable[[Dict[str, Any]], List[str]]] = None,
    campos_password: Optional[List[str]] = None,
    allow_creation: bool = True,
    campos_help: Optional[Dict[str, str]] = None,
    reactive_fields: Optional[Dict[str, List[str]]] = None
):
    """
    Componente optimizado para listados con ficha de edición.
    
    Versión mejorada que soluciona problemas de renderizado y performance.
    
    Parámetros:
    -----------
    df: DataFrame con los datos (debe incluir columna id_col)
    columnas_visibles: columnas que se muestran en la tabla
    titulo: título de la ficha
    on_save: función que recibe (id, datos_editados)
    id_col: columna identificadora (default: "id")
    on_create: función que recibe (datos_nuevos) para crear registros
    campos_select: dict {columna: [opciones]} para selectboxes
    campos_textarea: dict {columna: {"label": str, "height": int}} para áreas de texto
    campos_file: dict {columna: {"label": str, "type": [extensiones]}} para archivos
    campos_readonly: lista de columnas que no se pueden editar
    campos_dinamicos: función que recibe datos y devuelve lista de campos visibles
    campos_password: lista de campos que son contraseñas (solo para creación)
    allow_creation: bool para mostrar/ocultar formulario de creación
    campos_help: dict {columna: "texto de ayuda"} para ayuda contextual
    reactive_fields: dict {campo_trigger: [campos_dependientes]} para campos reactivos
    """
    
    # Inicializar parámetros opcionales
    campos_select = campos_select or {}
    campos_textarea = campos_textarea or {}
    campos_file = campos_file or {}
    campos_readonly = campos_readonly or []
    campos_password = campos_password or []
    campos_help = campos_help or {}
    reactive_fields = reactive_fields or {}

    # Validaciones básicas
    if df.empty:
        st.info(f"ℹ️ No hay {titulo.lower()}s registrados.")
        if allow_creation and on_create:
            _mostrar_formulario_creacion(
                titulo, on_create, columnas_visibles, campos_select, 
                campos_textarea, campos_file, campos_readonly,
                campos_password, campos_help, id_col
            )
        return

    if id_col not in df.columns:
        st.error(f"❌ La columna '{id_col}' no existe en los datos.")
        return

    # CSS optimizado
    st.markdown("""
    <style>
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
    
    .tabla-container {
        margin: 1rem 0;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #e1e5e9;
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

    # ===============================
    # PREPARAR DATOS PARA LA TABLA
    # ===============================
    try:
        # Asegurar que las columnas visibles existen
        columnas_existentes = [col for col in columnas_visibles if col in df.columns]
        if not columnas_existentes:
            st.error("❌ Ninguna de las columnas especificadas existe en los datos.")
            return

        # Preparar DataFrame para mostrar
        df_display = df[columnas_existentes].copy()
        
        # Limpiar datos para visualización
        for col in df_display.columns:
            if df_display[col].dtype == 'object':
                df_display[col] = df_display[col].fillna("")
            elif df_display[col].dtype == 'bool':
                df_display[col] = df_display[col].map({True: "✅ Sí", False: "❌ No", None: ""})
            elif pd.api.types.is_datetime64_any_dtype(df_display[col]):
                df_display[col] = df_display[col].dt.strftime('%d/%m/%Y').fillna("")

        # Renombrar columnas para mejor visualización
        column_mapping = {
            'nombre': 'Nombre',
            'email': 'Email',
            'cif': 'CIF/NIF',
            'telefono': 'Teléfono',
            'ciudad': 'Ciudad',
            'provincia': 'Provincia',
            'formacion_activo': 'Formación',
            'iso_activo': 'ISO 9001',
            'rgpd_activo': 'RGPD',
            'crm_activo': 'CRM',
            'created_at': 'Fecha Creación',
            'updated_at': 'Última Actualización'
        }
        
        df_display = df_display.rename(columns=column_mapping)

    except Exception as e:
        st.error(f"❌ Error al preparar datos para la tabla: {e}")
        return

    # ===============================
    # CONFIGURAR Y MOSTRAR TABLA
    # ===============================
    st.markdown(f"### 📋 {titulo}s registrados ({len(df)} total)")
    
    try:
        # Configurar AgGrid
        gb = GridOptionsBuilder.from_dataframe(df_display)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_selection('single', use_checkbox=False, rowMultiSelectWithClick=False)
        gb.configure_default_column(
            filterable=True,
            sorteable=True,
            resizable=True,
            minWidth=100
        )
        
        # Configurar columnas específicas
        for col in df_display.columns:
            if 'email' in col.lower():
                gb.configure_column(col, minWidth=200)
            elif col in ['✅ Sí', '❌ No'] or any(x in col.lower() for x in ['activo', 'estado']):
                gb.configure_column(col, maxWidth=120, cellStyle={'textAlign': 'center'})

        grid_options = gb.build()

        # Mostrar tabla con contenedor estilizado
        st.markdown('<div class="tabla-container">', unsafe_allow_html=True)
        
        grid_response = AgGrid(
            df_display,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            theme="balham",
            allow_unsafe_jscode=True,
            height=min(400, max(200, len(df_display) * 35 + 100)),
            width='100%'
        )
        
        st.markdown('</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Error al mostrar la tabla: {e}")
        # Fallback a tabla simple
        st.dataframe(df_display, use_container_width=True)
        grid_response = {"selected_rows": []}

    # ===============================
    # FICHA DE EDICIÓN
    # ===============================
    if grid_response.get("selected_rows"):
        selected_row = grid_response["selected_rows"][0]
        
        # Encontrar el registro original usando el índice
        try:
            # Obtener el índice de la fila seleccionada en el DataFrame original
            selected_index = df_display.index[df_display.iloc[:, 0] == selected_row[df_display.columns[0]]].tolist()[0]
            fila_original = df.iloc[selected_index].to_dict()
            
        except Exception as e:
            st.error(f"❌ Error al obtener datos de la fila seleccionada: {e}")
            return

        _mostrar_formulario_edicion(
            fila_original, titulo, on_save, id_col, columnas_visibles,
            campos_select, campos_textarea, campos_file, campos_readonly,
            campos_dinamicos, campos_help, reactive_fields
        )

    # ===============================
    # FORMULARIO DE CREACIÓN
    # ===============================
    if allow_creation and on_create:
        st.divider()
        _mostrar_formulario_creacion(
            titulo, on_create, columnas_visibles, campos_select,
            campos_textarea, campos_file, campos_readonly,
            campos_password, campos_help, id_col
        )

def _mostrar_formulario_edicion(
    fila: Dict[str, Any],
    titulo: str,
    on_save: Callable,
    id_col: str,
    columnas_visibles: List[str],
    campos_select: Dict,
    campos_textarea: Dict,
    campos_file: Dict,
    campos_readonly: List[str],
    campos_dinamicos: Optional[Callable],
    campos_help: Dict,
    reactive_fields: Dict
):
    """Muestra el formulario de edición optimizado."""
    
    st.markdown('<div class="ficha-container">', unsafe_allow_html=True)
    st.subheader(f"✏️ Editar {titulo}")
    
    # Mostrar identificador del registro
    nombre_display = (fila.get('nombre') or fila.get('nombre_completo') or 
                     fila.get('email') or str(fila.get(id_col, '')))
    st.caption(f"Modificando: {nombre_display}")

    # Determinar campos a mostrar
    campos_a_mostrar = columnas_visibles.copy()
    if campos_dinamicos:
        try:
            campos_a_mostrar = campos_dinamicos(fila)
            if id_col not in campos_a_mostrar:
                campos_a_mostrar.insert(0, id_col)
        except Exception as e:
            st.error(f"❌ Error en campos dinámicos: {e}")

    with st.form(f"form_editar_{fila[id_col]}", clear_on_submit=False):
        datos_editados = {}
        
        # Organizar campos en columnas si hay muchos
        if len(campos_a_mostrar) > 6:
            col1, col2 = st.columns(2)
            cols = [col1, col2]
        else:
            cols = [st]
        
        col_idx = 0
        
        for campo in campos_a_mostrar:
            if campo == id_col:
                continue
                
            # Determinar columna actual
            current_col = cols[col_idx % len(cols)] if len(cols) > 1 else cols[0]
            col_idx += 1
            
            with current_col:
                _crear_campo_formulario(
                    campo, fila, datos_editados, campos_select,
                    campos_textarea, campos_file, campos_readonly,
                    campos_help, is_creation=False
                )

        # Botones de acción
        col_guardar, col_cancelar = st.columns([1, 1])
        
        with col_guardar:
            guardar_clicked = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
        
        with col_cancelar:
            cancelar_clicked = st.form_submit_button("🚫 Cancelar", use_container_width=True)
        
        if guardar_clicked:
            try:
                # Filtrar solo los campos que realmente cambiaron
                cambios = {k: v for k, v in datos_editados.items() 
                          if v != fila.get(k) and v is not None}
                
                if cambios:
                    on_save(fila[id_col], cambios)
                else:
                    st.info("ℹ️ No se detectaron cambios para guardar.")
            except Exception as e:
                st.error(f"❌ Error al guardar: {e}")
        
        if cancelar_clicked:
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

def _mostrar_formulario_creacion(
    titulo: str,
    on_create: Callable,
    columnas_visibles: List[str],
    campos_select: Dict,
    campos_textarea: Dict,
    campos_file: Dict,
    campos_readonly: List[str],
    campos_password: List[str],
    campos_help: Dict,
    id_col: str
):
    """Muestra el formulario de creación optimizado."""
    
    with st.expander(f"➕ Crear nuevo {titulo.lower()}", expanded=False):
        st.markdown(f"### ➕ Nuevo {titulo}")
        
        with st.form(f"form_crear_{titulo.lower()}", clear_on_submit=True):
            datos_nuevos = {}
            
            # Filtrar campos para creación (excluir readonly excepto passwords)
            campos_creacion = [col for col in columnas_visibles 
                             if col not in campos_readonly or col in campos_password]
            
            # Excluir id_col de la creación
            if id_col in campos_creacion:
                campos_creacion.remove(id_col)
            
            # Organizar en columnas
            if len(campos_creacion) > 6:
                col1, col2 = st.columns(2)
                cols = [col1, col2]
            else:
                cols = [st]
            
            col_idx = 0
            
            for campo in campos_creacion:
                current_col = cols[col_idx % len(cols)] if len(cols) > 1 else cols[0]
                col_idx += 1
                
                with current_col:
                    _crear_campo_formulario(
                        campo, {}, datos_nuevos, campos_select,
                        campos_textarea, campos_file, campos_readonly,
                        campos_help, is_creation=True, campos_password=campos_password
                    )

            # Botón de creación
            crear_clicked = st.form_submit_button(f"➕ Crear {titulo.lower()}", use_container_width=True)
            
            if crear_clicked:
                try:
                    # Filtrar datos vacíos
                    datos_limpios = {k: v for k, v in datos_nuevos.items() 
                                   if v is not None and v != ""}
                    
                    if datos_limpios:
                        on_create(datos_limpios)
                    else:
                        st.warning("⚠️ Por favor, completa al menos los campos obligatorios.")
                except Exception as e:
                    st.error(f"❌ Error al crear: {e}")

def _crear_campo_formulario(
    campo: str,
    datos_actuales: Dict[str, Any],
    datos_form: Dict[str, Any],
    campos_select: Dict,
    campos_textarea: Dict,
    campos_file: Dict,
    campos_readonly: List[str],
    campos_help: Dict,
    is_creation: bool = False,
    campos_password: List[str] = None
):
    """Crea un campo individual del formulario."""
    
    campos_password = campos_password or []
    valor_actual = datos_actuales.get(campo, "")
    
    # Determinar etiqueta
    label = campo.replace('_', ' ').title()
    
    # Agregar ayuda si existe
    help_text = campos_help.get(campo, "")
    
    # Campo readonly
    if campo in campos_readonly and not (is_creation and campo in campos_password):
        st.text_input(f"{label} (solo lectura)", value=str(valor_actual), disabled=True, help=help_text)
        return

    # Campo select
    if campo in campos_select:
        opciones = campos_select[campo]
        if valor_actual in opciones:
            index = opciones.index(valor_actual)
        else:
            index = 0
        datos_form[campo] = st.selectbox(
            label, 
            options=opciones, 
            index=index,
            help=help_text,
            key=f"{campo}_{'create' if is_creation else 'edit'}"
        )
    
    # Campo textarea
    elif campo in campos_textarea:
        config = campos_textarea[campo]
        datos_form[campo] = st.text_area(
            config.get("label", label),
            value=str(valor_actual),
            height=config.get("height", 100),
            help=help_text,
            key=f"{campo}_{'create' if is_creation else 'edit'}"
        )
    
    # Campo file
    elif campo in campos_file:
        config = campos_file[campo]
        if valor_actual and not is_creation:
            st.caption(f"Archivo actual: {valor_actual}")
        datos_form[campo] = st.file_uploader(
            config.get("label", label),
            type=config.get("type", None),
            help=help_text,
            key=f"{campo}_{'create' if is_creation else 'edit'}"
        )
    
    # Campo password (solo en creación)
    elif campo in campos_password and is_creation:
        datos_form[campo] = st.text_input(
            label,
            type="password",
            help=help_text,
            key=f"{campo}_create"
        )
    
    # Campos específicos por tipo
    else:
        if 'fecha' in campo.lower():
            try:
                if valor_actual:
                    valor_fecha = pd.to_datetime(valor_actual).date()
                else:
                    valor_fecha = None
            except Exception:
                valor_fecha = None
            datos_form[campo] = st.date_input(
                label,
                value=valor_fecha,
                help=help_text,
                key=f"{campo}_{'create' if is_creation else 'edit'}"
            )
        
        elif campo.lower() in ['precio', 'importe', 'valor', 'cantidad', 'numero', 'horas']:
            try:
                valor_num = float(valor_actual) if valor_actual else 0.0
            except (ValueError, TypeError):
                valor_num = 0.0
            datos_form[campo] = st.number_input(
                label,
                value=valor_num,
                min_value=0.0,
                step=0.01 if any(x in campo.lower() for x in ['precio', 'importe']) else 1.0,
                help=help_text,
                key=f"{campo}_{'create' if is_creation else 'edit'}"
            )
        
        elif 'email' in campo.lower():
            datos_form[campo] = st.text_input(
                label,
                value=str(valor_actual),
                help=help_text,
                key=f"{campo}_{'create' if is_creation else 'edit'}"
            )
        
        elif campo.lower() in ['activo', 'activado', 'habilitado'] or '_activo' in campo:
            valor_bool = bool(valor_actual) if valor_actual is not None else False
            datos_form[campo] = st.checkbox(
                label,
                value=valor_bool,
                help=help_text,
                key=f"{campo}_{'create' if is_creation else 'edit'}"
            )
        
        else:
            # Campo de texto genérico
            datos_form[campo] = st.text_input(
                label,
                value=str(valor_actual),
                help=help_text,
                key=f"{campo}_{'create' if is_creation else 'edit'}"
            )
