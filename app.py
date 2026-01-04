import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="IPTV Manager", page_icon="📺", layout="wide")

# 2. CAMUFLAJE (ESTILO PROPIO)
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stDeployButton {display:none;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.title("📺 IPTV Manager Tool")

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

def proxificar_imagen(url_imagen):
    """Proxy para imágenes de VOD (Pelis/Series)"""
    if not url_imagen or not url_imagen.startswith('http'):
        return "https://via.placeholder.com/50?text=No+Img"
    return f"https://wsrv.nl/?url={url_imagen}&w=100&h=150&fit=contain&output=webp"

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

# --- FUNCIONES VOD (PELÍCULAS Y SERIES - CON IMÁGENES) ---

def obtener_peliculas(host, user, passw):
    try:
        url_cats = f"{host}/player_api.php?username={user}&password={passw}&action=get_vod_categories"
        cats_data = requests.get(url_cats, timeout=20).json()
        mapa_carpetas = {c['category_id']: c['category_name'] for c in cats_data}

        url_vod = f"{host}/player_api.php?username={user}&password={passw}&action=get_vod_streams"
        data = requests.get(url_vod, timeout=30).json()
        
        if not isinstance(data, list): return None
        
        lista = []
        for item in data:
            ext = item.get('container_extension', 'mp4')
            link = f"{host}/movie/{user}/{passw}/{item['stream_id']}.{ext}"
            cat_id = item.get('category_id')
            
            icon_raw = item.get('stream_icon')
            icon_final = proxificar_imagen(icon_raw)

            lista.append({
                "Portada": icon_final,
                "Título": item['name'],
                "📂 Carpeta": mapa_carpetas.get(cat_id, "Otras"),
                "Link": link
            })
        return pd.DataFrame(lista)
    except: return None

def obtener_lista_series(host, user, passw):
    try:
        url_cats = f"{host}/player_api.php?username={user}&password={passw}&action=get_series_categories"
        cats_data = requests.get(url_cats, timeout=20).json()
        mapa_carpetas = {c['category_id']: c['category_name'] for c in cats_data}

        url_series = f"{host}/player_api.php?username={user}&password={passw}&action=get_series"
        data = requests.get(url_series, timeout=30).json()
        
        if not isinstance(data, list): return None
        
        diccionario_series = {}
        for item in data:
            cat_id = item.get('category_id')
            nombre_carpeta = mapa_carpetas.get(cat_id, "Otras")
            nombre_serie = item['name']
            series_id = item['series_id']
            cover_raw = item.get('cover')
            cover_final = proxificar_imagen(cover_raw)
            
            etiqueta = f"{nombre_serie}  | 📂 {nombre_carpeta}"
            diccionario_series[etiqueta] = {
                "id": series_id,
                "cover": cover_final
            }
        return diccionario_series
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
                    lista_episodios.append({
                        "Episodio": nombre_cap, 
                        "Link": link
                    })
            return pd.DataFrame(lista_episodios)
        return None
    except: return None

# --- FUNCIONES AUDITORÍA (CANALES - SIN LOGOS, SOLO TEXTO) ---
@st.cache_data(ttl=600)
def mapear_canales_carpetas(host, user, passw):
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
            
            # Usamos 'num' si existe (es el número de canal ordenado), si no, usamos el stream_id
            numero_canal = canal.get('num', canal.get('stream_id'))

            lista_final.append({
                "N°": numero_canal,  # Nueva Columna solicitada
                "Nombre del Canal": canal.get('name'),
                "📂 Carpeta": nombre_carpeta
            })
            
        return pd.DataFrame(lista_final)
    except: return None

# --- INTERFAZ PRINCIPAL ---

tab1, tab2, tab3, tab4 = st.tabs(["🔍 Verificar", "📋 Masivo", "📥 VOD Visual", "🔎 Buscar Canal"])

# --- PESTAÑA 1 ---
with tab1:
    st.header("Verificador Individual")
    u = st.text_input("Enlace:", key="t1_in")
    if st.button("Verificar Estado"):
        res = verificar_url(u)
        if res and "Usuario" in res:
            st.success(f"Usuario: {res['Usuario']}")
            c1,c2,c3 = st.columns(3)
            c1.metric("Estado", res["Estado"])
            c2.metric("Vence", res["Vence"])
            c3.metric("Conexiones", res["Conexiones"])
        else: st.error("Error: Verifica el enlace.")

# --- PESTAÑA 2 ---
with tab2:
    st.header("Verificador Masivo")
    txt = st.text_area("Enlaces (uno por línea):", height=150)
    if st.button("Procesar Lista"):
        urls = txt.split('\n')
        res = [verificar_url(x) for x in urls if len(x)>10]
        st.dataframe(pd.DataFrame([r for r in res if r]), use_container_width=True)

# --- PESTAÑA 3 ---
with tab3:
    st.header("VOD (Películas y Series)")
    l_vod = st.text_input("Cuenta:", key="tvod")
    t_vod = st.radio("Buscar:", ["🎬 Películas", "📺 Series"], horizontal=True)
    
    if l_vod:
        h, u_c, p_c = extraer_credenciales(l_vod)
        if h:
            if t_vod == "🎬 Películas":
                if st.button("Buscar Películas"):
                    with st.spinner("Cargando catálogo..."):
                        st.session_state['df_p'] = obtener_peliculas(h, u_c, p_c)
                
                if 'df_p' in st.session_state and st.session_state['df_p'] is not None:
                    df = st.session_state['df_p']
                    filt = st.text_input("Filtrar Título:", key="fp")
                    if filt: df = df[df['Título'].str.contains(filt, case=False, na=False)]
                    
                    st.dataframe(
                        df, 
                        use_container_width=True, 
                        hide_index=True,
                        column_config={
                            "Portada": st.column_config.ImageColumn("Póster", width="small"),
                            "Link": st.column_config.LinkColumn("Video", display_text="⬇️ Bajar"),
                            "📂 Carpeta": st.column_config.TextColumn("Ubicación")
                        }
                    )
            else: # SERIES
                if st.button("Cargar Series"):
                    with st.spinner("Cargando series..."):
                        st.session_state['ls'] = obtener_lista_series(h, u_c, p_c)
                        st.rerun()
                
                if 'ls' in st.session_state:
                    series_data = st.session_state['ls']
                    lista_nombres = list(series_data.keys())
                    
                    filtro_serie = st.text_input("Filtrar series:", placeholder="Escribe el nombre...")
                    if filtro_serie:
                        lista_nombres = [s for s in lista_nombres if filtro_serie.lower() in s.lower()]

                    if lista_nombres:
                        sel = st.selectbox("Elige la Serie:", lista_nombres)
                        datos_serie = series_data[sel]
                        sid = datos_serie['id']
                        cover_url = datos_serie.get('cover')
                        
                        c_img, c_dat = st.columns([1, 4])
                        with c_img:
                             st.image(cover_url, caption="Portada", width=150)
                        
                        with c_dat:
                            if st.button(f"Ver Episodios"):
                                with st.spinner("Buscando capítulos..."):
                                    df_eps = obtener_episodios(h, u_c, p_c, sid)
                                    st.dataframe(
                                        df_eps, 
                                        use_container_width=True, 
                                        hide_index=True,
                                        column_config={"Link": st.column_config.LinkColumn("Video", display_text="⬇️ Bajar")}
                                    )
                    if st.button("🔄 Reiniciar"):
                        del st.session_state['ls']
                        st.rerun()

# --- PESTAÑA 4: CANALES (LIMPIA, SOLO NÚMERO Y NOMBRE) ---
with tab4:
    st.header("🔎 Ubicador de Canales")
    link_search = st.text_input("Pega tu cuenta:", key="t4_input")
    
    if link_search:
        url_c = limpiar_url(link_search)
        if url_c:
            host, user, pw = extraer_credenciales(url_c)
            
            if 'df_audit' not in st.session_state:
                if st.button("📡 Analizar Canales"):
                    with st.spinner("Descargando lista..."):
                        df = mapear_canales_carpetas(host, user, pw)
                        if df is not None:
                            st.session_state['df_audit'] = df
                            st.rerun()
                        else: st.error("Error al conectar.")

            if 'df_audit' in st.session_state:
                df = st.session_state['df_audit']
                busqueda = st.text_input("🔍 Buscar Canal:", placeholder="Escribe aquí el nombre...")
                
                if busqueda:
                    resultados = df[df['Nombre del Canal'].str.contains(busqueda, case=False, na=False)]
                    if not resultados.empty:
                        st.success(f"Encontrados: {len(resultados)}")
                        
                        # TABLA LIMPIA: NUMERO, NOMBRE, CARPETA
                        st.dataframe(
                            resultados,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "N°": st.column_config.NumberColumn("Canal #", format="%d"),
                                "Nombre del Canal": st.column_config.TextColumn("Nombre"),
                                "📂 Carpeta": st.column_config.TextColumn("Carpeta")
                            }
                        )
                    else:
                        st.warning("No encontrado.")
                
                st.write("---")
                if st.button("🔄 Nueva Búsqueda"):
                    del st.session_state['df_audit']
                    st.rerun()
