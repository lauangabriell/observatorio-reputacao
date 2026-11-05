from pathlib import Path
import json

import altair as alt
import pandas as pd
import streamlit as st

from modelo import treinar, prever
from revisao import sinalizar
from assuntos import identificar, ranking, REGRAS
from painel_dados import fontes, ler_fonte, classificar

ROOT = Path(__file__).resolve().parent
CORES = {"positivo": "#6EE7B7", "neutro": "#94A3B8", "negativo": "#FB7185"}
st.set_page_config(page_title="Observatório | Reputação", page_icon="◉", layout="wide")
st.markdown("""<style>
.block-container {max-width:1440px;padding-top:1.2rem;padding-bottom:3rem}
h1 {letter-spacing:-.045em;font-weight:750!important;font-size:2.3rem!important;padding-bottom:.25rem!important}
h2,h3 {letter-spacing:-.025em}
[data-testid="stMetric"] {background:#131D28;border:1px solid #233142;border-radius:14px;padding:12px 16px}
[data-testid="stMetricLabel"] {color:#9DAFC0}
[data-testid="stMetricValue"] {font-weight:650}
.eyebrow {color:#6EE7B7;font-size:12px;letter-spacing:.16em;font-weight:700}
.subcopy {color:#9DAFC0;font-size:16px;max-width:760px;margin-bottom:10px}
.status {display:inline-block;border:1px solid #30443D;border-radius:100px;padding:4px 12px;color:#B4D7C7;font-size:12px;margin-bottom:6px}
</style>""", unsafe_allow_html=True)


@st.cache_resource
def carregar_modelo(base):
    return treinar(base)


@st.cache_data
def resultados(base, conteudo):
    modelo, ids = carregar_modelo(base)
    return pd.DataFrame(classificar(modelo, ids, json.loads(conteudo)))


necessarios = [ROOT / "dados/base_treino.json", ROOT / "dados/comentarios.json"]
if any(not p.exists() for p in necessarios):
    st.title("Observatório de Reputação")
    st.info("Código instalado. Para abrir o painel, configure os dados locais conforme dados/README.md. As bases reais não são distribuídas neste repositório.")
    st.stop()

base = (ROOT / "dados/base_treino.json").read_text(encoding="utf-8")
metricas = json.loads((ROOT / "evidencias/metricas_v3.json").read_text(encoding="utf-8"))
with st.sidebar:
    st.markdown("### Observatório")
    st.caption("REPUTAÇÃO · YOUTUBE")
    st.divider()
    disponiveis = fontes(ROOT)
    labels = {str(f): "Nubank · coleta de demonstração" if f.suffix == ".json" else f"Coleta {f.parent.name}" for f in disponiveis}
    fonte = st.selectbox("Fonte dos comentários", list(labels), format_func=lambda k: labels[k])
    try:
        registros = ler_fonte(fonte)
    except (ValueError, KeyError) as erro:
        st.error(str(erro))
        st.stop()
    if not registros:
        st.info("Esta coleta não tem comentários elegíveis. Selecione outra fonte.")
        st.stop()
    empresas = sorted({r["company"] for r in registros})
    empresa = st.selectbox("Empresa registrada na coleta", empresas)
    registros = [r for r in registros if r["company"] == empresa]
    incluir_treino = st.checkbox("Incluir exemplos usados no treino", value=False)
    st.divider()
    st.caption("MODELO ATIVO")
    st.caption("Experimental · treino no Nubank")
    with st.expander("Detalhes técnicos"):
        st.write("Regressão logística balanceada · base v3 · 89 exemplos · português")
        st.caption("Coleta pelo comando coletar.py. O painel não chama a API.")

modelo, ids = carregar_modelo(base)
with st.spinner("Classificando os comentários da coleta..."):
    df = resultados(base, json.dumps(registros, ensure_ascii=False))
