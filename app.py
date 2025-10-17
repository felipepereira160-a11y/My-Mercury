import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import time
import unicodedata
from haversine import haversine, Unit

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Seu Assistente de Dados com IA")
st.write("Converse comigo ou faça o upload de seus arquivos na barra lateral para começar a analisar!")

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

# Exibe o status da chave de API na barra lateral
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

# --- Função Blacklist ---
def aplicar_blacklist_segura(df):
    """
    Remove linhas que contenham FCA, Chrysler, Stellantis ou Ceabs em qualquer coluna textual.
    """
    if df is None or df.empty:
        return df

    blacklist = ['ceabs', 'fca', 'chrysler', 'stellantis']
    mask_total = pd.Series([False] * len(df))
    
    for col in df.columns:
        if df[col].dtype == object:
            mask_col = df[col].fillna("").apply(
                lambda x: any(term in unicodedata.normalize('NFKD', str(x))
                               .encode('ASCII', 'ignore').decode('utf-8').lower() for term in blacklist)
            )
            mask_total |= mask_col
    
    return df[~mask_total].copy()

# --- Função de carregamento ---
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

# --- Função de análise de Pandas via IA ---
@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
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

# --- Barra Lateral ---
with st.sidebar:
    st.header("Base de Conhecimento")
    data_file = st.file_uploader("1. Upload de Agendamentos (OS)", type=["csv", "xlsx"])
    if data_file:
        try:
            df = carregar_dataframe(data_file, separador_padrao=';')
            st.session_state.df_dados = aplicar_blacklist_segura(df)
            st.success("Agendamentos carregados e filtrados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")

    st.markdown("---")
    map_file = st.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=["csv", "xlsx"])
    if map_file:
        try:
            df = carregar_dataframe(map_file, separador_padrao=',')
            st.session_state.df_mapeamento = aplicar_blacklist_segura(df)
            st.success("Mapeamento carregado e filtrado!")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- DASHBOARD ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de Ordens de Serviço")
    df_dados = st.session_state.df_dados.copy()

    # Colunas Dinâmicas
    status_col = next((col for col in df_dados.columns if 'status' in col.lower()), None)
    rep_col_dados = next((col for col in df_dados.columns if 'representante técnico' in col.lower() and 'id' not in col.lower()), None)
    city_col_dados = next((col for col in df_dados.columns if 'cidade agendamento' in col.lower()), None)
    motivo_fechamento_col = next((col for col in df_dados.columns if 'tipo de fechamento' in col.lower()), None)

    st.subheader("Análises Gráficas")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Ordens Agendadas por Cidade (Top 10)**")
        if status_col and city_col_dados:
            agendadas_df = df_dados[df_dados[status_col] == 'Agendada']
            st.bar_chart(agendadas_df[city_col_dados].value_counts().nlargest(10))
        st.write("**Ordens Realizadas por RT (Top 10)**")
        if status_col and rep_col_dados:
            realizadas_df = df_dados[df_dados[status_col] == 'Realizada']
            st.bar_chart(realizadas_df[rep_col_dados].value_counts().nlargest(10))
    with col2:
        st.write("**Total de Ordens por RT (Top 10)**")
        if rep_col_dados:
            st.bar_chart(df_dados[rep_col_dados].value_counts().nlargest(10))
        st.write("**Indisponibilidades por RT (Top 10)**")
        if motivo_fechamento_col and rep_col_dados:
            improdutivas_df = df_dados[df_dados[motivo_fechamento_col] == 'Visita Improdutiva']
            st.bar_chart(improdutivas_df[rep_col_dados].value_counts().nlargest(10))

    with st.expander("Ver tabela de dados completa com filtros"):
        st.dataframe(df_dados)

# --- FERRAMENTA DE MAPEAMENTO ---
if st.session_state.df_mapeamento is not None:
    st.markdown("---")
    st.header("🗺️ Ferramenta de Mapeamento e Consulta de RT")
    df_map = st.session_state.df_mapeamento.copy()
    city_col_map, rep_col_map, lat_col, lon_col, km_col = 'nm_cidade_atendimento', 'nm_representante', 'cd_latitude_atendimento', 'cd_longitude_atendimento', 'qt_distancia_atendimento_km'
    
    if all(col in df_map.columns for col in [city_col_map, rep_col_map, lat_col, lon_col, km_col]):
        col1, col2 = st.columns(2)
        cidade_selecionada_map = col1.selectbox("Filtrar Mapeamento por Cidade:", options=sorted(df_map[city_col_map].dropna().unique()))
        rep_selecionado_map = col2.selectbox("Filtrar Mapeamento por Representante:", options=sorted(df_map[rep_col_map].dropna().unique()))
        filtered_df_map = df_map
        if cidade_selecionada_map: filtered_df_map = df_map[df_map[city_col_map] == cidade_selecionada_map]
        elif rep_selecionado_map: filtered_df_map = df_map[df_map[rep_col_map] == rep_selecionado_map]
        st.dataframe(filtered_df_map[[rep_col_map, city_col_map, km_col]+[c for c in filtered_df_map.columns if c not in [rep_col_map, city_col_map, km_col]]])
        map_data = filtered_df_map.rename(columns={lat_col: 'lat', lon_col: 'lon'})
        map_data['lat'] = pd.to_numeric(map_data['lat'], errors='coerce')
        map_data['lon'] = pd.to_numeric(map_data['lon'], errors='coerce')
        map_data.dropna(subset=['lat','lon'], inplace=True)
        if not map_data.empty: st.map(map_data, size=100)

