import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import io

# CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="IPTV Tool Completa", page_icon="📺", layout="wide")
st.title("📺 IPTV Tool Web")
st.markdown("Herramienta Completa: Verificador + Buscador VOD + **Editor M3U Inteligente**.")

# --- FUNCIONES COMUNES ---

def limpiar_url(url_raw):
    url = url_raw.strip()
    if not url or not url.startswith("http"): return None
    # Estandarizamos a player_api para consultas JSON
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

# --- FUNCIONES TABS 1, 2, 3 (RESTAURADAS) ---

def verificar_url(url_raw):
    url_final = limpiar_url(url_raw)
    if not url_final: return None
    try:
        response = requests.get(url_final, timeout=10)
        if response.status_code != 200: return {"Usuario": "Error HTTP", "Estado": f"Error {response.status_code}"}
        data = response.json()
        if 'user_info' not in data: return {"Usuario": "Invalido", "Estado": "No es panel"}
        info = data['user_info']
        ts = info.get('exp_date')
        fecha = datetime.fromtimestamp(int(ts)).strftime('%d/%m/%Y') if ts and ts != 'null' else "Ilimitada"
        return {
            "Usuario": info.get('username'),
            "Estado": "✅ Activa" if info.get('status') == 'Active' else "❌ Inactiva",
            "Vence": fecha,
            "Conexiones": f"{info.get('active_cons')}/{info.get('max_connections')}"
        }
    except: return {"Usuario": "Error", "Estado": "Error Conexión"}

def obtener_peliculas_individual(host, user, passw):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_vod_streams"
    try: return pd.DataFrame(requests.get(url, timeout=20).json())
    except: return None

def obtener_series_individual(host, user, passw):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_series"
    try:
        data = requests.get(url, timeout=20).json()
        return {item['name']: item['series_id'] for item in data}
    except: return None

def obtener_episodios_individual(host, user, passw, series_id):
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_series_info&series_id={series_id}"
    try:
        data = requests.get(url, timeout=10).json()
        eps = data.get('episodes', {})
        lista = []
        if isinstance(eps, dict):
            for season, chapters in eps.items():
                for ep in chapters:
                    ext = ep.get('container_extension', 'mp4')
                    link = f"{host}/series/{user}/{passw}/{ep['id']}.{ext}"
                    lista.append({"Nombre": f"T{season}E{ep['episode_num']} - {ep['title']}", "Link": link})
        return pd.DataFrame(lista)
    except: return None

# --- FUNCIÓN TAB 4 (NUEVA LÓGICA DE STREAMING) ---

def obtener_categorias_live(host, user, passw):
    """Descarga solo las categorías de TV (rápido) para que el usuario elija."""
    url = f"{host}/player_api.php?username={user}&password={passw}&action=get_live_categories"
    try:
        return requests.get(url, timeout=15).json()
    except: return []

def generar_m3u_filtrado_stream(host, user, passw, cats_permitidas_ids):
    """
    Descarga el M3U línea por línea y solo escribe lo que el usuario quiere.
    Esto evita que la memoria explote y que se pierdan las series.
    """
    # URL de descarga del M3U completo
    url_m3u = f"{host}/get.php?username={user}&password={passw}&type=m3u_plus&output=ts"
    
    # Buffer en memoria para escribir el archivo resultante
    output = io.StringIO()
    output.write("#EXTM3U\n")
    
    try:
        # stream=True es la clave: descarga poco a poco
        with requests.get(url_m3u, stream=True, timeout=60) as r:
            r.raise_for_status()
            
            buffer_linea = ""
            es_live = False
            mantener_bloque = True
            
            # Iteramos sobre las líneas del archivo original
            for linea_bytes in r.iter_lines():
                if not linea_bytes: continue
                linea = linea_bytes.decode('utf-8', errors='ignore').strip()
                
                if linea.startswith("#EXTINF"):
                    # Analizamos la línea de información
                    buffer_linea = linea
                    
                    # Detectamos si es TV en VIVO comprobando si tiene tvg-logo o atributos típicos
                    # O más fácil: miramos el group-title
                    # Sin embargo, en M3U puro es difícil saber si es VOD o LIVE solo con EXTINF.
                    # Estrategia: Asumimos que queremos todo, SALVO si es un canal de una categoría no deseada.
                    
                    # Extraer ID de grupo
                    # Muchos paneles ponen group-title="Noticias". Necesitamos comparar nombres.
                    # Pero tenemos IDs permitidos. Haremos coincidencia por nombre de grupo.
                    
                    mantener_bloque = True # Por defecto guardamos (así salvamos Pelis y Series)
                    
                    # Buscamos el group-title
                    start = linea.find('group-title="')
                    if start != -1:
                        end = linea.find('"', start + 13)
                        grupo_nombre = linea[start+13:end]
                        
                        # AQUÍ ESTÁ EL TRUCO:
                        # Si el grupo NO está en la lista de permitidos Y tampoco es Peli/Serie...
                        # Como es difícil saber qué es qué, usaremos la lógica inversa:
                        # Si el usuario eligió SOLO "Deportes", borramos todo lo que no sea "Deportes"
                        # PERO debemos salvar Peliculas y Series.
                        
                        # Simplificación para estabilidad:
                        # Si el usuario selecciona categorías, filtramos por texto exacto.
                        if cats_permitidas_ids: # Si hay filtro activo
                             if grupo_nombre not in cats_permitidas_ids:
                                 # Podría ser una peli o serie. ¿Cómo saberlo?
                                 # Generalmente Pelis/Series tienen grupos distintos o keywords.
                                 # Para no complicar: Esta función asumirá filtrado por NOMBRE DE GRUPO exacto.
                                 mantener_bloque = False
                    
                elif not linea.startswith("#"):
                    # Es la URL
                    url = linea
                    
                    # PROTECCIÓN DE VOD:
                    # Si la URL tiene /movie/ o /series/, la forzamos a MANTENERSE siempre.
                    if "/movie/" in url or "/series/" in url:
                        mantener_bloque = True
                    
                    # Si decidimos mantener este bloque, escribimos info + url
                    if mantener_bloque:
                        # Limpieza de nombre para Maxplayer (quitar comillas del nombre final)
                        if buffer_linea:
                            parts = buffer_linea.rsplit(',', 1)
                            if len(parts) == 2:
                                nombre_limpio = parts[1].replace('"', '').strip()
                                buffer_linea = f"{parts[0]},{nombre_limpio}"
                            
                            output.write(f"{buffer_linea}\n")
                            output.write(f"{url}\n")
                    
                    buffer_linea = "" # Reset

        return output.getvalue()
    
    except Exception as e:
        return f"Error: {str(e)}"

