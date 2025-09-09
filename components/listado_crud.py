import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

def listado_crud(
    df,
    columnas_visibles,
    titulo,
    on_save,
    on_create,
    id_col="id",
    campos_select=None
):
    """
    Componente CRUD reutilizable con listado interactivo y ficha editable.

    Parámetros:
    -----------
    df : pandas.DataFrame
        DataFrame con los datos a mostrar. Debe incluir la columna id_col para actualizaciones.
    columnas_visibles : list
        Lista de columnas que se mostrarán en la tabla y en los formularios.
    titulo : str
        Título de la entidad (ej. "Usuario", "Participante").
    on_save : function
        Función que recibe (id, datos_editados) para guardar cambios.
    on_create : function
        Función que recibe (datos_nuevos) para crear un registro.
    id_col : str
        Nombre de la columna que contiene el identificador interno.
    campos_select : dict opcional
        Diccionario con { "NombreColumna": ["Opción1", "Opción2", ...] } para renderizar selects.
    """
    campos_select = campos_select or {}

    st.subheader(f"📋 {titulo}s registrados")

    # =========================
    # Tabla interactiva
    # =========================
    gb = GridOptionsBuilder.from_dataframe(df[columnas_visibles])
    gb.configure_default_column(filter=True, sortable=True, resizable=True)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)
    gb.configure_selection('single', use_checkbox=True)
    grid_options = gb.build()

    grid_response = AgGrid(
        df[columnas_visibles],
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        theme="balham",
        allow_unsafe_jscode=True
    )

    # =========================
    # Ficha de edición
    # =========================
    if grid_response["selected_rows"]:
        fila = grid_response["selected_rows"][0]
        st.markdown("---")
        st.subheader(f"✏️ Editar {titulo.lower()}: {fila[columnas_visibles[0]]}")
        with st.form("form_editar"):
            datos_editados = {}
            for col in columnas_visibles:
                if col != id_col:
                    if col in campos_select:
                        opciones = campos_select[col]
                        idx = opciones.index(fila[col]) if fila[col] in opciones else 0
                        datos_editados[col] = st.selectbox(col, opciones, index=idx)
                    else:
                        datos_editados[col] = st.text_input(col, value=fila[col] or "")
            if st.form_submit_button("💾 Guardar cambios"):
                on_save(fila[id_col], datos_editados)

    # =========================
    # Alta de nuevo registro
    # =========================
    st.markdown("---")
    st.subheader(f"➕ Nuevo {titulo.lower()}")
    with st.form("form_crear"):
        datos_nuevos = {}
        for col in columnas_visibles:
            if col != id_col:
                if col in campos_select:
                    datos_nuevos[col] = st.selectbox(col, campos_select[col])
                else:
                    datos_nuevos[col] = st.text_input(col)
        if st.form_submit_button("✅ Crear"):
            on_create(datos_nuevos)
            
