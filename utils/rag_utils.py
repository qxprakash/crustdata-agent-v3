import os
import dotenv
from time import time
from langchain_text_splitters import RecursiveCharacterTextSplitter
import streamlit as st

from langchain_community.document_loaders.text import TextLoader
from langchain_community.document_loaders import (
    WebBaseLoader,
    PyPDFLoader,
    Docx2txtLoader,
)

# pip install docx2txt, pypdf
from langchain_pinecone import PineconeVectorStore
from pinecone.grpc import PineconeGRPC as Pinecone
from langchain_openai import OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

from utils.prompts import RAG_PROMPT
from utils.notion_loader import NotionLoader
import pinecone

dotenv.load_dotenv()

os.environ["USER_AGENT"] = "myagent"
DB_DOCS_LIMIT = 10


# Function to stream the response of the LLM
def stream_llm_response(llm_stream, messages):
    response_message = ""

    for chunk in llm_stream.stream(messages):
        response_message += chunk.content
        yield chunk.content  # Changed to yield just the content

    # Store the complete message after streaming
    st.session_state.messages.append({"role": "assistant", "content": response_message})


# --- Indexing Phase ---


def load_doc_to_db():
    # Use loader according to doc type
    if "rag_docs" in st.session_state and st.session_state.rag_docs:
        docs = []
        for doc_file in st.session_state.rag_docs:
            if doc_file.name not in st.session_state.rag_sources:
                if len(st.session_state.rag_sources) < DB_DOCS_LIMIT:
                    os.makedirs("source_files", exist_ok=True)
                    file_path = f"./source_files/{doc_file.name}"
                    with open(file_path, "wb") as file:
                        file.write(doc_file.read())

                    try:
                        if doc_file.type == "application/pdf":
                            loader = PyPDFLoader(file_path)
                        elif doc_file.name.endswith(".docx"):
                            loader = Docx2txtLoader(file_path)
                        elif doc_file.type in ["text/plain", "text/markdown"]:
                            loader = TextLoader(file_path)
                        else:
                            st.warning(f"Document type {doc_file.type} not supported.")
                            continue
                        data = loader.load()
                        print(f"docs for url --> {doc_file.name}: {data[0]}")
                        docs.extend(data)
                        st.session_state.rag_sources.append(doc_file.name)

                    except Exception as e:
                        st.toast(
                            f"Error loading document {doc_file.name}: {e}", icon="⚠️"
                        )
                        print(f"Error loading document {doc_file.name}: {e}")

                    finally:
                        os.remove(file_path)

                else:
                    st.error(f"Maximum number of documents reached ({DB_DOCS_LIMIT}).")

        if docs:
            _split_and_load_docs(docs)
            st.toast(
                f"Document *{str([doc_file.name for doc_file in st.session_state.rag_docs])[1:-1]}* loaded successfully.",
                icon="✅",
            )


# def load_url_to_db():
#     if "rag_url" in st.session_state and st.session_state.rag_url:
#         url = st.session_state.rag_url
#         docs = []
#         if url not in st.session_state.rag_sources:
#             if len(st.session_state.rag_sources) < 10:
#                 try:
#                     # Use custom loader for Notion URLs
#                     if "notion.site" in url:
#                         print("Using NotionLoader for URL:", url)
#                         loader = NotionLoader(url, cache_enabled=True)
#                     else:
#                         print("Using WebBaseLoader for URL:", url)
#                         loader = WebBaseLoader(url)

#                     data = loader.load()
#                     if not data:
#                         raise Exception("No content could be extracted from the URL")

#                     docs.extend(data)
#                     st.session_state.rag_sources.append(url)

#                 except Exception as e:
#                     st.error(f"Error loading document from {url}: {e}")
#                     return

#                 if docs:
#                     _split_and_load_docs(docs)
#                     st.toast(
#                         f"Document from URL *{url}* loaded successfully.", icon="✅"
#                     )
#             else:
#                 st.error("Maximum number of documents reached (10).")


def initialize_vector_db():
    """Initialize connection to cloud vector store"""
    try:
        # Initialize Pinecone with new client
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

        embeddings = OpenAIEmbeddings(api_key=st.session_state.openai_api_key)
        vector_store = PineconeVectorStore(
            index_name="serverless-index", embedding=embeddings
        )

        # Update session state to reflect documents are available
        st.session_state.rag_sources = ["Crustdata API Documentation"]
        return vector_store

    except Exception as e:
        st.error(f"Failed to initialize vector store: {e}")
        return None


