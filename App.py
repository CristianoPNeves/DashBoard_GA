import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import datetime
import os
import glob
from pypdf import PdfReader

# Configuração da Página
st.set_page_config(
    page_title="Gestão de Ocorrências - Chamados Técnicos & Serviços",
    page_icon="🏢",
    layout="wide"
)

# Estilização CSS Personalizada
st.markdown("""
<style>
    .main-header { font-size: 26px; font-weight: bold; color: #1B365D; margin-bottom: 5px; }
    .sub-header { font-size: 14px; color: #595959; margin-bottom: 20px; }
    .metric-card { background-color: #F0F4F8; border-left: 5px solid #1B365D; padding: 12px 15px; border-radius: 6px; }
</style>
""", unsafe_allow_html=True)


# Extração do texto do PDF
def extrair_texto_pdf(file_source):
    reader = PdfReader(file_source)
    texto_completo = ""
    for page in reader.pages:
        texto = page.extract_text()
        if texto:
            texto_completo += texto + "\n"
    return texto_completo


# Parsing do Relatório
def parsear_relatorio(texto, nome_arquivo=""):
    registros = []

    cod_cliente_match = re.search(r'([A-Z0-9]{3,8}\s+\d{3,5})', texto)
    end_match = re.search(r'End\.?\s*Atendimento:\s*([^\n]+)', texto)

    if cod_cliente_match:
        codigo_cliente = cod_cliente_match.group(1).strip()
    else:
        codigo_cliente = nome_arquivo.replace(".pdf", "") if nome_arquivo else "Desconhecido"

    if end_match:
        raw_end = end_match.group(1).strip()
    else:
        end_linha = re.search(r'End\.:?\s*([^\n|]+)', texto)
        raw_end = end_linha.group(1).strip() if end_linha else "Endereço Não Informado"

    endereco_limpo = re.sub(r'\s*-\s*IMPRESSO.*', '', raw_end, flags=re.IGNORECASE).strip()

    os_blocks = re.split(r'(?=(?:A\d{5}\s+\d{2}/\d{2}/\d{4})|(?:\d{2}/\d{2}/\d{4}\s+.*\s+A\d{5}))', texto)

    for block in os_blocks:
        if "PREVENTIVA" in block or "MANUTENCAO PREVENTIVA" in block or "MANUTENCAC" in block:
            continue

        if "TECNICOS:" not in block and "TECNICO" not in block and "CHAMADO" not in block and "SERVICO" not in block and "SERVICOS" not in block and "RETORNO" not in block:
            continue

        os_match = re.search(r'A\d{5}', block)
        if not os_match: continue
        os_num = os_match.group(0)

        data_match = re.search(r'(\d{2}/\d{2}/\d{4})', block)
        data_str = data_match.group(1) if data_match else ""

        try:
            data_dt = datetime.datetime.strptime(data_str, "%d/%m/%Y").date()
            ano_mes_str = data_dt.strftime("%Y-%m")
            ano_mes_nome = data_dt.strftime("%m/%Y")
        except:
            data_dt = datetime.date.today()
            ano_mes_str = data_dt.strftime("%Y-%m")
            ano_mes_nome = data_dt.strftime("%m/%Y")

        tech_match = re.search(r'TECNICOS?:\s*([^\n|]+)', block)
        tecnico = tech_match.group(1).strip() if tech_match else "Não Informado"

        horas = re.findall(r'(\d{2}:\d{2})', block)
        hora_passado = horas[0] if len(horas) > 0 else "00:00"
        hora_entrada = horas[1] if len(horas) > 1 else hora_passado
        hora_saida = horas[-1] if len(horas) > 2 else hora_entrada

        if "SERVICO" in block or "SERVICOS" in block or "ORCAMENTO" in block or "TROCAR" in block:
            categoria_evento = "Serviço"
        else:
            categoria_evento = "Chamado Técnico"

        defeito_rec = "PARADO"
        if "PARADO FORA NIVEL" in block:
            defeito_rec = "PARADO FORA NIVEL"
        elif "PORTA LENTA" in block:
            defeito_rec = "PORTA LENTA"
        elif "PICO DE ENERGIA" in block:
            defeito_rec = "PARADO APÓS PICO DE ENERGIA"
        elif "GENTE" in block or "PRESA" in block:
            defeito_rec = "GENTE PRESA"
        elif "VERIFICAR OPERADOR" in block:
            defeito_rec = "VERIFICAR OPERADOR PORTA LENTO"
        elif "TROCAR" in block or "AMOSTRA" in block:
            defeito_rec = "TROCA DE DISPOSITIVO / PEÇA"

        elevador = "ELEVADOR 1"
        if "ELEVADOR 3" in block or "3-8231" in block:
            elevador = "ELEVADOR 3"
        elif "ELEVADOR 2" in block or "2-8230" in block:
            elevador = "ELEVADOR 2"
        elif "1-8229" in block and "2-8230" in block and "3-8231" in block:
            elevador = "ELEVADORES (TODOS)"

        peca = "Não Informada"
        if "PORTA" in block:
            peca = "Porta"
        elif "TRINCO" in block:
            peca = "Trinco"
        elif "PLACA" in block:
            peca = "Placa Eletrônica"
        elif "CABINA" in block or "CARINA" in block:
            peca = "Cabina"

        def_const = "Geral"
        if "DESREGULADO" in block:
            def_const = "Desregulados / Desajustados"
        elif "ALTERADO" in block:
            def_const = "Sinal/Placa Alterada"
        elif "TRAVADO" in block:
            def_const = "Componente Travado"

        gente_presa = "Sim" if ("GENTE" in block and "PRESA" in block) else "Não"

        try:
            t_pass = datetime.datetime.strptime(hora_passado, "%H:%M")
            t_ent = datetime.datetime.strptime(hora_entrada, "%H:%M")
            t_sai = datetime.datetime.strptime(hora_saida, "%H:%M")
            resp_min = int((t_ent - t_pass).total_seconds() / 60)
            atend_min = int((t_sai - t_ent).total_seconds() / 60)
            if resp_min < 0: resp_min += 1440
            if atend_min < 0: atend_min += 1440
        except:
            resp_min, atend_min = 0, 0

        registros.append({
            "Código Cliente": codigo_cliente,
            "Endereço": endereco_limpo,
            "OS": os_num,
            "Data_Obj": data_dt,
            "AnoMes_Sort": ano_mes_str,
            "Mês/Ano": ano_mes_nome,
            "Data": data_str,
            "Técnico": tecnico,
            "Hora Chamado": hora_passado, "Hora Chegada": hora_entrada, "Hora Saída": hora_saida,
            "Tempo Resposta (min)": resp_min,
            "Tempo Resposta (h)": round(resp_min / 60.0, 1),
            "Tempo Atendimento (min)": atend_min,
            "Tempo Atendimento (h)": round(atend_min / 60.0, 1),
            "Categoria": categoria_evento,
            "Sintoma / Defeito Reclamado": defeito_rec, "Elevador": elevador,
            "Peça Afetada": peca, "Defeito Constatado": def_const, "Gente Presa": gente_presa
        })

    return pd.DataFrame(registros)


