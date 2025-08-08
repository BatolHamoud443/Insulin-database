import os
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from typing import List

# Load environment variables
load_dotenv()

# Directory for Chroma database
PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIR", "Data_Bot_1/chroma")

# Load embedding model
embedding_function = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Initialize Chroma vector store
vectorstore = Chroma(
    persist_directory=PERSIST_DIRECTORY,
    embedding_function=embedding_function,
)

def find_similar_chunks(query: str, k: int = 3) -> List[str]:
    """
    Search for top-k most relevant chunks in the vectorstore.

    Args:
        query (str): The input question or search query.
        k (int): Number of similar documents to retrieve.

    Returns:
        List of string chunks (page_content).
    """
    try:
        docs = vectorstore.similarity_search(query, k=k)
        return [doc.page_content for doc in docs]
    except Exception as e:
        print(f"❌ Error during vector search: {e}")
        return []

