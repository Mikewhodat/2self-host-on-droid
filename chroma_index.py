#!/usr/bin/env python3

import os
import sys
import re
import json
import traceback
from pathlib import Path
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from chromadb.api.types import EmbeddingFunction
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

ROOT = Path.cwd()
SRC_DIR = ROOT
EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
CHROMA_DIR = ROOT / ".chroma-index"
COLLECTION_NAME = "codebase"

class SentenceTransformerEmbedding(EmbeddingFunction):
    def __init__(self, model):
        self.model = model

    def __call__(self, texts):
        return self.model.encode(texts, show_progress_bar=False).tolist()

    def name(self) -> str:
        return "sentence-transformers"

embedding_fn = SentenceTransformerEmbedding(EMBED_MODEL)

client = PersistentClient(path=str(CHROMA_DIR))
collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_fn,
)

def get_code_files(base_path: Path):
    exts = {".py", ".js", ".ts", ".html", ".css", ".java", ".json", ".md"}
    for file_path in base_path.rglob("*"):
        if file_path.is_file() and file_path.suffix in exts:
            yield file_path

def clean_code(content: str) -> str:
    return re.sub(r"\s+", " ", content).strip()

def index_files():
    files = list(get_code_files(SRC_DIR))
    print(f"[INFO] Indexing {len(files)} files...")

    for i, file_path in enumerate(tqdm(files)):
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            content = clean_code(content)
            doc_id = f"{file_path.relative_to(SRC_DIR)}"
            collection.upsert(
                documents=[content],
                ids=[doc_id],
                metadatas=[{"path": str(file_path)}]
            )
        except Exception as e:
            print(f"[ERROR] Failed to index {file_path}: {e}")

def query_context(query: str, k=5) -> list:
    try:
        results = collection.query(query_texts=[query], n_results=k)
        return [doc for doc in results.get("documents", [[]])[0]]
    except Exception as e:
        print(f"[ERROR] Query failed: {e}")
        return []

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "query":
        query_str = input("🔍 Enter your query: ").strip()
        hits = query_context(query_str)
        for i, doc in enumerate(hits):
            print(f"\n--- Match {i+1} ---\n{doc}\n")
    else:
        index_files()
