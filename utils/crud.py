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
                if campo == "empresa_id":
                    opciones_fk = obtener_opciones_fk(supabase, "empresas", "nombre")
                    seleccion_fk = st.selectbox(
                        "Empresa",
                        options=[""] + list(opciones_fk.keys()),
                        index=(list(opciones_fk.keys()).index(registro.get("empresa_id", "")) + 1) if registro.get("empresa_id", "") in opciones_fk else 0
                    )
                    nuevos_valores[campo] = opciones_fk.get(seleccion_fk) if seleccion_fk else None
                else:
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
                    confirmar_doble = st.text_input("Escribe ELIMINAR para confirmar")
                    if confirmar and confirmar_doble.upper() == "ELIMINAR":
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
            if campo == "empresa_id":
                opciones_fk = obtener_opciones_fk(supabase, "empresas", "nombre")
                seleccion_fk = st.selectbox("Empresa", options=[""] + list(opciones_fk.keys()))
                nuevo[campo] = opciones_fk.get(seleccion_fk) if seleccion_fk else None
            else:
                nuevo[campo] = st.text_input(campo.replace("_", " ").title())

        if st.form_submit_button("✅ Crear"):
            try:
                supabase.table(nombre_tabla).insert(nuevo).execute()
                st.success("✅ Registro creado correctamente.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ No se pudo crear el registro: {e}")


def mapear_relaciones(supabase, datos):
    # Solo mapeamos empresa_id → nombre
    ids = list({fila["empresa_id"] for fila in datos if "empresa_id" in fila and fila["empresa_id"]})
    if ids:
        try:
            registros = supabase.table("empresas").select("id", "nombre").in_("id", ids).execute().data
            mapa = {r["id"]: r["nombre"] for r in registros}
            for fila in datos:
                if "empresa_id" in fila and fila["empresa_id"] in mapa:
                    fila["empresa_id"] = mapa[fila["empresa_id"]]
        except:
            pass
    return datos


def obtener_opciones_fk(supabase, tabla, campo_nombre):
    try:
        registros = supabase.table(tabla).select("id", campo_nombre).execute().data
        return {r[campo_nombre]: r["id"] for r in registros}
    except:
        return {}