# --- OTIMIZADOR DE PROXIMIDADE ---
if st.session_state.df_dados is not None and st.session_state.df_mapeamento is not None:
    st.markdown("---")
    with st.expander("🚚 Abrir Otimizador de Proximidade de RT"):
        try:
            df_dados_otim = st.session_state.df_dados
            df_map_otim = st.session_state.df_mapeamento
            os_id_col = next((col for col in df_dados_otim.columns if 'número da o.s' in col.lower() or 'numeropedido' in col.lower()), None)
            os_cliente_col = next((col for col in df_dados_otim.columns if 'cliente' in col.lower() and 'id' not in col.lower()), None)
            os_city_col = next((col for col in df_dados_otim.columns if 'cidade agendamento' in col.lower()), None)
            os_status_col = next((col for col in df_dados_otim.columns if 'status' in col.lower()), None)
            os_rep_col = next((col for col in df_dados_otim.columns if 'representante técnico' in col.lower() and 'id' not in col.lower()), None)

            map_city_col = 'nm_cidade_atendimento'
            map_lat_col = 'cd_latitude_atendimento'
            map_lon_col = 'cd_longitude_atendimento'
            map_rep_col = 'nm_representante'
            map_rep_lat_col = 'cd_latitude_representante'
            map_rep_lon_col = 'cd_longitude_representante'

            if not all([os_id_col, os_cliente_col, os_city_col, os_status_col, os_rep_col]):
                st.warning("Colunas obrigatórias do agendamento não encontradas.")
            else:
                df_agendadas = df_dados_otim[df_dados_otim[os_status_col] == 'Agendada'].copy()
                cidade_selecionada_otim = st.selectbox("Selecione uma cidade para otimização:", sorted(df_agendadas[os_city_col].dropna().unique()))
                if cidade_selecionada_otim:
                    ordens_na_cidade = df_agendadas[df_agendadas[os_city_col] == cidade_selecionada_otim]
                    st.dataframe(ordens_na_cidade[[os_id_col, os_cliente_col, os_rep_col]])
                    cidade_info = df_map_otim[df_map_otim[map_city_col] == cidade_selecionada_otim]
                    if not cidade_info.empty:
                        ponto_atendimento = (cidade_info.iloc[0][map_lat_col], cidade_info.iloc[0][map_lon_col])
                        distancias = [{'Representante': rt_map[map_rep_col],
                                       'Distancia (km)': haversine((rt_map[map_rep_lat_col], rt_map[map_rep_lon_col]),
                                                                   ponto_atendimento, unit=Unit.KILOMETERS)}
                                      for _, rt_map in df_map_otim.iterrows()]
                        df_distancias = pd.DataFrame(distancias).drop_duplicates(subset=['Representante']).reset_index(drop=True)
                        rt_sugerido = df_distancias.loc[df_distancias['Distancia (km)'].idxmin()]
                        for index, ordem in ordens_na_cidade.iterrows():
                            rt_atual = ordem[os_rep_col]
                            with st.expander(f"**OS: {ordem[os_id_col]} | Cliente: {ordem[os_cliente_col]}**"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.info(f"RT Agendado: {rt_atual}")
                                    dist_atual_df = df_distancias[df_distancias['Representante']==rt_atual]
                                    if not dist_atual_df.empty:
                                        st.metric("Distância RT Agendado", f"{dist_atual_df['Distancia (km)'].values[0]:.1f} km")
                                with col2:
                                    st.success(f"RT Sugerido: {rt_sugerido['Representante']}")
                                    economia = (dist_atual_df['Distancia (km)'].values[0] - rt_sugerido['Distancia (km)']) if not dist_atual_df.empty else None
                                    st.metric("Distância RT Sugerido", f"{rt_sugerido['Distancia (km)']:.1f} km",
                                              delta=f"{economia:.1f} km de economia" if economia else None)
        except Exception as e:
            st.error(f"Erro inesperado no Otimizador: {e}")

# --- Chat de IA ---
st.markdown("---")
st.header("💬 Converse com a IA para análises personalizadas")
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta específica..."):
    st.session_state.display_history.append({"role":"user","content":prompt})
    with st.chat_message("user"): st.markdown(prompt)

    df_type = 'dados' if st.session_state.df_dados is not None else None
    with st.chat_message("assistant"):
        if df_type:
            df_hash = pd.util.hash_pandas_object(st.session_state.get(f"df_{df_type}")).sum()
            resultado, erro = executar_analise_pandas(df_hash, prompt, df_type)
            if erro=="PERGUNTA_INVALIDA":
                response_text="Desculpe, só posso responder a perguntas dos dados carregados."
            elif erro:
                st.error(erro); response_text="Não foi possível analisar os dados."
            else:
                if isinstance(resultado,(pd.DataFrame,pd.Series)):
                    st.dataframe(resultado); response_text="Resultado exibido acima."
                else:
                    response_text=f"O resultado da sua análise: **{resultado}**"
            st.markdown(response_text)
            st.session_state.display_history.append({"role":"assistant","content":response_text})
