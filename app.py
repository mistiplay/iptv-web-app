import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# CONFIGURACIÓN VISUAL
st.set_page_config(page_title="IPTV Manager Tool", page_icon="📺", layout="wide")
st.title("📺 IPTV Manager Tool")
st.markdown("Herramienta de Gestión: Verificación, VOD y **Auditoría de Canales**.")

# --- FUNCIONES DE UTILIDAD (CORE) ---

def limpiar_url(url_raw):
    url = url_raw.strip()
    if not url or not url.startswith("http"): return None
    # Estandarizamos para que siempre apunte a la API
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
    except: return {"Estado": "Error de Conexión"}

# --- FUNCIONES VOD (PELÍCULAS Y SERIES) ---

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

# --- FUNCIONES AUDITORÍA (SOLO UBICACIÓN) ---
@st.cache_data(ttl=600)
def mapear_canales_carpetas(host, user, passw):
    try:
        # 1. Bajamos nombres de carpetas
        cats_req = requests.get(f"{host}/player_api.php?username={user}&password={passw}&action=get_live_categories", timeout=20)
        cats_data = cats_req.json()
        mapa_carpetas = {c['category_id']: c['category_name'] for c in cats_data}

        # 2. Bajamos lista de canales
        live_req = requests.get(f"{host}/player_api.php?username={user}&password={passw}&action=get_live_streams", timeout=30)
        live_data = live_req.json()

        lista_final = []
        for canal in live_data:
            cat_id = canal.get('category_id')
            nombre_carpeta = mapa_carpetas.get(cat_id, "Sin Categoría / Oculto")
            
            lista_final.append({
                "Nombre del Canal": canal.get('name'),
                "📂 Carpeta (Categoría)": nombre_carpeta,
                "ID Canal": canal.get('stream_id') # Útil por si necesitas reportar un fallo al proveedor
            })
            
        return pd.DataFrame(lista_final)
    except: return None

# --- INTERFAZ PRINCIPAL ---

tab1, tab2, tab3, tab4 = st.tabs(["🔍 Verificar Cuenta", "📋 Verificador Masivo", "📥 Buscador VOD", "🔎 ¿Dónde está el Canal?"])

# --- PESTAÑA 1: UNA CUENTA ---
with tab1:
    st.header("Verificador Individual")
    u = st.text_input("Enlace (M3U o Xtream):", key="t1_in")
    if st.button("Verificar Estado"):
        res = verificar_url(u)
        if res and "Usuario" in res:
            st.success(f"Usuario: {res['Usuario']}")
            c1,c2,c3 = st.columns(3)
            c1.metric("Estado", res["Estado"])
            c2.metric("Vence", res["Vence"])
            c3.metric("Conexiones", res["Conexiones"])
        else: st.error("Error: Cuenta inválida o servidor caído.")

# --- PESTAÑA 2: MASIVO ---
with tab2:
    st.header("Verificador de Listas")
    st.caption("Pega múltiples enlaces (uno por línea).")
    txt = st.text_area("Enlaces:", height=150)
    if st.button("Procesar Lista"):
        urls = txt.split('\n')
        res = [verificar_url(x) for x in urls if len(x)>10]
        st.dataframe(pd.DataFrame([r for r in res if r]), use_container_width=True)

# --- PESTAÑA 3: VOD (PELIS Y SERIES) ---
with tab3:
    st.header("Descargas VOD")
    l_vod = st.text_input("Cuenta:", key="tvod")
    t_vod = st.radio("¿Qué buscas?", ["🎬 Películas", "📺 Series"], horizontal=True)
    
    if l_vod:
        h, u_c, p_c = extraer_credenciales(l_vod)
        if h:
            if t_vod == "🎬 Películas":
                if st.button("Buscar Películas"):
                    with st.spinner("Descargando catálogo..."):
                        st.session_state['df_p'] = obtener_peliculas(h, u_c, p_c)
                
                if 'df_p' in st.session_state and st.session_state['df_p'] is not None:
                    df = st.session_state['df_p']
                    filt = st.text_input("Filtrar nombre:", key="fp")
                    if filt: df = df[df['Título'].str.contains(filt, case=False, na=False)]
                    
                    st.dataframe(
                        df, 
                        use_container_width=True, 
                        hide_index=True,
                        column_config={"Link": st.column_config.LinkColumn("Enlace", display_text="⬇️ Descargar")}
                    )
            else: # SERIES
                if st.button("Cargar Lista de Series"):
                    with st.spinner("Descargando series..."):
                        st.session_state['ls'] = obtener_lista_series(h, u_c, p_c)
                        st.rerun()
                
                if 'ls' in st.session_state:
                    sel = st.selectbox("Elige la Serie:", list(st.session_state['ls'].keys()))
                    if st.button(f"Ver Episodios de: {sel}"):
                        with st.spinner("Buscando episodios..."):
                            sid = st.session_state['ls'][sel]
                            st.dataframe(
                                obtener_episodios(h, u_c, p_c, sid), 
                                use_container_width=True, 
                                hide_index=True,
                                column_config={"Link": st.column_config.LinkColumn("Enlace", display_text="⬇️ Descargar")}
                            )
                    
                    if st.button("🔄 Nueva Búsqueda"):
                        del st.session_state['ls']
                        st.rerun()

# --- PESTAÑA 4: AUDITOR DE CANALES (SOLO BÚSQUEDA) ---
with tab4:
    st.header("🔎 Ubicador de Canales")
    st.info("Escribe el nombre de un canal para saber en qué carpeta se encuentra.")
    
    link_search = st.text_input("Pega tu cuenta:", key="t4_input")
    
    if link_search:
        url_c = limpiar_url(link_search)
        if url_c:
            host, user, pw = extraer_credenciales(url_c)
            
            # Carga de datos
            if 'df_audit' not in st.session_state:
                if st.button("📡 Analizar Servidor"):
                    with st.spinner("Cruzando datos de canales y carpetas..."):
                        df = mapear_canales_carpetas(host, user, pw)
                        if df is not None:
                            st.session_state['df_audit'] = df
                            st.rerun()
                        else: st.error("Error al cargar los datos.")

            # Buscador
            if 'df_audit' in st.session_state:
                df = st.session_state['df_audit']
                
                busqueda = st.text_input("🔍 Buscar Canal (Ej: Star, HBO, Peru...):", placeholder="Escribe aquí...")
                
                if busqueda:
                    # Filtro insensible a mayúsculas/minúsculas
                    resultados = df[df['Nombre del Canal'].str.contains(busqueda, case=False, na=False)]
                    
                    if not resultados.empty:
                        st.success(f"Se encontraron **{len(resultados)}** coincidencias.")
                        st.dataframe(
                            resultados,
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.warning("No se encontró ningún canal con ese nombre.")
                else:
                    st.caption(f"Total de canales en la cuenta: {len(df)}")
                
                st.write("---")
                if st.button("🔄 Borrar datos y buscar de nuevo"):
                    del st.session_state['df_audit']
                    st.rerun()
