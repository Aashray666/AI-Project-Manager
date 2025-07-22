
# import os
# import json
# import uuid
# import requests
# from typing import Dict, Any, List

# # --- Configuration ---
# API_KEY = "AIzaSyCjkHKz8PpUjJ0NXcafrKmB65E38eFrfrc"

# def load_employees(filename: str = "employees.json") -> list[dict]:
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     project_root = os.path.abspath(os.path.join(script_dir, os.pardir))
#     data_path = r"C:\Users\aashr\Desktop\EmployeeA\data\employess.json"

#     if not os.path.isfile(data_path):
#         raise FileNotFoundError(f"Could not find employee file at {data_path}")
#     with open(data_path, "r", encoding="utf-8") as f:
#         return json.load(f)

# def generate_project(brief: str, eligible_employees: list[dict]) -> Dict[str, Any]:
#     """
#     Generates a project title, description, and team.
#     """
#     if not API_KEY:
#         raise ValueError("API_KEY is not set. Please add your Google AI API key.")

#     prompt = f"""
# You are an expert project manager. Given a project brief, you will:
# 1. Invent a creative and relevant project title and a detailed description.
# 2. Intelligently assemble a small, effective team from the provided roster.

# **Roster of Available Employees:**
# ```json
# {json.dumps(eligible_employees, indent=2)}
# ```

# **Project Brief:**
# \"\"\"{brief}\"\"\"

# Please **output valid JSON** with these keys:
# - "title" (string): A concise and professional project title.
# - "description" (string): A one-paragraph summary of the project.
# - "team" (list of employee IDs): A list of employee "id" strings.
# """
    
#     url = (
#         "https://generativelanguage.googleapis.com/"
#         "v1beta/models/gemini-1.5-flash-latest:generateContent"
#         f"?key={API_KEY}"
#     )
#     payload = {
#         "contents": [{"parts": [{"text": prompt}]}],
#         "generationConfig": {"responseMimeType": "application/json"}
#     }
#     headers = {"Content-Type": "application/json"}

#     try:
#         resp = requests.post(url, headers=headers, json=payload, timeout=60)
#         resp.raise_for_status()
#     except requests.exceptions.RequestException as e:
#         raise RuntimeError(f"API request failed: {e}")

#     data = resp.json()
#     try:
#         raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
#         return json.loads(raw_text)
#     except (KeyError, IndexError, json.JSONDecodeError) as e:
#         raise ValueError(f"Could not parse AI model's JSON response: {e}\n\nRaw response was:\n{data}")

# def modify_tasks_with_llm(current_tasks: List[Dict[str, Any]], project_team: List[Dict[str, Any]], command: str) -> List[Dict[str, Any]]:
#     """
#     Uses an LLM to interpret a user command and modify a list of structured task objects, including assignments.
#     """
#     if not API_KEY:
#         raise ValueError("API_KEY is not set. Please add your Google AI API key.")

#     prompt = f"""
# You are an intelligent project management assistant. Your primary role is to manage a list of tasks based on user commands.

# **Your Core Capabilities:**
# 1.  **Correct Mistakes:** Silently correct spelling or grammar in the user's command.
# 2.  **Interpret Intent:** Analyze the corrected command to understand the user's goal.
# 3.  **Manage Task Properties:** Each task object has an 'id', 'description', 'status', and 'assignee_id'.

# **Project Team Roster (for finding assignee IDs):**
# ```json
# {json.dumps(project_team, indent=2)}
# ```

# **Current Task List (JSON Array of Objects):**
# ```json
# {json.dumps(current_tasks, indent=2)}
# ```

# **User Command:**
# "{command}"

# **Execution Flow:**
# 1.  **To ADD a task:** Create a new task object. The `id` must be a new unique string, `description` comes from the command, `status` defaults to "To Do", and `assignee_id` defaults to `null`. If the command includes an assignment (e.g., "add task ... and assign to Ravi"), find the correct employee `id` from the roster and set it as the `assignee_id`.
# 2.  **To ASSIGN a task:** If the command is to assign a task (e.g., "assign task 2 to Anita"), find the target task object and update its `assignee_id` with the correct employee `id` from the roster.
# 3.  **To REMOVE/DELETE a task:** Remove the entire task object specified by its description or 1-based index.
# 4.  **To UPDATE STATUS (move/mark as):** Find the target task and update its `status` field to the new value ("To Do", "In Progress", or "Completed").

# **CRITICAL OUPUT RULE:** Your final output **MUST BE** only the complete, modified, and valid JSON array of task objects. Do not include any other text. Just the raw JSON.

# Now, process the provided task list and command.

# **Your Output (JSON Array of Objects only):**
# """
    
#     url = (
#         "https://generativelanguage.googleapis.com/"
#         "v1beta/models/gemini-1.5-flash-latest:generateContent"
#         f"?key={API_KEY}"
#     )
#     payload = {
#         "contents": [{"parts": [{"text": prompt}]}],
#         "generationConfig": {"responseMimeType": "application/json"}
#     }
#     headers = {"Content-Type": "application/json"}

