import os
import json
import uuid
import requests
import streamlit as st
from typing import Dict, Any, List
from datetime import datetime

# --- Securely load API key ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("API Key not found. Please create a `.streamlit/secrets.toml` file with your GOOGLE_API_KEY.")
    API_KEY = None

# --- Salary Grade Mapping ---
SALARY_GRADES = { "A": 3500, "B": 3000, "C": 2500, "D": 2200, "E": 2000 }

# --- Model Endpoint ---
MODEL_ENDPOINT = "gemini-2.5-flash" 


def load_employees(filename: str = "employees.json") -> list[dict]:
    """Loads employee data from the data folder."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, '..', 'data', filename)
    if not os.path.isfile(data_path):
        raise FileNotFoundError(f"Could not find employee file at {data_path}. Ensure it is in the 'data' folder.")
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_project(brief: str, eligible_employees: list[dict], user_budget: int) -> Dict[str, Any]:
    """Generates a project title, description, and team."""
    if not API_KEY: raise ValueError("API_KEY is not configured.")
    
    # --- UPGRADED PROMPT for better descriptions ---
    prompt = f"""
You are a Senior Technical Project Manager. Your task is to take a user's high-level brief and expand it into a professional project charter, then assemble a suitable team within budget.

**Your Instructions:**
1.  **Invent a professional and creative Project Title.**
2.  **Expand the User's Brief:** Write a detailed, one-paragraph project **Description**. This description should include the core objective, key technologies, primary features, and important non-functional requirements like scalability or maintainability.
3.  **Assemble a Team:** Select a team from the roster whose combined skills are a good fit for the project and whose salary is as close as possible to the **Target Monthly Budget** without exceeding it.
4.  **Calculate Budget:** Calculate your own `proposed_budget` (Team Salaries + 20% Overhead).

**This is an example of a high-quality Title and Description:**
```
"title": "Project Sentience: Python FastAPI Sentiment Analysis API",
"description": "This project aims to develop a robust and scalable Python API using FastAPI for analyzing and classifying text sentiment. The API will leverage Natural Language Processing (NLP) techniques to accurately determine the sentiment expressed in given text, categorizing it as positive, negative, or neutral. The project will prioritize efficiency, accuracy, and maintainability, adhering to best practices in API design and development. The API will be designed with scalability in mind, capable of handling high volumes of requests and adapting to future enhancements and evolving NLP models. Comprehensive documentation will be provided for developers to easily integrate and utilize the API."
```

---
**CONTEXT FOR THIS REQUEST:**

**User's Project Brief:**
"{brief}"

**Target Monthly Budget (EUR):**
{user_budget:,}

**Roster of Available Employees:**
```json
{json.dumps(eligible_employees, indent=2)}
```

**Salary Grade Values (EUR per month):**
```json
{json.dumps(SALARY_GRADES, indent=2)}
```

**CRITICAL OUTPUT RULE:**
Your output **MUST BE** only a valid JSON object with these exact keys: "title", "description", "team", "proposed_budget".
"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ENDPOINT}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(raw_text)
    except (requests.exceptions.RequestException, KeyError, IndexError, json.JSONDecodeError) as e:
        raise ValueError(f"Could not parse AI model's JSON response: {e}\\n\\nRaw response was:\\n{data if 'data' in locals() else 'No response'}")


