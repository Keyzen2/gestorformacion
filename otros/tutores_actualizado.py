import io
import re
import uuid
from typing import Optional, Dict, Any, List, Tuple
import pandas as pd
import streamlit as st
from datetime import datetime, date, timedelta
from services.data_service import DataService
from utils import validar_dni_cif, subir_archivo_supabase, borrar_archivo_supabase

# =========================
# CONFIG Y CONSTANTES
# =========================

PAGE_SIZE_OPTIONS = [10, 25, 50]
DEFAULT_PAGE_SIZE = 10

# Keys de sesión
KEY_FILTROS = "tutores_filtros"
KEY_PAGINA = "tutores_pagina"
KEY_SELEC = "tutores_sel_id"
KEY_MODO = "tutores_modo"            # "list" | "create" | "edit"
KEY_EDIT_ID = "tutores_edit_id"
KEY_FORM_PREFIX = "tutor_form"

# =========================
# HELPERS
# =========================

def _ensure_session_defaults():
    if KEY_FILTROS not in st.session_state:
        st.session_state[KEY_FILTROS] = {
            "q": "",
            "tipo_tutor": "Todos",
            "empresa_id": None,
        }
    if KEY_PAGINA not in st.session_state:
        st.session_state[KEY_PAGINA] = 1
    if KEY_MODO not in st.session_state:
        st.session_state[KEY_MODO] = "list"
    if KEY_SELEC not in st.session_state:
        st.session_state[KEY_SELEC] = None
    if KEY_EDIT_ID not in st.session_state:
        st.session_state[KEY_EDIT_ID] = None

def _csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

def _build_cv_path(empresa_id: str, tutor_id: str, filename: str) -> str:
    # Guardamos en bucket "documentos": empresa_<id>/tutores/<tutor_id>/<filename>
    # El helper subir_archivo_supabase de utils genera su propia ruta; aquí vamos a manejar
    # la ruta directamente con el storage del supabase del DataService, para conservar el árbol.
    # Como alternativa, puedes usar arriba subir_archivo_supabase y pasar bucket custom.
    # Aquí devolvemos solo el path relativo dentro del bucket, la URL pública se pedirá al storage.
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
    return f"empresa_{empresa_id}/tutores/{tutor_id}/{safe_name}"

def _filter_tutores(df: pd.DataFrame, q: str = "", tipo: str = "Todos") -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if q:
        q_lower = q.lower().strip()
        mask = False
        for col in ["nombre", "apellidos", "email", "telefono", "nif", "dni", "especialidad", "empresa_nombre"]:
            if col in out.columns:
                mask = mask | out[col].astype(str).str.lower().str.contains(q_lower, na=False)
        out = out[mask]
    if tipo and tipo != "Todos" and "tipo_tutor" in out.columns:
        out = out[out["tipo_tutor"] == tipo]
    return out

