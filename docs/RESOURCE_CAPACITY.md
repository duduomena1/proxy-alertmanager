# Capacidade disponível nos alertas

O endpoint `/alert` exibe os números enviados em `alerts[].annotations` no card (embed) do Discord, junto ao GIF,
sem repetir os dados em uma mensagem acima do card. Não é necessário configurar acesso do
proxy ao Prometheus. `/alert_minimal` e o formato legado não usam esse contrato.

O payload original contém `A=93.078...` (uso) e `C=1` (condição satisfeita).
Nenhum desses valores informa bytes. Sem `available_bytes`, disco e memória
mostram “Disponível: indisponível (não informado no webhook)”. O proxy não estima
bytes usando apenas a porcentagem e não altera a severidade nem o disparo.

## Configurar a regra no Grafana

Mantenha a consulta A de porcentagem e a condição C existentes. Acrescente
consultas **Instant** D e E na mesma fonte Prometheus. Se usar consultas Range,
crie expressões Reduce (Last) e use os IDs dessas expressões nas anotações.
Configure as anotações na **regra de alerta**, não no template do contact point.

Para o disco do exemplo, use os seletores reais das séries no Prometheus.
O webhook contém `instance=192.168.255.212`, mas o `valueString` mostra
`instance=node-exporter:9100`; confirme o alvo na fonte antes de copiar.
Restrinja também por job e outros labels que distingam servidores/ambientes.

D — bytes disponíveis para aplicações (não apenas livres para root):

```promql
node_filesystem_avail_bytes{job="node-exporter",instance="node-exporter:9100",mountpoint="/data",device="/dev/mapper/vg_images-images--btrfs--main"}
```

E — capacidade total, com exatamente os mesmos seletores:

```promql
node_filesystem_size_bytes{job="node-exporter",instance="node-exporter:9100",mountpoint="/data",device="/dev/mapper/vg_images-images--btrfs--main"}
```

Adicione estas anotações à regra:

| Nome | Valor |
|---|---|
| `available_bytes` | `{{ $values.D.Value }}` |
| `total_bytes` | `{{ $values.E.Value }}` |

Para memória, D deve consultar `node_memory_MemAvailable_bytes` e E,
`node_memory_MemTotal_bytes`, ambas com os seletores do mesmo servidor.
MemAvailable considera memória que pode ser recuperada, inclusive cache;
não substitua por MemFree se deseja capacidade disponível para aplicações.

Para CPU, adicione as consultas abaixo, ajustando o alvo:

D — porcentagem média de tempo ocioso nos últimos 5 minutos:

```promql
100 * avg by (job, instance) (rate(node_cpu_seconds_total{job="node-exporter",instance="node-exporter:9100",mode="idle"}[5m]))
```

E — quantidade de CPUs lógicas:

```promql
count by (job, instance) (node_cpu_seconds_total{job="node-exporter",instance="node-exporter:9100",mode="idle"})
```

| Nome | Valor |
|---|---|
| `cpu_idle_percent` | `{{ $values.D.Value }}` |
| `cpu_count` | `{{ $values.E.Value }}` |

Use a mesma janela de avaliação da consulta de uso. Ociosidade equivalente
não significa núcleos reservados ou capacidade garantida: 10% ocioso em 16 CPUs
lógicas equivale a 1,6 CPUs nessa janela. CPU não tem bytes “restantes”.

Em regras com vários alvos, preserve os labels que identificam cada host e,
para disco, cada dispositivo/montagem. Confira no preview de cada instância
se D/E correspondem ao mesmo recurso de A; não agregue discos ou servidores
juntos. Mantenha a condição original selecionada como condição do alerta.

## Contrato e exemplo

Envie números brutos, sem unidades e sem `humanize`, em cada alerta:

```json
"annotations": {
  "available_bytes": "1099511627776",
  "total_bytes": "10995116277760"
}
```

Resultado: **Disponível: 1.00 TiB**, **Capacidade total: 10.00 TiB**,
**Disponível (%): 10.00%**. São unidades binárias (1 TiB = 1024 GiB).
`available_bytes` pode ser enviado sozinho. Zero disponível é válido.
Valores negativos, não finitos ou templates não renderizados são ignorados;
disponível maior que total é sinalizado como inconsistente.

A mudança apenas acrescenta contexto. Para classificar um disco como “radar”
em vez de crítico, ajuste separadamente a política de alerta para considerar
espaço disponível e, se desejado, tendência de crescimento.

Referências:
- [Templates de anotações do Grafana](https://grafana.com/docs/grafana/latest/alerting/alerting-rules/templates/reference/)
- [Métricas do Node Exporter](https://prometheus.io/docs/guides/node-exporter/)
