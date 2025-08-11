import os
import sys
import re
import requests
import pypandoc
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# === Load environment variables ===
load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "qwen/qwen-2.5-72b-instruct"

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".py", ".js", ".html", ".css", ".ts", ".jsx", ".java", ".cpp"}
EXCLUDE_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__"}

def safe_path(path: str) -> str:
    """Make file paths safe for Markdown/PDF conversion."""
    path = path.replace("\\", "/")
    specials = r"([_#{}$%&~^\\])"
    return re.sub(specials, r"\\\1", path)

def read_code(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def remove_non_ascii(text):
    """Remove all non-ASCII characters to prevent LaTeX errors."""
    return text.encode('ascii', errors='ignore').decode('ascii')


def save_pdf_from_markdown(markdown_text, output_path):
    """Convert markdown text to PDF using xelatex for Unicode support."""
    pypandoc.convert_text(
        markdown_text,
        'pdf',
        format='md',
        outputfile=output_path,
        extra_args=['--pdf-engine=xelatex', '--standalone']
    )


def get_explanation(code):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Code Explainer"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a programming tutor. "
                    "Summarize the given code in at most TWO short sentences. "
                    "Avoid detailed breakdowns — just say what it does."
                )
            },
            {
                "role": "user",
                "content": f"Summarize this code:\n\n```{code}```"
            }
        ]
    }
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    explanation = resp.json()["choices"][0]["message"]["content"]
    return remove_non_ascii(explanation)

def process_file(file_path, rel_path, counter):
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None, None

    if os.path.getsize(file_path) > 50_000:
        print(f"⏩ Skipping large file: {rel_path}")
        return None, None

    code = read_code(file_path)
    safe_rel = safe_path(rel_path)

    code_md = f"## {counter}. {safe_rel}\n```{ext[1:]}\n{code}\n```\n\n"

    print(f"📤 Explaining {rel_path}...")
    explanation = get_explanation(code)
    explanation_md = f"## {counter}. {safe_rel}\n\n{explanation}\n\n"

    return code_md, explanation_md

def process_folder(folder_path):
    code_md = "# Project Code\n\n"
    explanation_md = "# Project Code with Short Explanations\n\n"

    tasks = []
    counter = 1

    with ThreadPoolExecutor(max_workers=5) as executor:
        for root, dirs, files in os.walk(folder_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in sorted(files):
                ext = os.path.splitext(file)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, folder_path)
                tasks.append(executor.submit(process_file, file_path, rel_path, counter))
                counter += 1

        for future in as_completed(tasks):
            file_code_md, file_explanation_md = future.result()
            if file_code_md and file_explanation_md:
                code_md += file_code_md
                explanation_md += file_explanation_md

    save_pdf_from_markdown(code_md, os.path.join(OUTPUT_DIR, "code_only.pdf"))
    save_pdf_from_markdown(explanation_md, os.path.join(OUTPUT_DIR, "code_with_explanation.pdf"))

def main():
    if not API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in environment variables.")

    if len(sys.argv) < 2:
        print("Usage: python explainer.py <folder_path>")
        sys.exit(1)

    folder_path = sys.argv[1]
    if not os.path.isdir(folder_path):
        print(f"❌ '{folder_path}' is not a valid folder.")
        sys.exit(1)

    process_folder(folder_path)

if __name__ == "__main__":
    main()
