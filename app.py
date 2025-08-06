from dotenv import load_dotenv 
import streamlit as st

if "selected_file_name" not in st.session_state: 
    st.session_state.selected_file_name=None
    
import tempfile
from streamlit_pdf_viewer import pdf_viewer
from streamlit_extras.stylable_container import stylable_container
import os
load_dotenv()
from data_processing import load_file, split_docs, convert_pptx_to_pdf
from db_utils import check_env, cleanup, add_documents, delete_file,search_index
from langgraph_flow import build_rag_graph, GraphState


@st.cache_resource(show_spinner=False)
def get_rag_graph():
    return build_rag_graph()

rag_graph_app = get_rag_graph()

st.set_page_config(layout="wide", page_title="DynaBOT")

try:
    check_env()
except EnvironmentError as e:
    st.error(str(e))
    st.stop()
    
if "processed_file_info" not in st.session_state:
    st.session_state.processed_file_info={} # key:file_name {str} ,value:{ tmp_path=str, ingestion=bool}


if "chat_history" not in st.session_state:
    st.session_state.chat_history = {} #key: file_name {str}, value: prev chat messages{List}

if "shown_toasts" not in st.session_state:
    st.session_state.shown_toasts=[]

if "orphan_cleanup" not in st.session_state:
    st.session_state.orphan_cleanup = False

if not st.session_state.orphan_cleanup:
    try:
        store_db = cleanup()
        uploaded_files_names_set = {f.name for f in st.session_state.uploaded_files} if "uploaded_files" in st.session_state else set()
        orphan_files=store_db-uploaded_files_names_set

        if orphan_files:
            for file_name in orphan_files:
                delete_file(file_name)
        st.session_state.orphan_cleanup = True
    except Exception as e:
        st.toast(f"Error during initial DB cleanup: {e}")
        st.session_state.initial_db_cleanup_done = True

uploaded_files=st.sidebar.file_uploader("**Upload a file**", type=["pdf","pptx"], accept_multiple_files=True)
selected_file_names = []


for uploaded_file in uploaded_files:
    if uploaded_file.name not in st.session_state.shown_toasts:
        st.toast(f"Uploaded file: {uploaded_file.name}", icon="🟣")
        st.session_state.shown_toasts.append(uploaded_file.name)

if uploaded_files:
    uploaded_files_names = {f.name for f in uploaded_files}
else:
    uploaded_files_names = set()

newly_added_files=[]
for uploaded_file in uploaded_files:
    if uploaded_file.name not in st.session_state.processed_file_info:
        newly_added_files.append(uploaded_file)
        

if newly_added_files:
    for uploaded_file in newly_added_files:
        file_name=uploaded_file.name
        tmp_path=None
        pdf_viewer_path=None

        try:
            file_ext = os.path.splitext(file_name)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                tmp_file.write(uploaded_file.read())
                tmp_path = tmp_file.name
                
            
            with st.spinner(f"Processing {file_name}..."):
                if file_ext == ".pptx":
                     pdf_viewer_path = convert_pptx_to_pdf(tmp_path, os.path.dirname(tmp_path))
                     if not pdf_viewer_path:
                        st.error(f"Failed to convert {file_name} to PDF.")
                     else:
                        tmp_path = pdf_viewer_path
                elif file_ext == ".pdf":
                    pdf_viewer_path = tmp_path  


                docs=load_file(tmp_path)
                chunks=split_docs(docs)
                
                add_documents(chunks,file_name)
                st.toast("added documents")

                st.session_state.processed_file_info[file_name] = {
                    "tmp_path": tmp_path,
                    "pdf_viewer_path": pdf_viewer_path,
                    "ingested": True
                }

                if file_name not in st.session_state.chat_history:
                    st.session_state.chat_history[file_name] = []

        except Exception as e:

                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)

                delete_file(file_name)
                if file_name in st.session_state.processed_file_info:
                    del st.session_state.processed_file_info[file_name]
                if file_name in st.session_state.chat_history:
                    del st.session_state.chat_history[file_name]
                st.toast("file not ingested")    

files_to_remove=[]
for file_name in st.session_state.processed_file_info.keys():
    if file_name not in uploaded_files_names:
        files_to_remove.append(file_name)

if files_to_remove:
    for file_name in files_to_remove:
        key_value=st.session_state.processed_file_info[file_name]
        tmp_path=key_value["tmp_path"]
        pdf_viewer_path = key_value.get("pdf_viewer_path")

        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        if pdf_viewer_path and os.path.exists(pdf_viewer_path) and pdf_viewer_path != tmp_path:
            os.remove(pdf_viewer_path)
        delete_file(file_name)
        del st.session_state.processed_file_info[file_name]
        if file_name in st.session_state.chat_history:
            del st.session_state.chat_history[file_name]

        if st.session_state.selected_file_name==file_name:
            st.session_state.selected_file_name=None

st.sidebar.markdown("**Select a File**")
available_files=list(st.session_state.processed_file_info.keys())

if not available_files:
     st.sidebar.markdown("<span style='color:red'>No files uploaded yet</span>", unsafe_allow_html=True)
     
