import os
from cosmpy.aerial.wallet import LocalWallet
from cosmpy.aerial.client import LedgerClient, NetworkConfig
from cosmpy.aerial.tx import Transaction
from cosmpy.crypto.keypairs import PrivateKey
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Corrected Babylon Testnet configuration
BABYLON_CONFIG = NetworkConfig(
    chain_id=os.getenv("BABYLON_CHAIN_ID", "babylon-2"),
    url=os.getenv("BABYLON_RPC_URL", "rest+https://rpc.babylon-2.btc.com"),  # Added rest+ prefix
    fee_minimum_gas_price=float(os.getenv("GAS_PRICE", 0.0025)),
    fee_denomination=os.getenv("DENOM", "ubbn"),
    staking_denomination=os.getenv("DENOM", "ubbn"),
)

def get_wallet_from_seed(seed_phrase):
    """Create wallet from seed phrase"""
    private_key = PrivateKey.from_mnemonic(seed_phrase)
    return LocalWallet(private_key)

def get_balance(client, address):
    """Get Babylon token balance"""
    return client.query_bank_balance(address)

def send_tokens(client, sender_wallet, recipient, amount, leave_amount=0.1):
    """Send tokens between wallets"""
    balance = get_balance(client, sender_wallet.address())
    if balance <= leave_amount:
        print(f"⚠️ Insufficient balance (has {balance}, needs {leave_amount})")
        return False
    
    amount_to_send = min(amount, balance - leave_amount)
    tx = Transaction()
    tx.add_bank_transfer(recipient, amount_to_send, "ubbn")
    
    tx = client.finalize_and_broadcast(tx, sender_wallet)  # Fixed typo in method name
    print(f"✅ Sent {amount_to_send}ubbn to {recipient[:10]}...")
    print(f"   Tx Hash: {tx.tx_hash}")
    return True

def many_to_one(client):
    """Consolidate funds from multiple wallets"""
    print("\n🔀 MANY-TO-ONE TRANSFER MODE")
    try:
        with open("seed.txt") as f:
            seeds = [s.strip() for s in f.readlines() if s.strip()]
    except FileNotFoundError:
        print("❌ seed.txt not found")
        return
    
    recipient = input("Enter recipient address: ").strip()
    for seed in seeds:
        try:
            wallet = get_wallet_from_seed(seed)  # Fixed typo in method name
            balance = get_balance(client, wallet.address())
            print(f"\n🏦 Wallet: {wallet.address()}")
            print(f"   Balance: {balance}ubbn")
            if balance > 0.1:
                send_tokens(client, wallet, recipient, balance)
        except Exception as e:
            print(f"❌ Error: {str(e)}")

def one_to_many(client):
    """Distribute funds to multiple wallets"""
    print("\n🔀 ONE-TO-MANY TRANSFER MODE")
    sender_seed = input("Enter sender seed phrase: ").strip()
    try:
        with open("wallet.txt") as f:
            recipients = [r.strip() for r in f.readlines() if r.strip()]
    except FileNotFoundError:
        print("❌ wallet.txt not found")
        return
    
    amount = float(input("Amount to send each: ").strip())
    wallet = get_wallet_from_seed(sender_seed)
    total = amount * len(recipients)
    balance = get_balance(client, wallet.address())
    
    print(f"\n👤 Sender: {wallet.address()}")
    print(f"   Balance: {balance}ubbn | Needed: {total}ubbn")
    
    if balance < total + 0.1:
        print("❌ Insufficient funds")
        return
    
    for addr in recipients:
        send_tokens(client, wallet, addr, amount)

def main():
    client = LedgerClient(BABYLON_CONFIG)
    print("\n" + "="*40)
    print(" BABYLON-2 TOKEN TRANSFER BOT")
    print("="*40)
    
    while True:
        print("\n1. Many wallets → One wallet (Consolidate)")
        print("2. One wallet → Many wallets (Distribute)")
        print("3. Exit")
        choice = input("Select mode (1-3): ").strip()
        
        if choice == "1":
            many_to_one(client)
        elif choice == "2":
            one_to_many(client)
        elif choice == "3":
            print("👋 Exiting...")
            break
        else:
            print("❌ Invalid choice")

if __name__ == "__main__":
    main()
