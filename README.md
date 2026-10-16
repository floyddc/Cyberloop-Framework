# Cyberloop RAG e triage

Il repository fornisce componenti Python riutilizzabili da integrare nel processo
Agentic Triage esistente. Non avvia un server o un orchestratore: il chiamante
passa direttamente l'alert alle funzioni di retrieval e triage, e la propria
infrastruttura decide come gestire i case attivi, pianificazione, validazione e
risposta.

## Requisiti

- Python 3.12+
- Ollama raggiungibile dall'applicazione, con `qwen2.5:7b` disponibile per il
  triage
- PostgreSQL per documenti e storico incidenti
- Accesso in scrittura alla directory `knowledge/indices/` per l'indice Chroma

Configurare `python/` nel `PYTHONPATH` dell'applicazione insieme alla root del
repository. Installare le dipendenze con:

```powershell
python -m pip install -r python/requirements.txt
```

Per usare il PostgreSQL locale incluso:

```powershell
docker compose up -d postgres rag-service
```

Il servizio HTTP RAG e' raggiungibile localmente su `http://localhost:8000`.
Durante l'avvio carica embedding e reranker; `GET /health` risponde `200`
solo al termine del caricamento e `503` prima che i modelli siano pronti.
L'indice Chroma e la cache dei modelli sono persistenti nei volumi Docker.

`POST /retrieve` riceve un customer numerico, la query e i limiti separati:

```json
{
  "customer": 123,
  "query": "suspicious PowerShell execution",
  "k_cases": 3,
  "k_kb": 5
}
```

Risponde con una lista di risultati `{type, id, title, text, score}`.
I case storici sono sempre filtrati per customer; la knowledge base e'
condivisa. `POST /index/cases` accetta un batch di case con `customer`,
`title` e `text`; `id` e' facoltativo in creazione e va fornito per aggiornare
un case esistente:

La route `/retrieve` delega al `RetrieveAgent`, che usa il retriever RAG per
generare l'embedding, cercare separatamente case e knowledge base in Chroma e
riordinare i risultati con il reranker.

```json
{
  "cases": [
    {
      "id": 42,
      "customer": 123,
      "title": "Suspicious PowerShell execution",
      "text": "Encoded command observed; endpoint isolated."
    }
  ]
}
```

Senza `id`, il servizio assegna e restituisce un ID numerico. Eliminare un
case con `DELETE /index/cases/{id}`. Le operazioni di indicizzazione aggiornano
sia `incident_history` in PostgreSQL sia i chunk corrispondenti in Chroma.

I parametri sono configurabili tramite `POSTGRES_HOST`, `POSTGRES_PORT`,
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_KNOWLEDGE_DB`, `OLLAMA_HOST`,
`TRIAGE_MODEL`, `EMBEDDING_MODEL`, `RERANKER_MODEL`, `KNOWLEDGE_DIR` e
`CACHE_DIR`. I valori predefiniti del triage sono `http://localhost:11434` e
`qwen2.5:7b`.

## Costruire la knowledge base

1. Inserire i documenti condivisi in `knowledge/base/`, `knowledge/policies/`
   o `knowledge/actions_catalog/`.
2. Inserire/aggiornare i documenti sorgente in PostgreSQL:

   ```powershell
   $env:PYTHONPATH = "python"
   python -m postgres.seed_knowledge_base
   ```

3. Costruire l'indice vettoriale:

   ```powershell
   python -m RAG.build_index
   ```

## Integrazione nel processo aziendale

`RAG.retrieve_context(alert)` riceve un alert JSON e restituisce direttamente
il contesto già formattato per il prompt. Il campo `customer` è obbligatorio e
deve essere una stringa non vuota:

```python
from RAG import retrieve_context

alert = {
    "customer": "cliente-123",
    "host": "workstation-042",
    "alert": "Suspicious PowerShell execution",
    "command_line": "powershell.exe -EncodedCommand ...",
}

context = retrieve_context(alert)
```

Il retrieval usa la knowledge base tecnica condivisa e, separatamente, cerca
case storici solo con il filtro esatto `customer`. L'assenza di `customer`
produce un `ValueError`: non viene eseguito un retrieval non filtrato.
La stessa funzione può essere invocata dal chiamante durante l'analisi dei
case attivi, passando i relativi campi JSON; merge o creazione restano una
decisione dell'orchestratore aziendale.

Il triage può ricevere il contesto prodotto dal chiamante oppure recuperarlo
direttamente dall'alert quando `context` non viene specificato:

```python
from MAPE.triage_agent import TriageAgent

triage_agent = TriageAgent()
triage = triage_agent.triage(alert, context=context)
# Oppure: triage = triage_agent.triage(alert)
```

Il cliente, la sorgente e l'identificativo esterno sono usati come metadati,
non inseriti nel testo dell'alert inviato al modello. L'agente restituisce
solo il risultato di classificazione (`summary`, `description`, `category`,
`severity`); non persiste incidenti e non esegue azioni.

## Case storici e isolamento cliente

Ogni record in `incident_history` deve avere `metadata.customer`. Usare lo
store fornito per salvare un case concluso:

```python
from RAG.knowledge_store import IncidentHistoryStore

IncidentHistoryStore().add(
    incident_id=123,
    source="EDR",
    summary="Suspicious PowerShell execution",
    description="Encoded command observed on endpoint",
    resolution="Endpoint isolated",
    metadata={"customer": "cliente-123"},
)
```

Le colonne `metadata` e la tabella dei cursori vengono predisposte dallo script
`postgres/init/002_knowledge_db.sql`. Per un database già inizializzato,
applicare una volta entrambe le migrazioni:

```powershell
Get-Content postgres/migrations/001_incident_history_customer_metadata.sql |
  docker compose exec -T postgres psql -U cyberresponse -d knowledge
Get-Content postgres/migrations/002_index_cursors.sql |
  docker compose exec -T postgres psql -U cyberresponse -d knowledge
```

Il cursore PostgreSQL tiene traccia dell'ultimo ID elaborato per entrambe le
tabelle; ogni esecuzione legge solo le righe inserite dopo quel cursore. Chroma
verifica inoltre gli ID dei chunk e calcola embeddings/upsert solo per quelli
assenti. I nuovi documenti e case vengono quindi aggiunti senza ricalcolare
quelli già indicizzati. Le modifiche a righe esistenti non sono considerate
nuovi inserimenti e richiedono una reindicizzazione esplicita.

Per indicizzare nuovi documenti/case:

```powershell
python -m RAG.build_index
```
