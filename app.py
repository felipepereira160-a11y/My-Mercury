
import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import os
import time
from haversine import haversine, Unit
from io import BytesIO
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Mercúrio IA")
st.write("Faça o upload de seus arquivos na barra lateral!")

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
        model = genai.GenerativeModel('gemini-pro')
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
if 'df_dados' not in st.session_state: # Para Agendamentos
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None
if 'df_devolucao' not in st.session_state:
    st.session_state.df_devolucao = None
if 'df_pagamento' not in st.session_state: # Para a base de pagamento/duplicidade
    st.session_state.df_pagamento = None


# --- Funções ---
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')

def safe_to_numeric(series):
    """Converte uma série para numérico de forma robusta."""
    if series.dtype == 'object':
        series = series.astype(str).str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
    return pd.to_numeric(series, errors='coerce').fillna(0)

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
        response = genai.GenerativeModel('gemini-pro').generate_content(prompt_engenharia)
        resposta_ia = response.text.strip().replace('`', '').replace('python', '')
        if resposta_ia == "PERGUNTA_INVALIDA":
            return None, "PERGUNTA_INVALIDA"
        resultado = eval(resposta_ia, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

def carregar_dataframe(arquivo, separador_padrao=','):
    nome_arquivo = arquivo.name.lower()
    if nome_arquivo.endswith('.xlsx'):
        return pd.read_excel(arquivo, engine='openpyxl')
    elif nome_arquivo.endswith('.xls'):
        return pd.read_excel(arquivo, engine='xlrd')
    elif nome_arquivo.endswith('.csv'):
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
    tipos_permitidos = ["csv", "xlsx", "xls"]
    
    data_file = st.sidebar.file_uploader("1. Upload de Agendamentos (OS)", type=tipos_permitidos)
    if data_file:
        try:
            st.session_state.df_dados = carregar_dataframe(data_file, separador_padrao=';')
            st.success("Agendamentos carregados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")

    st.markdown("---")
    map_file = st.sidebar.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=tipos_permitidos)
    if map_file:
        try:
            st.session_state.df_mapeamento = carregar_dataframe(map_file, separador_padrao=',')
            st.success("Mapeamento carregado!")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")

    st.markdown("---")
    devolucao_file = st.sidebar.file_uploader("3. Upload de Itens a Instalar (Devolução)", type=tipos_permitidos)
    if devolucao_file:
        try:
            st.session_state.df_devolucao = carregar_dataframe(devolucao_file, separador_padrao=';')
            st.success("Base de devolução carregada!")
        except Exception as e:
            st.error(f"Erro na base de devolução: {e}")
            
    st.markdown("---")
    pagamento_file = st.sidebar.file_uploader("4. Upload da Base de Pagamento (Duplicidade)", type=tipos_permitidos)
    if pagamento_file:
        try:
            st.session_state.df_pagamento = carregar_dataframe(pagamento_file, separador_padrao=';')
            st.success("Base de pagamento carregada!")
        except Exception as e:
            st.error(f"Erro na base de pagamento: {e}")


    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- Corpo Principal ---

