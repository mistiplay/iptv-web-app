import streamlit as st
import requests
import pandas as pd
import concurrent.futures
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# CONFIGURACIÓN
st.set_page_config(page_title="IPTV Tool Pro", page_icon="📺", layout="wide")
st.title("📺 IPTV Tool Web")
st.markdown("Verificador + Descargador Individual + **Creador M3U**.")

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

# --- FUNCIONES PARA PESTAÑA 3 (INDIVIDUAL) ---
def obtener_peliculas_tab3(host, user, passw):
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

def obtener_lista_series_tab3(host, user, passw):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_series"
    try:
        r = requests.get(url, timeout=30)
        data = r.json()
        return {item['name']: item['series_id'] for item in data}
    except: return None

def obtener_episodios_tab3(host, user, passw, series_id):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_series_info&series_id={series_id}"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
        episodes = data.get('episodes', {})
        lista_episodios = []
        # Verificación extra para evitar el error aquí también
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

# --- FUNCIONES PARA PESTAÑA 4 (MASIVA) ---

@st.cache_data(ttl=600)
def obtener_datos_completos(host, user, passw):
    """Descarga Canales, Categorías, Pelis y Series de una vez."""
    data = {}
    try:
        data['live'] = requests.get(f"{host}/player_api.php?username={user}&password={passw}&action=get_live_streams", timeout=30).json()
        data['cats_live'] = requests.get(f"{host}/player_api.php?username={user}&password={passw}&action=get_live_categories", timeout=30).json()
        data['vod'] = requests.get(f"{host}/player_api.php?username={user}&password={passw}&action=get_vod_streams", timeout=30).json()
        data['series'] = requests.get(f"{host}/player_api.php?username={user}&password={passw}&action=get_series", timeout=30).json()
    except: return None
    return data

def obtener_episodios_serie_individual(args):
    host, user, passw, series_id = args
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_series_info&series_id={series_id}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json().get('episodes', {})
    except: pass
    return {}

def generar_m3u_final(items_live, items_vod, items_episodios, host, user, passw):
    contenido = "#EXTM3U\r\n"
    
    # 1. CANALES
    for c in items_live:
        nombre = c.get('name', '').replace('"', '').replace(',', ' ').strip()
        cat_name = c.get('category_name', 'General').replace('"', '')
        sid = c.get('stream_id')
        link = f"{host}/live/{user}/{passw}/{sid}.ts"
        contenido += f'#EXTINF:-1 group-title="{cat_name}",{nombre}\r\n{link}\r\n'

    # 2. PELÍCULAS
    for p in items_vod:
        nombre = p.get('name', '').replace('"', '').replace(',', ' ').strip()
        sid = p.get('stream_id')
        ext = p.get('container_extension', 'mp4')
        link = f"{host}/movie/{user}/{passw}/{sid}.{ext}"
        contenido += f'#EXTINF:-1 group-title="Peliculas",{nombre}\r\n{link}\r\n'

    # 3. SERIES
    for s in items_episodios:
        nombre = s['name'].replace('"', '').replace(',', ' ').strip()
        link = s['link']
        contenido += f'#EXTINF:-1 group-title="Series",{nombre}\r\n{link}\r\n'

    return contenido

# --- INTERFAZ ---

tab1, tab2, tab3, tab4 = st.tabs(["🔍 Una Cuenta", "📋 Lista Masiva", "📥 Descargas Individuales", "🛠️ Creador M3U (Completo)"])

# PESTAÑA 1: VERIFICAR
with tab1:
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

# PESTAÑA 2: MASIVA
with tab2:
    txt = st.text_area("Lista:")
    if st.button("Procesar"):
        urls = txt.split('\n')
        res = [verificar_url(x) for x in urls if len(x)>10]
        st.dataframe(pd.DataFrame([r for r in res if r]))

# PESTAÑA 3: DESCARGAS INDIVIDUALES (RESTAURADA)
with tab3:
    st.header("Descargas VOD (Películas y Series)")
    link_vod = st.text_input("Pega tu cuenta:", key="vod_input_t3")
    tipo = st.radio("Tipo:", ["🎬 Películas", "📺 Series"], horizontal=True, key="radio_t3")

    if link_vod:
        url_clean = limpiar_url(link_vod)
        if url_clean:
            host, user, pw = extraer_credenciales(url_clean)

            # LÓGICA PELÍCULAS T3
            if tipo == "🎬 Películas":
                if st.button("Descargar Catálogo Pelis"):
                    with st.spinner("Bajando lista..."):
                        st.session_state['df_pelis_t3'] = obtener_peliculas_tab3(host, user, pw)
                
                if 'df_pelis_t3' in st.session_state and st.session_state['df_pelis_t3'] is not None:
                    df = st.session_state['df_pelis_t3']
                    filtro = st.text_input("🔍 Buscar Película:", placeholder="Ej: Batman", key="f_peli_t3")
                    
                    if filtro:
                        df_show = df[df['Título'].str.contains(filtro, case=False, na=False)]
                    else:
                        df_show = df

                    st.dataframe(df_show, use_container_width=True, hide_index=True,
                                 column_config={"Link": st.column_config.LinkColumn("Bajar", display_text="⬇️ Video")})

            # LÓGICA SERIES T3
            elif tipo == "📺 Series":
                if 'lista_series_t3' not in st.session_state:
                    if st.button("1️⃣ Cargar Series"):
                        with st.spinner("Leyendo series..."):
                            st.session_state['lista_series_t3'] = obtener_lista_series_tab3(host, user, pw)
                            st.rerun()
                
                if 'lista_series_t3' in st.session_state:
                    series = list(st.session_state['lista_series_t3'].keys())
                    seleccion = st.selectbox("Selecciona Serie (Escribe para buscar):", series, key="sel_serie_t3")
                    
                    if st.button(f"2️⃣ Ver caps de: {seleccion}"):
                        sid = st.session_state['lista_series_t3'][seleccion]
                        with st.spinner("Buscando episodios..."):
                            st.session_state['df_eps_t3'] = obtener_episodios_tab3(host, user, pw, sid)
                    
                    if 'df_eps_t3' in st.session_state and st.session_state['df_eps_t3'] is not None:
                        st.dataframe(st.session_state['df_eps_t3'], use_container_width=True, hide_index=True,
                                     column_config={"Link": st.column_config.LinkColumn("Bajar", display_text="⬇️ Ver")})
                    
                    if st.button("🔄 Nueva Búsqueda"):
                        del st.session_state['lista_series_t3']
                        st.rerun()

