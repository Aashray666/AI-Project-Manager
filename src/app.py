import streamlit as st
from streamlit.components.v1 import html
from agent import generate_project, load_employees, modify_tasks_with_llm, generate_and_assign_tasks
import json
import os
import uuid
from datetime import datetime, date
import base64

# --- Page Configuration ---
st.set_page_config(page_title="Project Manager Assistant", layout="wide")

# --- Session State Initialization for Theme ---
if "theme" not in st.session_state:
    st.session_state.theme = "dark" # Default to light theme

# --- Define File Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
PROJECT_DATA_FILE = os.path.join(DATA_DIR, 'project_data.json')
EMPLOYEE_DATA_FILE = os.path.join(DATA_DIR, 'employees.json')
LOGO_PATH = os.path.join(DATA_DIR, 'logo.png')
MAKER_LOGO_PATH = os.path.join(DATA_DIR, 'maker.png')
CSS_PATH = os.path.join(SCRIPT_DIR, 'style.css')


# --- Function to load local CSS ---
def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"CSS file not found: {file_name}. Make sure 'style.css' is in the 'src' folder.")

# Apply the unified stylesheet
local_css(CSS_PATH)


# --- JavaScript to apply the theme class to the body ---
def apply_theme():
    """Injects JS to add/remove the dark-mode class from the body tag."""
    js = f"""
    <script>
        function applyTheme() {{
            const body = parent.document.querySelector('body');
            if (body) {{
                body.classList.remove('light-mode', 'dark-mode');
                body.classList.add('{st.session_state.theme}-mode');
            }}
        }}
        applyTheme();

        const observer = new MutationObserver(mutations => {{
            mutations.forEach(mutation => {{
                if (mutation.type === 'childList') {{
                    applyTheme();
                }}
            }});
        }});

        observer.observe(parent.document.body, {{ childList: true, subtree: true }});
    </script>
    """
    html(js, height=0)

# Apply the theme on every run
apply_theme()


# --- Helper function to encode images ---
def image_to_base64(path):
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()


