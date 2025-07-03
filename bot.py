import os
from cosmpy.aerial.wallet import LocalWallet
from cosmpy.aerial.client import LedgerClient, NetworkConfig
from cosmpy.aerial.tx import Transaction
from cosmpy.crypto.keypairs import PrivateKey
from bip32utils import BIP32Key
from mnemonic import Mnemonic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Babylon Testnet configuration
BABYLON_CONFIG = NetworkConfig(
    chain_id=os.getenv("BABYLON_CHAIN_ID", "babylon-2"),
    url=os.getenv("BABYLON_RPC_URL", "rest+https://babylon-testnet-rpc.nodes.guru"),
    fee_minimum_gas_price=float(os.getenv("GAS_PRICE", 0.0025)),
    fee_denomination=os.getenv("DENOM", "ubbn"),
    staking_denomination=os.getenv("DENOM", "ubbn"),
)

def validate_babylon_address(address):
    """Validate Babylon testnet address format"""
    return address.startswith(("bbn1", "babylon1")) and len(address) == 45

def get_wallet_from_seed(seed_phrase):
    """Create wallet from seed phrase using BIP39/BIP44 derivation"""
    # Generate seed from mnemonic
    mnemo = Mnemonic("english")
    seed = mnemo.to_seed(seed_phrase)
    
    # Derive private key using Cosmos derivation path (44'/118'/0'/0/0)
    bip32_root = BIP32Key.fromEntropy(seed)
    bip32_child = bip32_root.ChildKey(44 + BIP32Key.HARDEN) \
                           .ChildKey(118 + BIP32Key.HARDEN) \
                           .ChildKey(0 + BIP32Key.HARDEN) \
                           .ChildKey(0) \
                           .ChildKey(0)
    private_key = PrivateKey(bip32_child.PrivateKey())
    return LocalWallet(private_key)

def get_balance(client, address):
    """Get Babylon token balance"""
    return client.query_bank_balance(address)

def send_tokens(client, sender_wallet, recipient, amount, leave_amount=0.1):
    """Send tokens between wallets"""
    try:
        balance = get_balance(client, sender_wallet.address())
        if balance <= leave_amount:
            print(f"⚠️ Insufficient balance (has {balance}, needs {leave_amount})")
            return False
        
        amount_to_send = min(amount, balance - leave_amount)
        tx = Transaction()
        tx.add_bank_transfer(recipient, amount_to_send, "ubbn")
        
        tx = client.finalize_and_broadcast(tx, sender_wallet)
        print(f"✅ Sent {amount_to_send}ubbn to {recipient[:10]}...")
        print(f"   Tx Hash: {tx.tx_hash}")
        return True
    except Exception as e:
        print(f"❌ Transaction failed: {str(e)}")
        return False

def many_to_one(client):
    """Consolidate funds from multiple wallets to one"""
    print("\n🔀 MANY-TO-ONE TRANSFER MODE")
    try:
        with open("seed.txt") as f:
            seeds = [s.strip() for s in f.readlines() if s.strip()]
    except FileNotFoundError:
        print("❌ seed.txt not found")
        return
    
    if not seeds:
        print("❌ No seed phrases found in seed.txt")
        return
    
    recipient = input("Enter recipient Babylon address: ").strip()
    if not validate_babylon_address(recipient):
        print("❌ Invalid Babylon address format (should start with bbn1 or babylon1)")
        return
    
    for seed in seeds:
        try:
            wallet = get_wallet_from_seed(seed)
            balance = get_balance(client, wallet.address())
            print(f"\n🏦 Wallet: {wallet.address()}")
            print(f"   Balance: {balance}ubbn")
            
            if balance > 0.1:
                if not send_tokens(client, wallet, recipient, balance):
                    print("   Skipping this wallet due to error")
            else:
                print("   Skipping - insufficient balance")
        except Exception as e:
            print(f"❌ Error processing wallet: {str(e)}")

def one_to_many(client):
    """Distribute funds from one wallet to many"""
    print("\n🔀 ONE-TO-MANY TRANSFER MODE")
    sender_seed = input("Enter sender seed phrase: ").strip()
    if not sender_seed:
        print("❌ No seed phrase provided")
        return
    
    try:
        with open("wallet.txt") as f:
            recipients = [r.strip() for r in f.readlines() if r.strip()]
    except FileNotFoundError:
        print("❌ wallet.txt not found")
        return
    
    if not recipients:
        print("❌ No recipient addresses found in wallet.txt")
        return
    
    try:
        amount = float(input("Enter amount to send to each recipient (in ubbn): ").strip())
        if amount <= 0:
            print("❌ Amount must be positive")
            return
    except ValueError:
        print("❌ Invalid amount")
        return
    
    try:
        wallet = get_wallet_from_seed(sender_seed)
        sender_balance = get_balance(client, wallet.address())
        total_needed = amount * len(recipients)
        
        print(f"\n👤 Sender: {wallet.address()}")
        print(f"   Balance: {sender_balance}ubbn")
        print(f"   Needed: {total_needed}ubbn ({len(recipients)} recipients)")
        
        if sender_balance < total_needed + 0.1:
            print("❌ Insufficient funds (need to leave 0.1 ubbn)")
            return
        
        for i, addr in enumerate(recipients, 1):
            print(f"\nRecipient {i}/{len(recipients)}: {addr[:10]}...")
            if not validate_babylon_address(addr):
                print("⚠️ Invalid address format, skipping")
                continue
            send_tokens(client, wallet, addr, amount)
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")

def main():
    try:
        client = LedgerClient(BABYLON_CONFIG)
        print("\n" + "="*40)
        print(" BABYLON-2 TOKEN TRANSFER BOT")
        print("="*40)
        
        while True:
            print("\nOPTIONS:")
            print("1. Many wallets → One wallet (Consolidate funds)")
            print("2. One wallet → Many wallets (Distribute funds)")
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
    except Exception as e:
        print(f"❌ Failed to initialize client: {str(e)}")
        print("Please check your RPC configuration and network connection")

if __name__ == "__main__":
    main()
