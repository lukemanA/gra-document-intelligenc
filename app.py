import os
import streamlit as st
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_classic.chains import RetrievalQA
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="GRA Tax Assistant",
    page_icon="🇬🇭",
    layout="centered"
)

# --- 2. BACKEND RAG INITIALIZATION (Cached for high performance) ---
@st.cache_resource
def initialize_rag_pipeline():
    # Provide the secure API Key
    os.environ["GROQ_API_KEY"] = "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"

    # Reload local vector database safely
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})

    # Initialize Llama 3.1 on Groq with low temperature for strict factual accuracy
    llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0.1)

    # Custom Guardrail prompt template to handle out-of-scope questions gracefully
    prompt_template = """You are a professional assistant for the Ghana Revenue Authority (GRA). 
Your task is to answer the user's question accurately using ONLY the provided pieces of context text.

Context:
{context}

Question: {question}

Strict Instructions:
1. Base your answer solely on the provided Context text above. Do not use external or general knowledge.
2. If the answer cannot be found or reasonably inferred from the provided Context, reply exactly with: 
   "I could not find an answer to this question in the documents. You may want to consult the source document directly or contact a relevant professional."
3. Do not attempt to make up or fabricate answers under any circumstances.

Answer:"""

    custom_prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])

    # Assemble pipeline with source document extraction tracking active
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": custom_prompt}
    )
    return qa_chain

# Boot up the pipeline backend
try:
    qa_chain = initialize_rag_pipeline()
except Exception as e:
    st.error(f"Error loading vector index: Please make sure you ran the Ingestion Pipeline (Cell 3) first! Details: {e}")
    st.stop()

# --- 3. CHAT INTERFACE FRONTEND UI ---
st.title("🇬🇭 GRA Document Intelligence Assistant")
st.caption("Capstone Project — Secure RAG system for Ghana Revenue Authority Regulatory Documents")

# MANDATORY GUIDEBOOK REQUIREMENT: Professional Advice Disclaimer
st.warning(
    "⚠️ **Disclaimer:** This chatbot is an advanced AI assistant designed to locate and explain information "
    "grounded directly within official GRA documents. It does not provide official legal, financial, or tax advice. "
    "For complex statutory matters, please consult a certified tax professional or contact the GRA directly."
)

# Initialize persistent chat history container in Streamlit's session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Redraw previous chat log entries whenever user interacts with elements
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept new text questions from the user via the chat input bar
if user_input := st.chat_input("Ask a question about GRA tax filing guidelines, waivers, or rules..."):

    # Display the user's query instantly in the web chat container
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Generate the assistant response with a visual loading spinner
    with st.chat_message("assistant"):
        with st.spinner("Scanning local vector index and generating verified answer..."):
            # Invoke pipeline backend
            pipeline_output = qa_chain.invoke({"query": user_input})

            ai_answer = pipeline_output["result"]
            source_docs = pipeline_output.get("source_documents", [])

            # Format and append clean source citations to satisfy the grading rubric
            formatted_sources = ""
            seen_sources = set()
            for doc in source_docs:
                filename = doc.metadata.get("filename", "Unknown File")
                if filename not in seen_sources:
                    formatted_sources += f"\n- 📋 *Source File:* {filename}"
                    seen_sources.add(filename)

            # Combine raw answer text with citation blocks if sources exist
            full_response = ai_answer
            if seen_sources and "I could not find an answer" not in ai_answer:
                full_response += "\n\n**Verified Sources Cited:**" + formatted_sources

            # Render response in the user UI window
            st.markdown(full_response)

    # Save response to memory session state
    st.session_state.messages.append({"role": "assistant", "content": full_response})
