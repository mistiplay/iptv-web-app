import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="IPTV Tool Pro", page_icon="📺", layout="wide")
st.title("📺 IPTV Tool Web")
st.markdown("Herramienta Todo en Uno: Verificador, Descargador y **Generador M3U**.")

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

# --- FUNCIONES DE CONTENIDO (VOD) ---

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

# --- FUNCIONES DE CANALES EN VIVO ---

def obtener_canales_live(host, user, passw):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_live_streams"
    try:
        r = requests.get(url, timeout=35)
        return r.json()
    except: return None

def generar_m3u_minimal(canales, host, user, passw):
    # Genera el formato más simple posible para evitar errores en Maxplayer
    contenido = "#EXTM3U\n"
    for c in canales:
        # Limpieza agresiva de nombres
        nombre = c.get('name', 'Canal').replace('"', '').replace(',', ' ').strip()
        sid = c.get('stream_id')
        link = f"{host}/live/{user}/{passw}/{sid}.ts"
        # Formato sin logos ni grupos para máxima compatibilidad
        contenido += f'#EXTINF:-1,{nombre}\n{link}\n'
    return contenido

# --- INTERFAZ PRINCIPAL ---

tab1, tab2, tab3, tab4 = st.tabs(["🔍 Una Cuenta", "📋 Lista Masiva", "📥 Descargas VOD", "🛠️ Generar M3U (Texto/Archivo)"])

# PESTAÑA 1
with tab1:
    u = st.text_input("Enlace:", key="t1_in")
    if st.button("Verificar", key="t1_btn"):
        res = verificar_url(u)
        if res and "Usuario" in res:
            st.success(f"Usuario: {res['Usuario']}")
            c1,c2,c3 = st.columns(3)
            c1.metric("Estado", res["Estado"])
            c2.metric("Vence", res["Vence"])
            c3.metric("Conexiones", res["Conexiones"])
        else: st.error("Error al conectar.")

# PESTAÑA 2
with tab2:
    txt = st.text_area("Lista:")
    if st.button("Procesar Lista"):
        urls = txt.split('\n')
        res = [verificar_url(x) for x in urls if len(x)>10]
        st.dataframe(pd.DataFrame([r for r in res if r]))

# PESTAÑA 3
with tab3:
    st.header("Buscador VOD")
    link_vod = st.text_input("Pega tu cuenta:", key="vod_input")
    tipo = st.radio("Tipo:", ["🎬 Películas", "📺 Series"], horizontal=True)

    if link_vod:
        url_clean = limpiar_url(link_vod)
        if url_clean:
            host, user, pw = extraer_credenciales(url_clean)

            if tipo == "🎬 Películas":
                if st.button("Descargar Catálogo"):
                    with st.spinner("Bajando lista..."):
                        st.session_state['df_pelis'] = obtener_peliculas(url_clean, host, user, pw)
                
                if 'df_pelis' in st.session_state and st.session_state['df_pelis'] is not None:
                    df = st.session_state['df_pelis']
                    filtro = st.text_input("🔍 Buscar:", placeholder="Batman", key="f_peli")
                    df_show = df[df['Título'].str.contains(filtro, case=False, na=False)] if filtro else df
                    st.dataframe(df_show, use_container_width=True, hide_index=True,
                                 column_config={"Link": st.column_config.LinkColumn("Bajar", display_text="⬇️ Video")})

            elif tipo == "📺 Series":
                if 'lista_series' not in st.session_state:
                    if st.button("1️⃣ Cargar Series"):
                        with st.spinner("Leyendo series..."):
                            st.session_state['lista_series'] = obtener_lista_series(url_clean, host, user, pw)
                            st.rerun()
                
                if 'lista_series' in st.session_state:
                    series = list(st.session_state['lista_series'].keys())
                    seleccion = st.selectbox("Serie:", series)
                    if st.button(f"2️⃣ Ver caps de: {seleccion}"):
                        sid = st.session_state['lista_series'][seleccion]
                        with st.spinner("Buscando..."):
                            st.session_state['df_eps'] = obtener_episodios(host, user, pw, sid)
                    
                    if 'df_eps' in st.session_state:
                        st.dataframe(st.session_state['df_eps'], use_container_width=True, hide_index=True,
                                     column_config={"Link": st.column_config.LinkColumn("Bajar", display_text="⬇️ Ver")})
                    if st.button("Limpiar Series"):
                        del st.session_state['lista_series']
                        st.rerun()

# PESTAÑA 4: GENERADOR DE M3U PARA COPIAR
with tab4:
    st.header("🛠️ Crear M3U para Rentry/Maxplayer")
    st.info("1. Carga canales. 2. Selecciónalos. 3. Copia el texto del cuadro negro.")
    
    link_m3u = st.text_input("Pega tu cuenta:", key="m3u_input")
    
    if link_m3u:
        url_c = limpiar_url(link_m3u)
        if url_c:
            host_m, user_m, pw_m = extraer_credenciales(url_c)
            
            # PASO 1: CARGAR
            if st.button("📡 Cargar Canales"):
                with st.spinner("Descargando lista completa..."):
                    st.session_state['todos_canales'] = obtener_canales_live(host_m, user_m, pw_m)
                    
            # PASO 2: SELECCIONAR
            if 'todos_canales' in st.session_state:
                todos = st.session_state['todos_canales']
                mapa = {c['name']: c for c in todos}
                nombres = list(mapa.keys())
                
                st.write("---")
                seleccionados = st.multiselect("Selecciona los canales:", options=nombres)
                
                if seleccionados:
                    st.success(f"Has seleccionado {len(seleccionados)} canales.")
                    
                    objs = [mapa[n] for n in seleccionados]
                    # Generamos el texto limpio
                    contenido_final = generar_m3u_minimal(objs, host_m, user_m, pw_m)
                    
                    st.write("---")
                    st.subheader("📝 Tu Lista M3U Generada")
                    st.write("Haz clic en el icono de **Copiar** (arriba a la derecha del cuadro negro) y pégalo en **rentry.co**.")
                    
                    # AQUÍ ESTÁ EL CUADRO NEGRO CON EL TEXTO
                    st.code(contenido_final, language="text")
                    
                    st.download_button("O descarga el archivo si prefieres", contenido_final, "lista_limpia.m3u")
