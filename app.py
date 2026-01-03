import streamlit as st
import requests
import pandas as pd
import concurrent.futures
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# CONFIGURACIÓN
st.set_page_config(page_title="IPTV Tool Pro", page_icon="📺", layout="wide")
st.title("📺 IPTV Tool Web")
st.markdown("Generador M3U: **Canales por Categoría (Nombres Reales) + Todo VOD**.")

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

# --- FUNCIONES DE CARGA (AHORA CON CATEGORÍAS) ---

@st.cache_data(ttl=600)
def obtener_datos_completos(host, user, passw):
    """Descarga Canales, Categorías, Pelis y Series de una vez."""
    data = {}
    try:
        # 1. Canales
        data['live'] = requests.get(f"{host}/player_api.php?username={user}&password={passw}&action=get_live_streams", timeout=30).json()
        # 2. Categorías de Canales (PARA VER NOMBRES REALES)
        data['cats_live'] = requests.get(f"{host}/player_api.php?username={user}&password={passw}&action=get_live_categories", timeout=30).json()
        # 3. Películas
        data['vod'] = requests.get(f"{host}/player_api.php?username={user}&password={passw}&action=get_vod_streams", timeout=30).json()
        # 4. Series
        data['series'] = requests.get(f"{host}/player_api.php?username={user}&password={passw}&action=get_series", timeout=30).json()
    except:
        return None
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

# --- GENERADOR M3U ---
def generar_m3u_final(items_live, items_vod, items_episodios, host, user, passw):
    contenido = "#EXTM3U\r\n"
    
    # 1. CANALES (Con formato Windows para Maxplayer)
    for c in items_live:
        # Limpiamos nombre
        nombre = c.get('name', '').replace('"', '').replace(',', ' ').strip()
        cat_name = c.get('category_name', 'General').replace('"', '') # Usamos el nombre real de la categoría
        sid = c.get('stream_id')
        link = f"{host}/live/{user}/{passw}/{sid}.ts"
        
        # Maxplayer lee el group-title
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

tab1, tab2, tab4 = st.tabs(["🔍 Una Cuenta", "📋 Lista Masiva", "🛠️ Creador M3U (Fácil)"])

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

