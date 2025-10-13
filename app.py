import streamlit as st
import google.generativeai as genai
import pandas as pd
import pydeck as pdk
import time

st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")
st.title("🧠 Seu Assistente de Dados com IA")
st.write("Converse comigo ou faça o upload de seus arquivos na barra lateral para começar a analisar!")

try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-pro-latest')
except Exception as e:
    st.error("Chave de API do Google não configurada ou inválida.")
    st.stop()

if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None

@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    contexto = "analisar dados de ordens de serviço." if df_type == 'dados' else "buscar informações sobre representantes."
    time.sleep(1)
    prompt_engenharia = f"""
    Sua tarefa é converter uma pergunta em uma única linha de código Pandas para {contexto}
    O dataframe é `df`. As colunas são: {', '.join(df.columns)}.
    Pergunta: "{pergunta}"
    Gere apenas a linha de código Pandas.
    """
    try:
        code_response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        codigo_pandas = code_response.text.strip().replace('`', '').replace('python', '').strip()
        resultado = eval(codigo_pandas, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

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
    st.markdown("---")
    data_file = st.sidebar.file_uploader("2. Upload dos Dados do Dia (Variável)", type=["csv", "xlsx"])
    if data_file:
        try:
            if data_file.name.endswith('.csv'):
                df = pd.read_csv(data_file, encoding='latin-1', sep=';', on_bad_lines='skip')
            else:
                df = pd.read_excel(data_file)
            st.session_state.df_dados = df
            st.success("Dados carregados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")
    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

if st.session_state.df_dados is not None:
    df = st.session_state.df_dados
    st.header("Dashboard dos Dados do Dia")
    st.subheader("Análises Frequentes (Custo Zero de IA)")
    b_col1, b_col2, b_col3 = st.columns(3)
    if b_col1.button("Contagem por Status"):
        st.write("Resultado da Análise:")
        st.bar_chart(df['Status'].value_counts())
    st.markdown("---")

if st.session_state.df_mapeamento is not None:
    st.success("Base de conhecimento de Representantes está ativa.")
    df_map = st.session_state.df_mapeamento
    st.markdown("---")
    st.header("🔎 Ferramenta de Consulta Rápida (Custo Zero)")
    city_col_map = next((col for col in df_map.columns if 'cidade' in col.lower() and 'atendimento' in col.lower()), None)
    if city_col_map:
        lista_cidades = sorted(df_map[city_col_map].dropna().unique())
        cidade_selecionada = st.selectbox("Selecione uma cidade para encontrar o representante:", options=lista_cidades, index=None, placeholder="Escolha uma cidade")
        if cidade_selecionada:
            resultado_busca = df_map[df_map[city_col_map] == cidade_selecionada]
            st.write(f"Resultado(s) para **{cidade_selecionada}**:")
            st.dataframe(resultado_busca)
    else:
        st.warning("Não foi possível encontrar uma coluna de 'cidade de atendimento' na sua planilha de mapeamento para a consulta rápida.")
    
    if st.button("Visualizar Mapa de Atendimento"):
        map_df = st.session_state.df_mapeamento.copy()
        lat_col = next((col for col in map_df.columns if 'latitude' in col.lower() and 'atendimento' in col.lower()), None)
        lon_col = next((col for col in map_df.columns if 'longitude' in col.lower() and 'atendimento' in col.lower()), None)
        city_col = next((col for col in map_df.columns if 'cidade' in col.lower() and 'atendimento' in col.lower()), None)
        rep_col = next((col for col in map_df.columns if 'representante' in col.lower()), None)
        if not all([lat_col, lon_col, city_col, rep_col]):
            st.error("Não foi possível encontrar as colunas necessárias (latitude, longitude, cidade, representante) para gerar o mapa.")
        else:
            map_df[lat_col] = pd.to_numeric(map_df[lat_col], errors='coerce')
            map_df[lon_col] = pd.to_numeric(map_df[lon_col], errors='coerce')
            map_df.dropna(subset=[lat_col, lon_col], inplace=True)
            map_df.rename(columns={lat_col: 'lat', lon_col: 'lon'}, inplace=True)
            if not map_df.empty:
                st.pydeck_chart(pdk.Deck(map_style='mapbox://styles/mapbox/light-v9', initial_view_state=pdk.ViewState(latitude=map_df['lat'].mean(), longitude=map_df['lon'].mean(), zoom=4, pitch=50), layers=[pdk.Layer('HexagonLayer', data=map_df, get_position='[lon, lat]', radius=20000, elevation_scale=4, elevation_range=[0, 1000], pickable=True, extruded=True)], tooltip={"text": f"Cidade: {{{city_col}}}\nRepresentante: {{{rep_col}}}"}))
            else:
                st.warning("Não foram encontradas coordenadas válidas para gerar o mapa.")
    st.markdown("---")

st.header("Converse com a IA")
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta..."):
    # (A lógica de chat e roteamento de custo zero permanece a mesma)
    pass # Omitido para clareza
