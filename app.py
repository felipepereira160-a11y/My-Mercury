import streamlit as st
import google.generativeai as genai
import pandas as pd

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Analista de Dados com IA", page_icon="📊", layout="wide")

# --- Título ---
st.title("📊 Seu Analista de Dados com IA")
st.write("Converse comigo ou faça o upload de um arquivo na barra lateral para começar a analisar!")

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
if 'dataframe' not in st.session_state:
    st.session_state.dataframe = None

# --- Barra Lateral ---
with st.sidebar:
    st.header("Adicionar Conhecimento")
    uploaded_file = st.sidebar.file_uploader("Faça o upload de um arquivo CSV ou XLSX", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, encoding='latin-1', sep=';', on_bad_lines='skip')
            elif uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file, engine='openpyxl')
            st.session_state.dataframe = df
            st.success("Arquivo carregado!")
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")

    if st.button("Limpar Arquivo e Chat"):
        st.session_state.dataframe = None
        st.session_state.chat = model.start_chat(history=[])
        st.session_state.display_history = []
        st.rerun()

# --- Dashboard (se houver arquivo) ---
if st.session_state.dataframe is not None:
    df = st.session_state.dataframe
    st.header("Dashboard do Arquivo")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Linhas", f"{df.shape[0]:,}".replace(",", "."), "linhas")
    col2.metric("Total de Colunas", f"{df.shape[1]}", "colunas")
    coluna_cliente = next((col for col in df.columns if 'cliente' in col.lower()), None)
    if coluna_cliente:
        clientes_unicos = df[coluna_cliente].nunique()
        col3.metric("Clientes Únicos", f"{clientes_unicos}", "clientes")
    with st.expander("Ver pré-visualização dos dados"):
        st.dataframe(df)
    st.header("Converse com seus Dados")

# --- Exibição do Histórico Visual ---
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Funções de Análise e Chat ---
def executar_analise_pandas(df, pergunta):
    prompt_engenharia = f"""
    Sua tarefa é converter uma pergunta em uma única linha de código Pandas que a responda.
    O dataframe é `df`. As colunas relevantes sobre status são na coluna 'Status'.
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

# --- Lógica de Entrada do Usuário ---
if prompt := st.chat_input("Converse com a IA ou faça uma pergunta sobre seus dados..."):
    # Adiciona a mensagem do usuário ao histórico visual
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Decide o modo de operação
    if st.session_state.dataframe is not None:
        # --- Modo Analista (Sem Memória de Conversa) ---
        with st.chat_message("assistant"):
            with st.spinner("Analisando os dados..."):
                resultado_analise, erro = executar_analise_pandas(st.session_state.dataframe, prompt)
                
                if erro:
                    st.error(erro)
                    response_text = "Desculpe, não consegui analisar os dados. Tente uma pergunta mais simples."
                else:
                    if isinstance(resultado_analise, (pd.Series, pd.DataFrame)) and len(resultado_analise) > 1:
                        st.write("Aqui está uma visualização para sua pergunta:")
                        st.bar_chart(resultado_analise)
                        response_text = "Gráfico gerado com sucesso acima!"
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
                
                st.markdown(response_text)
        st.session_state.display_history.append({"role": "assistant", "content": response_text})
    else:
        # --- Modo Chatbot (Com Memória de Conversa) ---
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                response = st.session_state.chat.send_message(prompt)
                response_text = response.text
                st.markdown(response_text)
        st.session_state.display_history.append({"role": "assistant", "content": response_text})
