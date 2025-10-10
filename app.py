import streamlit as st
import google.generativeai as genai
import pandas as pd

st.set_page_config(page_title="Seu Analista de Dados com IA", page_icon="📊", layout="wide")

st.title("📊 Seu Analista de Dados com IA")
st.write("Converse comigo ou faça o upload de um arquivo na barra lateral para começar a analisar!")

try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error("Chave de API do Google não configurada.")
    st.stop()

with st.sidebar:
    st.header("Adicionar Conhecimento")
    uploaded_file = st.sidebar.file_uploader("Faça o upload de um arquivo CSV ou XLSX", type=["csv", "xlsx"])
    if 'dataframe' not in st.session_state:
        st.session_state.dataframe = None
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
        st.rerun()

model = genai.GenerativeModel('gemini-pro-latest')
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])

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

for message in st.session_state.chat.history:
    role = "assistant" if message.role == 'model' else 'user'
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

def executar_analise_pandas(df, pergunta):
    prompt_engenharia = f"""
    Sua tarefa é converter uma pergunta em uma única linha de código Pandas que a responda.
    O dataframe está na variável `df`.
    Primeiras linhas do dataframe: {df.head().to_string()}
    REGRAS OBRIGATÓRIAS:
    1. A coluna 'Status' contém: 'Agendada', 'Realizada', 'Nao Realizada', 'Reagendamento'.
    2. Se a pergunta contiver "agendadas", "realizadas", etc., você DEVE filtrar o dataframe por essa coluna ANTES de qualquer outra operação.
    Pergunta do usuário: "{pergunta}"
    Baseado nas REGRAS, gere apenas a linha de código Pandas necessária.
    """
    try:
        code_response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        codigo_pandas = code_response.text.strip().replace('`', '').replace('python', '').strip()
        resultado = eval(codigo_pandas, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

if prompt := st.chat_input("Converse com a IA ou faça uma pergunta sobre seus dados..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.chat.history.append({'role': 'user', 'parts': [{'text': prompt}]})

    if st.session_state.dataframe is not None:
        response_container = st.chat_message("assistant")
        with response_container:
            st.markdown("Analisando os dados...")
            resultado_analise, erro = executar_analise_pandas(st.session_state.dataframe, prompt)
        
            if erro:
                st.error(erro)
                response_text = "Desculpe, não consegui analisar os dados. Tente uma pergunta mais simples."
            else:
                # --- AQUI ESTÁ A OTIMIZAÇÃO ---
                # Removemos a segunda chamada à API e formatamos a resposta diretamente
                if isinstance(resultado_analise, (pd.Series, pd.DataFrame)) and len(resultado_analise) > 1:
                    st.write("Aqui está um gráfico para sua pergunta:")
                    st.bar_chart(resultado_analise)
                    response_text = "Gráfico gerado com sucesso acima!"
                else:
                    response_text = f"O resultado da sua análise é: **{resultado_analise}**"
            
            response_container.markdown(response_text)
    else:
        # Modo Chatbot Geral (usa 1 chamada à API)
        response = st.session_state.chat.send_message(prompt)
        response_text = response.text
        with st.chat_message("assistant"):
            st.markdown(response_text)

    # Adiciona a resposta final ao histórico para exibição
    st.session_state.chat.history.append({'role': 'model', 'parts': [{'text': response_text}]})