def modify_tasks_with_llm(current_tasks: List[Dict[str, Any]], project_team: List[Dict[str, Any]], command: str) -> List[Dict[str, Any]]:
    """Uses an LLM to interpret a user command and modify a list of tasks."""
    if not API_KEY: raise ValueError("API_KEY is not configured.")
    
    prompt = f"""
You are an intelligent project management assistant. Your role is to manage a list of tasks based on user commands.
**Today's Date is: {datetime.now().strftime('%Y-%m-%d')}**
**How to Identify Tasks:**
Users can refer to tasks in two ways:
1.  **By Number:** The user might say "task 1", "assign task 3", etc. The number corresponds to the task's order in the list (starting from 1).
2.  **By Keyword:** The user might say "assign 'API Design' to...". You must find the task whose description best matches the keyword.
**Your Core Capabilities:**
-   **Add Task:** Create a new task object. The `id` must be a new unique string.
-   **Assign Task:** Find the target task and update its `assignee_id`. Match the employee name from the command to the roster.
-   **Set Deadline:** Find the target task and update its `due_date` in YYYY-MM-DD format.
-   **Update Status:** Find the target task and update its `status` field to "To Do", "In Progress", or "Completed".
-   **Delete Task:** Remove the entire task object from the list.
**Example Commands:**
- "add a new task: Final review with stakeholders"
- "assign task 2 to Ravi Kumar"
- "set the deadline for task 4 to next friday"
- "mark 'database setup' as completed"
- "delete task 1"
**Project Team Roster (for finding assignee IDs):**
```json
{json.dumps(project_team, indent=2)}
```
**Current Task List (JSON Array):**
```json
{json.dumps(current_tasks, indent=2)}
```
**User Command:**
"{command}"
**CRITICAL OUPUT RULE:** Your final output **MUST BE** only the complete, modified, and valid JSON array of task objects. Do not include any other text.
**Your Output (JSON Array of Objects only):**
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ENDPOINT}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        modified_list = json.loads(raw_text)
        if isinstance(modified_list, list):
            if not modified_list or (isinstance(modified_list[0], dict) and 'id' in modified_list[0]):
                 return modified_list
        raise ValueError("AI did not return a valid list of task objects.")
    except (requests.exceptions.RequestException, KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Could not parse AI model's JSON response: {e}\n\nRaw response was:\n{data if 'data' in locals() else 'No response'}")


def generate_and_assign_tasks(project_title: str, project_description: str, current_tasks: List[Dict[str, Any]], project_team: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Uses an LLM to generate new tasks and intelligently assign them based on team skills."""
    if not API_KEY: raise ValueError("API_KEY is not configured.")

    start_number = len(current_tasks) + 1

    prompt = f"""
You are a senior project manager. Your task is to intelligently suggest and assign the next logical tasks for a project.
**Project Context:**
- **Title:** {project_title}
- **Description:** {project_description}
**Current Project Team (with skills):**
```json
{json.dumps(project_team, indent=2)}
```
**Existing Tasks on the Board:**
```json
{json.dumps(current_tasks, indent=2)}
```
**Your Instructions:**
1.  **Analyze Context:** Review the project context, the existing tasks, and the skills of the team members.
2.  **Suggest Next Steps:** Based on your analysis, generate 3-4 new, high-level tasks that logically follow the existing ones.
3.  **Number Sequentially:** You MUST number the new tasks starting from **{start_number}**.
4.  **Assign Intelligently:** For each new task you create, you MUST assign it to the most suitable person on the team by setting their `assignee_id`. Base this decision on their listed skills. If no one is a clear fit, you can set `assignee_id` to `null`.
**CRITICAL OUTPUT RULE:**
Your output **MUST BE** a valid JSON array of objects. Each object must have two keys:
- `"description"` (string): The numbered, single-sentence task description.
- `"assignee_id"` (string or null): The ID of the employee best suited for the task.
**Example Output:**
```json
[
  {{
    "description": "{start_number}. Develop User Authentication Endpoints",
    "assignee_id": "emp_2"
  }},
  {{
    "description": "{start_number + 1}. Design the Initial Database Schema",
    "assignee_id": "emp_5"
  }}
]
```
**Your Output (JSON Array of Objects only):**
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ENDPOINT}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        new_tasks = json.loads(raw_text)
        if isinstance(new_tasks, list) and all(isinstance(item, dict) and "description" in item and "assignee_id" in item for item in new_tasks):
            return new_tasks
        else:
            raise ValueError("AI did not return the expected list of task objects.")
    except (requests.exceptions.RequestException, KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Could not parse AI model's JSON response: {e}\n\nRaw response was:\n{data if 'data' in locals() else 'No response'}")


# import os
# import json
# import uuid
# import requests
# import streamlit as st
# from typing import Dict, Any, List
# from datetime import datetime

# # --- Securely load API key ---
# try:
#     API_KEY = st.secrets["GOOGLE_API_KEY"]
# except (KeyError, FileNotFoundError):
#     st.error("API Key not found. Please create a `.streamlit/secrets.toml` file with your GOOGLE_API_KEY.")
#     API_KEY = None

# # --- Salary Grade Mapping ---
# SALARY_GRADES = { "A": 3500, "B": 3000, "C": 2500, "D": 2200, "E": 2000 }

# # --- Model Endpoint ---
# MODEL_ENDPOINT = "gemini-2.5-flash" 


# def load_employees(filename: str = "employees.json") -> list[dict]:
#     """Loads employee data from the data folder."""
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     data_path = os.path.join(script_dir, '..', 'data', filename)
#     if not os.path.isfile(data_path):
#         raise FileNotFoundError(f"Could not find employee file at {data_path}. Ensure it is in the 'data' folder.")
#     with open(data_path, "r", encoding="utf-8") as f:
#         return json.load(f)


# def generate_project(brief: str, eligible_employees: list[dict], user_budget: int) -> Dict[str, Any]:
#     """Generates a project title, description, and team."""
#     if not API_KEY: raise ValueError("API_KEY is not configured.")
#     prompt = f"""
# You are an expert project manager. Your task is to generate a project plan based on a brief and a strict budget.
# **Project Brief:** "{brief}"
# **Target Monthly Budget (EUR):** {user_budget:,}
# **Roster of Available Employees:** {json.dumps(eligible_employees, indent=2)}
# **Salary Grade Values (EUR per month):** {json.dumps(SALARY_GRADES, indent=2)}
# **Your Instructions:**
# 1.  **Create Title & Description:** Invent a creative project title and a detailed description.
# 2.  **Assemble a Team:** Select a team whose combined monthly salary is as close as possible to the **Target Monthly Budget** without exceeding it.
# 3.  **Calculate Budget:** Calculate your own `proposed_budget`. This is the sum of the salaries of the team members you selected, plus a 20% overhead.
# **CRITICAL OUTPUT RULE:** Output **ONLY a valid JSON object** with keys: "title", "description", "team", "proposed_budget".
# """
#     url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ENDPOINT}:generateContent?key={API_KEY}"
#     payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
#     headers = {"Content-Type": "application/json"}
#     try:
#         resp = requests.post(url, headers=headers, json=payload, timeout=60)
#         resp.raise_for_status()
#         data = resp.json()
#         raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
#         return json.loads(raw_text)
#     except (requests.exceptions.RequestException, KeyError, IndexError, json.JSONDecodeError) as e:
#         raise ValueError(f"Could not parse AI model's JSON response: {e}\n\nRaw response was:\n{data if 'data' in locals() else 'No response'}")


