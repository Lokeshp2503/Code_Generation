import pandas as pd
import requests
import json
import os
import traceback
import sqlite3
import contextlib
import io
import re
from flask import Flask, session
import secrets
from datetime import datetime

# === Flask App Setup ===1
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
user_sessions = {}

def get_user_sas_session():
    username = session.get("username_to_update")
    return user_sessions.get(username)

# === Config ===
GROQ_API_KEY = "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"  # Replace with your actual key
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-70b-8192"

# === TOOL REGISTRY ===
tool_list = [
    {"tool": "python_interpreter", "language": "python", "execution": "exec_in_memory"},
    {"tool": "sql_interpreter", "language": "sql", "execution": "run_sqlite"},
    {"tool": "sas_executor", "language": "sas", "execution": "run_sas"}
]

# === TOOL: File Loader ===
def load_data(file_path):
    try:
        if file_path.endswith(".csv"):
            return pd.read_csv(file_path, encoding="utf-8")
        elif file_path.endswith((".xlsx", ".xls")):
            return pd.read_excel(file_path)
        elif file_path.endswith(".json"):
            return pd.read_json(file_path)
        else:
            raise ValueError("Unsupported file format.")
    except Exception as e:
        print("❌ Error loading data:", e)
        return None

# === Helper: Extract and clean LLM response JSON ===
def extract_clean_json(content):
    match = re.search(r'\{(?:[^{}]|(?R))*\}', content, re.DOTALL)
    if not match:
        print("❌ No JSON object found in response.")
        return None

    content_json = match.group(0)
    content_json = re.sub(r"(?<!\\)'", '"', content_json)
    print(content_json)

    # Escape quotes inside the code string
    def escape_code_quotes(m):
        escaped_code = m.group(1).replace('"', '\\"')
        return f'"code": "{escaped_code}"'

    content_json = re.sub(r'"code"\s*:\s*"([^"]*?)"', escape_code_quotes, content_json, flags=re.DOTALL)
    return content_json

# === TOOL: Ask LLM to pick tool and generate code ===
def ask_llm(task, preview):
    system_msg = (
        "You are an intelligent agent for data analysis. A user gives a task and dataset preview.\n"
        "Choose the best tool from the following list based on the task:\n"
        + json.dumps(tool_list, indent=2) + "\n"
        "Return JSON in this format: {\"tool\": tool_name, \"language\": ..., \"execution\": ..., \"code\": ...}"
    )

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"Task:\n{task}\n\nPreview:\n{preview}"}
        ],
        "temperature": 0.3
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        res = requests.post(GROQ_API_URL, headers=headers, json=payload)
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"]

        content_json = extract_clean_json(content)
        if not content_json:
            return None

        return json.loads(content_json)

    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP error: {http_err}")
        print("🔑 Check your GROQ_API_KEY or GROQ_MODEL configuration.")
        return None

    except json.JSONDecodeError as parse_err:
        print("❌ JSON parse failed:", parse_err)
        print("🔍 Offending content:", content_json if 'content_json' in locals() else 'N/A')
        return None

    except Exception as e:
        print("❌ Unexpected LLM error:", e)
        return None

# === TOOL: Execute Code ===
def execute_code(tool, language, method, code, df):
    try:
        if method == "exec_in_memory":
            local_vars = {"pd": pd, "df": df.copy()}
            with contextlib.redirect_stdout(io.StringIO()) as out:
                exec(code, local_vars)
                result = local_vars.get("result", df)
                if isinstance(result, pd.DataFrame):
                    df = result
            return "✅ Executed", df

        elif method == "run_sqlite":
            conn = sqlite3.connect(":memory:")
            df.to_sql("table_name", conn, index=False, if_exists="replace")
            cur = conn.cursor()
            queries = [q.strip() for q in code.split(';') if q.strip()]
            for q in queries[:-1]:
                cur.execute(q)
            cur.execute(queries[-1])
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            df = pd.DataFrame(rows, columns=columns)
            return "✅ SQL executed", df

        elif method == "run_sas":
            sas = get_user_sas_session()
            if sas:
                sas.submit(code)
                return "✅ SAS executed", df
            return "❌ No SAS session", df

        return "❌ Unknown execution method", df

    except Exception as e:
        return f"❌ Error: {e}", df

# === TOOL: Retry Correction ===
def retry(task, df, tool, language, method, code, error):
    for i in range(3):
        print(f"\n🔁 Retry {i+1}: Sending error to LLM")
        result = ask_llm(f"Fix this error: {error}\n\nTask:\n{task}", df)
        if result:
            tool, language, method, code = result["tool"], result["language"], result["execution"], result["code"]
            status, df = execute_code(tool, language, method, code, df)
            if status.startswith("✅"):
                return status, df
    return "❌ Max retries reached", df

# === MAIN ===
def main():
    print("\n📥 1. Upload file\n📝 2. Instruction only")
    choice = input("Enter choice (1/2): ").strip()
    df = pd.DataFrame()

    if choice == "1":
        file_path = input("Enter file path: ").strip()
        df = load_data(file_path)
        if df is None:
            return
        task = input("\nWhat do you want to do with this data? ")
    elif choice == "2":
        path = input("Enter task file path: ").strip()
        task = open(path, encoding="utf-8").read()
    else:
        print("❌ Invalid choice")
        return

    preview = df.head().to_string() if not df.empty else ""
    response = ask_llm(task, preview)
    if not response:
        print("❌ Failed to get response from LLM")
        return

    tool, lang, method, code = response["tool"], response["language"], response["execution"], response["code"]
    print(f"\n🤖 Tool: {tool}\n🧠 Language: {lang}\n⚙️ Execution: {method}\n\n📜 Code:\n{code}")

    status, df = execute_code(tool, lang, method, code, df)

    if not status.startswith("✅"):
        status, df = retry(task, df, tool, lang, method, code, status)

    print("\n📤 Final Output:", status)
    if not df.empty:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"output_{timestamp}.xlsx"
            df.to_excel(output_file, index=False)
            print(f"💾 Saved to {output_file}")
        except Exception as e:
            print("❌ Save failed:", e)

if __name__ == "__main__":
    main()
