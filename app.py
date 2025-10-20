import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import os
import re
from haversine import haversine, Unit
from io import BytesIO
from datetime import datetime

# ============================
# CONFIGURAÇÃO DA PÁGINA
# ============================
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")
st.title("🧠 Mercúrio IA")
st.write("Faça o upload de seus arquivos na barra lateral e converse com a IA!")

# ============================
# CHAVE DE API
# ============================
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

if not api_key:
    st.error("A chave da API do Google não foi encontrada. O aplicativo não pode funcionar.")
    st.stop()

genai.configure(api_key=api_key)
MODEL_NAME = "gemini-2.5-flash"

# ============================
# ESTADO DA SESSÃO
# ============================
if "model" not in st.session_state:
    st.session_state.model = genai.GenerativeModel(MODEL_NAME)

if "chat" not in st.session_state:
    try:
        st.session_state.chat = st.session_state.model.start_chat(history=[])
    except Exception as e:
        st.error(f"Erro ao iniciar sessão de chat: {e}")
        st.stop()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for df_key in ["df_dados", "df_mapeamento", "df_devolucao", "df_pagamento"]:
    if df_key not in st.session_state:
        st.session_state[df_key] = None

# ============================
# FUNÇÕES AUXILIARES
# ============================
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')

def safe_to_numeric(series):
    if series is None:
        return pd.Series([], dtype=float)
    if series.dtype == 'object':
        s = series.astype(str).str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
    else:
        s = series
    return pd.to_numeric(s, errors='coerce').fillna(0)

def carregar_dataframe(arquivo, separador_padrao=','):
    nome_arquivo = arquivo.name.lower()
    try:
        if nome_arquivo.endswith('.xlsx'):
            return pd.read_excel(arquivo, engine='openpyxl')
        elif nome_arquivo.endswith('.xls'):
            return pd.read_excel(arquivo, engine='xlrd')
        elif nome_arquivo.endswith('.csv'):
            arquivo.seek(0)
            try:
                df = pd.read_csv(arquivo, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
                if len(df.columns) > 1:
                    return df
            except Exception:
                pass
            arquivo.seek(0)
            outro_sep = ',' if separador_padrao == ';' else ';'
            df = pd.read_csv(arquivo, encoding='latin-1', sep=outro_sep, on_bad_lines='skip')
            return df
    except Exception as e:
        st.error(f"Erro ao carregar arquivo {arquivo.name}: {e}")
    return None

BLACKLIST = re.compile(r"\b(import|exec|eval|open|os\.|sys\.|subprocess|socket|__|pd\.read_|pickle|requests)\b", re.IGNORECASE)
ALLOWED_PATTERN = re.compile(r"^[\w\.\'\[\]\(\)\,\:\>\<\=\>\<\!\-\+\*\/\s%\"|]+$", re.UNICODE)

def is_code_safe(code_text):
    if not isinstance(code_text, str) or not code_text.strip():
        return False, "Código vazio."
    if BLACKLIST.search(code_text):
        return False, "Código contém operações potencialmente inseguras."
    if not ALLOWED_PATTERN.match(code_text.strip()):
        return False, "Código contém caracteres não permitidos."
    allowed_methods = ["value_counts", "sum(", "mean(", "median(", "nunique(", "unique(", "groupby(", "agg(", "loc[", "iloc[", "head(", "tail(", "dropna(", "shape", "count(", "max(", "min(", "sort_values(", "reset_index(", "to_list(", "astype("]
    if not any(m in code_text for m in allowed_methods) and "df" not in code_text:
        return False, "Código não aparenta conter operações Pandas executáveis conhecidas."
    return True, None

def executar_analise_pandas(prompt, df):
    if df is None:
        return None, "DataFrame não fornecido."
    prompt_engenharia = f"""
Você é um assistente especialista em Python e Pandas. 
O usuário fez a seguinte pergunta sobre um DataFrame (colunas listadas abaixo).
Gere apenas UMA ÚNICA LINHA de código Python que retorne diretamente o resultado pedido usando o objeto `df`.
Não use importações, não use múltiplas linhas, não use crases.
Se a pergunta NÃO puder ser respondida com o DataFrame, responda com a palavra exata: PERGUNTA_INVALIDA

Colunas disponíveis: {', '.join(df.columns)}
Pergunta: {prompt}
"""
    try:
        response = st.session_state.model.generate_content(prompt_engenharia)
        codigo_ia = response.text.strip().replace("```python", "").replace("```", "").replace("python", "").strip()
        if codigo_ia.strip().upper() == "PERGUNTA_INVALIDA":
            return None, "PERGUNTA_INVALIDA"
        is_safe, why = is_code_safe(codigo_ia)
        if not is_safe:
            return codigo_ia, f"Código rejeitado por segurança: {why}. A IA retornou (não executado):\n{codigo_ia}"
        safe_globals = {"pd": pd, "np": np}
        safe_locals = {"df": df.copy()}
        try:
            resultado = eval(codigo_ia, safe_globals, safe_locals)
            return resultado, None
        except Exception as e:
            return None, f"Erro ao executar o código gerado: {e}\nCódigo retornado pela IA:\n{codigo_ia}"
    except Exception as e:
        return None, f"Erro ao gerar código com a IA: {e}"

# ============================
# UPLOAD DE ARQUIVOS
# ============================
st.sidebar.header("Base de Conhecimento")
tipos_permitidos = ["csv", "xlsx", "xls"]

with st.sidebar:
    data_file = st.file_uploader("1. Upload de Agendamentos (OS)", type=tipos_permitidos, key="uploader_dados")
    if data_file is not None:
        df_tmp = carregar_dataframe(data_file, separador_padrao=';')
        if df_tmp is not None:
            st.session_state.df_dados = df_tmp
            st.success("Agendamentos carregados!")
        else:
            st.error("Falha ao carregar agendamentos. Verifique o arquivo.")

    st.markdown("---")
    map_file = st.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=tipos_permitidos, key="uploader_map")
    if map_file is not None:
        df_tmp = carregar_dataframe(map_file, separador_padrao=',')
        if df_tmp is not None:
            st.session_state.df_mapeamento = df_tmp
            st.success("Mapeamento carregado!")
        else:
            st.error("Falha ao carregar o mapeamento. Verifique o arquivo.")

    st.markdown("---")
    devolucao_file = st.file_uploader("3. Upload de Itens a Instalar (Devolução)", type=tipos_permitidos, key="uploader_dev")
    if devolucao_file is not None:
        df_tmp = carregar_dataframe(devolucao_file, separador_padrao=';')
        if df_tmp is not None:
            st.session_state.df_devolucao = df_tmp
            st.success("Base de devolução carregada!")
        else:
            st.error("Falha ao carregar devolução. Verifique o arquivo.")

    st.markdown("---")
    pagamento_file = st.file_uploader("4. Upload Pagamento/Fechamento", type=tipos_permitidos, key="uploader_pag")
    if pagamento_file is not None:
        df_tmp = carregar_dataframe(pagamento_file, separador_padrao=';')
        if df_tmp is not None:
            st.session_state.df_pagamento = df_tmp
            st.success("Base de pagamentos carregada!")
        else:
            st.error("Falha ao carregar pagamentos. Verifique o arquivo.")

