# --- Pestaña 3 MODIFICADA CON BUSCADOR INTELIGENTE ---
with tab3:
    st.header("Buscador de Contenido y Descargas")
    link_vod = st.text_input("Pega el enlace de tu cuenta:", key="vod_input")
    
    # Selector de Tipo
    tipo = st.radio("¿Qué quieres buscar?", ["🎬 Películas", "📺 Series"], horizontal=True)

    if link_vod:
        # Preparamos credenciales
        url_clean = limpiar_url(link_vod)
        if url_clean:
            host, user, pw = extraer_credenciales(url_clean)

            # --- SECCIÓN PELÍCULAS ---
            if tipo == "🎬 Películas":
                if st.button("Cargar Catálogo de Películas"):
                    with st.spinner("Descargando lista..."):
                        # Guardamos en session_state para que no se borre al buscar
                        st.session_state['df_pelis'] = obtener_peliculas(url_clean, host, user, pw)
                
                # Si ya tenemos las películas en memoria
                if 'df_pelis' in st.session_state and st.session_state['df_pelis'] is not None:
                    df = st.session_state['df_pelis']
                    
                    # 🔍 EL BUSCADOR DE FILTRO
                    busqueda = st.text_input("🔍 Buscar película por nombre:", placeholder="Escribe aquí (ej: Matrix)")
                    
                    if busqueda:
                        # Filtramos la tabla para que SOLO muestre lo que coincide
                        # case=False hace que no importen mayúsculas/minúsculas
                        df_filtrado = df[df['Título'].str.contains(busqueda, case=False, na=False)]
                    else:
                        # Si no escriben nada, mostramos todo (o podrías poner df.head(0) para ocultar)
                        df_filtrado = df

                    st.write(f"Mostrando {len(df_filtrado)} resultados:")
                    
                    st.dataframe(
                        df_filtrado, 
                        use_container_width=True, 
                        hide_index=True,
                        column_config={"Link": st.column_config.LinkColumn("Descargar", display_text="⬇️ Bajar")}
                    )

            # --- SECCIÓN SERIES ---
            elif tipo == "📺 Series":
                # 1. Cargar lista de Series
                if 'lista_series' not in st.session_state:
                    if st.button("1️⃣ Cargar Catálogo de Series"):
                        with st.spinner("Leyendo todas las series..."):
                            series_dict = obtener_lista_series(url_clean, host, user, pw)
                            if series_dict:
                                st.session_state['lista_series'] = series_dict
                                st.rerun()
                
                # 2. Selector de Serie
                if 'lista_series' in st.session_state:
                    series_nombres = list(st.session_state['lista_series'].keys())
                    # El selectbox ya tiene buscador integrado (puedes escribir dentro)
                    seleccion = st.selectbox("Selecciona la Serie (Escribe para buscar):", series_nombres)
                    
                    if st.button(f"2️⃣ Ver Episodios de: {seleccion}"):
                        id_serie = st.session_state['lista_series'][seleccion]
                        with st.spinner(f"Buscando episodios..."):
                            st.session_state['df_episodios'] = obtener_episodios(host, user, pw, id_serie)
                    
                    # 3. Mostrar Episodios con filtro
                    if 'df_episodios' in st.session_state and st.session_state['df_episodios'] is not None:
                        df_eps = st.session_state['df_episodios']
                        
                        # Filtro opcional para episodios (útil si son 100 capitulos)
                        filtro_ep = st.text_input("Filtrar episodio:", placeholder="Ej: T1 E5")
                        if filtro_ep:
                            df_eps_final = df_eps[df_eps['Episodio'].str.contains(filtro_ep, case=False)]
                        else:
                            df_eps_final = df_eps
                            
                        st.dataframe(
                            df_eps_final, 
                            use_container_width=True, 
                            hide_index=True,
                            column_config={"Link": st.column_config.LinkColumn("Descargar", display_text="⬇️ Bajar Episodio")}
                        )

                    # Botón para limpiar
                    if st.button("🔄 Nueva Búsqueda"):
                        for key in ['lista_series', 'df_episodios']:
                            if key in st.session_state: del st.session_state[key]
                        st.rerun()