else:

    with stylable_container(
        key="scrollable_container",
        css_styles="""
            {
                max-height: 200px;
                overflow-y: scroll;
            }
            """,
    ):
        selected_file_names = st.sidebar.multiselect("select files",
            options=available_files,
            key="selected_file_radio",
            label_visibility="collapsed"
            )
        
    if len(selected_file_names) == 1:
        st.session_state.selected_file_name = selected_file_names[0]
    else:
        st.session_state.selected_file_name = None

    if st.session_state.selected_file_name is not None:
        selected_file_name=st.session_state.selected_file_name
        selected_file_info=st.session_state.processed_file_info.get(selected_file_name)
        chat_key=selected_file_name

        if selected_file_info is not None and selected_file_info["ingested"]==True:
            session_viewer_path=selected_file_info["pdf_viewer_path"]
    
            session_file_name=st.session_state.selected_file_name

            if chat_key not in st.session_state.chat_history:
                    st.session_state.chat_history[chat_key] = []
            session_chat_history = st.session_state.chat_history[chat_key]

            col1, col2 = st.columns([1, 1.5])

            with col1:
                st.subheader(f"Viewing: {st.session_state.selected_file_name}")
                use_container_width=True
                
                pdf_viewer(
                        session_viewer_path,
                        width="100%",
                        height=1000,
                        zoom_level="auto",
                        viewer_align="right",
                        show_page_separator=True,
                        )

            with col2:
                st.subheader("Chat with your file")
                with stylable_container(
                    key="scroll_chat_container",
                    css_styles="""
                    {
                         max-height: 70vh;
                         overflow-y: auto;
                         padding-right: 10px;
                    }
           """
                ):

                    for message in session_chat_history:
                         avatar="https://img.icons8.com/?size=100&id=0LnHUOCnYTrK&format=png&color=F25081" if message["role"] == "user" else "https://img.icons8.com/?size=100&id=100414&format=png&color=7950F2"
                         with st.chat_message(message["role"], avatar=avatar):
                              st.write(message["content"])
                    

                if user_input := st.chat_input("Ask a question about the document:"):
                
                    st.session_state.chat_history[chat_key].append({"role": "user", "content": user_input})

                    with st.spinner("Thinking..."):
                        initial_state = GraphState(
                        query=user_input,
                        selected_file_names=[st.session_state.selected_file_name],
                        search_index_name=search_index,
                        documents=[],
                        answer="",
                        relevance_grade="",
                        retry_count=0,
                        search_kwargs={"k": 5}
                    )
                        final_state = rag_graph_app.invoke(initial_state)
                        final_answer = final_state.get("answer")
                    
                    st.session_state.chat_history[chat_key].append({"role": "assistant", "content": final_answer})
                    st.rerun()



    if len(selected_file_names) > 1 and st.session_state.selected_file_name is None:
         chat_key = tuple(sorted(selected_file_names))
         if chat_key not in st.session_state.chat_history:
                st.session_state.chat_history[chat_key] = []
         session_chat_history = st.session_state.chat_history[chat_key]

         st.subheader(f"Chat with: {', '.join(selected_file_names)}")
         with stylable_container(
                    key="scroll_chat_container",
                    css_styles="""
                    {
                         max-height: 70vh;
                         overflow-y: auto;
                         padding-right: 10px;
                    }
           """
         ):
                     for message in session_chat_history:
                         avatar="https://img.icons8.com/?size=100&id=0LnHUOCnYTrK&format=png&color=F25081" if message["role"] == "user" else "https://img.icons8.com/?size=100&id=100414&format=png&color=7950F2"
                         with st.chat_message(message["role"], avatar=avatar):
                             st.write(message["content"])

         if user_input := st.chat_input("Ask a question about the files:"):

            st.session_state.chat_history[chat_key].append({"role": "user", "content": user_input})

            with st.spinner("Thinking..."):
                            
                initial_state = GraphState(
                                query=user_input,
                                selected_file_names=list(selected_file_names), 
                                search_index_name=search_index,
                                documents=[],
                                answer="",
                                relevance_grade="",
                                retry_count=0,
                                search_kwargs={"k": 5}
                            )

                            
                final_state = rag_graph_app.invoke(initial_state)
                            
                            
                final_answer = final_state.get("answer")

                        
            st.session_state.chat_history[chat_key].append({"role": "assistant", "content": final_answer})
            st.rerun() 

placeholder = st.empty()

if not selected_file_names:
    with placeholder:
        st.markdown(
            """
            <div style='text-align: center; padding: 60px 20px; color: #888;'>
                <h1 style='color: #F25081; font-size: 48px; margin-bottom: 10px;'>DynaBOT</h1>
                <img src='https://img.icons8.com/?size=100&id=100414&format=png&color=F25081' width='150' style='margin-bottom: 30px;' />
                <h2>No documents selected</h2>
                <p>Please upload or select a file from the sidebar to get started.</p>
            </div>
            """,
            unsafe_allow_html=True
        )
else:
    placeholder.empty()
    