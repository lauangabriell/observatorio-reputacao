# Dados locais

Para o painel histórico, copie da instalação local `reputacao_revisao/dados` os arquivos `base_treino.json` e `comentarios.json` para esta pasta. Não publique esses arquivos automaticamente.

- `base_treino.json`: objeto com `registros`, exatamente 89 IDs únicos. Cada registro contém `comment_id`, `texto`, `rotulo_atual` (negativo/neutro/positivo), `divisao` igual a treino e `historico_avaliacao01` falso. O modelo valida essas condições; não basta fabricar 89 linhas para reproduzir a base.
- `comentarios.json`: lista de registros com `comment_id`, `company`, `texto` e `published_at` (data ISO 8601).
- `historico_coleta.json`: necessário somente para expandir_coleta.py; contém listas `comment_ids`, `video_ids` e `text_hashes` das coletas anteriores. Use o histórico verdadeiro da instalação local para evitar recoleta.

As métricas agregadas publicadas não incluem esses textos. Coletar outra amostra não reproduz a avaliação histórica. As bases de desenvolvimento e a amostra reservada também não são distribuídas.
