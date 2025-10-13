import streamlit as st
import google.generativeai as genai
import pandas as pd
import pydeck as pdk
import time

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Seu Assistente de Dados com IA")
st.write("Converse comigo ou faça o upload de seus arquivos na barra lateral para começar a analisar!")

# --- Configuração da API e do Modelo ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-pro-latest')
except Exception as e:
    st.error("Chave de API do Google não configurada ou inválida.")
    st.stop()

# --- Inicialização do Estado da Sessão ---
# (O código de inicialização do session_state permanece o mesmo)
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None

# --- Funções de Análise (sem alterações) ---
# (A função 'executar_analise_pandas' permanece a mesma)

# --- Barra Lateral (sem alterações) ---
with st.sidebar:
    st.header("Base de Conhecimento")
    # (O código da barra lateral permanece o mesmo)

# --- Corpo Principal ---
if st.session_state.df_dados is not None:
    # (O código do dashboard permanece o mesmo)
    pass

if st.session_state.df_mapeamento is not None:
    st.success("Base de conhecimento de Representantes está ativa.")
    
    # --- LÓGICA DO MAPA ATUALIZADA ---
    if st.button("Visualizar Mapa de Atendimento"):
        map_df = st.session_state.df_mapeamento.copy()

        # Encontra dinamicamente as colunas necessárias
        lat_col = next((col for col in map_df.columns if 'latitude' in col.lower() and 'atendimento' in col.lower()), None)
        lon_col = next((col for col in map_df.columns if 'longitude' in col.lower() and 'atendimento' in col.lower()), None)
        city_col = next((col for col in map_df.columns if 'cidade' in col.lower() and 'atendimento' in col.lower()), None)
        rep_col = next((col for col in map_df.columns if 'representante' in col.lower()), None)
        
        # Verifica se todas as colunas foram encontradas
        if not all([lat_col, lon_col, city_col, rep_col]):
            st.error("Não foi possível encontrar as colunas necessárias (latitude, longitude, cidade, representante) na sua planilha. Verifique os nomes das colunas.")
        else:
            # Garante que as colunas de coordenadas sejam numéricas
            map_df[lat_col] = pd.to_numeric(map_df[lat_col], errors='coerce')
            map_df[lon_col] = pd.to_numeric(map_df[lon_col], errors='coerce')
            map_df.dropna(subset=[lat_col, lon_col], inplace=True)
            
            # Renomeia as colunas para um padrão ('lat', 'lon') para facilitar o uso no pydeck
            map_df.rename(columns={lat_col: 'lat', lon_col: 'lon'}, inplace=True)

            if not map_df.empty:
                st.pydeck_chart(pdk.Deck(
                    map_style='mapbox://styles/mapbox/light-v9',
                    initial_view_state=pdk.ViewState(
                        latitude=map_df['lat'].mean(),
                        longitude=map_df['lon'].mean(),
                        zoom=4,
                        pitch=50,
                    ),
                    layers=[
                        pdk.Layer(
                           'HexagonLayer',
                           data=map_df,
                           get_position='[lon, lat]', # Usa os nomes padronizados
                           radius=20000,
                           elevation_scale=4,
                           elevation_range=[0, 1000],
                           pickable=True,
                           extruded=True,
                        ),
                    ],
                    # Usa f-string para construir o tooltip dinamicamente
                    tooltip={"text": f"Cidade: {{{city_col}}}\nRepresentante: {{{rep_col}}}"}
                ))
            else:
                st.warning("Não foram encontradas coordenadas válidas na planilha de mapeamento.")

st.header("Converse com a IA")
# (O resto do seu código, com o histórico do chat e a lógica de entrada, permanece o mesmo)
# ...
st.header("Converse com a IA")
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Lógica de Entrada do Usuário com Roteador de Custo Zero ---
if prompt := st.chat_input("Faça uma pergunta..."):
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    keywords_mapeamento = ["quem atende", "representante de", "contato do rt", "telefone de", "rt para", "mapeamento"]
    df_type = 'chat'
    if any(keyword in prompt.lower() for keyword in keywords_mapeamento) and st.session_state.df_mapeamento is not None:
        df_type = 'mapeamento'
    elif st.session_state.df_dados is not None:
        df_type = 'dados'

    with st.chat_message("assistant"):
        if df_type in ['mapeamento', 'dados']:
            with st.spinner(f"Analisando no arquivo de '{df_type}'..."):
                df_hash = pd.util.hash_pandas_object(st.session_state.get(f"df_{df_type}")).sum()
                resultado_analise, erro = executar_analise_pandas(df_hash, prompt, df_type)
                if erro:
                    st.error(erro)
                    response_text = "Desculpe, não consegui analisar os dados."
                else:
                    if isinstance(resultado_analise, (pd.Series, pd.DataFrame)):
                        st.write(f"Resultado da busca na base de '{df_type}':")
                        st.dataframe(resultado_analise)
                        response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
                st.markdown(response_text)
        else:
            with st.spinner("Pensando..."):
                response = st.session_state.chat.send_message(prompt)
                response_text = response.text
                st.markdown(response_text)
    
    st.session_state.display_history.append({"role": "assistant", "content": response_text})