# --- DASHBOARD DE ANÁLISE DE ORDENS DE SERVIÇO (Usa df_dados)---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de Ordens de Serviço")
    df_dados_original = st.session_state.df_dados.copy()
    df_analise = df_dados_original.copy()

    status_col = next((col for col in df_analise.columns if 'status' in col.lower()), None)
    
    # CORREÇÃO: Lógica aprimorada para selecionar a coluna de NOME do representante
    rep_col_dados = next((col for col in df_analise.columns if 'representante técnico' in col.lower() and 'id' not in col.lower()), None)
    if not rep_col_dados:
        rep_col_dados = next((col for col in df_analise.columns if 'representante' in col.lower() and 'id' not in col.lower()), None)
        
    city_col_dados = next((col for col in df_analise.columns if 'cidade agendamento' in col.lower() or 'cidade o.s.' in col.lower()), None)
    motivo_fechamento_col = next((col for col in df_analise.columns if 'tipo de fechamento' in col.lower()), None)
    cliente_col = next((col for col in df_analise.columns if 'cliente' in col.lower() and 'id' not in col.lower()), None)
    
    st.subheader("Filtros de Análise")
    col_filtro1, col_filtro2 = st.columns(2)
    
    status_selecionado = None
    if status_col:
        opcoes_status = ["Exibir Todos"] + sorted(df_analise[status_col].dropna().unique())
        status_selecionado = col_filtro1.selectbox("Filtrar por Status:", options=opcoes_status)

    fechamento_selecionado = None
    if motivo_fechamento_col:
        opcoes_fechamento = ["Exibir Todos"] + sorted(df_analise[motivo_fechamento_col].dropna().unique())
        fechamento_selecionado = col_filtro2.selectbox("Filtrar por Tipo de Fechamento:", options=opcoes_fechamento)

    if status_selecionado and status_selecionado != "Exibir Todos":
        df_analise = df_analise[df_analise[status_col] == status_selecionado]
    if fechamento_selecionado and fechamento_selecionado != "Exibir Todos":
        df_analise = df_analise[df_analise[motivo_fechamento_col] == fechamento_selecionado]

    st.subheader("Análises Gráficas")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Ordens Agendadas por Cidade (Top 10)**")
        if status_col and city_col_dados:
            agendadas_df = df_analise[df_analise[status_col] == 'Agendada']
            st.bar_chart(agendadas_df[city_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Colunas 'Status' ou 'Cidade Agendamento' não encontradas.")

        st.write("**Ordens Realizadas por RT (Top 10)**")
        if status_col and rep_col_dados:
            realizadas_df = df_analise[df_analise[status_col] == 'Realizada']
            st.bar_chart(realizadas_df[rep_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Colunas 'Status' ou 'Representante Técnico' não encontradas.")

    with col2:
        st.write("**Total de Ordens por RT (Top 10)**")
        if rep_col_dados:
            st.bar_chart(df_analise[rep_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Coluna 'Representante Técnico' não encontrada.")

        st.write("**Indisponibilidades (Visitas Improdutivas) por RT (Top 10)**")
        if motivo_fechamento_col and rep_col_dados:
            improdutivas_df = df_analise[df_analise[motivo_fechamento_col] == 'Visita Improdutiva']
            st.bar_chart(improdutivas_df[rep_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Colunas 'Tipo de Fechamento' ou 'Representante Técnico' não encontradas.")

    st.subheader("Outras Análises")
    col3, col4 = st.columns(2)
    with col3:
        st.write("**Distribuição por Tipo de Fechamento (Top 10)**")
        if motivo_fechamento_col:
            st.bar_chart(df_analise[motivo_fechamento_col].value_counts().nlargest(10))
        else:
            st.warning("Coluna 'Tipo de Fechamento' não encontrada.")
    with col4:
        st.write("**Visitas Improdutivas por Cliente (Top 10)**")
        if motivo_fechamento_col and cliente_col:
            improdutivas_por_cliente_df = df_analise[df_analise[motivo_fechamento_col] == 'Visita Improdutiva']
            st.bar_chart(improdutivas_por_cliente_df[cliente_col].value_counts().nlargest(10))
        else:
            st.warning("Colunas 'Tipo de Fechamento' ou 'Cliente' não encontradas.")

    with st.expander("Ver tabela de dados completa (original, sem filtros)"):
        st.dataframe(df_dados_original)


# --- ANALISADOR DE CUSTOS E DUPLICIDADE (Usa df_pagamento) ---
if st.session_state.df_pagamento is not None:
    # Código inalterado...
    st.markdown("---")
    st.header("🔎 Analisador de Custos e Duplicidade de Deslocamento")
    with st.expander("Clique aqui para analisar custos e duplicidades da Base de Pagamento", expanded=True):
        try:
            df_custos = st.session_state.df_pagamento.copy()
            os_col = next((col for col in df_custos.columns if 'os' in col.lower()), None)
            data_fech_col = next((col for col in df_custos.columns if 'data de fechamento' in col.lower()), None)
            cidade_os_col = next((col for col in df_custos.columns if 'cidade o.s.' in col.lower()), None)
            cidade_rt_col = next((col for col in df_custos.columns if 'cidade rt' in col.lower()), None)
            rep_col = next((col for col in df_custos.columns if 'representante' in col.lower() and 'nome fantasia' not in col.lower()), None)
            tec_col = next((col for col in df_custos.columns if 'técnico' in col.lower()), None)
            valor_desl_col = next((col for col in df_custos.columns if 'valor deslocamento' in col.lower()), None)
            desloc_km_col = next((col for col in df_custos.columns if col.lower() == 'deslocamento'), None)
            valor_km_col = next((col for col in df_custos.columns if 'valor km rt' in col.lower()), None)
            abrang_col = next((col for col in df_custos.columns if 'abrangência rt' in col.lower()), None)
            valor_extra_col = next((col for col in df_custos.columns if 'valor extra' in col.lower()), None)
            pedagio_col = next((col for col in df_custos.columns if 'pedágio' in col.lower()), None)
            required_cols_custos = [os_col, data_fech_col, cidade_os_col, cidade_rt_col, rep_col, tec_col, valor_desl_col, desloc_km_col, valor_km_col, abrang_col, valor_extra_col, pedagio_col]
            if all(required_cols_custos):
                df_custos['VALOR_DESLOC_ORIGINAL'] = safe_to_numeric(df_custos[valor_desl_col])
                df_custos['VALOR_EXTRA_NUM'] = safe_to_numeric(df_custos[valor_extra_col])
                df_custos['PEDAGIO_NUM'] = safe_to_numeric(df_custos[pedagio_col])
                filtro_custos_positivos_mask = ((df_custos['VALOR_DESLOC_ORIGINAL'] > 0) | (df_custos['VALOR_EXTRA_NUM'] > 0) | (df_custos['PEDAGIO_NUM'] > 0))
                df_custos = df_custos[filtro_custos_positivos_mask].copy()
                if df_custos.empty:
                    st.success("✅ Nenhuma ordem com custos de deslocamento, extra ou pedágio foi encontrada para análise.")
                    st.stop()
                df_custos['DATA_ANALISE'] = pd.to_datetime(df_custos[data_fech_col], dayfirst=True, errors='coerce').dt.date
                st.subheader("Filtros da Análise")
                df_filtrado = df_custos.copy()
                col1_filtro, col2_filtro = st.columns(2)
                datas_disponiveis = df_filtrado['DATA_ANALISE'].dropna()
                if not datas_disponiveis.empty:
                    min_date, max_date = datas_disponiveis.min(), datas_disponiveis.max()
                    data_selecionada = col1_filtro.date_input("Filtrar por Data de Fechamento:", value=(min_date, max_date), min_value=min_date, max_value=max_date)
                    if len(data_selecionada) == 2:
                        start_date, end_date = data_selecionada
                        df_filtrado = df_filtrado[(df_filtrado['DATA_ANALISE'] >= start_date) & (df_filtrado['DATA_ANALISE'] <= end_date)]
                representantes_disponiveis = sorted(df_filtrado[rep_col].dropna().unique())
                if representantes_disponiveis:
                    reps_selecionados = col2_filtro.multiselect("Filtrar por Representante:", options=representantes_disponiveis, placeholder="Selecione um ou mais")
                    if reps_selecionados:
                        df_filtrado = df_filtrado[df_filtrado[rep_col].isin(reps_selecionados)]
                st.markdown("---")
                if df_filtrado.empty:
                    st.warning("Nenhum dado encontrado com os filtros selecionados.")
                    st.stop()
                for col in [cidade_os_col, rep_col, tec_col, cidade_rt_col]:
                    if col in df_filtrado.columns and df_filtrado[col].dtype == 'object':
                        df_filtrado[col] = df_filtrado[col].str.strip()
                df_filtrado['DESLOC_KM_NUM'] = safe_to_numeric(df_filtrado[desloc_km_col])
                df_filtrado['VALOR_KM_NUM'] = safe_to_numeric(df_filtrado[valor_km_col])
                df_filtrado['ABRANG_NUM'] = safe_to_numeric(df_filtrado[abrang_col])
                mesma_cidade_mask = df_filtrado[cidade_rt_col] == df_filtrado[cidade_os_col]
                valor_calculado = (df_filtrado['DESLOC_KM_NUM'] * df_filtrado['VALOR_KM_NUM']) - df_filtrado['ABRANG_NUM']
                valor_calculado[valor_calculado < 0] = 0
                df_filtrado['VALOR_CALCULADO'] = np.where(mesma_cidade_mask, 0, valor_calculado)
                df_filtrado['OBSERVACAO'] = np.where(mesma_cidade_mask, "Custo Zerado (Mesma Cidade)", "")
                df_filtrado[data_fech_col] = pd.to_datetime(df_filtrado[data_fech_col], errors='coerce').dt.strftime('%d/%m/%Y')
                st.subheader("Resultados da Análise")
                st.write("Ordens com Deslocamento Zerado (Cidade RT = Cidade O.S.)")
                df_custo_zero = df_filtrado[mesma_cidade_mask]
                if not df_custo_zero.empty:
                    st.dataframe(df_custo_zero[[os_col, data_fech_col, cidade_os_col, cidade_rt_col, rep_col, tec_col, 'VALOR_DESLOC_ORIGINAL', 'VALOR_CALCULADO', 'OBSERVACAO']])
                else:
                    st.info("Nenhuma ordem com Cidade RT = Cidade O.S. nos filtros selecionados.")
                st.write("Análise de Duplicidade de Deslocamento")
                group_keys = ['DATA_ANALISE', cidade_os_col, rep_col, tec_col]
                df_filtrado['is_first'] = ~df_filtrado.duplicated(subset=group_keys, keep='first')
                grupos_com_duplicatas = df_filtrado.groupby(group_keys).filter(lambda x: len(x) > 1)
                if grupos_com_duplicatas.empty:
                    st.success("✅ Nenhuma duplicidade de deslocamento encontrada nos filtros selecionados.")
                else:
                    grupos_com_duplicatas['VALOR_CALCULADO_AJUSTADO'] = np.where(grupos_com_duplicatas['is_first'], grupos_com_duplicatas['VALOR_CALCULADO'], 0)
                    grupos_com_duplicatas['OBSERVACAO'] = np.where(grupos_com_duplicatas['is_first'], grupos_com_duplicatas['OBSERVACAO'], "Duplicidade (Custo Zerado)")
                    df_resultado_final = grupos_com_duplicatas.sort_values(by=group_keys + [os_col])
                    cols_to_show = [os_col, data_fech_col, cidade_os_col, rep_col, tec_col, 'VALOR_DESLOC_ORIGINAL', 'VALOR_CALCULADO_AJUSTADO', 'OBSERVACAO']
                    st.dataframe(df_resultado_final[cols_to_show])
                    csv_duplicatas = convert_df_to_csv(df_resultado_final[cols_to_show])
                    st.download_button(label="📥 Exportar Resultado da Duplicidade (.csv)", data=csv_duplicatas, file_name="analise_duplicidade_deslocamento.csv", mime='text/csv')
            else:
                st.error("ERRO: Para usar esta análise, a planilha de pagamento precisa conter todas as seguintes colunas: 'OS', 'Data de Fechamento', 'Cidade O.S.', 'Cidade RT', 'Representante', 'Técnico', 'Valor Deslocamento', 'Deslocamento', 'Valor KM RT', 'AC Abrangência RT', 'Valor Extra', e 'Pedágio'.")
        except Exception as e:
            st.error(f"Ocorreu um erro inesperado no Analisador de Custos. Detalhe: {e}")

# --- FERRAMENTA DE DEVOLUÇÃO DE ORDENS (Usa df_devolucao) ---
if st.session_state.df_devolucao is not None:
    # Código inalterado...
    st.markdown("---")
    st.header("📦 Ferramenta de Devolução de Ordens Vencidas")
    df_devolucao = st.session_state.df_devolucao.copy()
    date_col_devolucao = next((col for col in df_devolucao.columns if 'prazoinstalacao' in col.lower().replace(' ', '')), None)
    cliente_col_devolucao = next((col for col in df_devolucao.columns if 'clientenome' in col.lower().replace(' ', '')), None)
    if date_col_devolucao and cliente_col_devolucao:
        df_devolucao[date_col_devolucao] = pd.to_datetime(df_devolucao[date_col_devolucao], dayfirst=True, errors='coerce')
        df_devolucao.dropna(subset=[date_col_devolucao], inplace=True)
        hoje = pd.Timestamp.now().normalize()
        df_vencidas = df_devolucao[df_devolucao[date_col_devolucao] < hoje].copy()
        if df_vencidas.empty:
            st.info("Nenhuma ordem de serviço vencida encontrada na base de dados carregada.")
        else:
            st.warning(f"Foram encontradas {len(df_vencidas)} ordens vencidas no total.")
            clientes_vencidos = sorted(df_vencidas[cliente_col_devolucao].dropna().unique())
            cliente_selecionado = st.selectbox("Pesquise ou selecione um cliente para filtrar as devoluções:", options=clientes_vencidos, index=None, placeholder="Selecione um cliente...")
            if cliente_selecionado:
                df_filtrado_cliente = df_vencidas[df_vencidas[cliente_col_devolucao] == cliente_selecionado]
                st.metric(label=f"Total de Ordens Vencidas para", value=cliente_selecionado, delta=f"{len(df_filtrado_cliente)} ordens", delta_color="inverse")
                st.dataframe(df_filtrado_cliente)
                csv = convert_df_to_csv(df_filtrado_cliente)
                st.download_button(label="📥 Exportar Devolutiva (.csv)", data=csv, file_name=f"devolutiva_{cliente_selecionado.replace(' ', '_').lower()}.csv", mime='text/csv')
    else:
        st.error("ERRO: Verifique se a planilha de devolução contém as colunas 'PrazoInstalacao' e 'ClienteNome'.")

# --- FERRAMENTA DE MAPEAMENTO (Usa df_mapeamento) ---
if st.session_state.df_mapeamento is not None:
    # Código inalterado...
    st.markdown("---")
    st.header("🗺️ Ferramenta de Mapeamento e Consulta de RT")
    df_map = st.session_state.df_mapeamento.copy()
    city_col_map, rep_col_map, lat_col, lon_col, km_col = 'nm_cidade_atendimento', 'nm_representante', 'cd_latitude_atendimento', 'cd_longitude_atendimento', 'qt_distancia_atendimento_km'
    if all(col in df_map.columns for col in [city_col_map, rep_col_map, lat_col, lon_col, km_col]):
        col1, col2 = st.columns(2)
        cidade_selecionada_map = col1.selectbox("Filtrar Mapeamento por Cidade:", options=sorted(df_map[city_col_map].dropna().unique()), index=None, placeholder="Selecione uma cidade")
        rep_selecionado_map = col2.selectbox("Filtrar Mapeamento por Representante:", options=sorted(df_map[rep_col_map].dropna().unique()), index=None, placeholder="Selecione um representante")
        filtered_df_map = df_map
        if cidade_selecionada_map: filtered_df_map = df_map[df_map[city_col_map] == cidade_selecionada_map]
        elif rep_selecionado_map: filtered_df_map = df_map[df_map[rep_col_map] == rep_selecionado_map]
        st.write("Resultados da busca:")
        ordem_colunas = [rep_col_map, city_col_map, km_col]; outras_colunas = [col for col in filtered_df_map.columns if col not in ordem_colunas]; nova_ordem = ordem_colunas + outras_colunas
        st.dataframe(filtered_df_map[nova_ordem])
        st.write("Visualização no Mapa:")
        map_data = filtered_df_map.rename(columns={lat_col: 'lat', lon_col: 'lon'}); map_data['lat'] = pd.to_numeric(map_data['lat'], errors='coerce'); map_data['lon'] = pd.to_numeric(map_data['lon'], errors='coerce'); map_data.dropna(subset=['lat', 'lon'], inplace=True)
        map_data['size'] = 1000 if cidade_selecionada_map or rep_selecionado_map else 100
        if not map_data.empty: st.map(map_data, color='#FF4B4B', size='size')
        else: st.warning("Nenhum resultado com coordenadas para exibir no mapa.")

# --- OTIMIZADOR DE PROXIMIDADE (Usa df_dados e df_mapeamento) ---
if st.session_state.df_dados is not None and st.session_state.df_mapeamento is not None:
    # Código inalterado, pois já estava correto...
    st.markdown("---")
    with st.expander("🚚 Abrir Otimizador de Proximidade de RT"):
        try:
            df_dados_otim = st.session_state.df_dados
            df_map_otim = st.session_state.df_mapeamento
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
                else:
                    st.subheader("Buscar Ordem de Serviço Específica (dentro do filtro)")
                    os_pesquisada_num = st.text_input("Digite o Número da O.S. para análise direta:")
                    cidade_selecionada_otim = None
                    ordens_na_cidade = None
                    if os_pesquisada_num:
                        df_otimizacao_filtrado[os_id_col] = df_otimizacao_filtrado[os_id_col].astype(str)
                        resultado_busca = df_otimizacao_filtrado[df_otimizacao_filtrado[os_id_col].str.strip() == os_pesquisada_num.strip()]
                        if not resultado_busca.empty:
                            ordens_na_cidade = resultado_busca
                            cidade_selecionada_otim = ordens_na_cidade.iloc[0][os_city_col]
                            st.success(f"O.S. '{os_pesquisada_num}' encontrada! Analisando cidade: {cidade_selecionada_otim}")
                        else:
                            st.warning(f"O.S. '{os_pesquisada_num}' não encontrada nos status selecionados.")
                    else:
                        st.subheader("Ou Selecione uma Cidade para Otimizar em Lote")
                        lista_cidades = sorted(df_otimizacao_filtrado[os_city_col].dropna().unique())
                        cidade_selecionada_otim = st.selectbox("Selecione uma cidade:", options=lista_cidades, index=None, placeholder="Selecione...")
                        if cidade_selecionada_otim:
                            ordens_na_cidade = df_otimizacao_filtrado[df_otimizacao_filtrado[os_city_col] == cidade_selecionada_otim]
                    if ordens_na_cidade is not None and not ordens_na_cidade.empty:
                        st.subheader(f"Ordens em {cidade_selecionada_otim} (Status: {', '.join(status_selecionados)})")
                        st.dataframe(ordens_na_cidade[[os_id_col, os_cliente_col, os_date_col, os_rep_col]])
                        st.subheader(f"Análise de Proximidade para cada Ordem:")
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
                            for index, ordem in ordens_na_cidade.iterrows():
                                rt_atual = ordem[os_rep_col]
                                with st.container(border=True):
                                    st.markdown(f"**OS: {ordem[os_id_col]}** | Cliente: {ordem[os_cliente_col]}")
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.info(f"**RT Agendado:** {rt_atual}")
                                        dist_atual_df = df_distancias[df_distancias['Representante'] == rt_atual]
                                        if not dist_atual_df.empty:
                                            dist_atual = dist_atual_df['Distancia (km)'].values[0]
                                            st.metric("Distância do RT Agendado", f"{dist_atual:.1f} km")
                                        else:
                                            st.warning(f"O RT '{rt_atual}' não foi encontrado no Mapeamento.")
                                            dist_atual = float('inf')
                                    with col2:
                                        if rt_sugerido is not None:
                                            st.success(f"**Sugestão (Mais Próximo):** {rt_sugerido['Representante']}")
                                            economia = dist_atual - rt_sugerido['Distancia (km)']
                                            st.metric("Distância do RT Sugerido", f"{rt_sugerido['Distancia (km)']:.1f} km", delta=f"{economia:.1f} km de economia" if economia > 0 and economia != float('inf') else None)
                                        else:
                                            st.warning("Nenhum RT disponível para sugestão após a filtragem.")
        except Exception as e:
            st.error(f"Ocorreu um erro inesperado no Otimizador. Verifique os nomes das colunas. Detalhe: {e}")

# --- Seção do Chat de IA ---
st.markdown("---")
st.header("💬 Converse com a IA")
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta específica..."):
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    keywords_mapeamento = ["quem atende", "representante de", "contato do rt", "telefone de", "rt para", "mapeamento"]
    df_type = 'chat'
    
    if any(keyword in prompt.lower() for keyword in keywords_mapeamento) and st.session_state.df_mapeamento is not None:
        df_type = 'mapeamento'
    elif st.session_state.df_dados is not None:
        df_type = 'dados'
        
    with st.chat_message("assistant"):
        if df_type in ['mapeamento', 'dados']:
            with st.spinner(f"Analisando no arquivo de '{df_type}'..."):
                current_df = st.session_state.get(f"df_{df_type}")
                df_hash = pd.util.hash_pandas_object(current_df).sum()
                resultado_analise, erro = executar_analise_pandas(df_hash, prompt, df_type)
                
                if erro == "PERGUNTA_INVALIDA":
                    response_text = "Desculpe, só posso responder a perguntas relacionadas aos dados da planilha carregada."
                elif erro:
                    st.error(erro)
                    response_text = "Desculpe, não consegui analisar os dados."
                else:
                    if isinstance(resultado_analise, (pd.Series, pd.DataFrame)):
                        st.write(f"Resultado da busca na base de '{df_type}':")
                        st.dataframe(resultado_analise)
                        response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
                st.markdown(response_text)
        else: # modo chat genérico
            with st.spinner("Pensando..."):
                response = st.session_state.chat.send_message(prompt)
                response_text = response.text
                st.markdown(response_text)
    
    st.session_state.display_history.append({"role": "assistant", "content": response_text})