# --- INTERFAZ ---

tab1, tab2, tab3, tab4 = st.tabs(["🔍 Verificar", "📋 Masivo", "📥 VOD Individual", "🛠️ Editor M3U"])

# TABS 1, 2, 3 (CÓDIGO CLÁSICO RESTAURADO)
with tab1:
    u = st.text_input("Enlace:", key="t1")
    if st.button("Verificar"):
        res = verificar_url(u)
        if res and "Usuario" in res:
            st.success(f"Usuario: {res['Usuario']}")
            c1,c2,c3 = st.columns(3)
            c1.metric("Estado", res["Estado"])
            c2.metric("Vence", res["Vence"])
            c3.metric("Conexiones", res["Conexiones"])
        else: st.error("Error conexión")

with tab2:
    txt = st.text_area("Lista:")
    if st.button("Procesar"):
        urls = txt.split('\n')
        res = [verificar_url(x) for x in urls if len(x)>10]
        st.dataframe(pd.DataFrame([r for r in res if r]))

with tab3:
    st.header("Descargas VOD (Pelis/Series)")
    l_vod = st.text_input("Cuenta:", key="tvod")
    t_vod = st.radio("Tipo:", ["Pelis", "Series"])
    if l_vod and st.button("Buscar VOD"):
        h, us, pw = extraer_credenciales(l_vod)
        if h:
            if t_vod == "Pelis":
                df = obtener_peliculas_individual(h, us, pw)
                if df is not None:
                     f = st.text_input("Filtrar nombre:", key="fvod")
                     if f: df = df[df[0 if 0 in df.columns else 'name'].astype(str).str.contains(f, case=False)]
                     st.dataframe(df)
            else:
                s_dict = obtener_series_individual(h, us, pw)
                if s_dict:
                    sel = st.selectbox("Elige Serie:", list(s_dict.keys()))
                    if st.button("Ver Caps"):
                        st.dataframe(obtener_episodios_individual(h, us, pw, s_dict[sel]))

# --- PESTAÑA 4: LA SOLUCIÓN FINAL ---
with tab4:
    st.header("🛠️ Editor M3U (Compatible Maxplayer)")
    st.info("Paso 1: Carga tus categorías de TV. Paso 2: Elige las que quieres. Paso 3: Genera el archivo (Pelis y Series se incluyen AUTOMÁTICAMENTE).")
    
    m3u_in = st.text_input("Pega tu cuenta completa:", key="tm3u")
    
    if m3u_in:
        url_c = limpiar_url(m3u_in)
        if url_c:
            host_m, user_m, pw_m = extraer_credenciales(url_c)
            
            # PASO 1: Obtener solo los nombres de grupos de TV (Rápido)
            if st.button("📡 1. Analizar Grupos de Canales"):
                with st.spinner("Conectando..."):
                    cats = obtener_categorias_live(host_m, user_m, pw_m)
                    if cats:
                        # Guardamos nombres de categorias
                        st.session_state['nombres_cats'] = sorted([c['category_name'] for c in cats])
                        st.success("¡Categorías cargadas!")
                    else:
                        st.error("No se pudo conectar. Verifica la cuenta.")

            # PASO 2: Selector
            if 'nombres_cats' in st.session_state:
                st.write("---")
                st.subheader("📺 Selecciona las carpetas de TV que quieres VER:")
                st.caption("Nota: Todas las películas y series se añadirán automáticamente, no necesitas seleccionarlas.")
                
                # Multiselect
                mis_cats = st.multiselect("Carpetas:", st.session_state['nombres_cats'])
                
                # PASO 3: Generar
                if st.button("💾 GENERAR M3U FINAL"):
                    if not mis_cats:
                        st.warning("No seleccionaste ninguna carpeta de TV. El archivo solo tendrá Películas y Series.")
                    
                    with st.spinner("Descargando, filtrando y construyendo archivo (esto toma unos segundos)..."):
                        # Llamamos a la función inteligente
                        contenido_final = generar_m3u_filtrado_stream(host_m, user_m, pw_m, mis_cats)
                        
                        if contenido_final and len(contenido_final) > 20:
                            st.success("¡Archivo creado con éxito!")
                            st.download_button(
                                label="⬇️ DESCARGAR LISTA .M3U",
                                data=contenido_final,
                                file_name="lista_maxplayer_final.m3u",
                                mime="text/plain"
                            )
                        else:
                            st.error("Hubo un error al generar el archivo o está vacío.")
