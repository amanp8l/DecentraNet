from fastapi import FastAPI, WebSocket, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import sqlite3
import shutil
import os
from fastapi.responses import HTMLResponse
from pathlib import Path
import requests # type: ignore
import json
from dotenv import load_dotenv

app = FastAPI()
load_dotenv()
# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SQLite Database Connection
def get_db():
    conn = sqlite3.connect("social_network.db")
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    try:
        yield conn
    finally:
        conn.close()

class ConnectionManager:
    def __init__(self):
        # Dictionary to store websocket connections for each user
        self.active_connections: Dict[int, WebSocket] = {}
        
    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        
    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            
    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)

    async def gconnect(self, websocket: WebSocket, group_id: int):
        await websocket.accept()
        if group_id not in self.active_connections:
            self.active_connections[group_id] = []
        self.active_connections[group_id].append(websocket)
        print(f"New connection in group {group_id}. Total connections: {len(self.active_connections[group_id])}")

    async def gdisconnect(self, websocket: WebSocket, group_id: int):
        if group_id in self.active_connections:
            self.active_connections[group_id].remove(websocket)
            print(f"Connection removed from group {group_id}. Remaining connections: {len(self.active_connections[group_id])}")
            if not self.active_connections[group_id]:
                del self.active_connections[group_id]

    async def broadcast_to_group(self, message: str, group_id: int):
        if group_id in self.active_connections:
            print(f"Broadcasting to group {group_id}. Message: {message[:50]}...")
            for connection in self.active_connections[group_id]:
                try:
                    await connection.send_text(message)
                    print(f"Message sent successfully to a connection in group {group_id}")
                except Exception as e:
                    print(f"Error sending message: {e}")
                    await self.disconnect(connection, group_id)

manager = ConnectionManager()

# Initialize Database Tables
def init_db():
    conn = sqlite3.connect("social_network.db")
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS user (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT NOT NULL,
            metamask_id TEXT UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            bio TEXT,
            avatar TEXT,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS post (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            content TEXT,
            paper_link TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user(user_id)
        );
        CREATE TABLE IF NOT EXISTS comment (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES post(post_id),
            FOREIGN KEY (user_id) REFERENCES user(user_id)
        );
        CREATE TABLE IF NOT EXISTS upvote (
            upvote_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES post(post_id),
            FOREIGN KEY (user_id) REFERENCES user(user_id)
        );
        CREATE TABLE IF NOT EXISTS follow (
            follow_id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id INTEGER,
            followee_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (follower_id) REFERENCES user(user_id),
            FOREIGN KEY (followee_id) REFERENCES user(user_id)
        );
        CREATE TABLE IF NOT EXISTS user_chat (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            read_status BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (sender_id) REFERENCES user(user_id),
            FOREIGN KEY (receiver_id) REFERENCES user(user_id)
        );
        CREATE TABLE IF NOT EXISTS group_details (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL,
            creator_user_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creator_user_id) REFERENCES user(user_id)
        );
        CREATE TABLE IF NOT EXISTS group_message (
            group_message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            group_id INTEGER,
            content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES user(user_id),
            FOREIGN KEY (group_id) REFERENCES group_details(group_id)
        );
    """)
    conn.commit()
    conn.close()

init_db()

# Pydantic Models
class UserCreate(BaseModel):
    Name: str
    metamask_id: str
    bio: Optional[str] = None
    avatar: Optional[str] = None
    status: Optional[str] = None

class PostCreate(BaseModel):
    user_id: int
    title: str
    content: str
    paper_link: Optional[str] = None

class CommentCreate(BaseModel):
    post_id: int
    user_id: int
    content: str

class UpvoteCreate(BaseModel):
    post_id: int
    user_id: int

class GroupCreate(BaseModel):
    group_name: str
    creator_user_id: int

class MessageCreate(BaseModel):
    sender_id: int
    receiver_id: int
    content: str

class GroupMessageCreate(BaseModel):
    sender_id: int
    group_id: int
    content: str

# API Endpoints

@app.post("/create-profile/")
def create_profile(user: UserCreate, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user (Name, metamask_id, bio, avatar, status)
        VALUES (?, ?, ?, ?, ?)
    """, (user.Name, user.metamask_id, user.bio, user.avatar, user.status))
    conn.commit()
    return {"message": "Profile created successfully"}

