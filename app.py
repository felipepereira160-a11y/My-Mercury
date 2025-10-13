import streamlit as st
import google.generativeai as genai
import pandas as pd
import time

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Analista de Dados com IA", page_icon="📊", layout="wide")

# --- Título ---
st.title("📊 Eo")
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

@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta):
    df = st.session_state.dataframe
    time.sleep(1)
    prompt_engenharia = f"""
    Sua tarefa é converter uma pergunta em uma única linha de código Pandas que a responda.
    O dataframe é `df`. A coluna relevante sobre status é 'Status'.
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

# --- Corpo Principal ---
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

    # --- NOVA SEÇÃO: BOTÕES DE ANÁLISE RÁPIDA ---
    st.markdown("---")
    st.subheader("Análises Frequentes (Custo Zero de IA)")
    
    b_col1, b_col2, b_col3 = st.columns(3)

    if b_col1.button("Contagem de Ordens por Status"):
        st.write("Resultado da Análise:")
        status_counts = df['Status'].value_counts()
        st.bar_chart(status_counts)
        st.session_state.display_history.append({"role": "user", "content": "Análise: Contagem de Ordens por Status"})
        st.session_state.display_history.append({"role": "assistant", "content": "Análise executada. O gráfico está acima."})

    if b_col2.button("Top 5 Cidades (Agendadas)"):
        st.write("Resultado da Análise:")
        try:
            cidade_counts = df[df['Status'] == 'Agendada']['Cidade Agendamento'].value_counts().nlargest(5)
            st.bar_chart(cidade_counts)
            st.session_state.display_history.append({"role": "user", "content": "Análise: Top 5 Cidades (Agendadas)"})
            st.session_state.display_history.append({"role": "assistant", "content": "Análise executada. O gráfico está acima."})
        except KeyError:
            st.error("Coluna 'Cidade Agendamento' não encontrada no arquivo.")
            
    if b_col3.button("Top 5 Representantes (Agendadas)"):
        st.write("Resultado da Análise:")
        try:
            rep_counts = df[df['Status'] == 'Agendada']['Representante Técnico'].value_counts().nlargest(5)
            st.bar_chart(rep_counts)
            st.session_state.display_history.append({"role": "user", "content": "Análise: Top 5 Representantes (Agendadas)"})
            st.session_state.display_history.append({"role": "assistant", "content": "Análise executada. O gráfico está acima."})
        except KeyError:
            st.error("Coluna 'Representante Técnico' não encontrada no arquivo.")
            
    st.markdown("---")
    st.header("Converse com seus Dados")

# --- Exibição do Histórico Visual ---
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Lógica de Entrada do Usuário ---
if prompt := st.chat_input("Converse com a IA ou faça uma pergunta sobre seus dados..."):
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if st.session_state.dataframe is not None:
        with st.chat_message("assistant"):
            with st.spinner("Analisando os dados..."):
                df_hash = pd.util.hash_pandas_object(st.session_state.dataframe).sum()
                resultado_analise, erro = executar_analise_pandas(df_hash, prompt)
                
                if erro:
                    st.error(erro)
                    response_text = "Desculpe, não consegui analisar os dados."
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
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                response = st.session_state.chat.send_message(prompt)
                response_text = response.text
                st.markdown(response_text)
        st.session_state.display_history.append({"role": "assistant", "content": response_text})
