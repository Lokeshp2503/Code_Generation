import subprocess
import sqlite3
import pandas as pd
import os
import difflib
from datetime import datetime

# === Logging folder ===
LOG_DIR = "execution_logs"
os.makedirs(LOG_DIR, exist_ok=True)

def timestamp():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# === Save code and output ===
def save_run(code: str, output: str, table_df: pd.DataFrame = None):
    ts = timestamp()
    code_file = os.path.join(LOG_DIR, f"{ts}_code.txt")
    output_file = os.path.join(LOG_DIR, f"{ts}_output.txt")

    with open(code_file, "w", encoding="utf-8") as f:
        f.write(code.strip())

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output.strip())

    if table_df is not None:
        csv_path = os.path.join(LOG_DIR, f"{ts}_output.csv")
        xlsx_path = os.path.join(LOG_DIR, f"{ts}_output.xlsx")
        table_df.to_csv(csv_path, index=False)
        table_df.to_excel(xlsx_path, index=False)

# === Remove ``` code fences ===
def clean_code_fencing(code: str) -> str:
    if code.strip().startswith("```"):
        return "\n".join(
            line for line in code.splitlines()
            if not line.strip().startswith("```")
        )
    return code

# === Python Runner ===
def run_python_code(code: str):
    try:
        code = clean_code_fencing(code)
        exec_globals = {}
        exec(code, exec_globals)
        output = "✅ Python code executed successfully."
    except Exception as e:
        output = f"❌ Python Error:\n{e}"
    save_run(code, output)
    return output

# === SQL Runner ===
def run_sql_code(code: str, db_path=":memory:", data_file="Sample.csv"):
    try:
        code = clean_code_fencing(code)

        ext = os.path.splitext(data_file)[1].lower()
        if ext == ".csv":
            df = pd.read_csv(data_file, encoding="ISO-8859-1")
        elif ext in [".xlsx", ".xls"]:
            df = pd.read_excel(data_file)
        elif ext == ".json":
            df = pd.read_json(data_file)
        else:
            output = f"❌ Unsupported file format: {ext}"
            save_run(code, output)
            return output

        df.columns = (
            df.columns
            .str.strip()
            .str.replace(r"\s+", "_", regex=True)
            .str.replace('"', '')
            .str.replace("'", '')
        )

        print("📌 Table Schema:", df.columns.tolist())

        conn = sqlite3.connect(db_path)
        table_name = os.path.splitext(os.path.basename(data_file))[0]
        df.to_sql(table_name, conn, if_exists="replace", index=False)

        cursor = conn.cursor()
        cursor.execute(code)
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]

        if rows:
            result_df = pd.DataFrame(rows, columns=col_names)
            output = f"✅ SQL executed.\nOutput:\n{result_df.to_string(index=False)}"
            save_run(code, output, result_df)
            return output
        else:
            col_line = next((line for line in code.splitlines() if "SELECT" in line.upper()), "")
            tokens = col_line.replace(",", " ").split()
            possible_col = next((t for t in tokens if t.lower() not in ["select", "distinct", "from"]), None)
            suggestion = difflib.get_close_matches(possible_col, df.columns.tolist(), n=1)
            suggestion_msg = f"\n⚠️ Did you mean column: `{suggestion[0]}`?" if suggestion else ""
            output = f"✅ SQL executed, but no data returned.{suggestion_msg}"
            save_run(code, output)
            return output

    except Exception as e:
        output = f"❌ SQL Error:\n{e}"  
        save_run(code, output)
        return output

# === SAS Runner ===
def run_sas_code(code: str, sas_exe_path="C:/Program Files/SAS/SASFoundation/9.4/sas.exe"):
    try:
        code = clean_code_fencing(code)
        with open("temp.sas", "w") as f:
            f.write(code)

        result = subprocess.run(
            [sas_exe_path, "-sysin", "temp.sas"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            output = f"❌ SAS Error:\n{result.stderr}"
        else:
            output = "✅ SAS code executed successfully."

        save_run(code, output)
        return output

    except Exception as e:
        output = f"❌ SAS Execution Error:\n{e}"
        save_run(code, output)
        return output

# === Universal Runner ===
def run_code(code: str, language: str, data_file="Sample.csv"):
    language = language.lower()
    if language == "python":
        return run_python_code(code)
    elif language == "sql":
        return run_sql_code(code, data_file=data_file)
    elif language == "sas":
        return run_sas_code(code)
    else:
        output = "❌ Unsupported language. Only Python, SQL, and SAS are supported."
        save_run(code, output)
        return output
