from typing import List
import config
from .embeddings import embed_texts

_BATCH_SIZE = 128

def _client():
    import chromadb

    return chromadb.PersistentClient(path=config.INDICES_DIR)

def get_collection():
    return _client().get_or_create_collection(
        name=config.COLLECTION_NAME
    )

def reset_collection():
    import chromadb

    client = _client()

    try:
        client.delete_collection(config.COLLECTION_NAME)
    except chromadb.errors.NotFoundError:
        pass

    return client.get_or_create_collection(
        name=config.COLLECTION_NAME
    )

def index_records(records: List[dict], reset: bool = False) -> int:

    collection = reset_collection() if reset else get_collection()

    if not records:
        return 0

    from tqdm import tqdm

    total = 0

    with tqdm(
        total=len(records),
        desc="Indexing knowledge base",
        unit="chunk",
    ) as progress:

        for i in range(0, len(records), _BATCH_SIZE):

            batch = records[i:i + _BATCH_SIZE]
            ids = [record["id"] for record in batch]
            existing_ids = set(collection.get(ids=ids, include=["metadatas"])["ids"])
            new_records = [record for record in batch if record["id"] not in existing_ids]
            if not new_records:
                progress.update(len(batch))
                continue

            new_ids = [record["id"] for record in new_records]
            texts = [record["text"] for record in new_records]
            metadatas = [record["metadata"] for record in new_records]
            embeddings = embed_texts(texts)
            collection.upsert(
                ids=new_ids,
                documents=texts,
                metadatas=metadatas,
                embeddings=embeddings,
            )

            total += len(new_records)
            progress.update(len(batch))

    return total
