import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# CONFIGURACIÓN
st.set_page_config(page_title="IPTV Tool Clappr", page_icon="📺", layout="wide")
st.title("📺 IPTV Tool Web")
st.markdown("Herramientas: Verificador + Buscador VOD + **Auditoría con Clappr**.")

# --- FUNCIONES DE UTILIDAD ---

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

def verificar_url(url_raw):
    url_final = limpiar_url(url_raw)
    if not url_final: return None
    try:
        response = requests.get(url_final, timeout=10)
        if response.status_code != 200: return {"Estado": "Error HTTP"}
        data = response.json()
        if 'user_info' not in data: return {"Estado": "No es panel"}
        info = data['user_info']
        ts = info.get('exp_date')
        fecha = datetime.fromtimestamp(int(ts)).strftime('%d/%m/%Y') if ts and ts != 'null' else "Ilimitada"
        return {
            "Usuario": info.get('username'),
            "Estado": "✅ Activa" if info.get('status') == 'Active' else "❌ Inactiva",
            "Vence": fecha,
            "Conexiones": f"{info.get('active_cons')}/{info.get('max_connections')}"
        }
    except: return {"Estado": "Error"}

# --- FUNCIONES DE VOD ---
def obtener_peliculas(host, user, passw):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_vod_streams"
    try:
        r = requests.get(url, timeout=25)
        data = r.json()
        if not isinstance(data, list): return None
        lista = []
        for item in data:
            ext = item.get('container_extension', 'mp4')
            link = f"{host}/movie/{user}/{passw}/{item['stream_id']}.{ext}"
            lista.append({"Título": item['name'], "Formato": ext, "Link": link})
        return pd.DataFrame(lista)
    except: return None

def obtener_lista_series(host, user, passw):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_series"
    try:
        r = requests.get(url, timeout=25)
        data = r.json()
        if not isinstance(data, list): return None
        return {item['name']: item['series_id'] for item in data}
    except: return None

def obtener_episodios(host, user, passw, series_id):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_series_info&series_id={series_id}"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
        episodes = data.get('episodes', {})
        lista_episodios = []
        if isinstance(episodes, dict):
            for season_num, eps in episodes.items():
                for ep in eps:
                    ext = ep.get('container_extension', 'mp4')
                    link = f"{host}/series/{user}/{passw}/{ep['id']}.{ext}"
                    nombre_cap = f"T{season_num} E{ep['episode_num']} - {ep['title']}"
                    lista_episodios.append({"Episodio": nombre_cap, "Formato": ext, "Link": link})
            return pd.DataFrame(lista_episodios)
        return None
    except: return None

# --- FUNCIONES PESTAÑA 4 ---
@st.cache_data(ttl=600)
def obtener_mapa_canales(host, user, passw):
    try:
        cats_req = requests.get(f"{host}/player_api.php?username={user}&password={passw}&action=get_live_categories", timeout=20)
        cats_data = cats_req.json()
        mapa_carpetas = {c['category_id']: c['category_name'] for c in cats_data}

        live_req = requests.get(f"{host}/player_api.php?username={user}&password={passw}&action=get_live_streams", timeout=30)
        live_data = live_req.json()

        lista_final = []
        for canal in live_data:
            cat_id = canal.get('category_id')
            nombre_carpeta = mapa_carpetas.get(cat_id, "Sin Categoría / Oculto")
            stream_id = canal.get('stream_id')
            
            # Generamos link M3U8 para Clappr
            link_m3u8 = f"{host}/live/{user}/{passw}/{stream_id}.m3u8"
            link_ts = f"{host}/live/{user}/{passw}/{stream_id}.ts"
            
            lista_final.append({
                "Nombre del Canal": canal.get('name'),
                "📂 Carpeta (Ubicación)": nombre_carpeta,
                "ID": stream_id,
                "Link M3U8": link_m3u8,
                "Link TS": link_ts
            })
            
        return pd.DataFrame(lista_final)
    except: return None

# --- EL REPRODUCTOR CLAPPR (ESTILO FUTBOL LIBRE) ---
def reproductor_clappr(url_stream):
    """
    Implementa Clappr Player, el mismo motor que usan páginas como FutbolLibre.
    """
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script type="text/javascript" src="https://cdn.jsdelivr.net/npm/clappr@latest/dist/clappr.min.js"></script>
        <style>
            body {{ margin: 0; background-color: black; display: flex; justify-content: center; align-items: center; height: 400px; }}
            #player {{ width: 100%; height: 100%; }}
        </style>
    </head>
    <body>
        <div id="player"></div>
        <script>
            var player = new Clappr.Player({{
                source: "{url_stream}",
                parentId: "#player",
                width: '100%',
                height: '100%',
                autoPlay: true,
                playback: {{
                    playInline: true,
                    recycleVideo: true,
                }}
            }});
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=400)

# --- INTERFAZ ---

