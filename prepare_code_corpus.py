import os
import json
from pathlib import Path

PROJECT_ROOT = Path.cwd()
OUTPUT_FILE = "finetune_data.jsonl"
EXCLUDE_DIRS = {'.git', '__pycache__', '.chroma-index', 'node_modules', '.venv'}

def should_process(path: Path) -> bool:
    # Exclude directories in the path
    if any(part in EXCLUDE_DIRS for part in path.parts):
        print(f"[-] Excluded directory: {path}")
        return False
    if not path.is_file():
        return False
    # Binary detection disabled to maximize inclusion
    # print(f"[+] Including file (no binary check): {path}")
    return True

def read_file_with_fallback(path: Path) -> str:
    encodings = ['utf-8', 'latin1', 'utf-16']
    for enc in encodings:
        try:
            with open(path, 'r', encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    raise UnicodeDecodeError(f"Failed to decode {path} with encodings {encodings}")

def sanitize_content(text: str) -> str:
    return text.replace('\r\n', '\n').strip()

def main():
    total_files = 0
    skipped_files = 0

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_file:
        for path in PROJECT_ROOT.rglob('*'):
            if should_process(path):
                try:
                    content = read_file_with_fallback(path)
                    content = sanitize_content(content)
                    record = {
                        "input": f"file: {path.relative_to(PROJECT_ROOT)}",
                        "output": content
                    }
                    out_file.write(json.dumps(record) + "\n")
                    total_files += 1
                    print(f"[+] Processed ({total_files}): {path.relative_to(PROJECT_ROOT)}")
                except Exception as e:
                    skipped_files += 1
                    print(f"[!] Skipped ({skipped_files}) {path.relative_to(PROJECT_ROOT)} due to read error: {e}")
            else:
                # Already logged excluded directories in should_process()
                pass

    print(f"[✔] Export complete: {total_files} files written to {OUTPUT_FILE}")
    if skipped_files > 0:
        print(f"[!] Skipped {skipped_files} files due to errors")

if __name__ == "__main__":
    main()
