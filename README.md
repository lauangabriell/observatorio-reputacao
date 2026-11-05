# Observatório de Reputação

Projeto acadêmico de **Lauan Gabriell Pereira Lima** para coletar comentários do YouTube, explorar sentimentos previstos e identificar assuntos recorrentes em um painel Streamlit. O domínio inicial é o Nubank.

O objetivo é conectar engenharia de dados, avaliação de modelos e uma interface que permita investigar as previsões. O projeto é experimental: não mede a opinião de todos os clientes e não determina automaticamente a qual empresa cada sentimento se refere.

## Funcionalidades

- Coleta explícita pela YouTube Data API, com identificação da empresa e organização dos resultados por execução.
- Classificação local em positivo, neutro e negativo com TF-IDF e regressão logística.
- Panorama de previsões, evolução temporal e consulta aos comentários.
- Assuntos por sentimento, identificados por regras lexicais, com contagens e inspeção dos exemplos.
- Alertas para escores próximos, múltiplas empresas e possíveis referências a contexto ausente.
- Laboratório para testar textos e seção de avaliação do modelo.

## Arquitetura

`coletar.py` configura a busca → `coleta/etl_youtube.py` coleta e prepara os comentários → `painel_dados.py` carrega os dados → `modelo.py` classifica → `revisao.py` sinaliza ambiguidades → `app.py` apresenta os resultados. `assuntos.py` identifica os temas por palavras-chave.

**Stack:** Python, pandas, scikit-learn, Streamlit, Altair, requests e python-dotenv. Não há treinamento de LLM neste projeto. Os experimentos com embeddings usam um encoder pré-treinado congelado e treinam somente o classificador.

## Executar no Windows

```powershell
git clone https://github.com/lauangabriell/observatorio-reputacao.git
cd observatorio-reputacao
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

**Os dados reais não são distribuídos neste repositório.** Para abrir o painel completo, configure os arquivos locais descritos em [dados/README.md](dados/README.md). Sem eles, a aplicação apresenta uma orientação de configuração. A reprodução integral das métricas exige as bases e divisões originais; o clone sozinho não reproduz os resultados históricos.

Para coletar novos comentários, copie `.env.example` para `.env`, configure sua chave e execute:

```powershell
.\.venv\Scripts\python.exe coletar.py --empresa "Nubank" --busca "Nubank atendimento" --aliases "Nubank" --videos 5
```

A coleta usa a cota da API. Trocar a empresa da busca não retreina nem valida o modelo para outro domínio. Nenhuma chamada à API é feita automaticamente ao abrir o painel.

## Resultados experimentais

As três linhas abaixo usam as mesmas cinco divisões e 169 comentários de desenvolvimento. São métricas agregadas sobre previsões fora do treino de cada divisão, em avaliação **exploratória**.

| Experimento | Representação e classificador | Acurácia | F1 macro | Recall positivo |
|---|---|---:|---:|---:|
| 06 | TF-IDF + regressão balanceada | 55,0% | 0,476 | 20,7% |
| 07 | Embeddings congelados + regressão balanceada | 62,7% | 0,584 | 44,8% |
| 08 | Mesmos embeddings + regressão sem balanceamento | 66,3% | 0,531 | 10,3% |

O experimento 08 ganhou acurácia, mas identificou apenas 3 dos 29 positivos, contra 13 no experimento 07. Por isso, o ganho não foi tratado como melhoria geral nem promovido ao painel. A meta de 70% ainda não foi alcançada nessa avaliação.

O **painel continua usando o modelo histórico da base v3**, com 89 exemplos e métricas próprias. Os números acima não são a acurácia dos comentários mostrados na interface. Consulte [evidencias/resumo_experimentos.json](evidencias/resumo_experimentos.json) para métricas, matrizes e hashes da base e das divisões. As saídas foram resumidas dos arquivos executados no notebook; os experimentos 06–08 não foram reexecutados nesta publicação.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes publicados verificam regras de revisão e de assuntos, incluindo múltiplos temas, duplicidade de IDs e denominadores. Eles não comprovam acurácia semântica. A interface requer verificação local com os dados configurados.

## Limitações e decisões

- Base pequena, coleta dirigida e rótulos assistidos por IA com revisão humana; não há anotação independente de dois avaliadores.
- Separação por grupos de conversa e similaridade não equivale a generalização para vídeos ou empresas inéditos.
- Os resultados de desenvolvimento já orientaram decisões; falta avaliação final em amostra reservada.
- Escores não calibrados não são porcentagens de acerto.
- O sentimento previsto é do texto inteiro; pode pertencer a outra empresa ou assunto.
- Assuntos são regras lexicais para serviços bancários, não um modelo de sentimento por aspecto. Um comentário pode contar em vários temas.
- Credenciais, comentários reais, bases anotadas, caches de modelos e ambientes virtuais ficam fora do Git.

## Autoria

Projeto desenvolvido por Lauan Gabriell Pereira Lima com assistência de IA na implementação, revisão e documentação. Os experimentos foram executados localmente e os rótulos passaram por revisão do autor. A assistência e as limitações são documentadas para permitir avaliação honesta do trabalho.