tab1, tab2, tab3, tab4 = st.tabs(["🔍 Una Cuenta", "📋 Lista Masiva", "📥 Buscador VOD", "🔎 AUDITOR DE CANALES"])

# TABS 1, 2, 3 (Iguales)
with tab1:
    st.header("Verificar Estado")
    u = st.text_input("Enlace:", key="t1_in")
    if st.button("Verificar"):
        res = verificar_url(u)
        if res and "Usuario" in res:
            st.success(f"Usuario: {res['Usuario']}")
            c1,c2,c3 = st.columns(3)
            c1.metric("Estado", res["Estado"])
            c2.metric("Vence", res["Vence"])
            c3.metric("Conexiones", res["Conexiones"])
        else: st.error("Error.")

with tab2:
    st.header("Verificador Masivo")
    txt = st.text_area("Lista de enlaces:")
    if st.button("Procesar"):
        urls = txt.split('\n')
        res = [verificar_url(x) for x in urls if len(x)>10]
        st.dataframe(pd.DataFrame([r for r in res if r]))

with tab3:
    st.header("Buscador VOD (Pelis/Series)")
    l_vod = st.text_input("Cuenta:", key="tvod")
    t_vod = st.radio("Tipo:", ["🎬 Películas", "📺 Series"], horizontal=True)
    if l_vod:
        h, u_c, p_c = extraer_credenciales(l_vod)
        if h:
            if t_vod == "🎬 Películas":
                if st.button("Buscar Pelis"):
                    st.session_state['df_p'] = obtener_peliculas(h, u_c, p_c)
                if 'df_p' in st.session_state and st.session_state['df_p'] is not None:
                    df = st.session_state['df_p']
                    filt = st.text_input("Nombre:", key="fp")
                    if filt: df = df[df['Título'].str.contains(filt, case=False, na=False)]
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                if st.button("Cargar Series"):
                    st.session_state['ls'] = obtener_lista_series(h, u_c, p_c)
                    st.rerun()
                if 'ls' in st.session_state:
                    sel = st.selectbox("Serie:", list(st.session_state['ls'].keys()))
                    if st.button("Ver Caps"):
                        st.dataframe(obtener_episodios(h, u_c, p_c, st.session_state['ls'][sel]), use_container_width=True)

# --- PESTAÑA 4 CON CLAPPR ---
with tab4:
    st.header("🔎 Buscador de Canales (con Clappr)")
    st.info("Usa el motor de reproducción Clappr (el mismo de las webs de fútbol).")
    
    link_search = st.text_input("Pega tu cuenta:", key="t4_input")
    
    if link_search:
        url_c = limpiar_url(link_search)
        if url_c:
            host, user, pw = extraer_credenciales(url_c)
            
            if 'df_canales' not in st.session_state:
                if st.button("📡 Cargar Lista de Canales"):
                    with st.spinner("Analizando lista..."):
                        df = obtener_mapa_canales(host, user, pw)
                        if df is not None:
                            st.session_state['df_canales'] = df
                            st.rerun()
                        else: st.error("Error de carga.")

            if 'df_canales' in st.session_state:
                df = st.session_state['df_canales']
                
                # 1. BUSCADOR
                busqueda = st.text_input("🔍 Buscar Canal (Ej: ESPN, Peru...):", placeholder="Escribe aquí...")
                
                resultados = df
                if busqueda:
                    resultados = df[df['Nombre del Canal'].str.contains(busqueda, case=False, na=False)]
                
                st.caption(f"Encontrados: {len(resultados)}")
                st.dataframe(
                    resultados[['Nombre del Canal', '📂 Carpeta (Ubicación)']],
                    use_container_width=True,
                    hide_index=True
                )
                
                st.write("---")
                
                # 2. REPRODUCTOR CLAPPR
                st.subheader("▶️ Reproductor en Vivo")
                
                lista_nombres = resultados['Nombre del Canal'].tolist()
                
                if lista_nombres:
                    seleccion = st.selectbox("📺 Selecciona para reproducir:", lista_nombres)
                    
                    if seleccion:
                        row = df[df['Nombre del Canal'] == seleccion].iloc[0]
                        link_m3u8 = row['Link M3U8']
                        carpeta = row['📂 Carpeta (Ubicación)']
                        
                        st.success(f"Cargando: **{seleccion}** | {carpeta}")
                        
                        # LLAMADA A CLAPPR
                        reproductor_clappr(link_m3u8)
                        
                        st.info("⚠️ Si no carga: Dale clic al candado 🔒 en la barra de direcciones del navegador y selecciona 'Configuración del sitio' -> 'Contenido inseguro' -> 'Permitir'.")
                else:
                    st.warning("No hay canales en la lista actual.")

                st.write("---")
                if st.button("🔄 Nueva Carga"):
                    del st.session_state['df_canales']
                    st.rerun()
