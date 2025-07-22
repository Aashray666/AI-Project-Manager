
import streamlit as st
from agent import generate_project, load_employees, modify_tasks_with_llm
import json
import os
import uuid
from datetime import datetime, date

# --- Page Configuration ---
st.set_page_config(page_title="Auto‑Staffing Dashboard", layout="wide")

# --- App Title ---
st.title("🚀 Auto‑Staffing Project Generator")

# --- Helper Functions ---
def get_employee_project_count():
    """Calculates how many projects each employee is assigned to."""
    count = {emp["id"]: 0 for emp in st.session_state.employees}
    for proj in st.session_state.get("projects", []):
        for emp_id in proj.get("team", []):
            if emp_id in count:
                count[emp_id] += 1
    return count

def get_employee_map():
    """Creates a dictionary mapping employee IDs to their data for quick lookups."""
    return {e["id"]: e for e in st.session_state.employees}

def delete_task(project_id, task_id):
    """Finds a project and removes a specific task from it."""
    for project in st.session_state.projects:
        if project['id'] == project_id:
            project['tasks'] = [t for t in project['tasks'] if t.get('id') != task_id]
            st.rerun()
            break

# --- Session State Initialization ---
if "employees" not in st.session_state:
    try:
        st.session_state.employees = load_employees("employess.json")
    except FileNotFoundError:
        st.error("Fatal Error: `employess.json` not found in the `data` directory. Please create it.")
        st.session_state.employees = []
        st.stop()

if "projects" not in st.session_state:
    st.session_state.projects = []

if "draft_project" not in st.session_state:
    st.session_state.draft_project = None

# --- Sidebar Navigation ---
tab = st.sidebar.radio("📂 Navigation", ["📥 New Project", "📋 Projects", "🧑‍💼 Employees"])

# --- TAB: New Project ---
if tab == "📥 New Project":
    st.header("📥 Create a New Project")
    st.write("Describe your project, and the AI will generate a title, description, and team.")
    
    brief = st.text_area("Enter your project brief here:", height=150, key="project_brief")

    if st.button("✨ Generate Project Draft"):
        if not brief.strip():
            st.warning("Please provide a brief before generating a project.")
        else:
            emp_counts = get_employee_project_count()
            eligible_employees = [e for e in st.session_state.employees if emp_counts.get(e["id"], 0) < 2]

            if not eligible_employees:
                st.error("No employees are available. All are assigned to 2 projects.")
            else:
                with st.spinner("🤖 AI Agent is crafting a project..."):
                    try:
                        new_project = generate_project(brief, eligible_employees)
                        new_project.update({"id": str(uuid.uuid4()), "status": "pending", "tasks": []}) 
                        st.session_state.draft_project = new_project
                    except Exception as e:
                        st.error(f"Failed to generate project: {e}")

    if st.session_state.draft_project:
        draft = st.session_state.draft_project
        st.markdown("---")
        st.subheader("📝 Project Draft")
        
        with st.container(border=True):
            st.markdown(f"#### {draft['title']}")
            st.write(draft["description"])
            
            emp_map = get_employee_map()
            team_names = [emp_map.get(eid, {"name": "Unknown"})["name"] for eid in draft.get("team", [])]
            st.info(f"**👥 Proposed Team:** {', '.join(team_names) if team_names else 'None'}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve Project", use_container_width=True):
                    draft["status"] = "approved"
                    st.session_state.projects.append(draft)
                    st.session_state.draft_project = None
                    st.success(f"Project '{draft['title']}' has been approved!")
                    st.rerun()
            with col2:
                if st.button("❌ Discard Draft", use_container_width=True):
                    st.session_state.draft_project = None
                    st.warning("Draft has been discarded.")
                    st.rerun()