visivel = df if incluir_treino else df[~df["usado_no_treino"]]
st.markdown('<div class="eyebrow">OBSERVATÓRIO / ANÁLISE DE REPUTAÇÃO</div>', unsafe_allow_html=True)
st.title(empresa)
st.markdown('<div class="status">MODELO EXPERIMENTAL · BASE V3</div>', unsafe_allow_html=True)
st.caption("Previsões sobre o texto completo. Sentimento por empresa exige revisão.")
st.caption(f"Fonte: {Path(fonte).parent.name} · {len(df)} comentários coletados nesta fonte · {int(df['usado_no_treino'].sum())} usados no treino")
if empresa.casefold() != "nubank":
    st.warning("O modelo foi treinado com comentários sobre o Nubank. Estas previsões para outra empresa não têm desempenho validado e podem confundir o alvo da opinião.")
panorama, assuntos, comentarios, laboratorio, avaliacao = st.tabs(["Panorama", "Assuntos", "Comentários", "Laboratório", "Avaliação do modelo"])

with panorama:
    st.caption("Distribuição das previsões do texto inteiro, incluindo casos sinalizados. Não é sentimento validado sobre a empresa nem acurácia.")
    contagem = visivel["sentimento"].value_counts()
    cols = st.columns(4)
    cols[0].metric("Comentários", len(visivel))
    for col, classe in zip(cols[1:], CORES):
        col.metric(classe.capitalize(), int(contagem.get(classe, 0)))
    st.info(f"{int(visivel['revisao_necessaria'].sum())} comentários sinalizados para revisão. Os demais não têm alerta pelas regras atuais, o que não comprova acerto nem resolução do alvo.")
    left, right = st.columns([1, 1.6])
    with left:
        st.subheader("Distribuição")
        chart = pd.DataFrame({"Sentimento": list(CORES), "Comentários": [int(contagem.get(c, 0)) for c in CORES]})
        barras = alt.Chart(chart).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
            x=alt.X("Sentimento:N", sort=list(CORES), title=None),
            y=alt.Y("Comentários:Q", scale=alt.Scale(domainMin=0), axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("Sentimento:N", scale=alt.Scale(domain=list(CORES), range=list(CORES.values())), legend=None),
            tooltip=["Sentimento", "Comentários"],
        ).properties(height=300)
        st.altair_chart(barras, use_container_width=True)
    with right:
        st.subheader("Volume ao longo do tempo")
        tempo = visivel.copy()
        tempo["dia"] = pd.to_datetime(tempo["published_at"], errors="coerce", utc=True).dt.floor("D")
        tempo = tempo.dropna(subset=["dia"])
        if tempo.empty:
            st.info("Não há datas válidas nesta seleção.")
        else:
            diario = tempo.groupby(["dia", "sentimento"]).size().unstack(fill_value=0).reindex(columns=list(CORES), fill_value=0)
            diario = diario.reindex(pd.date_range(diario.index.min(), diario.index.max(), freq="D"), fill_value=0)
            serie = diario.rename_axis("Dia").reset_index().melt("Dia", var_name="Sentimento", value_name="Comentários")
            linhas = alt.Chart(serie).mark_line(strokeWidth=2).encode(
                x="Dia:T", y=alt.Y("Comentários:Q", scale=alt.Scale(domainMin=0)),
                color=alt.Color("Sentimento:N", scale=alt.Scale(domain=list(CORES), range=list(CORES.values()))),
                tooltip=[alt.Tooltip("Dia:T", format="%d/%m/%Y"), "Sentimento", "Comentários"],
            ).properties(height=300)
            st.altair_chart(linhas, use_container_width=True)
        st.caption("Datas de publicação dos comentários desta amostra, com dias sem comentários preenchidos com zero. Não é volume total do YouTube.")