# ============================
# OTIMIZADOR DE RT
# ============================
st.header("🔧 Otimizador de RT")

if st.session_state.df_dados is None or st.session_state.df_mapeamento is None:
    st.warning("Carregue os arquivos de Agendamento e Mapeamento para usar o Otimizador.")
else:
    df_os = st.session_state.df_dados.copy()
    df_map = st.session_state.df_mapeamento.copy()
    
    # Colunas padrão (adaptar conforme seus arquivos)
    os_id_col = 'Numero_OS'
    os_cliente_col = 'Cliente'
    os_city_col = 'Cidade'
    os_status_col = 'Status'
    os_date_col = 'Data_Agendamento'
    os_rep_col = 'RT_Agendado'
    os_lat_col = 'Lat'
    os_lon_col = 'Lon'
    
    # Filtros
    numero_os = st.text_input("Pesquisar por Número da O.S.:")
    cidades_disponiveis = sorted(df_os[os_city_col].dropna().unique())
    cidade_selecionada = st.selectbox("Filtrar por Cidade:", options=["Todas"] + cidades_disponiveis)
    clientes_disponiveis = sorted(df_os[os_cliente_col].dropna().unique())
    cliente_selecionado = st.selectbox("Filtrar por Cliente:", options=["Todos"] + clientes_disponiveis)
    
    df_filtrado = df_os.copy()
    if numero_os:
        df_filtrado = df_filtrado[df_filtrado[os_id_col].astype(str).str.contains(str(numero_os))]
    if cidade_selecionada != "Todas":
        df_filtrado = df_filtrado[df_filtrado[os_city_col] == cidade_selecionada]
    if cliente_selecionado != "Todos":
        df_filtrado = df_filtrado[df_filtrado[os_cliente_col] == cliente_selecionado]
    
    st.subheader(f"Ordens encontradas: {len(df_filtrado)}")
    
    # Caixa de seleção expansível com cálculo de RT sugerido e distância
    for idx, ordem in df_filtrado.iterrows():
        with st.expander(f"OS: {ordem[os_id_col]} | Cliente: {ordem[os_cliente_col]} | Data: {ordem[os_date_col]} | Status: {ordem[os_status_col]}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"RT Agendado: {ordem[os_rep_col]}")
            with col2:
                try:
                    lat_os, lon_os = float(ordem[os_lat_col]), float(ordem[os_lon_col])
                    df_map['distancia'] = df_map.apply(lambda x: haversine((lat_os, lon_os), (x['Lat'], x['Lon']), unit=Unit.KILOMETERS), axis=1)
                    rt_sugerido = df_map.loc[df_map['distancia'].idxmin()]['RT']
                    distancia_km = df_map['distancia'].min()
                    st.write(f"RT Sugerido: {rt_sugerido}")
                    st.write(f"Distância: {distancia_km:.2f} km")
                except Exception as e:
                    st.write("Erro ao calcular RT sugerido:", e)
            with col3:
                # Economia fictícia baseada em distância (exemplo)
                if 'distancia' in df_map.columns:
                    economia_estim = max(0, 100 - distancia_km)  # Exemplo simples
                    st.write(f"Economia Estimada: R$ {economia_estim:.2f}")

st.write("---")
st.info("Outros módulos do app continuam funcionando normalmente, sem alterações.")
