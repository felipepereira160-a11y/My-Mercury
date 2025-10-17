import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
from haversine import haversine, Unit

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")
st.title("🧠 Seu Assistente de Dados com IA")
st.write("Converse comigo ou faça o upload de seus arquivos na barra lateral para começar a analisar!")

# --- Chave API ---
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not api_key:
    st.error("Chave da API do Google não encontrada.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-pro-latest')

# --- Inicialização do Estado da Sessão ---
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None

# --- Funções ---
BLACKLIST = ["FCA", "CHRYSLER", "STELLANTIS", "CEABS"]

def aplicar_blacklist(df):
    df_filtrado = df.copy()
    for col in df_filtrado.select_dtypes(include='object').columns:
        mask = df_filtrado[col].astype(str).str.upper().str.contains("|".join(BLACKLIST))
        df_filtrado = df_filtrado[~mask]
    return df_filtrado

@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    df = aplicar_blacklist(df)
    prompt_engenharia = f"""
    Você é um assistente especialista em Python e Pandas. Sua tarefa é analisar a pergunta do usuário.
    Colunas disponíveis: {', '.join(df.columns)}.

    INSTRUÇÕES:
    1. Determine se a pergunta do usuário PODE ser respondida usando os dados.
    2. Se for genérica, responda "PERGUNTA_INVALIDA".
    3. Caso contrário, converta em uma única linha de código Pandas.

    Pergunta: "{pergunta}"
    """
    try:
        response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        resposta_ia = response.text.strip().replace('`','').replace('python','')
        if resposta_ia == "PERGUNTA_INVALIDA": return None, "PERGUNTA_INVALIDA"
        resultado = eval(resposta_ia, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Erro na análise: {e}"

def carregar_dataframe(arquivo, separador_padrao=','):
    if arquivo.name.endswith('.xlsx'):
        return pd.read_excel(arquivo)
    elif arquivo.name.endswith('.csv'):
        try:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
            if len(df.columns) > 1: return df
        except:
            pass
        arquivo.seek(0)
        outro_sep = ',' if separador_padrao == ';' else ';'
        return pd.read_csv(arquivo, encoding='latin-1', sep=outro_sep, on_bad_lines='skip')
    return None

# --- Função para gráficos de fechamentos problemáticos ---
def grafico_fechamentos_problematicos(df, status_col, tipo_fechamento_col, rep_col, fechamento_selecionado, top_n=15):
    df_filtrado = df[(df[status_col] != 'Realizada') & (df[tipo_fechamento_col] == fechamento_selecionado)]
    if df_filtrado.empty:
        return pd.DataFrame(columns=[rep_col, 'Quantidade'])
    df_contagem = df_filtrado.groupby(rep_col).size().reset_index(name='Quantidade')
    df_contagem = df_contagem.sort_values(by='Quantidade', ascending=False).head(top_n)
    return df_contagem

# --- Barra Lateral ---
with st.sidebar:
    st.header("Base de Conhecimento")
    data_file = st.file_uploader("1. Upload de Agendamentos (OS)", type=["csv","xlsx"])
    if data_file:
        try:
            st.session_state.df_dados = carregar_dataframe(data_file, separador_padrao=';')
            st.success("Agendamentos carregados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")

    map_file = st.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=["csv","xlsx"])
    if map_file:
        try:
            st.session_state.df_mapeamento = carregar_dataframe(map_file, separador_padrao=',')
            st.success("Mapeamento carregado!")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- DASHBOARD PRINCIPAL ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de OS")
    df_dados = aplicar_blacklist(st.session_state.df_dados.copy())

    status_col = next((col for col in df_dados.columns if 'status' in col.lower()), None)
    rep_col = next((col for col in df_dados.columns if 'representante técnico' in col.lower() and 'id' not in col.lower()), None)
    city_col = next((col for col in df_dados.columns if 'cidade agendamento' in col.lower()), None)
    tipo_fechamento_col = next((col for col in df_dados.columns if 'tipo de fechamento' in col.lower()), None)

    # --- Filtros ---
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        status_opcoes = ["Todos"] + sorted(df_dados[status_col].dropna().unique())
        status_selecionado = st.selectbox("Filtrar por Status:", status_opcoes)
    with col_f2:
        cidade_opcoes = ["Todos"] + sorted(df_dados[city_col].dropna().unique())
        cidade_selecionada = st.selectbox("Filtrar por Cidade:", cidade_opcoes)

    df_filtrado_dash = df_dados.copy()
    if status_selecionado != "Todos":
        df_filtrado_dash = df_filtrado_dash[df_filtrado_dash[status_col]==status_selecionado]
    if cidade_selecionada != "Todos":
        df_filtrado_dash = df_filtrado_dash[df_filtrado_dash[city_col]==cidade_selecionada]

    col1, col2 = st.columns(2)
    with col1:
        if status_col and city_col:
            st.write("Ordens Agendadas por Cidade (Top 10)")
            st.bar_chart(df_filtrado_dash[df_filtrado_dash[status_col]=='Agendada'][city_col].value_counts().nlargest(10))
        if status_col and rep_col:
            st.write("Ordens Realizadas por RT (Top 10)")
            st.bar_chart(df_filtrado_dash[df_filtrado_dash[status_col]=='Realizada'][rep_col].value_counts().nlargest(10))
    with col2:
        if rep_col:
            st.write("Total de Ordens por RT (Top 10)")
            st.bar_chart(df_filtrado_dash[rep_col].value_counts().nlargest(10))
        if tipo_fechamento_col and rep_col:
            st.write("Indisponibilidades por RT (Top 10)")
            st.bar_chart(df_filtrado_dash[df_filtrado_dash[tipo_fechamento_col]=='Visita Improdutiva'][rep_col].value_counts().nlargest(10))

    with st.expander("Ver tabela completa com filtros"):
        st.dataframe(df_filtrado_dash)

# --- VISÕES ESPECÍFICAS ADICIONAIS ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.subheader("📌 Visões Específicas")

    # Realizada - Serviços realizados
    df_realizada_servicos = df_dados[(df_dados[status_col]=='Realizada') & (df_dados[tipo_fechamento_col]=='Serviços realizados')]
    st.write("✅ Ordens Realizadas - Serviços realizados")
    st.bar_chart(df_realizada_servicos[rep_col].value_counts().nlargest(15))

    # Realizada - Serviços parcialmente realizados
    df_realizada_parcial = df_dados[(df_dados[status_col]=='Realizada') & (df_dados[tipo_fechamento_col]=='Serviços parcialmente realizados')]
    st.write("✅ Ordens Realizadas - Serviços parcialmente realizados")
    st.bar_chart(df_realizada_parcial[rep_col].value_counts().nlargest(15))

    # Não realizadas - Fechamentos problemáticos
    tipos_nao_realizadas = ['Indisponibilidade técnica', 'Visita Improdutiva', 'Reagendamento solicitado', 'Não comparecimento do técnico']

    col1, col2 = st.columns(2)
    with col1:
        fechamento1 = st.selectbox("Filtrar gráfico 1 - Tipo de Fechamento Problemático", tipos_nao_realizadas, key='fech1')
        df_graf1 = grafico_fechamentos_problematicos(df_dados, status_col, tipo_fechamento_col, rep_col, fechamento1)
        st.write(f"❌ {fechamento1} - Top 15 RTs")
        if not df_graf1.empty:
            st.bar_chart(df_graf1.set_index(rep_col)['Quantidade'])
        else:
            st.info("Nenhuma ocorrência encontrada.")

    with col2:
        fechamento2 = st.selectbox("Filtrar gráfico 2 - Tipo de Fechamento Problemático", tipos_nao_realizadas, key='fech2')
        df_graf2 = grafico_fechamentos_problematicos(df_dados, status_col, tipo_fechamento_col, rep_col, fechamento2)
        st.write(f"❌ {fechamento2} - Top 15 RTs")
        if not df_graf2.empty:
            st.bar_chart(df_graf2.set_index(rep_col)['Quantidade'])
        else:
            st.info("Nenhuma ocorrência encontrada.")

# --- CHAT ---
st.markdown("---")
st.header("💬 Chat com IA")
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta específica..."):
    st.session_state.display_history.append({"role":"user","content":prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    df_type = 'chat'
    if any(k in prompt.lower() for k in ["quem atende","representante","mapeamento"]) and st.session_state.df_mapeamento is not None:
        df_type='mapeamento'
    elif st.session_state.df_dados is not None:
        df_type='dados'

    with st.chat_message("assistant"):
        if df_type in ['mapeamento','dados']:
            df_hash = pd.util.hash_pandas_object(st.session_state.get(f"df_{df_type}")).sum()
            resultado, erro = executar_analise_pandas(df_hash, prompt, df_type)
            if erro=="PERGUNTA_INVALIDA":
                response_text = "Desculpe, só posso responder perguntas relacionadas aos dados carregados."
            elif erro:
                st.error(erro)
                response_text = "Não foi possível analisar os dados."
            else:
                if isinstance(resultado, (pd.Series, pd.DataFrame)):
                    st.dataframe(resultado)
                    response_text = "Resultado exibido na tabela acima."
                else:
                    response_text = f"Resultado: {resultado}"
        st.markdown(response_text)