# def modify_tasks_with_llm(current_tasks: List[Dict[str, Any]], project_team: List[Dict[str, Any]], command: str) -> List[Dict[str, Any]]:
#     """Uses an LLM to interpret a user command and modify a list of tasks."""
#     if not API_KEY: raise ValueError("API_KEY is not configured.")
    
#     prompt = f"""
# You are an intelligent project management assistant. Your role is to manage a list of tasks based on user commands.
# **Today's Date is: {datetime.now().strftime('%Y-%m-%d')}**
# **How to Identify Tasks:**
# Users can refer to tasks in two ways:
# 1.  **By Number:** The user might say "task 1", "assign task 3", etc. The number corresponds to the task's order in the list (starting from 1).
# 2.  **By Keyword:** The user might say "assign 'API Design' to...". You must find the task whose description best matches the keyword.
# **Your Core Capabilities:**
# -   **Add Task:** Create a new task object. The `id` must be a new unique string.
# -   **Assign Task:** Find the target task and update its `assignee_id`. Match the employee name from the command to the roster.
# -   **Set Deadline:** Find the target task and update its `due_date` in YYYY-MM-DD format.
# -   **Update Status:** Find the target task and update its `status` field to "To Do", "In Progress", or "Completed".
# -   **Delete Task:** Remove the entire task object from the list.
# **Example Commands:**
# - "add a new task: Final review with stakeholders"
# - "assign task 2 to Ravi Kumar"
# - "set the deadline for task 4 to next friday"
# - "mark 'database setup' as completed"
# - "delete task 1"
# **Project Team Roster (for finding assignee IDs):**
# ```json
# {json.dumps(project_team, indent=2)}
# ```
# **Current Task List (JSON Array):**
# ```json
# {json.dumps(current_tasks, indent=2)}
# ```
# **User Command:**
# "{command}"
# **CRITICAL OUPUT RULE:** Your final output **MUST BE** only the complete, modified, and valid JSON array of task objects. Do not include any other text.
# **Your Output (JSON Array of Objects only):**
# """
#     url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ENDPOINT}:generateContent?key={API_KEY}"
#     payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
#     headers = {"Content-Type": "application/json"}
#     try:
#         resp = requests.post(url, headers=headers, json=payload, timeout=90)
#         resp.raise_for_status()
#         data = resp.json()
#         raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
#         modified_list = json.loads(raw_text)
#         if isinstance(modified_list, list):
#             if not modified_list or (isinstance(modified_list[0], dict) and 'id' in modified_list[0]):
#                  return modified_list
#         raise ValueError("AI did not return a valid list of task objects.")
#     except (requests.exceptions.RequestException, KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
#         raise ValueError(f"Could not parse AI model's JSON response: {e}\n\nRaw response was:\n{data if 'data' in locals() else 'No response'}")