def _split_and_load_docs(docs):
    """Split documents and add to vector store"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=5000,
        chunk_overlap=1000,
    )

    document_chunks = text_splitter.split_documents(docs)

    if "vector_db" not in st.session_state:
        st.session_state.vector_db = initialize_vector_db()

    if st.session_state.vector_db:
        try:
            st.session_state.vector_db.add_documents(document_chunks)
            # Add source to session state for UI display
            for doc in docs:
                source = doc.metadata.get("source", "Unknown Source")
                if source not in st.session_state.rag_sources:
                    st.session_state.rag_sources.append(source)
        except Exception as e:
            st.error(f"Failed to add documents to vector store: {e}")


def _get_context_retriever_chain(vector_db, llm):
    retriever = vector_db.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 3},  # Retrieve top 3 most relevant chunks
    )

    print("===================== get context retriever chain  ================")

    # Function to print retrieved documents
    def debug_and_retrieve(query):
        docs_with_scores = retriever.get_relevant_documents(query)
        print("\n=== Retrieved Documents for Query ===")
        print(f"Query: {query}")
        print(f"Number of Documents Retrieved: {len(docs_with_scores)}")
        for i, (doc) in enumerate(docs_with_scores, 1):
            print(f"\nDocument {i}:")
            print(f"Rank: {i}")
            print(f"Content: {doc.page_content}")  # Print entire content
            print(f"Metadata: {doc.metadata}")
            print(f"Source: {doc.metadata.get('source', 'Unknown')}")
            print("-" * 50)
        return [doc for doc in docs_with_scores]

    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name="messages"),
            ("user", "{input}"),
            ("user", RAG_PROMPT),
        ]
    )

    print(f"prompt for retriever: {prompt}")

    print(f"retriever: {retriever}")

    # Create the retriever chain
    retriever_chain = create_history_aware_retriever(
        llm,
        retriever,
        prompt,
    )

    # Call the debug function to log the retrieved documents
    st.session_state.retrieved_docs = debug_and_retrieve

    return retriever_chain


def get_conversational_rag_chain(llm, query):
    retriever_chain = _get_context_retriever_chain(st.session_state.vector_db, llm)
    print("\n=== Retriever Chain Output ===")
    print(f"Type: {type(retriever_chain)}")
    print(f"Content: {retriever_chain}")
    print("================================\n")

    print(f"last query ----> {query}")

    # Call the debug function to log the retrieved documents
    retrieved_docs = st.session_state.retrieved_docs(query)

    # Log the retrieved documents
    print("\n=== Retrieved Documents ===")
    # for i, doc in enumerate(retrieved_docs, 1):
    #     print(f"\nDocument {i}:")
    #     print(f"Content: {doc.page_content[:200]}...")  # Print first 200 characters
    #     print(f"Source: {doc.metadata.get('source', 'Unknown')}")
    #     print("-" * 50)

    print(f"retrieved_docs: -------------------> {retrieved_docs}")
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a knowledgeable and helpful customer support agent for Crustdata. Your role is to assist users with technical questions about Crustdata’s APIs, providing accurate answers based on the official documentation and examples.

    If a user asks about API functionality, provide detailed explanations with example requests.
    If a user encounters errors, help troubleshoot and suggest solutions or resources.
    Be conversational and allow follow-up questions.
    Reference and validate any specific requirements or resources, such as standardized region values or API behavior.
    Always provide clear, concise, and actionable responses.

    Focus on delivering accurate information and guiding users effectively to achieve their goals with Crustdata’s APIs.

    {context}""",
            ),
            MessagesPlaceholder(variable_name="messages"),
            ("user", "{input}"),
        ]
    )

    stuff_documents_chain = create_stuff_documents_chain(llm, prompt)

    return create_retrieval_chain(retriever_chain, stuff_documents_chain)


def stream_llm_rag_response(llm_stream, messages):
    print("\n=== RAG Request Started ===")
    print(f"User Query: {messages[-1].content}")

    last_query = messages[-1].content
    conversation_rag_chain = get_conversational_rag_chain(llm_stream, last_query)
    response_message = "*(RAG Response)*\n"

    start_time = time()

    for chunk in conversation_rag_chain.pick("answer").stream(
        {"messages": messages[:-1], "input": messages[-1].content}
    ):
        response_message += chunk
        yield chunk

    # Store the complete message after streaming
    st.session_state.messages.append({"role": "assistant", "content": response_message})

    print(f"\nTotal RAG processing time: {time() - start_time:.2f} seconds")
    print("=== RAG Request Completed ===\n")
