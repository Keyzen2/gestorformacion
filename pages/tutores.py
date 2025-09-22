import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid

# Servicios
from services.grupos_service import GruposService
from services.data_service import DataService

# Utils del proyecto
from utils import validar_dni_cif, safe_int_conversion

# =========================
# ENTRADA PRINCIPAL
# =========================

def main(supabase, session_state):
    st.markdown("## 👨‍🏫 Gestión de Tutores")

    # Instancias de servicios
    ds = DataService(supabase, session_state)          # Para CRUD de tutores (usa data_service)
    gs = GruposService(supabase, session_state)        # Para asignaciones con grupos

    # Estado de navegación
    if "tutor_view" not in st.session_state:
        # "list" | "new" | <tutor_id>
        st.session_state.tutor_view = "list"

    if st.session_state.tutor_view == "list":
        vista_listado_tutores(ds, gs)
    elif st.session_state.tutor_view == "new":
        vista_form_tutor(ds, gs, tutor_id=None, es_creacion=True)
    else:
        # Edición
        vista_form_tutor(ds, gs, tutor_id=st.session_state.tutor_view, es_creacion=False)

# =========================
# LISTADO + FILTROS + CSV
# =========================

def vista_listado_tutores(ds: DataService, gs: GruposService):
    st.markdown("### 📋 Listado de Tutores")

    # Carga
    try:
        df = ds.get_tutores_completos()
    except Exception as e:
        st.error(f"❌ Error al cargar tutores: {e}")
        return

    # Si no hay datos
    if df is None or df.empty:
        st.info("ℹ️ No hay tutores registrados todavía.")
        st.divider()
        if st.button("➕ Crear Tutor", type="primary"):
            st.session_state.tutor_view = "new"
            st.rerun()
        return

    # Asegurar columnas base
    for col in ["id","nombre","apellidos","dni","email","telefono","empresa_nombre","especialidad"]:
        if col not in df.columns:
            df[col] = ""

    # ---- Filtros ----
    with st.container(border=True):
        st.markdown("#### 🔎 Filtros")
        c1, c2, c3, c4 = st.columns([2,2,2,1])

        with c1:
            filtro_texto = st.text_input("Texto (nombre, apellidos, email, DNI)", "")

        with c2:
            empresas = sorted([e for e in df["empresa_nombre"].dropna().unique().tolist() if e])
            empresa_sel = st.multiselect("Empresa", empresas)

        with c3:
            esp_opts = sorted([e for e in df["especialidad"].dropna().unique().tolist() if e])
            especialidad_sel = st.multiselect("Especialidad", esp_opts)

        with c4:
            page_size = st.selectbox("Tamaño pág.", [10, 25, 50, 100], index=1)

        # Aplicar filtros en cliente
        df_filtrado = df.copy()

        if filtro_texto:
            t = filtro_texto.strip().lower()
            mask = (
                df_filtrado["nombre"].astype(str).str.lower().str.contains(t)
                | df_filtrado["apellidos"].astype(str).str.lower().str.contains(t)
                | df_filtrado["email"].astype(str).str.lower().str.contains(t)
                | df_filtrado["dni"].astype(str).str.lower().str.contains(t)
            )
            df_filtrado = df_filtrado[mask]

        if empresa_sel:
            df_filtrado = df_filtrado[df_filtrado["empresa_nombre"].isin(empresa_sel)]

        if especialidad_sel:
            df_filtrado = df_filtrado[df_filtrado["especialidad"].isin(especialidad_sel)]

        # Paginación sencilla
        total = len(df_filtrado)
        total_pages = max(1, (total + page_size - 1) // page_size)
        c5, c6, c7 = st.columns([1,2,1])
        with c5:
            current_page = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1)
        with c7:
            st.write(f"Total: **{total}**")

        start = (current_page - 1) * page_size
        end = start + page_size
        df_page = df_filtrado.iloc[start:end].copy()

    # ---- Tabla ----
    col_config = {
        "dni": st.column_config.TextColumn("🪪 DNI", width="small"),
        "nombre": st.column_config.TextColumn("👤 Nombre", width="medium"),
        "apellidos": st.column_config.TextColumn("👤 Apellidos", width="medium"),
        "email": st.column_config.TextColumn("📧 Email", width="large"),
        "telefono": st.column_config.TextColumn("📞 Teléfono", width="medium"),
        "empresa_nombre": st.column_config.TextColumn("🏢 Empresa", width="medium"),
        "especialidad": st.column_config.TextColumn("🎓 Especialidad", width="medium"),
    }

    st.dataframe(
        df_page[["dni","nombre","apellidos","email","telefono","empresa_nombre","especialidad"]],
        use_container_width=True,
        hide_index=True,
        column_config=col_config
    )

    # ---- Exportar CSV ----
    csv_bytes = df_filtrado[["dni","nombre","apellidos","email","telefono","empresa_nombre","especialidad"]].to_csv(index=False).encode("utf-8")
    c1, c2, c3, c4 = st.columns([1.5,1.5,1,2])
    with c1:
        st.download_button(
            "⬇️ Exportar CSV (filtrado)",
            data=csv_bytes,
            file_name=f"tutores_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # ---- Selección para acciones ----
    with c2:
        # Mostramos selector por nombre + apellidos para UX
        opciones = [""] + (df_page["nombre"].astype(str) + " " + df_page["apellidos"].astype(str)).tolist()
        elegido = st.selectbox("Seleccionar", opciones, index=0)
    elegido_id = None
    if elegido:
        fila = df_page[(df_page["nombre"].astype(str) + " " + df_page["apellidos"].astype(str)) == elegido]
        if not fila.empty:
            elegido_id = fila.iloc[0]["id"]

    # ---- Botones ----
    st.divider()
    b1, b2, b3, b4 = st.columns([1.3,1.8,1.7,1.2])

    with b1:
        if st.button("➕ Crear Tutor", type="primary", use_container_width=True):
            st.session_state.tutor_view = "new"
            st.rerun()

    with b2:
        if st.button("✏️ Editar Tutor Seleccionado", use_container_width=True, disabled=not bool(elegido_id)):
            st.session_state.tutor_view = elegido_id
            st.rerun()

    with b3:
        if st.button("👥 Asignar a Grupos", use_container_width=True, disabled=not bool(elegido_id)):
            with st.expander("Asignación de grupos", expanded=True):
                gestionar_asignacion_tutores(gs, elegido_id)

    with b4:
        if st.button("🗑️ Eliminar", use_container_width=True, disabled=not bool(elegido_id)):
            try:
                ok = ds.delete_tutor(elegido_id)
                if ok:
                    st.success("✅ Tutor eliminado")
                    st.rerun()
                else:
                    st.error("❌ No se pudo eliminar el tutor")
            except Exception as e:
                st.error(f"❌ Error al eliminar: {e}")

# =========================
# FORMULARIO CREAR/EDITAR
# =========================

def vista_form_tutor(ds: DataService, gs: GruposService, tutor_id: Optional[str], es_creacion: bool):
    if es_creacion:
        st.markdown("### ➕ Crear Tutor")
        datos = {}
    else:
        st.markdown("### ✏️ Editar Tutor")
        datos = _cargar_tutor_por_id(ds, tutor_id)

        if not datos:
            st.error("❌ No se encontró el tutor")
            st.session_state.tutor_view = "list"
            st.rerun()
            return

    with st.form(f"form_tutor_{tutor_id or 'nuevo'}", clear_on_submit=es_creacion):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("👤 Nombre *", value=datos.get("nombre", ""))
            apellidos = st.text_input("👤 Apellidos *", value=datos.get("apellidos", ""))
            dni = st.text_input("🪪 DNI *", value=datos.get("dni", ""))
            email = st.text_input("📧 Email *", value=datos.get("email", ""))

        with c2:
            telefono = st.text_input("📞 Teléfono", value=datos.get("telefono", ""))
            especialidad = st.text_input("🎓 Especialidad", value=datos.get("especialidad", ""))
            experiencia = st.text_area("💼 Experiencia", value=datos.get("experiencia", ""), height=80)

        # Validaciones mínimas
        errores = []
        if not nombre: errores.append("Nombre requerido")
        if not apellidos: errores.append("Apellidos requeridos")
        if not dni: errores.append("DNI requerido")
        if not email: errores.append("Email requerido")

        st.divider()
        b1, b2, b3 = st.columns([1.3,1.3,1])
        with b1:
            submit = st.form_submit_button(
                "💾 Guardar",
                type="primary",
                use_container_width=True,
                disabled=len(errores) > 0
            )
        with b2:
            cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)
        with b3:
            volver = st.form_submit_button("⬅️ Volver al listado", use_container_width=True)

        if submit and not errores:
            datos_guardar = {
                "nombre": nombre.strip(),
                "apellidos": apellidos.strip(),
                "dni": dni.strip(),
                "email": email.strip(),
                "telefono": telefono.strip(),
                "especialidad": especialidad.strip(),
                "experiencia": experiencia.strip(),
            }

            # Asignar empresa si es gestor
            if ds.rol == "gestor" and ds.empresa_id and es_creacion:
                datos_guardar["empresa_id"] = ds.empresa_id

            try:
                if es_creacion:
                    ok = ds.create_tutor(datos_guardar)
                    if ok:
                        st.success("✅ Tutor creado correctamente")
                        st.session_state.tutor_view = "list"
                        st.rerun()
                else:
                    ok = ds.update_tutor(tutor_id, datos_guardar)
                    if ok:
                        st.success("✅ Tutor actualizado")
                        st.session_state.tutor_view = "list"
                        st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar: {e}")

        if cancelar or volver:
            st.session_state.tutor_view = "list"
            st.rerun()

    # Bloques adicionales solo en edición
    if not es_creacion:
        st.divider()
        with st.expander("📂 Currículum (CV)", expanded=False):
            gestionar_curriculum_tutor(ds, tutor_id, datos)

        with st.expander("👥 Asignación a Grupos", expanded=False):
            gestionar_asignacion_tutores(gs, tutor_id)

