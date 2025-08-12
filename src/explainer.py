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

def call_llm(prompt):
    """Generic function to send a prompt to Qwen via OpenRouter."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Code Tool"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful programming tutor."},
            {"role": "user", "content": prompt}
        ]
    }
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    return remove_non_ascii(resp.json()["choices"][0]["message"]["content"])

def get_explanation(code):
    """Get short explanation for given code."""
    prompt = (
        "Summarize the given code in at most TWO short sentences. "
        "Avoid detailed breakdowns — just say what it does.\n\n"
        f"```{code}```"
    )
    return call_llm(prompt)

def generate_quiz(all_explanations):
    """Generate 10 MCQs for the entire project."""
    prompt = (
        "Based on the following project explanations, create a quiz with exactly 10 multiple-choice questions:\n"
        "- 2 easy\n"
        "- 3 medium\n"
        "- 5 hard\n"
        "Each question should have 4 options labeled A-D, one correct answer, and clearly mark the correct answer.\n\n"
        f"Project explanations:\n{all_explanations}"
    )
    return call_llm(prompt)

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
    all_explanations_text = ""

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
                all_explanations_text += file_explanation_md + "\n"

    # Save code + explanation PDFs
    save_pdf_from_markdown(code_md, os.path.join(OUTPUT_DIR, "code_only11.pdf"))
    save_pdf_from_markdown(explanation_md, os.path.join(OUTPUT_DIR, "code_with_explanation11.pdf"))

    # Generate quiz
    print("📝 Generating quiz...")
    quiz_text = generate_quiz(all_explanations_text)
    quiz_md = "# Project Quiz\n\n" + quiz_text
    save_pdf_from_markdown(quiz_md, os.path.join(OUTPUT_DIR, "quiz11.pdf"))

# ADD THIS AT THE END OF explainer.py, before `if __name__ == "__main__":`

def explain_project(project_path):
    """
    Returns:
        summary_text (str): Overview of the project
        ai_suggestions (str): Improvement recommendations
    """
    all_code = ""
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            try:
                all_code += read_code(os.path.join(root, file)) + "\n\n"
            except Exception as e:
                print(f"⚠️ Skipping {file}: {e}")

    # Call model for summary
    summary_prompt = (
        "Provide a short, plain-English overview of the following project's codebase:\n\n"
        f"{all_code[:12000]}"  # limit so we don't overflow context
    )
    summary_text = call_llm(summary_prompt)

    # Call model for improvement suggestions
    suggestions_prompt = (
        "Analyze the following project's codebase and suggest specific improvements in style, "
        "performance, and maintainability:\n\n"
        f"{all_code[:12000]}"
    )
    ai_suggestions = call_llm(suggestions_prompt)

    return summary_text, ai_suggestions

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