# PESTAÑA 4: CREADOR M3U MEJORADO (CON CORRECCIÓN DE ERROR)
with tab4:
    st.header("🛠️ Creador de Listas M3U")
    st.info("Elige tus carpetas de canales. Películas y Series se añaden automáticas.")
    
    link_m3u = st.text_input("Pega tu cuenta:", key="m3u_input_t4")
    
    if 'mis_canales' not in st.session_state: st.session_state['mis_canales'] = []

    if link_m3u:
        url_c = limpiar_url(link_m3u)
        if url_c:
            host_m, user_m, pw_m = extraer_credenciales(url_c)
            
            # 1. CARGA DE DATOS
            if st.button("📡 Cargar Datos"):
                with st.spinner("Conectando..."):
                    datos = obtener_datos_completos(host_m, user_m, pw_m)
                    if datos and datos.get('live'):
                        st.session_state['datos_full'] = datos
                        # Mapa categorías
                        cats_raw = datos.get('cats_live', [])
                        mapa_cats = {c['category_id']: c['category_name'] for c in cats_raw}
                        st.session_state['mapa_cats'] = mapa_cats
                        st.success("¡Datos cargados!")
                    else: st.error("Fallo al cargar.")

            # 2. SELECTOR
            if 'datos_full' in st.session_state:
                live_data = st.session_state['datos_full']['live']
                mapa_cats = st.session_state.get('mapa_cats', {})
                
                # Asignar nombres reales
                for c in live_data:
                    cid = c.get('category_id')
                    c['category_name'] = mapa_cats.get(cid, f"ID: {cid}")
                
                st.write("---")
                nombres_cats = sorted(list(set([c['category_name'] for c in live_data])))
                cat_seleccionada = st.selectbox("📂 Elige Categoría:", ["-- Selecciona --"] + nombres_cats)
                
                if cat_seleccionada and cat_seleccionada != "-- Selecciona --":
                    canales_cat = [c for c in live_data if c['category_name'] == cat_seleccionada]
                    st.write(f"Canales disponibles: **{len(canales_cat)}**")
                    
                    c_a, c_b = st.columns([1, 3])
                    with c_a:
                        if st.button(f"✅ Agregar TODOS"):
                            ids = [x['stream_id'] for x in st.session_state['mis_canales']]
                            nuevos = [c for c in canales_cat if c['stream_id'] not in ids]
                            st.session_state['mis_canales'].extend(nuevos)
                            st.rerun()
                    with c_b:
                        sel = st.multiselect("O elige individuales:", [c['name'] for c in canales_cat])
                        if st.button("➕ Agregar"):
                            nuevos = [c for c in canales_cat if c['name'] in sel]
                            st.session_state['mis_canales'].extend(nuevos)
                            st.rerun()

                # RESUMEN
                if st.session_state['mis_canales']:
                    st.success(f"📋 Canales en lista: {len(st.session_state['mis_canales'])}")
                    if st.button("Borrar todo"):
                        st.session_state['mis_canales'] = []
                        st.rerun()

                # 3. GENERAR (CON FIX DE ERROR)
                st.write("---")
                if st.button("🚀 GENERAR ARCHIVO M3U"):
                    if not st.session_state['mis_canales']:
                        st.error("Agrega al menos un canal.")
                    else:
                        data_vod = st.session_state['datos_full']['vod']
                        data_series_list = st.session_state['datos_full']['series']
                        episodios_finales = []

                        if data_series_list:
                            status = st.empty()
                            status.text("⏳ Procesando series (con corrección de errores)...")
                            args_list = [(host_m, user_m, pw_m, s['series_id']) for s in data_series_list]
                            
                            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                                futures = {executor.submit(obtener_episodios_serie_individual, arg): arg for arg in args_list}
                                for future in concurrent.futures.as_completed(futures):
                                    data_eps = future.result()
                                    
                                    # --- AQUÍ ESTÁ EL ARREGLO DEL ERROR ---
                                    # Verificamos que data_eps sea un diccionario válido antes de usar .items()
                                    if data_eps and isinstance(data_eps, dict):
                                        for season, eps in data_eps.items():
                                            for ep in eps:
                                                ext = ep.get('container_extension', 'mp4')
                                                link = f"{host_m}/series/{user_m}/{pw_m}/{ep['id']}.{ext}"
                                                full_name = f"{ep['title']} - S{season}E{ep['episode_num']}"
                                                episodios_finales.append({'name': full_name, 'link': link})
                                    # --------------------------------------
                            status.empty()

                        contenido = generar_m3u_final(
                            st.session_state['mis_canales'], 
                            data_vod, 
                            episodios_finales, 
                            host_m, user_m, pw_m
                        )
                        
                        st.download_button("⬇️ DESCARGAR LISTA FINAL", contenido, "lista_maxplayer.m3u")