# Carregamento de Relatórios
def carregar_dados(uploaded_files):
    lista_dfs = []

    if uploaded_files:
        for f in uploaded_files:
            texto = extrair_texto_pdf(f)
            df_t = parsear_relatorio(texto, f.name)
            if not df_t.empty:
                lista_dfs.append(df_t)
    else:
        pasta = "relatorios"
        if os.path.exists(pasta):
            arquivos = glob.glob(f"{pasta}/*.pdf")
            for arq in arquivos:
                nome_arq = os.path.basename(arq)
                with open(arq, "rb") as f:
                    texto = extrair_texto_pdf(f)
                    df_t = parsear_relatorio(texto, nome_arq)
                    if not df_t.empty:
                        lista_dfs.append(df_t)

    if lista_dfs:
        return pd.concat(lista_dfs, ignore_index=True)
    return pd.DataFrame()


# Base Exemplo
DADOS_DEMO = [
    {"Código Cliente": "SANT 398", "Endereço": "RUA SANTA CRUZ, 398", "OS": "A70100",
     "Data_Obj": datetime.date(2026, 5, 10), "AnoMes_Sort": "2026-05", "Mês/Ano": "05/2026", "Data": "10/05/2026",
     "Técnico": "WILLIAM MERCURIO", "Tempo Resposta (h)": 1.1, "Tempo Atendimento (h)": 1.5,
     "Categoria": "Chamado Técnico", "Sintoma / Defeito Reclamado": "PARADO FORA NIVEL", "Elevador": "ELEVADOR 3",
     "Peça Afetada": "Não Informada", "Defeito Constatado": "Geral", "Gente Presa": "Não"},
    {"Código Cliente": "SANT 398", "Endereço": "RUA SANTA CRUZ, 398", "OS": "A74200",
     "Data_Obj": datetime.date(2026, 6, 12), "AnoMes_Sort": "2026-06", "Mês/Ano": "06/2026", "Data": "12/06/2026",
     "Técnico": "EDISON PEREIRA", "Tempo Resposta (h)": 0.9, "Tempo Atendimento (h)": 1.0,
     "Categoria": "Chamado Técnico", "Sintoma / Defeito Reclamado": "PARADO NO 5°A", "Elevador": "ELEVADOR 1",
     "Peça Afetada": "Trinco", "Defeito Constatado": "Desregulados / Desajustados", "Gente Presa": "Não"},
    {"Código Cliente": "SANT 398", "Endereço": "RUA SANTA CRUZ, 398", "OS": "A78541",
     "Data_Obj": datetime.date(2026, 7, 6), "AnoMes_Sort": "2026-07", "Mês/Ano": "07/2026", "Data": "06/07/2026",
     "Técnico": "WILLIAM MERCURIO", "Tempo Resposta (h)": 1.0, "Tempo Atendimento (h)": 2.5,
     "Categoria": "Chamado Técnico", "Sintoma / Defeito Reclamado": "PARADO FORA NIVEL", "Elevador": "ELEVADOR 3",
     "Peça Afetada": "Não Informada", "Defeito Constatado": "Geral", "Gente Presa": "Não"},
    {"Código Cliente": "SANT 398", "Endereço": "RUA SANTA CRUZ, 398", "OS": "A79218",
     "Data_Obj": datetime.date(2026, 7, 12), "AnoMes_Sort": "2026-07", "Mês/Ano": "07/2026", "Data": "12/07/2026",
     "Técnico": "EDISON PEREIRA", "Tempo Resposta (h)": 1.0, "Tempo Atendimento (h)": 0.3,
     "Categoria": "Chamado Técnico", "Sintoma / Defeito Reclamado": "PORTA LENTA", "Elevador": "ELEVADOR 2",
     "Peça Afetada": "Porta", "Defeito Constatado": "Desregulados / Desajustados", "Gente Presa": "Não"}
]