# =========================
# CURRÍCULUM (STORAGE)
# =========================

def gestionar_curriculum_tutor(ds: DataService, tutor_id: str, tutor_datos: Dict[str, Any]):
    """Gestión de CV en bucket 'documentos' con ruta empresa/{empresa_id}/tutores/{tutor_id}/cv.pdf"""
    empresa_id = tutor_datos.get("empresa_id") or ds.empresa_id
    if not empresa_id:
        st.warning("⚠️ Este tutor no tiene empresa asociada; no se puede gestionar CV.")
        return

    bucket = "documentos"
    # Permitimos PDF por defecto; puedes ampliar si lo necesitas
    file_key = f"empresa/{empresa_id}/tutores/{tutor_id}/cv.pdf"

    # Ver si ya hay CV
    try:
        public = ds.supabase.storage.from_(bucket).get_public_url(file_key)
        if public:
            st.success(f"CV actual: [Abrir]({public})")
            if st.button("🗑️ Eliminar CV", key=f"del_cv_{tutor_id}"):
                try:
                    ds.supabase.storage.from_(bucket).remove([file_key])
                    # Limpiamos el campo en BD si lo usas
                    try:
                        ds.update_tutor(tutor_id, {"cv_url": None})
                    except Exception:
                        pass
                    st.success("✅ CV eliminado")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error eliminando CV: {e}")
    except Exception:
        st.info("ℹ️ No hay CV subido todavía.")

    # Subida
    up = st.file_uploader("Subir CV (PDF)", type=["pdf"], key=f"up_cv_{tutor_id}")
    if up is not None:
        try:
            # Subida con upsert
            ds.supabase.storage.from_(bucket).upload(file_key, up.getvalue(), {"content-type": "application/pdf", "upsert": "true"})
            # Guardar URL en tabla (si usas cv_url)
            try:
                public = ds.supabase.storage.from_(bucket).get_public_url(file_key)
                ds.update_tutor(tutor_id, {"cv_url": public or file_key})
            except Exception:
                # Si falla, al menos guardamos la ruta
                ds.update_tutor(tutor_id, {"cv_url": file_key})
            st.success("✅ CV subido correctamente")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al subir CV: {e}")

