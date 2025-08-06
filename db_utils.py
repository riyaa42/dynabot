import os
from dotenv import load_dotenv 
from pymongo import MongoClient
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
import streamlit as st

load_dotenv()

mongo_url=os.getenv("MONGO_URL")
db_name=os.getenv("DB_NAME")
search_index=os.getenv("SEARCH_INDEX")
langchain_api_key=os.getenv("LANGCHAIN_API_KEY")
google_api_key=os.getenv("GOOGLE_API_KEY")
embedding_model=os.getenv("EMBEDDING_MODEL")
collection_name=os.getenv("COLLECTION_NAME") 

def check_env():
    if not all(
        [
            mongo_url,
            db_name,
            search_index,
            langchain_api_key,
            google_api_key,
            embedding_model,
            collection_name
        ]
    ):
        raise EnvironmentError("[ERROR] Missing one or more environment variables")



def mongo_connection_url():
    try:
        client = MongoClient(mongo_url)
        client.admin.command('ping')  
        return client
    except Exception as e:
        st.error(f"Failed to connect to MongoDB: {e}")
        raise ConnectionError(f"[ERROR] Failed to connect to MongoDB: {e}")

def set_embedding_model():
    model_name = embedding_model
    model_kwargs = {'device': 'cpu'}
    encode_kwargs = {'normalize_embeddings': False}
    try:
        print("DEBUG: Attempting to initialize HuggingFaceEmbeddings...")
        hf_embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )
        print("HuggingFaceEmbeddings initialized successfully.")
        return hf_embeddings
    except Exception as e:
        print(f"ERROR: Exception caught during HuggingFaceEmbeddings initialization: {e}")
        
    
def get_collection():
    client = mongo_connection_url()
    db = client[db_name]
    return db[collection_name]
    

def add_documents(chunks:list[Document], file_name:str):  
    embedding_model = set_embedding_model()
    st.toast("embedding model set")
    collection=get_collection()
    st.toast("collection set")
    for chunk in chunks:
        chunk.metadata['file_name'] = file_name
    st.toast("metadata updated")
    vector_store = MongoDBAtlasVectorSearch(
    embedding=embedding_model,
    collection= collection,
    index_name=search_index,
    relevance_score_fn="cosine",
    embedding_key="vector_embedding")

    docs = [Document(page_content=chunk.page_content,metadata=chunk.metadata) for chunk in chunks] 
    vector_store.add_documents(docs)

def delete_file(file_name: str):
    collection = get_collection()
    result = collection.delete_many({"file_name": file_name})
    if result.deleted_count > 0:
        print(f"Deleted {result.deleted_count} chunks for file: {file_name}")
    else:
        print(f"No chunks found to delete for file: {file_name}")


def cleanup():
    collection = get_collection()
    store_db = set(collection.distinct("file_name"))
    return store_db

            
    
