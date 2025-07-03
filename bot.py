import os
import requests
from cosmpy.aerial.wallet import LocalWallet
from cosmpy.aerial.client import LedgerClient, NetworkConfig
from cosmpy.aerial.tx import Transaction
from cosmpy.crypto.keypairs import PrivateKey
from bip32utils import BIP32Key
from mnemonic import Mnemonic
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Babylon Testnet RPC endpoints (will try each in order)
RPC_ENDPOINTS = [
    "https://rpc.babylon-2.btc.com",
    "https://babylon-testnet-rpc.polkachu.com",
    "https://babylon-testnet-rpc.nodes.guru"
]

def get_working_rpc():
    """Test RPC endpoints and return first working one"""
    for endpoint in RPC_ENDPOINTS:
        try:
            response = requests.get(f"{endpoint}/status", timeout=5)
            if response.status_code == 200:
                print(f"✅ Connected to RPC: {endpoint}")
                return endpoint
            print(f"⚠️ RPC endpoint {endpoint} returned status {response.status_code}")
        except Exception as e:
            print(f"⚠️ Could not connect to {endpoint}: {str(e)}")
    raise ConnectionError("❌ No working RPC endpoint found. Please check your internet connection.")

# Get working RPC configuration
working_rpc = get_working_rpc()
BABYLON_CONFIG = NetworkConfig(
    chain_id=os.getenv("BABYLON_CHAIN_ID", "babylon-2"),
    url=f"rest+{working_rpc}",
    fee_minimum_gas_price=float(os.getenv("GAS_PRICE", 0.0025)),
    fee_denomination=os.getenv("DENOM", "ubbn"),
    staking_denomination=os.getenv("DENOM", "ubbn"),
)

def get_wallet_from_seed(seed_phrase):
    """Create wallet from seed phrase using BIP39/BIP44 derivation"""
    try:
        mnemo = Mnemonic("english")
        seed = mnemo.to_seed(seed_phrase)
        bip32_root = BIP32Key.fromEntropy(seed)
        bip32_child = bip32_root.ChildKey(44 + 0x80000000) \
                               .ChildKey(118 + 0x80000000) \
                               .ChildKey(0 + 0x80000000) \
                               .ChildKey(0) \
                               .ChildKey(0)
        private_key = PrivateKey(bip32_child.PrivateKey())
        return LocalWallet(private_key)
    except Exception as e:
        raise Exception(f"Failed to create wallet from seed: {str(e)}")

def get_balance(client, address, retries=3, delay=2):
    """Get Babylon token balance with retry logic"""
    for attempt in range(retries):
        try:
            balance = client.query_bank_balance(address)
            return balance
        except Exception as e:
            if attempt == retries - 1:
                raise Exception(f"Failed to get balance after {retries} attempts: {str(e)}")
            print(f"⚠️ Balance query failed (attempt {attempt + 1}), retrying in {delay} seconds...")
            time.sleep(delay)

def send_tokens(client, sender_wallet, recipient, amount, leave_amount=0.1):
    """Send tokens between wallets with enhanced error handling"""
    try:
        balance = get_balance(client, sender_wallet.address())
        if balance <= leave_amount:
            print(f"⚠️ Insufficient balance (has {balance}, needs {leave_amount})")
            return False
        
        amount_to_send = min(amount, balance - leave_amount)
        tx = Transaction()
        tx.add_bank_transfer(recipient, amount_to_send, "ubbn")
        
        tx = client.finalize_and_broadcast(tx, sender_wallet)
        print(f"✅ Successfully sent {amount_to_send}ubbn to {recipient}")
        print(f"   Transaction Hash: {tx.tx_hash}")
        return True
    except Exception as e:
        print(f"❌ Failed to send tokens: {str(e)}")
        return False

