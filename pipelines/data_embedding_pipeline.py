import os
import json
import glob
from typing import List, Dict, Any
from tqdm import tqdm
import uuid
from mistralai import Mistral
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance, CreateCollection

# === CONFIG ===
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
mistral_client = Mistral(api_key=MISTRAL_API_KEY)
qdrant = QdrantClient(url="http://185.209.49.210")
COLLECTION_NAME = "tds-embeddings"


if COLLECTION_NAME not in [c.name for c in qdrant.get_collections().collections]:
    qdrant.create_collection(
        COLLECTION_NAME,
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
    )


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks


def embed_text(texts: List[str]) -> List[List[float]]:
    response = mistral_client.embeddings.create(
        model="mistral-embed",
        inputs=texts
    )
    return [item.embedding for item in response.data]


def process_discourse(json_path: str) -> List[Dict[str, Any]]:
    with open(json_path, "r", encoding="utf-8") as f:
        posts = json.load(f)

    chunks = []
    for post in posts:
        topic_id = post["topic_id"]
        post_id = post["post_id"]
        text_chunks = chunk_text(post["content"].strip())
        for idx, chunk in enumerate(text_chunks):
            chunks.append({
                "id": f"discourse_{post_id}_{idx}",
                "text": chunk,
                "metadata": {
                    "source": "discourse",
                    "topic_id": topic_id,
                    "post_id": post_id,
                    "chunk_index": idx,
                    "url": post.get("url")
                }
            })
    return chunks


def process_markdown(md_dir: str) -> List[Dict[str, Any]]:
    chunks = []
    md_files = glob.glob(os.path.join(md_dir, "**/*.md"), recursive=True)
    for path in md_files:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        text_chunks = chunk_text(text)
        for idx, chunk in enumerate(text_chunks):
            chunks.append({
                "id": f"md_{os.path.basename(path)}_{idx}",
                "text": chunk,
                "metadata": {
                    "source": "course_material",
                    "filename": os.path.basename(path),
                    "path": path,
                    "chunk_index": idx
                }
            })
    return chunks


def embed_and_store(chunks: List[Dict[str, Any]], batch_size: int = 100):
    for i in tqdm(range(0, len(chunks), batch_size)):
        batch = chunks[i:i + batch_size]
        texts = [x["text"] for x in batch]
        embeddings = embed_text(texts)
        points = []
        for j, chunk in enumerate(batch):
            points.append(PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["id"])),
                vector=embeddings[j],
                payload={**chunk["metadata"], "text": chunk["text"]}
            ))
        qdrant.upsert(collection_name=COLLECTION_NAME, points=points)


if __name__ == "__main__":
    discourse_chunks = process_discourse("../data/tds_discourse_posts.json")
    markdown_chunks = process_markdown("../data/course_material")
    all_chunks = discourse_chunks + markdown_chunks
    print(f"Total Chunks: {len(all_chunks)}")
    embed_and_store(all_chunks)
    print("Embedding and Qdrant storage complete.")


# RESULTS POST PROCESSING:
# Total Chunks: 994
# 100%|███████████████████████████████████████████████████████████████████████████████| 10/10 [01:08<00:00,  6.84s/it]
# Embedding and Qdrant storage complete.