# --- SIDEBAR ---
st.sidebar.title("🏢 Painel de Controle")

uploaded_files = st.sidebar.file_uploader(
    "Upload de Relatórios PDF (Vários arquivos)",
    type=["pdf"],
    accept_multiple_files=True
)

df = carregar_dados(uploaded_files)

if df.empty:
    df = pd.DataFrame(DADOS_DEMO)
    st.sidebar.info("Exibindo dados de demonstração.")

st.sidebar.markdown("---")
st.sidebar.subheader("📅 Filtro de Período")

min_data = df["Data_Obj"].min()
max_data = df["Data_Obj"].max()

data_inicio, data_fim = st.sidebar.date_input(
    "Selecione o Período:",
    value=(min_data, max_data),
    min_value=min_data,
    max_value=max_data,
    format="DD/MM/YYYY"
)

st.sidebar.markdown("---")
st.sidebar.subheader("📍 Filtro de Endereço")

todos_enderecos = list(df["Endereço"].unique())
enderecos_selecionados = st.sidebar.multiselect(
    "Selecionar Endereço do Cliente:",
    options=todos_enderecos,
    default=todos_enderecos
)

# Filtros Combinados
df_filtered = df[
    (df["Endereço"].isin(enderecos_selecionados)) &
    (df["Data_Obj"] >= data_inicio) &
    (df["Data_Obj"] <= data_fim)
    ]

df_chamados = df_filtered[df_filtered["Categoria"] == "Chamado Técnico"]
df_servicos = df_filtered[df_filtered["Categoria"] == "Serviço"]

# --- CABEÇALHO ---
st.markdown('<div class="main-header">📊 Painel Estratégico: Chamados Técnicos vs. Serviços</div>',
            unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-header">Análise segregada no período de <b>{data_inicio.strftime("%d/%m/%Y")}</b> até <b>{data_fim.strftime("%d/%m/%Y")}</b> (Preventivas Excluídas).</div>',
    unsafe_allow_html=True)

# KPIs Globais
c1, c2, c3, c4 = st.columns(4)
c1.metric("Endereços Analisados", len(enderecos_selecionados))
c2.metric("Total Chamados Técnicos", len(df_chamados))
c3.metric("Total de Serviços Executados", len(df_servicos))
c4.metric("Passageiros Retidos", len(df_filtered[df_filtered["Gente Presa"] == "Sim"]))

st.markdown("<br>", unsafe_allow_html=True)

# --- ABAS SEPARADAS DE ANÁLISE ---
tab_chamados, tab_servicos, tab_matriz, tab_base = st.tabs([
    "🚨 Chamados Técnicos (Corretivos)",
    "🛠️ Serviços & Execuções",
    "🔍 Matriz Comparativa",
    "📋 Base de Dados Consolidada"
])

