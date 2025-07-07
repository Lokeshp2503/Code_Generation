import pandas as pd
import requests
import os

# === Config ===
GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-70b-8192"

# === Load Data ===
def load_data(file_path):
    try:
        df = pd.read_csv(file_path, encoding='ISO-8859-1')
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
    print("1. Upload a CSV file")
    print("2. Use a local instructions file (with data preview + task)")

    choice = input("Enter choice (1 or 2): ").strip()

    if choice == '1':
        file_path = input("📁 Enter CSV file path: ").strip()
        df = load_data(file_path)
        if df is None:
            return
        data_preview = df.head(5).to_string()
        while True:
            task = input("\n💬 Enter your data task (or type 'exit'): ")
            if task.lower() == "exit":
                break
            prompt = f"""Here is a preview of a dataset:\n{data_preview}\n\nTask: {task}\n\nProvide code only (no explanation). Let the model decide if it should use Python, SQL, or SAS."""
            code = ask_groq_for_code(prompt)
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
        print("\n🧾 Generated Code:\n")
        print(code)
        print("\n" + "=" * 60)


    else:
        print("❌ Invalid choice. Please enter 1 or 2.")

if __name__ == "__main__":
    main()
