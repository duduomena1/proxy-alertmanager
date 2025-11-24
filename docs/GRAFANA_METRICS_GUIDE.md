# 📊 Guia Completo de Métricas Grafana/Prometheus para Templates

## 🔍 Visão Geral

Este documento contém as informações oficiais sobre métricas disponíveis nos templates de notificação do Grafana e Prometheus, com estratégias práticas para implementação no proxy Discord.

---

## 🔑 Dados Principais da Notificação

Segundo a documentação oficial do Grafana, você tem acesso a estas variáveis principais:

| Variável | Tipo | Descrição | Exemplo de Uso |
|----------|------|-----------|----------------|
| `.Receiver` | string | Nome do contact point | `"discord-webhook"` |
| `.Status` | string | "firing" ou "resolved" | `{{ .Status }}` |
| `.Alerts` | []Alert | Lista de todos os alertas | `{{ len .Alerts }}` |
| `.Alerts.Firing` | []Alert | Alertas ativos | `{{ len .Alerts.Firing }}` |
| `.Alerts.Resolved` | []Alert | Alertas resolvidos | `{{ len .Alerts.Resolved }}` |
| `.GroupLabels` | KV | Labels que agrupam os alertas | `{{ .GroupLabels.alertname }}` |
| `.CommonLabels` | KV | Labels comuns a todos os alertas | `{{ .CommonLabels.instance }}` |
| `.CommonAnnotations` | KV | Annotations comuns | `{{ .CommonAnnotations.summary }}` |
| `.ExternalURL` | string | Link para o Grafana/Alertmanager | `{{ .ExternalURL }}` |
| `.GroupKey` | string | Chave de identificação do grupo | Para debugging |
| `.TruncatedAlerts` | integer | Número de alertas truncados | Webhook/OnCall apenas |

---

## 🏷️ Dados de Cada Alerta Individual

Para cada alerta em `.Alerts`, você tem acesso a:

| Campo | Tipo | Descrição | Uso no Template | Confiabilidade |
|-------|------|-----------|-----------------|----------------|
| `.Labels` | KV | Labels do alerta | `{{ .Labels.instance }}` | ✅ **Sempre presente** |
| `.Annotations` | KV | Annotations do alerta | `{{ .Annotations.summary }}` | ✅ **Sempre presente** |
| `.Values` | KV | **VALORES DAS MÉTRICAS** | `{{ .Values.A }}` | ⚠️ **Condicional** |
| `.StartsAt` | Time | Quando o alerta iniciou | `{{ .StartsAt }}` | ✅ **Sempre presente** |
| `.EndsAt` | Time | Quando o alerta terminou | `{{ .EndsAt }}` | ⚠️ **Apenas resolvidos** |
| `.Status` | string | Status individual | `{{ .Status }}` | ✅ **Sempre presente** |
| `.ValueString` | string | String com valores formatados | `{{ .ValueString }}` | ✅ **Grafana-managed** |
| `.GeneratorURL` | string | Link para fonte do alerta | `{{ .GeneratorURL }}` | ✅ **Sempre presente** |
| `.Fingerprint` | string | ID único do alerta | `{{ .Fingerprint }}` | ✅ **Sempre presente** |

### 🎯 Campos Específicos do Grafana (Grafana-managed alerts)

| Campo | Tipo | Descrição | Uso |
|-------|------|-----------|-----|
| `.DashboardURL` | string | Link para dashboard | Navigation |
| `.PanelURL` | string | Link para painel específico | Deep linking |
| `.SilenceURL` | string | Link para silenciar alerta | Actions |
| `.OrgID` | integer | ID da organização | Multi-tenancy |

---

## 🔍 Labels Confiáveis para Identificação

### ✅ **Sempre Disponíveis:**
```go
instance: {{ .Labels.instance | default "unknown" }}
job: {{ .Labels.job | default "unknown" }}
alertname: {{ .Labels.alertname | default "unnamed" }}
```

