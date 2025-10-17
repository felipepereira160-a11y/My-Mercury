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

# --- DASHBOARD ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de OS")
    df_dados = aplicar_blacklist(st.session_state.df_dados.copy())

    status_col = next((col for col in df_dados.columns if 'status' in col.lower()), None)
    rep_col = next((col for col in df_dados.columns if 'representante técnico' in col.lower() and 'id' not in col.lower()), None)
    city_col = next((col for col in df_dados.columns if 'cidade agendamento' in col.lower()), None)
    motivo_col = next((col for col in df_dados.columns if 'tipo de fechamento' in col.lower()), None)

    col1, col2 = st.columns(2)
    with col1:
        if status_col and city_col:
            st.write("Ordens Agendadas por Cidade (Top 10)")
            st.bar_chart(df_dados[df_dados[status_col]=='Agendada'][city_col].value_counts().nlargest(10))
        if status_col and rep_col:
            st.write("Ordens Realizadas por RT (Top 10)")
            st.bar_chart(df_dados[df_dados[status_col]=='Realizada'][rep_col].value_counts().nlargest(10))
    with col2:
        if rep_col:
            st.write("Total de Ordens por RT (Top 10)")
            st.bar_chart(df_dados[rep_col].value_counts().nlargest(10))
        if motivo_col and rep_col:
            st.write("Indisponibilidades por RT (Top 10)")
            st.bar_chart(df_dados[df_dados[motivo_col]=='Visita Improdutiva'][rep_col].value_counts().nlargest(10))

    with st.expander("Ver tabela completa com filtros"):
        st.dataframe(df_dados)

# --- MAPA ---
if st.session_state.df_mapeamento is not None:
    st.markdown("---")
    st.header("🗺️ Mapeamento de RT")
    df_map = aplicar_blacklist(st.session_state.df_mapeamento.copy())
    city_col_map, rep_col_map, lat_col, lon_col, km_col = 'nm_cidade_atendimento', 'nm_representante', 'cd_latitude_atendimento', 'cd_longitude_atendimento', 'qt_distancia_atendimento_km'

    if all(col in df_map.columns for col in [city_col_map, rep_col_map, lat_col, lon_col, km_col]):
        col1, col2 = st.columns(2)
        cidades_opcoes = ["Todos"] + sorted(df_map[city_col_map].dropna().unique())
        reps_opcoes = ["Todos"] + sorted(df_map[rep_col_map].dropna().unique())
        cidade_selecionada = col1.selectbox("Filtrar por Cidade:", cidades_opcoes)
        rep_selecionado = col2.selectbox("Filtrar por Representante:", reps_opcoes)

        df_filtrado = df_map.copy()
        if cidade_selecionada != "Todos": df_filtrado = df_filtrado[df_filtrado[city_col_map]==cidade_selecionada]
        if rep_selecionado != "Todos": df_filtrado = df_filtrado[df_filtrado[rep_col_map]==rep_selecionado]

        st.dataframe(df_filtrado)
        map_data = df_filtrado.rename(columns={lat_col:'lat', lon_col:'lon'})
        map_data['lat'] = pd.to_numeric(map_data['lat'], errors='coerce')
        map_data['lon'] = pd.to_numeric(map_data['lon'], errors='coerce')
        map_data.dropna(subset=['lat','lon'], inplace=True)
        if not map_data.empty: st.map(map_data, size=100)

