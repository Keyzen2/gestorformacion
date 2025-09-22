import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import validar_dni_cif, export_csv
from services.participantes_service import get_participantes_service
from services.empresas_service import get_empresas_service

# =========================
# Cargar datos auxiliares
# =========================
@st.cache_data(ttl=300)
def cargar_empresas_disponibles(empresas_service, session_state):
    """Empresas disponibles según rol (admin ve todas, gestor su empresa + hijas)."""
    try:
        df_empresas = empresas_service.get_empresas_con_jerarquia()
        if session_state.role == "admin":
            return df_empresas
        elif session_state.role == "gestor":
            empresa_id = session_state.user.get("empresa_id")
            return df_empresas[
                (df_empresas["id"] == empresa_id) |
                (df_empresas["empresa_matriz_id"] == empresa_id)
            ]
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error cargando empresas disponibles: {e}")
        return pd.DataFrame()
def mostrar_tabla_participantes(df_participantes, titulo_tabla="📋 Lista de Participantes"):
    """Muestra tabla con selección de fila."""
    if df_participantes.empty:
        st.info("No hay participantes disponibles")
        return None
    
    st.markdown(f"### {titulo_tabla}")
    
    df_display = df_participantes.copy()
    columnas = ["nombre", "apellidos", "dni", "email", "telefono", "empresa_nombre"]
    column_config = {
        "nombre": st.column_config.TextColumn("👤 Nombre", width="medium"),
        "apellidos": st.column_config.TextColumn("👥 Apellidos", width="large"),
        "dni": st.column_config.TextColumn("🆔 DNI", width="small"),
        "email": st.column_config.TextColumn("📧 Email", width="large"),
        "telefono": st.column_config.TextColumn("📞 Teléfono", width="medium"),
        "empresa_nombre": st.column_config.TextColumn("🏢 Empresa", width="large")
    }
    
    evento = st.dataframe(
        df_display[columnas],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    if evento.selection.rows:
        return df_display.iloc[evento.selection.rows[0]]
    return None
def mostrar_formulario_participante(participante_data, participantes_service, empresas_service, session_state, es_creacion=False):
    """Formulario para crear o editar participantes."""
    
    if es_creacion:
        st.subheader("➕ Crear Participante")
        datos = {}
    else:
        st.subheader(f"✏️ Editar Participante: {participante_data['nombre']} {participante_data.get('apellidos','')}")
        datos = participante_data.copy()
    
    form_id = f"participante_{datos.get('id','nuevo')}_{'crear' if es_creacion else 'editar'}"
    
    with st.form(form_id, clear_on_submit=es_creacion):
        # =========================
        # DATOS PERSONALES
        # =========================
        st.markdown("### 👤 Datos Personales")
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre", value=datos.get("nombre",""), key=f"{form_id}_nombre")
            apellidos = st.text_input("Apellidos", value=datos.get("apellidos",""), key=f"{form_id}_apellidos")
            tipo_documento = st.selectbox(
                "Tipo de Documento",
                options=["", "DNI", "NIE", "PASAPORTE"],
                index=["","DNI","NIE","PASAPORTE"].index(datos.get("tipo_documento","")) if datos.get("tipo_documento","") in ["","DNI","NIE","PASAPORTE"] else 0,
                key=f"{form_id}_tipo_doc"
            )
            dni = st.text_input("Documento (DNI/NIE/Pasaporte)", value=datos.get("dni",""), key=f"{form_id}_dni")
            nif = st.text_input("NIF", value=datos.get("nif",""), key=f"{form_id}_nif")
            niss = st.text_input("NISS (Seguridad Social)", value=datos.get("niss",""), key=f"{form_id}_niss")
        with col2:
            fecha_nacimiento = st.date_input(
                "Fecha de nacimiento",
                value=datos.get("fecha_nacimiento") if datos.get("fecha_nacimiento") else date(1990,1,1),
                key=f"{form_id}_fecha_nac"
            )
            sexo = st.selectbox(
                "Sexo",
                options=["", "M", "F", "O"],
                index=["","M","F","O"].index(datos.get("sexo","")) if datos.get("sexo","") in ["","M","F","O"] else 0,
                key=f"{form_id}_sexo"
            )
            telefono = st.text_input("Teléfono", value=datos.get("telefono",""), key=f"{form_id}_tel")
            email = st.text_input("Email", value=datos.get("email",""), key=f"{form_id}_email")

        # =========================
        # DATOS EMPRESA
        # =========================
        st.markdown("### 🏢 Empresa Asociada")
        df_empresas = cargar_empresas_disponibles(empresas_service, session_state)
        empresa_options = {row["nombre"]: row["id"] for _,row in df_empresas.iterrows()}
        
        empresa_actual_id = datos.get("empresa_id")
        empresa_actual_nombre = next((k for k,v in empresa_options.items() if v == empresa_actual_id), "")
        
        empresa_sel = st.selectbox(
            "Selecciona Empresa",
            options=[""] + list(empresa_options.keys()),
            index=list(empresa_options.keys()).index(empresa_actual_nombre)+1 if empresa_actual_nombre else 0,
            key=f"{form_id}_empresa"
        )
        empresa_id = empresa_options.get(empresa_sel) if empresa_sel else None
        
        # =========================
        # DATOS FORMACIÓN
        # =========================
        st.markdown("### 🎓 Formación")
        grupo_id = st.text_input("Grupo ID", value=datos.get("grupo_id","") or "", key=f"{form_id}_grupo")
        
        # =========================
        # VALIDACIONES
        # =========================
        errores = []
        if not nombre:
            errores.append("Nombre requerido")
        if not apellidos:
            errores.append("Apellidos requeridos")
        if dni and not validar_dni_cif(dni):
            errores.append("Documento inválido")
        if not empresa_id:
            errores.append("Debe seleccionar una empresa")
        
        if errores:
            st.error("⚠️ Errores: " + ", ".join(errores))
        
        # =========================
        # BOTONES
        # =========================
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button(
                "➕ Crear Participante" if es_creacion else "💾 Guardar Cambios",
                type="primary",
                use_container_width=True
            )
        with col2:
            eliminar = st.form_submit_button(
                "🗑️ Eliminar" if not es_creacion and session_state.role == "admin" else "Cancelar",
                type="secondary",
                use_container_width=True
            ) if not es_creacion else False
        
        # =========================
        # PROCESAMIENTO
        # =========================
        if submitted:
            procesar_guardado_participante(
                datos, nombre, apellidos, tipo_documento, dni, nif, niss,
                fecha_nacimiento, sexo, telefono, email, empresa_id, grupo_id,
                participantes_service, es_creacion
            )
        
        if eliminar:
            if st.session_state.get("confirmar_eliminar_participante"):
                try:
                    ok = participantes_service.delete_participante(datos["id"])
                    if ok:
                        st.success("✅ Participante eliminado correctamente")
                        del st.session_state["confirmar_eliminar_participante"]
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error eliminando participante: {e}")
            else:
                st.session_state["confirmar_eliminar_participante"] = True
                st.warning("⚠️ Pulsa nuevamente para confirmar eliminación")
# ==================================================
# GUARDADO DE PARTICIPANTE
# ==================================================
def procesar_guardado_participante(datos, nombre, apellidos, tipo_documento, dni, nif, niss,
                                   fecha_nacimiento, sexo, telefono, email, empresa_id, grupo_id,
                                   participantes_service, es_creacion=False):
    """Procesa creación o actualización de participante."""
    try:
        # Validaciones adicionales
        if dni and not validar_dni_cif(dni):
            st.error("❌ Documento inválido")
            return
        if not empresa_id:
            st.error("❌ Debe seleccionar una empresa")
            return
        
        datos_participante = {
            "nombre": nombre,
            "apellidos": apellidos,
            "tipo_documento": tipo_documento or None,
            "dni": dni,
            "nif": nif,
            "niss": niss,
            "fecha_nacimiento": fecha_nacimiento.isoformat() if fecha_nacimiento else None,
            "sexo": sexo,
            "telefono": telefono,
            "email": email,
            "empresa_id": empresa_id,
            "grupo_id": grupo_id or None,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if es_creacion:
            ok, _ = participantes_service.crear_participante(datos_participante)
            if ok:
                st.success("✅ Participante creado correctamente")
                st.rerun()
        else:
            ok = participantes_service.update_participante(datos["id"], datos_participante)
            if ok:
                st.success("✅ Participante actualizado correctamente")
                st.rerun()
    except Exception as e:
        st.error(f"❌ Error procesando participante: {e}")


# ==================================================
# EXPORTACIÓN
# ==================================================
def exportar_participantes(participantes_service, session_state):
    """Exporta listado de participantes según rol a CSV."""
    try:
        df = participantes_service.get_participantes_completos()
        if session_state.role == "gestor":
            empresa_id = session_state.user.get("empresa_id")
            df = df[(df["empresa_id"] == empresa_id) | (df["empresa_matriz_id"] == empresa_id)]
        if not df.empty:
            export_csv(df, "participantes_export.csv")
        else:
            st.warning("⚠️ No hay participantes para exportar")
    except Exception as e:
        st.error(f"❌ Error exportando participantes: {e}")


# ==================================================
# IMPORTACIÓN
# ==================================================
def importar_participantes(participantes_service, empresas_service, session_state):
    """Importa participantes masivamente desde CSV o Excel."""
    st.markdown("### 📥 Importar Participantes")
    file = st.file_uploader("Sube un archivo CSV o Excel", type=["csv","xlsx"])
    
    if file is not None:
        try:
            if file.name.endswith(".csv"):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            st.write("📊 Vista previa de los datos importados:")
            st.dataframe(df.head(10), use_container_width=True)
            
            if st.button("🚀 Importar ahora"):
                registros = df.to_dict(orient="records")
                ok, errores = participantes_service.importar_participantes_masivo(registros, session_state)
                if ok:
                    st.success("✅ Participantes importados correctamente")
                    st.rerun()
                else:
                    st.error(f"❌ Errores al importar: {errores}")
        except Exception as e:
            st.error(f"❌ Error procesando archivo: {e}")
# ==================================================
# MAIN
# ==================================================
def main(supabase, session_state):
    """Vista principal de Participantes."""
    participantes_service = get_participantes_service(supabase, session_state)
    empresas_service = get_empresas_service(supabase, session_state)
    
    st.title("👥 Gestión de Participantes")
    
    # Tabs según rol
    if session_state.role == "admin":
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Listado", "➕ Nuevo", "📥 Importar", "📤 Exportar"])
    else:
        tab1, tab2, tab3 = st.tabs(["📋 Mis Participantes", "➕ Nuevo", "📥 Importar"])
    
    # =========================
    # TAB 1 - LISTADO
    # =========================
    with tab1:
        try:
            df_participantes = participantes_service.get_participantes_completos()
            
            # Filtro por rol
            if session_state.role == "gestor":
                empresa_id = session_state.user.get("empresa_id")
                df_participantes = df_participantes[
                    (df_participantes["empresa_id"] == empresa_id) |
                    (df_participantes["empresa_matriz_id"] == empresa_id)
                ]
            
            participante_sel = mostrar_tabla_participantes(df_participantes)
            if participante_sel is not None:
                mostrar_formulario_participante(participante_sel, participantes_service, empresas_service, session_state, es_creacion=False)
        except Exception as e:
            st.error(f"❌ Error cargando participantes: {e}")
    
    # =========================
    # TAB 2 - CREAR
    # =========================
    with tab2:
        mostrar_formulario_participante({}, participantes_service, empresas_service, session_state, es_creacion=True)
    
    # =========================
    # TAB 3 - IMPORTAR
    # =========================
    with tab3:
        importar_participantes(participantes_service, empresas_service, session_state)
    
    # =========================
    # TAB 4 - EXPORTAR (solo admin)
    # =========================
    if session_state.role == "admin":
        with tab4:
            exportar_participantes(participantes_service, session_state)
    
    # Expander de ayuda
    with st.expander("ℹ️ Ayuda sobre Participantes"):
        st.markdown("""
        - Cada participante se asocia a **una empresa** (gestora o cliente).  
        - **Gestores** solo pueden gestionar participantes de su empresa y de sus clientes.  
        - El campo **Grupo ID** asigna el participante a un curso/grupo específico.  
        - Puede usar la **importación masiva** para cargar datos desde Excel o CSV.  
        """)
