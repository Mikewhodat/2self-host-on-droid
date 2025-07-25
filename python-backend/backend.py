from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import chromadb
from chromadb.config import Settings
import uuid
from datetime import datetime
import os

app = FastAPI(title="Blog Backend API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class BlogPost(BaseModel):
    title: str
    content: str
    author: str

class BlogPostResponse(BaseModel):
    id: str
    title: str
    content: str
    author: str
    created_at: str

# Embedded ChromaDB config
try:
    chroma_client = chromadb.Client(
        Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory="/data/chroma",
            allow_reset=True
        )
    )

    collection = chroma_client.get_or_create_collection(
        name="blog_posts",
        metadata={"description": "Collection for blog posts"}
    )
    print(f"✅ Embedded ChromaDB initialized at /data/chroma")

except Exception as e:
    print(f"❌ Failed to initialize ChromaDB: {e}")
    chroma_client = None
    collection = None

@app.get("/")
async def root():
    return {"message": "Blog Backend API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    chromadb_status = "connected" if chroma_client else "disconnected"
    return {
        "status": "healthy",
        "chromadb": chromadb_status,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/blog", response_model=BlogPostResponse)
async def create_blog_post(post: BlogPost):
    if not collection:
        raise HTTPException(status_code=503, detail="ChromaDB not available")
    try:
        post_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        metadata = {
            "title": post.title,
            "author": post.author,
            "created_at": created_at,
            "type": "blog_post"
        }
        collection.add(
            documents=[post.content],
            metadatas=[metadata],
            ids=[post_id]
        )
        return BlogPostResponse(
            id=post_id,
            title=post.title,
            content=post.content,
            author=post.author,
            created_at=created_at
        )
    except Exception as e:
        print(f"Error creating blog post: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create blog post: {str(e)}")

@app.get("/blog", response_model=List[BlogPostResponse])
async def get_blog_posts():
    if not collection:
        raise HTTPException(status_code=503, detail="ChromaDB not available")
    try:
        results = collection.get()
        if not results["ids"]:
            return []
        blog_posts = []
        for i, post_id in enumerate(results["ids"]):
            metadata = results["metadatas"][i]
            content = results["documents"][i]
            blog_posts.append(BlogPostResponse(
                id=post_id,
                title=metadata.get("title", "Untitled"),
                content=content,
                author=metadata.get("author", "Anonymous"),
                created_at=metadata.get("created_at", datetime.now().isoformat())
            ))
        blog_posts.sort(key=lambda x: x.created_at, reverse=True)
        return blog_posts
    except Exception as e:
        print(f"Error retrieving blog posts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve blog posts: {str(e)}")

@app.delete("/blog/{post_id}")
async def delete_blog_post(post_id: str):
    if not collection:
        raise HTTPException(status_code=503, detail="ChromaDB not available")
    try:
        result = collection.get(ids=[post_id])
        if not result["ids"]:
            raise HTTPException(status_code=404, detail="Blog post not found")
        collection.delete(ids=[post_id])
        return {"message": "Blog post deleted successfully", "id": post_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting blog post: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete blog post: {str(e)}")

@app.get("/blog/search")
async def search_blog_posts(query: str, limit: int = 10):
    if not collection:
        raise HTTPException(status_code=503, detail="ChromaDB not available")
    try:
        results = collection.query(
            query_texts=[query],
            n_results=limit
        )
        if not results["ids"] or not results["ids"][0]:
            return []
        blog_posts = []
        for i, post_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i]
            content = results["documents"][0][i]
            blog_posts.append(BlogPostResponse(
                id=post_id,
                title=metadata.get("title", "Untitled"),
                content=content,
                author=metadata.get("author", "Anonymous"),
                created_at=metadata.get("created_at", datetime.now().isoformat())
            ))
        return blog_posts
    except Exception as e:
        print(f"Error searching blog posts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search blog posts: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
