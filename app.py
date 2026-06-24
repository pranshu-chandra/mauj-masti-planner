import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta, time

# --- Setup & Config ---
st.set_page_config(page_title="Mauj Masti Planner", page_icon="🎉", layout="wide")
st.title("🎉 Mauj Masti Planner")
st.markdown("Find common free time slots so your plans don't clash with anyone's timetable!")

# --- Data Loading & Processing ---
@st.cache_data
def load_data():
    file_path = "Term-IV Time Table (PGP 2025-27 batch) AY 2026-27 (1).xlsx"
    xls = pd.ExcelFile(file_path)
    
    course_matrix = pd.read_excel(xls, sheet_name='Course Matrix')
    post_bid_tt = pd.read_excel(xls, sheet_name='Post bid TT T-4')

    # 1. Parse Students & Enrolled Courses
    students_list = course_matrix.iloc[3:, 5].dropna().tolist()
    courses_data = course_matrix.iloc[3:, 12:]
    
    def clean_course_name(name):
        if pd.isna(name): return None
        # Remove special characters/spaces and standardize to uppercase
        return re.sub(r'[^A-Za-z0-9]', '', str(name)).upper()

    student_courses = {}
    for idx, student in enumerate(students_list):
        row = courses_data.iloc[idx].dropna().tolist()
        student_courses[student] = set([clean_course_name(c) for c in row if pd.notna(c)])

    # 2. Parse Daily Timetable Slots
    slot_times = [
        ('09:00', '10:15'), ('10:30', '11:45'), ('12:00', '13:15'), ('13:15', '14:30'),
        ('14:30', '15:45'), ('16:00', '17:15'), ('17:30', '18:45'), ('19:00', '20:15'),
        ('20:45', '22:00'), ('22:15', '23:30')
    ]
    
    daily_schedule = {} 
    
    # Iterate through the schedule starting from row 3
    for i in range(3, len(post_bid_tt)):
        row = post_bid_tt.iloc[i]
        date_val = row.iloc[0]
        
        current_date = None
        if pd.notna(date_val):
            if isinstance(date_val, datetime):
                current_date = date_val.date()
            elif isinstance(date_val, str):
                try:
                    current_date = pd.to_datetime(date_val).date()
                except:
                    continue
                    
        if current_date is None:
            continue
            
        if current_date not in daily_schedule:
            daily_schedule[current_date] = {s_idx: set() for s_idx in range(10)}
            
        # Extract courses running in each of the 10 slots
        for s_idx in range(10):
            cell_val = row.iloc[s_idx + 2]
            if pd.notna(cell_val):
                c_clean = re.sub(r'\s*\d+$', '', str(cell_val)) # Strip section numbers
                c_clean = re.sub(r'[^A-Za-z0-9]', '', c_clean).upper()
                if c_clean and c_clean not in ['LUNCH', 'REGISTRATION']:
                    daily_schedule[current_date][s_idx].add(c_clean)
                    
    return student_courses, daily_schedule, slot_times

try:
    student_courses, daily_schedule, slot_times = load_data()
except Exception as e:
    st.error(f"Error loading the Excel file. Please ensure 'Term-IV Time Table (PGP 2025-27 batch) AY 2026-27 (1).xlsx' is in the same directory. Details: {e}")
    st.stop()

# --- Sidebar Interfaces ---
st.sidebar.header("Plan Your Mauj Masti 🍻")

all_students = sorted(list(student_courses.keys()))
default_students = ["Pranshu Chandra"] if "Pranshu Chandra" in all_students else []

selected_students = st.sidebar.multiselect(
    "1. Select the Gang:",
    options=all_students,
    default=default_students
)

available_dates = sorted(list(daily_schedule.keys()))
if not available_dates:
    st.warning("No valid dates found in the timetable.")
    st.stop()

selected_date = st.sidebar.date_input(
    "2. Select Date:",
    value=available_dates[0],
    min_value=min(available_dates),
    max_value=max(available_dates)
)

duration_hours = st.sidebar.selectbox(
    "3. Required Free Time (Hours):",
    options=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0],
    index=2
)

# --- Core Logic & Visualization ---
if not selected_students:
    st.info("👈 Please select at least one person from the sidebar to start finding free slots.")
else:
    # Union of all courses the selected group is taking
    group_courses = set()
    for student in selected_students:
        group_courses.update(student_courses[student])
        
    st.write(f"**Selected Group Size:** {len(selected_students)} people")
    
    if selected_date not in daily_schedule:
        st.warning(f"No classes scheduled on {selected_date}.")
    else:
        day_slots = daily_schedule[selected_date]
        busy_intervals = []
        
        # Determine exactly when the group is busy
        for s_idx in range(10):
            courses_in_slot = day_slots[s_idx]
            if group_courses.intersection(courses_in_slot):
                start_str, end_str = slot_times[s_idx]
                start_dt = datetime.combine(selected_date, datetime.strptime(start_str, '%H:%M').time())
                end_dt = datetime.combine(selected_date, datetime.strptime(end_str, '%H:%M').time())
                busy_intervals.append((start_dt, end_dt))
                
        # Calculate continuous Free Intervals across the day
        day_start = datetime.combine(selected_date, time(9, 0))
        day_end = datetime.combine(selected_date, time(23, 30))
        
        free_intervals = []
        current_time = day_start
        
        for b_start, b_end in sorted(busy_intervals):
            if current_time < b_start:
                free_intervals.append((current_time, b_start))
            current_time = max(current_time, b_end)
            
        if current_time < day_end:
            free_intervals.append((current_time, day_end))
            
        # Filter gaps by the requested duration
        req_td = timedelta(hours=duration_hours)
        valid_blocks = []
        
        for f_start, f_end in free_intervals:
            if f_end - f_start >= req_td:
                valid_blocks.append((f_start, f_end))
                
        # Output the Results
        st.subheader(f"Common Free Slots on {selected_date.strftime('%B %d, %Y')}")
        
        if valid_blocks:
            st.success(f"Found {len(valid_blocks)} slot(s) with at least {duration_hours} hours of free time!")
            for idx, (start, end) in enumerate(valid_blocks, 1):
                block_duration = (end - start).total_seconds() / 3600
                st.markdown(f"**Slot {idx}:** 🟢 `{start.strftime('%I:%M %p')} to {end.strftime('%I:%M %p')}` *(Total Block: {block_duration:.2f} hrs)*")
        else:
            st.error(f"No common free slots of {duration_hours} hours found for this group on {selected_date}. Someone has a class!")
            
        # Transparency check
        with st.expander("Show detailed schedule breakdown for the group"):
            for s_idx in range(10):
                courses_in_slot = day_slots[s_idx]
                clashing_courses = group_courses.intersection(courses_in_slot)
                start_str, end_str = slot_times[s_idx]
                
                if clashing_courses:
                    st.markdown(f"- 🔴 **{start_str} - {end_str}:** Busy (Classes: {', '.join(clashing_courses)})")
                else:
                    st.markdown(f"- 🟢 **{start_str} - {end_str}:** Free")