# =========================
# ASIGNACIÓN N:N CON GRUPOS
# =========================

def gestionar_asignacion_tutores(gs: GruposService, tutor_id: str):
    """Asignar/desasignar tutor en múltiples grupos."""
    try:
        # Cargar grupos (usa el método que tengas disponible en tu GruposService)
        # Esperamos algo tipo lista/dict con id & codigo_grupo
        grupos = gs.supabase.table("grupos").select("id,codigo_grupo").order("created_at").execute()
        lista_grupos = grupos.data or []
        if not lista_grupos:
            st.info("ℹ️ No hay grupos disponibles.")
            return

        # Asignaciones actuales del tutor
        asign = gs.supabase.table("tutores_grupos").select("grupo_id").eq("tutor_id", tutor_id).execute()
        asignados_ids = {r["grupo_id"] for r in (asign.data or [])}

        mapa = {g["codigo_grupo"]: g["id"] for g in lista_grupos if g.get("codigo_grupo") and g.get("id")}
        preseleccion = [cod for cod, gid in mapa.items() if gid in asignados_ids]

        seleccion = st.multiselect(
            "Seleccionar grupos",
            options=list(mapa.keys()),
            default=preseleccion,
            help="El tutor quedará asignado a los grupos seleccionados"
        )

        if st.button("💾 Guardar asignaciones", type="primary"):
            nuevos_ids = {mapa[cod] for cod in seleccion}

            # Borrar las que sobran
            a_quitar = asignados_ids - nuevos_ids
            for gid in a_quitar:
                try:
                    gs.supabase.table("tutores_grupos").delete().eq("tutor_id", tutor_id).eq("grupo_id", gid).execute()
                except Exception as e:
                    st.error(f"Error quitando del grupo {gid}: {e}")

            # Insertar nuevas
            a_insertar = nuevos_ids - asignados_ids
            if a_insertar:
                payload = [{"tutor_id": tutor_id, "grupo_id": gid, "created_at": datetime.utcnow().isoformat()} for gid in a_insertar]
                try:
                    gs.supabase.table("tutores_grupos").insert(payload).execute()
                except Exception as e:
                    st.error(f"Error asignando grupos: {e}")

            st.success("✅ Asignaciones actualizadas")
            st.rerun()

    except Exception as e:
        st.error(f"❌ Error en asignación: {e}")

# =========================
# HELPERS
# =========================

def _cargar_tutor_por_id(ds: DataService, tutor_id: str) -> Dict[str, Any]:
    """Carga un tutor por ID directo desde Supabase (independiente de data_service)."""
    try:
        res = ds.supabase.table("tutores").select("*").eq("id", tutor_id).limit(1).execute()
        if res.data:
            return res.data[0]
        return {}
    except Exception as e:
        st.error(f"Error al cargar tutor: {e}")
        return {}