### ⚠️ **Condicionalmente Disponíveis:**
```go
{{/* Disco */}}
{{- if .Labels.device -}}
device: {{ .Labels.device }}
mountpoint: {{ .Labels.mountpoint | default "/" }}
fstype: {{ .Labels.fstype | default "unknown" }}
{{- end -}}

{{/* Container */}}
{{- if .Labels.container -}}
container: {{ .Labels.container }}
{{- else if .Labels.container_name -}}
container: {{ .Labels.container_name }}
{{- end -}}

{{/* Kubernetes */}}
{{- if .Labels.pod -}}
pod: {{ .Labels.pod }}
namespace: {{ .Labels.namespace | default "default" }}
{{- end -}}
```

---

## 🎯 Estratégias de Detecção de Tipos de Alerta

### 1. **Detecção por Labels (Recomendado)**
```go
{{/* Determinar tipo de alerta baseado nos labels */}}
{{- $alertType := "system" -}}

{{/* Disco - Presença de device */}}
{{- if .Labels.device -}}
  {{- $alertType = "disk" -}}

{{/* Container - Múltiplas verificações */}}
{{- else if (or 
    (.Labels.container) 
    (.Labels.container_name)
    (contains "container" (.Labels.job | lower))
    (contains "docker" (.Labels.job | lower))
    (contains "pod" (.Labels.job | lower))
) -}}
  {{- $alertType = "container" -}}

{{/* CPU - Nome do alerta */}}
{{- else if (contains "cpu" (.Labels.alertname | lower)) -}}
  {{- $alertType = "cpu" -}}

{{/* Memória - Nome do alerta */}}
{{- else if (or 
    (contains "memory" (.Labels.alertname | lower)) 
    (contains "mem" (.Labels.alertname | lower))
) -}}
  {{- $alertType = "memory" -}}

{{/* Rede */}}
{{- else if (or
    (contains "network" (.Labels.alertname | lower))
    (contains "net" (.Labels.alertname | lower))
    (.Labels.interface)
) -}}
  {{- $alertType = "network" -}}

{{- end -}}
```

### 2. **Detecção por Annotations**
```go
{{/* Backup: verificar annotations */}}
{{- if eq $alertType "system" -}}
  {{- if (contains "disk" (.Annotations.description | lower)) -}}
    {{- $alertType = "disk" -}}
  {{- else if (contains "cpu" (.Annotations.description | lower)) -}}
    {{- $alertType = "cpu" -}}
  {{- else if (contains "memory" (.Annotations.description | lower)) -}}
    {{- $alertType = "memory" -}}
  {{- end -}}
{{- end -}}
```

---

## 💎 Extração Avançada de Valores de Métricas

### 1. **Extração Básica (Seu Método Atual)**
```go
{{/* Extrair valor da métrica A */}}
{{- $metricValue := 0.0 -}}
{{- if .Values -}}
  {{- range $k, $v := .Values -}}
    {{- if eq $k "A" -}}{{- $metricValue = $v -}}{{- end -}}
  {{- end -}}
{{- end -}}
```

### 2. **Extração de Múltiplos Valores (Recomendado)**
```go
{{/* Capturar todos os valores disponíveis */}}
{{- $primaryValue := 0.0 -}}
{{- $allValues := dict -}}
{{- if .Values -}}
  {{- range $k, $v := .Values -}}
    {{- $allValues = set $allValues $k $v -}}
    {{/* Assumir que A é o valor principal */}}
    {{- if eq $k "A" -}}{{- $primaryValue = $v -}}{{- end -}}
  {{- end -}}
{{- end -}}

{{/* Usar valor principal ou primeiro disponível */}}
{{- if eq $primaryValue 0.0 -}}
  {{- range $k, $v := $allValues -}}
    {{- $primaryValue = $v -}}
    {{- break -}}
  {{- end -}}
{{- end -}}
```

### 3. **Múltiplas Métricas com Labels**
```go
{{/* Para alertas complexos com múltiplas métricas */}}
metrics:
{{- range $k, $v := .Values }}
  {{ $k }}: {{ printf "%.2f" $v }}
{{- end }}

{{/* Valor formatado do Grafana */}}
{{- if .ValueString }}
formatted_values: {{ .ValueString }}
{{- end }}
```

---

## 🛡️ Estratégias de Fallback e Segurança

