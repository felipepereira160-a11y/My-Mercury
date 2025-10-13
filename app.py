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
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None

# --- Funções de Análise (com cache para economia) ---
@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    # (O código desta função permanece o mesmo)
    pass # Omitido para clareza

# --- Barra Lateral ---
with st.sidebar:
    st.header("Base de Conhecimento")
    map_file = st.file_uploader("1. Upload do Mapeamento (Fixo)", type=["csv", "xlsx"])
    if map_file:
        try:
            if map_file.name.endswith('.csv'):
                 df = pd.read_csv(map_file, encoding='latin-1', sep=',')
            else:
                df = pd.read_excel(map_file)
            st.session_state.df_mapeamento = df
            st.success("Mapeamento carregado!")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")
    # (O resto do código da barra lateral permanece o mesmo)

# --- Corpo Principal ---
if st.session_state.df_dados is not None:
    # (O código do Dashboard de Dados do Dia permanece o mesmo)
    pass

if st.session_state.df_mapeamento is not None:
    st.markdown("---")
    st.success("Base de conhecimento de Representantes está ativa.")
    df_map = st.session_state.df_mapeamento.copy()

    # --- NOVA SEÇÃO: FERRAMENTA DE CONSULTA INTERATIVA (CUSTO ZERO) ---
    st.header("🔎 Ferramenta de Consulta Interativa (Custo Zero)")
    
    # Nomes de coluna corretos
    city_col = 'nm_cidade_atendimento'
    rep_col = 'nm_representante'
    lat_col = 'cd_latitude_atendimento'
    lon_col = 'cd_longitude_atendimento'
    
    if not all(col in df_map.columns for col in [city_col, rep_col, lat_col, lon_col]):
        st.error("A planilha de mapeamento não contém as colunas necessárias (nm_cidade_atendimento, nm_representante, etc.).")
    else:
        # Cria os filtros de busca
        col1, col2 = st.columns(2)
        
        lista_cidades = sorted(df_map[city_col].dropna().unique())
        cidade_selecionada = col1.selectbox("Filtrar por Cidade:", options=lista_cidades, index=None, placeholder="Selecione uma cidade")
        
        lista_reps = sorted(df_map[rep_col].dropna().unique())
        rep_selecionado = col2.selectbox("Filtrar por Representante:", options=lista_reps, index=None, placeholder="Selecione um representante")

        # Aplica o filtro selecionado
        filtered_df = df_map
        if cidade_selecionada:
            filtered_df = df_map[df_map[city_col] == cidade_selecionada]
        elif rep_selecionado:
            filtered_df = df_map[df_map[rep_col] == rep_selecionado]

        # Exibe a tabela com os resultados filtrados
        st.write("Resultados da busca:")
        st.dataframe(filtered_df)

        # --- MAPA INTERATIVO ---
        st.write("Visualização no Mapa:")
        
        # Limpa os dados de coordenadas
        filtered_df[lat_col] = pd.to_numeric(filtered_df[lat_col], errors='coerce')
        filtered_df[lon_col] = pd.to_numeric(filtered_df[lon_col], errors='coerce')
        filtered_df.dropna(subset=[lat_col, lon_col], inplace=True)
        filtered_df.rename(columns={lat_col: 'lat', lon_col: 'lon'}, inplace=True)

        if not filtered_df.empty:
            # Ajusta o zoom do mapa com base no filtro
            if cidade_selecionada or len(filtered_df) == 1:
                zoom_level = 10 # Zoom maior para uma única cidade
            else:
                zoom_level = 4 # Zoom menor para ver o Brasil todo

            st.pydeck_chart(pdk.Deck(
                map_style='mapbox://styles/mapbox/satellite-streets-v11',
                initial_view_state=pdk.ViewState(
                    latitude=filtered_df['lat'].mean(),
                    longitude=filtered_df['lon'].mean(),
                    zoom=zoom_level,
                    pitch=45,
                ),
                layers=[
                    pdk.Layer('ScatterplotLayer', data=filtered_df, get_position='[lon, lat]', get_color='[200, 30, 0, 160]', get_radius=15000, pickable=True)
                ],
                tooltip={"html": f"<b>Cidade:</b> {{{city_col}}}<br/><b>Representante:</b> {{{rep_col}}}<br/><b>Distância:</b> {{{'qt_distancia_atendimento_km'}}} km"}
            ))
        else:
            st.warning("Nenhum resultado encontrado com os filtros aplicados.")

    st.markdown("---")


st.header("Converse com a IA")
# (O resto do seu código, com o histórico do chat e a lógica de entrada, permanece o mesmo)
# ...
