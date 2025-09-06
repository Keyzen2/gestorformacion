import streamlit as st
import pandas as pd
from datetime import date

def main(supabase, session_state):
    st.markdown("## 📊 Panel RGPD")
    st.caption("Resumen visual del cumplimiento RGPD de tu empresa.")
    st.divider()

    empresa_id = session_state.user.get("empresa_id")
    if not empresa_id:
        st.warning("No se ha detectado tu empresa.")
        st.stop()

    def semaforo(valor, total):
        if total == 0:
            return "⚪"
        if valor == total:
            return "🟢"
        elif valor >= total // 2:
            return "🟡"
        else:
            return "🔴"

    # Diagnóstico inicial
    try:
        diag = supabase.table("rgpd_diagnostico").select("*").eq("empresa_id", empresa_id).execute().data[0]
        cumplidos = sum([
            diag["registro_tratamiento"],
            diag["clausulas"],
            diag["encargados"],
            diag["derechos"],
            diag["seguridad"],
            diag["canal_brechas"]
        ])
        st.markdown(f"### 📋 Diagnóstico inicial: {semaforo(cumplidos, 6)}")
        st.write(f"{cumplidos}/6 elementos cumplidos")
        st.link_button("Ir al diagnóstico", "rgpd_inicio")
    except:
        st.markdown("### 📋 Diagnóstico inicial: 🔴")
        st.write("No se ha realizado el diagnóstico.")
        st.link_button("Ir al diagnóstico", "rgpd_inicio")

    # Tratamientos registrados
    try:
        tratamientos = supabase.table("rgpd_tratamientos").select("id").eq("empresa_id", empresa_id).execute().data or []
        st.markdown(f"### 📘 Tratamientos registrados: {semaforo(len(tratamientos), 1)}")
        st.write(f"{len(tratamientos)} tratamiento(s) documentado(s)")
        st.link_button("Ir a tratamientos", "rgpd_tratamientos")
    except:
        st.markdown("### 📘 Tratamientos registrados: 🔴")
        st.link_button("Ir a tratamientos", "rgpd_tratamientos")

    # Cláusulas registradas
    try:
        clausulas = supabase.table("rgpd_clausulas").select("id").eq("empresa_id", empresa_id).execute().data or []
        st.markdown(f"### 📄 Cláusulas registradas: {semaforo(len(clausulas), 1)}")
        st.write(f"{len(clausulas)} cláusula(s) registrada(s)")
        st.link_button("Ir a cláusulas", "rgpd_consentimientos")
    except:
        st.markdown("### 📄 Cláusulas registradas: 🔴")
        st.link_button("Ir a cláusulas", "rgpd_consentimientos")

    # Encargados registrados
    try:
        encargados = supabase.table("rgpd_encargados").select("id").eq("empresa_id", empresa_id).execute().data or []
        st.markdown(f"### 🤝 Encargados registrados: {semaforo(len(encargados), 1)}")
        st.write(f"{len(encargados)} proveedor(es) registrado(s)")
        st.link_button("Ir a encargados", "rgpd_encargados")
    except:
        st.markdown("### 🤝 Encargados registrados: 🔴")
        st.link_button("Ir a encargados", "rgpd_encargados")

    # Derechos gestionados
    try:
        derechos = supabase.table("rgpd_derechos").select("id").eq("empresa_id", empresa_id).execute().data or []
        pendientes = [d for d in derechos if d["estado"] in ["Pendiente", "En proceso"]]
        st.markdown(f"### 🧑‍⚖️ Solicitudes ARCO: {semaforo(len(derechos) - len(pendientes), len(derechos))}")
        st.write(f"{len(derechos)} solicitud(es), {len(pendientes)} pendiente(s)")
        st.link_button("Ir a derechos", "rgpd_derechos")
    except:
        st.markdown("### 🧑‍⚖️ Solicitudes ARCO: 🔴")
        st.link_button("Ir a derechos", "rgpd_derechos")

    # Evaluación de impacto
    try:
        eval = supabase.table("rgpd_evaluacion").select("*").eq("empresa_id", empresa_id).execute().data[0]
        criterios = sum([
            eval["datos_sensibles"],
            eval["seguimiento"],
            eval["gran_escala"],
            eval["tecnologia"],
            eval["perfiles"],
            eval["menores"]
        ])
        st.markdown(f"### 🧠 Evaluación de Impacto: {semaforo(criterios, 2)}")
        st.write(f"{criterios} criterio(s) marcados")
        st.link_button("Ir a evaluación", "rgpd_evaluacion")
    except:
        st.markdown("### 🧠 Evaluación de Impacto: 🔴")
        st.link_button("Ir a evaluación", "rgpd_evaluacion")

    # Medidas de seguridad
    try:
        medidas = supabase.table("rgpd_medidas").select("*").eq("empresa_id", empresa_id).execute().data[0]
        aplicadas = sum([
            medidas["cifrado"],
            medidas["backups"],
            medidas["acceso"],
            medidas["antivirus"],
            medidas["formacion"],
            medidas["registro"]
        ])
        st.markdown(f"### 🔐 Medidas de seguridad: {semaforo(aplicadas, 6)}")
        st.write(f"{aplicadas}/6 medidas aplicadas")
        st.link_button("Ir a medidas", "rgpd_medidas")
    except:
        st.markdown("### 🔐 Medidas de seguridad: 🔴")
        st.link_button("Ir a medidas", "rgpd_medidas")

    # Incidencias registradas
    try:
        incidencias = supabase.table("rgpd_incidencias").select("*").eq("empresa_id", empresa_id).execute().data or []
        sin_resolver = [i for i in incidencias if i["estado"] in ["Detectado", "Investigando"]]
        st.markdown(f"### 🚨 Incidencias registradas: {semaforo(len(incidencias) - len(sin_resolver), len(incidencias))}")
        st.write(f"{len(incidencias)} incidencia(s), {len(sin_resolver)} sin resolver")
        st.link_button("Ir a incidencias", "rgpd_incidencias")
    except:
        st.markdown("### 🚨 Incidencias registradas: 🔴")
        st.link_button("Ir a incidencias", "rgpd_incidencias")

    # NUEVO BLOQUE: Planner de tareas RGPD
    try:
        tareas = supabase.table("rgpd_tareas").select("*").eq("empresa_id", empresa_id).execute().data or []
        total_tareas = len(tareas)
        pendientes_t = [t for t in tareas if t["estado"] == "Pendiente"]
        en_curso_t = [t for t in tareas if t["estado"] == "En curso"]
        completadas_t = [t for t in tareas if t["estado"] == "Completada"]
        vencidas_t = [t for t in tareas if t.get("fecha_limite") and pd.to_datetime(t["fecha_limite"]).date() < date.today() and t["estado"] != "Completada"]

        st.markdown(f"### 🗂️ Planner de tareas RGPD: {semaforo(len(completadas_t), total_tareas)}")
        st.write(f"**Total:** {total_tareas} | **Pendientes:** {len(pendientes_t)} | **En curso:** {len(en_curso_t)} | **Completadas:** {len(completadas_t)}")
        if vencidas_t:
            st.error(f"⚠️ {len(vencidas_t)} tarea(s) vencida(s) sin completar")
        st.link_button("Ir al planner", "rgpd_planner")
    except Exception as e:
        st.markdown("### 🗂️ Planner de tareas RGPD: 🔴")
        st.write("No se pudieron cargar las tareas.")
        st.link_button("Ir al planner", "rgpd_planner")

    st.divider()
    st.caption("Este panel se actualiza automáticamente cada vez que accedes.")
    
