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

# --- OTIMIZADOR DE PROXIMIDADE (Usa df_dados e df_mapeamento) ---
if st.session_state.df_dados is not None and st.session_state.df_mapeamento is not None:
    st.markdown("---")
    with st.expander("🚚 Abrir Otimizador de Proximidade de RT"):
        try:
            df_dados_otim = st.session_state.df_dados
            df_map_otim = st.session_state.df_mapeamento

            # Colunas importantes
            os_id_col = next((col for col in df_dados_otim.columns if 'número da o.s' in col.lower() or 'numeropedido' in col.lower() or 'os' in col.lower()), None)
            os_cliente_col = next((col for col in df_dados_otim.columns if 'cliente' in col.lower() and 'id' not in col.lower()), None)
            os_date_col = next((col for col in df_dados_otim.columns if 'data agendamento' in col.lower()), None)
            os_city_col = next((col for col in df_dados_otim.columns if 'cidade agendamento' in col.lower() or 'cidade o.s.' in col.lower()), None)
            os_rep_col = next((col for col in df_dados_otim.columns if 'representante técnico' in col.lower() and 'id' not in col.lower()), None)
            if not os_rep_col:
                os_rep_col = next((col for col in df_dados_otim.columns if 'representante' in col.lower() and 'id' not in col.lower()), None)
            os_status_col = next((col for col in df_dados_otim.columns if 'status' in col.lower()), None)

            map_city_col = 'nm_cidade_atendimento'
            map_lat_atendimento_col = 'cd_latitude_atendimento'
            map_lon_atendimento_col = 'cd_longitude_atendimento'
            map_rep_col = 'nm_representante'
            map_rep_lat_col = 'cd_latitude_representante'
            map_rep_lon_col = 'cd_longitude_representante'

            required_cols = [os_id_col, os_cliente_col, os_date_col, os_city_col, os_rep_col, os_status_col]
            if not all(required_cols):
                st.warning("Para usar o otimizador, a planilha de agendamentos precisa conter colunas com os nomes corretos (incluindo Status e Representante sem ID).")
            else:
                # --- FILTRO DE STATUS ---
                st.subheader("Filtro de Status")
                all_statuses = df_dados_otim[os_status_col].dropna().unique().tolist()
                default_selection = [s for s in ['Agendada', 'Serviços realizados', 'Parcialmente realizado'] if s in all_statuses]
                status_selecionados = st.multiselect("Selecione os status para otimização:", options=all_statuses, default=default_selection)
                if not status_selecionados:
                    st.warning("Por favor, selecione ao menos um status para continuar.")
                    st.stop()

                df_otimizacao_filtrado = df_dados_otim[df_dados_otim[os_status_col].isin(status_selecionados)].copy()
                if df_otimizacao_filtrado.empty:
                    st.info(f"Nenhuma ordem com os status selecionados ('{', '.join(status_selecionados)}') foi encontrada.")
                    st.stop()

                # --- PESQUISA POR OS OU CLIENTE ---
                st.subheader("Pesquisar Ordem de Serviço ou Cliente")
                pesquisa_opcao = st.radio("Pesquisar por:", options=["Número da OS", "Cliente"], horizontal=True)

                ordens_na_cidade = None
                cidade_selecionada_otim = None

                if pesquisa_opcao == "Número da OS":
                    os_pesquisada_num = st.text_input("Digite o Número da O.S. para análise direta:")
                    if os_pesquisada_num:
                        df_otimizacao_filtrado[os_id_col] = df_otimizacao_filtrado[os_id_col].astype(str)
                        resultado_busca = df_otimizacao_filtrado[df_otimizacao_filtrado[os_id_col].str.strip() == os_pesquisada_num.strip()]
                        if not resultado_busca.empty:
                            ordens_na_cidade = resultado_busca
                            cidade_selecionada_otim = ordens_na_cidade.iloc[0][os_city_col]
                            st.success(f"O.S. '{os_pesquisada_num}' encontrada! Analisando cidade: {cidade_selecionada_otim}")
                        else:
                            st.warning(f"O.S. '{os_pesquisada_num}' não encontrada nos status selecionados.")
                else:  # pesquisa por cliente
                    clientes_disponiveis = sorted(df_otimizacao_filtrado[os_cliente_col].dropna().unique())
                    cliente_selecionado = st.selectbox("Selecione um cliente:", options=clientes_disponiveis, index=None, placeholder="Selecione um cliente...")
                    if cliente_selecionado:
                        ordens_na_cidade = df_otimizacao_filtrado[df_otimizacao_filtrado[os_cliente_col] == cliente_selecionado]
                        st.success(f"{len(ordens_na_cidade)} ordens encontradas para o cliente '{cliente_selecionado}'")

                # --- SELEÇÃO DE CIDADE PARA OTIMIZAÇÃO EM LOTE ---
                if ordens_na_cidade is None:
                    st.subheader("Ou Selecione uma Cidade para Otimizar em Lote")
                    lista_cidades = sorted(df_otimizacao_filtrado[os_city_col].dropna().unique())
                    cidade_selecionada_otim = st.selectbox("Selecione uma cidade:", options=lista_cidades, index=None, placeholder="Selecione...")
                    if cidade_selecionada_otim:
                        ordens_na_cidade = df_otimizacao_filtrado[df_otimizacao_filtrado[os_city_col] == cidade_selecionada_otim]

                # --- MOSTRAR ORDENS EM EXPANDERS ---
                if ordens_na_cidade is not None and not ordens_na_cidade.empty:
                    st.subheader(f"Ordens Selecionadas (Status: {', '.join(status_selecionados)})")
                    cidade_info = df_map_otim[df_map_otim[map_city_col] == cidade_selecionada_otim]
                    if cidade_info.empty:
                        st.error(f"Coordenadas para '{cidade_selecionada_otim}' não encontradas no Mapeamento.")
                    else:
                        ponto_atendimento = (cidade_info.iloc[0][map_lat_atendimento_col], cidade_info.iloc[0][map_lon_atendimento_col])
                        distancias = [{'Representante': str(rt_map[map_rep_col]), 'Distancia (km)': haversine((rt_map[map_rep_lat_col], rt_map[map_rep_lon_col]), ponto_atendimento, unit=Unit.KILOMETERS)} for _, rt_map in df_map_otim.iterrows()]
                        df_distancias = pd.DataFrame(distancias).drop_duplicates(subset=['Representante']).reset_index(drop=True)
                        termos_excluidos_otimizador = ['stellantis', 'ceabs', 'fca chrysler']
                        mascara_otimizador = ~df_distancias['Representante'].str.contains('|'.join(termos_excluidos_otimizador), case=False, na=False)
                        df_distancias_filtrado = df_distancias[mascara_otimizador]
                        rt_sugerido = None
                        if not df_distancias_filtrado.empty:
                            rt_sugerido = df_distancias_filtrado.loc[df_distancias_filtrado['Distancia (km)'].idxmin()]

                        # Expanders individuais por ordem
                        for index, ordem in ordens_na_cidade.iterrows():
                            with st.expander(f"OS: {ordem[os_id_col]} | Cliente: {ordem[os_cliente_col]} | RT Agendado: {ordem[os_rep_col]}"):
                                rt_atual = ordem[os_rep_col]
                                dist_atual_df = df_distancias[df_distancias['Representante'] == rt_atual]
                                if not dist_atual_df.empty:
                                    dist_atual = dist_atual_df['Distancia (km)'].values[0]
                                else:
                                    dist_atual = float('inf')
                                    st.warning(f"O RT '{rt_atual}' não foi encontrado no Mapeamento.")

                                st.write(f"**Distância do RT Agendado:** {dist_atual:.1f} km")

                                if rt_sugerido is not None:
                                    economia = dist_atual - rt_sugerido['Distancia (km)']
                                    st.success(f"**Sugestão de RT mais próximo:** {rt_sugerido['Representante']}")
                                    st.metric("Distância do RT Sugerido", f"{rt_sugerido['Distancia (km)']:.1f} km",
                                              delta=f"{economia:.1f} km de economia" if economia > 0 and economia != float('inf') else None)
                                else:
                                    st.warning("Nenhum RT disponível para sugestão após a filtragem.")
        except Exception as e:
            st.error(f"Ocorreu um erro inesperado no Otimizador. Detalhe: {e}")
