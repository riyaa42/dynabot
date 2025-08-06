# DynaBOT

**DynaBOT** is a Streamlit app for querying the content of uploaded PDF and PPTX files using a Retrieval-Augmented Generation (RAG) pipeline. 
It supports multi-file upload, intelligent chunking, MongoDB Atlas vector search, and a dynamic LLM query flow orchestrated using LangGraph.

---

Note: Its pretty much complete but some things work a bit roughly so i have to fix that and i want to modify some other things. 
      known issue: 
      -langgraph workflow works smoothly but if initial answer returned is graded as bad and it goes to the start of the retry process it will likely end up
        returning the default message asking you to input a better prompt eventually after going through the proceducers of rewriting prompt + retrieving more
        chunks. technically everything works as it should though so ill fix it later might need to change some parameters + a minor issue in logic 
        
---

## Features

### Dynamic File Handling

- **PDF and PPTX support**
- Extracts text and tables from PDFs (`pdfplumber`)
- Converts `.pptx` files to `.pdf` for inline viewing
- Single-file mode: Side-by-side viewer + chat
- Multi-file mode: Query across multiple files of different types
- Document metadata (like file name) stored for filtering during retrieval
- Supports live add/delete of documents from the vector store to sync with UI session

---

### Modular RAG Pipeline

- Uses LangGraph to define the flow:
  - **Retrieval → Generation → Evaluation → Retry → Fallback**
- Embeds user queries using HuggingFace models
- Performs top-k vector search using MongoDB Atlas
- Filters retrieved chunks by file name for scoped responses
- Evaluates the LLM answer quality on a 1–10 scale
- If quality is low:
  - Retry 1: Rewrites the query for clarity
  - Retry 2: Expands retrieval (increases `k`)
  - Fail: Falls back to default output
- Retry counter ensures clean loop exit

---

### Vector Store with MongoDB

- Stores embedded chunks in MongoDB Atlas using `MongoDBAtlasVectorSearch`
- Embeddings generated using `sentence-transformers/all-MiniLM-L6-v2`
- Real-time addition/removal of documents to keep storage in sync with session

---

###  Streamlit Chat Interface

- File upload, viewing, and selection in sidebar
- Inline chat window updates based on selected file(s)
- Maintains chat history and response traceability
- UI layout adapts to single or multi-file mode

---

##Setup Instructions 

IMPORTANT!!!!!!⚠️

  {
    1. LibreOffice should be installed in the system as streamlit ui doesnt support pptx files for viewing and i had to convert it to pdf for viewing purposes
      (program still processes .pptx files normally for rag processes it just converts for ui)
'''
      macOS
      
      '''
      brew install --cask libreoffice  
      '''
'''
      windows

      '''
       https://www.libreoffice.org/download/
       '''
       
'''      
    2. path to soffice is hardcoded in data_processing.py in function "def convert_pptx_to_pdf" as the default soffice path in MacOS. if different path or 
          if on :
               windows ( C:\\Program Files\\LibreOffice\\program\\soffice.exe), 
               linux (soffice) 
          please edit path to aforementioned before running.
          will update for ease of access in future.
     }

##1. Clone the repository
```
git clone https://github.com/yourusername/dynabot.git
cd dynabot
```

##2. Create a Virtual Environment
```
python3 -m venv .venv
source .venv/bin/activate
```
##3. Install Dependencies 
```
pip install -r requirements.txt
```

##4. Set up environment variables
```
cp .env.example .env
```
Edit the .env file and enter your actual values

```
LANGCHAIN_API_KEY=your_langchain_key
GOOGLE_API_KEY=your_google_key
MONGO_URL=your_mongodb_uri
DB_NAME=your_db_name
COLLECTION_NAME=your_collection
SEARCH_INDEX=your_index_name
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```
(make sure your vector search index is set up on mongodb using the .json file in the repo. number of embeddings depend on the embedding model and are set in my .json according to minilm-l6-v2)

##5.Run the app
```
streamlit run app.py
```



