import streamlit as st

def crud_tabla(supabase, nombre_tabla, campos_visibles, campos_editables):
    st.header(f"📋 Gestión de {nombre_tabla.replace('_', ' ').title()}")

    try:
        datos = supabase.table(nombre_tabla).select("*").execute().data
    except Exception as e:
        st.error(f"❌ Error al cargar datos: {e}")
        return

    if not datos:
        st.info("ℹ️ No hay registros disponibles.")
        return

    datos = mapear_relaciones(supabase, datos)

    st.dataframe([{k: fila.get(k) for k in campos_visibles} for fila in datos])

    opciones = {f"{fila[campos_visibles[0]]}": fila for fila in datos}
    seleccion = st.selectbox("Selecciona un registro para editar:", [""] + list(opciones.keys()))

    if seleccion:
        registro = opciones[seleccion]
        with st.form("form_editar"):
            nuevos_valores = {}
            for campo in campos_editables:
                nuevos_valores[campo] = st.text_input(
                    campo.replace("_", " ").title(),
                    value=registro.get(campo, "")
                )

            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 Guardar cambios"):
                    try:
                        supabase.table(nombre_tabla).update(nuevos_valores).eq("id", registro["id"]).execute()
                        st.success("✅ Registro actualizado correctamente.")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"❌ No se pudo guardar el registro: {e}")

            with col2:
                if st.form_submit_button("🗑️ Eliminar registro"):
                    confirmar = st.checkbox("Confirmar eliminación")
                    if confirmar:
                        try:
                            supabase.table(nombre_tabla).delete().eq("id", registro["id"]).execute()
                            st.success("✅ Registro eliminado correctamente.")
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"❌ No se pudo eliminar el registro: {e}")

    st.subheader("➕ Añadir nuevo registro")
    with st.form("form_nuevo"):
        nuevo = {}
        for campo in campos_editables:
            nuevo[campo] = st.text_input(campo.replace("_", " ").title())

        if st.form_submit_button("✅ Crear"):
            try:
                supabase.table(nombre_tabla).insert(nuevo).execute()
                st.success("✅ Registro creado correctamente.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ No se pudo crear el registro: {e}")

def mapear_relaciones(supabase, datos):
    tablas_relacion = {
        "empresa_id": ("empresas", "nombre"),
        "accion_formativa_id": ("acciones_formativas", "nombre"),
        "grupo_id": ("grupos", "codigo_grupo")
    }

    for campo_id, (tabla, campo_nombre) in tablas_relacion.items():
        ids = list({fila[campo_id] for fila in datos if campo_id in fila and fila[campo_id]})
        if ids:
            try:
                registros = supabase.table(tabla).select("id", campo_nombre).in_("id", ids).execute().data
                mapa = {r["id"]: r[campo_nombre] for r in registros}
                for fila in datos:
                    if campo_id in fila and fila[campo_id] in mapa:
                        fila[campo_id] = mapa[fila[campo_id]]
            except:
                pass
    return datos
