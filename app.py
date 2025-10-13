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

# --- Funções de Análise ---
@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    
    if df_type == 'dados':
        contexto = "analisar dados de ordens de serviço."
        prompt_engenharia = f"""
        Sua tarefa é converter uma pergunta em uma única linha de código Pandas para {contexto}
        O dataframe é `df`. As colunas são: {', '.join(df.columns)}.
        REGRAS: Se a pergunta for sobre status (agendadas, realizadas, etc.), filtre a coluna 'Status'.
        Pergunta: "{pergunta}"
        Gere apenas a linha de código Pandas.
        """
    else: # Mapeamento
        contexto = "buscar informações sobre representantes em uma planilha de mapeamento."
        prompt_engenharia = f"""
        Sua tarefa é converter uma pergunta em uma única linha de código Pandas para {contexto}
        O dataframe é `df`. As colunas importantes são 'nm_representante', 'nm_cidade_atendimento', 'qt_distancia_atendimento_km', e o telefone.
        Pergunta: "{pergunta}"
        Gere apenas a linha de código Pandas. Exemplo: Para "quem atende Santos", a resposta deve ser df[df['nm_cidade_atendimento'] == 'Santos']
        """

    time.sleep(1)
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
            else:
                df = pd.read_excel(map_file)
            st.session_state.df_mapeamento = df
            st.success("Mapeamento carregado!")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")
    # (Resto da barra lateral)
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
    # (Dashboard dos Dados do Dia)
    pass

if st.session_state.df_mapeamento is not None:
    st.markdown("---")
    st.success("Base de conhecimento de Representantes está ativa.")
    df_map = st.session_state.df_mapeamento.copy()

    # --- FERRAMENTA DE CONSULTA RÁPIDA (CORRIGIDA) ---
    st.header("🔎 Ferramenta de Consulta Rápida (Custo Zero)")
    
    # Usa o nome de coluna correto que você informou
    city_col_map = 'nm_cidade_atendimento'

    if city_col_map in df_map.columns:
        lista_cidades = sorted(df_map[city_col_map].dropna().unique())
        cidade_selecionada = st.selectbox("Selecione uma cidade para encontrar o representante:", options=lista_cidades, index=None, placeholder="Escolha uma cidade")
        if cidade_selecionada:
            resultado_busca = df_map[df_map[city_col_map] == cidade_selecionada]
            st.write(f"Resultado(s) para **{cidade_selecionada}**:")
            st.dataframe(resultado_busca)
    else:
        st.warning(f"A coluna '{city_col_map}' não foi encontrada na sua planilha de mapeamento.")

    # --- LÓGICA DO MAPA (CORRIGIDA) ---
    if st.button("Visualizar Mapa de Atendimento"):
        # Usa os nomes de coluna corretos que você informou
        lat_col = 'cd_latitude_atendimento'
        lon_col = 'cd_longitude_atendimento'
        city_col = 'nm_cidade_atendimento'
        rep_col = 'nm_representante'
        
        if not all(col in df_map.columns for col in [lat_col, lon_col, city_col, rep_col]):
            st.error("Sua planilha de mapeamento não contém as colunas necessárias (nm_representante, nm_cidade_atendimento, cd_latitude_atendimento, cd_longitude_atendimento) para gerar o mapa.")
        else:
            df_map[lat_col] = pd.to_numeric(df_map[lat_col], errors='coerce')
            df_map[lon_col] = pd.to_numeric(df_map[lon_col], errors='coerce')
            df_map.dropna(subset=[lat_col, lon_col], inplace=True)
            df_map.rename(columns={lat_col: 'lat', lon_col: 'lon'}, inplace=True)

            if not df_map.empty:
                st.pydeck_chart(pdk.Deck(
                    map_style='mapbox://styles/mapbox/light-v9',
                    initial_view_state=pdk.ViewState(latitude=df_map['lat'].mean(), longitude=df_map['lon'].mean(), zoom=4, pitch=50),
                    layers=[pdk.Layer('HexagonLayer', data=df_map, get_position='[lon, lat]', radius=20000, elevation_scale=4, elevation_range=[0, 1000], pickable=True, extruded=True)],
                    tooltip={"text": f"Cidade: {{{city_col}}}\nRepresentante: {{{rep_col}}}"}
                ))
            else:
                st.warning("Não foram encontradas coordenadas válidas na planilha de mapeamento.")
    st.markdown("---")

st.header("Converse com a IA")
# (O resto do código, com o histórico do chat e a lógica de entrada, permanece o mesmo)
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta..."):
    # (A lógica de chat e roteamento de custo zero permanece a mesma)
    pass
