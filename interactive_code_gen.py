#!/usr/bin/env python3

import os
import re
import sys
import json
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from chromadb import PersistentClient
from chromadb.api.types import EmbeddingFunction
from sentence_transformers import SentenceTransformer

ROOT = Path.cwd()
OUT_DIR = ROOT / "ai_gen_output"
OUT_DIR.mkdir(exist_ok=True)
CHROMA_DIR = ROOT / ".chroma-index"
COLLECTION_NAME = "codebase"
EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")

class SentenceTransformerEmbedding(EmbeddingFunction):
    def __init__(self, model):
        self.model = model

    def __call__(self, texts):
        return self.model.encode(texts, show_progress_bar=False).tolist()

    def name(self):
        return "sentence-transformers"

embedding_fn = SentenceTransformerEmbedding(EMBED_MODEL)

client = PersistentClient(path=str(CHROMA_DIR))
collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_fn
)

MODELS = {
    "planner_1": "deepseek-coder-v2:latest",
    "planner_2": "codeqwen:7b",
    "completer": "starcoder:15b",
    "foreman": "deepseek-r1:14b"
}

DOC_PATHS = {
    "codeqwen": ROOT / "report_codeqwen.md",
    "deepseekcoder": ROOT / "report_deepseekcoder.md",
    "deepseekr1": ROOT / "report_deepseekr1.md"
}

MD_OUTPUT = OUT_DIR / "ai_code_output.md"
MD_OUTPUT.touch(exist_ok=True)

def run_model(model: str, prompt: str) -> str:
    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return result.stdout.decode("utf-8").strip()
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {model} failed: {e.stderr.decode()}")
        return ""
    except Exception as e:
        print(f"[EXCEPTION] {model}: {e}")
        return ""

def extract_code_block(text: str) -> str:
    match = re.search(r"```(?:html|python|js|javascript|css|java)?\n(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()

def append_to_md_file(content: str, user_input: str) -> Path:
    """
    Append generated code into a markdown file with fenced code blocks
    and language inferred from user input. Also include timestamp and user prompt.
    """
    lang = "plaintext"
    if re.search(r"\bhtml?\b", user_input, re.IGNORECASE):
        lang = "html"
    elif re.search(r"\bcss\b", user_input, re.IGNORECASE):
        lang = "css"
    elif re.search(r"\bjs\b", user_input, re.IGNORECASE):
        lang = "javascript"
    elif re.search(r"\bjava\b", user_input, re.IGNORECASE):
        lang = "java"
    elif re.search(r"\bpython\b", user_input, re.IGNORECASE):
        lang = "python"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"\n\n---\n\n### Generated on {timestamp}\n\n**User request:** `{user_input}`\n\n"
    block = f"```{lang}\n{content}\n```\n"

    with open(MD_OUTPUT, "a", encoding="utf-8") as f:
        f.write(header)
        f.write(block)

    print(f"[SAVED] Appended output to Markdown file: {MD_OUTPUT}")
    return MD_OUTPUT

def load_docs() -> str:
    merged = ""
    for label, path in DOC_PATHS.items():
        if path.exists():
            merged += f"\n\n---\n# Documentation from {label.upper()}\n\n"
            merged += path.read_text(encoding="utf-8", errors="ignore")
    return merged

def load_src_theme(base: Path) -> str:
    context = ""
    for file in base.rglob("src/**/*.html"):
        try:
            content = file.read_text(encoding="utf-8", errors="ignore").strip()
            if content:
                rel_path = file.relative_to(base)
                context += f"\n\n---\n# FILE: {rel_path}\n```html\n{content}\n```\n"
        except Exception:
            continue
    for file in base.rglob("src/**/*.css"):
        try:
            content = file.read_text(encoding="utf-8", errors="ignore").strip()
            if content:
                rel_path = file.relative_to(base)
                context += f"\n\n---\n# FILE: {rel_path}\n```css\n{content}\n```\n"
        except Exception:
            continue
    return context

def query_chroma(user_query: str, directory_hint: str = "", top_k: int = 7) -> str:
    try:
        combined_query = f"{user_query} {directory_hint}".strip()
        results = collection.query(query_texts=[combined_query], n_results=top_k)
        docs = results.get("documents", [[]])[0]
        return "\n\n---\n".join(docs)
    except Exception as e:
        print(f"[ERROR] Chroma query failed: {e}")
        return ""

def build_context_prompt(user_input: str, chroma: str, themes: str) -> str:
    return f"""
# CODEBASE CONTEXT (STRICT USAGE REQUIRED)
{chroma}

# HTML/CSS THEME
{themes}

# USER REQUEST
"{user_input}"

## TASK:
- Use only code patterns and logic strictly derived from the above context.
- DO NOT invent or hallucinate code beyond what is represented in the indexed database.
- Adapt and assemble logic from matched files.
- Adhere to naming, style, and structure in the existing codebase.
"""

def orchestrate_session():
    print("[AI ORCHESTRATOR] Interactive session started.")
    html_themes = load_src_theme(ROOT)
    static_docs = load_docs()

    while True:
        try:
            user_input = input("🧠 request> ").strip()
            if user_input.lower() in {"exit", "quit"}:
                break
            if not user_input:
                continue

            dir_hint = ""
            # Optionally refine directory hinting for Chroma query
            lowered = user_input.lower()
            if "ai-weather" in lowered:
                dir_hint = "ai-weather"
            elif "blog" in lowered:
                dir_hint = "blog"
            elif "portfolio" in lowered:
                dir_hint = "portfolio"

            chroma_context = query_chroma(user_input, directory_hint=dir_hint)
            full_context = static_docs + "\n\n" + html_themes + "\n\n---\n# RELEVANT CHROMA CODE\n" + chroma_context
            planner_prompt = build_context_prompt(user_input, chroma_context, html_themes)

            print("[PLANNER] Sending to planner...")
            plan = run_model(MODELS["planner_1"], planner_prompt) or run_model(MODELS["planner_2"], planner_prompt)
            if not plan:
                print("[PLANNER] Failed.")
                continue

            extracted = extract_code_block(plan)
            print("[COMPLETER] Sending to completer...")
            result = run_model(MODELS["completer"], extracted)
            if not result:
                print("[COMPLETER] Failed.")
                continue

            print("[FOREMAN] Running review...")
            # If foreman review is desired, it can be reintegrated here.
            final_code = result

            append_to_md_file(final_code, user_input)

        except KeyboardInterrupt:
            print("\n[AI ORCHESTRATOR] Session terminated by user.")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            traceback.print_exc()

if __name__ == "__main__":
    orchestrate_session()