# --- OTIMIZADOR ---
if st.session_state.df_dados is not None and st.session_state.df_mapeamento is not None:
    st.markdown("---")
    with st.expander("🚚 Otimizador de Proximidade de RT"):
        df_dados_otim = aplicar_blacklist(st.session_state.df_dados.copy())
        df_map_otim = aplicar_blacklist(st.session_state.df_mapeamento.copy())

        os_id_col = next((col for col in df_dados_otim.columns if 'número da o.s' in col.lower() or 'numeropedido' in col.lower()), None)
        os_cliente_col = next((col for col in df_dados_otim.columns if 'cliente' in col.lower() and 'id' not in col.lower()), None)
        os_city_col = next((col for col in df_dados_otim.columns if 'cidade agendamento' in col.lower()), None)
        os_rep_col = next((col for col in df_dados_otim.columns if 'representante técnico' in col.lower() and 'id' not in col.lower()), None)
        os_status_col = next((col for col in df_dados_otim.columns if 'status' in col.lower()), None)
        os_date_col = next((col for col in df_dados_otim.columns if 'data agendamento' in col.lower()), None)

        if not all([os_id_col, os_cliente_col, os_city_col, os_rep_col, os_status_col, os_date_col]):
            st.warning("Colunas necessárias não encontradas no arquivo de agendamentos.")
        else:
            df_agendadas = df_dados_otim[df_dados_otim[os_status_col]=='Agendada'].copy()

            # --- FILTRO POR CIDADE OU NÚMERO DA O.S ---
            st.write("Escolha a Cidade ou o Número da O.S para exibir as ordens")
            cidade_opcoes = [""] + sorted(df_agendadas[os_city_col].dropna().unique())
            os_opcoes = [""] + sorted(df_agendadas[os_id_col].dropna().astype(str).unique())

            cidade_selecionada = st.selectbox("Cidade:", cidade_opcoes)
            os_selecionada = st.selectbox("Número da O.S:", os_opcoes)

            # --- MOSTRAR SOMENTE SE HOUVER FILTRO ---
            if cidade_selecionada or os_selecionada:
                ordens_filtradas = df_agendadas.copy()
                if cidade_selecionada: 
                    ordens_filtradas = ordens_filtradas[ordens_filtradas[os_city_col]==cidade_selecionada]
                if os_selecionada: 
                    ordens_filtradas = ordens_filtradas[ordens_filtradas[os_id_col].astype(str)==os_selecionada]

                if ordens_filtradas.empty:
                    st.info("Nenhuma OS encontrada com o filtro selecionado.")
                else:
                    st.dataframe(ordens_filtradas[[os_id_col, os_cliente_col, os_date_col, os_rep_col]])

                    # Cálculo de proximidade com RTs
                    map_city_col, map_lat_col, map_lon_col, map_rep_col_map, map_rep_lat_col, map_rep_lon_col = 'nm_cidade_atendimento', 'cd_latitude_atendimento', 'cd_longitude_atendimento', 'nm_representante', 'cd_latitude_representante', 'cd_longitude_representante'
                    for _, ordem in ordens_filtradas.iterrows():
                        cidade_info = df_map_otim[df_map_otim[map_city_col]==ordem[os_city_col]]
                        if not cidade_info.empty:
                            ponto_atendimento = (cidade_info.iloc[0][map_lat_col], cidade_info.iloc[0][map_lon_col])
                            distancias = [{'Representante': rt_map[map_rep_col_map], 'Distancia (km)': haversine((rt_map[map_rep_lat_col], rt_map[map_rep_lon_col]), ponto_atendimento, unit=Unit.KILOMETERS)} for _, rt_map in df_map_otim.iterrows()]
                            df_distancias = pd.DataFrame(distancias).drop_duplicates(subset=['Representante']).reset_index(drop=True)
                            rt_sugerido = df_distancias.loc[df_distancias['Distancia (km)'].idxmin()]
                            with st.expander(f"OS: {ordem[os_id_col]} | Cliente: {ordem[os_cliente_col]}"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.info(f"RT Agendado: {ordem[os_rep_col]}")
                                    dist_atual_df = df_distancias[df_distancias['Representante']==ordem[os_rep_col]]
                                    dist_atual = dist_atual_df['Distancia (km)'].values[0] if not dist_atual_df.empty else float('inf')
                                    st.metric("Distância do RT Agendado", f"{dist_atual:.1f} km")
                                with col2:
                                    st.success(f"Sugestão (Mais Próximo): {rt_sugerido['Representante']}")
                                    economia = dist_atual - rt_sugerido['Distancia (km)']
                                    st.metric("Distância do RT Sugerido", f"{rt_sugerido['Distancia (km)']:.1f} km", delta=f"{economia:.1f} km economia" if economia>0 and economia!=float('inf') else None)


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
        else:
            response = st.session_state.chat.send_message(prompt)
            st.markdown(response.text)
            response_text = response.text
    
    st.session_state.display_history.append({"role":"assistant","content":response_text})
