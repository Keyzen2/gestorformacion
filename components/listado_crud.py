import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

def listado_crud(df, columnas_visibles, titulo, on_save, on_create, id_col="id", campos_select=None):
    """
    Muestra un listado interactivo con filtros, ficha editable y alta de nuevos registros.
    
    campos_select: dict opcional con { "NombreColumna": ["Opción1", "Opción2", ...] }
    """
    campos_select = campos_select or {}

    st.subheader(f"📋 {titulo}")

    # Tabla interactiva
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

    # Ficha de edición
    if grid_response["selected_rows"]:
        fila = grid_response["selected_rows"][0]
        st.markdown("---")
        st.subheader(f"✏️ Editar {titulo.lower()}: {fila[columnas_visibles[0]]}")
        with st.form("form_editar"):
            datos_editados = {}
            for col in columnas_visibles:
                if col != id_col:
                    if col in campos_select:
                        datos_editados[col] = st.selectbox(col, campos_select[col], index=campos_select[col].index(fila[col]) if fila[col] in campos_select[col] else 0)
                    else:
                        datos_editados[col] = st.text_input(col, value=fila[col] or "")
            if st.form_submit_button("💾 Guardar cambios"):
                on_save(fila[id_col], datos_editados)

    # Alta de nuevo registro
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
            