#     try:
#         resp = requests.post(url, headers=headers, json=payload, timeout=90)
#         resp.raise_for_status()
#     except requests.exceptions.RequestException as e:
#         raise RuntimeError(f"API request failed: {e}")

#     data = resp.json()
#     try:
#         raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
#         modified_list = json.loads(raw_text)
#         if isinstance(modified_list, list):
#             if not modified_list or (isinstance(modified_list[0], dict) and 'id' in modified_list[0]):
#                  return modified_list
#         raise ValueError("AI did not return a valid list of task objects.")
#     except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
#         raise ValueError(f"Could not parse AI model's JSON response: {e}\n\nRaw response was:\n{data}")
import os
import json
import uuid
import requests
from typing import Dict, Any, List
from datetime import datetime

# --- Configuration ---
API_KEY = "AIzaSyCjkHKz8PpUjJ0NXcafrKmB65E38eFrfrc" # PASTE YOUR GOOGLE AI API KEY HERE

def load_employees(filename: str = "employees.json") -> list[dict]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, os.pardir))
    data_path = "./data/employess.json"

    if not os.path.isfile(data_path):
        raise FileNotFoundError(f"Could not find employee file at {data_path}")
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_project(brief: str, eligible_employees: list[dict]) -> Dict[str, Any]:
    """
    Generates a project title, description, and team.
    """
    if not API_KEY:
        raise ValueError("API_KEY is not set. Please add your Google AI API key.")

    prompt = f"""
You are an expert project manager. Given a project brief, you will:
1. Invent a creative and relevant project title and a detailed description.
2. Intelligently assemble a small, effective team from the provided roster.

**Roster of Available Employees:**
```json
{json.dumps(eligible_employees, indent=2)}
```

**Project Brief:**
\"\"\"{brief}\"\"\"

Please **output valid JSON** with these keys:
- "title" (string): A concise and professional project title.
- "description" (string): A one-paragraph summary of the project.
- "team" (list of employee IDs): A list of employee "id" strings.
"""
    
    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/gemini-1.5-flash-latest:generateContent"
        f"?key={API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"API request failed: {e}")

    data = resp.json()
    try:
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(raw_text)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise ValueError(f"Could not parse AI model's JSON response: {e}\n\nRaw response was:\n{data}")

def modify_tasks_with_llm(current_tasks: List[Dict[str, Any]], project_team: List[Dict[str, Any]], command: str) -> List[Dict[str, Any]]:
    """
    Uses an LLM to interpret a user command and modify a list of structured task objects, including assignments and due dates.
    """
    if not API_KEY:
        raise ValueError("API_KEY is not set. Please add your Google AI API key.")

    # Provide the current date to the AI for context
    current_date = datetime.now().strftime('%Y-%m-%d')

    prompt = f"""
You are an intelligent project management assistant. Your primary role is to manage a list of tasks based on user commands.

**Today's Date is: {current_date}**

**Your Core Capabilities:**
1.  **Correct Mistakes:** Silently correct spelling or grammar in the user's command.
2.  **Interpret Intent:** Analyze the corrected command to understand the user's goal.
3.  **Manage Task Properties:** Each task object has an 'id', 'description', 'status', 'assignee_id', and 'due_date'.

**Project Team Roster (for finding assignee IDs):**
```json
{json.dumps(project_team, indent=2)}
```

**Current Task List (JSON Array of Objects):**
```json
{json.dumps(current_tasks, indent=2)}
```

**User Command:**
"{command}"

**Execution Flow:**
1.  **To ADD a task:** Create a new task object. The `id` must be a new unique string, `description` from the command, `status` defaults to "To Do", `assignee_id` to `null`, and `due_date` to `null`.
2.  **To ASSIGN a task:** Find the target task and update its `assignee_id`.
3.  **To SET A DEADLINE (e.g., "set due date for task 1 to next monday"):** Find the target task and update its `due_date`. Use today's date ({current_date}) to calculate the correct absolute date in YYYY-MM-DD format.
4.  **To REMOVE/DELETE a task:** Remove the entire task object.
5.  **To UPDATE STATUS (move/mark as):** Find the target task and update its `status` field.

**CRITICAL OUPUT RULE:** Your final output **MUST BE** only the complete, modified, and valid JSON array of task objects. Do not include any other text. Just the raw JSON.

Now, process the provided task list and command.

**Your Output (JSON Array of Objects only):**
"""
    
    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/gemini-1.5-flash-latest:generateContent"
        f"?key={API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"API request failed: {e}")

    data = resp.json()
    try:
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        modified_list = json.loads(raw_text)
        if isinstance(modified_list, list):
            if not modified_list or (isinstance(modified_list[0], dict) and 'id' in modified_list[0]):
                 return modified_list
        raise ValueError("AI did not return a valid list of task objects.")
    except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Could not parse AI model's JSON response: {e}\n\nRaw response was:\n{data}")