with assuntos:
    st.subheader("Assuntos por sentimento")
    st.caption("Temas identificados por palavras-chave, cruzados com a previsão do texto inteiro. Não indica o sentimento específico sobre cada tema ou empresa.")
    st.caption("Categorias voltadas a serviços bancários; outras empresas podem exigir novas regras. Os filtros de fonte, empresa e exemplos de treino da lateral também se aplicam aqui.")
    filtro_alertas = st.checkbox("Ocultar comentários sinalizados para revisão", value=False, key="assuntos_alertas")
    dados_assuntos = visivel[~visivel["revisao_necessaria"]] if filtro_alertas else visivel
    st.caption(f"{len(dados_assuntos)} comentários na seleção. Um comentário pode aparecer em vários assuntos; os percentuais podem somar mais de 100%. Ausência de alerta não comprova acerto.")
    for coluna, sentimento in zip(st.columns(3), CORES):
        with coluna:
            st.markdown(f"### {sentimento.capitalize()}")
            subset = dados_assuntos[dados_assuntos["sentimento"] == sentimento]
            resumo = ranking(subset.to_dict("records"))
            st.caption(f"Base: {len(subset)} comentários previstos como {sentimento}.")
            if not resumo:
                st.info("Nenhum comentário nesta seleção.")
            else:
                tabela_assuntos = pd.DataFrame(resumo)
                grafico_assuntos = alt.Chart(tabela_assuntos).mark_bar(color=CORES[sentimento], cornerRadiusEnd=3).encode(
                    x=alt.X("Comentários:Q", axis=alt.Axis(tickMinStep=1), scale=alt.Scale(domainMin=0)),
                    y=alt.Y("Assunto:N", sort="-x", title=None, axis=alt.Axis(labelLimit=180)),
                    tooltip=["Assunto:N", "Comentários:Q", alt.Tooltip("Percentual:Q", format=".1f", title="% desta classe")],
                ).properties(height=max(160, 32 * len(resumo)))
                st.altair_chart(grafico_assuntos, use_container_width=True)
                st.dataframe(tabela_assuntos.assign(Percentual=tabela_assuntos["Percentual"].map(lambda v: f"{v:.1f}%")), hide_index=True, use_container_width=True)
    st.divider()
    st.subheader("Confira os comentários de cada assunto")
    classe_assunto = st.selectbox("Sentimento previsto", list(CORES), key="classe_assunto")
    inspecao = dados_assuntos[dados_assuntos["sentimento"] == classe_assunto].copy()
    resumo_inspecao = ranking(inspecao.to_dict("records"))
    if resumo_inspecao:
        tema = st.selectbox("Assunto", [r["Assunto"] for r in resumo_inspecao], key="tema_assunto")
        inspecao = inspecao[inspecao["texto"].map(lambda t: tema in identificar(t))]
        st.caption(f"{len(inspecao)} comentários · sentimento previsto para o texto completo.")
        st.dataframe(inspecao[["texto", "sentimento", "status_revisao", "comment_id"]].rename(columns={"texto": "Comentário", "sentimento": "Previsão do texto", "status_revisao": "Revisão", "comment_id": "ID"}), hide_index=True, use_container_width=True)
    else:
        st.info("Não há comentários dessa classe com os filtros atuais.")
    with st.expander("Como os assuntos são identificados"):
        st.write("Regras lexicais experimentais, sem modelo adicional e sem chamada à API. Uma menção pode se referir a outra empresa, uma dúvida ou um relato. Outros / não identificado significa ausência de correspondência nas regras, não ausência de assunto.")
        for nome, regra in REGRAS.items():
            st.text(f"{nome}: {regra}")

with comentarios:
    st.subheader("Inspeção de comentários")
    a, b = st.columns([1, 2])
    filtro = a.selectbox("Previsão do texto", ["todos", *CORES])
    busca = b.text_input("Buscar no texto", placeholder="Busque um termo, produto ou problema")
    tabela = visivel if filtro == "todos" else visivel[visivel["sentimento"] == filtro]
    status = st.selectbox("Alertas", ["todos", "revisão necessária", "sem alerta heurístico"])
    if status != "todos":
        tabela = tabela[tabela["revisao_necessaria"] == (status == "revisão necessária")]
    if busca:
        tabela = tabela[tabela["texto"].str.contains(busca, case=False, regex=False, na=False)]
    st.caption(f"{len(tabela)} comentários nesta seleção. Escores não calibrados: não são porcentagens de acerto.")
    st.dataframe(tabela[["texto", "previsao_texto", "status_revisao", "motivos_revisao", "marcas_detectadas", "margem_escores", "usado_no_treino", "comment_id"]].rename(columns={"texto": "Comentário", "previsao_texto": "Previsão do texto", "status_revisao": "Status", "motivos_revisao": "Motivos", "marcas_detectadas": "Marcas detectadas", "margem_escores": "Margem", "usado_no_treino": "Usado no treino", "comment_id": "ID"}), hide_index=True, use_container_width=True)
    st.download_button("Exportar seleção em CSV", tabela.to_csv(index=False).encode("utf-8-sig"), "previsoes_observatorio.csv", "text/csv")

