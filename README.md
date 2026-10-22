# Cyberloop RAG Service

Servizio RAG da integrare nell'infrastruttura Cyberloop. Tramite API, viene chiamato un Retrieve Agent che recupera contesto utile partendo dall'alert in input, 
servendosi del RAG (Retrieve Augmented Generation). Il resto dell'infrastruttura (Triage, Action Planning, Contenimento) non è incluso nella seguente repo.

- [Setup](#setup)
- [Download datasets](#download-datasets)
- [Avvio container](#avvio-container)
- [Popolare DB con datasets - in un altro Terminale](#popolare-db-con-datasets---in-un-altro-terminale)
- [Indicizzare knowledge base](#indicizzare-knowledge-base)
- [Invio alert e recupero del contesto](#invio-alert-e-recupero-del-contesto)
  - [Powershell](#powershell)
  - [Bash](#bash)
- [Workflow schema](#workflow-schema)

## Setup
```powershell
git clone https://github.com/floyddc/Cyberloop-RAG-Service.git  # oppure download della release
cd <REPOSITORY>
chmod +x *
echo "<HF_TOKEN>" > .env # sostituire con token HuggingFace, nel formato HF_TOKEN=xxxxxxxxxxxxx
pip install -r python/requirements.txt
```
- Sostituisci `HF_TOKEN` .

## Download datasets
```powershell
./fetch_datasets.sh
```

## Avvio container
```powershell
docker compose build
docker compose up
```
- Attendere che il servizio si avvii (`Application startup complete`) e restituisca `"GET /health HTTP/1.1" 200 OK`.

## Popolare DB con datasets - in un altro Terminale
```powershell
./seed_DB.sh
```
- Prima di avviarsi, dovrebbe restituire `PostgreSQL online`.

## Indicizzare knowledge base
```powershell
./build_index.sh
```

## Invio alert e recupero del contesto
- Modificare questi comandi per salvare il contesto recuperato e passarlo eventualmente ad altri agenti.

### Powershell
```powershell
$alert = Get-Content <ALERT_PATH> -Raw | ConvertFrom-Json
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
file=<ALERT_PATH>

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

## Workflow schema
```mermaid
flowchart TD
    Agent["Cyberloop Agent"] -->|"POST /retrieve<br/>customer, query, k_cases, k_kb"| API["Servizio HTTP<br/>FastAPI"]
    Agent -->|"GET /health"| Ready{"Embedding Model e <br/>Cross-Encoder Reranker caricati?"}
    
    Ready -->|"No"| HealthWait["503 Service Unavailable"]
    Ready -->|"Sì"| HealthOK["200 OK"]
    HealthOK --> |"Procedi"|Agent

    

    API --> Validate["Validazione alert/query"]
    Validate --> Embed["Creazione embedding<br/>(Embedding Model)"]
    Embed --> CaseSearch["Ricerca case storici<br/>in ChromaDB"]
    Embed --> KBSearch["Ricerca knowledge base<br/>in ChromaDB"]

    CaseSearch --> CaseFilter["Filtro obbligatorio:<br/>category = incident_history<br/>e customer = customer richiesto"]
    KBSearch --> KBFilter["Filtro docs condivisi"]

    CaseFilter --> CaseRerank["Reranking dei case pertinenti<br/>(Cross-Encoder Reranker)"]
    KBFilter --> KBRerank["Reranking dei docs pertinenti<br/>(Cross-Encoder Reranker)"]

    CaseRerank --> CaseLimit["Deduplicazione e <br/> k_cases come limite max"]
    KBRerank --> KBLimit["Deduplicazione e <br/> k_kb come limite max"]

    CaseLimit --> Merge["Unione dei risultati"]
    KBLimit --> Merge
    Merge --> Response["Contesto recuperato (cases/docs):<br/>type, id, title, text, score"]
    Response --> Agent

    subgraph Indexing["Gestione dei case storici"]
        Client["Analyst"] -->|"POST /index/cases"| Upsert["INSERT/UPDATE cases"]
        Upsert --> DB["PostgreSQL<br/>incident_history"]
        Upsert --> Chunks["Creazione chunk<br/>e embedding"]
        Chunks --> ChromaDB["ChromaDB<br/>indice vettoriale"]
        Client -->|"DELETE /index/cases/{id}"| Delete["DELETE case"]
        Delete --> DB
        Delete --> ChromaDB
    end

    CaseSearch -.-> ChromaDB
    KBSearch -.-> ChromaDB
```