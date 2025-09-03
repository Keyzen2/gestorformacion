import os

# Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# FUNDAE XSD
FUNDAE_XSD = {
    "accion_formativa": "https://empresas.fundae.es/Lanzadera/Content/schemas/2025/AAFF_Inicio.xsd",
    "inicio_grupo": "https://empresas.fundae.es/Lanzadera/Content/schemas/2025/AAFF_Inicio.xsd",
    "finalizacion_grupo": "https://empresas.fundae.es/Lanzadera/Content/schemas/2025/FinalizacionGrupo_Bonificada.xsd"
}
