import os
import pandas as pd
import difflib
from code_runner_agent import run_code
from code_generator_agent import ask_groq_for_code

# === Fuzzy Match Input File ===
def find_closest_filename(user_input):
    supported_exts = ('.csv', '.xlsx', '.xls', '.json')
    all_files = [f for f in os.listdir() if f.lower().endswith(supported_exts)]
    matches = difflib.get_close_matches(user_input, all_files, n=1, cutoff=0.5)
    if matches:
        print(f"🤖 Using closest match: {matches[0]}")
        return matches[0]
    else:
        print("❌ No close file match found.")
        return None

# === Load Data File ===
def load_data(file_path):
    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            df = pd.read_csv(file_path, encoding='ISO-8859-1')
        elif ext in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path)
        elif ext == ".json":
            df = pd.read_json(file_path)
        else:
            print(f"❌ Unsupported file format: {ext}")
            return None
        print("📊 Data Preview:")
        print(df.head())
        return df
    except Exception as e:
        print("❌ Error loading data:", e)
        return None

# === Detect Code Language from Generated Code (fallback)
def detect_language_from_code(code: str) -> str:
    if any(kw in code.lower() for kw in ["select", "from", "where"]):
        return "sql"
    elif "data " in code.lower() and "set" in code.lower():
        return "sas"
    else:
        return "python"

# === Main Orchestrator ===
def main():
    print("🧠 Welcome to CodeGen Runner!")
    user_input = input("📁 Enter file name (full or partial): ").strip()
    file_path = find_closest_filename(user_input)
    if not file_path:
        return

    df = load_data(file_path)
    if df is None:
        return

    file_name = os.path.basename(file_path)
    table_name = os.path.splitext(file_name)[0]
    data_preview = df.head(5).to_string()

    while True:
        task = input("\n💬 Enter your data task (or type 'exit'): ")
        if task.lower() == "exit":
            break

        # === Hardcoded language hint logic ===
        task_lower = task.lower()
        if "sql" in task_lower:
            lang_hint = "Respond ONLY with SQL code. Do not include any other languages."
        elif "python" in task_lower:
            lang_hint = "Respond ONLY with Python code. Do not include any other languages."
        elif "sas" in task_lower:
            lang_hint = "Respond ONLY with SAS code. Do not include any other languages."
        else:
            lang_hint = "Choose the best language (Python, SQL, SAS) and respond with only that."

        prompt = f"""Here is a preview of a dataset from file '{file_name}':\n{data_preview}

Task: {task}

Use the file name '{file_name}' for Python and table name '{table_name}' for SQL/SAS.
{lang_hint}
Respond with code only, no explanation."""

        generated_code = ask_groq_for_code(prompt)
        print("\n🧾 Generated Code:\n")
        print(generated_code)

        # Fallback language detection
        language = detect_language_from_code(generated_code)

        print("\n🚀 Executing Code...")
        result = run_code(generated_code, language, data_file=file_path)

        print("\n🧾 Execution Result:\n")
        print(result)
        print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
