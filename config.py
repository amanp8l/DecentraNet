from web3 import Web3
from dotenv import load_dotenv
import os

load_dotenv()

# Connect to local Ganache instance
WEB3_PROVIDER = os.getenv('WEB3_PROVIDER', 'http://127.0.0.1:8545')
web3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER))

# Your deployed contract address (you'll get this after deployment)
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS')

# Your account address and private key (from Ganache)
ACCOUNT_ADDRESS = os.getenv('ACCOUNT_ADDRESS')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')