# --- Data Persistence Functions ---
def save_project_data(data):
    with open(PROJECT_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_project_data():
    if os.path.exists(PROJECT_DATA_FILE):
        with open(PROJECT_DATA_FILE, 'r') as f:
            try: return json.load(f)
            except json.JSONDecodeError: return []
    return []


# --- App Title & Logo ---
title_col, logo1_col, logo2_col = st.columns([3, 1, 1])
with title_col:
    st.title("🤖 Project Manager Assistant")
with logo1_col:
    if os.path.exists(LOGO_PATH):
        logo_base64 = image_to_base64(LOGO_PATH)
        st.markdown(f'<p class="logo-main"><img src="data:image/png;base64,{logo_base64}"></p>', unsafe_allow_html=True)
with logo2_col:
    if os.path.exists(MAKER_LOGO_PATH):
        maker_logo_base64 = image_to_base64(MAKER_LOGO_PATH)
        st.markdown(f'<p class="logo-maker"><img src="data:image/png;base64,{maker_logo_base64}"></p>', unsafe_allow_html=True)


# --- Salary Grade Mapping ---
SALARY_GRADES = { "A": 3500, "B": 3000, "C": 2500, "D": 2200, "E": 2000 }

# --- Helper Functions ---
def get_employee_project_count():
    count = {emp["id"]: 0 for emp in st.session_state.employees}
    for proj in st.session_state.projects:
        for item in proj.get("team", []):
            emp_id = item.get('id') if isinstance(item, dict) else item
            if emp_id in count:
                count[emp_id] += 1
    return count

def get_employee_map():
    return {e["id"]: e for e in st.session_state.employees}

def delete_task(project_id, task_id):
    for project in st.session_state.projects:
        if project['id'] == project_id:
            project['tasks'] = [t for t in project['tasks'] if t.get('id') != task_id]
            save_project_data(st.session_state.projects)
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
    st.session_state.projects = load_project_data()

if "draft_project" not in st.session_state: st.session_state.draft_project = None
if "selected_project_id" not in st.session_state: st.session_state.selected_project_id = None
if "selected_employee_id" not in st.session_state: st.session_state.selected_employee_id = None
if "active_tab" not in st.session_state: st.session_state.active_tab = "➕ New Project"


# --- Sidebar Navigation ---
TABS = ["➕ New Project", "📂 Projects", "💡 AI Task Assistant", "👥 Employees"]
st.sidebar.radio(
    "📂 Navigation", TABS, 
    key="navigation_radio",
    on_change=lambda: st.session_state.update(active_tab=st.session_state.navigation_radio)
)

# --- Theme Toggle Logic ---
def toggle_theme():
    st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"

st.sidebar.markdown("---")
is_dark_mode = st.session_state.theme == "dark"
st.sidebar.toggle("🌙 Dark Mode", value=is_dark_mode, on_change=toggle_theme)


def go_to_project(project_id):
    st.session_state.selected_project_id = project_id
    st.session_state.active_tab = "📂 Projects"
    st.session_state.navigation_radio = "📂 Projects" 

cleaned_tab = st.session_state.active_tab.split(" ")[-1]

# --- TAB: New Project ---
if cleaned_tab == "Project":
    st.header("➕ Create a New Project")
    brief = st.text_area("Enter your project brief here:", height=150, key="project_brief")
    user_budget = st.number_input("Proposed Budget (€)", min_value=0, value=5000, step=100)

    if st.button("✨ Generate Project Draft"):
        if not brief.strip(): st.warning("Please provide a brief.")
        else:
            with st.spinner("🤖 AI Agent is crafting a project..."):
                emp_counts = get_employee_project_count()
                eligible_employees = [e for e in st.session_state.employees if emp_counts.get(e["id"], 0) < 2]
                if not eligible_employees: st.error("No employees are available.")
                else:
                    try:
                        new_project = generate_project(brief, eligible_employees, user_budget)
                        new_project.update({"id": str(uuid.uuid4()), "status": "pending", "tasks": [], "user_budget": user_budget})
                        st.session_state.draft_project = new_project
                    except Exception as e: st.error(f"Failed to generate project: {e}")

    if st.session_state.draft_project:
        draft = st.session_state.draft_project
        st.markdown("---"); st.subheader("📝 Project Draft")
        with st.container(border=True):
            st.markdown(f"#### {draft['title']}")
            st.write(draft["description"])
            emp_map = get_employee_map()
            team_ids = [item.get('id') if isinstance(item, dict) else item for item in draft.get("team", [])]
            team_names = [emp_map.get(emp_id, {"name": "Unknown"})["name"] for emp_id in team_ids]
            st.info(f"**👥 Proposed Team:** {', '.join(team_names) if team_names else 'None'}")
            target_budget = draft.get("user_budget", 0)
            team_cost = sum(SALARY_GRADES.get(emp_map.get(eid, {}).get("salary_grade"), 0) for eid in team_ids)
            if target_budget > 0:
                percentage = (team_cost / target_budget) * 100
                
                # Display color-coded warnings
                if percentage > 100:
                    st.error(f"**Over Budget:** Team salary (€{team_cost:,}) exceeds your target budget of €{target_budget:,}.")
                elif 90 <= percentage <= 100:
                    st.warning(f"**Nearing Budget:** Team salary (€{team_cost:,}) is close to your target budget of €{target_budget:,}.")
                else:
                    st.success(f"**Within Budget:** Team salary (€{team_cost:,}) is well within your target budget of €{target_budget:,}.")

                # Display the progress bar
                st.progress(int(min(percentage, 100)))
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve Project", use_container_width=True):
                    draft["status"] = "approved"
                    st.session_state.projects.append(draft)
                    save_project_data(st.session_state.projects)
                    st.session_state.draft_project = None
                    st.success(f"Project '{draft['title']}' approved and saved!")
                    st.rerun()
            with col2:
                if st.button("❌ Discard Draft", use_container_width=True):
                    st.session_state.draft_project = None; st.rerun()

# --- TAB: Projects ---
elif cleaned_tab == "Projects":
    st.header("📂 Projects Dashboard")
    if not st.session_state.projects: st.info("No projects created yet.")
    else:
        master_col, detail_col = st.columns([1, 3])
        emp_map = get_employee_map()
        with master_col:
            st.subheader("Projects")
            for proj in st.session_state.projects:
                if st.button(proj['title'], key=f"select_{proj['id']}", use_container_width=True):
                    st.session_state.selected_project_id = proj['id']
        with detail_col:
            if not st.session_state.selected_project_id: st.info("⬅️ Select a project to see its details.")
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
                        suggester_col, team_col = st.columns(2)
                        with suggester_col:
                            st.markdown("**AI Task Suggester**")
                            if st.button("✨ Suggest & Auto-Assign Tasks", key=f"suggest_tasks_{proj['id']}"):
                                with st.spinner("AI is generating and assigning tasks..."):
                                    try:
                                        current_tasks = proj.get('tasks', [])
                                        team_ids = [item.get('id') if isinstance(item, dict) else item for item in proj.get("team", [])]
                                        team_details = [emp_map[eid] for eid in team_ids if eid in emp_map]
                                        newly_suggested_tasks = generate_and_assign_tasks(
                                            project_title=proj['title'],
                                            project_description=proj.get('description', ''),
                                            current_tasks=current_tasks,
                                            project_team=team_details
                                        )
                                        if newly_suggested_tasks:
                                            for task_data in newly_suggested_tasks:
                                                new_task = {"id": str(uuid.uuid4()), "description": task_data['description'], "status": "To Do", "assignee_id": task_data['assignee_id'], "due_date": None}
                                                st.session_state.projects[proj_idx]['tasks'].append(new_task)
                                            save_project_data(st.session_state.projects)
                                            st.success(f"AI added and assigned {len(newly_suggested_tasks)} new tasks.")
                                            st.rerun()
                                    except Exception as e: st.error(f"Failed to get suggestions: {e}")
                        with team_col:
                            st.markdown("**Current Team**")
                            team_ids = [item.get('id') if isinstance(item, dict) else item for item in proj.get("team", [])]
                            team_names = [emp_map.get(emp_id, {"name": "Unknown"})["name"] for emp_id in team_ids]
                            if team_names: st.info(f"👥 {', '.join(team_names)}")
                            else: st.warning("No team assigned.")
                        st.markdown("---"); st.subheader("📋 Task Board")
                        def render_compact_task_card(task, project_id, proj_idx):
                            with st.container(border=True):
                                assignee_name = emp_map.get(task.get('assignee_id'), {}).get('name', 'Unassigned')
                                due_date_obj = datetime.strptime(task['due_date'], '%Y-%m-%d').date() if task.get('due_date') else None
                                st.markdown(f"**{task['description']}**")
                                st.caption(f"👤 {assignee_name} | 📅 {due_date_obj.strftime('%d %b') if due_date_obj else 'No due date'}")
                                st.markdown("---")
                                if task['status'] == 'To Do':
                                    if st.button("Start Progress ▶️", key=f"start_{project_id}_{task['id']}", use_container_width=True):
                                        task['status'] = 'In Progress'; save_project_data(st.session_state.projects); st.rerun()
                                elif task['status'] == 'In Progress':
                                    b1, b2 = st.columns(2)
                                    if b1.button("⏪ Send Back", key=f"send_back_{project_id}_{task['id']}", use_container_width=True):
                                        task['status'] = 'To Do'; save_project_data(st.session_state.projects); st.rerun()
                                    if b2.button("Complete ✔️", key=f"complete_{project_id}_{task['id']}", use_container_width=True):
                                        task['status'] = 'Completed'; save_project_data(st.session_state.projects); st.rerun()
                                elif task['status'] == 'Completed':
                                    if st.button("⏪ Re-open Task", key=f"reopen_{project_id}_{task['id']}", use_container_width=True):
                                        task['status'] = 'To Do'; save_project_data(st.session_state.projects); st.rerun()
                                with st.expander("Edit / Delete ✏️"):
                                    team_ids = [item.get('id') if isinstance(item, dict) else item for item in proj.get("team", [])]
                                    project_team_members = [emp_map[eid] for eid in team_ids if eid in emp_map]
                                    assignee_options = {emp['id']: emp['name'] for emp in project_team_members}; assignee_options['unassigned'] = "Unassigned"
                                    current_assignee_id = task.get('assignee_id', 'unassigned')
                                    if current_assignee_id not in assignee_options: current_assignee_id = 'unassigned'
                                    new_assignee_id = st.selectbox("Assign to:", options=list(assignee_options.keys()), index=list(assignee_options.keys()).index(current_assignee_id), format_func=lambda x: assignee_options[x], key=f"assign_{project_id}_{task['id']}")
                                    if new_assignee_id != current_assignee_id:
                                        task['assignee_id'] = new_assignee_id if new_assignee_id != 'unassigned' else None; save_project_data(st.session_state.projects); st.rerun()
                                    new_due_date = st.date_input("Due by:", value=due_date_obj, key=f"date_{project_id}_{task['id']}", format="YYYY-MM-DD")
                                    if (new_due_date.strftime('%Y-%m-%d') if new_due_date else None) != task.get('due_date'):
                                        task['due_date'] = new_due_date.strftime('%Y-%m-%d') if new_due_date else None; save_project_data(st.session_state.projects); st.rerun()
                                    st.markdown("---")
                                    if st.button("Delete Task 🗑️", key=f"delete_{project_id}_{task['id']}", use_container_width=True, type="primary"): 
                                        delete_task(project_id, task['id'])
                        k_col1, k_col2, k_col3 = st.columns(3)
                        with k_col1:
                            st.markdown("#### 📥 To Do")
                            for t in [t for t in proj.get('tasks', []) if t['status'] == 'To Do']: render_compact_task_card(t, proj['id'], proj_idx)
                        with k_col2:
                            st.markdown("#### ⚙️ In Progress")
                            for t in [t for t in proj.get('tasks', []) if t['status'] == 'In Progress']: render_compact_task_card(t, proj['id'], proj_idx)
                        with k_col3:
                            st.markdown("#### ✔️ Completed")
                            for t in [t for t in proj.get('tasks', []) if t['status'] == 'Completed']: render_compact_task_card(t, proj['id'], proj_idx)
                        with st.expander("⚙️ Project Settings"):
                            st.markdown("**Modify Team:**")
                            default_team_ids = [item.get('id') if isinstance(item, dict) else item for item in proj.get("team", [])]
                            selected_ids = st.multiselect("Team", options=[e["id"] for e in st.session_state.employees], default=default_team_ids, format_func=lambda x: emp_map[x]["name"], key=f"emp_select_{proj['id']}", label_visibility="collapsed")
                            b_col1, b_col2 = st.columns([3, 1])
                            if b_col1.button("💾 Save Team", key=f"save_team_{proj['id']}", use_container_width=True):
                                st.session_state.projects[proj_idx]["team"] = selected_ids; save_project_data(st.session_state.projects); st.success("Team updated."); st.rerun()
                            if b_col2.button("🗑️ Delete Project", key=f"delete_proj_{proj['id']}", use_container_width=True, type="primary"):
                                st.session_state.projects.pop(proj_idx); st.session_state.selected_project_id = None; save_project_data(st.session_state.projects); st.warning("Project deleted."); st.rerun()

# --- TAB: AI Task Assistant ---
elif cleaned_tab == "Assistant":
    st.header("💡 AI Task Assistant")
    emp_map = get_employee_map()
    if not st.session_state.projects: st.info("No projects available.")
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
                            team_ids = [item.get('id') if isinstance(item, dict) else item for item in st.session_state.projects[proj_index].get("team", [])]
                            proj_team_details = [emp_map[eid] for eid in team_ids if eid in emp_map]
                            st.session_state.projects[proj_index]['tasks'] = modify_tasks_with_llm(current_tasks, proj_team_details, command)
                            save_project_data(st.session_state.projects)
                            st.success("Tasks updated!")
                    except Exception as e: st.error(f"Failed to modify tasks: {e}")

# --- TAB: Employees (Read-Only Dashboard) ---
elif cleaned_tab == "Employees":
    st.header("👥 Employee Dashboard")
    emp_map = get_employee_map()
    
    master_col, detail_col = st.columns([1, 2])

    with master_col:
        st.subheader("Filters")
        search_term = st.text_input("Search by Name").lower()
        
        all_skills = sorted(list(set(skill.strip() for emp in st.session_state.employees for skill in emp['skills'].split(','))))
        selected_skills = st.multiselect("Filter by Skill", options=all_skills)

        st.markdown("---")
        
        emp_counts = get_employee_project_count()
        
        filtered_employees = st.session_state.employees
        if search_term:
            filtered_employees = [emp for emp in filtered_employees if search_term in emp['name'].lower()]
        if selected_skills:
            filtered_employees = [emp for emp in filtered_employees if all(skill in emp['skills'] for skill in selected_skills)]

        assigned_employees = [emp for emp in filtered_employees if emp_counts.get(emp['id'], 0) > 0]
        unassigned_employees = [emp for emp in filtered_employees if emp_counts.get(emp['id'], 0) == 0]

        with st.expander(f"✅ Assigned Employees ({len(assigned_employees)})", expanded=True):
            if not assigned_employees:
                st.caption("No assigned employees match filters.")
            for emp in assigned_employees:
                if st.button(emp['name'], key=f"select_emp_{emp['id']}", use_container_width=True):
                    st.session_state.selected_employee_id = emp['id']

        with st.expander(f"⚪ Unassigned Employees ({len(unassigned_employees)})", expanded=True):
            if not unassigned_employees:
                st.caption("No unassigned employees match filters.")
            for emp in unassigned_employees:
                if st.button(emp['name'], key=f"select_emp_free_{emp['id']}", use_container_width=True):
                    st.session_state.selected_employee_id = emp['id']
    
    with detail_col:
        if not st.session_state.selected_employee_id:
            st.info("⬅️ Select an employee to view their profile.")
        else:
            emp = next((e for e in st.session_state.employees if e['id'] == st.session_state.selected_employee_id), None)
            if emp:
                with st.container(border=True):
                    st.subheader(emp['name'])
                    st.markdown(f"**Skills:** *{emp['skills']}*")
                    c1, c2 = st.columns(2)
                    c1.metric("Experience", f"{emp['experience']} years")
                    c2.metric("Salary Grade", emp['salary_grade'])
                    
                    st.markdown("---")
                    st.subheader("Current Assignments")
                    assigned_projects = []
                    for project in st.session_state.projects:
                        team_ids = [item.get('id') if isinstance(item, dict) else item for item in project.get("team", [])]
                        if emp['id'] in team_ids:
                            assigned_projects.append(project['title'])
                    if assigned_projects:
                        for proj_title in assigned_projects:
                            st.info(f"• {proj_title}")
                    else:
                        st.success("This employee is currently available for new projects.")
