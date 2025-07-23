import os
import json
import uuid
import requests
import streamlit as st  # --- ADDED: To access secrets
from typing import Dict, Any, List
from datetime import datetime

# --- FIXED: API key is now securely loaded from secrets ---
# It reads from the .streamlit/secrets.toml file you created.
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("API Key not found. Please create a `.streamlit/secrets.toml` file with your GOOGLE_API_KEY.")
    API_KEY = None

# --- Salary Grade Mapping ---
SALARY_GRADES = {
    "A": 3500,
    "B": 3000,
    "C": 2500,
    "D": 2200,
    "E": 2000,
}

def load_employees(filename: str = "employees.json") -> list[dict]:
    """Loads employee data from the data folder."""
    # --- FIXED: Path is now relative to the script location ---
    # This allows the app to run on any computer.
    script_dir = os.path.dirname(os.path.abspath(__file__)) # src/
    data_path = os.path.join(script_dir, '..', 'data', filename) # src/../data/employees.json

    if not os.path.isfile(data_path):
        raise FileNotFoundError(f"Could not find employee file at {data_path}. Ensure it is in the 'data' folder.")
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_project(brief: str, eligible_employees: list[dict], user_budget: int) -> Dict[str, Any]:
    """
    Generates a project title, description, and team, constrained by a user-provided budget.
    """
    if not API_KEY:
        raise ValueError("API_KEY is not configured. Please check your secrets file.")

    prompt = f"""
You are an expert project manager responsible for cost-effective staffing.
Your task is to generate a project plan based on a brief and a strict budget.

**Project Brief:**
\"\"\"{brief}\"\"\"

**Target Monthly Budget (EUR):**
{user_budget:,}

**Roster of Available Employees (with salary grades):**
```json
{json.dumps(eligible_employees, indent=2)}
```

**Salary Grade Values (EUR per month):**
```json
{json.dumps(SALARY_GRADES, indent=2)}
```

**Your Instructions:**
1.  **Create Title & Description:** Invent a creative project title and a detailed description.
2.  **Assemble a Team:** Select a team from the roster. Your primary goal is to select a team whose combined monthly salary is as close as possible to the **Target Monthly Budget** without exceeding it.
3.  **Calculate Budget:** Calculate your own `proposed_budget`. This is the sum of the salaries of the team members you selected, plus a 20% overhead. For example, if team salaries total €5,000, the `proposed_budget` would be €6,000.

**CRITICAL OUTPUT RULE:**
Please output **ONLY a valid JSON object** with these exact keys:
- "title" (string): A concise and professional project title.
- "description" (string): A one-paragraph summary of the project.
- "team" (list of employee IDs): A list of employee "id" strings from the roster.
- "proposed_budget" (integer): Your calculated budget (Team Salaries + 20% Overhead).
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
    Uses an LLM to interpret a user command and modify a list of structured task objects.
    """
    if not API_KEY:
        raise ValueError("API_KEY is not configured. Please check your secrets file.")

    current_date = datetime.now().strftime('%Y-%m-%d')

    prompt = f"""
You are an intelligent project management assistant. Your primary role is to manage a list of tasks based on user commands.
**Today's Date is: {current_date}**
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
3.  **To SET A DEADLINE:** Find the target task and update its `due_date`. Use today's date ({current_date}) to calculate the correct absolute date in YYYY-MM-DD format.
4.  **To REMOVE/DELETE a task:** Remove the entire task object.
5.  **To UPDATE STATUS:** Find the target task and update its `status` field.
**CRITICAL OUPUT RULE:** Your final output **MUST BE** only the complete, modified, and valid JSON array of task objects. Do not include any other text.
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

def generate_task_suggestions(project_title: str, project_description: str) -> List[str]:
    """
    Uses an LLM to generate a list of standard tasks for a given project.
    """
    if not API_KEY:
        raise ValueError("API_KEY is not configured. Please check your secrets file.")

    prompt = f"""
You are a senior project manager. Your task is to break down a project into a list of high-level, actionable tasks.
Based on the project title and description below, generate a list of 6-7 standard tasks required to complete it.

**Project Title:**
{project_title}

**Project Description:**
{project_description}

**CRITICAL OUTPUT RULE:**
Your output **MUST BE** a valid JSON array of **concise, single-sentence strings**, where each string is a task description.
Example: ["Define API endpoints for user service.", "Set up the initial database schema.", "Implement JWT-based authentication filter."]

**Your Output (JSON Array of Strings only):**
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
        task_list = json.loads(raw_text)
        if isinstance(task_list, list) and all(isinstance(item, str) for item in task_list):
            return task_list
        else:
            raise ValueError("AI did not return a valid list of task strings.")
    except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Could not parse AI model's JSON response: {e}\n\nRaw response was:\n{data}")
