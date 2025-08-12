import os
import re
import sys
import lizard
from fpdf import FPDF
from explainer import explain_project, ALLOWED_EXTENSIONS, EXCLUDE_DIRS


EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".idea", ".vscode"}
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def remove_unicode(text):
    return re.sub(r'[^\x00-\x7F]+', '', text)

class PDF(FPDF):
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(2)
    def chapter_body(self, body):
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 10, body)
        self.ln()

def run_lizard(path):
    results = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if file.endswith((".js", ".py", ".java", ".cpp", ".c", ".ts")):
                file_path = os.path.join(root, file)
                try:
                    results.extend(lizard.analyze_file(file_path).function_list)
                except Exception as e:
                    print(f"⚠️ Error analyzing {file_path}: {e}")
    return results



def generate_report(project_path):
    print("📊 Running AI analysis...")
    summary_text, ai_suggestions = explain_project(project_path)
    summary_text = remove_unicode(summary_text)
    ai_suggestions = remove_unicode(ai_suggestions)

    print("📈 Running complexity analysis...")
    functions = run_lizard(project_path)
    complexity_report = "\n".join(
        [f"{func.name} - CC: {func.cyclomatic_complexity} - LOC: {func.length}"
         for func in functions]
    )
    complexity_report = remove_unicode(complexity_report)

    print("📝 Generating PDF report...")
    pdf = PDF()
    pdf.add_page()
    pdf.chapter_title("Project Summary")
    pdf.chapter_body(summary_text)
    pdf.chapter_title("AI Recommendations")
    pdf.chapter_body(ai_suggestions)
    pdf.chapter_title("Complexity Report")
    pdf.chapter_body(complexity_report)

    output_path = os.path.join(OUTPUT_DIR, "project_report.pdf")
    pdf.output(output_path)
    print(f"✅ Report generated: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python report.py <project_path>")
        sys.exit(1)
    generate_report(sys.argv[1])
