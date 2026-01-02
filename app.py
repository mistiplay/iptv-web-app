import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# Configuración de la página (debe ser lo primero)
st.set_page_config(page_title="IPTV Tool Pro", page_icon="📺", layout="wide")

st.title("📺 IPTV Tool Web")
st.markdown("Verificador de estado y buscador de contenido **sin bloqueos**.")

# --- FUNCIONES ---

def limpiar_url(url_raw):
    """Limpia el enlace para asegurar que apunta al API."""
    url = url_raw.strip()
    if not url or not url.startswith("http"):
        return None
    # Estandarizamos a player_api para extraer datos fácilmente
    url_final = url.replace("/get.php", "/player_api.php").replace("/xmltv.php", "/player_api.php")
    return url_final

def extraer_credenciales(url_api):
    """Intenta sacar host, usuario y pass del enlace."""
    try:
        parsed = urlparse(url_api)
        host = f"{parsed.scheme}://{parsed.netloc}"
        params = parse_qs(parsed.query)
        username = params.get('username', [''])[0]
        password = params.get('password', [''])[0]
        if not username or not password:
            return None, None, None
        return host, username, password
    except:
        return None, None, None

def verificar_url(url_raw):
    """Función de verificación de cuenta (Pestañas 1 y 2)."""
    url_final = limpiar_url(url_raw)
    if not url_final: return None

    try:
        response = requests.get(url_final, timeout=15)
        if response.status_code != 200:
            return {"Usuario": "Error HTTP", "Estado": f"Error {response.status_code}", "Vence": "-", "Conexiones": "-"}

        try: data = response.json()
        except: return {"Usuario": "Error", "Estado": "No es un panel JSON", "Vence": "-", "Conexiones": "-"}
        
        if 'user_info' not in data:
            return {"Usuario": "Invalido", "Estado": "Credenciales malas", "Vence": "-", "Conexiones": "-"}

        info = data['user_info']
        timestamp = info.get('exp_date')
        if timestamp and timestamp != 'null':
            try: fecha = datetime.fromtimestamp(int(timestamp)).strftime('%d/%m/%Y')
            except: fecha = "Error fecha"
        else:
            fecha = "Ilimitada"

        return {
            "Usuario": info.get('username', 'Desconocido'),
            "Estado": "✅ Activa" if info.get('status') == 'Active' else f"❌ {info.get('status')}",
            "Vence": fecha,
            "Conexiones": f"{info.get('active_cons', 0)} / {info.get('max_connections', 0)}"
        }
    except requests.exceptions.RequestException:
        return {"Usuario": "Error", "Estado": "Timeout/Caído", "Vence": "-", "Conexiones": "-"}

def obtener_peliculas_vod(url_raw):
    """Función nueva para descargar la lista de películas."""
    url_api = limpiar_url(url_raw)
    if not url_api: return None, "URL inválida"

    host, user, password = extraer_credenciales(url_api)
    if not user: return None, "No se pudieron extraer usuario/contraseña del enlace."

    # Construimos la URL específica que pide la lista de películas (action=get_vod_streams)
    api_vod_url = f"{host}/player_api.php?username={user}&password={password}&action=get_vod_streams"

    try:
        with st.spinner("Conectando al servidor y descargando catálogo... (esto puede tardar si son muchas)"):
            response = requests.get(api_vod_url, timeout=30) # Más tiempo de espera
            if response.status_code != 200:
                return None, f"Error del servidor: {response.status_code}"
            
            data_vod = response.json()
            if not data_vod or not isinstance(data_vod, list):
                 return None, "El servidor no devolvió una lista de películas válida o no tiene VOD."

            # Procesamos la lista
            lista_procesada = []
            for item in data_vod:
                # Construimos el enlace directo de descarga
                stream_id = item.get('stream_id')
                ext = item.get('container_extension', 'mp4')
                nombre = item.get('name', 'Sin nombre')
                
                if stream_id:
                    # Estructura: http://host/movie/user/pass/ID.ext
                    download_link = f"{host}/movie/{user}/{password}/{stream_id}.{ext}"
                    
                    lista_procesada.append({
                        "Nombre de la Película": nombre,
                        "Formato": ext.upper(),
                        "Enlace de Descarga": download_link
                    })
            
            if not lista_procesada:
                 return None, "Se encontró el catálogo pero estaba vacío."

            return pd.DataFrame(lista_procesada), None

    except Exception as e:
        return None, f"Error de conexión: {e}"

# --- INTERFAZ ---

# Creamos 3 pestañas ahora
tab1, tab2, tab3 = st.tabs(["🔍 Verificar Cuenta", "📋 Verificar Masivo", "📥 Descargar Películas (NUEVO)"])

# Pestaña 1: Verificación individual (Igual que antes)
with tab1:
    url_input = st.text_input("Pega el enlace de conexión aquí:", key="t1_input")
    if st.button("Verificar Estado", type="primary", key="t1_btn"):
        if url_input:
            with st.spinner('Comprobando...'):
                resultado = verificar_url(url_input)
                if resultado and resultado["Estado"] != "Error":
                    if "Activa" in resultado["Estado"]:
                        st.success(f"**Usuario:** {resultado['Usuario']}")
                    else:
                        st.error(f"**Usuario:** {resultado['Usuario']}")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Estado", resultado["Estado"])
                    c2.metric("Vencimiento", resultado["Vence"])
                    c3.metric("Conexiones", resultado["Conexiones"])
                else:
                    st.warning("No se pudo conectar o enlace no válido.")

# Pestaña 2: Masivo (Igual que antes)
with tab2:
    st.write("Pega muchas cuentas (una por línea):")
    text_area = st.text_area("Lista de URLs", height=150, key="t2_area")
    if st.button("Verificar Lista Masiva", key="t2_btn"):
        if text_area:
            urls = text_area.split('\n')
            resultados = []
            progreso = st.progress(0)
            for i, linea in enumerate(urls):
                if len(linea) > 10:
                    res = verificar_url(linea)
                    if res:
                        resultados.append(res)
                progreso.progress((i + 1) / len(urls))
            if resultados:
                st.dataframe(pd.DataFrame(resultados), use_container_width=True)
            else:
                st.info("No se encontraron enlaces válidos.")

# Pestaña 3: Descargas (LA NUEVA)
with tab3:
    st.header("Buscador de Películas VOD")
    st.info("Pega tu enlace de conexión normal. La app extraerá el catálogo y generará los enlaces de descarga directa.")
    
    url_vod_input = st.text_input("Pega el enlace de conexión aquí:", key="t3_input")
    
    if st.button("🔎 Obtener Lista de Películas", type="primary", key="t3_btn"):
        if len(url_vod_input) > 10:
            df_peliculas, error = obtener_peliculas_vod(url_vod_input)
            
            if error:
                st.error(error)
            elif df_peliculas is not None and not df_peliculas.empty:
                st.success(f"✅ Se encontraron {len(df_peliculas)} películas.")
                st.write("Utiliza la lupa 🔍 en la esquina superior derecha de la tabla para buscar.")
                
                # Mostramos la tabla interactiva configurando la columna de enlaces
                st.dataframe(
                    df_peliculas,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Enlace de Descarga": st.column_config.LinkColumn(
                            "Descargar",
                            help="Haz clic para abrir el video directo",
                            validate="^http",
                            display_text="⬇️ Abrir Video"
                        )
                    }
                )
            else:
                 st.warning("Algo salió mal. No se obtuvieron datos.")
        else:
            st.warning("Pega un enlace válido primero.")
