import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# 1. CONFIGURACIÓN DE PÁGINA (Siempre debe ir primero)
st.set_page_config(page_title="IPTV Tool Pro", page_icon="📺", layout="wide")
st.title("📺 IPTV Tool Web")
st.markdown("Verificador y Descargador con **Buscador Inteligente**.")

# --- FUNCIONES ---

def limpiar_url(url_raw):
    url = url_raw.strip()
    if not url or not url.startswith("http"): return None
    # Forzamos uso de API
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

def obtener_peliculas(url_api, host, user, passw):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_vod_streams"
    try:
        r = requests.get(url, timeout=30)
        data = r.json()
        lista = []
        for item in data:
            ext = item.get('container_extension', 'mp4')
            link = f"{host}/movie/{user}/{passw}/{item['stream_id']}.{ext}"
            lista.append({"Título": item['name'], "Formato": ext, "Link": link})
        return pd.DataFrame(lista)
    except: return None

def obtener_lista_series(url_api, host, user, passw):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_series"
    try:
        r = requests.get(url, timeout=30)
        data = r.json()
        return {item['name']: item['series_id'] for item in data}
    except: return None

def obtener_episodios(host, user, passw, series_id):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_series_info&series_id={series_id}"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
        episodes = data.get('episodes', {})
        lista_episodios = []
        for season_num, eps in episodes.items():
            for ep in eps:
                ext = ep.get('container_extension', 'mp4')
                link = f"{host}/series/{user}/{passw}/{ep['id']}.{ext}"
                nombre_cap = f"T{season_num} E{ep['episode_num']} - {ep['title']}"
                lista_episodios.append({"Episodio": nombre_cap, "Formato": ext, "Link": link})
        return pd.DataFrame(lista_episodios)
    except: return None

# --- INTERFAZ PRINCIPAL ---

# ESTA ES LA LÍNEA QUE FALTABA Y DABA ERROR:
tab1, tab2, tab3 = st.tabs(["🔍 Una Cuenta", "📋 Lista Masiva", "📥 BUSCADOR (Pelis/Series)"])

# Pestaña 1
with tab1:
    u = st.text_input("Enlace:")
    if st.button("Verificar"):
        res = verificar_url(u)
        if res and "Usuario" in res:
            st.success(f"Usuario: {res['Usuario']}")
            c1,c2,c3 = st.columns(3)
            c1.metric("Estado", res["Estado"])
            c2.metric("Vence", res["Vence"])
            c3.metric("Conexiones", res["Conexiones"])
        else: st.error("Error al conectar.")

# Pestaña 2
with tab2:
    txt = st.text_area("Lista:")
    if st.button("Procesar Lista"):
        urls = txt.split('\n')
        res = [verificar_url(x) for x in urls if len(x)>10]
        st.dataframe(pd.DataFrame([r for r in res if r]))

# Pestaña 3 (CON BUSCADOR FILTRADO)
with tab3:
    st.header("Descargas con Filtro")
    link_vod = st.text_input("Pega tu cuenta:", key="vod_input")
    tipo = st.radio("Tipo:", ["🎬 Películas", "📺 Series"], horizontal=True)

    if link_vod:
        url_clean = limpiar_url(link_vod)
        if url_clean:
            host, user, pw = extraer_credenciales(url_clean)

            # LÓGICA PELÍCULAS
            if tipo == "🎬 Películas":
                if st.button("Descargar Catálogo"):
                    with st.spinner("Bajando lista..."):
                        st.session_state['df_pelis'] = obtener_peliculas(url_clean, host, user, pw)
                
                if 'df_pelis' in st.session_state and st.session_state['df_pelis'] is not None:
                    df = st.session_state['df_pelis']
                    # EL BUSCADOR
                    filtro = st.text_input("🔍 Buscar Película:", placeholder="Ej: Batman")
                    
                    if filtro:
                        df_show = df[df['Título'].str.contains(filtro, case=False, na=False)]
                    else:
                        df_show = df

                    st.write(f"Viendo {len(df_show)} resultados:")
                    st.dataframe(df_show, use_container_width=True, hide_index=True,
                                 column_config={"Link": st.column_config.LinkColumn("Bajar", display_text="⬇️ Video")})

            # LÓGICA SERIES
            elif tipo == "📺 Series":
                if 'lista_series' not in st.session_state:
                    if st.button("1️⃣ Cargar Series"):
                        with st.spinner("Leyendo series..."):
                            st.session_state['lista_series'] = obtener_lista_series(url_clean, host, user, pw)
                            st.rerun()
                
                if 'lista_series' in st.session_state:
                    series = list(st.session_state['lista_series'].keys())
                    seleccion = st.selectbox("Selecciona Serie (Escribe para buscar):", series)
                    
                    if st.button(f"2️⃣ Ver caps de: {seleccion}"):
                        sid = st.session_state['lista_series'][seleccion]
                        with st.spinner("Buscando episodios..."):
                            st.session_state['df_eps'] = obtener_episodios(host, user, pw, sid)
                    
                    if 'df_eps' in st.session_state:
                        # Filtro de episodios
                        f_ep = st.text_input("Filtrar episodio:", placeholder="Ej: T1 E1")
                        df_e = st.session_state['df_eps']
                        if f_ep: df_e = df_e[df_e['Episodio'].str.contains(f_ep, case=False)]
                        
                        st.dataframe(df_e, use_container_width=True, hide_index=True,
                                     column_config={"Link": st.column_config.LinkColumn("Bajar", display_text="⬇️ Ver")})
                    
                    if st.button("Borrar todo"):
                        st.session_state.clear()
                        st.rerun()
