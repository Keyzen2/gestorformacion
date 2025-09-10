import streamlit as st
import pandas as pd

def listado_crud(
    df,
    columnas_visibles,
    titulo,
    on_save,
    on_create,
    id_col,
    campos_select=None,
    campos_file=None,
    campos_textarea=None,
    campos_readonly=None,
    show_create=True,
    show_edit=True
):
    """
    Componente CRUD mejorado para listados con creación y edición.
    
    Parámetros:
    -----------
    df: DataFrame con los datos
    columnas_visibles: lista de columnas a mostrar
    titulo: título del CRUD
    on_save: función(id, datos_editados)
    on_create: función(datos_nuevos)
    id_col: nombre de la columna que actúa como ID
    campos_select: dict {columna: [opciones]}
    campos_file: dict {columna: {"label": str, "type": [extensiones]}}
    campos_textarea: dict {columna: {"label": str, "height": int}}
    campos_readonly: lista de campos de solo lectura
    show_create: bool para mostrar formulario de creación
    show_edit: bool para mostrar formularios de edición
    """
    
    campos_select = campos_select or {}
    campos_file = campos_file or {}
    campos_textarea = campos_textarea or {}
    campos_readonly = campos_readonly or []

    # ===============================
    # TABLA DE DATOS
    # ===============================
    st.markdown(f"### 📋 {titulo}s registrados")
    
    if df.empty:
        st.info(f"ℹ️ No hay {titulo.lower()}s registrados. Crea el primero usando el formulario de abajo.")
    else:
        # Mostrar métricas básicas
        col1, col2 = st.columns(2)
        with col1:
            st.metric(f"Total {titulo}s", len(df))
        with col2:
            # Última fecha de creación si existe
            if 'created_at' in df.columns:
                try:
                    ultima_fecha = pd.to_datetime(df['created_at']).dt.date.max()
                    st.metric("Último registro", ultima_fecha.strftime("%d/%m/%Y"))
                except Exception:
                    st.metric("Último registro", "N/D")
        
        # Tabla interactiva
        st.dataframe(
            df[columnas_visibles], 
            use_container_width=True,
            hide_index=True,
            height=300
        )

    # ===============================
    # FORMULARIO DE CREACIÓN
    # ===============================
    if show_create:
        st.divider()
        st.markdown(f"### ➕ Crear nuevo {titulo}")
        
        with st.form(f"create_{titulo.lower().replace(' ', '_')}", clear_on_submit=True):
            datos_nuevos = {}
            
            # Organizar campos en columnas si son muchos
            num_campos = len([col for col in columnas_visibles if col != id_col])
            if num_campos > 4:
                col1, col2 = st.columns(2)
                columnas_ui = [col1, col2]
                col_idx = 0
            else:
                columnas_ui = [st]
                col_idx = 0
                
            for col in columnas_visibles:
                if col == id_col:
                    continue
                    
                # Alternar entre columnas si hay más de 4 campos
                if len(columnas_ui) > 1:
                    current_col = columnas_ui[col_idx % 2]
                    col_idx += 1
                else:
                    current_col = columnas_ui[0]
                
                with current_col:
                    label = col.replace('_', ' ').title()
                    
                    if col in campos_select:
                        datos_nuevos[col] = st.selectbox(label, campos_select[col])
                        
                    elif col in campos_textarea:
                        cfg = campos_textarea[col]
                        datos_nuevos[col] = st.text_area(
                            cfg.get("label", label), 
                            height=cfg.get("height", 100)
                        )
                        
                    elif col in campos_file:
                        cfg = campos_file[col]
                        datos_nuevos[col] = st.file_uploader(
                            cfg.get("label", label), 
                            type=cfg.get("type", None)
                        )
                        
                    else:
                        # Detectar campos de fecha
                        if 'fecha' in col.lower():
                            datos_nuevos[col] = st.date_input(label)
                        # Detectar campos numéricos
                        elif col.lower() in ['precio', 'importe', 'valor', 'cantidad', 'numero', 'num']:
                            datos_nuevos[col] = st.number_input(label, min_value=0.0, step=0.01)
                        # Detectar campos de email
                        elif 'email' in col.lower():
                            datos_nuevos[col] = st.text_input(label, placeholder="usuario@ejemplo.com")
                        # Detectar campos de teléfono
                        elif 'telefono' in col.lower() or 'movil' in col.lower():
                            datos_nuevos[col] = st.text_input(label, placeholder="600123456")
                        else:
                            datos_nuevos[col] = st.text_input(label)
            
            col1, col2 = st.columns([1, 3])
            with col1:
                submitted = st.form_submit_button(f"✅ Crear {titulo}", use_container_width=True)
                
        if submitted:
            # Validar campos obligatorios básicos
            campos_vacios = [col for col in ['nombre', 'titulo', 'descripcion'] 
                           if col in datos_nuevos and not datos_nuevos[col]]
            
            if campos_vacios:
                st.error(f"⚠️ Los siguientes campos son obligatorios: {', '.join(campos_vacios)}")
            else:
                try:
                    on_create(datos_nuevos)
                except Exception as e:
                    st.error(f"❌ Error al crear {titulo.lower()}: {e}")

    # ===============================
    # FORMULARIOS DE EDICIÓN
    # ===============================
    if show_edit and not df.empty:
        st.divider()
        st.markdown(f"### ✏️ Editar {titulo}s")
        
        # Selector de registro a editar
        opciones_edicion = {}
        for _, row in df.iterrows():
            # Crear etiqueta descriptiva
            etiqueta = f"{row[id_col]}"
            if 'nombre' in row:
                etiqueta += f" - {row['nombre']}"
            elif 'titulo' in row:
                etiqueta += f" - {row['titulo']}"
            elif 'descripcion' in row:
                etiqueta += f" - {row['descripcion'][:50]}..."
            opciones_edicion[etiqueta] = row[id_col]
        
        registro_seleccionado = st.selectbox(
            f"Selecciona el {titulo.lower()} a editar:",
            options=list(opciones_edicion.keys()),
            format_func=lambda x: x
        )
        
        if registro_seleccionado:
            registro_id = opciones_edicion[registro_seleccionado]
            row_data = df[df[id_col] == registro_id].iloc[0]
            
            with st.expander(f"📝 Editando: {registro_seleccionado}", expanded=True):
                with st.form(f"edit_{titulo.lower().replace(' ', '_')}_{registro_id}"):
                    datos_editados = {}
                    
                    # Organizar campos en columnas para edición también
                    num_campos = len([col for col in columnas_visibles if col != id_col])
                    if num_campos > 4:
                        col1, col2 = st.columns(2)
                        columnas_ui = [col1, col2]
                        col_idx = 0
                    else:
                        columnas_ui = [st]
                        col_idx = 0
                    
                    for col in columnas_visibles:
                        if col == id_col:
                            continue
                            
                        # Alternar entre columnas
                        if len(columnas_ui) > 1:
                            current_col = columnas_ui[col_idx % 2]
                            col_idx += 1
                        else:
                            current_col = columnas_ui[0]
                            
                        valor_actual = row_data.get(col, "")
                        if pd.isna(valor_actual):
                            valor_actual = ""
                        
                        with current_col:
                            label = col.replace('_', ' ').title()
                            
                            # Campo readonly
                            if col in campos_readonly:
                                st.text_input(
                                    label, 
                                    value=str(valor_actual), 
                                    disabled=True,
                                    key=f"readonly_{col}_{registro_id}"
                                )
                                continue
                                
                            # Campo select
                            elif col in campos_select:
                                opciones = campos_select[col]
                                try:
                                    idx = opciones.index(valor_actual) if valor_actual in opciones else 0
                                except (ValueError, TypeError):
                                    idx
                