# ==========================================
# ABA 1: CHAMADOS TÉCNICOS
# ==========================================
with tab_chamados:
    st.markdown("### 🚨 Análise Exclusiva de Chamados Técnicos (Paradas e Emergências)")

    # EXIBE O GRÁFICO MENSAL CASO 1 ENDEREÇO SEJA SELECIONADO E O PERÍODO TENHA MAIS DE 1 MÊS
    num_meses_distintos = df_chamados["AnoMes_Sort"].nunique()

    if len(enderecos_selecionados) == 1 and num_meses_distintos > 1:
        end_unico = enderecos_selecionados[0]
        st.markdown(f"#### 📅 Evolução Mensal de Chamados Técnicos — `{end_unico}`")

        df_mensal = df_chamados.groupby(["AnoMes_Sort", "Mês/Ano"]).size().reset_index(name="Qtd Chamados").sort_values(
            "AnoMes_Sort")

        fig_mensal = px.bar(
            df_mensal,
            x="Mês/Ano",
            y="Qtd Chamados",
            text="Qtd Chamados",
            color_discrete_sequence=["#1B365D"]
        )
        fig_mensal.update_traces(textposition='outside')
        fig_mensal.update_layout(
            height=380,
            xaxis=dict(title="Mês / Ano"),
            yaxis=dict(title="Quantidade de Chamados Técnicos")
        )
        st.plotly_chart(fig_mensal, use_container_width=True)
        st.markdown("---")

    col_c1, col_c2 = st.columns(2)

    with col_c1:
        st.subheader("1. Chamados Técnicos por Endereço")
        df_rank_c = df_chamados.groupby("Endereço").size().reset_index(name="Quantidade").sort_values(by="Quantidade",
                                                                                                      ascending=False)

        if not df_rank_c.empty:
            fig_rank_c = px.bar(
                df_rank_c,
                x="Quantidade",
                y="Endereço",
                orientation='h',
                text="Quantidade",
                color="Endereço",
                color_discrete_sequence=px.colors.qualitative.Prism
            )
            fig_rank_c.update_traces(textposition='outside')
            fig_rank_c.update_layout(
                height=400,
                showlegend=False,
                yaxis=dict(autorange="reversed", title="Endereço do Cliente"),
                xaxis=dict(title="Qtd de Chamados Técnicos")
            )
            st.plotly_chart(fig_rank_c, use_container_width=True)
        else:
            st.info("Nenhum chamado técnico registrado no período.")

    with col_c2:
        st.subheader("2. Tempo Médio de Resposta/Chegada (horas)")
        df_sla_c = df_chamados.groupby("Endereço")["Tempo Resposta (h)"].mean().reset_index()

        if not df_sla_c.empty:
            fig_sla_c = px.bar(
                df_sla_c,
                x="Endereço",
                y="Tempo Resposta (h)",
                text_auto='.1f',
                color="Tempo Resposta (h)",
                color_continuous_scale="Reds"
            )
            fig_sla_c.update_traces(texttemplate='%{y:.1f} h', textposition='outside')
            fig_sla_c.update_layout(
                height=400,
                coloraxis_showscale=False,
                xaxis=dict(title="Endereço do Cliente"),
                yaxis=dict(title="Tempo Resposta (horas)")
            )
            st.plotly_chart(fig_sla_c, use_container_width=True)
        else:
            st.info("Nenhum atendimento de chamado técnico no período.")

    st.markdown("---")

    st.subheader("3. Tempo Médio de Atendimento/Reparo dos Chamados Técnicos (horas)")
    df_atend_c = df_chamados.groupby("Endereço")["Tempo Atendimento (h)"].mean().reset_index().sort_values(
        by="Tempo Atendimento (h)", ascending=False)

    if not df_atend_c.empty:
        fig_atend_c = px.bar(
            df_atend_c,
            x="Endereço",
            y="Tempo Atendimento (h)",
            text_auto='.1f',
            color="Tempo Atendimento (h)",
            color_continuous_scale="Oranges"
        )
        fig_atend_c.update_traces(texttemplate='%{y:.1f} h', textposition='outside')
        fig_atend_c.update_layout(
            height=380,
            coloraxis_showscale=False,
            xaxis=dict(title="Endereço do Cliente"),
            yaxis=dict(title="Duração da Manutenção/Reparo (horas)")
        )
        st.plotly_chart(fig_atend_c, use_container_width=True)
    else:
        st.info("Nenhum tempo de reparo registrado no período.")

