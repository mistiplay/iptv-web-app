# --- PESTAÑA 4: MULTI-FORMATO + VISOR DE TEXTO ---
with tab4:
    st.header("🛠️ Crear M3U (Descargar o Copiar)")
    st.info("Selecciona canales. Usa los botones para descargar archivo, o copia el texto de abajo para Rentry.")
    
    link_m3u = st.text_input("Pega tu cuenta:", key="m3u_input")
    
    if link_m3u:
        url_c = limpiar_url(link_m3u)
        if url_c:
            host_m, user_m, pw_m = extraer_credenciales(url_c)
            
            if st.button("📡 Cargar Canales"):
                with st.spinner("Descargando lista..."):
                    st.session_state['todos_canales'] = obtener_canales_live(host_m, user_m, pw_m)
                    
            if 'todos_canales' in st.session_state:
                todos = st.session_state['todos_canales']
                mapa = {c['name']: c for c in todos}
                nombres = list(mapa.keys())
                
                st.write("---")
                seleccionados = st.multiselect("Selecciona los canales:", options=nombres)
                
                if seleccionados:
                    st.success(f"Seleccionaste {len(seleccionados)} canales.")
                    objs = [mapa[n] for n in seleccionados]
                    
                    # Generamos la versión Minimalista (La más compatible para copiar)
                    contenido_final = generar_m3u_v3_minimal(objs, host_m, user_m, pw_m)
                    
                    st.write("👇 **Opciones de Descarga:**")
                    colA, colB = st.columns(2)
                    with colA:
                        st.download_button("⬇️ Descargar Archivo .m3u", contenido_final, "lista_maxplayer.m3u")
                    
                    st.write("---")
                    st.subheader("📝 Copiar Texto (Para Rentry/Pastebin)")
                    st.write("Copia todo este código y pégalo en rentry.co para obtener tu URL:")
                    
                    # AQUÍ ESTÁ EL CUADRO NEGRO QUE FALTABA
                    st.code(contenido_final, language="text")
