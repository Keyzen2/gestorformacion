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
    allow_creation: bool = True,
    campos_help: Optional[Dict[str, str]] = None,
    reactive_fields: Optional[Dict[str, List[str]]] = None
):
    """
    Componente simplificado que muestra una tabla con Streamlit nativo
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
        allow_creation: Si permitir crear nuevos registros
        campos_help: Dict con textos de ayuda
        reactive_fields: Dict con campos que dependen de otros
    """
    
    # Inicializar valores por defecto
    campos_select = campos_select or {}
    campos_textarea = campos_textarea or {}
    campos_file = campos_file or {}
    campos_readonly = campos_readonly or []
    campos_password = campos_password or []
    campos_help = campos_help or {}
    reactive_fields = reactive_fields or {}

    # CSS para mejorar la apariencia
    st.markdown("""
    <style>
    .ficha-container {
        border: 2px solid #e1e5e9;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
    }
    
    .registro-seleccionado {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
        padding: 8px;
        margin: 4px 0;
        border-radius: 4px;
    }
    
    .btn-accion {
        margin: 2px;
    }
    
    div.row-widget.stSelectbox > div[data-baseweb="select"] > div {
        background-color: #f8f9fa;
    }
    
    .stTextInput > div > div > input {
        background-color: #f8f9fa;
    }
    
    .campo-obligatorio label {
        font-weight: 600;
    }
    
    .campo-obligatorio label:after {
        content: " *";
        color: #ff4444;
    }
    </style>
    """, unsafe_allow_html=True)

    if df is None or df.empty:
        st.info(f"📋 No hay {titulo.lower()}s para mostrar.")
        
        # Mostrar formulario de creación si está permitido
        if allow_creation and on_create:
            mostrar_formulario_creacion(titulo, on_create, campos_select, campos_textarea, 
                                      campos_file, campos_password, campos_help, reactive_fields)
        return

    # =========================
    # TABLA PRINCIPAL CON SELECCIÓN
    # =========================
    st.markdown(f"### 📊 Lista de {titulo}s")
    st.caption(f"Total: {len(df)} registros")

    # Verificar que todas las columnas existen
    columnas_disponibles = [col for col in columnas_visibles if col in df.columns]
    if not columnas_disponibles:
        st.error("❌ Las columnas especificadas no existen en los datos.")
        return

    # Mostrar tabla simplificada
    df_display = df[columnas_disponibles + [id_col]].copy()
    
    # Formatear datos para mostrar
    for col in df_display.columns:
        if df_display[col].dtype == 'bool':
            df_display[col] = df_display[col].map({True: '✅ Sí', False: '❌ No', None: '⚪ N/A'})
        elif pd.api.types.is_datetime64_any_dtype(df_display[col]):
            df_display[col] = pd.to_datetime(df_display[col], errors='coerce').dt.strftime('%d/%m/%Y')

    # Selección de registro
    if id_col not in df.columns:
        st.error(f"❌ La columna ID '{id_col}' no existe en los datos.")
        return

    # Lista de registros para seleccionar
    opciones = []
    for _, row in df.iterrows():
        nombre_display = ""
        # Intentar usar diferentes campos para el nombre
        for campo_nombre in ['nombre', 'nombre_completo', 'titulo', columnas_disponibles[0]]:
            if campo_nombre in row and pd.notna(row[campo_nombre]):
                nombre_display = str(row[campo_nombre])
                break
        
        if not nombre_display:
            nombre_display = f"{titulo} {row[id_col]}"
            
        opciones.append(f"{nombre_display} (ID: {row[id_col]})")

    # Selectbox para elegir registro
    if opciones:
        seleccion = st.selectbox(
            f"🎯 Seleccionar {titulo.lower()} para editar:",
            options=[""] + opciones,
            key=f"selector_{titulo.lower()}"
        )

        if seleccion:
            # Extraer ID del registro seleccionado
            try:
                registro_id = seleccion.split("(ID: ")[-1].rstrip(")")
                fila_seleccionada = df[df[id_col].astype(str) == str(registro_id)].iloc[0]
                
                # Mostrar formulario de edición
                mostrar_formulario_edicion(
                    fila_seleccionada, titulo, on_save, on_delete, id_col,
                    campos_select, campos_textarea, campos_file, campos_readonly,
                    campos_dinamicos, campos_help, reactive_fields
                )
                
            except (IndexError, ValueError) as e:
                st.error(f"❌ Error al seleccionar registro: {e}")

    # =========================
    # TABLA DE VISTA PREVIA
    # =========================
    st.markdown("#### 👀 Vista previa de datos")
    
    # Mostrar tabla con paginación simple
    if len(df_display) > 10:
        page_size = st.selectbox("Registros por página:", [5, 10, 25, 50], index=1)
        page_number = st.number_input("Página:", min_value=1, max_value=(len(df_display) // page_size) + 1, value=1)
        start_idx = (page_number - 1) * page_size
        end_idx = start_idx + page_size
        df_page = df_display.iloc[start_idx:end_idx]
    else:
        df_page = df_display

    st.dataframe(df_page, use_container_width=True, hide_index=True)

    # =========================
    # FORMULARIO DE CREACIÓN
    # =========================
    if allow_creation and on_create:
        st.divider()
        mostrar_formulario_creacion(titulo, on_create, campos_select, campos_textarea,
                                  campos_file, campos_password, campos_help, reactive_fields)


def mostrar_formulario_edicion(fila, titulo, on_save, on_delete, id_col, campos_select,
                             campos_textarea, campos_file, campos_readonly, campos_dinamicos,
                             campos_help, reactive_fields):
    """Muestra el formulario de edición para un registro."""
    
    st.markdown('<div class="ficha-container">', unsafe_allow_html=True)
    st.markdown(f"### ✏️ Editar {titulo}")
    
    # Determinar campos a mostrar
    if campos_dinamicos:
        try:
            campos_a_mostrar = campos_dinamicos(fila)
        except Exception as e:
            st.error(f"❌ Error en campos dinámicos: {e}")
            campos_a_mostrar = list(fila.index)
    else:
        campos_a_mostrar = [col for col in fila.index if col != id_col]

    with st.form(f"form_editar_{fila[id_col]}", clear_on_submit=False):
        datos_editados = {}
        
        # Organizar en columnas si hay muchos campos
        if len(campos_a_mostrar) > 6:
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
                    campos_readonly, campos_password, campos_help, f"edit_{fila[id_col]}"
                )
                
                if valor_editado is not None:
                    datos_editados[campo] = valor_editado

        # Botones de acción
        col_save, col_delete = st.columns(2)
        
        with col_save:
            btn_guardar = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
        
        with col_delete:
            if on_delete:
                btn_eliminar = st.form_submit_button("🗑️ Eliminar", use_container_width=True)
            else:
                btn_eliminar = False

        # Procesar acciones
        if btn_guardar:
            try:
                on_save(fila[id_col], datos_editados)
            except Exception as e:
                st.error(f"❌ Error al guardar: {e}")
        
        if btn_eliminar and on_delete:
            if st.session_state.get(f"confirmar_eliminar_{fila[id_col]}", False):
                try:
                    on_delete(fila[id_col])
                    st.session_state[f"confirmar_eliminar_{fila[id_col]}"] = False
                except Exception as e:
                    st.error(f"❌ Error al eliminar: {e}")
            else:
                st.session_state[f"confirmar_eliminar_{fila[id_col]}"] = True
                st.warning("⚠️ Haz clic en Eliminar otra vez para confirmar.")

    st.markdown('</div>', unsafe_allow_html=True)


def mostrar_formulario_creacion(titulo, on_create, campos_select, campos_textarea,
                              campos_file, campos_password, campos_help, reactive_fields):
    """Muestra el formulario para crear un nuevo registro."""
    
    st.markdown(f"### ➕ Crear Nuevo {titulo}")
    
    with st.form("form_crear", clear_on_submit=True):
        datos_nuevos = {}
        
        # Obtener todos los campos posibles de los parámetros
        todos_campos = set()
        todos_campos.update(campos_select.keys())
        todos_campos.update(campos_textarea.keys())
        todos_campos.update(campos_file.keys())
        todos_campos.update(campos_password)
        
        # Si no hay campos definidos, mostrar campos básicos
        if not todos_campos:
            todos_campos = ['nombre', 'email']  # Campos por defecto
        
        # Organizar en columnas
        if len(todos_campos) > 4:
            col1, col2 = st.columns(2)
            columnas = [col1, col2]
        else:
            columnas = [st]
        
        for i, campo in enumerate(sorted(todos_campos)):
            col_actual = columnas[i % len(columnas)] if len(columnas) > 1 else columnas[0]
            
            with col_actual:
                valor = crear_campo_formulario(
                    campo, "", campos_select, campos_textarea, campos_file,
                    [], campos_password, campos_help, "create"
                )
                
                if valor is not None and valor != "":
                    datos_nuevos[campo] = valor

        btn_crear = st.form_submit_button("➕ Crear", type="primary", use_container_width=True)
        
        if btn_crear:
            try:
                on_create(datos_nuevos)
            except Exception as e:
                st.error(f"❌ Error al crear: {e}")


def crear_campo_formulario(campo, valor_actual, campos_select, campos_textarea, campos_file,
                         campos_readonly, campos_password, campos_help, prefix):
    """Crea un campo de formulario según el tipo."""
    
    # Texto de ayuda
    help_text = campos_help.get(campo, None)
    
    # Campo de solo lectura
    if campo in campos_readonly:
        st.text_input(f"{campo.replace('_', ' ').title()}", value=str(valor_actual), disabled=True, help=help_text)
        return valor_actual
    
    # Campo de contraseña
    if campo in campos_password:
        return st.text_input(
            f"{campo.replace('_', ' ').title()}", 
            value="", 
            type="password", 
            help=help_text,
            key=f"{prefix}_{campo}"
        )
    
    # Campo select
    if campo in campos_select:
        opciones = campos_select[campo]
        try:
            index = opciones.index(valor_actual) if valor_actual in opciones else 0
        except (ValueError, TypeError):
            index = 0
        
        return st.selectbox(
            f"{campo.replace('_', ' ').title()}", 
            opciones, 
            index=index, 
            help=help_text,
            key=f"{prefix}_{campo}"
        )
    
    # Campo textarea
    if campo in campos_textarea:
        return st.text_area(
            f"{campo.replace('_', ' ').title()}", 
            value=str(valor_actual), 
            help=help_text,
            key=f"{prefix}_{campo}"
        )
    
    # Campo file
    if campo in campos_file:
        config = campos_file[campo]
        return st.file_uploader(
            f"{campo.replace('_', ' ').title()}", 
            type=config.get("type", None), 
            help=help_text,
            key=f"{prefix}_{campo}"
        )
    
    # Campo booleano
    if isinstance(valor_actual, bool) or str(valor_actual).lower() in ['true', 'false', 'sí', 'no', '✅', '❌']:
        valor_bool = valor_actual if isinstance(valor_actual, bool) else str(valor_actual).lower() in ['true', 'sí', '✅']
        return st.checkbox(
            f"{campo.replace('_', ' ').title()}", 
            value=valor_bool, 
            help=help_text,
            key=f"{prefix}_{campo}"
        )
    
    # Campo de texto por defecto
    return st.text_input(
        f"{campo.replace('_', ' ').title()}", 
        value=str(valor_actual), 
        help=help_text,
        key=f"{prefix}_{campo}"
      )
