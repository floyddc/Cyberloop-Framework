# Cyberloop RAG Service

Servizio RAG da integrare nell'infrastruttura Cyberloop. Tramite API, viene chiamato un Retrieve Agent che recupera contesto utile partendo dall'alert in input, 
servendosi del RAG (Retrieve Augmented Generation). Il resto dell'infrastruttura (Triage, Action Planning, Contenimento) non è incluso nella seguente repo.

## Download datasets
```powershell
./fetch_datasets.sh
```

## Popolamento DB con datasets
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
$alert = Get-Content .\knowledge\raw_data\edr_alerts\test_alert3.json -Raw | ConvertFrom-Json
$query = "$($alert.alert). $($alert.message). $($alert.command_line)"

@{ customer = 1; query = $query; k_cases = 3; k_kb = 3 } |
  ConvertTo-Json -Compress |
  curl.exe -sS -X POST http://localhost:8000/retrieve `
    -H "Content-Type: application/json" --data-binary "@-"
```

### Bash
```bash
query=$(jq -r '"\(.alert). \(.message). \(.command_line)"' \
  knowledge/raw_data/edr_alerts/test_alert3.json)

jq -n \
  --arg query "$query" \
  '{customer: 1, query: $query, k_cases: 3, k_kb: 3}' |
  curl -sS -X POST http://localhost:8000/retrieve \
    -H "Content-Type: application/json" \
    --data-binary @-
```

## Invio alert (stampa solo contesto)

### Powershell
```powershell
$alert = Get-Content .\knowledge\raw_data\edr_alerts\test_alert4.json -Raw | ConvertFrom-Json
$query = "$($alert.alert). $($alert.message). $($alert.command_line)"

$body = @{ customer = 1; query = $query; k_cases = 0; k_kb = 3 } |
  ConvertTo-Json -Compress

$response = $body |
  curl.exe -sS -X POST http://localhost:8000/retrieve `
    -H "Content-Type: application/json" --data-binary "@-"

$results = $response | ConvertFrom-Json
$context = ($results | ForEach-Object { $_.text }) -join "`n`n"

$context
```

### Bash
```bash
query=$(jq -r '"\(.alert). \(.message). \(.command_line)"' \
  knowledge/raw_data/edr_alerts/test_alert4.json)

context=$(
  jq -n \
    --arg query "$query" \
    '{customer: 1, query: $query, k_cases: 0, k_kb: 3}' |
  curl -sS -X POST http://localhost:8000/retrieve \
    -H "Content-Type: application/json" \
    --data-binary @- |
  jq -r 'map(.text) | join("\n\n")'
)

printf '%s\n' "$context"
```