# ==========================================
# ABA 2: SERVIÇOS E EXECUÇÕES
# ==========================================
with tab_servicos:
    st.markdown("### 🛠️ Análise Exclusiva de Serviços (Trocas de Peças, Reformas e Adequações)")

    col_s1, col_s2 = st.columns(2)

    with col_s1:
        st.subheader("1. Volume de Serviços Executados por Endereço")
        df_rank_s = df_servicos.groupby("Endereço").size().reset_index(name="Quantidade").sort_values(by="Quantidade",
                                                                                                      ascending=False)

        if not df_rank_s.empty:
            fig_rank_s = px.bar(
                df_rank_s,
                x="Quantidade",
                y="Endereço",
                orientation='h',
                text="Quantidade",
                color="Endereço",
                color_discrete_sequence=px.colors.qualitative.Dark24
            )
            fig_rank_s.update_traces(textposition='outside')
            fig_rank_s.update_layout(
                height=400,
                showlegend=False,
                yaxis=dict(autorange="reversed", title="Endereço do Cliente"),
                xaxis=dict(title="Quantidade de Serviços")
            )
            st.plotly_chart(fig_rank_s, use_container_width=True)
        else:
            st.info("Nenhum serviço registrado no período.")

    with col_s2:
        st.subheader("2. Duração Média de Execução dos Serviços (horas de trabalho)")
        df_dur_s = df_servicos.groupby("Endereço")["Tempo Atendimento (h)"].mean().reset_index()

        if not df_dur_s.empty:
            fig_dur_s = px.bar(
                df_dur_s,
                x="Endereço",
                y="Tempo Atendimento (h)",
                text_auto='.1f',
                color="Tempo Atendimento (h)",
                color_continuous_scale="Blues"
            )
            fig_dur_s.update_traces(texttemplate='%{y:.1f} h', textposition='outside')
            fig_dur_s.update_layout(
                height=400,
                coloraxis_showscale=False,
                xaxis=dict(title="Endereço do Cliente"),
                yaxis=dict(title="Duração do Serviço (horas)")
            )
            st.plotly_chart(fig_dur_s, use_container_width=True)
        else:
            st.info("Nenhum tempo de serviço computado no período.")

# ==========================================
# ABA 3: MATRIZ DE PROBLEMAS E SINTOMAS
# ==========================================
with tab_matriz:
    st.markdown("### 🔍 Apontamento de Defeitos e Componentes por Endereço")

    col_p1, col_p2 = st.columns([6, 4])

    with col_p1:
        st.subheader("Matriz de Sintomas/Problemas por Endereço")
        if not df_filtered.empty:
            matrix_prob = pd.crosstab(df_filtered["Endereço"], df_filtered["Sintoma / Defeito Reclamado"])
            fig_matrix = px.imshow(
                matrix_prob,
                labels=dict(x="Sintoma Reclamado", y="Endereço do Cliente", color="Ocorrências"),
                color_continuous_scale="Blues",
                text_auto=True
            )
            fig_matrix.update_layout(height=450)
            st.plotly_chart(fig_matrix, use_container_width=True)
        else:
            st.info("Nenhum dado encontrado para gerar a matriz no período.")

    with col_p2:
        st.subheader("Componentes Mais Afetados (Geral)")
        df_pecas = df_filtered[df_filtered["Peça Afetada"] != "Não Informada"]
        if not df_pecas.empty:
            pecas_count = df_pecas["Peça Afetada"].value_counts().reset_index()
            fig_pecas = px.pie(
                pecas_count, names="Peça Afetada", values="count",
                hole=0.4, color_discrete_sequence=px.colors.sequential.Blues_r
            )
            fig_pecas.update_layout(height=450)
            st.plotly_chart(fig_pecas, use_container_width=True)
        else:
            st.info("Sem dados de peças para o período e filtro atuais.")

# ==========================================
# ABA 4: BASE CONSOLIDADA
# ==========================================
with tab_base:
    st.markdown("### 📋 Base Consolidada de Eventos")
    st.dataframe(
        df_filtered[["Endereço", "Código Cliente", "Categoria", "OS", "Data", "Elevador", "Sintoma / Defeito Reclamado",
                     "Peça Afetada", "Técnico", "Tempo Resposta (h)", "Tempo Atendimento (h)"]],
        use_container_width=True
    )

    csv_data = df_filtered.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Baixar Relatório Consolidado (CSV)",
        data=csv_data,
        file_name="relatorio_chamados_e_servicos.csv",
        mime="text/csv"
    )