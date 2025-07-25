#!/usr/bin/env python3

"""
Multi-Model Documentation Generator with Controlled Parallel File Processing

Maintains original behavior:
- Sequential model execution: CodeQwen → DeepSeekCoder → DeepSeekR1.
- Per-file stdout tracing.
- Appended output to report files.
- Parallelism introduced only within a single model phase, preserving model order and per-file reporting.

Place this script in the root of your project directory.
"""

import subprocess
from pathlib import Path
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── CONFIG ─────────────────────────────────────────────────────────────
MODELS = {
    "codeqwen": "codeqwen:7b",
    "deepseekcoder": "deepseek-coder-v2:latest",
    "deepseekr1": "deepseek-r1:14b"
}

REPORTS = {
    "codeqwen": "report_codeqwen.md",
    "deepseekcoder": "report_deepseekcoder.md",
    "deepseekr1": "report_deepseekr1.md"
}

SUPPORTED_EXTENSIONS = {
    '.abap', '.asm', '.bash', '.bat', '.bib', '.c', '.clj', '.cljc', '.cljs', '.cmake', '.coffee', '.cpp', '.cs',
    '.csharp', '.css', '.csv', '.cuda', '.dart', '.d', '.dockerfile', '.el', '.elm', '.erb', '.erl', '.ex', '.exs',
    '.f', '.f77', '.f90', '.fish', '.for', '.forth', '.fs', '.fsharp', '.go', '.graphql', '.groovy', '.h', '.haml',
    '.handlebars', '.hs', '.html', '.ini', '.ipynb', '.java', '.jl', '.js', '.json', '.jsx', '.kt', '.kts', '.lisp',
    '.lua', '.lsp', '.m', '.make', '.matlab', '.md', '.ml', '.nim', '.nix', '.php', '.pl', '.prisma', '.prolog',
    '.ps1', '.py', '.r', '.raku', '.rb', '.re', '.rescript', '.rs', '.sass', '.scala', '.scss', '.sh', '.sql',
    '.svelte', '.swift', '.tcl', '.tex', '.toml', '.ts', '.tsx', '.vb', '.vim', '.vue', '.xml', '.yaml', '.yml', '.zsh'
}

VALID_FILENAMES = {
    'Dockerfile', 'Makefile', '.gitignore', '.dockerignore', 'CMakeLists.txt',
    'build.gradle', 'settings.gradle', 'package.json', 'tsconfig.json', 'requirements.txt',
    'Pipfile', 'pyproject.toml', 'Cargo.toml', 'Gemfile', 'go.mod', 'go.sum',
    'environment.yml', 'Procfile'
}

# ─── DISCOVERY ───────────────────────────────────────────────────────────
def collect_source_files(root: Path) -> List[Path]:
    return [
        f.resolve()
        for f in root.rglob("*")
        if f.is_file() and (f.name in VALID_FILENAMES or f.suffix.lower() in SUPPORTED_EXTENSIONS)
    ]

# ─── MODEL EXECUTION ─────────────────────────────────────────────────────
def run_model_on_file(model: str, file_path: Path, report_path: Path, log_path: Path, root_dir: Path) -> None:
    rel_path = file_path.relative_to(root_dir)
    print(f"[{model}] Processing file: {rel_path}")

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not content:
            log_path.write_text(f"[{model}] [SKIP_EMPTY] {rel_path}\n", append=True)
            return

        ext = file_path.suffix.lower()[1:] if file_path.suffix else ""
        prompt = (
            f"Document the following source file thoroughly, including explanations of functions, classes, and overall purpose.\n\n"
            f"### File: {rel_path}\n"
            f"```{ext}\n{content}\n```\n"
        )

        proc = subprocess.run(
            ["ollama", "run", MODELS[model]],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )

        output = proc.stdout.decode("utf-8").strip()
        if output:
            with report_path.open("a", encoding="utf-8") as r:
                r.write(f"\n---\n\n# Documentation for file: {rel_path}\n\n{output}\n")
            with log_path.open("a", encoding="utf-8") as l:
                l.write(f"[{model}] [OK] {rel_path}\n")
        else:
            with log_path.open("a", encoding="utf-8") as l:
                l.write(f"[{model}] [EMPTY_OUTPUT] {rel_path}\n")

    except subprocess.CalledProcessError as e:
        with log_path.open("a", encoding="utf-8") as l:
            l.write(f"[{model}] [ERROR] {rel_path} | {e.stderr.decode('utf-8')}\n")
    except Exception as e:
        with log_path.open("a", encoding="utf-8") as l:
            l.write(f"[{model}] [EXCEPTION] {rel_path} | {e}\n")

# ─── PARALLEL EXECUTION ─────────────────────────────────────────────────
def run_model_batch_parallel(model: str, files: List[Path], report_path: Path, log_path: Path, root_dir: Path, max_workers: int = 6):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for file_path in files:
            executor.submit(run_model_on_file, model, file_path, report_path, log_path, root_dir)

# ─── FINAL MERGE ─────────────────────────────────────────────────────────
def merge_reports(root_dir: Path, debug_log_path: Path):
    codeqwen_data = (root_dir / REPORTS["codeqwen"]).read_text(encoding="utf-8", errors="ignore")
    deepseek_data = (root_dir / REPORTS["deepseekcoder"]).read_text(encoding="utf-8", errors="ignore")

    merge_prompt = f"""
# Report From CodeQwen
{codeqwen_data}

# Report From DeepSeekCoder
{deepseek_data}

# Instructions
Merge these two reports into a single, styled, human-readable, comprehensive technical documentation.
Use section headers, themed blocks, color-coded markdown tips if supported.
Eliminate duplicates, resolve inconsistencies. Format using modern Markdown.
"""

    try:
        proc = subprocess.run(
            ["ollama", "run", MODELS["deepseekr1"]],
            input=merge_prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        output = proc.stdout.decode("utf-8")
        (root_dir / REPORTS["deepseekr1"]).write_text(output, encoding="utf-8")
        debug_log_path.write_text("[DeepSeekR1] Merge complete\n")
    except subprocess.CalledProcessError as e:
        debug_log_path.write_text(f"[DeepSeekR1] Merge failed: {e.stderr.decode('utf-8')}\n")
        raise RuntimeError("Merge failed")

# ─── ENTRY ───────────────────────────────────────────────────────────────
def main():
    root_dir = Path.cwd()
    files = collect_source_files(root_dir)
    print(f"[INFO] Discovered {len(files)} source files to document.")

    # Reset output files
    for key in REPORTS:
        (root_dir / REPORTS[key]).write_text("", encoding="utf-8")
        (root_dir / f"debug_{key}.log").write_text("", encoding="utf-8")

    # CodeQwen Phase (parallel)
    run_model_batch_parallel(
        model="codeqwen",
        files=files,
        report_path=root_dir / REPORTS["codeqwen"],
        log_path=root_dir / "debug_codeqwen.log",
        root_dir=root_dir,
        max_workers=6
    )

    # DeepSeekCoder Phase (parallel)
    run_model_batch_parallel(
        model="deepseekcoder",
        files=files,
        report_path=root_dir / REPORTS["deepseekcoder"],
        log_path=root_dir / "debug_deepseekcoder.log",
        root_dir=root_dir,
        max_workers=6
    )

    # Merge Phase
    merge_reports(root_dir, root_dir / "debug_deepseekr1.log")
    print(f"[INFO] Final documentation written to {REPORTS['deepseekr1']}")

if __name__ == "__main__":
    main()
