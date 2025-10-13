import streamlit as st
import google.generativeai as genai
import pandas as pd
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

if st.session_state.df_mapeamento is not None:
    st.markdown("---")
    st.success("Base de conhecimento de Representantes está ativa.")
    df_map = st.session_state.df_mapeamento.copy()

    st.header("🔎 Ferramenta de Consulta Interativa (Custo Zero)")
    
    city_col = 'nm_cidade_atendimento'
    rep_col = 'nm_representante'
    lat_col = 'cd_latitude_atendimento'
    lon_col = 'cd_longitude_atendimento'
    
    if not all(col in df_map.columns for col in [city_col, rep_col, lat_col, lon_col]):
        st.error("A planilha de mapeamento não contém as colunas necessárias (cidade, representante, latitude, longitude).")
    else:
        col1, col2 = st.columns(2)
        lista_cidades = sorted(df_map[city_col].dropna().unique())
        cidade_selecionada = col1.selectbox("Filtrar por Cidade:", options=lista_cidades, index=None, placeholder="Selecione uma cidade")
        lista_reps = sorted(df_map[rep_col].dropna().unique())
        rep_selecionado = col2.selectbox("Filtrar por Representante:", options=lista_reps, index=None, placeholder="Selecione um representante")

        filtered_df = df_map
        if cidade_selecionada:
            filtered_df = df_map[df_map[city_col] == cidade_selecionada]
        elif rep_selecionado:
            filtered_df = df_map[df_map[rep_col] == rep_selecionado]

        st.write("Resultados da busca:")
        st.dataframe(filtered_df)

        st.write("Visualização no Mapa:")
        
        map_data = filtered_df.copy()
        map_data = map_data.rename(columns={lat_col: 'lat', lon_col: 'lon'})
        map_data['lat'] = pd.to_numeric(map_data['lat'], errors='coerce')
        map_data['lon'] = pd.to_numeric(map_data['lon'], errors='coerce')
        map_data.dropna(subset=['lat', 'lon'], inplace=True)

        if not map_data.empty:
            st.map(map_data)
        else:
            st.warning("Nenhum resultado com coordenadas válidas para exibir no mapa.")
    st.markdown("---")

st.header("Converse com a IA")
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta..."):
    # (A lógica de chat e roteamento de custo zero permanece a mesma)
    pass
