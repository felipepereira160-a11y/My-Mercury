# Writing the corrected app.py to /mnt/data/app_corrigido.py so the user can download it.
code = r'''
import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
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

st.sidebar.caption(f"**Status da Chave de API:** {api_key_status}")

model = None
if api_key:
    try:
        # Mantive o modelo exatamente como estava no arquivo original para evitar mudanças inesperadas
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro-latest')
    except Exception as e:
        st.error(f"Erro ao configurar a API do Google: {e}")
        st.stop()
else:
    st.error("A chave da API do Google não foi encontrada. O aplicativo não pode funcionar.")
    st.stop()

# --- Estado da sessão ---
if "chat" not in st.session_state and model:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None

# --- Funções utilitárias ---
def carregar_dataframe(arquivo, separador_padrao=','):
    if arquivo.name.endswith('.xlsx') or arquivo.name.endswith('.xls'):
        return pd.read_excel(arquivo)
    elif arquivo.name.endswith('.csv'):
        try:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
            if len(df.columns) > 1:
                return df
        except Exception:
            pass
        arquivo.seek(0)
        outro_separador = ',' if separador_padrao == ';' else ';'
        df = pd.read_csv(arquivo, encoding='latin-1', sep=outro_separador, on_bad_lines='skip')
        return df
    return None

def aplicar_filtro_exclusao(df, termos_excluidos, campos_verificados=None):
    """Remove linhas que contenham qualquer um dos termos_excluidos em colunas relevantes.
    Se campos_verificados for None, verifica todas as colunas que contenham 'cliente' ou 'representante' no nome.
    Retorna cópia filtrada do df.
    """
    if df is None:
        return None
    df_f = df.copy()
    if campos_verificados is None:
        campos_verificados = [col for col in df_f.columns if any(x in col.lower() for x in ['cliente', 'representante', 'rep', 'represent'])]
    # Se não encontrou colunas típicas, verificamos todas as colunas de texto para segurança
    if not campos_verificados:
        campos_verificados = [col for col in df_f.columns if df_f[col].dtype == object]
    pattern = '|'.join([p.lower() for p in termos_excluidos if p.strip()])
    if not pattern:
        return df_f
    mask_total = pd.Series(False, index=df_f.index)
    for col in campos_verificados:
        try:
            mask = df_f[col].astype(str).str.lower().str.contains(pattern, na=False)
            mask_total = mask_total | mask
        except Exception:
            # ignora colunas que não podem ser convertidas para string
            continue
    return df_f[~mask_total].copy()

@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    prompt_engenharia = f\"\"\"
    Você é um assistente especialista em Python e Pandas. Sua tarefa é analisar a pergunta do usuário.
    As colunas disponíveis no dataframe `df` são: {', '.join(df.columns)}.

    INSTRUÇÕES:
    1. Determine se a pergunta do usuário PODE ser respondida usando os dados.
    2. Se a pergunta for genérica (ex: "quem descobriu o Brasil?"), responda APENAS com: "PERGUNTA_INVALIDA".
    3. Se a pergunta for sobre os dados, converta-a em uma única linha de código Pandas que gere o resultado.

    Pergunta: \"{pergunta}\"
    Sua resposta:
    \"\"\"
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
    st.write("1) Faça upload dos arquivos: Agendamentos (OS) e Mapemento (RT)")
    data_file = st.file_uploader("Upload de Agendamentos (OS) (.csv ou .xlsx)", type=["csv", "xlsx"])
    if data_file:
        try:
            df_temp = carregar_dataframe(data_file, separador_padrao=';')
            st.session_state.df_dados = df_temp
            st.success("Agendamentos carregados com sucesso!")
        except Exception as e:
            st.error(f"Erro ao carregar agendamentos: {e}")

    st.markdown("---")
    map_file = st.file_uploader("Upload do Mapeamento de RT (Fixo) (.csv ou .xlsx)", type=["csv", "xlsx"])
    if map_file:
        try:
            df_temp_map = carregar_dataframe(map_file, separador_padrao=',')
            st.session_state.df_mapeamento = df_temp_map
            st.success("Mapeamento carregado com sucesso!")
        except Exception as e:
            st.error(f"Erro ao carregar mapeamento: {e}")

    st.markdown("---")
    st.write("Filtro de exclusão (palavras que serão ignoradas em cliente/representante):")
    termos_padrao = ['stellantis', 'ceabs', 'ceabvs', 'fca', 'fca chrysler', 'serviços ceabs', 'locadora', 'montadora']
    termos_input = st.text_area("Termos (separe por vírgula) — mantém a lista padrão se vazio:", value=', '.join(termos_padrao), height=90)
    termos_excluidos = [t.strip() for t in termos_input.split(',') if t.strip()]

    if st.button("Aplicar filtro e resetar visualizações"):
        # aplica filtro imediatamente nas bases carregadas (se existirem)
        if st.session_state.df_dados is not None:
            st.session_state.df_dados = aplicar_filtro_exclusao(st.session_state.df_dados, termos_excluidos)
        if st.session_state.df_mapeamento is not None:
            # além de filtrar por cliente/representante, também garanto que o nome do representante não contenha termos excluídos
            st.session_state.df_mapeamento = aplicar_filtro_exclusao(st.session_state.df_mapeamento, termos_excluidos)
        st.success("Filtro aplicado nas bases carregadas.")

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.experimental_rerun()

# --- Dashboard de OS ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de Ordens de Serviço")
    df_dados = st.session_state.df_dados.copy()

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
        else:
            st.warning("Colunas 'Status' ou 'Cidade Agendamento' não encontradas.")
        st.write("**Ordens Realizadas por RT (Top 10)**")
        if status_col and rep_col_dados:
            realizadas_df = df_dados[df_dados[status_col] == 'Realizada']
            st.bar_chart(realizadas_df[rep_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Colunas 'Status' ou 'Representante Técnico' não encontradas.")

    with col2:
        st.write("**Total de Ordens por RT (Top 10)**")
        if rep_col_dados:
            st.bar_chart(df_dados[rep_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Coluna 'Representante Técnico' não encontrada.")

        st.write("**Indisponibilidades (Visitas Improdutivas) por RT (Top 10)**")
        if motivo_fechamento_col and rep_col_dados:
            improdutivas_df = df_dados[df_dados[motivo_fechamento_col] == 'Visita Improdutiva']
            st.bar_chart(improdutivas_df[rep_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Colunas 'Tipo de Fechamento' ou 'Representante Técnico' não encontradas.")

    with st.expander("Ver tabela de dados completa com filtros"):
        st.dataframe(df_dados)

# --- Ferramenta de Mapeamento ---
if st.session_state.df_mapeamento is not None:
    st.markdown("---")
    st.header("🗺️ Ferramenta de Mapeamento e Consulta de RT")
    df_map = st.session_state.df_mapeamento.copy()
    city_col_map, rep_col_map, lat_col, lon_col, km_col = 'nm_cidade_atendimento', 'nm_representante', 'cd_latitude_atendimento', 'cd_longitude_atendimento', 'qt_distancia_atendimento_km'

    if all(col in df_map.columns for col in [city_col_map, rep_col_map, lat_col, lon_col, km_col]):
        col1, col2 = st.columns(2)
        cidade_selecionada_map = col1.selectbox("Filtrar Mapeamento por Cidade:", options=sorted(df_map[city_col_map].dropna().unique()), index=None, placeholder="Selecione uma cidade")
        rep_selecionado_map = col2.selectbox("Filtrar Mapeamento por Representante:", options=sorted(df_map[rep_col_map].dropna().unique()), index=None, placeholder="Selecione um representante")
        filtered_df_map = df_map
        if cidade_selecionada_map:
            filtered_df_map = df_map[df_map[city_col_map] == cidade_selecionada_map]
        elif rep_selecionado_map:
            filtered_df_map = df_map[df_map[rep_col_map] == rep_selecionado_map]
        st.write("Resultados da busca:")
        ordem_colunas = [rep_col_map, city_col_map, km_col]; outras_colunas = [col for col in filtered_df_map.columns if col not in ordem_colunas]; nova_ordem = ordem_colunas + outras_colunas
        st.dataframe(filtered_df_map[nova_ordem])
        st.write("Visualização no Mapa:")
        map_data = filtered_df_map.rename(columns={lat_col: 'lat', lon_col: 'lon'})
        map_data['lat'] = pd.to_numeric(map_data['lat'], errors='coerce')
        map_data['lon'] = pd.to_numeric(map_data['lon'], errors='coerce')
        map_data.dropna(subset=['lat', 'lon'], inplace=True)
        map_data['size'] = 1000 if cidade_selecionada_map or rep_selecionado_map else 100
        if not map_data.empty:
            st.map(map_data, color='#FF4B4B', size='size')
        else:
            st.warning("Nenhum resultado com coordenadas para exibir no mapa.")
    else:
        st.warning("A planilha de mapeamento não contém as colunas esperadas (nm_cidade_atendimento, nm_representante, cd_latitude_atendimento, cd_longitude_atendimento, qt_distancia_atendimento_km).")

# --- Otimizador de Proximidade (com seleção por cidade, RT ou Número da O.S.) ---
if st.session_state.df_dados is not None and st.session_state.df_mapeamento is not None:
    st.markdown("---")
    with st.expander("🚚 Abrir Otimizador de Proximidade de RT"):
        try:
            df_dados_otim = st.session_state.df_dados.copy()
            df_map_otim = st.session_state.df_mapeamento.copy()

            # Colunas possíveis nas bases de agendamentos
            os_id_col = next((col for col in df_dados_otim.columns if 'número da o.s' in col.lower() or 'numero da o.s' in col.lower() or 'numeropedido' in col.lower() or 'os' == col.lower()), None)
            os_cliente_col = next((col for col in df_dados_otim.columns if 'cliente' in col.lower() and 'id' not in col.lower()), None)
            os_date_col = next((col for col in df_dados_otim.columns if 'data agendamento' in col.lower() or 'data' in col.lower()), None)
            os_city_col = next((col for col in df_dados_otim.columns if 'cidade agendamento' in col.lower() or 'cidade' == col.lower()), None)
            os_rep_col = next((col for col in df_dados_otim.columns if 'representante técnico' in col.lower() and 'id' not in col.lower()) or
                              (col for col in df_dados_otim.columns if 'representante' in col.lower()), None)
            os_status_col = next((col for col in df_dados_otim.columns if 'status' in col.lower()), None)

            # Colunas do mapeamento (esperadas)
            map_city_col = 'nm_cidade_atendimento'
            map_lat_atendimento_col = 'cd_latitude_atendimento'
            map_lon_atendimento_col = 'cd_longitude_atendimento'
            map_rep_col = 'nm_representante'
            map_rep_lat_col = 'cd_latitude_representante'
            map_rep_lon_col = 'cd_longitude_representante'

            # Reaplica filtro de exclusão - garante que otimizador não use registros proibidos
            termos_padrao = termos_excluidos
            df_dados_otim = aplicar_filtro_exclusao(df_dados_otim, termos_padrao)
            df_map_otim = aplicar_filtro_exclusao(df_map_otim, termos_padrao)

            # Também garante que na tabela de mapeamento nenhum representante com termo proibido permaneça
            if map_rep_col in df_map_otim.columns:
                df_map_otim = df_map_otim[~df_map_otim[map_rep_col].astype(str).str.lower().str.contains('|'.join([t.lower() for t in termos_padrao]), na=False)].copy()

            required_cols = [os_id_col, os_cliente_col, os_date_col, os_city_col, os_rep_col, os_status_col]
            if not all(required_cols):
                st.warning("Para usar o otimizador, a planilha de agendamentos deve conter colunas com nomes compatíveis (ex: 'Status', 'Cidade Agendamento', 'Número da O.S.', 'Representante Técnico').")
            else:
                df_agendadas = df_dados_otim[df_dados_otim[os_status_col].astype(str).str.lower() == 'agendada'].copy()
                if df_agendadas.empty:
                    st.info("Nenhuma ordem 'Agendada' encontrada após filtragem.")
                else:
                    modo_busca = st.radio("Buscar por:", options=["Cidade", "Representante (RT)", "Número da O.S."], index=0, horizontal=True)
                    cidade_selecionada_otim = None
                    ordens_na_cidade = pd.DataFrame()
                    if modo_busca == "Cidade":
                        lista_cidades_agendadas = sorted(df_agendadas[os_city_col].dropna().unique())
                        cidade_selecionada_otim = st.selectbox("Selecione uma cidade com agendamentos para otimizar:", options=lista_cidades_agendadas, index=None, placeholder="Escolha uma cidade")
                        if cidade_selecionada_otim:
                            ordens_na_cidade = df_agendadas[df_agendadas[os_city_col] == cidade_selecionada_otim]

                    elif modo_busca == "Representante (RT)":
                        lista_rts = sorted(df_map_otim[map_rep_col].dropna().unique()) if map_rep_col in df_map_otim.columns else []
                        rt_escolhido = st.selectbox("Selecione o RT (filtra ordens relacionadas):", options=lista_rts, index=None, placeholder="Escolha um RT")
                        if rt_escolhido and os_rep_col in df_agendadas.columns:
                            ordens_na_cidade = df_agendadas[df_agendadas[os_rep_col] == rt_escolhido]

                    elif modo_busca == "Número da O.S.":
                        lista_os = sorted(df_agendadas[os_id_col].dropna().astype(str).unique())
                        os_escolhido = st.selectbox("Selecione o Número da O.S.: ", options=lista_os, index=None, placeholder="Escolha uma O.S.")
                        if os_escolhido:
                            ordens_na_cidade = df_agendadas[df_agendadas[os_id_col].astype(str) == str(os_escolhido)]
                            # se a OS existir, extraímos a cidade dela (se disponível) para calcular o ponto
                            if not ordens_na_cidade.empty and os_city_col in ordens_na_cidade.columns:
                                cidade_selecionada_otim = ordens_na_cidade.iloc[0][os_city_col]

                    if ordens_na_cidade.empty:
                        st.info("Nenhuma ordem encontrada para o filtro selecionado.")
                    else:
                        st.subheader(f"Ordens selecionadas:")
                        st.dataframe(ordens_na_cidade[[c for c in [os_id_col, os_cliente_col, os_date_col, os_rep_col, os_city_col] if c in ordens_na_cidade.columns]])

                        # busca coordenadas da cidade selecionada na base de mapeamento
                        cidade_info = df_map_otim[df_map_otim[map_city_col] == cidade_selecionada_otim] if cidade_selecionada_otim is not None else pd.DataFrame()
                        if cidade_info.empty and modo_busca != "Representante (RT)":
                            st.error(f"Coordenadas para '{cidade_selecionada_otim}' não encontradas no mapeamento.")
                        else:
                            # se busca por RT, calculamos distâncias diretamente entre RTs do mapeamento e a(s) OS selecionadas
                            if modo_busca == "Representante (RT)" and not ordens_na_cidade.empty:
                                # pegar coordenadas dos RTs do mapeamento
                                pontos_rts = df_map_otim[[map_rep_col, map_rep_lat_col, map_rep_lon_col]].dropna(subset=[map_rep_lat_col, map_rep_lon_col]).drop_duplicates(subset=[map_rep_col])
                                distancias_rt = []
                                for _, rt in pontos_rts.iterrows():
                                    try:
                                        latlon_rt = (float(rt[map_rep_lat_col]), float(rt[map_rep_lon_col]))
                                    except Exception:
                                        continue
                                    # para cada ordem selecionada, calcular distância e apresentar
                                    for _, ordem in ordens_na_cidade.iterrows():
                                        # obter ponto atendimento da ordem: tenta buscar na tabela de cidade, senão usa NaNs
                                        if map_city_col in df_map_otim.columns and ordem.get(os_city_col) in df_map_otim[map_city_col].values:
                                            ponto_ordem = (df_map_otim[df_map_otim[map_city_col] == ordem[os_city_col]].iloc[0][map_lat_atendimento_col],
                                                           df_map_otim[df_map_otim[map_city_col] == ordem[os_city_col]].iloc[0][map_lon_atendimento_col])
                                        else:
                                            ponto_ordem = (None, None)
                                        if None in ponto_ordem:
                                            continue
                                        d = haversine(latlon_rt, ponto_ordem, unit=Unit.KILOMETERS)
                                        distancias_rt.append({'OS': ordem.get(os_id_col), 'Representante': rt[map_rep_col], 'Distancia (km)': d})
                                if not distancias_rt:
                                    st.warning("Não foi possível calcular distâncias (faltam coordenadas).")
                                else:
                                    df_distancias_rt = pd.DataFrame(distancias_rt)
                                    # sugerir para cada OS o RT com menor distância
                                    melhores = df_distancias_rt.loc[df_distancias_rt.groupby('OS')['Distancia (km)'].idxmin()].reset_index(drop=True)
                                    st.subheader("Melhor RT por OS (baseado em distância):")
                                    st.dataframe(melhores)
                            else:
                                # ponto de atendimento (pega o primeiro registro de coordenadas da cidade)
                                ponto_atendimento = (float(cidade_info.iloc[0][map_lat_atendimento_col]), float(cidade_info.iloc[0][map_lon_atendimento_col]))
                                # construir lista de distâncias entre todos os RTs (após filtragem) e o ponto de atendimento
                                distancias = []
                                for _, rt in df_map_otim.dropna(subset=[map_rep_lat_col, map_rep_lon_col]).iterrows():
                                    try:
                                        latlon_rt = (float(rt[map_rep_lat_col]), float(rt[map_rep_lon_col]))
                                    except Exception:
                                        continue
                                    d = haversine(latlon_rt, ponto_atendimento, unit=Unit.KILOMETERS)
                                    distancias.append({'Representante': rt[map_rep_col], 'Distancia (km)': d})
                                df_distancias = pd.DataFrame(distancias)
                                if df_distancias.empty:
                                    st.warning("Nenhum representante disponível com coordenadas após filtragem.")
                                else:
                                    # RT sugerido (mais próximo)
                                    df_distancias = df_distancias.drop_duplicates(subset=['Representante']).reset_index(drop=True)
                                    rt_sugerido = df_distancias.loc[df_distancias['Distancia (km)'].idxmin()]
                                    # mostrar comparação para cada OS selecionada
                                    for index, ordem in ordens_na_cidade.iterrows():
                                        rt_atual = ordem.get(os_rep_col, "N/A") if os_rep_col in ordem.index else "N/A"
                                        with st.expander(f\"**OS: {ordem.get(os_id_col, '')}** | Cliente: {ordem.get(os_cliente_col, '')}\"):
                                            col1, col2 = st.columns(2)
                                            with col1:
                                                st.info(f\"**RT Agendado:** {rt_atual}\")
                                                dist_atual_df = df_distancias[df_distancias['Representante'] == rt_atual] if isinstance(rt_atual, str) else pd.DataFrame()
                                                if not dist_atual_df.empty:
                                                    dist_atual = dist_atual_df['Distancia (km)'].values[0]
                                                    st.metric(\"Distância do RT Agendado\", f\"{dist_atual:.1f} km\")
                                                else:
                                                    st.warning(f\"O RT '{rt_atual}' não foi encontrado no mapeamento ou não tem coordenadas.\")
                                                    dist_atual = float('inf')
                                            with col2:
                                                st.success(f\"**Sugestão (Mais Próximo):** {rt_sugerido['Representante']}\")
                                                economia = dist_atual - rt_sugerido['Distancia (km)']
                                                st.metric(\"Distância do RT Sugerido\", f\"{rt_sugerido['Distancia (km)']:.1f} km\", delta=f\"{economia:.1f} km de economia\" if economia > 0 and economia != float('inf') else None)

        except Exception as e:
            st.error(f"Ocorreu um erro inesperado no Otimizador. Detalhe: {e}")

# --- Seção do Chat de IA ---
st.markdown(\"---\")
st.header(\"💬 Converse com a IA para análises personalizadas\")
for message in st.session_state.display_history:
    with st.chat_message(message[\"role\"]):
        st.markdown(message[\"content\"])

if prompt := st.chat_input(\"Faça uma pergunta específica...\"):
    st.session_state.display_history.append({\"role\": \"user\", \"content\": prompt})
    with st.chat_message(\"user\"):
        st.markdown(prompt)
    keywords_mapeamento = [\"quem atende\", \"representante de\", \"contato do rt\", \"telefone de\", \"rt para\", \"mapeamento\", \"número da o.s\", \"numero da o.s\", \"os\"]

    df_type = 'chat'
    if any(keyword in prompt.lower() for keyword in keywords_mapeamento) and st.session_state.df_mapeamento is not None:
        df_type = 'mapeamento'
    elif st.session_state.df_dados is not None:
        df_type = 'dados'

    with st.chat_message(\"assistant\"):
        if df_type in ['mapeamento', 'dados']:
            with st.spinner(f\"Analisando no arquivo de '{df_type}'...\"):
                df_hash = pd.util.hash_pandas_object(st.session_state.get(f\"df_{df_type}\")).sum()
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
            with st.spinner(\"Pensando...\"):
                response = st.session_state.chat.send_message(prompt)
                response_text = response.text
                st.markdown(response_text)

    st.session_state.display_history.append({\"role\": \"assistant\", \"content\": response_text})
'''
path = "/mnt/data/app_corrigido.py"
with open(path, "w", encoding="utf-8") as f:
    f.write(code)

path