### 1. **Fallbacks para Campos Essenciais**
```go
{{/* Identificação segura do servidor */}}
server: {{ .Labels.instance | default (.Labels.host | default "unknown-server") }}

{{/* Nome do serviço/job */}}
service: {{ .Labels.job | default (.Labels.service_name | default "unknown-service") }}

{{/* Container name com múltiplas opções */}}
container: {{ .Labels.container | default (.Labels.container_name | default (.Labels.pod | default .Labels.job)) }}

{{/* Descrição segura */}}
description: {{ .Annotations.description | default (.Annotations.summary | default "No description available") }}
```

### 2. **Validação de Valores Numéricos**
```go
{{/* Formatação segura de valores numéricos */}}
{{- if and (.Values) (gt $metricValue 0.0) -}}
  usage: {{ printf "%.1f" $metricValue }}%
{{- else if .ValueString -}}
  usage: {{ .ValueString }}
{{- else -}}
  usage: N/A
{{- end -}}
```

### 3. **Tratamento de Timestamps**
```go
{{/* Formatação segura de tempo */}}
start_time: {{ .StartsAt | date "2006-01-02 15:04:05 MST" }}
{{- if ne .EndsAt.Unix 0 }}
end_time: {{ .EndsAt | date "2006-01-02 15:04:05 MST" }}
duration: {{ .EndsAt.Sub .StartsAt }}
{{- else }}
duration: {{ time.Now.Sub .StartsAt | humanizeDuration }}
{{- end }}
```

---

## 🔄 Funções Úteis Disponíveis

### Funções de String
```go
{{ title "hello world" }}          {{/* Hello World */}}
{{ toUpper "Hello World" }}        {{/* HELLO WORLD */}}
{{ toLower "Hello World" }}        {{/* hello world */}}
{{ trimSpace " hello " }}          {{/* hello */}}
{{ join "-" (stringSlice "a" "b" "c") }} {{/* a-b-c */}}
```

### Funções de Tempo
```go
{{ .StartsAt | date "15:04:05 MST" }}
{{ .StartsAt | tz "America/Sao_Paulo" | date "15:04:05 MST" }}
{{ since .StartsAt | humanizeDuration }}
```

### Funções de Comparação
```go
{{ if gt $value 90.0 }}CRITICAL{{ else if gt $value 80.0 }}HIGH{{ else }}NORMAL{{ end }}
{{ match ".*cpu.*" .Labels.alertname }}
{{ reReplaceAll "localhost:(.*)" "server:$1" .Labels.instance }}
```

---

## 🚀 Template de Exemplo Melhorado