@app.put("/update-profile/{user_id}")
def update_profile(user_id: int, user: UserCreate, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user
        SET Name = ?, metamask_id = ?, bio = ?, avatar = ?, status = ?
        WHERE user_id = ?
    """, (user.Name, user.metamask_id, user.bio, user.avatar, user.status, user_id))
    conn.commit()
    return {"message": "Profile updated successfully"}

@app.get("/get-user-id/")
def get_user_id(metamask_id: str, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM user WHERE metamask_id = ?", (metamask_id,))
    result = cursor.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": result[0]}

@app.get("/read-profile/{user_id}")
def read_profile(user_id: str, conn=Depends(get_db)):  # Change `int` to `str`
    cursor = conn.cursor()

    # Fetch user details
    cursor.execute("SELECT * FROM user WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Calculate total engagement (likes + comments) for the user's posts
    cursor.execute("""
        SELECT 
            COUNT(c.comment_id) AS total_comments,
            COUNT(u.upvote_id) AS total_upvotes
        FROM post p
        LEFT JOIN comment c ON p.post_id = c.post_id
        LEFT JOIN upvote u ON p.post_id = u.post_id
        WHERE p.user_id = ?
    """, (user_id,))
    engagement_data = cursor.fetchone()

    total_comments = engagement_data["total_comments"] if engagement_data["total_comments"] else 0
    total_upvotes = engagement_data["total_upvotes"] if engagement_data["total_upvotes"] else 0
    total_engagement = total_comments + total_upvotes

    # Convert user data to a dictionary and add the engagement field
    user_dict = dict(user)
    user_dict["engagement"] = total_engagement

    return user_dict

@app.get("/get-user-id/")
def get_user_id(metamask_id: str, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM user WHERE metamask_id = ?", (metamask_id,))
    result = cursor.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": result[0]}

@app.post("/create-post/")
def create_post(post: PostCreate, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO post (user_id, title, content, paper_link)
        VALUES (?, ?, ?, ?)
    """, (post.user_id, post.title, post.content, post.paper_link))
    conn.commit()
    return {"message": "Post created successfully"}

@app.put("/edit-post/{post_id}")
def edit_post(post_id: int, post: PostCreate, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE post
        SET title = ?, content = ?, paper_link = ?
        WHERE post_id = ?
    """, (post.title, post.content, post.paper_link, post_id))
    conn.commit()
    return {"message": "Post updated successfully"}

@app.get("/read-post/{post_id}")
def read_post(post_id: int, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, COUNT(c.comment_id) AS comment_count, COUNT(u.upvote_id) AS upvote_count
        FROM post p
        LEFT JOIN comment c ON p.post_id = c.post_id
        LEFT JOIN upvote u ON p.post_id = u.post_id
        WHERE p.post_id = ?
        GROUP BY p.post_id
    """, (post_id,))
    post = cursor.fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return dict(post)

@app.get("/read-all-posts/")
def read_all_posts(conn=Depends(get_db)):
    cursor = conn.cursor()
    
    # Query to fetch posts with user_name, comment_count, upvote_count, and comments list
    cursor.execute("""
        SELECT 
            p.post_id,
            p.title,
            p.content,
            p.paper_link,
            p.created_at AS post_created_at,
            u.Name AS user_name,
            COUNT(DISTINCT c.comment_id) AS comment_count,
            COUNT(DISTINCT up.upvote_id) AS upvote_count
        FROM post p
        LEFT JOIN user u ON p.user_id = u.user_id
        LEFT JOIN comment c ON p.post_id = c.post_id
        LEFT JOIN upvote up ON p.post_id = up.post_id
        GROUP BY p.post_id
    """)
    posts = cursor.fetchall()

    # Fetch comments for each post
    posts_with_comments = []
    for post in posts:
        post_dict = dict(post)
        
        # Fetch all comments for the current post
        cursor.execute("""
            SELECT 
                c.comment_id,
                c.content AS comment_content,
                c.created_at AS comment_created_at,
                u.Name AS commenter_name
            FROM comment c
            LEFT JOIN user u ON c.user_id = u.user_id
            WHERE c.post_id = ?
        """, (post_dict["post_id"],))
        comments = cursor.fetchall()
        
        # Add comments to the post dictionary
        post_dict["comments"] = [dict(comment) for comment in comments]
        
        # Append the enriched post to the final list
        posts_with_comments.append(post_dict)

    return posts_with_comments