# # --- NEW/UPGRADED Function to generate and assign tasks ---
# def generate_and_assign_tasks(project_title: str, project_description: str, current_tasks: List[Dict[str, Any]], project_team: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     """Uses an LLM to generate new tasks and intelligently assign them based on team skills."""
#     if not API_KEY: raise ValueError("API_KEY is not configured.")

#     # Determine the next task number
#     start_number = len(current_tasks) + 1

#     prompt = f"""
# You are a senior project manager. Your task is to intelligently suggest and assign the next logical tasks for a project.

# **Project Context:**
# - **Title:** {project_title}
# - **Description:** {project_description}

# **Current Project Team (with skills):**
# ```json
# {json.dumps(project_team, indent=2)}
# ```

# **Existing Tasks on the Board:**
# ```json
# {json.dumps(current_tasks, indent=2)}
# ```

# **Your Instructions:**
# 1.  **Analyze Context:** Review the project context, the existing tasks, and the skills of the team members.
# 2.  **Suggest Next Steps:** Based on your analysis, generate 5-7 new, high-level tasks that logically follow the existing ones.
# 3.  **Number Sequentially:** You MUST number the new tasks starting from **{start_number}**.
# 4.  **Assign Intelligently:** For each new task you create, you MUST assign it to the most suitable person on the team by setting their `assignee_id`. Base this decision on their listed skills. If no one is a clear fit, you can set `assignee_id` to `null`.

# **CRITICAL OUTPUT RULE:**
# Your output **MUST BE** a valid JSON array of objects. Each object must have two keys:
# - `"description"` (string): The numbered, single-sentence task description.
# - `"assignee_id"` (string or null): The ID of the employee best suited for the task.

# **Example Output:**
# ```json
# [
#   {{
#     "description": "{start_number}. Develop User Authentication Endpoints",
#     "assignee_id": "emp_2"
#   }},
#   {{
#     "description": "{start_number + 1}. Design the Initial Database Schema",
#     "assignee_id": "emp_5"
#   }}
# ]
# ```

# **Your Output (JSON Array of Objects only):**
# """
#     url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ENDPOINT}:generateContent?key={API_KEY}"
#     payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
#     headers = {"Content-Type": "application/json"}
#     try:
#         resp = requests.post(url, headers=headers, json=payload, timeout=90)
#         resp.raise_for_status()
#         data = resp.json()
#         raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
#         new_tasks = json.loads(raw_text)
#         # Validate the output structure
#         if isinstance(new_tasks, list) and all(isinstance(item, dict) and "description" in item and "assignee_id" in item for item in new_tasks):
#             return new_tasks
#         else:
#             raise ValueError("AI did not return the expected list of task objects.")
#     except (requests.exceptions.RequestException, KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
#         raise ValueError(f"Could not parse AI model's JSON response: {e}\n\nRaw response was:\n{data if 'data' in locals() else 'No response'}")

