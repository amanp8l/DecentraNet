from fastapi import FastAPI, Depends
from web3 import Web3
from config import web3, CONTRACT_ADDRESS
import json
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI()

# Load contract ABI (you'll get this after compiling the contract)
with open('smart_contract/build/contracts/PostStorage.json') as f:
    contract_json = json.load(f)
    CONTRACT_ABI = contract_json['abi']

contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

class PostCreate(BaseModel):
    user_id: int
    title: str
    content: str
    paper_link: Optional[str] = None

@app.post("/create-post/")
async def create_post(post: PostCreate):
    # Build transaction
    transaction = contract.functions.createPost(
        post.title,
        post.content,
        post.paper_link or ""
    ).build_transaction({
        'from': ACCOUNT_ADDRESS,
        'gas': 2000000,
        'gasPrice': web3.eth.gas_price,
        'nonce': web3.eth.get_transaction_count(ACCOUNT_ADDRESS),
    })
    
    # Sign and send transaction
    signed_txn = web3.eth.account.sign_transaction(transaction, PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    
    # Wait for transaction receipt
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    
    return {"message": "Post created successfully", "transaction_hash": receipt['transactionHash'].hex()}

@app.get("/read-all-posts/")
async def read_all_posts():
    # Get total number of posts
    posts = contract.functions.getAllPosts().call()
    
    # Format posts
    formatted_posts = []
    for post in posts:
        post_dict = {
            "post_id": post[0],
            "author": post[1],
            "title": post[2],
            "content": post[3],
            "paper_link": post[4],
            "timestamp": post[5],
            "upvotes": contract.functions.postUpvotes(post[0]).call(),
        }
        formatted_posts.append(post_dict)
    
    return formatted_posts