# --- TAB: Projects ---
elif tab == "📋 Projects":
    st.header("📋 Projects Overview")

    if not st.session_state.projects:
        st.info("No approved projects yet. Go to 'New Project' to create one.")
    else:
        emp_map = get_employee_map()
        
        proj_col1, proj_col2 = st.columns(2)
        
        for proj_idx, proj in enumerate(st.session_state.projects):
            target_col = proj_col1 if proj_idx % 2 == 0 else proj_col2
            with target_col:
                with st.container(border=True):
                    st.markdown(f"### {proj['title']}")
                    st.markdown(f"**Status:** `{proj['status']}`")
                    st.markdown("---")
                    
                    st.subheader("📋 Task Board")
                    tasks = proj.get("tasks", [])
                    project_team_ids = proj.get("team", [])
                    project_team_members = [emp_map[eid] for eid in project_team_ids if eid in emp_map]
                    
                    k_col1, k_col2, k_col3 = st.columns(3)

                    def update_task_property(task_id, key, value):
                        for p in st.session_state.projects:
                            if p['id'] == proj['id']:
                                for t in p['tasks']:
                                    if t['id'] == task_id:
                                        t[key] = value
                                        st.rerun()

                    # FIX: Pass the project_id to ensure all keys are unique
                    def render_task_card(task, project_id):
                        desc_col, del_col = st.columns([4, 1])
                        with desc_col:
                            st.markdown(f"**{task['description']}**")
                        with del_col:
                            # FIX: Key now includes the unique project_id
                            if st.button("🗑️", key=f"delete_task_{project_id}_{task['id']}", help="Delete this task"):
                                delete_task(project_id, task['id'])
                        
                        current_due_date_str = task.get('due_date')
                        current_due_date_obj = datetime.strptime(current_due_date_str, '%Y-%m-%d').date() if current_due_date_str else None
                        
                        # FIX: Key now includes the unique project_id
                        new_due_date = st.date_input(
                            "Due by:", 
                            value=current_due_date_obj, 
                            key=f"date_{project_id}_{task['id']}",
                            format="YYYY-MM-DD"
                        )

                        new_due_date_str = new_due_date.strftime('%Y-%m-%d') if new_due_date else None
                        if new_due_date_str != current_due_date_str:
                            update_task_property(task['id'], 'due_date', new_due_date_str)

                        if current_due_date_obj and current_due_date_obj < date.today() and task['status'] != 'Completed':
                            st.error(f"Overdue: {current_due_date_str}")

                        assignee_options = {emp['id']: emp['name'] for emp in project_team_members}
                        assignee_options['unassigned'] = "Unassigned"
                        current_assignee_id = task.get('assignee_id', 'unassigned')
                        if current_assignee_id not in assignee_options: current_assignee_id = 'unassigned'
                        option_keys = list(assignee_options.keys())
                        current_index = option_keys.index(current_assignee_id)
                        
                        # FIX: Key now includes the unique project_id
                        new_assignee_id = st.selectbox("Assign to:", options=option_keys, index=current_index, format_func=lambda x: assignee_options[x], key=f"assign_{project_id}_{task['id']}")
                        if new_assignee_id != current_assignee_id:
                            update_task_property(task['id'], 'assignee_id', new_assignee_id if new_assignee_id != 'unassigned' else None)

                        # FIX: Keys for status buttons now include the unique project_id
                        if task['status'] == 'To Do':
                            if st.button("Start ▶️", key=f"start_{project_id}_{task['id']}", use_container_width=True):
                                update_task_property(task['id'], 'status', 'In Progress')
                        elif task['status'] == 'In Progress':
                             if st.button("Complete ✅", key=f"complete_{project_id}_{task['id']}", use_container_width=True):
                                update_task_property(task['id'], 'status', 'Completed')
                        elif task['status'] == 'Completed':
                             if st.button("Re-open ⏪", key=f"reopen_{project_id}_{task['id']}", use_container_width=True):
                                update_task_property(task['id'], 'status', 'To Do')

                        st.markdown("---")

                    with k_col1:
                        st.markdown("#### 📥 To Do")
                        with st.container(height=350, border=True):
                            for task in [t for t in tasks if t['status'] == 'To Do']:
                                # FIX: Pass proj['id'] to the render function
                                render_task_card(task, proj['id'])
                    with k_col2:
                        st.markdown("#### ⚙️ In Progress")
                        with st.container(height=350, border=True):
                            for task in [t for t in tasks if t['status'] == 'In Progress']:
                                # FIX: Pass proj['id'] to the render function
                                render_task_card(task, proj['id'])
                    with k_col3:
                        st.markdown("#### ✔️ Completed")
                        with st.container(height=350, border=True):
                            for task in [t for t in tasks if t['status'] == 'Completed']:
                                # FIX: Pass proj['id'] to the render function
                                render_task_card(task, proj['id'])

                    with st.expander("✏️ Modify Team / Delete Project"):
                        st.markdown("**Modify Team:**")
                        selected_ids = st.multiselect("Team", options=[e["id"] for e in st.session_state.employees], default=proj.get("team", []), format_func=lambda x: emp_map[x]["name"], key=f"emp_select_{proj['id']}", label_visibility="collapsed")
                        
                        b_col1, b_col2 = st.columns([3, 1])
                        with b_col1:
                            if st.button("💾 Save Team", key=f"save_team_{proj['id']}", use_container_width=True):
                                st.session_state.projects[proj_idx]["team"] = selected_ids
                                st.success(f"Team for '{proj['title']}' updated.")
                                st.rerun()
                        with b_col2:
                            if st.button("🗑️ Delete Project", key=f"delete_proj_{proj['id']}", use_container_width=True, type="primary"):
                                st.session_state.projects.pop(proj_idx)
                                st.warning(f"Project '{proj['title']}' deleted.")
                                st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("---")
        st.header("🤖 AI Task Assistant")
        
        if st.session_state.projects:
            project_options = {p['id']: p['title'] for p in st.session_state.projects}
            selected_proj_id = st.selectbox("Select a project to modify", options=list(project_options.keys()), format_func=lambda x: project_options[x])
            
            command = st.text_input("Enter a command (e.g., 'add task: Client meeting due tomorrow')", key="ai_task_command")

            if st.button("⚡ Execute Command"):
                if selected_proj_id and command:
                    with st.spinner("AI is processing your command..."):
                        try:
                            proj_index = next((i for i, p in enumerate(st.session_state.projects) if p['id'] == selected_proj_id), None)
                            if proj_index is not None:
                                current_tasks = st.session_state.projects[proj_index].get('tasks', [])
                                proj_team_ids = st.session_state.projects[proj_index].get('team', [])
                                proj_team_details = [emp_map[eid] for eid in proj_team_ids if eid in emp_map]
                                
                                new_task_list = modify_tasks_with_llm(current_tasks, proj_team_details, command)
                                
                                st.session_state.projects[proj_index]['tasks'] = new_task_list
                                st.success(f"Tasks for '{project_options[selected_proj_id]}' have been updated!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Failed to modify tasks: {e}")
                else:
                    st.warning("Please select a project and enter a command.")

# --- TAB: Employees ---
elif tab == "🧑‍💼 Employees":
    st.header("🧑‍💼 Employee Assignments")
    if not st.session_state.employees:
        st.warning("No employee data available.")
    else:
        emp_counts = get_employee_project_count()
        assigned = sorted([e for e in st.session_state.employees if emp_counts.get(e["id"], 0) > 0], key=lambda x: x['name'])
        unassigned = sorted([e for e in st.session_state.employees if emp_counts.get(e["id"], 0) == 0], key=lambda x: x['name'])
        
        st.subheader(f"✅ Assigned Employees ({len(assigned)})")
        if not assigned: st.info("No employees are currently assigned.")
        else:
            for emp in assigned:
                count = emp_counts[emp['id']]
                st.markdown(f"- **{emp['name']}** (Skills: *{emp['skills']}*) — Assigned to **{count}** project(s).")
        st.markdown("---")
        st.subheader(f"⚪ Unassigned Employees ({len(unassigned)})")
        if not unassigned: st.info("All employees are assigned to at least one project.")
        else:
            for emp in unassigned:
                st.markdown(f"- **{emp['name']}** (Skills: *{emp['skills']}*)")
