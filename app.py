import streamlit as st
import requests
import pandas as pd
import concurrent.futures
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# CONFIGURACIÓN
st.set_page_config(page_title="IPTV Tool Pro", page_icon="📺", layout="wide")
st.title("📺 IPTV Tool Web")
st.markdown("Generador M3U: **Canales a elección + TODO Cine y Series**.")

# --- FUNCIONES ---

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

# --- FUNCIONES DE CARGA ---
@st.cache_data(ttl=600)
def obtener_todo_live(host, user, passw):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_live_streams"
    try: return requests.get(url, timeout=30).json()
    except: return []

@st.cache_data(ttl=600)
def obtener_todo_vod(host, user, passw):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_vod_streams"
    try: return requests.get(url, timeout=30).json()
    except: return []

@st.cache_data(ttl=600)
def obtener_todo_series_lista(host, user, passw):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_series"
    try: return requests.get(url, timeout=30).json()
    except: return []

def obtener_episodios_serie_individual(args):
    """Función auxiliar para descarga paralela"""
    host, user, passw, series_id = args
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_series_info&series_id={series_id}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json().get('episodes', {})
    except:
        pass
    return {}

# --- GENERADOR M3U ---
def generar_m3u_completo(items_live, items_vod, items_episodios, host, user, passw):
    contenido = "#EXTM3U\r\n"
    
    # 1. CANALES (Seleccionados por usuario)
    for c in items_live:
        nombre = c.get('name', '').replace('"', '').replace(',', ' ').strip()
        sid = c.get('stream_id')
        link = f"{host}/live/{user}/{passw}/{sid}.ts"
        contenido += f'#EXTINF:-1 group-title="TV en Vivo",{nombre}\r\n{link}\r\n'

    # 2. PELÍCULAS (Todas)
    for p in items_vod:
        nombre = p.get('name', '').replace('"', '').replace(',', ' ').strip()
        sid = p.get('stream_id')
        ext = p.get('container_extension', 'mp4')
        link = f"{host}/movie/{user}/{passw}/{sid}.{ext}"
        contenido += f'#EXTINF:-1 group-title="Peliculas",{nombre}\r\n{link}\r\n'

    # 3. SERIES (Todas las procesadas)
    for s in items_episodios:
        nombre = s['name'].replace('"', '').replace(',', ' ').strip()
        link = s['link']
        contenido += f'#EXTINF:-1 group-title="Series",{nombre}\r\n{link}\r\n'

    return contenido

# --- INTERFAZ ---

tab1, tab2, tab4 = st.tabs(["🔍 Una Cuenta", "📋 Lista Masiva", "🛠️ Creador M3U (Auto)"])

# PESTAÑA 1
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

# PESTAÑA 2
with tab2:
    txt = st.text_area("Lista:")
    if st.button("Procesar"):
        urls = txt.split('\n')
        res = [verificar_url(x) for x in urls if len(x)>10]
        st.dataframe(pd.DataFrame([r for r in res if r]))

