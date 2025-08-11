import pypandoc
from pygments import highlight
from pygments.lexers import PythonLexer, guess_lexer
from pygments.formatters import HtmlFormatter
import sys
import os

def code_to_markdown(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()

    lang = "python"  # Force Python for now
    md_content = f"```{lang}\n{code}\n```"
    return md_content


def markdown_to_pdf(md_content, output_path):
    # Save markdown temp file
    temp_md = "temp.md"
    with open(temp_md, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Convert to PDF using Pandoc + XeLaTeX
    pypandoc.convert_file(
        temp_md,
        'pdf',
        outputfile=output_path,
        extra_args=['--pdf-engine=xelatex']
    )

    os.remove(temp_md)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <codefile>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = os.path.join("output", "result.pdf")

    md = code_to_markdown(input_file)
    markdown_to_pdf(md, output_file)

    print(f"✅ PDF saved at {output_file}")