def many_to_one(client):
    """Consolidate funds from multiple wallets to one"""
    print("\n🔀 MANY-TO-ONE TRANSFER MODE")
    try:
        with open("seed.txt") as f:
            seeds = [s.strip() for s in f.readlines() if s.strip()]
    except FileNotFoundError:
        print("❌ Error: seed.txt file not found")
        return
    
    if not seeds:
        print("❌ Error: No seed phrases found in seed.txt")
        return
    
    recipient = input("Enter recipient address: ").strip()
    if not recipient:
        print("❌ Error: No recipient address provided")
        return
    
    for seed in seeds:
        try:
            wallet = get_wallet_from_seed(seed)
            balance = get_balance(client, wallet.address())
            print(f"\n🏦 Processing wallet: {wallet.address()}")
            print(f"   Current balance: {balance}ubbn")
            
            if balance > 0.1:
                print(f"   Attempting to send {balance - 0.1}ubbn...")
                if not send_tokens(client, wallet, recipient, balance):
                    print("   ⚠️ Transaction failed, skipping this wallet")
            else:
                print("   ⚠️ Skipping - insufficient balance (less than 0.1 ubbn)")
        except Exception as e:
            print(f"❌ Error processing wallet: {str(e)}")
            continue

def one_to_many(client):
    """Distribute funds from one wallet to many"""
    print("\n🔀 ONE-TO-MANY TRANSFER MODE")
    sender_seed = input("Enter sender seed phrase: ").strip()
    if not sender_seed:
        print("❌ Error: No seed phrase provided")
        return
    
    try:
        with open("wallet.txt") as f:
            recipients = [r.strip() for r in f.readlines() if r.strip()]
    except FileNotFoundError:
        print("❌ Error: wallet.txt file not found")
        return
    
    if not recipients:
        print("❌ Error: No recipient addresses found in wallet.txt")
        return
    
    try:
        amount = float(input("Enter amount to send to each recipient (in ubbn): ").strip())
        if amount <= 0:
            print("❌ Error: Amount must be positive")
            return
    except ValueError:
        print("❌ Error: Invalid amount entered")
        return
    
    try:
        wallet = get_wallet_from_seed(sender_seed)
        sender_balance = get_balance(client, wallet.address())
        total_needed = amount * len(recipients)
        
        print(f"\n👤 Sender Wallet: {wallet.address()}")
        print(f"   Current Balance: {sender_balance}ubbn")
        print(f"   Required for Distribution: {total_needed}ubbn (to {len(recipients)} recipients)")
        
        if sender_balance < total_needed + 0.1:
            print("❌ Error: Insufficient funds (need to leave 0.1 ubbn)")
            return
        
        for i, addr in enumerate(recipients, 1):
            print(f"\nProcessing recipient {i}/{len(recipients)}: {addr}")
            if not send_tokens(client, wallet, addr, amount):
                print("⚠️ Failed to send to this recipient, continuing with others...")
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")

def main():
    try:
        client = LedgerClient(BABYLON_CONFIG)
        print("\n" + "="*40)
        print(" BABYLON-2 TOKEN TRANSFER BOT")
        print(f" Connected to: {working_rpc}")
        print("="*40)
        
        while True:
            print("\nMAIN MENU:")
            print("1. Consolidate funds (Many wallets → One wallet)")
            print("2. Distribute funds (One wallet → Many wallets)")
            print("3. Exit")
            
            choice = input("Select option (1-3): ").strip()
            
            if choice == "1":
                many_to_one(client)
            elif choice == "2":
                one_to_many(client)
            elif choice == "3":
                print("\n👋 Exiting the Babylon Token Transfer Bot")
                break
            else:
                print("❌ Invalid choice, please select 1, 2, or 3")
    except Exception as e:
        print(f"\n❌ Critical error: {str(e)}")
        print("Possible solutions:")
        print("- Check your internet connection")
        print("- Verify the RPC endpoint is available")
        print("- Ensure you're using valid seed phrases and addresses")
    finally:
        print("\nThank you for using the Babylon Token Transfer Bot!")

if __name__ == "__main__":
    main()