@app.post("/create-upvote/")
def create_upvote(upvote: UpvoteCreate, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO upvote (post_id, user_id)
        VALUES (?, ?)
    """, (upvote.post_id, upvote.user_id))
    conn.commit()
    return {"message": "Upvote created successfully"}

@app.delete("/delete-upvote/{upvote_id}")
def delete_upvote(upvote_id: int, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM upvote WHERE upvote_id = ?", (upvote_id,))
    conn.commit()
    return {"message": "Upvote deleted successfully"}

@app.post("/create-comment/")
def create_comment(comment: CommentCreate, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO comment (post_id, user_id, content)
        VALUES (?, ?, ?)
    """, (comment.post_id, comment.user_id, comment.content))
    conn.commit()
    return {"message": "Comment created successfully"}

@app.post("/create-group/")
def create_group(group: GroupCreate, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO group_details (group_name, creator_user_id)
        VALUES (?, ?)
    """, (group.group_name, group.creator_user_id))
    conn.commit()
    return {"message": "Group created successfully"}

# WebSocket for Chat
@app.websocket("/ws/chat/{current_user_id}/{selected_user_id}")
async def websocket_chat(websocket: WebSocket, current_user_id: int, selected_user_id: int):
    # Connect the current user
    await manager.connect(current_user_id, websocket)
    try:
        while True:
            # Receive message from current user
            data = await websocket.receive_text()
            
            # Format the message
            formatted_message = f"User {current_user_id}: {data}"
            
            # Send to selected user if they're connected
            await manager.send_personal_message(data, selected_user_id)
            
    except WebSocketDisconnect:
        manager.disconnect(current_user_id)

@app.websocket("/ws/group-chat/{group_id}")
async def websocket_group_chat(websocket: WebSocket, group_id: int):
    print(f"New WebSocket connection request for group {group_id}")
    await manager.gconnect(websocket, group_id)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received message in group {group_id}: {data[:50]}...")
            # Ensure the message is valid JSON
            try:
                parsed_data = json.loads(data)
                # Add server timestamp if not present
                if 'timestamp' not in parsed_data:
                    parsed_data['timestamp'] = datetime.datetime.now().isoformat()
                data = json.dumps(parsed_data)
            except json.JSONDecodeError:
                print("Invalid JSON received")
                continue
            
            await manager.broadcast_to_group(data, group_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await manager.gdisconnect(websocket, group_id)



@app.get("/api/users")
def get_all_users(conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, Name FROM user")
    users = cursor.fetchall()
    # Convert rows to a list of dictionaries
    user_list = [{"user_id": user["user_id"], "Name": user["Name"]} for user in users]
    return user_list


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Mount the uploads directory to serve files statically
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.post("/upload-file/")
async def upload_file(
    file: UploadFile = File(...),
    sender_id: int = Form(...),
    receiver_id: int = Form(...)
):
    try:
        # Create a safe filename to prevent directory traversal
        safe_filename = Path(file.filename).name
        file_path = UPLOAD_DIR / safe_filename

        # Save the uploaded file
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Return the relative file URL
        file_url = f"/uploads/{safe_filename}"
        
        return {
            "status": "success",
            "file_url": file_url,
            "file_name": safe_filename,
            "message": "File uploaded successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Optional: Add an endpoint to check if file exists
@app.get("/uploads/{filename}")
async def get_file(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)




OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

class QueryRequest(BaseModel):
    pdf_url: str
    question: str

@app.post("/query")
def query_pdf(request: QueryRequest):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are an AI assistant that extracts relevant answers from urls."},
            {"role": "user", "content": f"Extract the answer to this question from the {request.pdf_url}: {request.question}"}
        ]
    }
    
    response = requests.post(OPENAI_API_URL, json=payload, headers=headers)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    
    return response.json()


# pages

@app.get("/chat/")
async def get():
    with open("chat.html", "r") as f:
        return HTMLResponse(content=f.read())
    

@app.get("/profile/")
async def get():
    with open("profile.html", "r") as f:
        return HTMLResponse(content=f.read())
    
@app.get("/create-post/")
async def get():
    with open("create-post.html", "r") as f:
        return HTMLResponse(content=f.read())
    
@app.get("/group-chat/")
async def get():
    with open("group-chat.html", "r") as f:
        return HTMLResponse(content=f.read())
    
@app.get("/")
async def get():
    with open("index.html", "r") as f:
        return HTMLResponse(content=f.read())
    
@app.get("/ask-ai/")
async def get():
    with open("ask-ai.html", "r") as f:
        return HTMLResponse(content=f.read())
    
@app.get("/scripts.js")
async def get():
    with open("scripts.js", "r") as f:
        return HTMLResponse(content=f.read())


    