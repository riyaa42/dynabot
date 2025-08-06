import os
from typing import TypedDict, List
from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, END
from langchain_community.vectorstores import MongoDBAtlasVectorSearch
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from db_utils import get_collection, set_embedding_model
import streamlit as st

class GraphState(TypedDict):
    query: str
    db_name: str
    selected_file_names: List[str]
    documents: List[Document]
    answer: str
    relevance_score: int
    retry_count: int
    search_kwargs: dict
    search_index_name: str
    initial_answer: str

def get_retriever(search_index_name: str, file_names_filter: List[str],k:int=5):
    embeddings = set_embedding_model()
    collection = get_collection()

    vector_store=MongoDBAtlasVectorSearch(
        collection=collection,
        embedding=embeddings,
        index_name=search_index_name,
        relevance_score_fn="cosine",
        embedding_key="vector_embedding"
    )

    retriever = vector_store.as_retriever(
        search_type="similarity",      
        search_kwargs={"k": k}          
    )

    return retriever

def retrieve_documents(state: GraphState) -> GraphState:
    query = state.get("query", "")
    selected_file_names = state.get("selected_file_names", [])
    search_index_name = state.get("search_index_name", "")

    k_value = state.get("search_kwargs", {}).get("k", 5)

    try:
        retriever = get_retriever(search_index_name, selected_file_names, k=k_value)
        mongo_filter = {"metadata.file_name": {"$in": selected_file_names}}
        documents = retriever.invoke(query, config={"search_kwargs": {"pre_filter": mongo_filter}})
       
        state["documents"] = documents
    except Exception as e:
        print(f"Error during document retrieval: {e}")
        state["documents"] = []
    st.toast("Retrieved documents for query")
    return state
    
def generate_answer(state: GraphState) -> GraphState:
    query = state.get("query", "")
    documents = state.get("documents", [])
    
    context = "\n\n".join([doc.page_content for doc in documents])
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3)
    
    prompt_template = ChatPromptTemplate.from_template(
        """You are a chatbot answering questions about documents uploaded by a user. Use the provided context to answer the question.
        You may infer reasonable conclusions if they logically follow from the context and extend the answer.
        Do not mention the existence of "context" or "document" in your response. Do not mention anything referring to the document provided
        The context you see has already been collected from the documents for you to answer questions from.
        Make your answer readable by utilizing bullet points whenever possible.

        Context: {context}
        Question: {query}
        Answer:"""
    )
    
    rag_chain = (
        prompt_template
        | llm
        | StrOutputParser()
    )
    
    try:
        answer = rag_chain.invoke({"query": query, "context": context})
        state["answer"] = answer
    
       
    except Exception as e:
        print(f"Error during answer generation: {e}")
        state["answer"] = "I apologize, but I encountered an error while generating the answer."
    st.toast("Generated answer for query")
 
    return state

def evaluate_answer(state: GraphState) -> dict:
  
    query = state.get("query", "")
    answer = state.get("answer", "")
    documents = state.get("documents", [])
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3)

    evaluation_prompt = ChatPromptTemplate.from_template(
      """You are an answer evaluator. Your task is to determine the relevance of a generated answer 
        to the user's query based on the provided documents that act as context. A relevant answer is something
        that is defined as fulfilling the user's query and being supported by the context. Rate the relevance
        on a scale from 1 (not relevant) to 10 (highly relevant).
        Respond with only the number.
        
        User Query: {query}
        Retrieved Documents: {documents}
        Generated Answer: {answer}

        Relevance Score (1-10):"""
    )
    
    evaluator = (evaluation_prompt | llm | StrOutputParser())
    
    try:
        if not documents:
            score=1
        else:
            raw_score = evaluator.invoke({"query": query, "documents": documents, "answer": answer}).strip()
            try:
                score = int(raw_score)
                score = max(1, min(10,score)) 
            except ValueError:
                score = 1
    except Exception as e:
        print(f"Error during answer evaluation: {e}")
        score=1

    print(f"Answer relevance score: {score}")
    state["relevance_score"] = score
    st.toast("Evaluated answer relevance")
    return state

def retry_counter(state: GraphState) -> GraphState:
   
    retry_count = state.get("retry_count", 0)
    
    
    state["retry_count"] = retry_count + 1
    st.toast("retry count increased")
    return state

def generate_better_prompt(state: GraphState) -> GraphState:
    query = state.get("query", "")
    documents = state.get("documents", [])
    retrieved_content = "\n\n".join([doc.page_content for doc in documents])
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.5)
    
    reprompt_template = ChatPromptTemplate.from_template(
      """You are a query re-writer. The initial retrieval for the user's query was unsuccessful.
        To help you, here is the original query and the content that was retrieved initially. Analyze the retrieved content to 
        get clues on the what the user might be looking for, and rephrase the original query to be more effective
         for a new retrieval attempt. Your goal is to find
        a query that is more specific and better suited for a vector search.
        Only return the rephrased query without any additional text.

        Original Query: {original_query}

        Initially Retrieved Content:
        {retrieved_content}

        Rephrased Query:"""
    )
    
    
    rephraser = (reprompt_template | llm | StrOutputParser())
    
    try:
        new_query = rephraser.invoke({"query": query}).strip()
        state["query"] = new_query
    except Exception as e:
        print(f"Error during prompt generation: {e}")
    st.toast("Generated better prompt for query")    
    print(f"NEW QUERY: {new_query}")
    return state

def expand_retrieval(state: GraphState) -> GraphState:
    current_k = state.get("search_kwargs", {}).get("k", 5)
    new_k = current_k + 5 
    
    state["search_kwargs"] = {"k": new_k}
    print(f"Expanding retrieval to k={new_k}")
    st.toast("Expanding retrieval docs")
    return state

def handle_failure(state: GraphState) -> GraphState:
    last_answer = state.get("initial_answer", "")
    state["answer"] = "I apologize, but I was unable to find a relevant answer in the uploaded file(s). Please try rephrasing your question for better results. "
    st.toast("bad answer.")
    return state
    
def pass_answer(state: GraphState) -> GraphState:
    st.toast("answer passed")
    return state

def build_rag_graph():
 
    workflow = StateGraph(GraphState)
    

    workflow.add_node("retrieve", retrieve_documents)
    workflow.add_node("generate", generate_answer)
    workflow.add_node("evaluate", evaluate_answer)
    workflow.add_node("retry_counter", retry_counter)
    workflow.add_node("rewrite_query", generate_better_prompt)
    workflow.add_node("expand_retrieval", expand_retrieval)
    workflow.add_node("handle_failure", handle_failure)
    workflow.add_node("pass_answer", pass_answer)
    
   
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "evaluate")
    
  
    workflow.add_conditional_edges(
        "evaluate",
        lambda state: "pass" if state["relevance_score"] > 5 else "fail",
        {
            "pass": "pass_answer",
            "fail": "retry_counter"
        }
    )
    
   
    workflow.add_conditional_edges(
        "retry_counter",
        lambda state: state["retry_count"], 
        {
            1: "rewrite_query",
            2: "expand_retrieval",
            3: "handle_failure"
        }
    )

    workflow.add_edge("rewrite_query", "retrieve")
    workflow.add_edge("expand_retrieval", "retrieve")
    
 
    workflow.add_edge("pass_answer", END)
    workflow.add_edge("handle_failure", END)

    app = workflow.compile()
    print("LangGraph RAG workflow with self-correction compiled successfully.")
    return app 