import os
import pandas as pd
from langgraph.graph import StateGraph, END
from utils import load_data, detect_language
from typing import TypedDict, Optional, Any
# from code_generator import ask_groq_for_code
# from code_executor import run_code
# from data_preparation_agent import data_preparation_agent

# === Shared Utilities ===
def find_closest_filename(user_input):
    import difflib
    supported_exts = ('.csv', '.xlsx', '.xls', '.json')
    all_files = [f for f in os.listdir() if f.lower().endswith(supported_exts)]
    matches = difflib.get_close_matches(user_input, all_files, n=1, cutoff=0.5)
    if matches:
        print(f"🤖 Using closest match: {matches[0]}")
        return matches[0]
    else:
        print("❌ No close file match found.")
        return None

# === LangGraph Nodes ===
def decide_next_tool(state):
    """Simple logic to pick next step based on current state"""
    if state.get("result") and "Error" in str(state["result"]):
        if not state.get("cleaned_once"):
            return "data_preparation"
        else:
            return "code_generator"
    elif not state.get("code"):
        return "code_generator"
    elif not state.get("result"):
        return "code_executor"
    else:
        return END

def code_generator_node(state):
    prompt = state["prompt"]
    print("🧠 Generating code...")
    code = ask_groq_for_code(prompt)
    state["code"] = code
    return state

def code_executor_node(state):
    print("🚀 Running code...")
    language = detect_language(state["code"])
    result = run_code(state["code"], language, data_file=state["file_path"])
    state["language"] = language
    state["result"] = result
    return state

def data_preparation_node(state):
    print("🧪 Cleaning data and retrying...")
    cleaning_code, cleaned_file = data_preparation_agent(
        state["result"], state["data_preview"], state["file_path"]
    )
    if cleaned_file:
        state["file_path"] = cleaned_file
        state["cleaned_once"] = True
    return state

# === Main Entry Point ===
def main():
    print("\U0001f9e0 Agentic AI Code Gen (LangGraph Style)")
    user_input = input("📁 Enter filename (CSV, Excel, JSON): ").strip()
    file_path = find_closest_filename(user_input)
    if not file_path or not os.path.exists(file_path):
        print("❌ File not found.")
        return

    df = load_data(file_path)
    if df is None:
        print("❌ Failed to load the file.")
        return

    table_name = os.path.splitext(os.path.basename(file_path))[0]
    data_preview = df.head(5).to_string()

    task = input("\n💬 What do you want to do with the data? ").strip()
    prompt = f"""
Here is a preview of a dataset from a file named '{file_path}':
{data_preview}

Task: {task}

Please generate only code (no explanation). Use the file name '{file_path}' if using Python,
and table name '{table_name}' if using SQL or SAS.
"""

    initial_state = {
        "prompt": prompt,
        "file_path": file_path,
        "data_preview": data_preview,
        "task": task,
        "cleaned_once": False,
    }

    # Build LangGraph
    class AgentState(TypedDict, total=False):
        prompt: str
        code: str
        result: Any
        language: str
        file_path: str
        data_preview: str
        task: str
        cleaned_once: bool

    graph = StateGraph(AgentState)
    graph.add_node("decide", decide_next_tool)
    graph.add_node("code_generator", code_generator_node)
    graph.add_node("code_executor", code_executor_node)
    graph.add_node("data_preparation", data_preparation_node)

    graph.set_entry_point("decide")
    graph.add_edge("decide", "code_generator")
    graph.add_edge("decide", "code_executor")
    graph.add_edge("decide", "data_preparation")
    graph.add_edge("code_generator", "decide")
    graph.add_edge("code_executor", "decide")
    graph.add_edge("data_preparation", "decide")

    app = graph.compile()
    final_state = app.invoke(initial_state)

    print("\n📄 Final Code:\n", final_state.get("code", "N/A"))
    print("\n🚀 Final Result:\n", final_state.get("result", "N/A"))

if __name__ == "__main__":
    main()
