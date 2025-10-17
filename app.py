import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import time
from haversine import haversine, Unit
import unicodedata

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Seu Assistente de Dados com IA")
st.write("Converse comigo ou faça o upload de seus arquivos na barra lateral para começar a analisar!")

# --- Função para normalizar strings e remover acentos ---
def normalize_text(text):
    if pd.isna(text):
        return ""
    text = str(text)
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    return text.lower()

# --- Função para aplicar filtro de blacklist ---
def aplicar_blacklist(df, blacklist_keywords):
    df_filtered = df.copy()
    mask_total = pd.Series([False] * len(df_filtered))
    for col in df_filtered.columns:
        if df_filtered[col].dtype == object:
            mask_col = df_filtered[col].fillna("").apply(lambda x: any(k in normalize_text(x) for k in blacklist_keywords))
            mask_total = mask_total | mask_col
    return df_filtered[~mask_total]

BLACKLIST = ['ceabs', 'fca', 'chrysler', 'stellantis']

# --- Lógica robusta para carregar a chave da API ---
api_key = None
api_key_status = "Não configurada"
try:
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if api_key:
        api_key_status = "✔️ Carregada (Streamlit Secrets)"
except Exception:
    pass

if not api_key:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        api_key_status = "✔️ Carregada (Variável de Ambiente)"
    else:
        api_key_status = "❌ ERRO: Chave não encontrada."

st.sidebar.caption(f"**Status da Chave de API:** {api_key_status}")

model = None
if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro-latest')
    except Exception as e:
        st.error(f"Erro ao configurar a API do Google: {e}")
        st.stop()
else:
    st.error("A chave da API do Google não foi encontrada. O aplicativo não pode funcionar.")
    st.stop()

# --- Inicialização do Estado da Sessão ---
if "chat" not in st.session_state and model:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None

# --- Funções ---
@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    # Aplicar filtro de blacklist antes de gerar resposta
    df = aplicar_blacklist(df, BLACKLIST)
    
    prompt_engenharia = f"""
    Você é um assistente especialista em Python e Pandas. Sua tarefa é analisar a pergunta do usuário.
    As colunas disponíveis no dataframe `df` são: {', '.join(df.columns)}.

    INSTRUÇÕES:
    1. Determine se a pergunta do usuário PODE ser respondida usando os dados.
    2. Se a pergunta for genérica (ex: "quem descobriu o Brasil?"), responda APENAS com: "PERGUNTA_INVALIDA".
    3. Se a pergunta for sobre os dados, converta-a em uma única linha de código Pandas que gere o resultado.

    Pergunta: "{pergunta}"
    Sua resposta:
    """
    try:
        response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        resposta_ia = response.text.strip().replace('`', '').replace('python', '')
        if resposta_ia == "PERGUNTA_INVALIDA":
            return None, "PERGUNTA_INVALIDA"
        resultado = eval(resposta_ia, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

def carregar_dataframe(arquivo, separador_padrao=','):
    if arquivo.name.endswith('.xlsx'):
        return pd.read_excel(arquivo)
    elif arquivo.name.endswith('.csv'):
        try:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
            if len(df.columns) > 1: return df
        except Exception:
            pass
        arquivo.seek(0)
        outro_separador = ',' if separador_padrao == ';' else ';'
        df = pd.read_csv(arquivo, encoding='latin-1', sep=outro_separador, on_bad_lines='skip')
        return df
    return None

# --- Barra Lateral ---
with st.sidebar:
    st.header("Base de Conhecimento")
    data_file = st.sidebar.file_uploader("1. Upload de Agendamentos (OS)", type=["csv", "xlsx"])
    if data_file:
        try:
            df = carregar_dataframe(data_file, separador_padrao=';')
            st.session_state.df_dados = aplicar_blacklist(df, BLACKLIST)
            st.success("Agendamentos carregados e filtrados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")

    st.markdown("---")
    map_file = st.sidebar.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=["csv", "xlsx"])
    if map_file:
        try:
            df_map = carregar_dataframe(map_file, separador_padrao=',')
            st.session_state.df_mapeamento = aplicar_blacklist(df_map, BLACKLIST)
            st.success("Mapeamento carregado e filtrado!")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- Corpo Principal ---

# --- Dashboard ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de Ordens de Serviço")
    df_dados = st.session_state.df_dados.copy()
    # ... o resto do seu dashboard continua igual, pois o df já está filtrado

# --- Ferramenta de Mapeamento ---
if st.session_state.df_mapeamento is not None:
    st.markdown("---")
    st.header("🗺️ Ferramenta de Mapeamento e Consulta de RT")
    df_map = st.session_state.df_mapeamento.copy()
    # ... lógica de filtro/mapa continua igual, df já filtrado

# --- Otimizador de proximidade ---
if st.session_state.df_dados is not None and st.session_state.df_mapeamento is not None:
    st.markdown("---")
    with st.expander("🚚 Abrir Otimizador de Proximidade de RT"):
        try:
            df_dados_otim = st.session_state.df_dados.copy()
            df_map_otim = st.session_state.df_mapeamento.copy()

            # Permitir busca por OS
            os_id_col = next((col for col in df_dados_otim.columns if 'número da o.s' in col.lower() or 'numeropedido' in col.lower()), None)
            cidade_selecionada_otim = st.selectbox("Selecione uma cidade ou digite uma OS:", options=sorted(df_dados_otim['cidade agendamento'].dropna().unique()) if 'cidade agendamento' in df_dados_otim.columns else [])
            os_input = st.text_input("OU digite o número da OS para busca direta:")

            # Filtrar por cidade ou OS
            if os_input:
                ordens_na_cidade = df_dados_otim[df_dados_otim[os_id_col].astype(str).str.contains(os_input, case=False, na=False)]
            else:
                ordens_na_cidade = df_dados_otim[df_dados_otim['cidade agendamento'] == cidade_selecionada_otim]

            # ... resto do código do otimizador continua igual
        except Exception as e:
            st.error(f"Ocorreu um erro inesperado no Otimizador. Detalhe: {e}")

# --- Chat de IA ---
st.markdown("---")
st.header("💬 Converse com a IA para análises personalizadas")
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta específica..."):
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    df_type = 'chat'
    keywords_mapeamento = ["quem atende", "representante de", "contato do rt", "telefone de", "rt para", "mapeamento"]
    if any(keyword in prompt.lower() for keyword in keywords_mapeamento) and st.session_state.df_mapeamento is not None:
        df_type = 'mapeamento'
    elif st.session_state.df_dados is not None:
        df_type = 'dados'
    
    with st.chat_message("assistant"):
        if df_type in ['mapeamento', 'dados']:
            with st.spinner(f"Analisando no arquivo de '{df_type}'..."):
                df_hash = pd.util.hash_pandas_object(st.session_state.get(f"df_{df_type}")).sum()
                resultado_analise, erro = executar_analise_pandas(df_hash, prompt, df_type)
                
                if erro == "PERGUNTA_INVALIDA":
                    response_text = "Desculpe, só posso responder a perguntas relacionadas aos dados da planilha carregada."
                elif erro:
                    st.error(erro); response_text = "Desculpe, não consegui analisar os dados."
                else:
                    if isinstance(resultado_analise, (pd.Series, pd.DataFrame)):
                        st.write(f"Resultado da busca na base de '{df_type}':"); st.dataframe(resultado_analise); response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
                st.markdown(response_text)
        else:
            with st.spinner("Pensando..."):
                response = st.session_state.chat.send_message(prompt)
                response_text = response.text
                st.markdown(response_text)
    
    st.session_state.display_history.append({"role": "assistant", "content": response_text})
