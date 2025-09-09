import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

def listado_con_ficha(df, columnas_visibles, titulo, on_save, id_col="id"):
    """
    Muestra un listado interactivo con filtros y ficha editable.
    
    df: DataFrame con los datos (incluyendo columna id_col para actualizaciones)
    columnas_visibles: lista de columnas que se mostrarán en la tabla
    titulo: título de la ficha
    on_save: función que recibe (id, datos_editados) para guardar cambios
    id_col: nombre de la columna que contiene el identificador interno
    """
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

    if grid_response["selected_rows"]:
        fila = grid_response["selected_rows"][0]
        st.subheader(f"✏️ {titulo}: {fila[columnas_visibles[0]]}")
        with st.form("form_editar"):
            datos_editados = {}
            for col in columnas_visibles:
                if col != id_col:
                    datos_editados[col] = st.text_input(col, value=fila[col] or "")
            if st.form_submit_button("💾 Guardar cambios"):
                on_save(fila[id_col], datos_editados)
              