with laboratorio:
    st.subheader("Experimente um comentário")
    st.caption("O modelo recebe somente o texto. A empresa selecionada organiza a coleta; ela não é uma instrução adicional para o classificador.")
    with st.form("teste"):
        texto = st.text_area("Texto do comentário", placeholder="Digite um comentário para examinar a previsão", height=130)
        enviar = st.form_submit_button("Analisar comentário")
    if enviar:
        if not texto.strip():
            st.info("Digite um comentário antes de analisar.")
        else:
            r = prever(modelo, [texto])[0]
            alerta = sinalizar(texto, empresa, r)
            st.metric("Status", "Revisão necessária" if alerta["revisao_necessaria"] else "Sem alerta heurístico")
            st.write(f"**Sentimento sobre {empresa}:** não determinado automaticamente.")
            st.write("**Previsão bruta do texto inteiro:**", r["sentimento"])
            st.caption(f"Margem entre os dois maiores escores: {alerta['margem_escores']:.3f}.")
            if alerta["revisao_necessaria"]:
                st.warning("Motivos: " + alerta["motivos_revisao"].replace("_", " "))
            else:
                st.caption("Ausência de alerta não comprova acerto ou identificação do alvo.")
            st.caption("Marcas detectadas pela lista limitada: " + (alerta["marcas_detectadas"] or "nenhuma"))
            st.caption("Distribuição de escores do modelo, sem calibração ou garantia de acerto.")
            for c in CORES:
                st.progress(r[f"escore_{c}"], text=f"{c.capitalize()}: {r[f'escore_{c}']:.3f}")

with avaliacao:
    st.subheader("Evidências da base v3")
    st.caption("Validação cruzada exploratória em cinco divisões. Estes números não medem os comentários exibidos no panorama.")
    linhas = []
    nomes = {"referencia_majoritaria": "Referência majoritária", "atual": "Regressão sem balanceamento", "balanceado": "Regressão balanceada"}
    for nome, r in metricas["modelos"].items():
        s = r["resumo"]
        linhas.append({"Configuração": nomes[nome], "Acurácia média": f"{s['acuracia']['media']:.1%}", "F1 macro médio": f"{s['f1_macro']['media']:.3f}", "Recall positivo médio": f"{s['recall_positivo']['media']:.1%}"})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True)
    st.info("A meta de 80% ainda não foi atingida. Base pequena e rótulos assistidos por IA revisados pelo candidato; falta uma avaliação final em amostra nova e reservada.")
    with st.expander("O que muda ao trocar de empresa?"):
        st.write("A busca encontra outros vídeos; os aliases ajudam a selecionar comentários. O classificador continua com os mesmos pesos treinados no Nubank. Menções à empresa não garantem que a opinião seja sobre ela. Exemplo: ‘iFood é bom, mas o Nubank é ruim’ exige distinguir os alvos.")
    with st.expander("Procedência e limites"):
        st.write("Treino: 36 negativos, 35 neutros e 18 positivos. TF-IDF e regressão balanceada ajustados aos 89 exemplos para esta demonstração. Na validação, cada vocabulário foi ajustado somente ao treino da respectiva divisão. Os exemplos usados no treino ficam ocultos por padrão no panorama, mas isso não torna os demais um teste independente.")
        st.write("O coletor usa uma busca limitada de vídeos e comentários. Os dados não representam todos os clientes ou todas as opiniões sobre a empresa. Alguns rótulos dependem do comentário principal, que o classificador atual não recebe.")

    with st.expander("Regras de revisão experimental"):
        st.write("Alerta se a margem dos dois maiores escores for menor que 0,10, se várias marcas da lista forem mencionadas, se o alvo não for detectado, se houver uma possível referência a fala anterior ou se a empresa não for Nubank. Limiar provisório sem calibração. A lista de marcas é incompleta e os alertas podem falhar. Não são um novo modelo nem nova medida de acurácia.")
