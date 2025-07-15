import pandas as pd
import requests
import os
import json
import difflib

# === Config ===
GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-70b-8192"

# === Fuzzy Match File ===
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

# === Load Data ===
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

# === Load Instructions ===
def load_instructions(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print("❌ Error reading instruction file:", e)
        return None

# === Generate Code from Groq ===
def ask_groq_for_code(prompt):
    system_msg = (
        "You are a helpful data expert. The user will provide a dataset and a task. "
        "Choose the most appropriate programming or query language to solve the task. "
        "You can use Python, SQL, SAS, R, MATLAB, Julia, or any other language the task seems to call for. "
        "Respond with code only (no explanation or description)."
    )

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    response = requests.post(GROQ_API_URL, headers=headers, json=payload)

    if response.status_code != 200:
        print("❌ Groq API Error:", response.status_code)
        print(response.text)
        return None

    return response.json()['choices'][0]['message']['content']

# === Main Flow ===
def main():
    print("🧠 Choose input method:")
    print("1. Upload a data file (CSV, Excel, or JSON)")
    print("2. Use a local instructions file (with data preview + task)")

    choice = input("Enter choice (1 or 2): ").strip()

    if choice == '1':
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

            prompt = f"""Here is a preview of a dataset from a file named '{file_name}':\n{data_preview}

Task: {task}

Please generate only code (no explanation). Use the file name '{file_name}' if using Python, and table name '{table_name}' if using SQL or SAS."""
            code = ask_groq_for_code(prompt)
            if code:
                print("\n🧾 Generated Code:\n")
                print(code)
            print("\n" + "=" * 60)

    elif choice == '2':
        # Automatically detect instructions file in current directory
        instruction_file = None
        for fname in os.listdir():
            if fname.lower().startswith("instruction") and fname.lower().endswith((".txt", ".md")):
                instruction_file = fname
                break

        if instruction_file:
            print(f"📄 Found instructions file: {instruction_file}")
        else:
            instruction_file = input("❓ No 'instructions' file found. Enter path to instructions file manually: ").strip()

        full_text = load_instructions(instruction_file)
        if full_text is None:
            return

        print("📨 Sending instructions to Groq...")
        code = ask_groq_for_code(full_text)
        if code:
            print("\n🧾 Generated Code:\n")
            print(code)
        print("\n" + "=" * 60)

    else:
        print("❌ Invalid choice. Please enter 1 or 2.")
def ask_groq_for_tool_plan(prompt):
    system_msg = (
        "You are an intelligent planner agent. Given a user's task and metadata, "
        "you will decide which tools to use to complete the task. "
        "Available tools: ['code_generator', 'code_runner']. "
        "Reply ONLY with a Python list of tool names in the ord er to be used. "
        "Examples: ['code_generator'], or ['code_generator', 'code_runner']."
    )

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    response = requests.post(GROQ_API_URL, headers=headers, json=payload)

    if response.status_code != 200:
        print("❌ Tool Planner API Error:", response.status_code)
        print(response.text)
        return []

    raw = response.json()["choices"][0]["message"]["content"]
    
    try:
        tools = eval(raw.strip())  # 👈 safe here because we expect a Python list from LLM
        if isinstance(tools, list):
            return tools
        else:
            return []
    except:
        return []


if __name__ == "__main__":
    main()