# --- PESTAÑA 4: LÓGICA AUTOMÁTICA ---
with tab4:
    st.header("🛠️ Creador de Listas M3U")
    st.info("Elige tus canales. Las Películas y Series se añadirán TODAS automáticamente.")
    
    link_m3u = st.text_input("Pega tu cuenta:", key="m3u_input")
    
    if link_m3u:
        url_c = limpiar_url(link_m3u)
        if url_c:
            host_m, user_m, pw_m = extraer_credenciales(url_c)
            
            if st.button("📡 Cargar Información del Servidor"):
                with st.spinner("Descargando catálogos..."):
                    st.session_state['data_live'] = obtener_todo_live(host_m, user_m, pw_m)
                    st.session_state['data_vod'] = obtener_todo_vod(host_m, user_m, pw_m)
                    st.session_state['data_series_list'] = obtener_todo_series_lista(host_m, user_m, pw_m)
                    st.success("¡Datos cargados!")

            if 'data_live' in st.session_state:
                
                # 1. SELECCIÓN DE CANALES (Con filtro rápido)
                st.write("---")
                st.subheader("📺 1. Selecciona los Canales")
                live_data = st.session_state['data_live']
                
                if live_data:
                    # Filtro por categoría
                    cats = sorted(list(set([x.get('category_id', 'Sin Cat') for x in live_data])))
                    cat_sel = st.multiselect("Filtrar por Categoría (Opcional):", cats)
                    
                    if cat_sel:
                        live_view = [x for x in live_data if x.get('category_id') in cat_sel]
                    else:
                        live_view = live_data # Cuidado si son muchos

                    # Mapeo para nombres únicos
                    mapa_live = {f"{c['name']} (ID:{c['stream_id']})": c for c in live_view}
                    
                    sel_keys = st.multiselect(
                        f"Elige canales ({len(live_view)} disponibles):",
                        options=list(mapa_live.keys())
                    )
                    st.session_state['final_live'] = [mapa_live[k] for k in sel_keys]
                
                # 2. INFORMACIÓN VOD y SERIES (Solo informativo)
                st.write("---")
                c_vod, c_ser = st.columns(2)
                
                with c_vod:
                    st.subheader("🎬 Películas")
                    n_peli = len(st.session_state['data_vod'])
                    st.success(f"✅ Se añadirán {n_peli} películas automáticamente.")
                
                with c_ser:
                    st.subheader("📺 Series")
                    n_ser = len(st.session_state['data_series_list'])
                    st.warning(f"⚠️ Hay {n_ser} series disponibles.")
                    st.caption("Al generar, el sistema descargará los episodios de TODAS. Esto puede tardar un poco.")

                # BOTÓN FINAL
                st.write("---")
                if st.button("💾 GENERAR LISTA COMPLETA"):
                    canales_elegidos = st.session_state.get('final_live', [])
                    peliculas_todas = st.session_state.get('data_vod', [])
                    series_lista = st.session_state.get('data_series_list', [])
                    
                    if not canales_elegidos:
                        st.warning("No elegiste ningún canal, pero generaremos la lista con Pelis y Series.")
                    
                    episodios_finales = []
                    
                    # PROCESAMIENTO MULTI-HILO PARA SERIES (Para que no sea eterno)
                    if series_lista:
                        status_text = st.empty()
                        progress_bar = st.progress(0)
                        total_series = len(series_lista)
                        
                        # Preparamos los argumentos para cada hilo
                        args_list = [(host_m, user_m, pw_m, s['series_id']) for s in series_lista]
                        
                        # Usamos 10 hilos simultáneos
                        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                            # Lanzamos todas las tareas
                            futures = {executor.submit(obtener_episodios_serie_individual, arg): arg for arg in args_list}
                            
                            completed = 0
                            for future in concurrent.futures.as_completed(futures):
                                data_eps = future.result()
                                # Procesamos los episodios recibidos
                                for season, eps in data_eps.items():
                                    for ep in eps:
                                        ext = ep.get('container_extension', 'mp4')
                                        link = f"{host_m}/series/{user_m}/{pw_m}/{ep['id']}.{ext}"
                                        full_name = f"{ep['title']} - S{season}E{ep['episode_num']}"
                                        episodios_finales.append({'name': full_name, 'link': link})
                                
                                completed += 1
                                if completed % 5 == 0: # Actualizar barra cada 5 series
                                    progress_bar.progress(completed / total_series)
                                    status_text.text(f"Procesando series: {completed}/{total_series}")
                        
                        status_text.text("¡Series procesadas!")
                        progress_bar.progress(1.0)

                    # Generar Archivo
                    contenido = generar_m3u_completo(canales_elegidos, peliculas_todas, episodios_finales, host_m, user_m, pw_m)
                    
                    st.balloons()
                    st.download_button(
                        label="⬇️ DESCARGAR LISTA DEFINITIVA (.m3u)",
                        data=contenido,
                        file_name="lista_full_maxplayer.m3u",
                        mime="text/plain"
                    )
