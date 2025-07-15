import os
import pandas as pd
import difflib
from code_executor import run_code
from code_generator import ask_groq_for_code, ask_groq_for_tool_plan

# === Tool Registry ===
tools = {
    "code_generator": ask_groq_for_code,
    "code_runner": run_code
}

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

# === Language Detector ===
def detect_language_from_code(code: str) -> str:
    code_lower = code.lower()
    if "proc " in code_lower or "data " in code_lower:
        return "sas"
    elif any(kw in code_lower for kw in ["select", "from", "where"]):
        return "sql"
    else:
        return "python"

# === Main Agent ===
def main():
    print("\U0001f9e0 Welcome to CodeGen Runner!")
    user_input = input("\U0001f4c1 Enter file name (full or partial): ").strip()
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
        task = input("\n\U0001f4ac Enter your data task (or type 'exit'): ")
        if task.lower() == "exit":
            break

        # === Ask LLM to decide which tools to use ===
        tool_plan_prompt = f"""
Given the user task below, return a Python list of tool names (as strings) you want to use to accomplish the task. 
Available tools = ["code_generator", "code_runner"]
ONLY respond with a Python list like: ["code_generator"] or ["code_generator", "code_runner"]

User Task: "{task}"
"""
        tool_plan_raw = ask_groq_for_tool_plan(tool_plan_prompt)
        try:
            tool_plan = eval(tool_plan_raw.strip())
            print(f"\U0001f527 Tool Plan Response: {tool_plan}")
        except:
            print("❌ Failed to interpret tool plan.")
            continue

        generated_code = None

        for tool_name in tool_plan:
            if tool_name == "code_generator":
                prompt = f"""
Here is a preview of a dataset from file '{file_name}':
{data_preview}

Task: {task}

Use the file name '{file_name}' for Python and table name '{table_name}' for SQL/SAS.
Respond with code only, no explanation.
"""
                generated_code = tools["code_generator"](prompt)
                print("\n\U0001f4be Generated Code:\n")
                print(generated_code)

            elif tool_name == "code_runner":
                if not generated_code:
                    print("❌ No code to run.")
                    continue
                language = detect_language_from_code(generated_code)
                print("\n\U0001f680 Executing Code...")
                result = tools["code_runner"](generated_code, language, data_file=file_path)
                print("\n\U0001f4be Execution Result:\n")
                print(result)

        print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
