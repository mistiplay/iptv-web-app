import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
from urllib.parse import urlparse, parse_qs

st.set_page_config(page_title="IPTV Player con Proxy", page_icon="📺", layout="wide")
st.title("📺 IPTV Web Player (Con Proxy)")
st.markdown("Si el video no carga, activa la casilla de **Proxy** para saltar el bloqueo de seguridad.")

# --- FUNCIONES BÁSICAS ---
def limpiar_url(url_raw):
    url = url_raw.strip()
    if not url or not url.startswith("http"): return None
    return url.replace("/get.php", "/player_api.php").replace("/xmltv.php", "/player_api.php")

def extraer_credenciales(url_api):
    try:
        parsed = urlparse(url_api)
        host = f"{parsed.scheme}://{parsed.netloc}"
        params = parse_qs(parsed.query)
        username = params.get('username', [''])[0]
        password = params.get('password', [''])[0]
        if not username or not password: return None, None, None
        return host, username, password
    except: return None, None, None

@st.cache_data(ttl=600)
def obtener_lista_canales(host, user, passw):
    try:
        # Descargamos canales
        url = f"{host}/player_api.php?username={user}&password={passw}&action=get_live_streams"
        data = requests.get(url, timeout=30).json()
        
        # Descargamos categorias para poner nombres bonitos
        cats = requests.get(f"{host}/player_api.php?username={user}&password={passw}&action=get_live_categories").json()
        mapa_cats = {c['category_id']: c['category_name'] for c in cats}
        
        lista_final = []
        for c in data:
            cat_id = c.get('category_id')
            stream_id = c.get('stream_id')
            # Generamos enlace M3U8 (mejor para web)
            link = f"{host}/live/{user}/{passw}/{stream_id}.m3u8"
            
            lista_final.append({
                "Nombre": c.get('name'),
                "Categoria": mapa_cats.get(cat_id, "Otras"),
                "Link": link
            })
        return pd.DataFrame(lista_final)
    except: return None

# --- REPRODUCTOR CON LÓGICA DE PROXY ---
def reproductor_clappr(url_video, activar_proxy):
    
    url_final = url_video
    
    # AQUÍ ESTÁ LA MAGIA DEL PROXY
    if activar_proxy:
        # Usamos corsproxy.io, que es gratuito y soporta video
        url_final = f"https://corsproxy.io/?{url_video}"
    
    html = f"""
    <html>
    <head>
        <script type="text/javascript" src="https://cdn.jsdelivr.net/npm/clappr@latest/dist/clappr.min.js"></script>
        <style>body {{ margin:0; background:black; }} #player {{ width:100%; height:400px; }}</style>
    </head>
    <body>
        <div id="player"></div>
        <script>
            var player = new Clappr.Player({{
                source: "{url_final}",
                parentId: "#player",
                width: '100%',
                height: '100%',
                autoPlay: true,
            }});
        </script>
    </body>
    </html>
    """
    components.html(html, height=400)
    return url_final

# --- INTERFAZ ---

link = st.text_input("Pega tu cuenta (M3U o enlace API):")

if link:
    url_c = limpiar_url(link)
    if url_c:
        host, user, pw = extraer_credenciales(url_c)
        
        if 'df_tv' not in st.session_state:
            if st.button("📡 Cargar Canales"):
                with st.spinner("Bajando lista..."):
                    st.session_state['df_tv'] = obtener_lista_canales(host, user, pw)

        if 'df_tv' in st.session_state:
            df = st.session_state['df_tv']
            
            # FILTROS
            col1, col2 = st.columns(2)
            with col1:
                cats = sorted(df['Categoria'].unique())
                cat_sel = st.selectbox("Carpeta:", cats)
            with col2:
                # Filtramos canales de esa carpeta
                canales_filtrados = df[df['Categoria'] == cat_sel]
                canal_sel = st.selectbox("Canal:", canales_filtrados['Nombre'].tolist())
            
            # OBTENER LINK DEL CANAL ELEGIDO
            row = canales_filtrados[canales_filtrados['Nombre'] == canal_sel].iloc[0]
            link_original = row['Link']
            
            st.write("---")
            
            # === ZONA DEL REPRODUCTOR ===
            st.subheader(f"Viendos: {canal_sel}")
            
            # EL INTERRUPTOR QUE SOLUCIONA TODO
            usa_proxy = st.checkbox("🔄 Activar Proxy de Corrección (Úsalo si la pantalla se queda negra)", value=True)
            
            # Llamamos al reproductor
            url_usada = reproductor_clappr(link_original, usa_proxy)
            
            st.caption(f"Reproduciendo desde: `{url_usada}`")
            
            if usa_proxy:
                st.info("ℹ️ Estás usando un 'puente' seguro para evitar el bloqueo del navegador.")
