import os
from pathlib import Path
import sys
import json
from pinecone import Pinecone
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore
import pinecone
from pinecone.grpc import PineconeGRPC as Pinecone
from pinecone import ServerlessSpec

load_dotenv()
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)


def build_and_upload_index():
    # Initialize Pinecone with new syntax
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

    # Create index if it doesn't exist
    index_name = "crustdata-docs"
    print(f"crust data docs index: {pc.list_indexes().names()}")
    # if index_name not in pc.list_indexes().names():
    # pc.create_index(
    #     name="serverless-index",
    #     dimension=1536,
    #     metric="cosine",
    #     spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    # )

    # Load documents from data/content directory and their corresponding metadata
    content_dir = Path("data/content")
    metadata_dir = Path("data/metadata")
    docs = []

    for file_path in content_dir.glob("*.txt"):
        # Load content
        loader = TextLoader(str(file_path))
        content_docs = loader.load()

        # Load corresponding metadata
        metadata_path = metadata_dir / f"{file_path.stem}.json"
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
                # Update metadata for each document
                for doc in content_docs:
                    doc.metadata.update(metadata)

        docs.extend(content_docs)

    # Split documents
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=5000,
        chunk_overlap=1000,
    )
    splits = text_splitter.split_documents(docs)

    # Create embeddings and upload to Pinecone
    embeddings = OpenAIEmbeddings()
    vector_store = PineconeVectorStore.from_documents(
        documents=splits,
        embedding=embeddings,
        index_name="serverless-index",
    )

    print(f"Successfully uploaded {len(splits)} document chunks to Pinecone")


if __name__ == "__main__":
    build_and_upload_index()
