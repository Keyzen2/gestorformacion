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
    campos_file=None
):
    """
    df: DataFrame con los datos
    columnas_visibles: lista de columnas a mostrar
    titulo: título del CRUD
    on_save: función(id, datos_editados)
    on_create: función(datos_nuevos)
    id_col: nombre de la columna que actúa como ID
    campos_select: dict {columna: [opciones]}
    campos_file: dict {columna: {"label": str, "type": [extensiones]}}
    """

    st.markdown(f"### 📋 {titulo}s registrados")

    # Tabla de datos
    st.dataframe(df[columnas_visibles], use_container_width=True)

    st.divider()
    st.markdown(f"### ➕ Crear nuevo {titulo}")

    # Formulario de creación
    with st.form(f"create_{titulo}", clear_on_submit=True):
        datos_nuevos = {}
        for col in columnas_visibles:
            if col == id_col:
                continue
            if campos_select and col in campos_select:
                datos_nuevos[col] = st.selectbox(col, campos_select[col])
            elif campos_file and col in campos_file:
                cfg = campos_file[col]
                datos_nuevos[col] = st.file_uploader(cfg["label"], type=cfg.get("type", None))
            else:
                datos_nuevos[col] = st.text_input(col)
        submitted = st.form_submit_button("Crear")
    if submitted:
        on_create(datos_nuevos)

    st.divider()
    st.markdown(f"### ✏️ Editar {titulo}")

    # Formulario de edición por cada fila
    for _, row in df.iterrows():
        with st.expander(f"{row[id_col]} - {row[columnas_visibles[1]]}"):
            with st.form(f"edit_{titulo}_{row[id_col]}", clear_on_submit=True):
                datos_editados = {}
                for col in columnas_visibles:
                    if col == id_col:
                        continue
                    valor_actual = row[col] if col in row else ""
                    if campos_select and col in campos_select:
                        opciones = campos_select[col]
                        idx = opciones.index(valor_actual) if valor_actual in opciones else 0
                        datos_editados[col] = st.selectbox(col, opciones, index=idx)
                    elif campos_file and col in campos_file:
                        cfg = campos_file[col]
                        datos_editados[col] = st.file_uploader(cfg["label"], type=cfg.get("type", None), key=f"{col}_{row[id_col]}")
                    else:
                        datos_editados[col] = st.text_input(col, value=valor_actual or "")
                guardar = st.form_submit_button("Guardar cambios")
            if guardar:
                on_save(row[id_col], datos_editados)
                
