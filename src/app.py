import streamlit as st
from agent import generate_project, load_employees, modify_tasks_with_llm, generate_task_suggestions
import json
import os
import uuid
from datetime import datetime, date
import base64 # --- ADDED: Required for encoding images ---

# --- Page Configuration ---
st.set_page_config(page_title="A.I. Project Manager", layout="wide")

# --- Define File Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
PROJECT_DATA_FILE = os.path.join(DATA_DIR, 'project_data.json')
LOGO_PATH = os.path.join(DATA_DIR, 'logo.png')
MAKER_LOGO_PATH = os.path.join(DATA_DIR, 'maker.png')
CSS_PATH = os.path.join(SCRIPT_DIR, 'style.css')


# --- Function to load local CSS ---
def local_css(file_name):
    """Loads a local CSS file into the Streamlit app."""
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"CSS file not found: {file_name}. Make sure it's in the 'src' folder.")

# Apply the custom CSS
local_css(CSS_PATH)


# --- NEW: Helper function to encode images for HTML embedding ---
def image_to_base64(path):
    """Converts a local image file to a Base64 string."""
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()


# --- Data Persistence Functions ---
def save_data(data):
    """Saves the current project data to a JSON file."""
    with open(PROJECT_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_data():
    """Loads project data from a JSON file, or returns default if not found."""
    if os.path.exists(PROJECT_DATA_FILE):
        with open(PROJECT_DATA_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return [] # Return empty list if file is corrupted
    return []


# --- App Title & Logo ---
title_col, logo1_col, logo2_col = st.columns([3, 1, 1])
with title_col:
    st.title("🤖 A.I. Project Manager")
with logo1_col:
    if os.path.exists(LOGO_PATH):
        # --- FIX: Using st.markdown with Base64 to apply CSS class ---
        logo_base64 = image_to_base64(LOGO_PATH)
        st.markdown(f'<p class="logo-main"><img src="data:image/png;base64,{logo_base64}"></p>', unsafe_allow_html=True)
    else:
        st.caption("logo.png not found")
with logo2_col:
    if os.path.exists(MAKER_LOGO_PATH):
        # --- FIX: Using st.markdown with Base64 to apply CSS class ---
        maker_logo_base64 = image_to_base64(MAKER_LOGO_PATH)
        st.markdown(f'<p class="logo-maker"><img src="data:image/png;base64,{maker_logo_base64}"></p>', unsafe_allow_html=True)
    else:
        st.caption("maker.png not found")


# --- Salary Grade Mapping ---
SALARY_GRADES = { "A": 3500, "B": 3000, "C": 2500, "D": 2200, "E": 2000 }

# --- Helper Functions ---
def get_employee_project_count():
    count = {emp["id"]: 0 for emp in st.session_state.employees}
    for proj in st.session_state.projects:
        for emp_id in proj.get("team", []):
            if emp_id in count: count[emp_id] += 1
    return count

def get_employee_map():
    return {e["id"]: e for e in st.session_state.employees}

def delete_task(project_id, task_id):
    for project in st.session_state.projects:
        if project['id'] == project_id:
            project['tasks'] = [t for t in project['tasks'] if t.get('id') != task_id]
            save_data(st.session_state.projects)
            st.rerun()
            break

# --- Session State Initialization ---
if "employees" not in st.session_state:
    try:
        st.session_state.employees = load_employees("employees.json")
    except FileNotFoundError as e:
        st.error(f"Fatal Error: {e}")
        st.session_state.employees = []
        st.stop()

if "projects" not in st.session_state:
    st.session_state.projects = load_data()

if "draft_project" not in st.session_state:
    st.session_state.draft_project = None

if "selected_project_id" not in st.session_state:
    st.session_state.selected_project_id = None


# --- Sidebar Navigation ---
tab = st.sidebar.radio("📂 Navigation", ["➕ New Project", "📂 Projects", "💡 AI Task Assistant", "👥 Employees"])
cleaned_tab = tab.split(" ")[-1]

# --- TAB: New Project ---
if cleaned_tab == "Project":
    st.header("➕ Create a New Project")
    brief = st.text_area("Enter your project brief here:", height=150, key="project_brief")
    user_budget = st.number_input("Proposed Budget (EUR)", min_value=0, value=5000, step=100)

    if st.button("✨ Generate Project Draft"):
        if not brief.strip():
            st.warning("Please provide a brief before generating a project.")
        else:
            with st.spinner("🤖 AI Agent is crafting a project..."):
                emp_counts = get_employee_project_count()
                eligible_employees = [e for e in st.session_state.employees if emp_counts.get(e["id"], 0) < 2]
                if not eligible_employees:
                    st.error("No employees are available.")
                else:
                    try:
                        new_project = generate_project(brief, eligible_employees, user_budget)
                        new_project.update({"id": str(uuid.uuid4()), "status": "pending", "tasks": [], "user_budget": user_budget})
                        st.session_state.draft_project = new_project
                    except Exception as e:
                        st.error(f"Failed to generate project: {e}")

    if st.session_state.draft_project:
        draft = st.session_state.draft_project
        st.markdown("---"); st.subheader("📝 Project Draft")
        with st.container(border=True):
            st.markdown(f"#### {draft['title']}")
            st.write(draft["description"])
            emp_map = get_employee_map()
            team_names = [emp_map.get(eid, {"name": "Unknown"})["name"] for eid in draft.get("team", [])]
            st.info(f"**👥 Proposed Team:** {', '.join(team_names) if team_names else 'None'}")
            target_budget = draft.get("user_budget", 0)
            team_cost = sum(SALARY_GRADES.get(emp_map.get(eid, {}).get("salary_grade"), 0) for eid in draft.get("team", []))
            if target_budget > 0:
                percentage = (team_cost / target_budget) * 100
                st.metric(label="Team Salary vs. Your Budget", value=f"€{team_cost:,}", delta=f"€{target_budget - team_cost:,} remaining")
                st.progress(int(min(percentage, 100)), text=f"{percentage:.1f}% of Budget Used")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve Project", use_container_width=True):
                    draft["status"] = "approved"
                    st.session_state.projects.append(draft)
                    save_data(st.session_state.projects)
                    st.session_state.draft_project = None
                    st.success(f"Project '{draft['title']}' approved and saved!")
                    st.rerun()
            with col2:
                if st.button("❌ Discard Draft", use_container_width=True):
                    st.session_state.draft_project = None; st.rerun()

# --- TAB: Projects ---
elif cleaned_tab == "Projects":
    st.header("📂 Projects Dashboard")
    if not st.session_state.projects:
        st.info("No projects created yet.")
    else:
        master_col, detail_col = st.columns([1, 3])
        emp_map = get_employee_map()
        with master_col:
            st.subheader("Projects")
            for proj in st.session_state.projects:
                if st.button(proj['title'], key=f"select_{proj['id']}", use_container_width=True):
                    st.session_state.selected_project_id = proj['id']
        with detail_col:
            if not st.session_state.selected_project_id:
                st.info("⬅️ Select a project to see its details.")
            else:
                proj = next((p for p in st.session_state.projects if p['id'] == st.session_state.selected_project_id), None)
                proj_idx = next((i for i, p in enumerate(st.session_state.projects) if p['id'] == st.session_state.selected_project_id), None)
                if proj and proj_idx is not None:
                    with st.container(border=True):
                        p_title_col, p_close_col = st.columns([4, 1])
                        with p_title_col: st.markdown(f"### {proj['title']}")
                        with p_close_col:
                            if st.button("Close ✖️", key=f"close_{proj['id']}", use_container_width=True):
                                st.session_state.selected_project_id = None; st.rerun()
                        st.markdown(f"*{proj.get('description', '')}*"); st.markdown("---")
                        if st.button("✨ Suggest and Add Tasks", key=f"suggest_tasks_{proj['id']}"):
                            with st.spinner("AI is generating tasks..."):
                                try:
                                    suggestions = generate_task_suggestions(proj['title'], proj.get('description', ''))
                                    if suggestions:
                                        for desc in suggestions:
                                            st.session_state.projects[proj_idx]['tasks'].append({"id": str(uuid.uuid4()), "description": desc, "status": "To Do", "assignee_id": None, "due_date": None})
                                        save_data(st.session_state.projects)
                                        st.success(f"AI added {len(suggestions)} new tasks.")
                                        st.rerun()
                                except Exception as e: st.error(f"Failed to get suggestions: {e}")
                        st.markdown("---"); st.subheader("📋 Task Board")
                        
                        def render_compact_task_card(task, project_id, proj_idx):
                            with st.container(border=True):
                                assignee_name = emp_map.get(task.get('assignee_id'), {}).get('name', 'Unassigned')
                                due_date_obj = datetime.strptime(task['due_date'], '%Y-%m-%d').date() if task.get('due_date') else None
                                st.markdown(f"**{task['description']}**")
                                st.caption(f"👤 {assignee_name} | 📅 {due_date_obj.strftime('%d %b') if due_date_obj else 'No due date'}")
                                with st.expander("Edit ✏️"):
                                    project_team_members = [emp_map[eid] for eid in proj.get("team", []) if eid in emp_map]
                                    assignee_options = {emp['id']: emp['name'] for emp in project_team_members}; assignee_options['unassigned'] = "Unassigned"
                                    current_assignee_id = task.get('assignee_id', 'unassigned')
                                    if current_assignee_id not in assignee_options: current_assignee_id = 'unassigned'
                                    new_assignee_id = st.selectbox("Assign to:", options=list(assignee_options.keys()), index=list(assignee_options.keys()).index(current_assignee_id), format_func=lambda x: assignee_options[x], key=f"assign_{project_id}_{task['id']}")
                                    if new_assignee_id != current_assignee_id:
                                        task['assignee_id'] = new_assignee_id if new_assignee_id != 'unassigned' else None; save_data(st.session_state.projects); st.rerun()
                                    new_due_date = st.date_input("Due by:", value=due_date_obj, key=f"date_{project_id}_{task['id']}", format="YYYY-MM-DD")
                                    if (new_due_date.strftime('%Y-%m-%d') if new_due_date else None) != task.get('due_date'):
                                        task['due_date'] = new_due_date.strftime('%Y-%m-%d') if new_due_date else None; save_data(st.session_state.projects); st.rerun()
                                    s_col1, s_col2, s_col3 = st.columns(3)
                                    if s_col1.button("To Do", key=f"todo_{project_id}_{task['id']}", use_container_width=True, disabled=(task['status']=='To Do')): task['status'] = 'To Do'; save_data(st.session_state.projects); st.rerun()
                                    if s_col2.button("In Progress", key=f"prog_{project_id}_{task['id']}", use_container_width=True, disabled=(task['status']=='In Progress')): task['status'] = 'In Progress'; save_data(st.session_state.projects); st.rerun()
                                    if s_col3.button("Completed", key=f"done_{project_id}_{task['id']}", use_container_width=True, disabled=(task['status']=='Completed')): task['status'] = 'Completed'; save_data(st.session_state.projects); st.rerun()
                                    if st.button("Delete Task 🗑️", key=f"delete_{project_id}_{task['id']}", use_container_width=True): delete_task(project_id, task['id'])
                        
                        k_col1, k_col2, k_col3 = st.columns(3)
                        with k_col1:
                            st.markdown("#### 📥 To Do")
                            for t in [t for t in proj.get('tasks', []) if t['status'] == 'To Do']:
                                render_compact_task_card(t, proj['id'], proj_idx)
                        with k_col2:
                            st.markdown("#### ⚙️ In Progress")
                            for t in [t for t in proj.get('tasks', []) if t['status'] == 'In Progress']:
                                render_compact_task_card(t, proj['id'], proj_idx)
                        with k_col3:
                            st.markdown("#### ✔️ Completed")
                            for t in [t for t in proj.get('tasks', []) if t['status'] == 'Completed']:
                                render_compact_task_card(t, proj['id'], proj_idx)
                        
                        with st.expander("⚙️ Project Settings"):
                            st.markdown("**Modify Team:**")
                            selected_ids = st.multiselect("Team", options=[e["id"] for e in st.session_state.employees], default=proj.get("team", []), format_func=lambda x: emp_map[x]["name"], key=f"emp_select_{proj['id']}", label_visibility="collapsed")
                            b_col1, b_col2 = st.columns([3, 1])
                            if b_col1.button("💾 Save Team", key=f"save_team_{proj['id']}", use_container_width=True):
                                st.session_state.projects[proj_idx]["team"] = selected_ids; save_data(st.session_state.projects); st.success("Team updated."); st.rerun()
                            if b_col2.button("🗑️ Delete Project", key=f"delete_proj_{proj['id']}", use_container_width=True, type="primary"):
                                st.session_state.projects.pop(proj_idx); st.session_state.selected_project_id = None; save_data(st.session_state.projects); st.warning("Project deleted."); st.rerun()

# --- TAB: AI Task Assistant ---
elif cleaned_tab == "Assistant":
    st.header("💡 AI Task Assistant")
    emp_map = get_employee_map()
    if not st.session_state.projects:
        st.info("No projects available.")
    else:
        project_options = {p['id']: p['title'] for p in st.session_state.projects}
        selected_proj_id = st.selectbox("Select a project to modify", options=list(project_options.keys()), format_func=lambda x: project_options[x])
        command = st.text_input("Enter a command (e.g., 'add task: Client meeting due tomorrow')", key="ai_task_command")
        if st.button("⚡ Execute Command"):
            if selected_proj_id and command:
                with st.spinner("AI is processing..."):
                    try:
                        proj_index = next((i for i, p in enumerate(st.session_state.projects) if p['id'] == selected_proj_id), None)
                        if proj_index is not None:
                            current_tasks = st.session_state.projects[proj_index].get('tasks', [])
                            proj_team_details = [emp_map[eid] for eid in st.session_state.projects[proj_index].get('team', []) if eid in emp_map]
                            st.session_state.projects[proj_index]['tasks'] = modify_tasks_with_llm(current_tasks, proj_team_details, command)
                            save_data(st.session_state.projects)
                            st.success("Tasks updated!")
                    except Exception as e: st.error(f"Failed to modify tasks: {e}")

# --- TAB: Employees ---
elif cleaned_tab == "Employees":
    st.header("👥 Employee Assignments")
    if not st.session_state.employees:
        st.warning("No employee data available.")
    else:
        emp_counts = get_employee_project_count()
        assigned = sorted([e for e in st.session_state.employees if emp_counts.get(e["id"], 0) > 0], key=lambda x: x['name'])
        unassigned = sorted([e for e in st.session_state.employees if emp_counts.get(e["id"], 0) == 0], key=lambda x: x['name'])
        st.subheader(f"✅ Assigned Employees ({len(assigned)})")
        if not assigned: st.info("No employees are currently assigned.")
        else:
            for emp in assigned: st.markdown(f"- **{emp['name']}** (Skills: *{emp['skills']}*) — Assigned to **{emp_counts[emp['id']]}** project(s).")
        st.markdown("---")
        st.subheader(f"⚪ Unassigned Employees ({len(unassigned)})")
        if not unassigned: st.info("All employees are assigned to at least one project.")
        else:
            for emp in unassigned: st.markdown(f"- **{emp['name']}** (Skills: *{emp['skills']}*)")


# import streamlit as st
# from agent import generate_project, load_employees, modify_tasks_with_llm, generate_task_suggestions
# import json
# import os
# import uuid
# from datetime import datetime, date

# # --- Page Configuration ---
# st.set_page_config(page_title="A.I. Project Manager", layout="wide")

# # --- Define File Paths ---
# SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
# PROJECT_DATA_FILE = os.path.join(DATA_DIR, 'project_data.json')
# LOGO_PATH = os.path.join(DATA_DIR, 'logo.png')
# MAKER_LOGO_PATH = os.path.join(DATA_DIR, 'maker.png')
# CSS_PATH = os.path.join(SCRIPT_DIR, 'style.css')


# # --- Function to load local CSS ---
# def local_css(file_name):
#     """Loads a local CSS file into the Streamlit app."""
#     try:
#         with open(file_name) as f:
#             st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
#     except FileNotFoundError:
#         st.error(f"CSS file not found: {file_name}. Make sure it's in the 'src' folder.")

# # Apply the custom CSS
# local_css(CSS_PATH)


# # --- Data Persistence Functions ---
# def save_data(data):
#     """Saves the current project data to a JSON file."""
#     with open(PROJECT_DATA_FILE, 'w') as f:
#         json.dump(data, f, indent=4)

# def load_data():
#     """Loads project data from a JSON file, or returns default if not found."""
#     if os.path.exists(PROJECT_DATA_FILE):
#         with open(PROJECT_DATA_FILE, 'r') as f:
#             try:
#                 return json.load(f)
#             except json.JSONDecodeError:
#                 return [] # Return empty list if file is corrupted
#     return []


# # --- App Title & Logo ---
# title_col, logo1_col, logo2_col = st.columns([3, 1, 1])
# with title_col:
#     st.title("🤖 A.I. Project Manager")
# with logo1_col:
#     if os.path.exists(LOGO_PATH):
#         st.image(LOGO_PATH, width=150)
#     else:
#         st.caption("logo.png not found in 'data' folder")
# with logo2_col:
#     if os.path.exists(MAKER_LOGO_PATH):
#         st.image(MAKER_LOGO_PATH, width=150)
#     else:
#         st.caption("maker.png not found in 'data' folder")


# # --- Salary Grade Mapping ---
# SALARY_GRADES = { "A": 3500, "B": 3000, "C": 2500, "D": 2200, "E": 2000 }

# # --- Helper Functions ---
# def get_employee_project_count():
#     count = {emp["id"]: 0 for emp in st.session_state.employees}
#     for proj in st.session_state.projects:
#         for emp_id in proj.get("team", []):
#             if emp_id in count: count[emp_id] += 1
#     return count

# def get_employee_map():
#     return {e["id"]: e for e in st.session_state.employees}

# def delete_task(project_id, task_id):
#     for project in st.session_state.projects:
#         if project['id'] == project_id:
#             project['tasks'] = [t for t in project['tasks'] if t.get('id') != task_id]
#             save_data(st.session_state.projects)
#             st.rerun()
#             break

# # --- Session State Initialization ---
# if "employees" not in st.session_state:
#     try:
#         st.session_state.employees = load_employees("employees.json")
#     except FileNotFoundError as e:
#         st.error(f"Fatal Error: {e}")
#         st.session_state.employees = []
#         st.stop()

# if "projects" not in st.session_state:
#     st.session_state.projects = load_data()

# if "draft_project" not in st.session_state:
#     st.session_state.draft_project = None

# if "selected_project_id" not in st.session_state:
#     st.session_state.selected_project_id = None


# # --- Sidebar Navigation ---
# tab = st.sidebar.radio("📂 Navigation", ["➕ New Project", "📂 Projects", "💡 AI Task Assistant", "👥 Employees"])
# cleaned_tab = tab.split(" ")[-1]

# # --- TAB: New Project ---
# if cleaned_tab == "Project":
#     st.header("➕ Create a New Project")
#     brief = st.text_area("Enter your project brief here:", height=150, key="project_brief")
#     user_budget = st.number_input("Proposed Budget (EUR)", min_value=0, value=5000, step=100)

#     if st.button("✨ Generate Project Draft"):
#         if not brief.strip():
#             st.warning("Please provide a brief before generating a project.")
#         else:
#             with st.spinner("🤖 AI Agent is crafting a project..."):
#                 emp_counts = get_employee_project_count()
#                 eligible_employees = [e for e in st.session_state.employees if emp_counts.get(e["id"], 0) < 2]
#                 if not eligible_employees:
#                     st.error("No employees are available.")
#                 else:
#                     try:
#                         new_project = generate_project(brief, eligible_employees, user_budget)
#                         new_project.update({"id": str(uuid.uuid4()), "status": "pending", "tasks": [], "user_budget": user_budget})
#                         st.session_state.draft_project = new_project
#                     except Exception as e:
#                         st.error(f"Failed to generate project: {e}")

#     if st.session_state.draft_project:
#         draft = st.session_state.draft_project
#         st.markdown("---"); st.subheader("📝 Project Draft")
#         with st.container(border=True):
#             st.markdown(f"#### {draft['title']}")
#             st.write(draft["description"])
#             emp_map = get_employee_map()
#             team_names = [emp_map.get(eid, {"name": "Unknown"})["name"] for eid in draft.get("team", [])]
#             st.info(f"**👥 Proposed Team:** {', '.join(team_names) if team_names else 'None'}")
#             target_budget = draft.get("user_budget", 0)
#             team_cost = sum(SALARY_GRADES.get(emp_map.get(eid, {}).get("salary_grade"), 0) for eid in draft.get("team", []))
#             if target_budget > 0:
#                 percentage = (team_cost / target_budget) * 100
#                 st.metric(label="Team Salary vs. Your Budget", value=f"€{team_cost:,}", delta=f"€{target_budget - team_cost:,} remaining")
#                 st.progress(int(min(percentage, 100)), text=f"{percentage:.1f}% of Budget Used")
#             col1, col2 = st.columns(2)
#             with col1:
#                 if st.button("✅ Approve Project", use_container_width=True):
#                     draft["status"] = "approved"
#                     st.session_state.projects.append(draft)
#                     save_data(st.session_state.projects)
#                     st.session_state.draft_project = None
#                     st.success(f"Project '{draft['title']}' approved and saved!")
#                     st.rerun()
#             with col2:
#                 if st.button("❌ Discard Draft", use_container_width=True):
#                     st.session_state.draft_project = None; st.rerun()

# # --- TAB: Projects ---
# elif cleaned_tab == "Projects":
#     st.header("📂 Projects Dashboard")
#     if not st.session_state.projects:
#         st.info("No projects created yet.")
#     else:
#         master_col, detail_col = st.columns([1, 3])
#         emp_map = get_employee_map()
#         with master_col:
#             st.subheader("Projects")
#             for proj in st.session_state.projects:
#                 if st.button(proj['title'], key=f"select_{proj['id']}", use_container_width=True):
#                     st.session_state.selected_project_id = proj['id']
#         with detail_col:
#             if not st.session_state.selected_project_id:
#                 st.info("⬅️ Select a project to see its details.")
#             else:
#                 proj = next((p for p in st.session_state.projects if p['id'] == st.session_state.selected_project_id), None)
#                 proj_idx = next((i for i, p in enumerate(st.session_state.projects) if p['id'] == st.session_state.selected_project_id), None)
#                 if proj and proj_idx is not None:
#                     with st.container(border=True):
#                         p_title_col, p_close_col = st.columns([4, 1])
#                         with p_title_col: st.markdown(f"### {proj['title']}")
#                         with p_close_col:
#                             if st.button("Close ✖️", key=f"close_{proj['id']}", use_container_width=True):
#                                 st.session_state.selected_project_id = None; st.rerun()
#                         st.markdown(f"*{proj.get('description', '')}*"); st.markdown("---")
#                         if st.button("✨ Suggest and Add Tasks", key=f"suggest_tasks_{proj['id']}"):
#                             with st.spinner("AI is generating tasks..."):
#                                 try:
#                                     suggestions = generate_task_suggestions(proj['title'], proj.get('description', ''))
#                                     if suggestions:
#                                         for desc in suggestions:
#                                             st.session_state.projects[proj_idx]['tasks'].append({"id": str(uuid.uuid4()), "description": desc, "status": "To Do", "assignee_id": None, "due_date": None})
#                                         save_data(st.session_state.projects)
#                                         st.success(f"AI added {len(suggestions)} new tasks.")
#                                         st.rerun()
#                                 except Exception as e: st.error(f"Failed to get suggestions: {e}")
#                         st.markdown("---"); st.subheader("📋 Task Board")
                        
#                         def render_compact_task_card(task, project_id, proj_idx):
#                             with st.container(border=True):
#                                 assignee_name = emp_map.get(task.get('assignee_id'), {}).get('name', 'Unassigned')
#                                 due_date_obj = datetime.strptime(task['due_date'], '%Y-%m-%d').date() if task.get('due_date') else None
#                                 st.markdown(f"**{task['description']}**")
#                                 st.caption(f"👤 {assignee_name} | 📅 {due_date_obj.strftime('%d %b') if due_date_obj else 'No due date'}")
#                                 with st.expander("Edit ✏️"):
#                                     project_team_members = [emp_map[eid] for eid in proj.get("team", []) if eid in emp_map]
#                                     assignee_options = {emp['id']: emp['name'] for emp in project_team_members}; assignee_options['unassigned'] = "Unassigned"
#                                     current_assignee_id = task.get('assignee_id', 'unassigned')
#                                     if current_assignee_id not in assignee_options: current_assignee_id = 'unassigned'
#                                     new_assignee_id = st.selectbox("Assign to:", options=list(assignee_options.keys()), index=list(assignee_options.keys()).index(current_assignee_id), format_func=lambda x: assignee_options[x], key=f"assign_{project_id}_{task['id']}")
#                                     if new_assignee_id != current_assignee_id:
#                                         task['assignee_id'] = new_assignee_id if new_assignee_id != 'unassigned' else None; save_data(st.session_state.projects); st.rerun()
#                                     new_due_date = st.date_input("Due by:", value=due_date_obj, key=f"date_{project_id}_{task['id']}", format="YYYY-MM-DD")
#                                     if (new_due_date.strftime('%Y-%m-%d') if new_due_date else None) != task.get('due_date'):
#                                         task['due_date'] = new_due_date.strftime('%Y-%m-%d') if new_due_date else None; save_data(st.session_state.projects); st.rerun()
#                                     s_col1, s_col2, s_col3 = st.columns(3)
#                                     if s_col1.button("To Do", key=f"todo_{project_id}_{task['id']}", use_container_width=True, disabled=(task['status']=='To Do')): task['status'] = 'To Do'; save_data(st.session_state.projects); st.rerun()
#                                     if s_col2.button("In Progress", key=f"prog_{project_id}_{task['id']}", use_container_width=True, disabled=(task['status']=='In Progress')): task['status'] = 'In Progress'; save_data(st.session_state.projects); st.rerun()
#                                     if s_col3.button("Completed", key=f"done_{project_id}_{task['id']}", use_container_width=True, disabled=(task['status']=='Completed')): task['status'] = 'Completed'; save_data(st.session_state.projects); st.rerun()
#                                     if st.button("Delete Task 🗑️", key=f"delete_{project_id}_{task['id']}", use_container_width=True): delete_task(project_id, task['id'])
                        
#                         k_col1, k_col2, k_col3 = st.columns(3)
#                         with k_col1:
#                             st.markdown("#### 📥 To Do")
#                             # --- FIX: Changed from list comprehension to a for loop ---
#                             for t in [t for t in proj.get('tasks', []) if t['status'] == 'To Do']:
#                                 render_compact_task_card(t, proj['id'], proj_idx)
#                         with k_col2:
#                             st.markdown("#### ⚙️ In Progress")
#                             # --- FIX: Changed from list comprehension to a for loop ---
#                             for t in [t for t in proj.get('tasks', []) if t['status'] == 'In Progress']:
#                                 render_compact_task_card(t, proj['id'], proj_idx)
#                         with k_col3:
#                             st.markdown("#### ✔️ Completed")
#                             # --- FIX: Changed from list comprehension to a for loop ---
#                             for t in [t for t in proj.get('tasks', []) if t['status'] == 'Completed']:
#                                 render_compact_task_card(t, proj['id'], proj_idx)
                        
#                         with st.expander("⚙️ Project Settings"):
#                             st.markdown("**Modify Team:**")
#                             selected_ids = st.multiselect("Team", options=[e["id"] for e in st.session_state.employees], default=proj.get("team", []), format_func=lambda x: emp_map[x]["name"], key=f"emp_select_{proj['id']}", label_visibility="collapsed")
#                             b_col1, b_col2 = st.columns([3, 1])
#                             if b_col1.button("💾 Save Team", key=f"save_team_{proj['id']}", use_container_width=True):
#                                 st.session_state.projects[proj_idx]["team"] = selected_ids; save_data(st.session_state.projects); st.success("Team updated."); st.rerun()
#                             if b_col2.button("🗑️ Delete Project", key=f"delete_proj_{proj['id']}", use_container_width=True, type="primary"):
#                                 st.session_state.projects.pop(proj_idx); st.session_state.selected_project_id = None; save_data(st.session_state.projects); st.warning("Project deleted."); st.rerun()

# # --- TAB: AI Task Assistant ---
# elif cleaned_tab == "Assistant":
#     st.header("💡 AI Task Assistant")
#     emp_map = get_employee_map()
#     if not st.session_state.projects:
#         st.info("No projects available.")
#     else:
#         project_options = {p['id']: p['title'] for p in st.session_state.projects}
#         selected_proj_id = st.selectbox("Select a project to modify", options=list(project_options.keys()), format_func=lambda x: project_options[x])
#         command = st.text_input("Enter a command (e.g., 'add task: Client meeting due tomorrow')", key="ai_task_command")
#         if st.button("⚡ Execute Command"):
#             if selected_proj_id and command:
#                 with st.spinner("AI is processing..."):
#                     try:
#                         proj_index = next((i for i, p in enumerate(st.session_state.projects) if p['id'] == selected_proj_id), None)
#                         if proj_index is not None:
#                             current_tasks = st.session_state.projects[proj_index].get('tasks', [])
#                             proj_team_details = [emp_map[eid] for eid in st.session_state.projects[proj_index].get('team', []) if eid in emp_map]
#                             st.session_state.projects[proj_index]['tasks'] = modify_tasks_with_llm(current_tasks, proj_team_details, command)
#                             save_data(st.session_state.projects)
#                             st.success("Tasks updated!")
#                     except Exception as e: st.error(f"Failed to modify tasks: {e}")

# # --- TAB: Employees ---
# elif cleaned_tab == "Employees":
#     st.header("👥 Employee Assignments")
#     if not st.session_state.employees:
#         st.warning("No employee data available.")
#     else:
#         emp_counts = get_employee_project_count()
#         assigned = sorted([e for e in st.session_state.employees if emp_counts.get(e["id"], 0) > 0], key=lambda x: x['name'])
#         unassigned = sorted([e for e in st.session_state.employees if emp_counts.get(e["id"], 0) == 0], key=lambda x: x['name'])
#         st.subheader(f"✅ Assigned Employees ({len(assigned)})")
#         if not assigned: st.info("No employees are currently assigned.")
#         else:
#             for emp in assigned: st.markdown(f"- **{emp['name']}** (Skills: *{emp['skills']}*) — Assigned to **{emp_counts[emp['id']]}** project(s).")
#         st.markdown("---")
#         st.subheader(f"⚪ Unassigned Employees ({len(unassigned)})")
#         if not unassigned: st.info("All employees are assigned to at least one project.")
#         else:
#             for emp in unassigned: st.markdown(f"- **{emp['name']}** (Skills: *{emp['skills']}*)")
