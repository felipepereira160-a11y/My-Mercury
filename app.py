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

# --- Barra Lateral ---
with st.sidebar:
    st.header("Base de Conhecimento")
    map_file = st.file_uploader("1. Upload do Mapeamento (Fixo)", type=["csv", "xlsx"])
    if map_file:
        try:
            if map_file.name.endswith('.csv'):
                 df = pd.read_csv(map_file, encoding='latin-1', sep=',')
            else: # Para arquivos .xlsx
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

# --- Corpo Principal ---
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
    df_map = st.session_state.df_mapeamento.copy()

    st.header("🔎 Ferramenta de Consulta Rápida (Custo Zero)")
    city_col_map = 'nm_cidade_atendimento'
    if city_col_map in df_map.columns:
        lista_cidades = sorted(df_map[city_col_map].dropna().unique())
        cidade_selecionada = st.selectbox("Selecione uma cidade para encontrar o representante:", options=lista_cidades, index=None, placeholder="Escolha uma cidade")
        if cidade_selecionada:
            resultado_busca = df_map[df_map[city_col_map] == cidade_selecionada]
            st.write(f"Resultado(s) para **{cidade_selecionada}**:")
            st.dataframe(resultado_busca)
    else:
        st.warning(f"A coluna '{city_col_map}' não foi encontrada na sua planilha de mapeamento para a consulta rápida.")
    
    # --- LÓGICA DO MAPA (COM TOOLTIP MELHORADO) ---
    if st.button("Visualizar Mapa de Atendimento"):
        lat_col = 'cd_latitude_atendimento'
        lon_col = 'cd_longitude_atendimento'
        city_col = 'nm_cidade_atendimento'
        rep_col = 'nm_representante'
        km_col = 'qt_distancia_atendimento_km' # Nova coluna para a distância

        if not all(col in df_map.columns for col in [lat_col, lon_col, city_col, rep_col, km_col]):
            st.error("Sua planilha de mapeamento não contém todas as colunas necessárias (representante, cidade, latitude, longitude, km) para gerar o mapa.")
        else:
            df_map[lat_col] = pd.to_numeric(df_map[lat_col], errors='coerce')
            df_map[lon_col] = pd.to_numeric(df_map[lon_col], errors='coerce')
            df_map.dropna(subset=[lat_col, lon_col], inplace=True)
            df_map.rename(columns={lat_col: 'lat', lon_col: 'lon'}, inplace=True)

            if not df_map.empty:
                st.pydeck_chart(pdk.Deck(
                    map_style='mapbox://styles/mapbox/satellite-streets-v11',
                    initial_view_state=pdk.ViewState(latitude=df_map['lat'].mean(), longitude=df_map['lon'].mean(), zoom=4, pitch=45),
                    layers=[
                        pdk.Layer('ScatterplotLayer', data=df_map, get_position='[lon, lat]', get_color='[200, 30, 0, 160]', get_radius=15000, pickable=True)
                    ],
                    # --- TOOLTIP ATUALIZADO ---
                    tooltip={
                        "html": f"<b>Cidade:</b> {{{city_col}}}<br/>"
                                f"<b>Representante:</b> {{{rep_col}}}<br/>"
                                f"<b>Distância:</b> {{{km_col}}} km"
                    }
                ))
            else:
                st.warning("Não foram encontradas coordenadas válidas na planilha de mapeamento.")
    st.markdown("---")


st.header("Converse com a IA")
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

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
