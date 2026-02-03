import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import os
from dotenv import load_dotenv
from PIL import Image

# Load environment variables
# Load environment variables
import os
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path, override=True)
import time
from datetime import datetime
import base64
from io import BytesIO
import docx # Added for .docx support

# --- Configuration & Setup ---
st.set_page_config(
    page_title="Elite Master Plan & Academic Consulting",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
# Constants
# Constants
DATA_FILE = "students_data.json"
DOCS_DIR = "student_docs" # Directory to save files
MODEL_PRO = "gemini-3-pro-preview"   # Available v3 Preview model
MODEL_FLASH = "gemini-3-flash-preview" # Available v3 Flash Preview model

# --- Utility Functions ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def init_gemini(api_key):
    if api_key:
        genai.configure(api_key=api_key)
        return True
    return False

def extract_text_from_docx(file_stream):
    """Extracts text from a docx file stream."""
    try:
        doc = docx.Document(file_stream)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\\n'.join(full_text)
    except Exception as e:
        print(f"Error reading docx: {e}")
        return ""

def get_image_base64(image_path):
    if not os.path.exists(image_path):
        return ""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

def save_uploaded_files(student_name, uploaded_files):
    if not uploaded_files:
        return []
    
    student_dir = os.path.join(DOCS_DIR, student_name)
    os.makedirs(student_dir, exist_ok=True)
    
    saved_file_paths = []
    
    for file in uploaded_files:
        file_path = os.path.join(student_dir, file.name)
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
        saved_file_paths.append(file_path)
        
    return saved_file_paths

def delete_data(student_name):
    if not student_name: return False
    
    # 1. Remove from JSON
    data = load_data()
    if student_name in data:
        del data[student_name]
        save_data(data)
        
        # 2. Remove Files (Optional - strictly remove only if exists to avoid errors)
        import shutil
        student_dir = os.path.join(DOCS_DIR, student_name)
        if os.path.exists(student_dir):
            try:
                shutil.rmtree(student_dir)
            except Exception as e:
                print(f"Error deleting directory: {e}")
        return True
    return False

# --- Custom Styling (Premium Dashboard Look) ---
st.markdown("""
<style>
    /* Main Background and Text */
    .stApp {
        background-color: #ffffff; /* Light background */
        color: #31333F;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #e0e0e0;
    }

    /* Headers */
    h1, h2, h3 {
        color: #31333F;
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-weight: 700;
    }
    
    h1 {
        background: -webkit-linear-gradient(45deg, #005bea, #00c6fb); /* Blue gradient for light mode */
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2rem;
    }

    /* Buttons */
    .stButton>button {
        background: linear-gradient(90deg, #005bea 0%, #00c6fb 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 91, 234, 0.3);
    }

    /* Dataframes/Tables */
    [data-testid="stDataFrame"] {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }

    /* Chat Messages */
    .stChatMessage {
        background-color: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
    }
    
    /* Input Fields */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div {
        background-color: #ffffff;
        color: #31333F;
        border: 1px solid #e0e0e0;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

# --- Main App Logic ---

def main():
    # Title with Logo using Flexbox for perfect centering
    logo_path = "logo.png"
    logo_base64 = get_image_base64(logo_path)
    
    header_html = f"""
    <div style="display: flex; align-items: center; justify-content: flex-start; gap: 20px; margin-bottom: 2rem;">
        <img src="data:image/png;base64,{logo_base64}" style="height: 60px;">
        <h1 style="margin: 0; font-size: 3rem; padding: 0;">Elite Master Plan & Academic Consulting</h1>
    </div>
    """
    if not logo_base64: # Fallback if no logo
        header_html = """
        <div style="display: flex; align-items: center; justify-content: flex-start; gap: 20px; margin-bottom: 2rem;">
            <span style="font-size: 60px;">🎓</span>
            <h1 style="margin: 0; font-size: 3rem; padding: 0;">Elite Master Plan & Academic Consulting</h1>
        </div>
        """
        
    st.markdown(header_html, unsafe_allow_html=True)
    
    # Authenticate
    with st.sidebar:
        st.header("⚙️ 설정 (Settings)")
        
        # Load from env
        api_key = os.getenv("GOOGLE_API_KEY")
        
        # Fallback to input if not in env
        if not api_key:
            api_key = st.text_input("Gemini API Key를 입력하세요", type="password")
        
        is_ready = init_gemini(api_key)
        
        if not is_ready:
            st.warning("⚠️ API Key가 필요합니다.")
            st.stop()
        else:
            st.success("✅ 시스템 연결됨")

        st.divider()
        st.subheader("📁 Student Profile (학생 프로필)")
        
        # Load Data
        saved_data = load_data()
        student_list = list(saved_data.keys())
        
        # Select Student to Edit/View
        selected_student_key = st.selectbox("📂 Load Profile (학생 선택)", ["Create New (신규)"] + student_list)
        
        # Default values
        d_name, d_grade, d_target, d_major, d_status = "", "9th Grade", "", "", ""
        
        if selected_student_key != "Create New (신규)":
            student_info = saved_data[selected_student_key]
            d_name = selected_student_key
            d_grade = student_info.get("grade", "9th Grade")
            d_target = student_info.get("target", "")
            d_major = student_info.get("major", "")
            d_status = student_info.get("status", "")
        
        # Student Profile Inputs
        student_name = st.text_input("Student Name (이름)", value=d_name, placeholder="Alex Kim")
        
        # Grade Selectbox - need to find index for default
        grade_options = ["9th Grade", "10th Grade", "11th Grade", "12th Grade", "Gap Year"]
        try:
            grade_index = grade_options.index(d_grade)
        except ValueError:
            grade_index = 0
            
        student_grade = st.selectbox("Grade (학년)", grade_options, index=grade_index)
        target_university = st.text_input("Target Colleges (목표 대학)", value=d_target, placeholder="Harvard, Stanford, UC Berkeley, NYU...")
        intended_major = st.text_input("Intended Major/Field (전공/관심 분야)", value=d_major, placeholder="Computer Science, Pre-Med, Business...")
        current_status = st.text_area("Profile Summary (GPA, Test Scores, ECs)", value=d_status, 
                                      placeholder="GPA: 3.9/4.0 (UW)\nSAT: 1520\nAP: Calc BC(5), Chem(4)\nECs: Debate Club President, Research at Local Lab...")
        
        uploaded_files = st.file_uploader("Upload Documents (Transcript, Resume, Awards, etc, Files for reference)", 
                                          type=['pdf', 'png', 'jpg', 'jpeg', 'docx', 'doc', 'xlsx', 'xls', 'csv', 'txt'], 
                                          accept_multiple_files=True)
        
        if st.checkbox("Show Saved Files (저장된 파일 보기)"):
            if d_name and selected_student_key != "Create New (신규)":
                student_info = saved_data.get(d_name, {})
                saved_files = student_info.get("files", [])
                if saved_files:
                    st.write("📂 Saved Documents:")
                    for f in saved_files:
                        st.caption(f"- {os.path.basename(f)}")
                else:
                    st.caption("No saved documents.")

        if st.button("💾 Save Profile (Includes Files)"):
            if student_name:
                # Save & Merge Files
                data = load_data() # Load latest data
                existing_files = []
                
                # Check if we are updating an existing student (by name match)
                if student_name in data:
                     existing_files = data[student_name].get("files", [])
                
                new_files = []
                if uploaded_files:
                    new_files = save_uploaded_files(student_name, uploaded_files)
                
                # Combine and remove duplicates while preserving order
                saved_paths = list(dict.fromkeys(existing_files + new_files))
                data[student_name] = {
                    "grade": student_grade,
                    "target": target_university,
                    "major": intended_major,
                    "status": current_status,
                    "files": saved_paths,
                    "last_updated": str(datetime.now())
                }
                save_data(data)
                st.success(f"Saved profile & {len(saved_paths)} files for '{student_name}'!")
            else:
                st.error("Please enter specific student name.")
        
        # Delete Profile Option - REMOVED as per user request (Manual deletion only)
        # if selected_student_key != "Create New (신규)":
        #    ... (Code removed for safety)

    # Main Area Tabs
    tab1, tab2, tab3 = st.tabs(["📊 US Master Plan Generator", "💬 US Admissions Chatbot", "📧 Monthly Automated Email System"])

    # --- Tab 1: Master Plan Generator (Gemini 3 Pro) ---
    with tab1:
        st.subheader(f"🚀 Master Plan for {student_name if student_name else 'Student'}")
        
        # Prepare Analysis Files (Consolidated)
        available_files = {}
        # 1. Saved Files
        if selected_student_key == student_name:
             for f_path in saved_data.get(student_name, {}).get("files", []):
                  available_files[f"[Saved] {os.path.basename(f_path)}"] = f_path
        # 2. Uploaded Files
        if uploaded_files:
             for f in uploaded_files:
                  available_files[f"[New] {f.name}"] = f
        
        selected_filenames = []
        if available_files:
            with st.expander("📂 Select Documents for Analysis (분석할 파일 선택)", expanded=True):
                 st.write("Check the files you want to use:")
                 for fname in available_files.keys():
                     # Default to True (Checked)
                     if st.checkbox(fname, value=True, key=f"mp_{fname}"):
                         selected_filenames.append(fname)
        else:
             st.info("No documents available. Generating plan based on profile text only.")

        
        if st.button("✨ Generate Master Plan", type="primary"):
            if not student_name or not current_status:
                st.error("Please enter student profile and summary first.")
            else:
                with st.spinner("🔄 데이터 분석 및 로드맵 생성 중... (Gemini 3 Pro)"):
                    try:
                        # Prepare prompt
                        system_prompt = f"""
                        You are an expert US College Admissions Consultant (Elite Level).
                        You strictly follow the 2026 US Common App & University specific trends.
                        
                        [Student Profile]
                        - Name: {student_name}
                        - Grade: {student_grade}
                        - Target Colleges: {target_university}
                        - Intended Major: {intended_major}
                        - Profile Summary: {current_status}
                        
                        [Request]
                        Create a highly detailed 'US College Admissions Master Plan' in Korean.
                        
                        1. **Holistic Review Strategy**: Analyze GPA (Weighted/Unweighted), Rigor (AP/IB), Standardized Tests (SAT/ACT), and Extracurriculars. Identify the student's "Spike" or "Theme".
                        2. **Timeline & Monthly Action Plan**: Provide a month-by-month checklist up to graduation. Include specific times for SAT/ACT attempts, Summer Programs (RSI, TASP, etc.), Internship hunting, and Essay brainstorming.
                        3. **College List Strategy**: Suggest a balanced list (Reach, Match, Safety) if targets are unrealistic, or refine strategies for the targets.
                        4. **Application Strategy**: Early Decision (ED) vs Early Action (EA) vs Regular Decision (RD) recommendations.
                        
                        Output in clean Markdown (Korean). Use a Table for the Monthly Action Plan.
                        """
                        
                        # Handle Files - Logic to handle file content or upload to Gemini
                        content_parts = [system_prompt]
                        
                        # Handle Files - Logic to handle file content or upload to Gemini
                        content_parts = [system_prompt]
                        
                        files_to_process = []
                        
                        # File Selection Logic
                        files_to_process = []
                        
                        # Process selected files
                        if selected_filenames:
                            for fname in selected_filenames:
                                file_source = available_files[fname]
                                
                                # Case A: UploadedFile object
                                if hasattr(file_source, "type"): 
                                    file = file_source
                                    if file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or file.name.endswith(".docx"):
                                        extracted_text = extract_text_from_docx(file)
                                        if extracted_text:
                                            content_parts.append(f"\\n[Attached Document Content: {file.name}]\\n{extracted_text}\\n")
                                    else:
                                        files_to_process.append({
                                            "name": file.name,
                                            "mime_type": file.type,
                                            "data": file.getvalue()
                                        })
                                # Case B: File Path (Saved file)
                                else:
                                    file_path = file_source
                                    if os.path.exists(file_path):
                                        ext = os.path.splitext(file_path)[1].lower()
                                        mime_type = "application/pdf"
                                        
                                        if ext == ".docx":
                                            with open(file_path, "rb") as f:
                                                extracted_text = extract_text_from_docx(f)
                                                if extracted_text:
                                                     content_parts.append(f"\\n[Attached Document Content: {os.path.basename(file_path)}]\\n{extracted_text}\\n")
                                            continue 
                                        
                                        if ext == ".pdf": mime_type = "application/pdf"
                                        elif ext in [".jpg", ".jpeg"]: mime_type = "image/jpeg"
                                        elif ext == ".png": mime_type = "image/png"
                                        elif ext == ".doc": mime_type = "application/msword"
                                        elif ext == ".xlsx": mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                        elif ext == ".xls": mime_type = "application/vnd.ms-excel"
                                        elif ext == ".csv": mime_type = "text/csv"
                                        elif ext == ".txt": mime_type = "text/plain"
                                        
                                        try:
                                            with open(file_path, "rb") as f:
                                                files_to_process.append({
                                                    "name": os.path.basename(file_path),
                                                    "mime_type": mime_type,
                                                    "data": f.read()
                                                })
                                        except Exception as e:
                                            print(f"Error reading file {file_path}: {e}")

                        if files_to_process:
                            for f_obj in files_to_process:
                                content_parts.append({
                                    "mime_type": f_obj["mime_type"],
                                    "data": f_obj["data"]
                                })
                        elif not selected_filenames: 
                             st.warning("No documents selected. Analyzing based on text only.")

                        model = genai.GenerativeModel(MODEL_PRO) # Using requested 3-pro
                        # Note: In a real scenario with "gemini-3-pro" available, we'd swap the string.
                        # I will use a variable to mimic the intent.
                        
                        # Real code implementation note: 
                        # If 'gemini-3-pro' does not exist yet, this will fail. 
                        # I will code it to use "gemini-1.5-pro" but label it as requested in UI.
                        # OR if the user purely wants the code structure, I can use "gemini-3-pro" string.
                        # I'll use "gemini-1.5-pro" to ensure runnable code, but comment about v3.
                        
                        # model = genai.GenerativeModel('gemini-1.5-pro') 
                        
                        response = model.generate_content(content_parts)
                        
                        # Clean up common hallucinated tags if necessary, but enabling HTML usually fixes standard <br>
                        # Replacing <br-> just in case it's a model artifact
                        cleaned_text = response.text.replace("<br->", "<br>- ")
                        
                        st.markdown(cleaned_text, unsafe_allow_html=True)
                        
                        # Save result locally for record
                        # (Optional implementation detail)
                        
                    except Exception as e:
                        st.error(f"에러 발생: {e}")
                        st.error("API Key 또는 모델 권한을 확인해주세요.")

    # --- Tab 2: Consulting Chatbot (Gemini 3 Flash) ---
    with tab2:
        st.subheader(f"💬 US Admissions Chatbot for {student_name if student_name else 'Student'}")
        st.caption("⚡ Powered by Gemini-3-Flash")
        
        # Chat File Selection
        available_files_chat = {}
        if selected_student_key == student_name:
             for f_path in saved_data.get(student_name, {}).get("files", []):
                  available_files_chat[f"[Saved] {os.path.basename(f_path)}"] = f_path
        if uploaded_files:
             for f in uploaded_files:
                  available_files_chat[f"[New] {f.name}"] = f
        
        selected_filenames_chat = []
        if available_files_chat:
             with st.expander("📂 Context Documents (대화에 참고할 파일 설정)", expanded=False):
                 st.write("Select files for chatbot context:")
                 for fname in available_files_chat.keys():
                     if st.checkbox(fname, value=True, key=f"chat_{fname}"):
                         selected_filenames_chat.append(fname)
        
        # Chat History
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Display Chat
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat Input
        if prompt := st.chat_input("Ask about US Admissions (e.g., 'Does NYU require SAT?')"):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate response
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                
                try:
                    # Retrieve files for context
                    chat_context_parts = []
                    
                    # System Prompt Text
                    system_text = f"""
                    You are a knowledgeable US College Admissions Chatbot.
                    Student Info: {student_name}, {student_grade}, Target: {target_university}, Major: {intended_major}.
                    
                    [Attached Documents]
                    The user has provided the following files (Transcripts, Essays, etc.). 
                    Use the information in these files to answer specific questions (e.g., "What is my GPA?", "Critique my essay").
                    
                    Answer questions about Common App, Essays, SAT/ACT, Financial Aid, and specific university culture.
                    Be concise and encouraging. 
                    IMPORTANT: Always answer in Korean (한국어).
                    """
                    chat_context_parts.append(system_text)

                    # Add Saved Files to Context
                    if selected_filenames_chat:
                        for fname in selected_filenames_chat:
                             file_source = available_files_chat[fname]
                             
                             # Case A: UploadedFile object
                             if hasattr(file_source, "type"):
                                 file = file_source
                                 if file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or file.name.endswith(".docx"):
                                     extracted_text = extract_text_from_docx(file)
                                     if extracted_text:
                                         chat_context_parts.append(f"\\n[Attached Document Content: {file.name}]\\n{extracted_text}\\n")
                                 else:
                                     chat_context_parts.append({
                                         "mime_type": file.type,
                                         "data": file.getvalue()
                                     })

                             # Case B: File Path (Saved file)
                             else:
                                 file_path = file_source
                                 if os.path.exists(file_path):
                                     ext = os.path.splitext(file_path)[1].lower()
                                     mime_type = "application/pdf"
                                     if ext == ".docx":
                                         try:
                                             with open(file_path, "rb") as f:
                                                 extracted_text = extract_text_from_docx(f)
                                                 if extracted_text:
                                                     chat_context_parts.append(f"\\n[Attached Document Content: {os.path.basename(file_path)}]\\n{extracted_text}\\n")
                                         except Exception as e:
                                             print(f"Error reading docx {file_path}: {e}")
                                         continue 

                                     if ext == ".pdf": mime_type = "application/pdf"
                                     elif ext in [".jpg", ".jpeg"]: mime_type = "image/jpeg"
                                     elif ext == ".png": mime_type = "image/png"
                                     elif ext == ".doc": mime_type = "application/msword"
                                     elif ext == ".xlsx": mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                     elif ext == ".xls": mime_type = "application/vnd.ms-excel"
                                     elif ext == ".csv": mime_type = "text/csv"
                                     elif ext == ".txt": mime_type = "text/plain"
                                     
                                     try:
                                         with open(file_path, "rb") as f:
                                             chat_context_parts.append({
                                                "mime_type": mime_type,
                                                "data": f.read()
                                             })
                                     except Exception as e:
                                         print(f"Error reading file {file_path}: {e}")

                    # Use Flash model
                    model_flash = genai.GenerativeModel(MODEL_FLASH) # Logic for 3-flash
                    
                    # Construct history for API (System Context + User Turn)
                    # Note: We inject the files into the very first turn to serve as "Context"
                    history_for_api = [
                        {"role": "user", "parts": chat_context_parts}
                    ]
                    
                    # Add Model acknowledgment to simulate a history where model knows context
                    history_for_api.append({"role": "model", "parts": ["네, 학생의 자료와 정보를 숙지했습니다. 무엇이든 물어보세요!"]})
                    
                    # Append actual conversation history
                    for m in st.session_state.messages:
                        role = "user" if m["role"] == "user" else "model"
                        history_for_api.append({"role": role, "parts": [m["content"]]})
                    
                    with st.spinner("Thinking... (분석 중입니다)"):
                        response = model_flash.generate_content(history_for_api)
                    
                    full_response = response.text
                    message_placeholder.markdown(full_response)
                    
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    
                except Exception as e:
                    st.error(f"Error: {e}")
    with tab3:
        st.subheader("📧 Automated Monthly Newsletter (General Monthly Master Plan)")
        st.caption("Manage subscribers and send monthly guides.")
        
        # 1. Subscriber Management
        st.write("### 👥 Subscribers (구독자 관리)")
        
        # Load Subscribers
        import newsletter_utils
        subscribers = newsletter_utils.load_subscribers()
        
        col_sub1, col_sub2 = st.columns([3, 1])
        with col_sub1:
            new_emails_input = st.text_area("Add Email Address(es)", placeholder="Paste list of emails here (one per line, or comma separated)", height=100)
        with col_sub2:
            st.write("")
            st.write("")
            if st.button("Add (+)", type="secondary"):
                if new_emails_input:
                    # Parse inputs (split by newline or comma)
                    raw_list = new_emails_input.replace(',', '\n').split('\n')
                    valid_emails = []
                    for e in raw_list:
                        e = e.strip()
                        if "@" in e:
                            valid_emails.append(e)
                    
                    if valid_emails:
                        added = newsletter_utils.save_subscribers(valid_emails)
                        if added > 0:
                            st.success(f"Successfully added {added} new subscribers!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("All valid emails already exist.")
                    else:
                        st.error("No valid emails found in input.")
                else:
                    st.warning("Please enter emails.")
        
        if subscribers:
            st.dataframe(pd.DataFrame({"Subscribers": subscribers}), hide_index=True)
            
            # Remove Option (Bulk)
            emails_to_remove = st.multiselect("Select Subscribers to Remove", subscribers)
            
            col_rem1, col_rem2 = st.columns([1, 1])
            with col_rem1:
                if st.button("🗑️ Remove Selected"):
                    if emails_to_remove:
                        newsletter_utils.remove_subscribers(emails_to_remove)
                        st.success(f"Removed {len(emails_to_remove)} subscribers.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.warning("Select valid emails to remove.")
            
            with col_rem2:
                if st.button("⚠️ Remove ALL Subscribers", type="primary"):
                    newsletter_utils.remove_subscribers(subscribers)
                    st.success("All subscribers removed.")
                    time.sleep(1)
                    st.rerun()

        else:
            st.info("No subscribers yet. Add one above!")
            
        st.divider()
        
        # 2. Email Configuration
        st.write("### ⚙️ Sender Configuration (발신자 설정)")
        st.info("Gmail 'App Password' is required for automation.")
        
        col_conf1, col_conf2 = st.columns(2)
        with col_conf1:
            # We don't save this to file for security in this simple demo, 
            # we rely on .env or session state. 
            # Ideally, user sets this in .env manually.
            current_sender = os.getenv("SENDER_EMAIL", "")
            st.text_input("Sender Email (From .env)", value=current_sender, disabled=True)
        
        with col_conf2:
             is_password_set = bool(os.getenv("SENDER_PASSWORD"))
             st.text_input("App Password Status", value="✅ Set in .env" if is_password_set else "❌ Not Set", disabled=True)
        
        st.divider()
        
        # 3. Preview & Test
        st.write("### 📢 Content Preview & Test (미리보기 및 발송)")
        
        preview_grade = st.selectbox("Select Grade for Preview", ["9th Grade", "10th Grade", "11th Grade", "12th Grade"])
        
        if st.button("👁️ Generate Preview for This Month"):
            current_month = datetime.now().strftime("%B")
            with st.spinner(f"Generating optimized plan for {preview_grade} ({current_month})..."):
                preview_content = newsletter_utils.generate_monthly_plan(api_key, preview_grade, current_month)
                st.markdown(preview_content)
                st.session_state['last_preview'] = preview_content
        
        st.write("")
        st.write("---")
        st.subheader("🚀 Bulk Email Sender (대량 발송)")
        
        # Step 1: Generate Draft
        if st.button("📝 STAGE 1: Generate Draft for Review (내용 생성 및 확인)"):
            with st.spinner("Generating content for all grades... (This may take ~30 seconds)"):
                try:
                    # Current logic to generate content
                    current_month = datetime.now().strftime("%B")
                    full_body = f"# Elite Prep – {current_month} Academic Master Plan\n\n"
                    
                    grades = ["9th Grade", "10th Grade", "11th Grade", "12th Grade"]
                    progress_bar = st.progress(0)
                    
                    for i, grade in enumerate(grades):
                        content = newsletter_utils.generate_monthly_plan(api_key, grade, current_month)
                        full_body += f"## 📌 {grade}\n{content}\n\n---\n\n"
                        progress_bar.progress((i + 1) / len(grades))
                    
                    # Append Footer Signature
                    full_body += """
Sent by Elite Prep Master Plan & Academic Consulting

Andy Lee  | Branch Director <br>
Elite Prep Suwanee powered by Elite Open School <br>
1291 Old Peachtree Rd. NW #127, Suwanee, GA 30024 <br>
Tel & Text: 470.253.1004
"""
                    
                    # Store in session state
                    st.session_state['draft_email_content'] = full_body
                    st.session_state['draft_month'] = current_month
                    st.success("Draft Generated! Please review below.")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error generating draft: {e}")

        # Step 2: Review & Send
        if 'draft_email_content' in st.session_state:
            st.write("### 📝 Review & Edit Draft (내용 확인 및 수정)")
            st.info("아래 내용을 확인하고 필요하면 직접 수정하세요. 수정된 내용 그대로 발송됩니다.")
            
            # Editable Text Area
            edited_body = st.text_area("Email Content", value=st.session_state['draft_email_content'], height=400)
            
            # Update session state if edited
            if edited_body != st.session_state['draft_email_content']:
                st.session_state['draft_email_content'] = edited_body

            col_send1, col_send2 = st.columns([1, 1])
            with col_send1:
                if st.button("🚀 STAGE 2: Send to ALL Subscribers (최종 발송)", type="primary"):
                    # Force reload env to get latest credentials (absolute path)
                    env_path = os.path.join(os.path.dirname(__file__), '.env')
                    load_dotenv(dotenv_path=env_path, override=True)
                    sender = os.getenv("SENDER_EMAIL")
                    pwd = os.getenv("SENDER_PASSWORD")
                    
                    if not sender or not pwd:
                        st.error("Please set SENDER_EMAIL and SENDER_PASSWORD in .env file first.")

                    elif not subscribers:
                        st.error("No subscribers to send to.")
                    else:
                        with st.status("Sending Emails...", expanded=True) as status:
                            current_month = st.session_state.get('draft_month', datetime.now().strftime("%B"))
                            
                            success, msg = newsletter_utils.send_email(
                                sender, 
                                pwd, 
                                subscribers, 
                                f"[{current_month}] Monthly Academic Master Plan", 
                                st.session_state['draft_email_content'] # Use the (potentially edited) content
                            )
                            
                            if success:
                                status.update(label="✅ Newsletter Sent Successfully!", state="complete", expanded=False)
                                st.success(msg)
                                # Clear draft after successful send
                                del st.session_state['draft_email_content']
                                time.sleep(2)
                                st.rerun()
                            else:
                                status.update(label="❌ Failed", state="error")
                                st.error(msg)
            
            with col_send2:
                 if st.button("🗑️ Discard Draft (초안 삭제)"):
                    del st.session_state['draft_email_content']
                    st.rerun()

if __name__ == "__main__":
    main()

