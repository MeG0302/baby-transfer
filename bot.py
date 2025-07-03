import os
import requests
import time
from dotenv import load_dotenv
from cosmpy.aerial.wallet import LocalWallet
from cosmpy.aerial.client import LedgerClient, NetworkConfig
from cosmpy.aerial.tx import Transaction
from cosmpy.crypto.keypairs import PrivateKey
from bip32utils import BIP32Key
from mnemonic import Mnemonic

# Load environment variables
load_dotenv()

# Babylon Testnet configuration with verified RPC endpoints
RPC_ENDPOINTS = [
    "https://babylon-testnet-rpc.polkachu.com",
    "https://rpc.babylon-2.btc.com",
    "https://babylon-testnet-rpc.nodes.guru"
]

def get_working_rpc():
    """Find first working RPC endpoint with balance API"""
    for endpoint in RPC_ENDPOINTS:
        try:
            test_addr = "bbn1hf9zkqvtfwwfn7e3cw8zwenxgrhfkyqsth22fw"  # Sample Babylon address
            status = requests.get(f"{endpoint}/status", timeout=5)
            balance = requests.get(
                f"{endpoint}/cosmos/bank/v1beta1/balances/{test_addr}/by_denom?denom=ubbn",
                timeout=5
            )
            if status.status_code == 200 and balance.status_code in [200, 404]:
                print(f"✅ Verified RPC: {endpoint}")
                return endpoint
        except Exception:
            continue
    raise ConnectionError("❌ No working RPC endpoint found.")

# Initialize RPC and network config
working_rpc = get_working_rpc()
BABYLON_CONFIG = NetworkConfig(
    chain_id="bbn-test-5",
    url=f"rest+{working_rpc}",
    fee_minimum_gas_price=0.0025,
    fee_denomination="ubbn",
    staking_denomination="ubbn",
)

def get_wallet_from_seed(seed_phrase):
    """Create Babylon wallet from seed phrase with correct bbn prefix"""
    try:
        mnemo = Mnemonic("english")
        seed = mnemo.to_seed(seed_phrase)
        bip32_root = BIP32Key.fromEntropy(seed)
        bip32_child = bip32_root.ChildKey(44 + 0x80000000) \
                               .ChildKey(118 + 0x80000000) \
                               .ChildKey(0 + 0x80000000) \
                               .ChildKey(0) \
                               .ChildKey(0)
        wallet = LocalWallet(PrivateKey(bip32_child.PrivateKey()))
        wallet.set_bech32_prefix("bbn")  # Force correct prefix
        return wallet
    except Exception as e:
        raise Exception(f"Wallet creation failed: {str(e)}")

def get_balance(address):
    """Query wallet balance with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(
                f"{working_rpc}/cosmos/bank/v1beta1/balances/{address}/by_denom?denom=ubbn",
                timeout=10
            )
            if response.status_code == 200:
                return float(response.json()['balance']['amount'])
            elif response.status_code == 404:
                return 0.0
            raise Exception(f"API returned {response.status_code}")
        except Exception as e:
            if attempt == max_retries - 1:
                raise Exception(f"Balance query failed: {str(e)}")
            time.sleep(2)

def send_tokens(client, sender_wallet, recipient, amount, leave_amount=0.1):
    """Send tokens with error handling"""
    try:
        balance = get_balance(sender_wallet.address())
        if balance <= leave_amount:
            print(f"⚠️ Insufficient balance (has {balance}, needs {leave_amount})")
            return False
        
        amount_to_send = min(amount, balance - leave_amount)
        tx = Transaction()
        tx.add_bank_transfer(recipient, amount_to_send, "ubbn")
        
        tx = client.finalize_and_broadcast(tx, sender_wallet)
        print(f"✅ Sent {amount_to_send}ubbn to {recipient}")
        print(f"   Tx Hash: {tx.tx_hash}")
        return True
    except Exception as e:
        print(f"❌ Transaction failed: {str(e)}")
        return False

def many_to_one(client):
    """Transfer all funds from many wallets to one recipient"""
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
    
    recipient = input("Enter recipient address: ").strip()
    if not recipient:
        print("❌ No recipient address provided")
        return
    
    for seed in seeds:
        try:
            wallet = get_wallet_from_seed(seed)
            address = wallet.address()
            balance = get_balance(address)
            
            print(f"\n🏦 Wallet: {address}")
            print(f"   Balance: {balance}ubbn")
            
            if balance > 0.1:
                if not send_tokens(client, wallet, recipient, balance):
                    print("   Skipping due to error")
            else:
                print("   Skipping - insufficient balance")
        except Exception as e:
            print(f"❌ Error processing wallet: {str(e)}")

def one_to_many(client):
    """Send fixed amount from one wallet to many recipients"""
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
        sender_balance = get_balance(wallet.address())
        total_needed = amount * len(recipients)
        
        print(f"\n👤 Sender: {wallet.address()}")
        print(f"   Balance: {sender_balance}ubbn")
        print(f"   Needed: {total_needed}ubbn ({len(recipients)} recipients)")
        
        if sender_balance < total_needed + 0.1:
            print("❌ Insufficient funds (need to leave 0.1 ubbn)")
            return
        
        for i, addr in enumerate(recipients, 1):
            print(f"\nRecipient {i}/{len(recipients)}: {addr}")
            send_tokens(client, wallet, addr, amount)
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
            print("\nOPTIONS:")
            print("1. Consolidate funds (Many wallets → One wallet)")
            print("2. Distribute funds (One wallet → Many wallets)")
            print("3. Exit")
            
            choice = input("Select option (1-3): ").strip()
            
            if choice == "1":
                many_to_one(client)
            elif choice == "2":
                one_to_many(client)
            elif choice == "3":
                print("\n👋 Exiting...")
                break
            else:
                print("❌ Invalid choice")
    except Exception as e:
        print(f"\n❌ Critical error: {str(e)}")
        print("Please check:")
        print("- Internet connection")
        print("- RPC endpoint status")
        print("- Seed phrase validity")
    finally:
        print("\nOperation completed.")

if __name__ == "__main__":
    main()
