import streamlit as st
import google.generativeai as genai
import pandas as pd
import time

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Brain")
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
if 'df_dados' not in st.session_state: # Dataframe para dados variáveis
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state: # Dataframe para o mapeamento fixo
    st.session_state.df_mapeamento = None


# --- Funções de Análise (movidas para o topo para melhor organização) ---
@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type='dados'):
    # Seleciona o dataframe correto para a análise
    if df_type == 'mapeamento' and st.session_state.df_mapeamento is not None:
        df = st.session_state.df_mapeamento
        prompt_contexto = "Sua tarefa é buscar informações sobre representantes em uma planilha de mapeamento."
    elif st.session_state.df_dados is not None:
        df = st.session_state.df_dados
        prompt_contexto = "Sua tarefa é analisar dados de ordens de serviço."
    else:
        return None, "Nenhum dataframe carregado para análise."

    time.sleep(1)
    prompt_engenharia = f"""
    {prompt_contexto}
    O dataframe é `df`. As colunas são: {', '.join(df.columns)}.
    Pergunta: "{pergunta}"
    Gere apenas a linha de código Pandas necessária para responder à pergunta.
    """
    try:
        code_response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        codigo_pandas = code_response.text.strip().replace('`', '').replace('python', '').strip()
        resultado = eval(codigo_pandas, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

# --- Barra Lateral com Dois Uploaders ---
with st.sidebar:
    st.header("Base de Conhecimento")
    
    # Uploader para o mapeamento fixo
    map_file = st.file_uploader("1. Upload do Mapeamento de Representantes (Fixo)", type=["csv", "xlsx"])
    if map_file:
        try:
            if map_file.name.endswith('.csv'):
                st.session_state.df_mapeamento = pd.read_csv(map_file, encoding='latin-1', sep=';', on_bad_lines='skip')
            else:
                st.session_state.df_mapeamento = pd.read_excel(map_file)
            st.success("Mapeamento carregado!")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")

    st.markdown("---")
    
    # Uploader para os dados do dia a dia
    data_file = st.sidebar.file_uploader("2. Upload dos Dados do Dia (Variável)", type=["csv", "xlsx"])
    if data_file:
        try:
            if data_file.name.endswith('.csv'):
                st.session_state.df_dados = pd.read_csv(data_file, encoding='latin-1', sep=';', on_bad_lines='skip')
            else:
                st.session_state.df_dados = pd.read_excel(data_file)
            st.success("Dados carregados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")

    if st.button("Limpar Tudo"):
        st.session_state.df_dados = None
        st.session_state.df_mapeamento = None
        st.session_state.chat = model.start_chat(history=[])
        st.session_state.display_history = []
        st.rerun()

# --- Corpo Principal ---
# Exibe o dashboard apenas se os dados do dia foram carregados
if st.session_state.df_dados is not None:
    df = st.session_state.df_dados
    st.header("Dashboard dos Dados do Dia")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Linhas", f"{df.shape[0]:,}".replace(",", "."), "linhas")
    col2.metric("Total de Colunas", f"{df.shape[1]}", "colunas")
    # ... (resto do dashboard)
    with st.expander("Ver pré-visualização dos dados"):
        st.dataframe(df)

# Se o mapeamento foi carregado, mostra uma confirmação
if st.session_state.df_mapeamento is not None:
    st.success("Base de conhecimento de Representantes está ativa.")
    with st.expander("Ver Mapeamento de Representantes"):
        st.dataframe(st.session_state.df_mapeamento)

st.header("Converse com a IA")
# Exibição do Histórico Visual
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Lógica de Entrada do Usuário ---
if prompt := st.chat_input("Faça uma pergunta..."):
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Decide qual dataframe usar
    keywords_mapeamento = ["quem atende", "representante de", "contato do rt", "telefone de", "rt para"]
    
    if any(keyword in prompt.lower() for keyword in keywords_mapeamento) and st.session_state.df_mapeamento is not None:
        df_type = 'mapeamento'
        df_hash = pd.util.hash_pandas_object(st.session_state.df_mapeamento).sum()
    elif st.session_state.df_dados is not None:
        df_type = 'dados'
        df_hash = pd.util.hash_pandas_object(st.session_state.df_dados).sum()
    else:
        df_type = 'chat'

    # Executa a ação
    with st.chat_message("assistant"):
        if df_type in ['mapeamento', 'dados']:
            with st.spinner("Analisando os dados..."):
                resultado_analise, erro = executar_analise_pandas(df_hash, prompt, df_type)
                if erro:
                    st.error(erro)
                    response_text = "Desculpe, não consegui analisar os dados."
                else:
                    if isinstance(resultado_analise, (pd.Series, pd.DataFrame)):
                        st.write(f"Resultado da análise sobre **{df_type.replace('_', ' ')}**:")
                        st.dataframe(resultado_analise) # Mostra a tabela de resultados para buscas
                        response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
                st.markdown(response_text)
        else: # Modo Chatbot
            with st.spinner("Pensando..."):
                response = st.session_state.chat.send_message(prompt)
                response_text = response.text
                st.markdown(response_text)
    
    st.session_state.display_history.append({"role": "assistant", "content": response_text})
