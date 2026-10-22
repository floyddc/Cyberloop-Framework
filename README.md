# Cyberloop RAG Service

Servizio RAG da integrare nell'infrastruttura Cyberloop. Tramite API, viene chiamato un Retrieve Agent che recupera contesto utile partendo dall'alert in input, 
servendosi del RAG (Retrieve Augmented Generation). Il resto dell'infrastruttura (Triage, Action Planning, Contenimento) non è incluso nella seguente repo.

- [Download datasets](#download-datasets)
- [Popolare DB con datasets](#popolare-db-con-datasets)
- [Indicizzare knowledge base](#indicizzare-knowledge-base)
- [Invio alert](#invio-alert)
  - [Powershell](#powershell)
  - [Bash](#bash)
- [Invio alert (stampa solo contesto)](#invio-alert-stampa-solo-contesto)
  - [Powershell](#powershell-1)
  - [Bash](#bash-1)

## Download datasets
```powershell
./fetch_datasets.sh
```

## Popolare DB con datasets
```powershell
./seed_DB.sh
```

## Indicizzare knowledge base
```powershell
./build_index.sh
```

## Invio alert

### Powershell
```powershell
$alert = Get-Content .\knowledge\raw_data\edr_alerts\test_alert4.json -Raw | ConvertFrom-Json
$body = @{
  customer = $alert.alert_customer_id
  alert = $alert
  k_cases = 0
  k_kb = 10
} | ConvertTo-Json -Depth 20 -Compress

$body | curl.exe -sS -X POST http://localhost:8000/retrieve `
  -H "Content-Type: application/json" --data-binary "@-"
```

### Bash
```bash
file=knowledge/raw_data/edr_alerts/test_alert4.json

jq -n \
  --slurpfile alert "$file" \
  '{customer: $alert[0].alert_customer_id, alert: $alert[0], k_cases: 0, k_kb: 10}' |
  curl -sS -X POST http://localhost:8000/retrieve \
    -H "Content-Type: application/json" \
    --data-binary @-
```

## Invio alert (stampa solo contesto)

### Powershell
```powershell
$alert = Get-Content .\knowledge\raw_data\edr_alerts\test_alert4.json -Raw | ConvertFrom-Json
$body = @{
  customer = $alert.alert_customer_id
  alert = $alert
  k_cases = 0
  k_kb = 10
} | ConvertTo-Json -Depth 20 -Compress

$response = $body |
  curl.exe -sS -X POST http://localhost:8000/retrieve `
    -H "Content-Type: application/json" --data-binary "@-"

$results = $response | ConvertFrom-Json
$context = ($results | ForEach-Object { $_.text }) -join "`n`n"

$context
```

### Bash
```bash
file=knowledge/raw_data/edr_alerts/test_alert4.json

context=$(
  jq -n \
    --slurpfile alert "$file" \
    '{customer: $alert[0].alert_customer_id, alert: $alert[0], k_cases: 0, k_kb: 10}' |
  curl -sS -X POST http://localhost:8000/retrieve \
    -H "Content-Type: application/json" \
    --data-binary @- |
  jq -r 'map(.text) | join("\n\n")'
)

printf '%s\n' "$context"
```