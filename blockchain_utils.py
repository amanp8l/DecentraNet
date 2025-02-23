from web3 import Web3
from eth_account import Account
import json
import hashlib
from typing import Dict, Any

class BlockchainManager:
    def __init__(self):
        # Connect to local Ethereum node (replace with your provider URL)
        self.w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
        
        # Load contract ABI and address
        with open('SocialNetwork.json', 'r') as f:
            contract_data = json.load(f)
        
        self.contract = self.w3.eth.contract(
            address=contract_data['address'],
            abi=contract_data['abi']
        )
        
    def hash_content(self, content: Dict[str, Any]) -> str:
        """Create a hash of the content to store on blockchain"""
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    async def store_post_on_chain(self, post_data: Dict[str, Any], private_key: str) -> str:
        """Store post hash on blockchain"""
        try:
            # Create content hash
            content_hash = self.hash_content(post_data)
            
            # Get account from private key
            account = Account.from_key(private_key)
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(account.address)
            
            # Create the transaction
            transaction = self.contract.functions.createPost(content_hash).build_transaction({
                'from': account.address,
                'nonce': nonce,
                'gas': 2000000,
                'gasPrice': self.w3.eth.gas_price
            })
            
            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            return content_hash
            
        except Exception as e:
            raise Exception(f"Failed to store post on blockchain: {str(e)}")
    
    async def verify_post(self, post_id: int, content: Dict[str, Any]) -> bool:
        """Verify if post content matches blockchain hash"""
        try:
            # Get post from blockchain
            chain_post = self.contract.functions.getPost(post_id).call()
            
            # Calculate hash of current content
            current_hash = self.hash_content(content)
            
            # Compare hashes
            return chain_post[2] == current_hash
            
        except Exception as e:
            raise Exception(f"Failed to verify post: {str(e)}")

# Modified FastAPI endpoint
@app.post("/create-post/")
async def create_post(
    post: PostCreate,
    private_key: str = Header(None),
    conn=Depends(get_db)
):
    cursor = conn.cursor()
    
    # First store in SQLite
    cursor.execute("""
        INSERT INTO post (user_id, title, content, paper_link)
        VALUES (?, ?, ?, ?)
    """, (post.user_id, post.title, post.content, post.paper_link))
    post_id = cursor.lastrowid
    conn.commit()
    
    # Then store hash on blockchain
    if private_key:
        try:
            blockchain_manager = BlockchainManager()
            post_data = {
                "post_id": post_id,
                "user_id": post.user_id,
                "title": post.title,
                "content": post.content,
                "paper_link": post.paper_link
            }
            
            content_hash = await blockchain_manager.store_post_on_chain(post_data, private_key)
            
            # Update post with blockchain reference
            cursor.execute("""
                UPDATE post 
                SET blockchain_hash = ?
                WHERE post_id = ?
            """, (content_hash, post_id))
            conn.commit()
            
        except Exception as e:
            # Log error but don't fail the post creation
            print(f"Blockchain storage failed: {str(e)}")
    
    return {"message": "Post created successfully", "post_id": post_id}

# Add verification endpoint
@app.get("/verify-post/{post_id}")
async def verify_post(post_id: int, conn=Depends(get_db)):
    cursor = conn.cursor()
    
    # Get post data
    cursor.execute("SELECT * FROM post WHERE post_id = ?", (post_id,))
    post = cursor.fetchone()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    post_dict = dict(post)
    
    try:
        blockchain_manager = BlockchainManager()
        is_verified = await blockchain_manager.verify_post(post_id, post_dict)
        return {"verified": is_verified}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))