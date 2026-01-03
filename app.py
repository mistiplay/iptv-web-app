import streamlit as st
import requests
import re
from urllib.parse import urlparse, parse_qs

# CONFIGURACIÓN
st.set_page_config(page_title="IPTV Editor Pro", page_icon="📺", layout="wide")
st.title("📺 IPTV Editor Web")
st.markdown("Modifica solo los **Canales**. Películas y Series se mantienen al 100%.")

# --- FUNCIONES ---

def limpiar_url(url_raw):
    url = url_raw.strip()
    if not url or not url.startswith("http"): return None
    # Estandarizamos para API
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

def descargar_m3u_original(host, user, passw):
    # Construimos la URL para bajar el M3U completo directo del servidor
    # Usamos type=m3u_plus para tener metadatos (logos, grupos)
    url_m3u = f"{host}/get.php?username={user}&password={passw}&type=m3u_plus&output=ts"
    try:
        with st.spinner("⏳ Descargando lista completa del servidor (esto puede tardar si pesa mucho)..."):
            r = requests.get(url_m3u, timeout=60) # 60 segundos timeout para listas grandes
            r.raise_for_status()
            return r.text
    except Exception as e:
        return None

def parsear_y_filtrar(contenido_m3u):
    """
    Separa el contenido en 2 bloques:
    1. Canales en Vivo (Para que el usuario elija)
    2. VOD/Series (Se guardan todos automáticamente)
    """
    lineas = contenido_m3u.splitlines()
    
    items_live = []  # Lista de dicts {info, link, group}
    items_vod = []   # Lista de strings directos (info + link)
    
    buffer_info = ""
    
    # Expresión regular para sacar el group-title="..."
    rx_group = re.compile(r'group-title="([^"]+)"')
    
    for linea in lineas:
        linea = linea.strip()
        if not linea: continue
        
        if linea.startswith("#EXTINF"):
            buffer_info = linea
        elif not linea.startswith("#"):
            # Es un enlace (URL)
            url = linea
            
            # CLASIFICACIÓN CLAVE:
            # Si tiene /live/ es canal. Si tiene /movie/ o /series/ es VOD.
            if "/live/" in url:
                # Es canal en vivo -> Lo procesamos para el selector
                match = rx_group.search(buffer_info)
                grupo = match.group(1) if match else "Sin Categoría"
                
                # Limpieza de nombre para Maxplayer
                # Sacamos el nombre que está después de la última coma
                nombre_sucio = buffer_info.split(',')[-1]
                nombre_limpio = nombre_sucio.replace('"', '').strip()
                
                # Reconstruimos la linea info limpia para evitar errores en Maxplayer
                # Usamos un formato seguro
                info_segura = f'#EXTINF:-1 group-title="{grupo}",{nombre_limpio}'
                
                items_live.append({
                    'group': grupo,
                    'full_entry': f"{info_segura}\r\n{url}", # Guardamos par info+link
                    'name': nombre_limpio
                })
            else:
                # Es Película o Serie -> Lo guardamos TAL CUAL (No lo tocamos)
                # Solo nos aseguramos de usar saltos de línea Windows por si acaso
                items_vod.append(f"{buffer_info}\r\n{url}")
            
            buffer_info = "" # Reset buffer

    return items_live, items_vod

# --- INTERFAZ ---

st.info("Paso 1: Pega tu enlace. Paso 2: Elige categorías de TV. Paso 3: Descarga.")

link_input = st.text_input("Enlace de conexión (M3U o Xtream):")

if link_input:
    url_clean = limpiar_url(link_input)
    if url_clean:
        host, user, passw = extraer_credenciales(url_clean)
        
        if 'm3u_raw' not in st.session_state:
            if st.button("🚀 ANALIZAR MI LISTA"):
                raw_data = descargar_m3u_original(host, user, passw)
                if raw_data:
                    # Parseamos
                    live_objs, vod_list = parsear_y_filtrar(raw_data)
                    st.session_state['live_objs'] = live_objs
                    st.session_state['vod_list'] = vod_list
                    st.success("¡Lista analizada correctamente!")
                else:
                    st.error("No se pudo descargar la lista. Verifica tu conexión o usuario/contraseña.")

        # Si ya tenemos los datos, mostramos el editor
        if 'live_objs' in st.session_state:
            live_items = st.session_state['live_objs']
            vod_items_count = len(st.session_state['vod_list'])
            
            st.write("---")
            # --- PANEL DE ESTADÍSTICAS ---
            c1, c2 = st.columns(2)
            c1.metric("Canales Detectados", len(live_items))
            c2.metric("Pelis/Series Detectadas", vod_items_count, help="Estas se incluirán TODAS automáticamente")
            
            st.write("---")
            st.subheader("📺 Selecciona tus Categorías de TV")
            st.caption("Desmarca lo que NO quieras ver (ej: Países que no te interesan, 24/7, Adultos, etc)")
            
            # Obtener grupos únicos
            grupos_unicos = sorted(list(set([x['group'] for x in live_items])))
            
            # Selector de Grupos (Multiselect)
            # Por defecto seleccionamos TODO para que el usuario quite lo que no quiere
            grupos_seleccionados = st.multiselect(
                "Categorías de Canales:",
                options=grupos_unicos,
                default=grupos_unicos # Marcar todo por defecto
            )
            
            st.write(f"Has seleccionado **{len(grupos_seleccionados)}** categorías de TV.")
            
            if st.button("💾 GENERAR NUEVA LISTA (.m3u)"):
                # 1. Filtramos los canales según los grupos elegidos
                canales_finales = [item['full_entry'] for item in live_items if item['group'] in grupos_seleccionados]
                
                # 2. Unimos: Canales Elegidos + Todo VOD
                # Cabecera obligatoria
                contenido_final = "#EXTM3U\r\n"
                
                # Añadir canales
                for canal in canales_finales:
                    contenido_final += canal + "\r\n"
                    
                # Añadir VOD (Pelis/Series)
                for vod in st.session_state['vod_list']:
                    contenido_final += vod + "\r\n"
                
                # Estadísticas finales
                peso_mb = len(contenido_final) / (1024 * 1024)
                st.success(f"✅ Archivo generado con éxito.")
                st.info(f"📊 Resumen: {len(canales_finales)} Canales + {vod_items_count} VOD/Series.")
                st.warning(f"⚖️ Peso del archivo: {peso_mb:.2f} MB")
                
                st.download_button(
                    label="⬇️ DESCARGAR LISTA MODIFICADA",
                    data=contenido_final,
                    file_name="lista_editada_maxplayer.m3u",
                    mime="text/plain"
                )
                
                if peso_mb > 15:
                    st.error("🚨 CUIDADO: El archivo sigue pesando más de 15MB. Maxplayer podría fallar.")
                    st.write("Sugerencia: Intenta quitar categorías de TV que no uses para bajar el peso.")
