import pandas as pd
import requests
import json
import os
import traceback
import sqlite3
import subprocess
from flask import Flask, session
import secrets

# === Initialize Flask App (for SAS session support) ===
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
user_sessions = {}

# === SAS Session Placeholder ===
def get_user_sas_session():
    username = session.get('username_to_update')
    if username and username in user_sessions:
        return user_sessions[username]
    return None

# === Config ===
GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-70b-8192"

# === Load any data file ===
def load_data(file_path):
    try:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path, encoding='ISO-8859-1')
        elif file_path.endswith(".xlsx") or file_path.endswith(".xls"):
            df = pd.read_excel(file_path)
        else:
            print("❌ Unsupported file format. Use CSV or Excel.")
            return None
        print("\n📊 Data Preview:")
        print(df.head())
        return df
    except Exception as e:
        print("❌ Error loading data:", e)
        return None

# === Prompt the LLM ===
def ask_groq_for_code(task, data_preview):
    system_msg = (
        "You are an agentic code execution assistant. A user gives you a dataset preview and a task.\n"
        "Your job is to choose the correct language and execution tool based on the prompt and data.\n"
        "Only use the language explicitly mentioned in the prompt.\n"
        "Return a JSON object with: 'language', 'execution', and 'code'.\n"
        "Execution types: 'exec_in_memory', 'run_rscript', 'run_matlab', 'run_sqlite', 'run_sas', 'run_julia', 'external_only'."
    )

    user_msg = f"""
Task:
{task}

Data Preview:
{data_preview}

Respond only in JSON format like:
{{
  "language": "python",
  "execution": "exec_in_memory",
  "code": "print(\"hello\")"
}}
"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.2
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        return json.loads(content)
    except Exception as e:
        print("❌ Error querying Groq or parsing response:", e)
        return None

# === Execute Code ===
def agentic_run(language, execution_type, code, df):
    try:
        if execution_type == "exec_in_memory":
            local_vars = {"pd": pd, "df": df}
            exec(code, local_vars)
            return "✅ Executed successfully."


        elif execution_type == "run_sqlite":
            conn = sqlite3.connect(":memory:")
            df.to_sql("table_name", conn, index=False, if_exists="replace")
            cursor = conn.cursor()

            statements = [stmt.strip() for stmt in code.strip().split(';') if stmt.strip()]
            if not statements:
                return "❌ SQL code is empty or invalid."

            for stmt in statements[:-1]:
                cursor.execute(stmt)

            last_stmt = statements[-1]
            cursor.execute(last_stmt)

            rows = cursor.fetchall()
            if cursor.description:
                col_names = [desc[0] for desc in cursor.description]
                result_df = pd.DataFrame(rows, columns=col_names)
                print("\n📊 SQL Output:")
                print(result_df)
            else:
                print("ℹ️ SQL executed. No result to fetch.")

            return "✅ SQL executed."

        elif execution_type == "run_rscript":
            with open("temp.R", "w") as f:
                f.write(code)
            subprocess.run(["Rscript", "temp.R"], check=True)
            return "✅ R script executed."

        elif execution_type == "run_matlab":
            with open("temp.m", "w") as f:
                f.write(code)
            subprocess.run(["matlab", "-batch", "temp"], check=True)
            return "✅ MATLAB script executed."

        elif execution_type == "run_julia":
            with open("temp.jl", "w") as f:
                f.write(code)
            subprocess.run(["julia", "temp.jl"], check=True)
            return "✅ Julia script executed."

        elif execution_type == "run_sas":
            sas = get_user_sas_session()
            if sas:
                sas.submit(code)
                return "✅ SAS code submitted."
            else:
                return "❌ No SAS session found."

        elif execution_type == "external_only":
            return "ℹ️ Execution requires external tools. Please run manually."

        return "❌ Unknown execution type."

    except Exception as e:
        return f"❌ Execution error: {str(e)}\n{traceback.format_exc()}"

# === Retry Loop ===
def retry_with_correction(language, execution_type, code, df, error, task, max_retries=4):
    for attempt in range(max_retries):
        print(f"\n🔁 Retrying correction (attempt {attempt+1})...")
        correction_prompt = f"Fix this code. Error: {error}\n\nCode:\n{code}\n\nTask:\n{task}"
        correction = ask_groq_for_code(correction_prompt, df.head().to_string())
        if not correction:
            return "❌ Correction failed."
        language = correction['language']
        execution_type = correction['execution']
        code = correction['code']
        output = agentic_run(language, execution_type, code, df)
        if output.startswith("✅"):
            return output
        error = output
    return "❌ Max retries reached."

# === Main Loop ===
def main():
    print("\n🧠 Choose input method:")
    print("1. Upload a CSV or Excel file")
    print("2. Use an instruction file (no data)")
    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":
        path = input("📁 Enter path to data file: ").strip()
        df = load_data(path)
        if df is None: return
        preview = df.head().to_string()
        task = input("\n💬 What do you want to do with this data? ")
    elif choice == "2":
        path = input("📄 Enter instruction file path: ").strip()
        if not os.path.exists(path):
            print("❌ File not found.")
            return
        task = open(path, encoding='utf-8').read()
        df = pd.DataFrame()
        preview = "(no preview from file only)"
    else:
        print("❌ Invalid choice.")
        return

    response = ask_groq_for_code(task, preview)
    if not response:
        return

    language = response['language']
    execution = response['execution']
    code = response['code']

    print(f"\n📦 Language: {language}\n⚙️ Execution: {execution}\n\n🧾 Code:\n{code}")
    print("\n🚀 Executing...")
    output = agentic_run(language, execution, code, df)
    if not output.startswith("✅"):
        output = retry_with_correction(language, execution, code, df, output, task)

    print("\n📤 Final Output:")
    print(output)

if __name__ == "__main__":
    main()