def _paginate(df: pd.DataFrame, page: int, page_size: int) -> Tuple[pd.DataFrame, int]:
    if df.empty:
        return df, 1
    total_pages = max(1, (len(df) + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return df.iloc[start:end], total_pages

def _render_pagination(total_pages: int):
    if total_pages <= 1:
        return
    cols = st.columns([1,1,1,5])
    with cols[0]:
        if st.button("⏮ Primera", use_container_width=True):
            st.session_state[KEY_PAGINA] = 1
            st.rerun()
    with cols[1]:
        if st.button("◀ Anterior", use_container_width=True):
            st.session_state[KEY_PAGINA] = max(1, st.session_state[KEY_PAGINA] - 1)
            st.rerun()
    with cols[2]:
        if st.button("Siguiente ▶", use_container_width=True):
            st.session_state[KEY_PAGINA] = st.session_state[KEY_PAGINA] + 1
            st.rerun()
    with cols[3]:
        st.caption(f"Página {st.session_state[KEY_PAGINA]} de {total_pages}")

# =========================
# FORMULARIO
# =========================

def _form_tutor(ds: DataService, tutor: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Devuelve el dict con datos si submitted, si no None."""
    es_edicion = tutor is not None
    titulo = "✏️ Editar Tutor" if es_edicion else "➕ Nuevo Tutor"
    st.subheader(titulo)

    # Prefills
    datos = tutor.copy() if tutor else {}
    empresa_id_default = datos.get("empresa_id") or (ds.empresa_id if ds.rol == "gestor" else None)

    with st.form(f"{KEY_FORM_PREFIX}_{datos.get('id','nuevo')}"):
        c1, c2 = st.columns(2)

        with c1:
            nombre = st.text_input("👤 Nombre *", value=datos.get("nombre", ""))
            apellidos = st.text_input("👤 Apellidos *", value=datos.get("apellidos", ""))
            dni = st.text_input("🪪 DNI", value=datos.get("dni", ""))
            if dni and not validar_dni_cif(dni):
                st.warning("El DNI/NIF parece inválido")
            email = st.text_input("📧 Email *", value=datos.get("email", ""))
            telefono = st.text_input("📞 Teléfono", value=datos.get("telefono", ""))
            tipo_tutor = st.selectbox("🏷️ Tipo de tutor", ["Interno", "Externo", "Otro"], index=
                                      ["Interno","Externo","Otro"].index(datos.get("tipo_tutor","Interno"))
                                      if datos.get("tipo_tutor") in ["Interno","Externo","Otro"] else 0)
            especialidad = st.text_input("🎯 Especialidad", value=datos.get("especialidad", ""))

        with c2:
            direccion = st.text_input("🏠 Dirección", value=datos.get("direccion", ""))
            ciudad = st.text_input("🏙️ Ciudad", value=datos.get("ciudad", ""))
            provincia = st.text_input("🗺️ Provincia", value=datos.get("provincia", ""))
            codigo_postal = st.text_input("📮 Código Postal", value=datos.get("codigo_postal", ""))

            if ds.rol == "admin":
                # Cargar empresas para asignar propietario del tutor
                try:
                    emp_df = ds.get_empresas_completas()
                    opciones = {"— Selecciona —": None}
                    for _, row in emp_df.iterrows():
                        opciones[f"{row.get('nombre','(sin nombre)')} — {row.get('cif','')}"] = row["id"]
                    empresa_nombre = None
                    if datos.get("empresa_id"):
                        # reconstruir label
                        m = emp_df[emp_df["id"]==datos["empresa_id"]]
                        if not m.empty:
                            empresa_nombre = f"{m.iloc[0].get('nombre','(sin nombre)')} — {m.iloc[0].get('cif','')}"
                    sel = st.selectbox("🏢 Empresa (propietaria del tutor) *", list(opciones.keys()),
                                       index=list(opciones.keys()).index(empresa_nombre) if empresa_nombre in opciones else 0)
                    empresa_id = opciones[sel]
                except Exception as e:
                    st.error(f"No se pudieron cargar empresas: {e}")
                    empresa_id = empresa_id_default
            else:
                empresa_id = empresa_id_default
                st.info("Este tutor se asignará a tu empresa por defecto.")

        observaciones = st.text_area("📝 Observaciones", value=datos.get("observaciones",""), height=100)

        # Botonera
        cols = st.columns([2,1,1])
        submitted = cols[0].form_submit_button("💾 Guardar", type="primary", use_container_width=True)
        cancelar = cols[2].form_submit_button("Cancelar", use_container_width=True)

    if cancelar:
        return {"_cancelar": True}

    if not submitted:
        return None

    # Validaciones mínimas
    errores = []
    if not nombre.strip():
        errores.append("Nombre es obligatorio")
    if not apellidos.strip():
        errores.append("Apellidos es obligatorio")
    if not email.strip():
        errores.append("Email es obligatorio")
    if ds.rol == "admin" and not empresa_id:
        errores.append("Empresa propietaria obligatoria para admin")

    if errores:
        st.error("Revisa los siguientes errores:")
        for e in errores:
            st.error(f"• {e}")
        return None

    payload = {
        "nombre": nombre.strip(),
        "apellidos": apellidos.strip(),
        "dni": dni.strip() if dni else None,
        "email": email.strip(),
        "telefono": telefono.strip() if telefono else None,
        "tipo_tutor": tipo_tutor,
        "especialidad": especialidad.strip() if especialidad else None,
        "direccion": direccion.strip() if direccion else None,
        "ciudad": ciudad.strip() if ciudad else None,
        "provincia": provincia.strip() if provincia else None,
        "codigo_postal": codigo_postal.strip() if codigo_postal else None,
        "observaciones": observaciones.strip() if observaciones else None,
    }
    if empresa_id:
        payload["empresa_id"] = empresa_id
    return payload

# =========================
# CV MANAGEMENT
# =========================

def _seccion_cv(ds: DataService, tutor: Dict[str, Any]):
    st.markdown("### 📄 Currículum")
    cv_url = tutor.get("cv_url")

    c1, c2 = st.columns([2,1])
    with c1:
        if cv_url:
            st.success("CV subido")
            st.link_button("📎 Ver CV", cv_url, use_container_width=True)
        else:
            st.info("Sin CV")

    with c2:
        archivo = st.file_uploader("Subir/actualizar CV (PDF)", type=["pdf"], key=f"cv_{tutor['id']}")
        if archivo is not None:
            try:
                # Guardar en bucket "documentos" con árbol por empresa y tutor
                empresa_id = tutor.get("empresa_id") or ds.empresa_id
                if not empresa_id:
                    st.error("No se pudo determinar la empresa del tutor.")
                    return
                path_rel = _build_cv_path(empresa_id, tutor["id"], archivo.name)
                # Subir directo usando el cliente de storage
                ds.supabase.storage.from_("documentos").upload(path_rel, archivo.getvalue(), {"upsert": True})
                public_url = ds.supabase.storage.from_("documentos").get_public_url(path_rel)
                # Persistir URL
                ds.update_tutor(tutor["id"], {"cv_url": public_url})
                st.success("CV actualizado")
                st.rerun()
            except Exception as e:
                st.error(f"Error subiendo CV: {e}")

    if cv_url:
        if st.button("🗑️ Eliminar CV", type="secondary", key=f"delcv_{tutor['id']}"):
            try:
                # Intentar deducir el path desde la URL pública
                # Si no se puede, simplemente borramos el campo en DB.
                # (Opcional) Aquí se podría mapear URL->path si se sigue convención fija
                ds.update_tutor(tutor["id"], {"cv_url": None})
                st.success("CV eliminado (registro)")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo eliminar el CV: {e}")

# =========================
# LISTADO Y ACCIONES
# =========================

def _acciones_listado(ds: DataService, df: pd.DataFrame):
    # Cabecera de acciones
    c1, c2, c3, c4 = st.columns([2,1,1,1])
    with c1:
        st.write("")
    with c2:
        if st.button("🔄 Recargar", use_container_width=True):
            try:
                ds.get_tutores_completos.clear()
            except Exception:
                pass
            st.rerun()
    with c3:
        if not df.empty:
            st.download_button(
                "⬇️ Exportar CSV",
                data=_csv_bytes(df),
                file_name=f"tutores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
    with c4:
        if st.button("➕ Nuevo tutor", type="primary", use_container_width=True):
            st.session_state[KEY_MODO] = "create"
            st.session_state[KEY_EDIT_ID] = None
            st.session_state[KEY_SELEC] = None
            st.rerun()

def _render_listado(ds: DataService):
    # Filtros
    st.markdown("### 🔎 Filtros")
    fc1, fc2, fc3, fc4 = st.columns([3,1.5,1.5,1])
    with fc1:
        q = st.text_input("Buscar (nombre, apellidos, email, NIF, especialidad, empresa)", 
                          value=st.session_state[KEY_FILTROS]["q"], key="tut_q")
    with fc2:
        tipo = st.selectbox("Tipo de tutor", ["Todos","Interno","Externo","Otro"], 
                            index=["Todos","Interno","Externo","Otro"].index(st.session_state[KEY_FILTROS]["tipo_tutor"]))
    with fc3:
        page_size = st.selectbox("Filas por página", PAGE_SIZE_OPTIONS, index=PAGE_SIZE_OPTIONS.index(DEFAULT_PAGE_SIZE))
    with fc4:
        aplicar = st.button("Aplicar", use_container_width=True)

    if aplicar:
        st.session_state[KEY_FILTROS]["q"] = q
        st.session_state[KEY_FILTROS]["tipo_tutor"] = tipo
        st.session_state[KEY_PAGINA] = 1
        st.rerun()

    # Datos
    try:
        df = ds.get_tutores_completos()
    except Exception as e:
        st.error(f"Error en cargar tutores: {e}")
        return

    df = _filter_tutores(df, st.session_state[KEY_FILTROS]["q"], st.session_state[KEY_FILTROS]["tipo_tutor"])

    # Acciones superiors
    _acciones_listado(ds, df)

    if df.empty:
        st.info("No hay tutores con los criterios aplicados.")
        return

    # Selección por fila (mostramos con un índice y un botón Editar + Seleccionar)
    vista_cols = []
    for c in ["nombre","apellidos","email","telefono","nif","especialidad","tipo_tutor","empresa_nombre","created_at"]:
        if c in df.columns:
            vista_cols.append(c)

    page_df, total_pages = _paginate(df.reset_index(drop=True), st.session_state[KEY_PAGINA], page_size)

    st.dataframe(
        page_df[vista_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "nombre": st.column_config.TextColumn("Nombre", width="medium"),
            "apellidos": st.column_config.TextColumn("Apellidos", width="medium"),
            "email": st.column_config.TextColumn("Email", width="large"),
            "telefono": st.column_config.TextColumn("Teléfono", width="medium"),
            "nif": st.column_config.TextColumn("DNI/NIF", width="small"),
            "especialidad": st.column_config.TextColumn("Especialidad", width="medium"),
            "tipo_tutor": st.column_config.TextColumn("Tipo", width="small"),
            "empresa_nombre": st.column_config.TextColumn("Empresa", width="large"),
            "created_at": st.column_config.DatetimeColumn("Creado", format="YYYY-MM-DD", width="small")
        }
    )

    # Bloque de tarjetas con acciones por fila
    st.markdown("#### Acciones")
    for i, row in page_df.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([3,2,2,2,2])
            nombre_completo = f"{row.get('nombre','')} {row.get('apellidos','')}".strip()
            with c1:
                st.write(f"**{nombre_completo}**")
                st.caption(f"📧 {row.get('email','')} | 📞 {row.get('telefono','')}")
                if row.get("especialidad"):
                    st.caption(f"🎯 {row['especialidad']}")
            with c2:
                st.caption("Empresa")
                st.write(row.get("empresa_nombre",""))
            with c3:
                st.caption("DNI/NIF")
                st.write(row.get("nif","") or row.get("dni",""))
            with c4:
                if st.button("✏️ Editar", key=f"edit_{row['id']}", use_container_width=True):
                    st.session_state[KEY_MODO] = "edit"
                    st.session_state[KEY_EDIT_ID] = row["id"]
                    st.session_state[KEY_SELEC] = row["id"]
                    st.rerun()
            with c5:
                if st.button("🗑️ Eliminar", key=f"del_{row['id']}", use_container_width=True):
                    try:
                        ok = ds.delete_tutor(row["id"])
                        if ok:
                            st.success("Tutor eliminado")
                            st.rerun()
                        else:
                            st.error("No se pudo eliminar")
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")

    _render_pagination(total_pages)

# =========================
# MAIN
# =========================

def main(supabase_admin, session_state):
    st.title("👨‍🏫 Tutores")
    _ensure_session_defaults()

    # Crear servicio
    ds = DataService(supabase_admin, session_state)

    modo = st.session_state[KEY_MODO]
    edit_id = st.session_state[KEY_EDIT_ID]

    if modo == "list":
        _render_listado(ds)

    elif modo == "create":
        datos = _form_tutor(ds, None)
        if datos is None:
            return
        if datos.get("_cancelar"):
            st.session_state[KEY_MODO] = "list"
            st.rerun()
        else:
            ok = ds.create_tutor(datos)
            if ok:
                st.success("Tutor creado correctamente")
                st.session_state[KEY_MODO] = "list"
                st.rerun()
            else:
                st.error("No se pudo crear el tutor")

    elif modo == "edit":
        if not edit_id:
            st.warning("No se ha seleccionado tutor a editar")
            st.session_state[KEY_MODO] = "list"
            st.rerun()
            return
        # Cargar tutor
        try:
            df = ds.get_tutores_completos()
            fila = df[df["id"] == edit_id]
            if fila.empty:
                st.error("Tutor no encontrado")
                st.session_state[KEY_MODO] = "list"
                st.rerun()
                return
            tutor = fila.iloc[0].to_dict()
        except Exception as e:
            st.error(f"No se pudo cargar el tutor: {e}")
            st.session_state[KEY_MODO] = "list"
            return

        datos = _form_tutor(ds, tutor)
        if datos is None:
            # Mostrar sección de CV aunque no se haya enviado el form todavía
            _seccion_cv(ds, tutor)
            return

        if datos.get("_cancelar"):
            st.session_state[KEY_MODO] = "list"
            st.rerun()
            return

        # Guardar cambios
        try:
            ok = ds.update_tutor(tutor["id"], datos)
            if ok:
                st.success("Cambios guardados")
                st.session_state[KEY_MODO] = "list"
                st.rerun()
            else:
                st.error("No se pudo guardar")
        except Exception as e:
            st.error(f"Error guardando cambios: {e}")

        # Sección CV después de guardar (por si se quiere seguir gestionando)
        _seccion_cv(ds, {**tutor, **datos})

# Permitir ejecutar esta página de forma aislada para pruebas locales
if __name__ == "__main__":
    st.write("Esta página está diseñada para ejecutarse desde la app principal.")