```go
{{ define "__enhanced_alert_context" }}
{{range .}}
{{/* Auto-detecção de tipo */}}
{{- $alertType := "system" -}}
{{- $primaryValue := 0.0 -}}
{{- $deviceInfo := "" -}}
{{- $containerInfo := "" -}}
{{- $serviceInfo := "" -}}

{{/* Detecção de tipo de alerta */}}
{{- if .Labels.device -}}
  {{- $alertType = "disk" -}}
  {{- $deviceInfo = .Labels.device -}}
{{- else if (or (.Labels.container) (.Labels.container_name) (contains "container" (.Labels.job | lower))) -}}
  {{- $alertType = "container" -}}
  {{- $containerInfo = (.Labels.container | default (.Labels.container_name | default .Labels.job)) -}}
{{- else if (contains "cpu" (.Labels.alertname | lower)) -}}
  {{- $alertType = "cpu" -}}
{{- else if (or (contains "memory" (.Labels.alertname | lower)) (contains "mem" (.Labels.alertname | lower))) -}}
  {{- $alertType = "memory" -}}
{{- end -}}

{{/* Extração de valores */}}
{{- if .Values -}}
  {{- range $k, $v := .Values -}}
    {{- if eq $k "A" -}}{{- $primaryValue = $v -}}{{- end -}}
  {{- end -}}
  {{/* Se não encontrou A, pega o primeiro */}}
  {{- if eq $primaryValue 0.0 -}}
    {{- range $k, $v := .Values -}}
      {{- $primaryValue = $v -}}
      {{- break -}}
    {{- end -}}
  {{- end -}}
{{- end -}}

{{/* Informações do serviço */}}
{{- $serviceInfo = (.Labels.job | default (.Labels.service_name | default "unknown")) -}}

alert_type: {{ $alertType }}
server: {{ .Labels.instance | default "unknown" }}
service: {{ $serviceInfo }}
{{- if ne $deviceInfo "" }}
device: {{ $deviceInfo }}
mountpoint: {{ .Labels.mountpoint | default "/" }}
{{- end }}
{{- if ne $containerInfo "" }}
container: {{ $containerInfo }}
{{- end }}
status: {{ .Status }}
{{- if gt $primaryValue 0.0 }}
value: {{ printf "%.2f" $primaryValue }}
{{- end }}
{{- if .ValueString }}
formatted_value: {{ .ValueString }}
{{- end }}
severity: {{if eq $alertType "container"}}{{if eq .Status "firing"}}container_down{{else}}container_up{{end}}{{else}}{{if ge $primaryValue 90.0}}critical{{else if ge $primaryValue 80.0}}high{{else if ge $primaryValue 70.0}}medium{{else}}low{{end}}{{end}}
start_time: {{ .StartsAt | date "2006-01-02 15:04:05 MST" }}
{{- if ne .EndsAt.Unix 0 }}
end_time: {{ .EndsAt | date "2006-01-02 15:04:05 MST" }}
{{- end }}
description: {{ .Annotations.description | default (.Annotations.summary | default "No description") }}
{{- if .Values }}
all_metrics:
{{- range $k, $v := .Values }}
  {{ $k }}: {{ printf "%.2f" $v }}
{{- end }}
{{- end }}
---
{{end}}
{{ end }}
```

---

## ⚙️ Configurações Avançadas

### 1. **Agrupamento Inteligente**
```go
{{/* Informações de agrupamento */}}
group_by: {{ .GroupLabels.SortedPairs.Values | join ", " }}
common_tags: {{ .CommonLabels.Names | join ", " }}
alert_count: {{ len .Alerts }}
firing_count: {{ len .Alerts.Firing }}
resolved_count: {{ len .Alerts.Resolved }}
```

### 2. **Contexto Adicional**
```go
{{/* Informações extras quando disponíveis */}}
{{- if .Labels.grafana_folder }}
folder: {{ .Labels.grafana_folder }}
{{- end }}
{{- if .Annotations.runbook_url }}
runbook: {{ .Annotations.runbook_url }}
{{- end }}
{{- if .DashboardURL }}
dashboard: {{ .DashboardURL }}
{{- end }}
```

---

## 📋 Checklist de Implementação

### ✅ **Essenciais (Implementar Primeiro)**
- [ ] Detecção robusta de tipo de alerta
- [ ] Extração segura de valores de métricas
- [ ] Fallbacks para campos obrigatórios
- [ ] Formatação consistente de timestamps
- [ ] Tratamento de alertas firing/resolved

### ⚡ **Melhorias (Implementar Depois)**
- [ ] Múltiplos valores de métricas
- [ ] Links para dashboard/painéis
- [ ] Informações de contexto adicional
- [ ] Agrupamento inteligente de alertas
- [ ] Personalização por tipo de serviço

### 🔮 **Avançado (Opcional)**
- [ ] Correlação de alertas relacionados
- [ ] Métricas históricas/tendências
- [ ] Integração com runbooks
- [ ] Ações automatizadas
- [ ] Machine learning para classificação

---

## 📚 Referências

- [Grafana Notification Template Reference](https://grafana.com/docs/grafana/latest/alerting/configure-notifications/template-notifications/reference/)
- [Prometheus Notification Template Reference](https://prometheus.io/docs/alerting/latest/notifications/)
- [Go Template Documentation](https://golang.org/pkg/text/template/)
- [Grafana Alerting Examples](https://grafana.com/docs/grafana/latest/alerting/configure-notifications/template-notifications/examples/)

---

*Documento criado em: 08/10/2025*  
*Versão: 1.0*  
*Autor: Análise baseada na documentação oficial Grafana/Prometheus*