# --- PESTAÑA 4 MEJORADA ---
with tab4:
    st.header("🛠️ Creador de Listas M3U")
    st.info("Ahora con NOMBRES REALES de carpetas y selección rápida.")
    
    link_m3u = st.text_input("Pega tu cuenta:", key="m3u_input")
    
    # Inicializar estado de selección si no existe
    if 'mis_canales' not in st.session_state:
        st.session_state['mis_canales'] = []

    if link_m3u:
        url_c = limpiar_url(link_m3u)
        if url_c:
            host_m, user_m, pw_m = extraer_credenciales(url_c)
            
            # 1. CARGA DE DATOS
            if st.button("📡 Cargar Datos (Canales y Categorías)"):
                with st.spinner("Conectando al servidor..."):
                    datos = obtener_datos_completos(host_m, user_m, pw_m)
                    if datos and datos.get('live'):
                        st.session_state['datos_full'] = datos
                        
                        # CREAR DICCIONARIO ID -> NOMBRE CATEGORÍA
                        # Esto convierte "104" en "Deportes HD"
                        cats_raw = datos.get('cats_live', [])
                        mapa_cats = {c['category_id']: c['category_name'] for c in cats_raw}
                        st.session_state['mapa_cats'] = mapa_cats
                        
                        st.success("¡Datos cargados correctamente!")
                    else:
                        st.error("No se pudo cargar la lista.")

            # 2. SELECTOR INTELIGENTE
            if 'datos_full' in st.session_state:
                live_data = st.session_state['datos_full']['live']
                mapa_cats = st.session_state.get('mapa_cats', {})
                
                st.write("---")
                st.subheader("📺 Paso 1: Selecciona Canales")
                
                # Obtener lista de nombres de categorías
                # Asignamos el nombre real a cada canal para usarlo luego
                for c in live_data:
                    cid = c.get('category_id')
                    c['category_name'] = mapa_cats.get(cid, f"ID: {cid}") # Si no encuentra nombre, usa ID
                
                # LISTA DESPLEGABLE DE CATEGORÍAS (Nombres Reales)
                nombres_cats = sorted(list(set([c['category_name'] for c in live_data])))
                cat_seleccionada = st.selectbox("📂 1. Elige una Carpeta (Categoría):", ["-- Selecciona --"] + nombres_cats)
                
                if cat_seleccionada and cat_seleccionada != "-- Selecciona --":
                    # Filtrar canales de esa categoría
                    canales_en_carpeta = [c for c in live_data if c['category_name'] == cat_seleccionada]
                    
                    st.write(f"Viendo **{len(canales_en_carpeta)}** canales en: **{cat_seleccionada}**")
                    
                    colA, colB = st.columns([1, 3])
                    with colA:
                        # BOTÓN MÁGICO: AGREGAR TODOS
                        if st.button(f"✅ Agregar TODOS ({len(canales_en_carpeta)})"):
                            # Añadimos a la cesta sin duplicados
                            ids_actuales = [x['stream_id'] for x in st.session_state['mis_canales']]
                            nuevos = [c for c in canales_en_carpeta if c['stream_id'] not in ids_actuales]
                            st.session_state['mis_canales'].extend(nuevos)
                            st.rerun() # Recargar para ver cambios
                    
                    with colB:
                        # O SELECCIONAR INDIVIDUALMENTE
                        nombres_canales = [c['name'] for c in canales_en_carpeta]
                        seleccion = st.multiselect("O marca los que quieras:", nombres_canales)
                        if st.button("➕ Agregar seleccionados"):
                            nuevos = [c for c in canales_en_carpeta if c['name'] in seleccion]
                            st.session_state['mis_canales'].extend(nuevos)
                            st.rerun()

                # MOSTRAR LO QUE TENEMOS SELECCIONADO
                st.write("---")
                total_sel = len(st.session_state['mis_canales'])
                if total_sel > 0:
                    st.success(f"📋 Tienes **{total_sel} canales** en tu lista.")
                    with st.expander("Ver mi lista de canales seleccionados"):
                        df_sel = pd.DataFrame(st.session_state['mis_canales'])
                        st.dataframe(df_sel[['name', 'category_name']], hide_index=True)
                        if st.button("🗑️ Borrar todo y empezar de cero"):
                            st.session_state['mis_canales'] = []
                            st.rerun()
                else:
                    st.info("Tu lista está vacía. Selecciona una categoría arriba y añade canales.")

                # 3. GENERAR
                st.write("---")
                st.subheader("💾 Paso 2: Descargar")
                st.caption("Películas y Series se añadirán automáticamente.")
                
                if st.button("🚀 GENERAR ARCHIVO M3U"):
                    if total_sel == 0:
                        st.error("¡Primero añade al menos un canal!")
                    else:
                        # Preparar datos extra
                        data_vod = st.session_state['datos_full']['vod']
                        data_series_list = st.session_state['datos_full']['series']
                        episodios_finales = []

                        # Procesar Series (Multi-hilo)
                        if data_series_list:
                            status = st.empty()
                            status.text("⏳ Procesando todas las series (esto toma unos segundos)...")
                            args_list = [(host_m, user_m, pw_m, s['series_id']) for s in data_series_list]
                            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                                futures = {executor.submit(obtener_episodios_serie_individual, arg): arg for arg in args_list}
                                for future in concurrent.futures.as_completed(futures):
                                    data_eps = future.result()
                                    for season, eps in data_eps.items():
                                        for ep in eps:
                                            ext = ep.get('container_extension', 'mp4')
                                            link = f"{host_m}/series/{user_m}/{pw_m}/{ep['id']}.{ext}"
                                            full_name = f"{ep['title']} - S{season}E{ep['episode_num']}"
                                            episodios_finales.append({'name': full_name, 'link': link})
                            status.empty()

                        # Crear contenido
                        contenido = generar_m3u_final(
                            st.session_state['mis_canales'], 
                            data_vod, 
                            episodios_finales, 
                            host_m, user_m, pw_m
                        )
                        
                        st.download_button(
                            label="⬇️ DESCARGAR LISTA FINAL (.m3u)",
                            data=contenido,
                            file_name="lista_personalizada_maxplayer.m3u",
                            mime="text/plain"
                        )
