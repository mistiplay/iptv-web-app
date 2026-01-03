import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# CONFIGURACIÓN
st.set_page_config(page_title="IPTV Tool Lite", page_icon="📺", layout="wide")
st.title("📺 IPTV Tool Web")
st.markdown("Herramientas de Gestión: **Verificador y Buscador VOD**.")

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

# --- FUNCIONES DE VOD (PELÍCULAS Y SERIES) ---

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
        # Retornamos diccionario Nombre -> ID
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

# --- INTERFAZ ---

tab1, tab2, tab3 = st.tabs(["🔍 Una Cuenta", "📋 Lista Masiva", "📥 Buscador VOD"])

# PESTAÑA 1: VERIFICADOR SIMPLE
with tab1:
    st.header("Verificar Estado de Cuenta")
    u = st.text_input("Enlace (M3U o Xtream):", key="t1_input")
    if st.button("Verificar Cuenta", key="t1_btn"):
        res = verificar_url(u)
        if res and "Usuario" in res:
            st.success(f"Usuario: {res['Usuario']}")
            c1,c2,c3 = st.columns(3)
            c1.metric("Estado", res["Estado"])
            c2.metric("Vence", res["Vence"])
            c3.metric("Conexiones", res["Conexiones"])
        else: st.error("Error: No se pudo conectar o la cuenta no existe.")

# PESTAÑA 2: VERIFICADOR MASIVO
with tab2:
    st.header("Verificador Masivo")
    st.caption("Pega una lista de enlaces (uno por línea) para chequearlos todos.")
    txt = st.text_area("Lista de enlaces:", height=200)
    
    if st.button("Procesar Lista"):
        urls = txt.split('\n')
        # Filtramos líneas vacías o muy cortas
        validos = [x.strip() for x in urls if len(x) > 10]
        
        if not validos:
            st.warning("No se detectaron enlaces válidos.")
        else:
            progreso = st.progress(0)
            resultados = []
            
            for i, link in enumerate(validos):
                res = verificar_url(link)
                if res:
                    resultados.append(res)
                progreso.progress((i + 1) / len(validos))
            
            if resultados:
                st.dataframe(pd.DataFrame(resultados), use_container_width=True)
            else:
                st.error("Ningún enlace funcionó.")

# PESTAÑA 3: BUSCADOR VOD (PELIS Y SERIES)
with tab3:
    st.header("Buscador de Contenido (VOD)")
    st.info("Busca Películas o Series específicas y obtén sus enlaces directos.")
    
    link_vod = st.text_input("Pega tu cuenta:", key="vod_input")
    tipo_contenido = st.radio("¿Qué buscas?", ["🎬 Películas", "📺 Series"], horizontal=True)

    if link_vod:
        url_clean = limpiar_url(link_vod)
        if url_clean:
            host, user, pw = extraer_credenciales(url_clean)

            # --- OPCIÓN PELÍCULAS ---
            if tipo_contenido == "🎬 Películas":
                if st.button("1. Descargar Catálogo de Películas"):
                    with st.spinner("Descargando lista de películas..."):
                        st.session_state['df_pelis'] = obtener_peliculas(host, user, pw)
                
                if 'df_pelis' in st.session_state and st.session_state['df_pelis'] is not None:
                    df = st.session_state['df_pelis']
                    filtro = st.text_input("🔍 Buscar por nombre:", placeholder="Ej: Mario Bros")
                    
                    if filtro:
                        df_show = df[df['Título'].str.contains(filtro, case=False, na=False)]
                    else:
                        df_show = df.head(100) # Mostrar solo las primeras 100 si no hay filtro

                    st.dataframe(
                        df_show, 
                        use_container_width=True, 
                        hide_index=True,
                        column_config={
                            "Link": st.column_config.LinkColumn("Enlace", display_text="⬇️ Abrir/Descargar")
                        }
                    )

            # --- OPCIÓN SERIES ---
            elif tipo_contenido == "📺 Series":
                if 'lista_series' not in st.session_state:
                    if st.button("1. Cargar Lista de Series"):
                        with st.spinner("Descargando lista de series..."):
                            st.session_state['lista_series'] = obtener_lista_series(host, user, pw)
                            st.rerun()
                
                if 'lista_series' in st.session_state:
                    series_dict = st.session_state['lista_series']
                    nombres_series = list(series_dict.keys())
                    
                    seleccion = st.selectbox("2. Selecciona la Serie:", nombres_series)
                    
                    if st.button(f"Ver Episodios de: {seleccion}"):
                        sid = series_dict[seleccion]
                        with st.spinner("Obteniendo episodios..."):
                            st.session_state['df_episodios'] = obtener_episodios(host, user, pw, sid)
                    
                    if 'df_episodios' in st.session_state and st.session_state['df_episodios'] is not None:
                        st.dataframe(
                            st.session_state['df_episodios'], 
                            use_container_width=True, 
                            hide_index=True,
                            column_config={
                                "Link": st.column_config.LinkColumn("Enlace", display_text="⬇️ Abrir/Descargar")
                            }
                        )
                    
                    if st.button("🔄 Nueva Búsqueda"):
                        del st.session_state['lista_series']
                        st.rerun()
