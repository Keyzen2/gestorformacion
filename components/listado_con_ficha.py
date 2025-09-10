import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

def listado_con_ficha(
    df,
    columnas_visibles,
    titulo,
    on_save,
    id_col="id",
    campos_select=None,
    campos_textarea=None,
    campos_readonly=None
):
    """
    Muestra un listado interactivo y, al seleccionar un registro, abre una ficha editable.

    df: DataFrame con los datos (incluyendo columna id_col)
    columnas_visibles: columnas que se muestran en la tabla
    titulo: título de la ficha
    on_save: función que recibe (id, datos_editados)
    id_col: columna identificadora
    campos_select: dict {columna: [opciones]} para selects
    campos_textarea: dict {columna: {"label": str}} para áreas de texto
    campos_readonly: lista de columnas que no se pueden editar
    """
    campos_select = campos_select or {}
    campos_textarea = campos_textarea or {}
    campos_readonly = campos_readonly or []

    gb = GridOptionsBuilder.from_dataframe(df[columnas_visibles])
    gb.configure_default_column(filter=True, sortable=True, resizable=True)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)
    gb.configure_selection('single', use_checkbox=False)  # selección por clic
    gb.configure_grid_options(rowSelection='single')
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
        st.subheader(f"✏️ {titulo}: {fila.get('nombre', fila[columnas_visibles[0]])}")

        with st.form("form_editar"):
            datos_editados = {}
            for col in columnas_visibles:
                if col == id_col:
                    continue

                valor_actual = fila[col] or ""

                if col in campos_readonly:
                    st.text_input(col, value=valor_actual, disabled=True)
                elif col in campos_select:
                    datos_editados[col] = st.selectbox(
                        col, options=campos_select[col], index=campos_select[col].index(valor_actual) if valor_actual in campos_select[col] else 0
                    )
                elif col in campos_textarea:
                    datos_editados[col] = st.text_area(
                        campos_textarea[col].get("label", col), value=valor_actual
                    )
                else:
                    datos_editados[col] = st.text_input(col, value=valor_actual)

            if st.form_submit_button("💾 Guardar cambios"):
                on_save(fila[id_col], datos_editados)
                
