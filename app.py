import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="IPTV Checker Pro", page_icon="📺", layout="centered")

st.title("📺 IPTV Checker Web")
st.markdown("Verificador de estado **sin bloqueos** para móvil y PC.")

# Función de verificación (La misma de tu Python)
def verificar_url(url_raw):
    url = url_raw.strip()
    if not url or not url.startswith("http"):
        return None

    # Corrección automática
    url_final = url.replace("/get.php", "/player_api.php").replace("/xmltv.php", "/player_api.php")
    
    try:
        # Usamos requests igual que en tu PC
        response = requests.get(url_final, timeout=10)
        
        if response.status_code != 200:
            return {"Usuario": "Error HTTP", "Estado": f"Error {response.status_code}", "Vence": "-", "Conexiones": "-"}

        data = response.json()
        
        if 'user_info' not in data:
            return {"Usuario": "Invalido", "Estado": "No es panel", "Vence": "-", "Conexiones": "-"}

        info = data['user_info']
        
        # Procesar fecha
        timestamp = info.get('exp_date')
        if timestamp and timestamp != 'null':
            fecha = datetime.fromtimestamp(int(timestamp)).strftime('%d/%m/%Y')
        else:
            fecha = "Ilimitada"

        return {
            "Usuario": info.get('username', 'Desconocido'),
            "Estado": "✅ Activa" if info.get('status') == 'Active' else f"❌ {info.get('status')}",
            "Vence": fecha,
            "Conexiones": f"{info.get('active_cons', 0)} / {info.get('max_connections', 0)}"
        }

    except Exception as e:
        return {"Usuario": "Error", "Estado": "Caído/Timeout", "Vence": "-", "Conexiones": "-"}

# --- INTERFAZ ---

# Pestañas para elegir modo
tab1, tab2 = st.tabs(["🔍 Una sola cuenta", "📋 Lista Masiva"])

with tab1:
    url_input = st.text_input("Pega el enlace completo aquí:")
    if st.button("Verificar Cuenta", type="primary"):
        if url_input:
            with st.spinner('Conectando con el servidor...'):
                resultado = verificar_url(url_input)
                if resultado:
                    # Mostrar resultados bonitos
                    if "Activa" in resultado["Estado"]:
                        st.success(f"**Usuario:** {resultado['Usuario']}")
                    else:
                        st.error(f"**Usuario:** {resultado['Usuario']}")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Estado", resultado["Estado"])
                    c2.metric("Vencimiento", resultado["Vence"])
                    c3.metric("Conexiones", resultado["Conexiones"])
                else:
                    st.warning("Enlace no válido.")

with tab2:
    st.write("Pega muchas cuentas (una por línea):")
    text_area = st.text_area("Lista de URLs", height=150)
    
    if st.button("Verificar Lista Masiva"):
        if text_area:
            urls = text_area.split('\n')
            resultados = []
            progress_bar = st.progress(0)
            
            for i, linea in enumerate(urls):
                if len(linea) > 5:
                    res = verificar_url(linea)
                    if res:
                        resultados.append(res)
                progress_bar.progress((i + 1) / len(urls))
            
            if resultados:
                df = pd.DataFrame(resultados)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No se encontraron enlaces válidos.")